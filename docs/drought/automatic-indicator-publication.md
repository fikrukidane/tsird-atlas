# Automatic indicator publication

## Decision

TSIRD source-derived indicator views may publish automatically after their
technical checks pass. They do not require a named human release approval.
This applies to final and preliminary rainfall, NDVI, soil water, land-surface
temperature and WaPOR crop-water-use summaries. The separately approved HLS
vegetation-moisture view is packageable as `manual-experimental`: the release
preserves its last validated all-Tabia snapshot but creates no schedule,
provider retry policy, raw-raster release or operational use.

The same automatic package carries the six fixed, display-ready native-grid
TIFF derivatives already used in development. They preserve provider-grid
resolution and physical values, but are not provider archives or a new
analysis: source archives, credentials, model outputs, priority replay and
FEWS NET context remain outside this channel.

Priority Replay, Model Studio configuration, Scenario Laboratory outcomes,
FEWS NET provider context and any future prediction remain on the existing
named-approval release path.

## Technical gate

`tools/build_drought_indicator_release.py` reads only fixed development API
summary endpoints and writes an immutable `-indicators` package. It
requires all six source streams to have retained Tabia rows with at least one
quality-approved observation. It rejects failed/unavailable sources and
records a visible degraded freshness state without silently relabelling it.
It also requires exactly six safe, regular TIFF files from the local
display-ready `data/drought/published` directory. The package validator checks
their fixed names, checksums and observation windows before the indicator
pointer can advance. It also carries the retained source-run indexes and
compact per-Tabia values needed by the rainfall snapshot selector and History
map/date comparisons. Tabia boundary geometry is copied once and joined to
each compact run by its stable ID; raw rasters and provider archives are never
duplicated for history. The same package carries the three static, independent
Tabia exposure baselines (People, Cropland and Road proximity) so the shared
public Exposure controls use released records rather than any development API.

The companion validator accepts an `auto-validated` package only when invoked
with `--allow-auto-validated-indicators`; the standard publisher and normal
production pointer still reject it. VPS activation uses the fixed command
`activate-indicators <release-id>`, which can advance only the nested
indicator pointer and cannot advance the reviewed Priority Replay pointer.

## Freshness and forward-only publication

`n8n/publisher/drought-indicator-freshness-contract.json` is the one declared
cadence contract for the six scheduled source-derived views. Every automatic package
must contain per-source `source_observation_end`, `expected_next`,
`stale_after`, and `automation_state` metadata derived from that contract.
The release validator refuses an automatic package without it, and the public
indicator endpoint exposes the same records for the map UI and monitoring.

The automatic activation command is a one-way data ratchet: it compares each
candidate source observation end with the current indicator package and
refuses any candidate that would make a source older. Validation, transfer,
or activation failure leaves the existing pointer unchanged. Equal dates are
allowed because a source may correct a value for the same observation period.

The current contract is intentionally honest about capability: CHIRPS final
and rapid rainfall are automatic; NDVI, SWI and WaPOR remain
`manual-until-acquisition`; HLS NDMI remains `manual-experimental`; thermal is
`replacement-required` because the upstream LST product is superseded. Those
states are visible, rather than being presented as successfully automated feeds.

Run `tools/monitor_drought_public_freshness.py` from a scheduler outside n8n
with an ignored state file. It reads only the public indicator metadata, emits
one notification when freshness becomes stale/unreachable and one recovery
notification when the state changes back. Telegram credentials are optional
environment variables (`TSIRD_MONITOR_TELEGRAM_BOT_TOKEN` and
`TSIRD_MONITOR_TELEGRAM_CHAT_ID`) and must never be committed. This is a
public-freshness deadman; it does not grant the monitor any access to n8n,
source data, releases, or production activation.

## Native-raster serving contract

The activation utility atomically advances both `indicators/current.json` and
the sibling `indicators/current` directory symlink. Production MapServer mounts
only that parent directory read-only and serves six fixed WMS layer names from
the immutable display-ready copies. This enables the existing Native raster /
Tabia average switch without mounting development `data/drought`, a source
archive, n8n state, or credentials on the VPS.

## Automatic n8n publication

The tracked automatic publisher is intentionally a separate inactive n8n
workflow. It coalesces the current retained evidence, its retained
observation-history assets, and the six display rasters into one package. It
publishes only when the six summary streams pass the technical gate and its
fingerprint differs from the last successful automatic package. This keeps
ordinary source-derived evidence dynamic in production while the reviewed
Priority Replay remains on its separate approval path.
The fixed workflow, restricted keys, pinned server key, and narrow read-only
native-raster mount are documented in
[n8n automatic indicator publisher setup](n8n-automatic-indicator-publisher-setup.md).
