# Drought source-refresh reliability contract (v2 workflow templates)

Status: tracked development templates. They are **not imported, activated or
executed** by the change that introduced them. Importing, rehearsing and
activating them is a separate, deliberate step on the development machine.

These templates replace the probe-only behaviour of the v1 definitions for the
four recurring sources. The v1 files remain tracked, unchanged, as the record
of what ran until 2026-09.

## Why v2 exists

The v1 CHIRPS rapid, NDVI and SWI workflows called a metadata probe and stopped,
whatever the probe found. A `ready` result produced a receipt and no data. The
v1 WaPOR workflow did start an acquisition, but it read the runner job exactly
once after a fixed 60-second wait, so a longer job was recorded in whatever
state it happened to be in at that moment and was never followed up.

Both patterns report "success" for a run that changed nothing. A monitor
watching workflow status alone cannot tell a healthy no-op from a silent stall.

## The three run outcomes

Every v2 run ends in exactly one terminal node, and every terminal node writes
the same receipt shape (`schema_version: tsird-drought-source-refresh-receipt/v2`).
The field that matters is `run_outcome`:

| `run_outcome` | Meaning | `outcome_detail` values | `evidence_changed` | `action_required` |
| --- | --- | --- | --- | --- |
| `no_new_data` | The provider probe completed and found nothing newer to retain. | `provider_has_no_newer_item` | false | true only when `provider_state` is `degraded` |
| `data_updated` | A newer provider item was acquired, validated, loaded into PostGIS and synchronised to the current display raster. | `acquired_validated_loaded` | true | true only when the artifact status is `degraded` |
| `failure` | The run could not establish either of the above. | `runner_unavailable_or_busy`, `probe_failed`, `probe_poll_budget_exhausted`, `acquisition_not_started`, `acquisition_failed`, `acquisition_poll_budget_exhausted` | false | true |

`provider_state` carries the runner's own probe vocabulary unchanged:
`ready`, `current`, `degraded`, `unavailable`. A `current` or `degraded` probe
is a normal operational answer, not an error.

## Shape of each workflow

```
manual trigger ─┐
schedule ───────┴─► Start source probe (POST probe endpoint)
                      └─ not HTTP 202 ─► Report runner unavailable        (failure)
                      └─ HTTP 202 ─► Wait ──► Read probe job ──► still running?
                                       ▲                          │yes ─► budget left? ─┐
                                       └──────────────────────────┘                     │no
                                                                   │no                  ▼
                                                                   ▼         Report probe timeout (failure)
                                                          newer data available?
                                                            │no ─► provider state known?
                                                            │        ├─ current/degraded ─► Report no new data
                                                            │        └─ otherwise ───────► Report probe failure
                                                            │yes
                                                            ▼
                                                   Start acquisition (POST summary endpoint)
                                                     └─ not HTTP 202 ─► Report acquisition rejected (failure)
                                                     └─ HTTP 202 ─► Wait ─► Read acquisition job ─► still running?
                                                                      ▲                               │yes ─► budget left? ─┐
                                                                      └───────────────────────────────┘                     │no
                                                                                        │no                                 ▼
                                                                                        ▼                    Report acquisition timeout (failure)
                                                                               acquisition failed?
                                                                                 ├─ yes ─► Report acquisition failure (failure)
                                                                                 └─ no ──► Report data updated (data_updated)
```

Both HTTP calls use `fullResponse` with `neverError`, so an HTTP status is data
to branch on rather than a node exception. Node-level `retryOnFail` (3 tries,
5 s apart) therefore covers only connection-level faults, which is the only
class of fault where an immediate retry is appropriate. A runner that answers
HTTP 409 (another drought job is active) is recorded as a deferred run, not
retried: the next scheduled cycle picks it up.

## Bounded polling and backoff

Polling is bounded in two independent ways: a growing wait and a hard attempt
budget enforced by a `$runIndex` guard on the loop edge.

- Probe loop: `min(30, 5 × (attempt + 1))` seconds.
- Acquisition loop: `min(60, 15 × (attempt + 1))` seconds.

Each budget is set **longer than the runner's own timeout** for that job, so a
budget-exhausted verdict means the runner itself should already have given up.
That makes the timeout outcomes meaningful rather than routine.

| Source | Schedule (Africa/Addis_Ababa) | Probe endpoint | Acquisition endpoint | Probe budget | Acquisition budget |
| --- | --- | --- | --- | --- | --- |
| CHIRPS preliminary pentad | 06:30 daily | `/runs/chirps-preliminary-pentad/development-test` | `/runs/chirps-preliminary-pentad-summary/development-test` | 25 attempts ≈ 11.2 min (runner cap 10 min) | 75 attempts ≈ 73.5 min (runner cap 70 min) |
| Copernicus NDVI | 06:45 daily | `/runs/ndvi-source-probe/development-test` | `/runs/ndvi-tabia-summary/development-test` | 8 attempts ≈ 2.8 min (runner cap 2 min) | 45 attempts ≈ 43.5 min (runner cap 40 min) |
| Copernicus SWI | 06:50 daily | `/runs/swi-source-probe/development-test` | `/runs/swi-tabia-summary/development-test` | 8 attempts ≈ 2.8 min (runner cap 2 min) | 45 attempts ≈ 43.5 min (runner cap 40 min) |
| FAO WaPOR T/AETI | 07:00 daily | `/runs/wapor-probe/development-test` | `/runs/wapor-tabia-summary/development-test` | 14 attempts ≈ 5.8 min (runner cap 5 min) | 75 attempts ≈ 73.5 min (runner cap 70 min) |

Every URL above already exists in `etl/drought/runner.py`. No provider URL,
credential or new endpoint is introduced by these templates. The runner's
single-job lock still serialises everything, so the 15-minute spacing between
the four schedules remains deliberate.

## Expected freshness per source

Freshness thresholds live in the runner's probe scripts and in
`model_readiness.py`; the workflows do not restate or override them.

| Source | Provider cadence | Retained cadence today | Probe freshness threshold |
| --- | --- | --- | --- |
| CHIRPS preliminary | pentadal | one six-pentad window | 10 days |
| NDVI (CLMS v3) | 10-daily | one snapshot per month | 15 days |
| SWI (CLMS v4) | 10-daily | one snapshot per month | 15 days |
| WaPOR v3 L2 | dekadal | one dekad per month (D3) | 25 days |

A run that ends `no_new_data` with `provider_state: degraded` is the signal that
a provider has gone quiet for longer than its own cadence allows. That is the
condition worth alerting on, and it is distinct from a failure.

## Failure behaviour

- No terminal path deletes, overwrites or rolls back retained evidence. The
  previous valid artifact stays current until a complete acquisition succeeds.
- A failure never triggers an immediate re-run. The next scheduled cycle is the
  retry, which keeps a provider outage from becoming a request storm.
- The two timeout outcomes state explicitly that the runner job may still be
  running. They instruct an operator to read the job rather than start a second
  one, because the runner permits only one active job and a duplicate request
  would simply be rejected.
- `action_required` is the single boolean an alerting rule should read. It is
  false for a healthy no-op and true for every failure and every degraded state.

## What a successful run proves

A `data_updated` receipt proves that, for that source: one newer provider item
was retrieved into the local evidence store, its Tabia summary was derived and
validated, the summary rows were loaded into PostGIS, and the current display
raster was re-synchronised from the same run. The receipt carries the runner
`run_id` and the artifact status so the claim can be checked against the
database and the published raster.

It does **not** prove that the evidence is fresh enough to use, that coverage is
adequate, or that any downstream public release happened. Freshness and coverage
remain the readiness gate's job, and publication remains the publisher's.

A `no_new_data` receipt proves only that the provider was reachable and had
nothing newer. It is not evidence that the pipeline as a whole is healthy, which
is why the receipt records `checked_at` on every run.

## What these templates deliberately do not do

- They do not notify. There is no email, webhook or chat node, by design: the
  receipt is the machine-readable surface an external watcher should read.
- They do not publish to production, touch the release pointer, or call the
  indicator publisher.
- They do not change any model, threshold, classification or public data
  contract.
- They carry no workflow `id`, so importing one creates a new workflow instead
  of overwriting a live definition. Retiring the matching v1 workflow is a
  separate, deliberate operator step.

## Static validation

`tools/validate_n8n_workflows.py` checks every tracked definition without
contacting anything: JSON validity, absence of credential material, node-name
uniqueness, connection integrity, expression references to real nodes, and that
every HTTP URL resolves to a route that actually exists in the tracked runner.
For `*-v2.development.json` it additionally requires all three run outcomes,
expression-based backoff on every wait node, a `$runIndex` budget guard on every
poll loop, and both outputs wired on every IF node.

```bash
python3 tools/validate_n8n_workflows.py
```

## Required live rehearsal before activation

Static validation cannot prove runtime behaviour. On the development machine,
with the runner reachable, each template needs one manual rehearsal that
confirms, per source:

1. A `current` probe ends in `Report no new data` without starting an
   acquisition.
2. A `ready` probe starts exactly one acquisition and ends in
   `Report data updated` with a `run_id` that exists in PostGIS.
3. A deliberately busy runner (409) ends in `Report runner unavailable` or
   `Report acquisition rejected`, and no second job is created.
4. The loop expressions evaluate as intended on the installed n8n version,
   in particular `$runIndex` inside the Wait node's `amount` field and the
   `$('Start source probe').item.json.body.job_id` reference after a retry.
5. The schedule trigger's timezone resolves to Africa/Addis_Ababa with the
   workflow-level `timezone` setting these templates carry.

Only after those five checks should a v2 workflow be activated, and only
alongside retiring its v1 counterpart.
