# Drought intelligence — development foundation

The first drought-intelligence milestone is a dedicated local workspace at `/map/drought/`, separate from the primary `/map/` Atlas landing page. It uses the active classic-script OpenLayers application and shared TSIRD services. The implementation foundation and source plan are in [the data-assets register](../drought/data-assets-register.md) and [pipeline contract](../drought/pipeline-contract.md).

## Current behavior

- `/map/` remains the general Atlas landing page and links to `/map/drought/`. The dedicated workspace defaults to the development CHIRPS Tabia classification layer. Its local evidence modes also include CHIRPS rapid rainfall, Copernicus NDVI/SWI/LST, and FAO WaPOR v3 agricultural water-use context.
- `ui/web/src/drought/DroughtDashboard.js` provides the workspace evidence panel. Outlook and Exposure use versioned fixtures, but its Current tab reads the latest local CHIRPS development artifact from `GET /map/api/drought/development/observed-rainfall/latest`.
- The observed-artifact response contains its run ID, provider/product/version, source-latest date, native grid resolution, quality counts, canonical Tabia IDs, and individual coverage/quality fields. It is deliberately a development-only API route.
- `ui/web/data/drought-intelligence.dev.json` keeps three roles separate: observed condition, seasonal outlook, and vulnerability/exposure.
- The panel displays source/provider, native-resolution text, update date, and an explicit development/uncertainty notice.
- Selecting a record in the panel fits and outlines the actual administrative boundary. Observed and exposure fixtures select a Tabia; the intentionally coarse seasonal-outlook fixture selects its Woreda. No town point is used as a proxy for a boundary.
- No composite risk score is calculated.

## Data contract for the next milestone

The fixture schema is `tsird-drought-intelligence.v1`. A production artifact must retain, for every source observation or forecast:

- source identifier, provider, product/version, and license;
- acquisition/valid time, publication time, and ingestion time;
- native spatial resolution and aggregation method;
- forecast reference period and lead time where applicable;
- missing-data flags, quality flags, and uncertainty/confidence metadata;
- stable Tabia identifier and boundary dataset version when an aggregation is performed.

The ingestion pipeline must validate these fields before an artifact is made available to the web application. Coarse regional or seasonal forecasts must remain labelled as regional/seasonal probabilities; they must not be rendered as precise Tabia predictions.

The local fixture uses `tsird_tabia_id` for Tabia lookup. It is a unique,
versioned boundary-record identifier that preserves the original source code and
geometry fingerprint; see [Tabia identity policy](../atlas/tabia-identity.md).
The available `T8ID` field is not unique in this boundary release, so drought
processing must retain it for traceability but must not use it as a key.

## Development limitation

The current repository does not contain a validated public drought artifact. The locally wired CHIRPS product is structurally validated but remains `development` status pending scientific review; it must not be injected into the VPS or presented as public intelligence. Outlook and Exposure remain fixtures until governed source artifacts exist.
