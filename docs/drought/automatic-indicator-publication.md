# Automatic indicator publication

## Decision

TSIRD source-derived indicator views may publish automatically after their
technical checks pass. They do not require a named human release approval.
This applies to final and preliminary rainfall, NDVI, soil water, land-surface
temperature and WaPOR crop-water-use summaries.

The same automatic package carries the six fixed, display-ready native-grid
TIFF derivatives already used in development. They preserve provider-grid
resolution and physical values, but are not provider archives or a new
analysis: source archives, credentials, model outputs, priority replay and
FEWS NET context remain outside this channel.

Priority Replay, Model Studio configuration, Scenario Laboratory outcomes,
FEWS NET provider context and any future prediction remain on the existing
named-approval release path.

## Technical gate

`tools/build_drought_indicator_release.py` reads only the fixed development
API summary endpoints and writes an immutable `-indicators` package. It
requires all six source streams to have retained Tabia rows with at least one
quality-approved observation. It rejects failed/unavailable sources and
records a visible degraded freshness state without silently relabelling it.
It also requires exactly six safe, regular TIFF files from the local
display-ready `data/drought/published` directory. The package validator checks
their fixed names, checksums and observation windows before the indicator
pointer can advance.

The companion validator accepts an `auto-validated` package only when invoked
with `--allow-auto-validated-indicators`; the standard publisher and normal
production pointer still reject it. VPS activation uses the fixed command
`activate-indicators <release-id>`, which can advance only the nested
indicator pointer and cannot advance the reviewed Priority Replay pointer.

## Native-raster serving contract

The activation utility atomically advances both `indicators/current.json` and
the sibling `indicators/current` directory symlink. Production MapServer mounts
only that parent directory read-only and serves six fixed WMS layer names from
the immutable display-ready copies. This enables the existing Native raster /
Tabia average switch without mounting development `data/drought`, a source
archive, n8n state, or credentials on the VPS.
