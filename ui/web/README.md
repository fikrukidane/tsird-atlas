# TSIRD Phase 2 - Stage 6 Milestone 1 Frontend

**Status**: 🚀 In Development  
**Version**: 0.1.0  
**Scope**: Basic map + registry-driven TOC + tiled WMS rendering  
**Reference**: [STAGE6_FRONTEND.md](../../docs/phase2/STAGE6_FRONTEND.md)  
**Task List**: [STAGE6_MILESTONE1_TASKS.md](../../docs/phase2/STAGE6_MILESTONE1_TASKS.md)  

---

## Overview

Milestone 1 implements the foundational frontend:

1. **RegistryLoader** — Load and normalize YAML/JSON registry
2. **MapController** — OpenLayers map with CRS transformation
3. **LayerFactory** — Create TileWMS layers (published only)
4. **InteractionController** — TOC rendering + layer toggle
5. **HTML/CSS** — Responsive layout (map 70%, TOC 30%)

**NOT included in Milestone 1**:
- Identify (GetFeatureInfo) — deferred to Milestone 2
- Scale enforcement — deferred to Milestone 2
- Search UI — deferred to Phase 3

---

## Directory Structure

```
ui/web/
├── index.html                    # Entry point
├── css/
│   └── style.css                # Responsive layout
├── src/
│   ├── main.js                  # Orchestration
│   ├── registry/
│   │   └── RegistryLoader.js   # Load + normalize registry
│   ├── map/
│   │   ├── MapController.js    # OL map init + CRS
│   │   └── LayerFactory.js     # Create TileWMS layers
│   └── interactions/
│       └── InteractionController.js  # TOC + toggle
├── data/
│   ├── atlas-registry.yaml     # Development registry (YAML)
│   └── atlas-registry.json     # Development registry (JSON)
├── test/
│   └── (Unit tests — Milestone 2)
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

**Purpose**: Create TileWMS layers from registry

**Features**:
- Published layers only
- Stable WMS params (FORMAT=image/png, TRANSPARENT=true, TILED=true)
- No WFS
- Metadata attached to layers

### InteractionController

**Purpose**: TOC rendering and layer toggle (Milestone 1 scope)

**Features**:
- TOC hierarchy rendering (categories → groups → layers)
- Per-layer toggle (checkbox ↔ visibility)
- Group toggle (children respecting defaults)
- Default visibility initialization

---

## Testing Checklist (Milestone 1 DoD)

- [ ] Map loads without errors
- [ ] View fits registry extent
- [ ] Center/zoom match registry (after CRS transform)
- [ ] TOC renders in correct order
- [ ] Default visibility matches registry
- [ ] Layer checkboxes toggle visibility
- [ ] Only published layers appear in TOC
- [ ] WMS GetMap requests to `/map/ogc`
- [ ] Stable WMS params (FORMAT, TRANSPARENT, TILED)
- [ ] No WFS GetFeature calls
- [ ] Console clean (no errors)
- [ ] Responsive layout works

---

**✓ TSIRD Phase 2 Milestone 1 — Frontend Skeleton In Development**
