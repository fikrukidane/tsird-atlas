# TSIRD Atlas v0.2.0 Release Notes

**Release Date**: February 28, 2026  
**Tag**: `v0.2.0`  
**Status**: Stable Baseline  

---

## What's Included

### Frontend (Phase 2 Milestone 2 Complete)

- **Scale-dependent visibility** — Layers auto-hide/show based on zoom level and registry scale constraints
- **Mutex pair enforcement** — Roads and towns pairs mutually exclude at scale boundaries (no overlap)
- **GetFeatureInfo with allowlist** — Click-to-identify with filtered attribute display (`identify_fields`)
- **Legend integration** — WMS GetLegendGraphic fetched inline within TOC (◧ toggle per layer)
- **Out-of-scale indicators** — Visual feedback in TOC when layers are outside visible scale range
- **Popup rendering** — Attribute popups for queryable layers with clean formatting

### MapServer (33 Layers Published)

- **20 styled vector layers** — Custom CLASS/STYLE definitions with colors, outlines, line widths
- **LEGEND object configured** — KEYSIZE 20x12, KEYSPACING 5x5, Arial font labels
- **CLASS NAME attributes** — Added to 13 layers for proper GetLegendGraphic support
- **Font and symbol assets** — Arial fonts and symbol definitions added for cartographic rendering

### Layer Categories

| Category | Layers |
|----------|--------|
| Administrative (Regional) | ethiopia_zones, ethiopia_woredas, tigray_tabias, ethiopia_admin, ethiopia_boundary_level1/2/3 |
| Infrastructure | Roads (5 layers), rivers, streams, ponds, perennial rivers |
| Terrain | ethiopia_dem, ethiopia_slope, contours, isoheight |
| Rainfall & Climate | ethiopia_major_basins, rainfall_pattern, rainfall_stations |
| Points of Interest | towns, schools, health facilities |

### Documentation

- Updated `COMPLETION.md` with Phase 7 (Style Migration & Legend UI)
- Updated `ui/web/README.md` with Legend Feature section
- Updated main `README.md` system status

---

## What's NOT Included

- **Search functionality** — Deferred to future milestone
- **MapCache/tile caching** — Not yet implemented
- **External basemaps** — OpenStreetMap/satellite basemaps not yet integrated
- **WFS/WCS services** — Read-only WMS only

---

## Known Limitations

- **Cartographic refinement pending** — Some layer styles are functional but not production-polished
- **Portal polish pending** — UI/UX refinements for public-facing deployment not complete
- **Label rendering** — Layer labels not yet implemented (feature deferred)
- **Print/export** — No print or PDF export functionality
- **Mobile optimization** — Responsive but not mobile-first

---

## Upgrade Path

This release serves as the **stable baseline** before introducing:

1. External basemaps (OpenStreetMap, satellite imagery)
2. Tile caching for improved performance
3. Additional cartographic styling
4. Search and filtering features

---

## Verification

```bash
# Verify tag exists
git tag -l "v0.2.0"

# Verify on GitHub
# https://github.com/fikrukidane/tsird-atlas/releases/tag/v0.2.0

# Test WMS service
curl -s "http://localhost:18080/map/ogc?SERVICE=WMS&REQUEST=GetCapabilities" | head -20
```

---

**Baseline Locked**: This version is frozen as the known-good state before external basemap integration.
