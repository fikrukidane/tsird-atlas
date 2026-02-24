# Phase 2 - Step 3: Stage 6 Milestone 1 (Implementation Task List)

**Objective**: Implement basic map + registry-driven TOC + tiled WMS rendering (NO identify yet)

**Reference**: [STAGE6_FRONTEND.md](STAGE6_FRONTEND.md) Sections 1-4

**Duration Estimate**: 5–7 working days (solo developer)

---

## Task Breakdown

### Module 1: RegistryLoader

**File**: `ui/web/js/modules/RegistryLoader.js`

- [ ] **1.1**: Create RegistryLoader class
  - Constructor accepts registry path (YAML or JSON)
  - `load()` method fetches and parses registry
  - Validate basic shape (CONFIG_MODEL.md structure)
  
- [ ] **1.2**: Output normalized data structure
  - `atlasConfig` (title, center, zoom, extent, CRS)
  - `tocModel` (ordered categories → groups → layers)
  - `layerDefs` (layer metadata keyed by layer_id)
  - `scaleMutexPairs` (from rules)
  
- [ ] **1.3**: Error handling
  - Log file-not-found clearly
  - Parse errors show helpful messages
  - Emit `onError` event for UI

**Acceptance Criteria**:
- [ ] Registry loads from both YAML (build-time) and JSON (runtime)
- [ ] `atlasConfig` properties accessible as expected
- [ ] `tocModel` preserves YAML order
- [ ] `layerDefs` indexed by ID with all metadata keys present
- [ ] Error messages non-technical (user-facing)

---

### Module 2: MapController

**File**: `ui/web/js/modules/MapController.js`

- [ ] **2.1**: Initialize OpenLayers map
  - Set projection to EPSG:3857 (view_crs)
  - Create View object
  - Create Map with HTMLElement target
  
- [ ] **2.2**: Apply atlas configuration
  - Read center from atlasConfig (in EPSG:4326)
  - Transform to EPSG:3857 using ol.proj.transform
  - Set map view center to transformed coordinate
  - Set map view zoom level
  
- [ ] **2.3**: Apply extent constraint
  - Read extent from atlasConfig (in EPSG:4326)
  - Transform to EPSG:3857 using ol.proj.transformExtent
  - Fit map view to extent (ol.View.fit)
  
- [ ] **2.4**: Resolution-to-scale utility function
  - Implement `getScaleDenominator(resolution)` helper
  - Assume 96 DPI (standard web)
  - Return cartographic scale denominator

**Acceptance Criteria**:
- [ ] Map initializes without console errors
- [ ] Map center visible at expected location (spot-check with lat/lon)
- [ ] Zoom level matches YAML (or browser auto-fit respects extent)
- [ ] Extent constraint prevents panning outside bounds
- [ ] Scale function returns sensible values (e.g., 1M at zoom 7)

---

### Module 3: LayerFactory

**File**: `ui/web/js/modules/LayerFactory.js`

- [ ] **3.1**: Create TileWMS layers from registry
  - For each layer with `published: true`
  - Create `ol.source.TileWMS`
  - Create `ol.layer.Tile` wrapping the source
  
- [ ] **3.2**: Configure WMS parameters
  - LAYERS param: layer's `wms_name`
  - TILED: true (cache-friendly)
  - TRANSPARENT: true (for overlays)
  - FORMAT: image/png (fixed)
  - CRS: automatic (ol.source.TileWMS handles projection)
  
- [ ] **3.3**: Store metadata on layer object
  - Attach `layerDef` to layer (for later GetFeatureInfo)
  - Attach `layerId` to layer
  - Ensure properties accessible for InteractionController
  
- [ ] **3.4**: Return layers ordered by YAML
  - Iterate tocModel → collect all layers
  - Maintain YAML iteration order
  - Return array of ol.layer.Tile objects

**Acceptance Criteria**:
- [ ] All published layers create TileWMS sources
- [ ] WMS tiles download over network (no WFS calls)
- [ ] Layer titles visible in DevTools network tab
- [ ] Metadata accessible: `layer.layerDef.wms_name` === wms_name
- [ ] TILED=true in request URL (DevTools)

---

### Module 4: InteractionController (Partial — TOC Only)

**File**: `ui/web/js/modules/InteractionController.js`

- [ ] **4.1**: Render TOC (Table of Contents)
  - Traverse `tocModel` (categories → groups → layers)
  - Create nested <ul> list structure
  - Add checkbox for each layer
  - Add labels matching YAML
  
- [ ] **4.2**: Implement per-layer toggle
  - Checkbox listener calls `toggleLayer(layerId, enabled)`
  - Set `layer.setVisible(enabled)` on corresponding ol.layer.Tile
  - Update UI state (checked/unchecked)
  
- [ ] **4.3**: Implement default visibility
  - At startup, set layer visibility per `default_visible` in layerDef
  - Example: `national_roads` is `default_visible: true` → shown
  - Others are `default_visible: false` → hidden
  
- [ ] **4.4**: Group toggle (optional but recommended)
  - Checkbox for group label toggles all child layers
  - When toggled on: show all children (no scale check yet)
  - When toggled off: hide all children

**Acceptance Criteria**:
- [ ] TOC renders without errors
- [ ] Checkboxes align with layer visibility on map
- [ ] Default visibility matches YAML (spot-check 2–3 layers)
- [ ] Toggling layer off → map updates immediately
- [ ] Toggling group off → all children hide

---

### UI Integration

**File**: `ui/web/index.html`

- [ ] **5.1**: Create HTML structure
  - `<div id="map-container"></div>` (map)
  - `<div id="toc-container"></div>` (TOC)
  - Basic responsive CSS (map 70%, TOC 30%)
  
- [ ] **5.2**: Load dependencies
  - OpenLayers 8+ (CDN or bundled)
  - js-yaml (for YAML parsing if YAML registry)
  - Module scripts in correct order
  
- [ ] **5.3**: Bootstrap application
  - Orchestration in `js/main.js`:
    1. Initialize RegistryLoader
    2. Initialize MapController
    3. Initialize LayerFactory
    4. Initialize InteractionController
    5. Attach event listeners

**Acceptance Criteria**:
- [ ] Page loads without 404s
- [ ] Map visible and interactive
- [ ] TOC sidebar visible with layer list
- [ ] No console errors or warnings

---

## Testing (Milestone 1)

### Unit Tests

**File**: `test/test-registry-loader.js` (example framework: Jest or Mocha)

- [ ] Load good YAML, verify structure
- [ ] Reject bad registry (missing keys)
- [ ] Parse JSON fallback

**File**: `test/test-map-controller.js`

- [ ] Center transformation (EPSG:4326 → EPSG:3857)
- [ ] Extent transformation
- [ ] Scale denominator calculation

**File**: `test/test-layer-factory.js`

- [ ] Create TileWMS for published layers only
- [ ] Skip unpublished layers
- [ ] Verify metadata storage

### Integration Test

- [ ] Load registry → create map → add layers → toggle one layer
- [ ] Verify no console errors
- [ ] Verify map tile request contains expected WMS params

### Manual Testing (Browser)

- [ ] Open `index.html` in browser
- [ ] Verify map loads with initial zoom/center
- [ ] Verify map tiles load (DevTools Network tab)
- [ ] Toggle each layer in TOC
  - Layer disappears from map ✓
  - Layer reappears when toggled on ✓
- [ ] Check Network tab: no WFS calls (only GetMap)

---

## Definition of Done (Milestone 1)

All must be true:

- [ ] **Code**: All 4 modules implemented and integrated
- [ ] **Interface**: TOC renders correctly, map visible
- [ ] **Behavior**: Toggle works, visibility matches YAML
- [ ] **Testing**: Unit tests pass, manual confirmation passes
- [ ] **Network**: WMS GetMap requests only (no WFS)
- [ ] **Errors**: Console clean (no errors or warnings)
- [ ] **Review**: Peer review (or self-review) complete
- [ ] **Commit**: Code committed with clear message

---

## Known Constraints (Milestone 1 Only)

- **NO Identify yet**: GetFeatureInfo popup deferred to Milestone 2
- **NO Scale Rules**: Min/max scale enforcement deferred to Milestone 2
- **NO Mutex**: Scale-dependent mutual exclusion deferred to Milestone 2
- **NO Search**: Always empty (Phase 3)
- **NO Error Handling**: Page errors acceptable in Milestone 1 (hardened in Milestone 2)

---

## Deliverables

```
ui/web/
├── index.html
├── js/
│   ├── main.js
│   └── modules/
│       ├── RegistryLoader.js
│       ├── MapController.js
│       ├── LayerFactory.js
│       └── InteractionController.js
├── css/
│   └── style.css
└── data/
    └── atlas-registry.json (or reference to YAML source)

test/
├── test-registry-loader.js
├── test-map-controller.js
└── test-layer-factory.js
```

---

## Risk Mitigation

| Risk | Mitigation |
|---|---|
| YAML parsing fails | Pre-build registry as JSON; test both formats |
| CRS transformation wrong | Test with known coordinate; verify against map visuals |
| WMS request format incorrect | Inspect DevTools Network tab; compare to Stage 2 spec |
| TOC toggle doesn't sync with map | Log layer visibility state; add UI indicators |
| Layer order wrong | Verify `tocModel` preserves YAML order; add test |

---

## Next Stage (Milestone 2)

Once Milestone 1 passes Definition of Done:

1. Add scale-dependent visibility (min/max scale rules)
2. Enforce scale mutex pairs (roads/towns mutual exclusion)
3. Implement GetFeatureInfo on click
4. Add attribute allowlisting for identify popup
5. Full error handling and resilience
6. Performance optimization (tile caching, request batching)

**Milestone 2 target date**: immediately after Milestone 1 sign-off

---

**✓ END OF STAGE 6 MILESTONE 1 TASK LIST**

This task list is your working document. Track progress, update checkboxes, commit at each phase boundary.
