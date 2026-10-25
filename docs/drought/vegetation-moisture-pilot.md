# Vegetation-moisture pilot — development only

## Purpose

This is a bounded, development-only design for a vegetation-moisture evidence
stream.  It complements, but does not replace, retained NDVI, soil-water,
rainfall, thermal, and WaPOR evidence.  It does not create a drought class,
food-security classification, forecast, allocation rule, or composite score.

The user-facing development panel calls the proposed signal **Vegetation
moisture (NDMI / LSWI)**.  Both labels are used in remote-sensing literature
for the normalised NIR–SWIR difference:

```text
(NIR - SWIR) / (NIR + SWIR)
```

The pilot starts with no values.  The existing CLMS NDVI source contains an
already-derived NDVI product, not the NIR and SWIR surface-reflectance bands
needed to calculate this index.  No value may be inferred from NDVI alone.

## Acknowledgement

The educational index-selection framing refers to Geoinfotech's
*Spatial Indices Analysis* explainer, shared with TSIRD on 24 October 2026.
This acknowledgement credits that explainer for its educational framing only.
Geoinfotech does not provide the imagery, validate the method, endorse the
platform, or supply any TSIRD result.

## Initial Sentinel-2 candidate — retained for audit, not the active design

The first candidate is a cloud- and shadow-masked Sentinel-2 Level-2A
surface-reflectance composite.  It must use B08 (NIR) and B11 (SWIR), whose
native resolutions differ; the analytical grid is therefore 20 m unless a
documented resampling method is accepted.  The display must never suggest
10 m analytical precision.

That initial candidate is retained as a bounded integration experiment only.
It must not become a monthly evidence map: a 90-day temporal composite would
measure seasonal surface condition rather than a particular month's condition.
The stopped full-region test did not load or publish a replacement artifact.

## Active design: HLS monthly feasibility pilot

The active DEV design uses NASA's **Harmonized Landsat and Sentinel-2 (HLS)
v2.0** L30 and S30 surface-reflectance products. HLS supplies harmonised 30 m
narrow-NIR and SWIR1 bands from both sensors, allowing a completed
calendar-month evidence window without silently extending it across a season.
The pilot uses the common HLS pairs: S30 B8A/B11 and L30 B05/B06.

It applies the HLS Fmask quality flags conservatively: cloud, the 150 m
cloud/shadow-adjacent buffer, cloud shadow, snow/ice, water, fill, saturation
and high aerosol are excluded. It does **not** infer clear observations from
unmasked values. The pilot stores no raw HLS scenes or provider URLs; it uses
authenticated Cloud Optimized GeoTIFF range reads and retains only compact
Tabia statistics.

The first HLS run is a fixed **20-Tabia** technical feasibility sample: five
repeatable canonical Tabias from each area quartile. It has no schedule, no
public API or WMS layer, and no release/publish path. Every row records:

1. candidate and valid observation-pixel counts and their percentage;
2. candidate and usable-acquisition counts;
3. first, last and median contributing acquisition time; and
4. an explicit quality reason: insufficient valid pixels, observation coverage
   or acquisition count, rather than an interpolated value.

An `ok` result requires all three thresholds: at least **30** valid observation
pixels, **70%** valid observation coverage, and **two** contributing
acquisitions. Coverage is explicitly defined as valid observation pixels
divided by candidate observation pixels across the queried acquisitions; it is
not presented as gap-filled composite coverage. This makes the uncertainty
inspectable for small and large Tabias alike.

The fixed, internal runner endpoint is
`/runs/hls-ndmi-monthly-pilot/development-test`. It accepts no date, geometry,
URL, command, database statement or credential from a caller and requires one
locally injected `EARTHDATA_TOKEN`. The token is DEV-only, untracked and never
printed, persisted in an artifact, or sent to a browser.

NASA Earthdata authentication is required only to read HLS data. Before the
first DEV run, the operator must inject an Earthdata token into the local
runner environment; no token belongs in Git, a mapfile, a workflow export, or
production configuration. The pilot must be reviewed against retained CLMS
NDVI before any proposal for a full 748-Tabia run or map.

## Implemented DEV technical path

The first technical path uses the Copernicus Data Space Sentinel Hub
**Statistical API**, rather than downloading Sentinel scenes.  It sends one
Tabia geometry at a time with a fixed, completed 30-day UTC window and retains
only returned NDMI mean, median, valid-pixel count, grid-cell count and valid
coverage.  The provider performs B08/B11 calculation and polygon aggregation;
TSIRD does not retain a raw scene or a regional raster for this pilot.

The fixed runner endpoint is
`/runs/sentinel2-ndmi-pilot/development-test`.  It has no request body, accepts
no date, geometry, URL, command or SQL input, permits only one active runner
job, and selects no more than 20 deterministic canonical Tabias.  It is
manual-only and remains inactive in the n8n registry.

The pilot uses Sentinel-2 L2A `dataMask` and only SCL classes **4**
(vegetation) and **5** (bare soil); cloud, cloud shadow, cirrus, snow, water,
no-data and unclassified pixels are excluded.  A row with less than 70% valid
coverage is explicitly `insufficient_evidence`.  This is a quality rule, not
a moisture or drought threshold.  The run manifest records the exact window,
20 m analytical resolution, masking rule, mosaicking rule, processing version
and Geoinfotech acknowledgement.

The sample is a technical integration and quality check, **not** a
representative regional survey or a map-ready product.  It is displayed only
as a DEV table after a successful run.  A same-calendar reference period,
full regional coverage design, practitioner review and a separate release
decision are still required before any public or production use.

Before a DEV run can appear in the workspace, it must retain:

1. acquisition and composite windows, sensor/product identifiers and a
   processing version;
2. cloud, shadow, invalid-pixel and no-data masking rules;
3. valid-pixel count and percent coverage for every Tabia;
4. an explicit `insufficient_evidence` result below the approved coverage
   rule, rather than interpolation; and
5. a same-calendar-period Tabia reference distribution and the number of
   valid reference years.

The first operationally useful review is whether NDMI/LSWI changes add
information alongside NDVI, SWI, rainfall and WaPOR in contrasting Tigray
settings.  This requires a small retained-artifact pilot and practitioner
review before any publication decision.

## Excluded from this pilot

- No provider download, credential use, scheduled workflow, or source-data
  ingestion is performed by this UI change.
- No production route, public release asset, public navigation item, or
  publication contract changes.
- No universal moisture-stress threshold or automatic decision trigger.

## Superseded all-Tabia Sentinel-2 experiment

The earlier proposed separate, manual **748-Tabia DEV acquisition** remains
in the repository solely for audit and rollback of its technical experiment.
It does not replace or reinterpret the 20-Tabia integration pilot.  The full
path used a fixed, completed 90-day UTC window ending five days before the run
and a pixel-wise temporal-median composite across valid `ORBIT` observations
(with the provider's `leastCC` selection per day). The longer review window is
explicitly recorded because the 30-day pilot retained too little cloud- and
shadow-free coverage to make a useful regional map. This is a completed-window
surface-condition composite, not a single-date snapshot.

The resulting DEV WMS layer is `tigray_drought_sentinel2_ndmi_dev`.  It is a
Tabia-statistic layer, not a 10 m or 20 m raster: TSIRD retains only returned
mean/median NDMI statistics, coverage, and quality metadata.  Tabias at or
above 70% valid coverage receive source-value NDMI bands; every other Tabia is
shown as **insufficient evidence**.  Neither colour nor absence of colour is a
drought, food-security, priority, allocation, or response classification.

The run endpoint is fixed and manual only:
`/runs/sentinel2-ndmi-full/development-test`.  It accepts no user-supplied
date, geometry, URL, credentials, command, or SQL.  It makes one bounded
provider request per canonical Tabia and loads no partial result; it has no
n8n schedule, production route, public asset, or release activation path.
The collector spaces requests by five seconds and honours a bounded CDSE
`Retry-After` response for a single rate-limited request.  This is transport
protection, not an automatic repeat of the regional run.

The DEV collector refreshes its OAuth access token only when CDSE reports it
expired, and keeps a private compact-statistics checkpoint until the complete
748-Tabia artifact validates. A checkpoint is neither a database run nor a
served WMS/release asset; it exists solely to resume a bounded manual run
after a provider-side interruption without re-requesting completed Tabias.

The all-Tabia collector uses a **25 m analytical grid**. Sentinel-2 B11 and
SCL remain 20 m source bands, but the provider rejects a request dimension
above 2,500 pixels; one canonical Tabia is 2,704 pixels high at 20 m. The
25 m grid keeps every Tabia within that hard limit and is recorded in each
artifact. It must never be described as a 10 m or 20 m result.

No further run of this 90-day path is authorised by this design. If retained
for later seasonal-context research, it must be renamed and displayed as a
completed-window surface-condition composite, never a monthly HLS replacement.
