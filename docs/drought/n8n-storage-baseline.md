# Local n8n and drought-storage baseline

Inspected locally on 2026-09-09. This is a development-only baseline; it does
not certify a VPS deployment or authorize a production schedule.

## Verified topology

- `powermachine-n8n` runs n8n 2.6.4, is healthy, and is bound only to
  `127.0.0.1:5678` on the host.
- It has persistent bind mounts for `/home/node/.n8n` and `/workflows`.
- It is joined to `tsird-network`, where it can reach the internal
  `tsird-drought-runner`; the runner has no host port and no Docker socket.
- n8n is configured for `Africa/Addis_Ababa`, regular execution mode, a
  30-day execution-data pruning policy, and blocked node environment access.
  Diagnostics and personalization are disabled. `N8N_SECURE_COOKIE=false` is
  acceptable only for local HTTP on loopback; a future HTTPS deployment must
  enable secure cookies.
- The n8n persistence directory is approximately 5 MiB and uses the default
  SQLite database. Its database file, WAL file, configuration, and workflow
  exports require a coordinated local backup plan.

## Workflow baseline

There are 27 local workflows. Six bounded development workflows are active:
calendar-aware CHIRPS final monthly refresh, CHIRPS rapid source probe, NDVI
and SWI metadata probes, WaPOR’s provider-gated refresh, and read-only monthly
capacity inventory. The intended drought set
includes CHIRPS, NDVI, SWI, LST, and WaPOR fixed development endpoints. The
runner rejects concurrent work globally, which protects the local machine but
means schedules must be deliberately serialized.

Five superseded CHIRPS Tabia-refresh variants remain in n8n. They must not be
scheduled. The repository retains canonical tracked definitions for the active
workflows and inactive definitions for LST, Outlook, and forecast experiments.
Each active source has a fixed runner endpoint, a manual execution receipt,
and a recorded activation gate in `n8n-workflow-registry.md`.

## Drought-data footprint

The read-only runner inventory completed successfully after the first
historical evidence backfill on 2026-09-10. It measured 518,419,095 bytes
(approximately 494 MiB):

| Tier | Approximate size | Interpretation |
| --- | ---: | --- |
| WorldCover baseline | 230 MiB | Static 2021 reference input. |
| WorldPop baseline | 152 MiB | Static reference input. |
| Raw provider subsets | 96 MiB | Retained bounded January--August 2026 provider evidence inputs. |
| Published rasters | 9 MiB | Current map artifacts. |
| Cache, outputs, logs | 6 MiB | Receipts and derived summaries. |

The host had approximately 558 GiB free at inspection. Capacity is sufficient
for the proposed local-first design, but retention must be explicit before
enabling recurring ingestion.

The read-only Pipeline Control capacity safeguard currently classifies the
mount as `normal` (about 30% free). It reports only; it cannot start work,
archive data, or delete data.

The proposed tiered retention, capacity thresholds, and deliberately manual
archive process are recorded in [storage-retention-policy.md](storage-retention-policy.md).
No automated archive or deletion operation has been introduced.

## Hardening sequence

1. Establish a tracked workflow registry: workflow ID, owner, fixed endpoint,
   source, frequency, dependencies, timeout, retry policy, and retention.
2. Retain one canonical development workflow per source; label superseded
   n8n workflows as archived rather than deleting them during early testing.
3. Add fixed schedule candidates as inactive definitions and test every path
   manually end-to-end before activation.
4. Add no-overlap, freshness, success/failure receipt, and operator-notice
   controls. A failed or degraded refresh must preserve the last valid map.
5. Add storage reporting and retention: short-lived cache, retained raw and
   published artifacts, durable Tabia/provenance history, and a tested n8n
   SQLite/workflow export backup.
6. Review the n8n release lifecycle separately before any upgrade; the current
   instance reports its release is more than six weeks old. No upgrade is
   performed by this baseline.

The active storage workflow runs on the first of each month at 07:15 Addis
time. It only reports capacity and has no archive or deletion capability. The
active final-CHIRPS workflow runs daily at 08:00 Addis time: it discovers the
newest available completed final month first, then starts a bounded refresh
only when that month is not already retained. All other active workflows keep
their source-specific gates; none archives or deletes data.

Five source-state or capacity checks have also been exercised through the
local n8n editor against the local evidence store: CHIRPS rapid and WaPOR
reported their already-represented periods as `current`; NDVI and SWI reported
their stale catalogue items as `degraded`; and the capacity inventory
`succeeded` read-only. None downloaded, republished, archived, or deleted
data. These normal outcomes are required before the workflows can be
considered for a recurring schedule; they do not themselves authorize one.
