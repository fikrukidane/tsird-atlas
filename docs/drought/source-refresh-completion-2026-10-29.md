# Source-refresh completion — DEV implementation record

Date: 2026-10-29 (America/Chicago)

## Objective

Every dynamic drought-indicator source has a bounded DEV source check. A
check retrieves and retains a newer valid observation only when one exists;
otherwise it records `current`, `degraded`, or `unavailable` without replacing
the last valid artifact. Source acquisition remains separate from public
release publication.

## Implemented contracts

| Indicator | Source check | Acquisition condition | Retention / display rule |
| --- | --- | --- | --- |
| Final rainfall | Calendar-aware CHIRPS final probe | A new provider-final completed month | Store the run and refresh the stable display only after the database load succeeds. |
| Rapid rainfall | CHIRPS preliminary pentad probe | A newer valid six-pentad window | Retain the window and preserve final-rainfall evidence separately. |
| Vegetation | CLMS NDVI v3 catalogue probe | A fresh, unretained 10-daily item | Retain source timestamp and current provider-grid derivative. |
| Vegetation moisture | NASA HLS L30/S30 monthly probe | One newly eligible completed calendar month with CMR-STAC items | Resume the 748-Tabia, cloud/shadow-masked monthly composite from its compact checkpoint. |
| Soil water | CLMS SWI v4 catalogue probe | A fresh, unretained item | Retain the provider observation and its current derivative. |
| Crop water use | FAO WaPOR v3 dekad probe | A newer provider dekad | Retain transpiration/AETI evidence and current transpiration derivative. |
| Thermal | CLMS LST Daily Cycle 3 km 10-daily V3 catalogue probe | A fresh, unretained 10-daily item | Retain temperature context and FOBS observation fraction; V2 stays history-only. |

The HLS workflow is deliberately bounded: it probes daily at 07:15 Addis,
acquires no earlier than the sixth day of a month, and starts at most one
resumable all-Tabia job. A busy runner is recorded as deferred; it does not
start overlapping work.

The LST V3 replacement uses Copernicus collection
`7f175dfe-eee2-4c4c-93a6-db8072e76a44`. `MEDIAN` is represented in Celsius as
the raw value times `0.01`: its documented physical representation applies a
`+273.15 K` offset, which must not be subtracted twice. `FOBS` is retained in
the new `fobs_mean` field rather than being relabelled as V2 PPP.

## Safety boundaries

- All new endpoints are internal-only `tsird-drought-runner` endpoints.
- Source schedules start no raw data archive, production deployment, forecast,
  model scoring, allocation, or response action.
- A failed, unavailable, degraded, or busy receipt leaves the existing
  retained artifact unchanged.
- The public indicator publisher remains a separate validation and
  publication step; no source workflow can write production directly.

## Verification still required before schedule activation

1. Rebuild the local DEV runner/API/web with the same `tsird-atlas` Compose
   project, named PostGIS volume, shared `data` directory and environment
   files. The DEV overlay is `docker-compose.source-refresh.override.yml`.
2. Apply `20261029_add_drought_lst_v3_fobs.sql` once to the existing DEV
   database.
3. Run the HLS workflow manually; with the retained September artifact it
   should finish as `current` and start no acquisition.
4. Run the thermal V3 workflow manually; verify its catalogue probe, one
   bounded acquisition, 748 retained Tabia rows, current raster, Celsius
   range, and FOBS field.
5. Activate only the reviewed HLS and thermal V3 workflow definitions, then
   record their n8n IDs and first receipts in the workflow registry.
6. Run the automatic indicator publisher only after all retained-source and
   release validation checks pass. Production remains unchanged until then.
