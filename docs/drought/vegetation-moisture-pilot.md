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

## Candidate source and processing contract

The first candidate is a cloud- and shadow-masked Sentinel-2 Level-2A
surface-reflectance composite.  It must use B08 (NIR) and B11 (SWIR), whose
native resolutions differ; the analytical grid is therefore 20 m unless a
documented resampling method is accepted.  The display must never suggest
10 m analytical precision.

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
