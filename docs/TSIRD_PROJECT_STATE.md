# TSIRD Project State

## Inspected baseline and release state

Inspected **2026-09-08** against [fikrukidane/tsird-atlas](https://github.com/fikrukidane/tsird-atlas). This records repository state, not a new live operational acceptance test. It supersedes the earlier context snapshot that identified v0.2.2 and planned Phase 3 search.

| Evidence | State at inspection |
| --- | --- |
| GitHub `main` | [`8848d9d743e6f2cb97f50e0b214b2c85d3eeb169`](https://github.com/fikrukidane/tsird-atlas/commit/8848d9d743e6f2cb97f50e0b214b2c85d3eeb169), 2026-03-27: `chore: remove backup files, update gitignore for public release`. |
| Highest version tag | `v1.0.0`, resolving to commit `70e68e360e0ba229225e350b9e8bdd8bb24f431d`, the 2026-03-07 Phase 3/cartography merge. Main is four commits ahead. |
| In-repository release description | [v1.0.0 — First Production Release](releases/v1.0.0.md), dated 2026-03-07. |
| GitHub latest formal Release | [v0.3.0 — Search & Zoom for Tigray Woredas and Tabias](https://github.com/fikrukidane/tsird-atlas/releases/tag/v0.3.0), published 2026-03-04; tag resolves to `4bfbde5c2a689a265eed6cff5b32e55dcc5d41b2`. Confirmed through GitHub's `/releases/latest` API. |

These are different records: current main is **post-v1.0.0 code**, while GitHub's latest formal Release remains v0.3.0. Do not describe main as v0.2.2, equate it with the v1.0.0 tag, or infer a newer formal release. Registry title `TSIRD Atlas v2.0`, registry `version: 1.0`, frontend package version `0.1.0`, and edge `/map/version` value `0.1.0` are separate embedded labels, not evidence of another atlas release.

### Changes after the v1.0.0 tag

| Commit | Change |
| --- | --- |
| `2285bab` | Removes production localhost/device-app triggers from the frontend; adds a release guard script. |
| `d21ab55` | Corrects `MS_MAPFILE_PATTERN` to `MS_MAP_PATTERN` in MapServer configuration. |
| `c1edfbe` | Documents the FCGI recycle failure and fix as Lesson 7 / Problem #13. |
| `8848d9d` | Removes backup files and updates ignore rules for public release. |

## Implemented state

See [master context](TSIRD_MASTER_CONTEXT.md) for source paths and request flow.

- Phase 3 search is implemented: FastAPI/PostGIS bilingual Woreda/Tabia lookup, zoom-to-bbox, and orange bbox highlight. The active frontend has moved beyond the static JSON search described by the formal v0.3.0 Release.
- Navigator overview, full zoom, distance/area tools, persistent Display Settings, temporal controls, TOC and legend behavior, scale handling, and GetFeatureInfo are present in the active scripts.
- Cartography includes Tigray zone-based Woreda styling, bilingual Woreda/Tabia labels, Ethiopia hierarchy, Eritrea admin layers, and DEM/slope classifications.
- Compose defines `tsird-postgis`, `tsird-mapserver`, `tsird-web`, `tsird-api`, `tsird-etl`, and `tsird-edge`. Jupyter is historical context, not a current Compose service.
- The `/map/` proxy contract remains active, including `/map/ogc` and `/map/api/gazetteer`. Public URLs in release notes are documented deployment targets, not availability checks performed here.

### Registry inventory

Static counts from [ui/web/data/atlas-registry.json](../ui/web/data/atlas-registry.json) at the baseline commit:

| Item | Count |
| --- | ---: |
| Categories | 12 |
| Layer definitions | 62 |
| Definitions marked published | 59 |
| Vector definitions | 38 |
| External WMS raster definitions | 16 |
| Other raster definitions | 6 |
| XYZ basemaps | 2 |

The last four rows partition all 62 definitions, including unpublished entries. `ethiopia_hillshade`, `ethiopia_cia_basemap`, and `ethiopia_language` are marked unpublished. These are **registry counts**, not a count of advertised WMS layers, visible TOC entries, or successfully rendered datasets.

## Known limits and remaining work

- Live containers, production availability, map rendering, bilingual search results, and external WMS availability were not tested in this documentation inspection. Historical reports of stability remain historical evidence.
- A complete deployment requires external spatial data, populated PostGIS tables, and local credentials. `db/init/` does not create/populate the gazetteer tables. Existing credential-like defaults or placeholders in tracked configuration must not be treated as valid deployment credentials or copied into new documentation.
- API `/health` returns a static OK response without checking database access. Gazetteer database errors are logged and returned as an empty result list, so HTTP 200 or no matches alone does not prove working search.
- Several README/phase examples are stale: Jupyter, static search, registry paths, ETL script paths, and absolute localhost WMS guidance must be checked against active code. The main mapfile includes `vectors_gold.map`; the alternate publication includes are not selected by it.
- The repository has focused validation scripts and Compose healthchecks, but `ui/web/package.json` has only a placeholder npm test command. No complete automated test suite is established by this checkout.
- README lists incremental orchestration and raster pipeline integration as in progress, and real-time incremental updates/full WCS configuration as unimplemented. Treat these as recorded backlog statements, not new commitments. Phase 3 search must no longer be presented as the next unimplemented milestone. No subsequent milestone is established by this inspection.

## Verification and development checks

Inspection covered GitHub main/history, local tag targets, GitHub's latest Release API, Compose/Dockerfiles, active HTML/JavaScript, registry JSON, API SQL, MapServer configuration/includes, database initialization, and release/troubleshooting notes. Registry counts were computed from JSON. Documentation validation checks local links and whitespace; no application code is changed.

For future changes, run only the checks relevant to the change and record actual outcomes. From the repository root:

```bash
git diff --check
# Registry changes; requires Python 3 and PyYAML:
python3 tools/validate_registry.py ui/web/data/atlas-registry.json
# Served frontend changes and before tagging releases:
bash scripts/check-no-localhost-in-production.sh
```

With an intentionally configured local stack on port 18080, read-only smoke requests include:

```bash
curl -fI http://localhost:18080/map/
curl -fsS http://localhost:18080/map/data/atlas-registry.json
curl -fsS 'http://localhost:18080/map/ogc?SERVICE=WMS&REQUEST=GetCapabilities'
curl -fsS 'http://localhost:18080/map/api/gazetteer?q=Adwa'
```

Inspect capabilities contents and actual map rendering, not merely HTTP status. Search checks need known populated English/Tigrinya records and correct bbox zoom/highlight. UI changes also need browser checks of the `/map/` entry point and affected controls. Data-changing ETL runs and production deployments require separate task scope; this documentation refresh does not perform them.
