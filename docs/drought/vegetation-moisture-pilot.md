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
