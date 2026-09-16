# Seasonal rainfall outlook implementation

## Purpose

The Drought Intelligence **Outlook** workspace is reserved for a
provider-issued seasonal climate probability product. Its first variable is
`seasonal_rainfall`; seasonal temperature is a later, separate variable.

It is not a forecast of NDVI, soil water, land-surface temperature, crop water
use, food insecurity, hunger, or TSIRD response priority.

## Display contract

The dashboard chooses the newest **active** release by `valid_from` and
`valid_to`, falling back only to the nearest **upcoming** release. A completed
release is labelled `archived` and is never the default current map.

Each record must supply:

- provider/product/version and source URL;
- issue timestamp and validity start/end dates;
- lead range, native CRS/resolution, and source geography;
- below-, near-, and above-normal rainfall probabilities;
- quality and provenance metadata.

The source-faithful default is `native_grid`. `woreda_context` is optional and
must be a documented summary of that provider grid with coverage. Neither
representation contains a Tabia forecast.

## Pipeline gate

`tsird-icpac-seasonal-outlook-probe-v1.development.json` is inactive and only
checks the fixed public ICPAC catalogue URL. It cannot derive values from page
imagery, download a forecast, or publish an artifact.

Before a real loader is introduced, a named reviewer must confirm one official
machine-readable asset and record its licence/terms, exact issue/validity
dates, complete probability distribution, CRS/resolution, geography, and
stable retrieval method. The loader then writes only to the local development
`drought_seasonal_outlook_run` and `drought_seasonal_outlook_feature` tables.

If no such reviewed release is present, the dashboard displays an explicit
no-data state and draws no Outlook map.

## C3S candidate path

The local development runner can now verify two technical C3S gates using
ECMWF System 51 and a temporary 0.5 degree Tigray precipitation window:

1. **Account and dataset access:** a current seasonal monthly request is
   accepted under the account's CDS terms.
2. **Matched hindcast availability:** one retrospective initialization can be
   retrieved using that same system.

Both probes delete their GRIB file immediately and retain only a redacted
receipt. They prove neither forecast skill nor that a C3S result is suitable
for a public map.

Before a C3S loader or user-visible Outlook is proposed, a scientific review
must approve a reproducible skill study:

- use a fixed system and the matching hindcasts, never a mixed-system sample;
- define the target season and lead months before retrieval;
- compare the hindcast ensemble with an observed rainfall reference on the
  provider's native or coarser analysis grid;
- convert seasonal monthly total-precipitation values using the provider's
  accumulation convention before comparison (the monthly C3S rate must be
  converted to a monthly depth in millimetres using the target month's number
  of seconds);
- evaluate calibration and discrimination for below/near/above-normal
  probability categories, including a documented reference period;
- record the applicable years, excluded samples, spatial aggregation, and
  pass/fail criteria; and
- have a named reviewer approve the resulting Woreda-scale publication
  contract.

Only a passing, reviewed study can unlock a bounded loader. A future C3S map
would remain probabilistic rainfall-planning context at provider/Woreda scale;
it would not forecast individual Tabias, crops, food insecurity, or response
priority.

### First technical result — blocked

The first development-only case used ECMWF System 51 August initialisations,
lead month 1, and 1993--2016 CHIRPS August rainfall over an unweighted
Tigray-bounds mean. Its leave-one-year-out tercile Brier skill scores were
negative for below-normal (`-0.4180`), near-normal (`-0.2813`), and
above-normal (`-0.3403`) categories. In this case, the forecast probabilities
performed worse than the climatological reference.

This is not a general conclusion about all systems, seasons, leads, or local
geographies. It is, however, sufficient to block C3S System 51 August
lead-one values from being published as a TSIRD Outlook. The retained result is
an internal technical diagnostic only; no map, forecast, or decision product
is produced from it.

### August lead comparison — also blocked

To isolate planning horizon rather than change the rainfall target, the same
1993--2016 regional method was repeated for **August rainfall** using July
initialisation at a two-month lead and June initialisation at a three-month
lead. The leave-one-year-out tercile Brier skill scores were:

| Lead | Below-normal | Near-normal | Above-normal |
| --- | ---: | ---: | ---: |
| Two months | -0.7950 | -0.2630 | -0.2501 |
| Three months | -0.4216 | -0.2538 | -0.0808 |

All scores are negative, so both longer August lead tests also performed worse
than the historical-normal reference. This strengthens the publication block
for this narrow August regional pilot; it still does not generalize to other
seasons, spatial methods, systems, or a reviewed provider-issued product.
