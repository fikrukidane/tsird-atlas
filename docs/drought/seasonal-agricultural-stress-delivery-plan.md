# Seasonal Agricultural Stress & Response Priority — delivery plan

## Outcome

TSIRD will provide a transparent, evidence-led monthly planning workspace for
Tigray. It will distinguish **observed conditions**, **static context**,
**historical evidence**, and a reviewed **response-priority draft**. It will
not present a drought, hunger, famine, or food-security classification unless
TSIRD has a separately reviewed source and governance decision for that claim.

The local Pipeline Control page is the operational checklist. A phase is
**done** only when its completion evidence below has been verified locally.
It is not a forecast, a production deployment record, or a substitute for
scientific and programmatic review.

## Delivery checklist

| Phase | Current state | Completion evidence |
| --- | --- | --- |
| 1. Observed-data engine | In progress | Each observed source has bounded ingestion, provenance, coverage/freshness checks, retry-safe local workflow behavior, and a verified January 2026 onward monthly evidence record. LST has an honest June--August source gap. |
| 2. Static decision layers | In progress | DEM/elevation, slope/terrain complexity, soil context, cropland baseline, population, and ERAA/TRRA road proximity are documented in Atlas and have an appropriate, disclosed Tabia summary where used. |
| 3. Historical evidence workspace | Ready for local acceptance | Users can select a retained month from January 2026 onward, inspect source-specific Tabia evidence, retained native raster where available, source age, coverage, gaps, and selected-Tabia history. |
| 4. Priority-model draft | In progress | The v0.1 specification defines transparent components, safeguards, three-month planning horizon, Model Studio governance, 10 priority classes, and per-Tabia rationale. No score has been calculated or published. |
| 5. Seasonal Outlook research | Blocked | A provider-issued, machine-readable release with documented validity, or a calibrated Woreda-scale forecast method that passes preregistered skill checks and review. |
| 6. Production package | Not started | Development acceptance, Git review, release package, backup/rollback plan, and low-impact file-transfer deployment plan are approved. |

## Current Phase 1 acceptance evidence

Verified locally on 2026-09-12:

| Indicator | Retained historical coverage | Tabia records | State |
| --- | --- | ---: | --- |
| Copernicus NDVI v3 | 21st of every month, January--August 2026 | 8 runs × 748 | Complete for the bounded history target; source age is correctly labelled degraded. |
| Copernicus SWI v4 | 21st of every month, January--August 2026 | 8 runs × 748 | Complete for the bounded history target; coarse-grid coverage remains visible per Tabia. |
| WaPOR v3 T/AETI | Third dekad of every month, January--August 2026 | 8 runs × 748 | Complete for the bounded history target; it remains crop water-use context only. |
| Copernicus LST v2 | January--May monthly observations, plus retained late-May/early-June source snapshots | 9 runs × 748 | Provider-compatible monthly records were unavailable for June--August. LST v2 is superseded upstream and remains historical evidence only pending a reviewed replacement. |
| CHIRPS final rainfall | One run for each month, January--August 2026 | 8 runs × 748 | Complete for the bounded history target. Each run has a retained 0.05-degree native rainfall-total grid, source receipt, baseline comparison, and Tabia summary. |
| CHIRPS rapid rainfall | One six-pentad preliminary window ending each month, January--August 2026 | 8 runs × 748 | Complete for the bounded history target. It remains an observed preliminary accumulation with no drought class. |

Every CDSE timestamp above was selected from the provider catalogue. No source
timestamp was invented to make a calendar month appear complete. The same
principle applies to CHIRPS rapid-rain history: each retained period identifies
its six provider pentads and its source receipts.

## End state in the user interface

### Atlas

The existing Atlas remains the reference map. It exposes reusable natural
resource and context layers such as elevation, slope, soils, land cover,
cropland, roads, and other approved sources. Layer legends identify source,
resolution, reference date, and appropriate interpretation. Static layers are
not described as current conditions.

### Drought Intelligence

The Drought Intelligence panel provides these source-specific views:

- **Latest rainfall** and **Rapid rain**, with the exact observation period
  visible at all times;
- **Vegetation**, **Soil water**, **Thermal**, and **Crop water use**, each
  with an indicator-specific retained-evidence selector.  The latest retained
  observation can be shown as either its native grid or a clearly labelled
  Tabia average.  Earlier selections show only the retained Tabia average:
  TSIRD does not reconstruct a historical native raster where one was not
  retained;
- **History**, where selecting a Tabia on the map highlights it and plots the
  chosen indicator's retained observations without interpolating gaps. Final
  CHIRPS rainfall additionally offers a **Relative to normal** view: each
  monthly total is compared with that Tabia's same-calendar-month 1991--2020
  CHIRPS median and percentile. The control remains unavailable for the other
  indicators until TSIRD has retained a provider-appropriate seasonal baseline;
- **Exposure**, as separate people, cropland, and ERAA/TRRA road-proximity
  contexts, each with its own legend and reference year.  Each map is a
  direct, read-only collection of the active Tabia summaries, so selecting a
  Tabia reports the measure actually retained for that Tabia rather than a
  combined exposure score;

### Relative-to-normal baseline roadmap

- **Final CHIRPS rainfall:** ready now, using the retained 1991--2020 monthly
  climatology already supplied with the source-derived Tabia summaries.
- **Copernicus NDVI:** a candidate same-date baseline can be built from the
  available archive beginning in 2015. It must be processed and quality-checked
  before it is shown as a normal.
- **Copernicus SWI:** a candidate same-date baseline can be built from the
  available archive beginning in 2010. Its coarse native grid remains an
  essential interpretation caveat.
- **WaPOR crop water use:** a candidate same-dekad baseline can be built from
  its archive beginning in 2018; it is agricultural water-use context, not a
  food-security classification.
- **Copernicus LST:** the configured historical collection is not suitable for
  a comparable seasonal baseline. TSIRD will not manufacture one; it requires a
  reviewed replacement source first.
- **Seasonal Agricultural Stress & Response Priority** once phase 4 passes:
  a selectable three-month Tabia planning-priority map in ten ordered classes,
  an explanation panel showing contributing evidence, data-quality exclusions,
  model version, and a statement of how long the analysis should be used; and
- **Outlook** only when phase 5 passes. Until then, it explicitly says no
  reviewed provider forecast is available and draws no fabricated map.

No screen silently converts an observed layer into a forecast, or a priority
map into a food-security classification.

### Pipeline Control

The local, read-only Pipeline Control page shows phase state, source freshness,
storage capacity, provider receipts, inactive workflow policy, and recent
runner jobs. It never exposes credentials, enables schedules, retries a job,
or changes production.

## Priority-map minimum contract

Before the priority view is shown, every monthly result must state:

- analysis month and the latest usable source date for each dynamic input;
- the Tabia boundary version and evidence coverage;
- component values, standardization method, weights, and explicit missing-data
  handling;
- the ten-class legend and why a Tabia received its class;
- the intended planning-use window and when the next update supersedes it;
- a clear statement that it supports targeting and monitoring, not automatic
  eligibility, allocation, or a food-security determination.
