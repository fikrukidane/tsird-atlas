# Historical evidence replay — development policy

## Purpose

Historical views let a user inspect the measured evidence recorded for a past
period at Tabia level. They are useful for learning seasonal context and for
checking whether a future decision logic behaves plausibly across different
months.

They are **not** a retrospective claim that a forecast or a decision product
was available on that historical date.

## Two distinct products

1. **Evidence timeline** — archived observations keyed to their source
   observation period. This is the first development product. It can answer,
   for example, “what did the May 2026 CHIRPS rainfall evidence show for this
   Tabia?”
2. **As-issued decision replay** — a later, stricter validation product. It
   must use only inputs demonstrably available before a defined decision
   cutoff, with documented source publication latency and the schedule that
   would have run at that time.

The user interface and API must label the first product as **Historical
evidence snapshot**. It must not be called a forecast, model backtest, or
historical priority score.

## Initial 2026 development timeline

The initial evidence timeline preserves bounded native provider rasters and
matching Tabia summaries. All derived records use the full canonical boundary
set; the native grid is retained at the provider's stated resolution and is
never represented as a Tabia-scale measurement.

| Snapshot period | Retained evidence | Decision-use caveat |
| --- | --- | --- |
| January–April 2026 | NDVI, SWI-040, LST, and WaPOR third-dekad transpiration | Retrieval time is not proof of the provider's original publication time. |
| May–June 2026 | Same indicators, including retained additional LST snapshots | Use only as historical context until provider-latency rules are recorded. |
| July–August 2026 | NDVI, SWI-040, and WaPOR third-dekad transpiration | No accessible CDSE LST item was available near the requested monthly snapshot dates; the timeline must show that gap rather than fill it. |
| May–August 2026 | CHIRPS monthly rainfall, with 1991–2020 same-month baseline | This is observation evidence, not an as-issued forecast or decision replay. |

All 748 canonical `tsird_tabia_id` records are retained. The 65 records with a
duplicate source `T8ID` remain review flags; they are not omitted.

## API contract

- `GET /map/api/drought/development/observed-rainfall/latest` returns the
  newest source observation period, not the most recently imported artifact.
- `GET /map/api/drought/development/observed-rainfall/runs` lists retained
  monthly evidence snapshots without returning all records.
- `GET /map/api/drought/development/observed-rainfall/runs/{run_id}` returns
  a deliberately selected historical snapshot. It includes an explicit
  archived-observation label and no-look-ahead caveat.
- The Tabia History view reads retained source-run records. It plots only
  actual observation timestamps and leaves provider gaps visible; a historical
  record marked `degraded` is old relative to the current date, not a claim
  that the historical raster or Tabia aggregation failed.
- `GET /map/api/drought/development/evidence/{ndvi|swi|lst|wapor}/runs`
  lists retained native evidence snapshots without filesystem paths. The
  associated fixed raster URL is catalogue-addressed and may serve only the
  matching retained GeoTIFF from the local read-only development mount.

## Conditions before an as-issued replay or score validation

Before calculating any historical Seasonal Agricultural Stress & Response
Priority result, record the following per source and run:

- source observation timestamp and provider publication/availability time;
- the source version/revision and any later revision policy;
- the scheduled processing cutoff in Addis Ababa time;
- the exact boundary version and static reference layers;
- data-quality state and missing-data handling at that cutoff;
- independent evaluation material, such as reviewed field reports, without
  feeding it into the score.

The resulting comparison must report agreement, disagreement, and unknown
areas. It cannot certify a food-security or famine outcome.
