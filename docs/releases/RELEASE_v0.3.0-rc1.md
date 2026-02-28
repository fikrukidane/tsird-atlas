# TSIRD Phase 2 — v0.3.0-rc1 (Release Candidate)

**Released:** February 28, 2026  
**Branch:** feature/basemaps  
**Commit:** 516449d

---

## What's New

### OSM Basemap
- OSM basemap added under `cat_basemaps` (XYZ tile source)
- Basemap radio behavior (only one basemap visible at a time)
- Basemaps forced to `zIndex=0` (always rendered behind other layers)

### Display Settings Panel (commit 516449d)
- Single **Boundary Opacity** slider at top of TOC
- Applies to boundary/admin polygon layers as a group:
  - ethiopia_zones, ethiopia_woredas, ethiopia_admin, ethiopia_aoi
  - tigray_woreda, tigray_tabias
  - ethiopia_boundary_level1, ethiopia_boundary_level2, ethiopia_boundary_level3
- Persisted to `localStorage` (remembers user preference)
- Only visible when basemap or raster layer is active

### Labels
- **Tigray Tabias:** Labels appear at 1:500,000 and below
- **Tigray Woredas:** Labels using `WEREDA` field, appear at 1:2,000,000 and below
- **Ethiopia Woredas:** Labels appear at 1:2,000,000 and below

### Tigray Towns Styling
- Red star symbols (replacing circles)
- Graduated sizes based on population

---

## What's Retained from v0.2.0

- WMS-only architecture (no WFS)
- Scale enforcement + mutex pairs
- GetFeatureInfo allowlist filtering
- Legend support for all vector layers
- Multi-source layer stack

---

## Known Limits / Pending Polish

- [ ] External WMS catalog not yet implemented (MODIS/VIIRS/etc.)
- [ ] Cartographic normalization pass still pending for full layer stack
- [ ] Performance baseline + load testing not completed
- [ ] MapCache still deferred to Phase 3

---

## Acceptance Checklist

- [ ] OSM loads as basemap
- [ ] Toggle basemaps behaves like radio buttons
- [ ] Boundary opacity slider appears only when basemap/raster visible
- [ ] Slider affects all boundary layers and persists after refresh
- [ ] WMS layers still render and GetFeatureInfo works

---

## Commits Since v0.2.0

```
516449d UX: Replace per-layer opacity sliders with global Display Settings panel
c05e1d4 Style: Change Tigray Towns to red stars
145da42 Fix: Use WEREDA field for Woreda labels (wor_name has corrupted data)
433b822 Labels: Show Woreda/Tabia names at reasonable zoom levels
df65b2c Set default opacity to 50% for all polygon layers
0cf3e47 Feat: Add opacity slider for polygon layers
9e81b1c Fix: Pass basemap fields through RegistryLoader
1ef2def Feat: Basemap radio behavior in TOC
84032be Feat: Add XYZ basemap support in LayerFactory
0069b06 Feat: Add basemap category + OSM to registry
```
