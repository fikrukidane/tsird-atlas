# TSIRD — Tigray Insights Spatial Research & Development Platform

## Purpose and source of truth

TSIRD Atlas is the Tigray Insights initiative's Docker-based geospatial web atlas and data engineering platform. It combines an OpenLayers UI, MapServer publication, PostGIS, vector normalization, raster processing, and external WMS sources, with an explicit focus on Tigray and Ethiopian spatial data.

This document updates the earlier v0.2.2 master context against GitHub main inspected on **2026-09-08**, commit `8848d9d743e6f2cb97f50e0b214b2c85d3eeb169`. See [project state](TSIRD_PROJECT_STATE.md) for release evidence and verification limits. Code/configuration at that commit takes precedence over older README examples and phase reports. This is a repository description, not a fresh certification of a running deployment.

## Architecture and deployment

[docker-compose.yml](../docker-compose.yml) defines six services on `tsird-network`:

| Service | Current configuration and role |
| --- | --- |
| `tsird-postgis` | `postgis/postgis:16-3.4`; spatial database; named volume `tsird-pgdata`; mounts `db/init` read-only. |
| `tsird-mapserver` | `camptocamp/mapserver:8.6.0`; WMS rendering from PostGIS and file datasets; mounts mapfiles, fonts, symbols, and read-only `/data`. |
| `tsird-web` | Built from `ui/web`; Nginx static frontend on internal port 8080. |
| `tsird-api` | Built from `api`; Python 3.11, FastAPI, asyncpg, Uvicorn on internal port 8000; bilingual gazetteer lookup. |
| `tsird-etl` | Built from `etl`; GDAL `ubuntu-small-3.10.1`, Python environment, writable `/data`; long-lived processing container with `sleep infinity`, not a scheduled pipeline runner. |
| `tsird-edge` | Built from `infra/edge`; Nginx entry point, bound to `127.0.0.1:${TSIRD_EDGE_PORT}:8080`. |

All six have Compose healthchecks. There is **no Jupyter service in current Compose**; the notebook and historical Jupyter documentation remain in the repository. The MapServer Dockerfile is also retained, but current Compose uses the published image rather than building that Dockerfile.

The Git-ignored local development override adds `tsird-drought-runner`: an
internal-only FastAPI job runner on `tsird-network`, with no host port and no
Docker socket. Local n8n can call only its fixed development endpoints,
including a read-only capacity inventory over the known `/data/drought`
subdirectories. The runner retains drought artifacts beneath that local mount
and is not part of the six-service production Compose definition. All local
Six local-only n8n schedules have passed their documented development gates:
calendar-aware CHIRPS final monthly refresh, CHIRPS rapid source probe, NDVI
and SWI metadata probes, WaPOR’s provider-gated refresh, and monthly read-only
storage inventory. Thermal, outlook, and forecast-study workflows remain
inactive until their separate data contracts pass.
The local-only `/map/drought/control/` page reads a redacted runner snapshot
through the same-origin API. It reports storage, provider receipts, declared
workflow policy, and in-memory recent jobs; it has no workflow, scheduling,
archive, deletion, or credential controls.
The same local control snapshot now includes a read-only Seasonal Agricultural
Stress & Response Priority evidence-readiness gate. It records aggregate
source freshness, quality coverage, boundary-version compatibility, and static
reference years before any reviewed draft matrix can be created. It cannot
calculate or publish a decision score.
The fixed local development Priority Replay runner can subsequently apply the
active Model Studio draft to retained January--August 2026 rainfall plus static
exposure/context evidence. It creates draft-only historical plausibility
snapshots with per-Tabia rule provenance and planning cues; it is not scheduled,
does not use an outlook, and cannot publish a future priority product.
The next model step is a documented local historical-calibration review of
those replays with agricultural and disaster-risk practitioners. It records
rule, seasonal-profile, and planning-cue findings before any revised draft is
run; FEWS NET comparison remains provider-native context only. See
[priority calibration review protocol](drought/priority-calibration-review-protocol.md).
Model Studio also contains a bounded, client-side Scenario Laboratory for the
documented 16-case candidate-reference shortlist. It exposes retained August
2026 evidence and unsaved discussion controls only; it cannot modify the
active matrix, calculate a replay, classify a Tabia, forecast, or recommend
allocation. See the [candidate reference review proposal](drought/candidate-reference-review-proposal.md).
The accompanying metadata-only seasonal-baseline availability check found
complete configured NDVI catalogue coverage for 2016--2025 and matching WaPOR
T/AETI coverage from 2018--2025. On 2026-09-14, the project sponsor adopted the
shared 2018--2025 range as a provisional, reviewable eight-year candidate. It
has a completed fixed 27-file technical pilot and a completed manual fixed
2018--2025 retrieval. Its same-calendar-month NDVI and WaPOR reference has
8,952 quality-approved Tabia-month rows per indicator (24 of 8,976 possible
rows excluded by the declared quality/coverage rule). The reference remains
candidate/review-only: it is not scientifically certified, a priority-model
input, or a valid seasonal baseline. See [baseline availability preflight](drought/seasonal-baseline-availability-preflight.md).
The proposed [baseline acquisition design](drought/seasonal-baseline-acquisition-design.md)
estimates about 1.15 GB of source rasters for one 2018--2025 monthly NDVI and
WaPOR snapshot series, before temporary processing space; it requires a
reviewed pilot and method approval before any retrieval. The fixed candidate
[pilot protocol](drought/seasonal-baseline-pilot-protocol.md) specifies a
small 2018/2021/2025, February/August/November technical sample and clear
stop/revise conditions; it is not a baseline or a priority input.

FEWS NET provides retained, provider-issued Ethiopia native Food Security
Classification (FSC) context for January, February, April, June and July 2026.
The Priority workspace can display one historical provider issue separately or
as an outline comparison with TSIRD's historical replay; a selected Tabia can
report intersecting provider-native areas only. A weekly local-only n8n
catalogue check looks for future public releases, but cannot automatically
retain a new asset. FEWS NET must never be downscaled into a Tabia
classification or alter the TSIRD priority model.

The local Drought Intelligence evidence stack currently retains CHIRPS final
and preliminary rainfall, CLMS NDVI 300 m/10-daily, CLMS SWI 12.5 km/10-daily,
CLMS land-surface temperature 5 km/hourly, and FAO WaPOR v3 Level-2 dekadal
transpiration (T) / actual evapotranspiration and interception (AETI)
artifacts. WaPOR T is published as a current agricultural water-use / crop-
activity context view; it is not a crop-extent, yield, drought, or food-
security classification. FastAPI exposes the
latest development artifact, deliberately selected historical rainfall evidence
snapshots, and per-Tabia retained-observation history; MapServer exposes
development WMS layers. Historical snapshots are archived observations, not
as-issued forecast or model replays. Source timestamps form the evidence
history; the UI does not interpolate gaps or combine indicators into a score.

The production-release builder packages retained API summaries,
historical replay snapshots, and provider-native FEWS NET display GeoJSON into
a checksum-verified release. The API reads only the approved `current.json`
pointer under its narrowly mounted release root. The first public package,
`2026-09-17T032845Z`, was explicitly approved and activated at
`2026-09-17T03:42:03Z`; its predecessor `2026-09-16T225513Z` remains available
for rollback. This does not add a production n8n route, raw-data mount,
automatic promotion, or model-scoring capability. See the
[production release contract](drought/production-release-contract.md).

The tracked production overlay mounts only `/opt/tigrayinsights/apps/tsird/releases/drought`
read-only into `tsird-api`; it does not start an n8n worker or expose raw evidence.
It also requires immutable prebuilt web/API/edge image references and excludes
the ETL service from the default production Compose profile, so the constrained
VPS cannot build or process drought data during `compose up`.
The tracked GitHub Actions publisher builds those three images only from an
explicit `tsird-drought-v*` tag or manual dispatch; a production activation
must pin the resulting SHA image tags rather than a mutable image name. The
private [release ledger template](drought/templates/drought-production-release-ledger.example.md)
records the code, image, data-release, verification and rollback references
together.
The hand-off uses a restricted SFTP ingress account and a separate forced-command
activation account. The production VPS accounts, their restricted directories,
and the SSH configuration were provisioned and boundary-tested on 2026-09-16;
the activation utility accepts only an already-approved, checksum-verified
release and atomically advances `current.json`. It cannot build data or run the
model. A version-controlled, inactive local n8n publisher template now records
the fixed allow-listed transfer and activation sequence. It was used to publish
the approved 18-asset release `2026-09-17T032845Z` at
`2026-09-17T03:42:03Z`. The publisher shell script is explicitly checked out
with Unix line endings because it executes in an Alpine Linux n8n container.
The release did not perform data processing or expose development services. See the
[activation design](../infra/host-nginx/tsird-drought-release-activation.md)
and [n8n publisher setup](drought/n8n-production-publisher-setup.md).

A separate automatic indicator-evidence channel now has its own nested
`indicators/current.json` pointer. It can carry only technically validated
Tabia indicator summaries; it cannot advance Priority Replay, FEWS NET context,
model configuration or a raw-raster layer. See
[automatic indicator publication](drought/automatic-indicator-publication.md).

The public-only release viewer is `/map/drought/release/`. It calls only the
approved-release API, displays neutral C1--C4 retrospective draft codes and
provider-native FEWS NET outlines, and explicitly remains unavailable until an
approved `current.json` exists. It never falls back to development evidence.

The production-only web overlay preserves the familiar public route hierarchy:
`/map/drought/` is a searchable approved-evidence workspace over all retained
Tabia summaries in the release; `/priority/`
retains approved review-month, FEWS NET issue and map-display controls over
sanitised historical assets; and `/scenario/` and `/model/` explain
the bounded public candidate-review and model context. The shared local web
image retains the full development workspace. Production never mounts its
development runner, raw grids, workflow state, or scoring controls; its
`/map/drought/control/` route is an explicit development-only notice.

### Request routing

[Edge Nginx](../infra/edge/nginx.conf) routes:

- `/map/` to `tsird-web:8080`, preserving the URI.
- `/map/ogc` to `tsird-mapserver:80`, injecting `map=/etc/mapserver/tsird.map` and stripping client-supplied `map` arguments.
- `/map/api/` to `tsird-api:8000/`, stripping the `/map/api/` prefix.
- `/map/health` to an edge-local response; `/map/version` returns a hardcoded component version, not the atlas release.

The documented local entry point is `http://localhost:18080/map/` when the edge port is configured as 18080. The [host Nginx configuration](../infra/host-nginx/tsird-map.conf) proxies `/map/` to `127.0.0.1:18080` and redirects bare `/map` to `/map/`. [Production notes](releases/v1.0.0.md) identify `https://lab.tigrayinsights.net` and its `/map/` path; deployment availability was not tested in this inspection.

Keep browser assets relative to `/map/` (for example `src/`, `css/`, and `data/`) and API/WMS requests same-origin. The current WMS registry value is `/map/ogc`; older instructions requiring an absolute localhost URL do not describe the active frontend.

## Active frontend and registry

[ui/web/index.html](../ui/web/index.html) loads OpenLayers **8.1.0** and js-yaml **4.1.0** from a CDN, followed by plain classic scripts under `src/`. [src/main.js](../ui/web/src/main.js) orchestrates the map, TOC, interactions, and Phase 3 toolbar. There is no bundling step in the web Dockerfile. Older `js/`, `src/search/`, and `src/components/` implementations exist; their presence does not mean the current entry point loads them.

The active registry is [ui/web/data/atlas-registry.json](../ui/web/data/atlas-registry.json), requested by `src/main.js` with a cache query. It contains atlas settings, service URLs, categories/groups, layer definitions, visibility, legend and temporal options, and rules. It is **JSON UI configuration, not a MapServer mapfile**. Other registry files (`config/atlas-registry.yaml`, web YAML, and `ui/web/static/atlas-registry.json`) are not the default registry selected by the active entry point.

The registry specifies canonical coordinates in EPSG:4326 and the map view in EPSG:3857. Its 12 categories include Ethiopia Administrative, Tigray State, Horn of Africa, Infrastructure, Terrain, Rainfall & Climate, Nature, Raster, Satellite Images, Land Use & Land Cover, Other WMS Sources, and Basemaps.

Implemented UI capabilities include:

- Registry-driven TOC, layer toggles and ordering, basemap selection, scale rules, legends, scale bar, and GetFeatureInfo.
- Global date, per-layer temporal settings, and Follow Global controls.
- A sticky Display Settings panel with boundary opacity and TOC density controls persisted in localStorage. Density controls sidebar presentation; do not assume it changes map label density.
- Phase 3 bilingual Woreda/Tabia search, zoom-to-feature, orange bounding-box highlight, overview navigator map, full-extent zoom, and distance/area measurement.

### Gazetteer search

[SearchControl.js](../ui/web/src/controls/SearchControl.js) queries `GET /map/api/gazetteer?q=...`. [api/main.py](../api/main.py) performs parameterized English/Tigrinya `ILIKE` matching against `tigray_woredas_ws` and `tigray_tabias_ws`, ranks exact/prefix/other matches, and returns up to 15 records containing `type`, `name_en`, `name_ti`, and `bbox`.

The query depends on `geometry`, `WEREDA`/`TABIA`, and `woreda_tig`/`tabia_tig`. Gazetteer records include `id`: Tabias use the unique, versioned `tsird_tabia_id`; Woredas currently expose their local feature ID. The UI interprets bbox coordinates as EPSG:4326, transforms them to EPSG:3857, and fits the view; Tabias use extra padding and a maximum zoom of 12. [HighlightOverlay.js](../ui/web/src/tools/HighlightOverlay.js) draws the returned **bounding rectangle**, not the feature's exact polygon. Static search-index/gazetteer JSON files remain from earlier implementations, but the active SearchControl uses the API.

## MapServer and cartography

The active mapfile is [infra/mapserver/mapfiles/tsird.map](../infra/mapserver/mapfiles/tsird.map). It includes [includes/vectors_gold.map](../infra/mapserver/mapfiles/includes/vectors_gold.map) and defines additional layers directly. Do not assume `layers_published.map` or `layers_published_all.map` is active merely because it exists.

Rendering combines OGR/file-backed vectors, PostGIS layers, and rasters. Mapfile classes define styles, raster classification, labels, and legends. The UI uses WMS; older broad WFS/WCS claims do not establish verified WFS/WCS functionality in this checkout.

Current cartography includes zone-based muted fills and bilingual labels for Tigray Woredas, boundary-only bilingual Tabias, Ethiopia administrative hierarchy, Eritrea admin0/admin1/admin2, and classified DEM/slope rasters. NotoSansEthiopic and Arial supply Tigrinya and English labels. The bilingual Woreda/Tabia TOC entries suppress legends via registry options. External entries include NASA FIRMS, NASA GIBS, and ESA WorldCover; XYZ basemaps include OSM and Esri. Registry entries do not guarantee upstream availability or successful rendering.

[ms.config](../infra/mapserver/mapfiles/ms.config) uses `MS_MAP_PATTERN` and `MS_MAPFILE`. Compose sets `MAPSERVER_CONFIG_FILE=/etc/mapserver.conf` and mounts that config there. Preserve this wiring: commit `d21ab55` corrected the invalid `MS_MAPFILE_PATTERN` setting associated with FCGI recycle failures; [troubleshooting](TSIRD_TROUBLESHOOTING.md) records Problem #13.

## Data processing and dependencies

The vector pipeline follows raw inventory audit → CRS normalization to EPSG:4326 → regional separation, with YAML CRS/classification overrides, geometry repair/quarantine, and CSV/Markdown audit reports. Its tracked scripts and configuration reside under `Docker Projects/TSIRD-Atlas-Data-Pipeline/`, not at the older README's `etl/*.py` example paths. The `etl/` directory supplies the processing image and healthcheck. Review mounts and script paths before attempting to run the pipeline in a container.

[scripts/](../scripts/README.md) contains DEM/slope processing, AOI preparation, vector checks, and WMS verification tools. Read each script before execution: some prepare or modify data and are not read-only checks.

Source datasets, processed outputs, and deployment credentials are not supplied as a complete runnable instance. MapServer requires external files such as `/data/gold/eritrea/gadm41_ERI_*.shp` and the configured PostGIS tables. `db/init/` contains placeholders and a `tsird` schema initializer; it does not provision the gazetteer tables required by `api/main.py`. A clean checkout alone therefore cannot establish working search or map rendering. Configure local secrets without committing them, and preserve source data and database volumes.

## Further references

- [Project state](TSIRD_PROJECT_STATE.md): inspected baseline, releases, caveats, verification.
- [v1.0.0 release notes](releases/v1.0.0.md): historical production milestone.
- [Operations guide](TSIRD_OPERATIONS_GUIDE.md) and [troubleshooting](TSIRD_TROUBLESHOOTING.md): operational background; check examples against current files.
- [Documentation index](README.md): deeper phase, pipeline, and incident documentation.
