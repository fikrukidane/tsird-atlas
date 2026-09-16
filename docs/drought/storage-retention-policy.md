# Drought Intelligence local storage and retention policy

Status: development policy. It governs the local PowerMachine evidence store;
it does not authorize VPS storage, automatic archival, or deletion.

## Purpose

The Atlas needs durable, inspectable Tabia evidence history while keeping large,
reproducible raster inputs bounded. The governing principle is:

> Preserve provenance and Tabia summaries for analysis; retain only the
> minimum raster evidence required for map rendering, validation, and recovery.

Every retention decision must preserve the source timestamp, source/product
version, boundary version, run ID, quality/coverage result, and checksum. A
retention action must never remove the only validated artifact for an indicator.

## Tiers and proposed local retention

| Tier | Examples | Proposed retention | Action in this phase |
| --- | --- | --- | --- |
| Durable evidence history | Tabia source values, provenance, quality state, run receipts | Keep for the life of the program; review after 10 years | Append only; no automatic deletion. |
| Static reference baselines | WorldCover 2021, WorldPop reference raster, roads, boundaries, DEM/slope | Keep until a documented replacement is validated | Version rather than overwrite. |
| Published map artifacts | Latest validated raster and tabular map views for each indicator | Latest artifact plus 12 monthly snapshots where source cadence permits | Keep existing artifacts; no automatic pruning. |
| Raw dynamic inputs | CHIRPS, CDSE, WaPOR T/AETI clipped Tigray windows | 180 days after a validated replacement; retain one input per published snapshot | Report candidates only; no archive/delete job exists. |
| Processing cache | Reprojection tiles, temporary downloads, intermediate windows | 30 days after successful validation | Report candidates only; no archive/delete job exists. |
| Workflow execution records | n8n execution metadata and redacted runner receipts | n8n: 30 days; durable receipt/provenance: keep with evidence history | Existing n8n pruning remains enabled; no runner log deletion. |

"180 days" is intentionally conservative for the first operating season. It
allows method review, provider revision comparison, and replay of recent runs
without treating re-downloadable rasters as permanent archives. It may only be
shortened after measured source-size and recovery testing.

## Capacity safeguards

The read-only inventory is the authority for local drought-data capacity. As of
2026-09-10 it measured approximately 416 MiB managed data and approximately
563 GiB free filesystem space. The initial triggers are:

| State | Condition | Required operator response |
| --- | --- | --- |
| Normal | More than 100 GiB and more than 20% filesystem free | Continue controlled ingestion. |
| Warning | 50–100 GiB free, or 10–20% free | Review the storage inventory before any new backfill or source expansion. |
| Critical | Less than 50 GiB free, or less than 10% free | Do not start new heavy backfills. Prepare a reviewed archive proposal. |
| Stop | Less than 25 GiB free, or less than 5% free | Block heavy acquisitions until capacity is restored through an approved, recoverable action. |

The monthly n8n capacity workflow remains read-only. Before it becomes
scheduled, its receipt must be reviewed in n8n and its warning/critical state
must be visible in Pipeline Control. Email notification is deferred by the
operator and is not currently a replacement for that review.

## Archive process — deliberately not automated yet

When a tier reaches its review point, the operator must:

1. Generate a read-only candidate inventory: path, age, indicator, run ID,
   checksum, and replacement artifact reference.
2. Confirm that durable Tabia summaries/provenance and the newest validated
   map artifact remain available.
3. Copy candidates to a named, checksum-verified archive destination.
4. Verify the archive can be read and its manifest matches the source list.
5. Obtain explicit approval for any removal from the live data mount.

No n8n workflow, runner endpoint, or dashboard control may perform steps 3–5
until that approval is granted. A mere backup file is not evidence of a
recoverable archive.

## Storage planning checkpoints

Before enabling a new acquisition workflow, record its first three actual run
sizes and processing-output sizes. Update the capacity forecast using measured
values, not global source resolution alone. Review the forecast before adding:

- a historical backfill beyond the bounded Copernicus test history;
- a new high-resolution or hourly product;
- full-resolution map archives instead of current-plus-snapshot artifacts; or
- any production/VPS replication.

This keeps the local PowerMachine as the computational and evidence-preparation
environment, with any future VPS receiving only reviewed, compact published
artifacts and durable summaries.
