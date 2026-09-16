# Drought Intelligence pipeline contract

## Roles

**n8n** schedules, retries, records run state, alerts operators, and calls
controlled local ETL entrypoints. The development-only drought runner accepts
only named refresh requests and cannot run arbitrary commands. Its general
refresh endpoint is token-protected; explicit fixed development-test endpoints
are internal-only, and their read-only job-state endpoint is available to the
isolated local n8n network so it can record results without holding the runner
token.
Python/GDAL/PostGIS perform raster and
network analysis. PostGIS, MapServer, FastAPI, and the web UI expose only a
`validated` or explicitly `degraded` artifact. n8n credentials and tokens are
not copied to PostGIS, artifacts, browser files, or Git.

## First workflows

1. `observed-climate-refresh`: retrieve the requested CHIRPS current-period
   files from the Climate Hazards Center, verify the raster structure and
   Tabia-extent intersection, retain a redacted acquisition receipt (URL,
   HTTP status, timestamp, size, checksum and provider metadata), create Tabia
   summaries, validate the artifact, load local development tables, and request
   review. Baseline-period clipped caches are retained separately and must be
   refreshed through a reviewed maintenance run.
2. `chirps-preliminary-pentad-probe`: inspect the official African preliminary
   feed, validate the newest file, and report its observation end-date and age.
   It is **not** allowed to publish or overwrite the final monthly artifact.
   A source older than ten days is recorded as `degraded` and requires an
   operator investigation before any later aggregation step.
3. `chirps-preliminary-pentad-summary`: create a separate six-pentad (about
   30–31 day) Tabia **observed-rainfall total** only after a ready probe. It
   does not assign anomaly, drought, or food-security classes and cannot
   replace the final monthly artifact.
4. `chirps-preliminary-pentad-baseline`: cache matching final CHIRPS pentad
   windows for 1991–2020 and calculate a **provisional** comparative percentile.
   It must disclose the preliminary-versus-final source difference and may not
   generate a drought, food-security, or response-priority class.
5. `seasonal-outlook-refresh`: retrieve the current ICPAC outlook and retain
   source geography/period/probability. It must not create Tabia predictions.
6. `road-accessibility-baseline-refresh`: validate the local road graph, run
   documented travel-time/distance analysis, and publish a versioned baseline.
   The current local development baseline uses the ERA and TRRA-owned records
   in the published `TigrayRoads2006t` layer: nearest Federal/Regional-road
   network proximity from a Tabia point-on-surface. It must be labelled as straight-line network
   proximity rather than travel time, road condition, seasonal passability, or
   humanitarian access.
7. `ndvi-access-check`: requests a short-lived CDSE OAuth access token and
   reads metadata for the configured CLMS NDVI v3 BYOC collection. It validates
   credentials and collection entitlement only; it downloads no imagery,
   creates no remote resource, and publishes no Tabia condition.
8. `ndvi-tabia-summary`: requests one latest CLMS NDVI v3 Tigray raster at a
   near-native 300 m grid, stores it only on the local development data mount,
   and derives mean/median/coverage/QFLAG diagnostic summaries for canonical
   Tabias. It must not classify drought, food insecurity, or response priority.
9. `swi-access-check`: verifies CDSE collection access for CLMS Soil Water
   Index v4 before any raster work. A later SWI summary must retain the native
   0.1° (about 12.5 km) scale and report cell coverage; it must never imply
   that the indicator is observed at Tabia resolution.
10. `swi-tabia-summary`: retains one current 0.1-degree SWI v4 raster and
    derive separate SWI010, SWI040, and SWI100 coverage-aware zonal means.
    These are soil-water response times, not a composite index or classification.
11. `lst-access-check`: verifies CDSE collection access for CLMS LST v2 before
    any raster work. It downloads no pixels.
12. `lst-tabia-summary`: retains one latest CLMS LST v2 raster at its
    approximately 5 km hourly native grid and derives coverage-aware Tabia
    zonal summaries of land-surface temperature, provider error bar, PPP, and
    QFLAG. It must never present land-surface temperature as air temperature.
13. `population-baseline-refresh`: retain the licensed WorldPop Ethiopia
    constrained population raster for its stated reference year, validate its
    CRS, no-data semantics and Tabia intersection, and publish coverage-aware
    Tabia totals and density. It is a modeled population baseline, not an
    official census, current displacement estimate, drought exposure count, or
    response-priority score.
14. `cropland-baseline-refresh`: retain only the required ESA WorldCover 2021
    v200 tiles and summarize class 40 (cropland) to canonical Tabias. It is a
    2021 land-cover reference baseline, not current cultivation, crop output,
    food insecurity, or response-priority evidence.
15. `wapor-source-probe`: inspect the public FAO WaPOR v3 catalogue for a
    matching Level 2 dekadal transpiration (T) and AETI pair. It records only
    provider metadata, period and freshness; it downloads no raster and needs
    no API credential.
16. `wapor-tabia-summary`: retrieve only the Tigray bounding window of the
    selected provider COG pair, retain the native approximately 100 m
    transpiration raster and summarize transpiration and AETI to canonical
    Tabias. Transpiration is vegetation water-use context; AETI also includes
    evaporation/interception. Neither product establishes current crop extent,
    yield, drought, food insecurity, or response priority. Near-real-time and
    provider-final revisions must remain distinguishable in retained history.
17. `fews-net-public-classification-discovery`: inspect only the official FEWS
    NET acute-food-insecurity catalogue and an Ethiopia provider publication,
    retaining candidate public asset URLs and provenance metadata. It downloads
    no provider GIS data and cannot create a Tabia crosswalk, a TSIRD
    food-security class, an IPC determination, or a priority score. A bounded
    native-FSC asset loader requires separate approval after issue/validity
    periods, terms, schema, and provider geography are confirmed.

## Retention and time-series rule

Each source observation has a deterministic source-time run ID. New source
timestamps append a new run and its Tabia summaries; a retry of the same source
timestamp updates that run rather than duplicating it. The current dashboard
reads the newest completed run, while the History mode and API expose the local
evidence time series. No time-series chart may hide source gaps,
degraded rows, different temporal supports (monthly, pentad, 10-daily, hourly),
or a change in provider product version.

The local development backfill is bounded: it may retain at most four evenly
spaced recent catalog timestamps per Copernicus indicator. It uses the same
source-specific acquisition and load path as a normal refresh, never creates
synthetic points, and leaves the latest timestamp as the native-grid map
artifact. Any later production retention policy requires separate review.

## State machine

`queued → acquired → quality_checked → processed → validated → published`

Any run may instead end as `degraded` (usable but incomplete, with a visible
warning) or `failed`. A failed run never replaces the prior valid artifact.
Only a named reviewer can promote `validated` to `published`.

## Required controls

- Reject stale, malformed, unlicensed, or unexpected-CRS inputs.
- Use canonical Tabia IDs and a recorded boundary dataset version.
- Preserve native resolution, source time, run ID, quality/coverage, and
  uncertainty in every output.
- Keep raw downloads and generated artifacts outside Git.
- Place an approval gate before any future VPS injection.
- Notify on failure, stale source data, low coverage, or a degraded result.
- Never give n8n the Docker socket, host shell access, database credentials, or
  a production-network route.

## Artifact publication rule

The UI queries a current-artifact view, never an in-progress run. A map and
detail card must show source/provider, observation or forecast period,
processing date, native resolution, coverage, quality state, and linkable
method metadata. If no ready artifact exists, the UI says so rather than
displaying a stale fixture as current intelligence.

## Map publication geography

Seasonal outlooks are rendered at their provider geography (normally Woreda or
coarser). A future Tabia reporting display may repeat its parent Woreda value
only when it carries a visible "Woreda-scale, not Tabia prediction" warning;
it must not manufacture a Tabia forecast. The map records the complete
below-/near-/above-normal probability distribution where the provider supplies
it, plus period, lead time, issue date, and source status.

Exposure is rendered as separate Tabia measures (for example population,
cropland, road accessibility, or verified humanitarian access), each with its
own source date and legend. It must not collapse those measures into a single
unexplained risk score. Development fixtures colour only boundaries with an
available fixture record and leave all other boundaries uncoloured as no data.
