# Drought Intelligence n8n workflow registry

This registry is the planning source of truth for the local development n8n
instance. A workflow may not be scheduled until it has a tracked definition,
passed a manual end-to-end test, and has a row here marked **schedule-ready**.
All schedule times use `Africa/Addis_Ababa`.

## Contract rules

- Source and evidence workflows may call only fixed, internal
  `tsird-drought-runner` endpoints. The separately named, manual Production
  Publisher is the sole exception: it invokes only its tracked fixed-purpose
  OpenSSH script, which accepts one approved release ID and one verified VPS
  host; it has no runner, source-retrieval, or schedule path.
- New canonical workflows read job state from `GET /runs/{job_id}`. The older
  `GET /runs/development-test/{job_id}` endpoint remains compatibility-only.
- The runner permits only one active job. Schedules must not overlap; a 409
  busy response is a deferred run, not a retry storm.
- A source probe can run daily. A heavy acquisition runs only when the probe
  detects a new or revised source timestamp.
- The WaPOR probe compares the latest provider dekad with its local manifest:
  `ready` starts a refresh, `current` ends the run without downloading, and
  `degraded` records a stale-provider condition.
- The CHIRPS preliminary probe compares the latest provider pentad with the
  final pentad in a valid local six-pentad manifest. `current` is therefore a
  normal no-summary outcome; only `ready` may later enter a reviewed summary
  branch.
- A successful run records source time, freshness, status, output count and
  run ID. It never logs credentials or source payloads in n8n.

## Canonical workflow plan

| Key | Canonical workflow | Fixed endpoint(s) | Proposed cadence | Status |
| --- | --- | --- | --- | --- |
| `chirps-final` | CHIRPS final monthly refresh v1 | provider-discovered final-month probe, then fixed calendar refresh | Daily 08:00 Addis; process only a new completed final month | **Active locally.** Discovery never downloads; a run-specific raster replaces the current display only after provider validation and database load succeed. |
| `chirps-rapid` | CHIRPS rapid source probe v1 | preliminary probe | Daily 06:30 probe; process only new pentad | **Active locally.** Manual receipt and busy-run rejection passed. The workflow records a redacted receipt in n8n; it does not publish a drought class. |
| `ndvi` | CDSE NDVI source probe v1 | latest-item metadata probe | Daily 06:45 candidate; process only a `ready` 10-daily item | **Active locally.** Metadata-only. A `degraded` or `current` result downloads nothing; acquisition remains a separately reviewed branch. |
| `swi` | CDSE SWI source probe v1 | latest-item metadata probe | Daily 06:50 candidate; process only a `ready` 10-daily item | **Active locally.** Metadata-only. A `degraded` or `current` result downloads nothing; acquisition remains a separately reviewed branch. |
| `lst` | CLMS LST v3 summary v1 | future LST v3 access and summary | Daily probe; process new 10-daily synthesis | Blocked: replace superseded v2 source |
| `wapor` | WaPOR crop water-use v1 | WaPOR probe, then T/AETI summary | Daily 07:00 probe; process only a `ready` dekad | **Active locally.** The provider gate prevents download when the local dekad is current or the source is degraded. |
| `chirps-final-fixture` | CHIRPS final monthly rainfall verification fixture v1 | fixed June--July 2026 final-rainfall development check | Manual development verification; no schedule activated | Superseded test fixture, retained only as evidence of the initial acquisition/validation/load chain. It is not a recurring workflow. |
| `ndvi-summary` | CDSE NDVI Tabia evidence v1 | one bounded native-grid NDVI raster and Tabia summary | Manual development verification; no schedule activated | Tracked and inactive. Historical backfill uses the same acquisition/load path with real catalogue timestamps. |
| `lst-history` | CLMS LST v2 historical evidence | bounded historical raster and Tabia summary | Manual history only; no schedule activated | Tracked and inactive. LST v2 is superseded upstream, so it cannot be promoted to a recurring current-data workflow without a reviewed replacement product. |
| `seasonal-outlook` | ICPAC seasonal outlook probe v1 | ICPAC catalogue probe only | Weekly Monday 07:10 candidate; no data acquisition | Tracked but inactive; the probe cannot scrape map imagery or publish a forecast. A reviewed machine-readable asset, licence, issue date, validity period, and native geography are required before a loader is built. |
| `c3s-seasonal` | C3S seasonal forecast access probe v1 | one temporary CDS precipitation subset | Monthly candidate, day 15 at 08:30 Addis; no schedule activated | Tracked and inactive. It verifies CDS access and accepted dataset terms only; the file is deleted immediately. Matched hindcasts, skill assessment, probability method, and a reviewed native-grid publication contract are required before an Outlook loader is considered. |
| `c3s-hindcast` | C3S matched hindcast availability probe v1 | one temporary ECMWF System 51 precipitation hindcast subset | Manual development gate; no schedule activated | Tracked and inactive. It confirms only that one hindcast request is available using the same system as the access probe; it deletes the file and cannot calculate skill, define probabilities, or publish an Outlook. |
| `c3s-skill-pilot` | C3S–CHIRPS seasonal skill pilot v1 | fixed 1993–2016 August ECMWF System 51 / CHIRPS regional comparison | Manual development study; no schedule activated | Tracked and inactive. It deletes source rasters and retains annual regional summaries plus leave-one-year-out tercile Brier diagnostics. It is not Woreda/Tabia skill, calibration, a provider-issued forecast, or a public Outlook. |
| `fews-net-food-security` | FEWS NET public classification discovery v1 | official Ethiopia publication and linked-asset metadata only | Weekly availability check pending local n8n activation; no automatic provider-geometry retention | The loader retains the reviewed January--July 2026 native-FSC issues for the historical comparison view. The future check remains a provider-catalogue gate until an explicit release-selection and validity-period rule is approved. No Tabia crosswalk or TSIRD food-security class is created. |
| `storage-inventory` | Drought storage inventory v1 | read-only storage inventory | First day of month, 07:15 | **Active locally.** Read-only; it never archives or deletes. Capacity status is reviewed in Pipeline Control and n8n execution history. |
| `automatic-indicator-publisher` | Automatic retained indicator publisher v1 | fixed local API reads, fixed display-ready raster package, pinned-host SFTP and `activate-indicators` | Daily 10:30 Addis after a manual end-to-end rehearsal | Tracked and inactive. It coalesces complete source-derived evidence, avoids duplicates with a persistent fingerprint, and can advance only the separate public indicator pointer. |

## Existing inactive n8n workflow records

The n8n instance includes five prior CHIRPS refresh variants. They remain
inactive as compatibility history and must not be scheduled:

| n8n ID | Name | Disposition |
| --- | --- | --- |
| `llf9vD94USCsxhQr` | CHIRPS Tabia refresh | Superseded; has an old inactive monthly trigger. |
| `eVpYidLMyU02MLSW` | CHIRPS Tabia refresh v2 | Superseded. |
| `szx3aFo5M83grg3y` | CHIRPS Tabia refresh v3 | Superseded. |
| `eoGcHfWP8kdRiwyb` | CHIRPS Tabia refresh v4 | Superseded. |
| `LbA5gOvfTqCEIuhF` | CHIRPS Tabia refresh v5 | Superseded. |

The current manual CHIRPS rapid (`ZpvgyY8PHVJiWYyt`), CDSE, and WaPOR
workflows are reference implementations only until their tracked workflow
definition, status-route convention, and manual test receipt agree.

The current tracked metadata-only CDSE probe records are imported locally but
remain unpublished/inactive:

| n8n ID | Name | Manual result |
| --- | --- | --- |
| `Fzx2NRkkqoqv72zG` | CDSE NDVI source probe v1 (development) | `degraded` freshness receipt; no acquisition or publication |
| `paMEAIeZkmLcgsav` | CDSE SWI source probe v1 (development) | `degraded` freshness receipt; no acquisition or publication |

## Current scheduling decision

Six local-only, bounded workflows are active as of 2026-09-14: calendar-aware
CHIRPS final monthly refresh, CHIRPS rapid, NDVI metadata, SWI metadata,
WaPOR’s provider-gated refresh, and monthly storage inventory. Their
operational notice is deliberately local: the n8n execution record plus
Pipeline Control’s redacted source receipt. There is no email, external
webhook, automatic retry storm, or VPS action.

| n8n ID | Active workflow | Trigger |
| --- | --- | --- |
| `Rv68djQkbK16AmSf` | CHIRPS rapid source probe v1 | Daily 06:30 Addis |
| `gHJ43eNNcRyMs1AF` | CHIRPS final monthly refresh v1 | Daily 08:00 Addis |
| `Fzx2NRkkqoqv72zG` | CDSE NDVI source probe v1 | Daily 06:45 Addis |
| `paMEAIeZkmLcgsav` | CDSE SWI source probe v1 | Daily 06:50 Addis |
| `ZmPT6StaKMtWlpNM` | WaPOR crop water-use v1 | Daily 07:00 Addis |
| `WHt7tJ7U3DGQ4k8f` | Drought storage inventory v1 | Day 1, 07:15 Addis |

The final-month CHIRPS endpoint accepts a parameterized request, but its
development-test shortcut is deliberately fixed to June–July 2026. A future
schedule must call a calendar-aware, fixed-purpose endpoint that selects only
the latest eligible final month and records the chosen month in its receipt.
It must not put a token or an arbitrary date expression in an n8n workflow.

NDVI and SWI now have metadata-only source-state endpoints. Their first
successful checks found already-summarized catalogue items that exceeded the
15-day freshness threshold, so both were correctly recorded as `degraded`.
They must not trigger a summary while degraded. A future workflow may enter a
summary branch only for a `ready` item and after its schedule/error policy is
reviewed.

The local no-overlap test ran the WaPOR probe while requesting the CHIRPS
rapid probe. The runner completed the first probe and rejected the second
request as busy before creating a second job. The published artifact directory
remained unchanged. This confirms the runner-level serialization gate; it does
not replace source-specific acquisition failure testing.

## Activation gate

Before any workflow becomes active:

1. Validate the JSON definition and import it into n8n.
2. Execute it manually and retain a redacted success/failure receipt.
3. Confirm it does not overlap an active job and correctly preserves the last
   valid artifact after a simulated source or processing failure.
4. Confirm its retention/export controls and failure notification destination.
5. Change this registry row to **schedule-ready**, then activate only the
   reviewed schedule trigger.

## Manual Production Publisher (tracked template; not imported or configured)

`production-publisher` is a tracked, inactive **manual-only** n8n workflow
template, not a source-retrieval workflow and not a production schedule. It
has no current n8n ID, configured production credential, or production-network
route. It uses a fixed OpenSSH publisher script and a separately verified
production host key rather than the installed n8n SFTP/SSH nodes, which do not
expose host-key pinning. Its exact import/binding/staging procedure is in
[n8n production publisher setup](n8n-production-publisher-setup.md).

It may be imported only after a compact release directory passes
[`production-release-contract.md`](production-release-contract.md), a named
approver changes its manifest from `validated` to `approved`, and a separate
least-privilege SFTP/SSH account is provisioned for the production release-data
path. It will upload to a new versioned release directory, verify remote
checksums, and switch a small current-release pointer. It must never retrieve
data, build images, run a remote shell, publish raw rasters, alter the priority
model, or accept arbitrary destination/command parameters.

The template permits one manual release ID, one verified production host, and
exactly seven compact package files. The fixed script performs SFTP upload to
the restricted ingress account, then issues the forced
`activate <release-id>` request. The VPS repeats approval/checksum validation
before changing its pointer. It cannot create a release, retrieve data, build
images, execute an arbitrary remote command, remove files, or schedule itself.
Until the credentials are bound and a named approver supplies a package, it
remains an inactive local import template.

## Automatic indicator publisher (tracked template; not yet activated)

The automatic indicator publisher is separate from the reviewed-release
publisher. It accepts only the verified production host, uses the existing
least-privilege keys and pinned server identity, and has no user-supplied
release ID, path, source URL, model option or remote command. It reads only the
fixed six development summary endpoints and the read-only display-ready raster
folder, makes a checksum-validated nine-asset package, and calls only the
forced `activate-indicators <release-id>` command. Its persistent fingerprint
means an unchanged daily check does not upload or activate another package.

Its setup and mandatory first rehearsal are in
[n8n automatic indicator publisher setup](n8n-automatic-indicator-publisher-setup.md).
