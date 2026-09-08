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

The query depends on `geometry`, `WEREDA`/`TABIA`, and `woreda_tig`/`tabia_tig`. The UI interprets bbox coordinates as EPSG:4326, transforms them to EPSG:3857, and fits the view; Tabias use extra padding and a maximum zoom of 12. [HighlightOverlay.js](../ui/web/src/tools/HighlightOverlay.js) draws the returned **bounding rectangle**, not the feature's exact polygon. Static search-index/gazetteer JSON files remain from earlier implementations, but the active SearchControl uses the API.

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
