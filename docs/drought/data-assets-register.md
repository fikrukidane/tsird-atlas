# Drought Intelligence data-assets register

This is the development acquisition plan, not evidence that every listed
source has been downloaded, licensed for a particular use, or validated for
decision-making. No source secret belongs in this file or in the Atlas.

## Local TSIRD assets

| Asset | Role | Required preparation |
| --- | --- | --- |
| Canonical Tigray Tabia boundaries | Reporting geography and zonal summaries | Use `tsird_tabia_id`; retain source `T8ID` only as traceability metadata. |
| Tigray road network | Physical road-accessibility baseline | Record source/revision, road classes, topology, known gaps, and the chosen travel assumptions. |
| Woredas, towns, terrain, land cover | Context, aggregation, and exposure | Document source date before use in a current decision product. |
| Local CHIRPS development table | Observed rainfall prototype | Reprocess after the spatial-mean correction; validate before any map publication. |

## Recommended external sources

| Source ID | Product | Intended indicator | Access / cadence | Initial decision |
| --- | --- | --- | --- | --- |
| `chc-chirps-v3` | CHIRPS v3 rainfall | Observed rainfall anomaly/percentile | Open repository; preliminary pentad and final monthly | Enable first. |
| `igad-icpac-monitoring` | ICPAC climate, vegetation, soil products | Regional monitoring/cross-check | Portal/geoportal; product-specific cadence | Evaluate metadata and services first. |
| `igad-icpac-seasonal` | ICPAC seasonal outlook | Broad regional probability context | Seasonal releases | Display at native regional resolution only. |
| `fao-wapor-v3` | Level 2 dekadal transpiration (T) and AETI | Agricultural water-use / vegetation-water-use context | Public FAO catalogue API and COG subsets; no token | Local development probe and bounded Tigray T/AETI pipeline implemented; never interpret as crop extent, yield, drought, food security, or priority. |
| `fews-net-public-classifications` | FEWS NET Ethiopia acute food-insecurity classifications, mapping units, and associated public downloads | Provider-native FSC-unit food-security context | Public GIS downloads; FDW/API access is permission-aware | Local development retains the official January, February, April, June and July 2026 Ethiopia native-FSC GeoJSON issues with source URLs and raw properties. It is selectable as separate context or an outline comparison with the TSIRD historical replay. A spatial intersection can identify an overlapping provider area for a selected Tabia, but never transfers or downscales a classification to that Tabia and never changes the priority model. |
| `cdse-clms-ndvi-v3` | Copernicus CLMS NDVI 300 m, 10-daily v3 | Vegetation-condition monitoring | CDSE Sentinel Hub OAuth2 / BYOC collection metadata and Process API; 10-daily | Access check enabled in local development; aggregation design and cost guardrails come before pixel retrieval. |
| `cdse-clms-swi-v4` | Copernicus CLMS Soil Water Index 12.5 km, 10-daily v4 | Broad root-zone wetness context | CDSE Sentinel Hub OAuth2 / BYOC collection metadata and Process API; 10-daily | Collection access verified. Keep at native 0.1° resolution; any Tabia statistic must disclose sparse/coarse cell coverage. |
| `cdse-clms-lst-v2` | Copernicus CLMS land-surface temperature 5 km, hourly v2 | Thermal context and heat-stress diagnostic | CDSE Sentinel Hub OAuth2 / BYOC collection metadata and Process API; hourly | Collection access verified. Retain native grid and provider error/quality diagnostics; never label as air temperature. |
| `copernicus-c3s-seasonal` | Multi-system seasonal forecast | Ensemble/skill assessment | CDS account, terms, API token | Later technical workflow; do not Tabia-downscale. |
| `copernicus-sentinel-2` | Surface reflectance | Higher-resolution vegetation/crop review | Copernicus Data Space | Later; needs cloud-mask/processing capacity. |
| `nasa-earthdata` | SMAP/IMERG and related products | Diagnostic cross-check | Earthdata account/token | Later; do not duplicate CHIRPS without a defined question. |
| `wfp-logistics-cluster` | Physical access constraints | Dated route constraints | Published operational products | Human-reviewed import only. |

## Deliberately excluded from the first automated release

- An Atlas-generated IPC phase or food-insecurity classification.
- Any aid-reach estimate inferred only from roads, facilities, or population.
- Undocumented scraped PDFs or images.
- A composite risk score.

## Minimum source-registration fields

Every enabled source needs provider/product/version, licence/terms, access
method, expected cadence/latency, geographic coverage, native resolution,
historical coverage, source contact, retention policy, and a named TSIRD owner.
For each retrieval, save the non-secret request parameters, retrieval time,
checksum, source timestamp, and quality result.
