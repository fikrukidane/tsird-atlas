# TSIRD Phase 2 - Stage 6 Milestone 2 Frontend

**Status**: ✅ Complete  
**Version**: 0.2.0  
**Scope**: Scale enforcement + mutex pairs + GetFeatureInfo + UI polish  
**Reference**: [STAGE6_FRONTEND.md](../../docs/phase2/STAGE6_FRONTEND.md)  
**Task List**: [STAGE6_MILESTONE2_TASKS.md](../../docs/phase2/STAGE6_MILESTONE2_TASKS.md)  

---

## Overview

Milestone 2 extends the frontend with production-ready features:

1. **ScaleEngine** — Cartographic scale calculations and visibility rules
2. **Mutex Enforcement** — Scale-based mutual exclusion for roads/towns pairs
3. **GetFeatureInfo** — Click-based attribute queries with allowlist filtering
4. **InteractionController** (extended) — Scale monitoring + mutex logic + identify
5. **UI Polish** — Out-of-scale indicators, feature info popup, error handling

**Milestone 1 deliverables** (retained):
- RegistryLoader — Load and normalize YAML/JSON registry
- MapController — OpenLayers map with CRS transformation
- LayerFactory — Create TileWMS layers (published only)
- InteractionController — TOC rendering + layer toggle
- HTML/CSS — Responsive layout (map 70%, TOC 30%)

---

## Directory Structure

```
ui/web/
├── index.html                    # Entry point (Milestone 2 updated)
├── css/
│   └── style.css                # Responsive layout + M2 styles
├── src/
│   ├── main.js                  # Orchestration (M2 extended)
│   ├── registry/
│   │   └── RegistryLoader.js   # Load + normalize registry
│   ├── map/
│   │   ├── MapController.js    # OL map init + CRS
│   │   ├── LayerFactory.js     # Create TileWMS layers
│   │   └── ScaleEngine.js      # NEW: Scale calculations
│   └── interactions/
│       └── InteractionController.js  # TOC + toggle + scale + mutex + identify
├── data/
│   ├── atlas-registry.yaml     # Development registry (YAML)
│   └── atlas-registry.json     # Development registry (JSON, with mutex pairs)
├── test/
│   └── (Unit tests — Future)
└── package.json                # Dependencies (CDN-based)
```

---

## Getting Started

### Development Server

```bash
# Option 1: Using http-server (requires Node.js)
cd ui/web
npm run serve

# Option 2: Using Python 3
python3 -m http.server 8000 -d ui/web

# Option 3: Using PHP
php -S localhost:8000 -t ui/web
```

Then open: `http://localhost:8000`

### Verify Registry

```bash
# From project root
python3 tools/validate_registry.py ui/web/data/atlas-registry.json
```

Should output: `✓ All constraints passed`

---

## Module Architecture

### RegistryLoader

**Purpose**: Load and normalize YAML/JSON registry

**Input**: Path to registry file (YAML or JSON)

**Output**:
```javascript
{
  atlasConfig: { title, center, zoom, canonical_crs, view_crs, extent },
  wmsBaseUrl: "/map/ogc",
  tocModel: [ categories → groups → layers ],
  layerDefs: { [layer_id]: { wms_name, label, published, ... } },
  scaleMutexPairs: [ [id1, id2], ... ]
}
```

### MapController

**Purpose**: Initialize OpenLayers map with CRS handling

**Features**:
- Map projection = view_crs (EPSG:3857)
- Transform center: canonical_crs → view_crs
- Transform extent and apply as constraint
- Resolution-to-scale conversion utility

### LayerFactory

**Purpose**: Create OpenLayers WMS layers from registry

**Features**:
- Published layers only
- ImageWMS source (simpler, better MapServer compatibility)
- Stable WMS params (FORMAT=image/png, TRANSPARENT=true)
- No WFS
- Metadata attached to layers

### InteractionController

**Purpose**: TOC rendering, layer toggle, scale enforcement, mutex logic, GetFeatureInfo

**Milestone 1 Features**:
- TOC hierarchy rendering (categories → groups → layers)
- Per-layer toggle (checkbox ↔ visibility)
- Group toggle (children respecting defaults)
- Default visibility initialization

**Milestone 2 Features (NEW)**:
- Scale-dependent visibility (auto-hide/show on zoom)
- Mutex pair enforcement (roads/towns never overlap)
- GetFeatureInfo on map click (queryable layers only)
- Attribute allowlist filtering (identify_fields)
- Out-of-scale visual indicators in TOC
- Popup rendering with filtered attributes
- **Legend display** (WMS GetLegendGraphic integration)

### Legend Feature (NEW - February 2026)

**Purpose**: Display WMS legend graphics inline within the TOC for each layer

**Implementation**:
- Toggle button (◧) in each layer row
- Fetches legend via WMS GetLegendGraphic request on first click
- Caches legend image after initial load
- Handles loading/error states gracefully

**UI Components**:
- `.toc-legend-toggle` — Button with ◧/◨ icon
- `.toc-legend-container` — Collapsible container with blue left border
- `.toc-legend-header` — "LEGEND" label in bold
- `.toc-legend-image` — Loaded PNG from MapServer

**Usage**:
```javascript
// In InteractionController._renderLayer():
// Creates toggle button and legend container
// Calls _loadLegend() on first expand

_loadLegend(wmsName, container) {
  const legendUrl = `${wmsBaseUrl}?SERVICE=WMS&VERSION=1.3.0` +
    `&REQUEST=GetLegendGraphic&LAYER=${wmsName}` +
    `&FORMAT=image/png&SLD_VERSION=1.1.0`;
  // Fetch and display...
}
```

**Requirements**:
- MapServer LEGEND object in mapfile (KEYSIZE, KEYSPACING, LABEL)
- Each LAYER must have at least one CLASS with NAME attribute
- Layer STATUS must be ON

### ScaleEngine (NEW - Milestone 2)

**Purpose**: Cartographic scale calculations and layer visibility rules

**Convention** (frozen):
- `min_scale`: Largest denominator (most zoomed out)
- `max_scale`: Smallest denominator (most zoomed in)
- Layer visible if: `max_scale <= current_scale <= min_scale`

**Features**:
- `getScaleDenominator(resolution)`: OL resolution → cartographic scale
- `isLayerInScale(layerDef, currentScale)`: Check if layer should be visible
- `getCurrentScale(view)`: Get current scale from map view
- `formatScale(scale)`: Human-readable scale string (e.g., "1:5,000,000")

**Example**:
```javascript
// Layer: ethiopia_roads (min=50000000, max=1000001)
// At 1:5M scale: VISIBLE (1000001 <= 5000000 <= 50000000)
// At 1:500K scale: NOT VISIBLE (500000 < 1000001)

const currentScale = ScaleEngine.getCurrentScale(view);
const inScale = ScaleEngine.isLayerInScale(layerDef, currentScale);
```

---

## Testing Checklist (Milestone 2 DoD)

**Milestone 1 Tests** (retain all):
- [x] Map loads without errors
- [x] View fits registry extent
- [x] Center/zoom match registry (after CRS transform)
- [x] TOC renders in correct order
- [x] Default visibility matches registry
- [x] Layer checkboxes toggle visibility
- [x] Only published layers appear in TOC
- [x] WMS GetMap requests to `/map/ogc`
- [x] Stable WMS params (FORMAT, TRANSPARENT, TILED)
- [x] No WFS GetFeature calls
- [x] Console clean (no errors)
- [x] Responsive layout works

**Milestone 2 Tests (NEW)**:
- [ ] **Scale Constraints**: Zoom in/out: Layers hide/show based on scale ranges
- [ ] **Mutex: Roads**: Toggle both ethiopia_roads + tigray_roads_2006 ON
  - At 1:5M scale (zoomed out): Only ethiopia_roads visible
  - At 1:500K scale (zoomed in): Only tigray_roads_2006 visible
  - Handoff at 1:1,000,000 scale: Clean transition, no overlap
- [ ] **Mutex: Towns**: Toggle both ethiopia_towns + tigray_towns ON
  - At 1:5M scale: Only ethiopia_towns visible
  - At 1:1M scale: Only tigray_towns visible
  - Handoff at 1:2,000,000 scale: Clean transition
- [ ] **GetFeatureInfo**: Click on queryable layer (e.g., tigray_health_facilities_2006)
  - Popup appears with attributes
  - Only fields in `identify_fields` displayed
  - Non-queryable layers do not respond to clicks
- [ ] **Out-of-Scale Indicator**: Layer out of scale shows grayed style in TOC with "(out of scale)" label
- [ ] **Mutex Suppressed Indicator**: Suppressed layer shows "(suppressed)" label
- [ ] **WMS Traffic**: DevTools Network tab shows GetFeatureInfo requests on click, no WFS
- [ ] **Error Resilience**: Test with MapServer down → friendly error (not stack trace)

---

**✓ TSIRD Phase 2 Milestone 1 — Frontend Skeleton In Development**
