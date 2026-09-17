# Automatic indicator publication

## Decision

TSIRD source-derived indicator views may publish automatically after their
technical checks pass. They do not require a named human release approval.
This applies to final and preliminary rainfall, NDVI, soil water, land-surface
temperature and WaPOR crop-water-use summaries.

Priority Replay, Model Studio configuration, Scenario Laboratory outcomes,
FEWS NET provider context and any future prediction remain on the existing
named-approval release path.

## Technical gate

`tools/build_drought_indicator_release.py` reads only the fixed development
API summary endpoints and writes an immutable `-indicators` package. It
requires all six source streams to have retained Tabia rows with at least one
quality-approved observation. It rejects failed/unavailable sources and
records a visible degraded freshness state without silently relabelling it.

The companion validator accepts an `auto-validated` package only when invoked
with `--allow-auto-validated-indicators`; the standard publisher and normal
production pointer still reject it. VPS activation uses the fixed command
`activate-indicators <release-id>`, which can advance only the nested
indicator pointer and cannot advance the reviewed Priority Replay pointer.

## What this does not yet publish

The automatic package contains compact Tabia summaries, not source-native
rasters. Native raster publishing needs a separate retained COG/tile/WMS asset
contract per indicator, including source licence checks, checksum/size limits,
storage-retention rules, and a production MapServer or tile-serving path. It
must be added before the public Native raster / Tabia average switch can be
enabled.
