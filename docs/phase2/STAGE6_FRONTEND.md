# Phase 2 - Stage 6: Frontend Implementation Contract

**Generated**: 2026-02-24  
**Status**: ✓ FRONTEND CONTRACT FROZEN  
**Scope**: OpenLayers Client, Registry Consumption, WMS Integration

---

## Overview

This document defines how the Phase 2 frontend (OpenLayers 8+) integrates with the TSIRD Phase 2 architecture:

- **Single Source of Truth**: `atlas-registry.yaml` governs all UI behavior
- **WMS-First Architecture**: All tile rendering via WMS GetMap (tiled, cache-friendly)
- **No Search Backend**: Phase 2 has empty search array; search deferred to Phase 3
- **Scale Enforcement**: Roads/towns mutual exclusion enforced in client + MapServer layers
- **Proxy-Only Access**: Frontend reaches WMS only through NGINX edge proxy (Stage 2)

---

## 1. Non-Negotiable Inputs

### 1.1 Registry (`atlas-registry.yaml`)

Single source of truth for **all UI state and behavior**:

| Registry Section | Frontend Usage |
|---|---|
| `atlas.view_crs` | Map projection (EPSG:3857) |
| `atlas.canonical_crs` | Input CRS for center/extent (EPSG:4326) |
| `atlas.center` | Initial map center (in canonical_crs) |
| `atlas.zoom` | Initial zoom level |
| `atlas.extent` | View bounds constraint (in canonical_crs) |
| `categories[].label`, `groups[].label` | TOC hierarchy and display text |
| `layers[].label`, `.published`, `.default_visible` | Layer visibility toggle state |
| `layers[].min_scale`, `.max_scale` | Scale-dependent visibility rules |
| `layers[].queryable`, `.identify_fields` | GetFeatureInfo allowlist |
| `rules.scale_mutex_pairs` | Mutual exclusion enforcement |
| `services.wms.base_url` | WMS endpoint path (e.g., `/map/ogc`) |
| `services.wms.allowed_requests` | WMS operations available (Phase 2: GetCapabilities, GetMap, GetFeatureInfo only) |

**Frontend Dependency**: If registry unavailable or malformed at runtime, frontend shows error page ("Registry unavailable").

### 1.2 WMS Endpoint (MapServer via Proxy)

**Authoritative**:
- Base URL: from `services.wms.base_url` in registry
- Protocol: HTTPS through edge proxy (Stage 2)
- Operations: GetCapabilities, GetMap, GetFeatureInfo only
- No WFS, no direct MapServer access, no data ETL exposure

**Frontend Responsibility**: Make WMS requests through proxy URL only.

---

## 2. Frontend Architecture (4 Modules)

Implement internal separation of concerns to minimize coupling and enable independent testing:

### Module 1: RegistryLoader

**Purpose**: Load and normalize registry configuration.

**Inputs**:
- `atlas-registry.yaml` (or pre-generated JSON artifact)

**Outputs**:
- `atlasConfig`: Top-level settings (center, zoom, extent, CRS)
- `tocModel`: Ordered categories/groups/layers structure
- `layerDefs`: Dictionary keyed by layer_id with metadata

**Behavior**:
- Load YAML and parse into JavaScript object
- Validate basic shape (structure must conform to CONFIG_MODEL.md)
- **Note**: Full validation (Stage 4 rules) assumed to be done at build/deploy time
- Normalize layer definitions (ensure all required keys present)
- Emit error if registry structure fundamentally broken

**Example Output**:
```javascript
const registry = {
  atlasConfig: {
    title: "Tigray Digital Web Atlas",
    center: [38.5, 13.5],  // [lon, lat] in EPSG:4326
    zoom: 7,
    canonical_crs: "EPSG:4326",
    view_crs: "EPSG:3857",
    extent: [33.0, 3.0, 48.0, 15.5]
  },
  
  tocModel: [
    {
      id: "cat_admin",
      label: "Administrative Boundaries",
      groups: [
        {
          id: "grp_admin_ethiopia",
          label: "Ethiopia Administrative",
          layers: ["ethiopia_zones", "ethiopia_woredas"]
        }
      ]
    },
    // ... more categories
  ],
  
  layerDefs: {
    ethiopia_zones: {
      wms_name: "ethiopia_zones",
      label: "Ethiopia Zones",
      type: "vector",
      published: true,
      default_visible: false,
      queryable: true,
      min_scale: 10000000,
      max_scale: 250000,
      identify_fields: ["NAME", "CODE"]
    },
    // ... more layers
  },
  
  scaleMutexPairs: [
    ["ethiopia_roads", "tigray_roads_2006"],
    ["ethiopia_towns", "tigray_towns"]
  ]
};
```

---

### Module 2: MapController

**Purpose**: Initialize and manage the OpenLayers map with CRS transformation.

**Inputs**:
- `atlasConfig` from RegistryLoader
- WMS base URL (from registry)

**Outputs**:
- Initialized OpenLayers Map object
- Configured for EPSG:3857 view
- Extent constraint applied

**Behavior**:

1. **Projection Setup**
   ```javascript
   const map = new ol.Map({
     projection: ol.proj.get('EPSG:3857'),  // view_crs
     target: 'map-container'
   });
   ```

2. **Center Transformation**
   - Registry center is in canonical_crs (EPSG:4326)
   - Transform to view_crs (EPSG:3857) before setting
   ```javascript
   const centerEPSG4326 = atlasConfig.center;  // [lon, lat]
   const centerEPSG3857 = ol.proj.transform(
     centerEPSG4326,
     'EPSG:4326',
     'EPSG:3857'
   );
   map.getView().setCenter(centerEPSG3857);
   map.getView().setZoom(atlasConfig.zoom);
   ```

3. **Extent Constraint**
   - Transform extent from EPSG:4326 → EPSG:3857
   - Set as view constraint (fit-to-extent)
   ```javascript
   const extentEPSG4326 = atlasConfig.extent;  // [minx, miny, maxx, maxy]
   const extent4326 = ol.extent.getHalid(extentEPSG4326);
   const extentEPSG3857 = ol.proj.transformExtent(
     extent4326,
     'EPSG:4326',
     'EPSG:3857'
   );
   map.getView().fit(extentEPSG3857);
   ```

4. **Resolution to Scale Mapping**
   - OpenLayers uses resolution (meters/pixel), not scale denominators
   - For scale rule enforcement, convert resolution ↔ scale:
   ```javascript
   // Cartographic scale denominator from resolution
   function getScaleDenominator(resolution) {
     // Assumes 96 DPI (standard web)
     const dotsPerMeter = 96 / 0.0254;  // ~3779 dpi/meter
     const scaleDenominator = resolution * dotsPerMeter;
     return scaleDenominator;
   }
   ```

---

### Module 3: LayerFactory

**Purpose**: Create OpenLayers layer objects from registry definitions.

**Inputs**:
- `layerDefs` from RegistryLoader
- WMS base URL
- Only layers with `published: true`

**Outputs**:
- Array of OpenLayers `TileWMS` layer objects (no WFS)
- In YAML order

**Requirements**:

1. **WMS-First: Use TileWMS**
   ```javascript
   const layer = new ol.layer.Tile({
     title: layerDef.label,
     visible: false,  // Will be set by InteractionController
     source: new ol.source.TileWMS({
       url: wmsBaseUrl,
       params: {
         'LAYERS': layerDef.wms_name,
         'TILED': true,
         'TRANSPARENT': true,
         'FORMAT': 'image/png'
       }
     })
   });
   ```

2. **Stable WMS Parameters** (cache-friendly)
   - FORMAT: always `image/png` (fixed)
   - STYLES: empty or default (no dynamic style selection Phase 2)
   - TRANSPARENT: `true` (for overlays)
   - CRS: client's view CRS (EPSG:3857, auto-handled by ol.source.TileWMS)

3. **Never Create WFS Source**
   - No `ol.source.Vector` with WFS
   - No GetFeature calls
   - No Feature objects loaded from WFS

4. **Metadata Storage**
   - Store `layerDef` as custom property on layer for later reference:
   ```javascript
   layer.layerDef = layerDef;
   layer.layerId = layerId;
   ```

---

### Module 4: InteractionController

**Purpose**: Manage user interactions and state-dependent visibility.

**Inputs**:
- Map object
- Layers array
- `tocModel` and `layerDefs`
- Scale mutex pairs
- Current view (zoom/resolution)

**Outputs**:
- User-facing TOC (layer checkboxes, group toggle)
- GetFeatureInfo popup (on click)
- Synchronized layer visibility state

**Key Behaviors**:

1. **TOC Rendering** (categories → groups → layers)
   - Render checkboxes respecting `tocModel` hierarchy
   - Hide/disable Credits (not a layer)
   - Disable unpublished layers (should not exist in UI)

2. **Layer Toggle with Scale Enforcement**
   ```javascript
   function toggleLayer(layerId, enabled) {
     const layer = findLayer(layerId);
     const layerDef = layer.layerDef;
     
     // Check scale constraint
     const scale = getScaleDenominator(map.getView().getResolution());
     const inScaleRange =
       scale >= layerDef.max_scale &&
       scale <= layerDef.min_scale;
     
     if (enabled && !inScaleRange) {
       // Option 1: disable checkbox (recommended)
       UI.disableCheckbox(layerId, reason: "not visible at this scale");
       return;
     }
     
     layer.setVisible(enabled);
     
     // Check mutex pairs
     enforceScaleMutex();
   }
   ```

3. **Scale Mutex Enforcement**
   - On zoom change, apply scale rules
   - For each mutex pair: ensure at most one is visible at current scale
   ```javascript
   function enforceScaleMutex() {
     const scale = getScaleDenominator(map.getView().getResolution());
     
     for (const [layerAId, layerBId] of scaleMutexPairs) {
       const layerA = findLayer(layerAId);
       const layerB = findLayer(layerBId);
       
       const aInRange = scale >= layerA.layerDef.max_scale &&
                        scale <= layerA.layerDef.min_scale;
       const bInRange = scale >= layerB.layerDef.max_scale &&
                        scale <= layerB.layerDef.min_scale;
       
       // If both in range (should not happen), deterministically pick one
       if (aInRange && bInRange) {
         console.warn(`Scale overlap detected: ${layerAId} vs ${layerBId}`);
         // Prefer "regional" (smaller area) or deterministic rule
         layerB.setVisible(false);
       }
     }
   }
   ```

4. **GetFeatureInfo (Identify) on Click**
   - Single click triggers feature query
   - Only queryable layers participate
   ```javascript
   map.on('singleclick', function(evt) {
     const queryableLayers = layers.filter(l =>
       l.layerDef.queryable && l.getVisible()
     );
     
     if (queryableLayers.length === 0) return;
     
     // Request GetFeatureInfo for topmost queryable layer
     queryFeatureInfo(queryableLayers[0], evt.coordinate);
   });
   
   function queryFeatureInfo(layer, coordinate) {
     const wmsParams = {
       SERVICE: 'WMS',
       REQUEST: 'GetFeatureInfo',
       QUERY_LAYERS: layer.layerDef.wms_name,
       LAYERS: layer.layerDef.wms_name,
       BBOX: getCurrentBBox(),
       WIDTH: mapWidth,
       HEIGHT: mapHeight,
       I: pixel_x,
       J: pixel_y,
       INFO_FORMAT: 'application/json',  // From registry
       FEATURE_COUNT: 5
     };
     
     fetch(`${wmsBaseUrl}?${new URLSearchParams(wmsParams)}`)
       .then(r => r.json())
       .then(features => showPopup(layer.layerDef, features));
   }
   ```

5. **Popup Rendering with Allowlist**
   ```javascript
   function showPopup(layerDef, features) {
     const html = features.map(feature => {
       const allowlist = new Set(layerDef.identify_fields);
       const properties = feature.properties || {};
       
       const rows = Object.entries(properties)
         .filter(([key]) => allowlist.has(key))  // Strict allowlist
         .map(([key, val]) => `<tr><td>${key}</td><td>${val}</td></tr>`)
         .join('');
       
       return `
         <div class="feature-popup">
           <h3>${layerDef.label}</h3>
           <table>${rows}</table>
         </div>
       `;
     }).join('');
     
     showMapPopup(html);
   }
   ```

---

## 3. Map Initialization Sequence

### Required Behavior (in order)

1. **Load Registry**
   - Fetch `atlas-registry.yaml` (or JSON artifact)
   - Parse and normalize
   - Show error if unavailable

2. **Create Map Controller**
   - Initialize OpenLayers map
   - Set projection to view_crs (EPSG:3857)
   - Transform center from canonical_crs
   - Transform and apply extent constraint

3. **Create Layers**
   - For each layer with `published: true`, create TileWMS layer
   - Set initial visibility based on `default_visible` + scale rules at initial zoom

4. **Build TOC**
   - Render registry categories/groups hierarchy
   - Attach layer toggle handlers
   - Disable/mark out-of-scale layers

5. **Attach Interactions**
   - Click handler for GetFeatureInfo
   - Zoom event handler for scale-dependent visibility
   - Scale mutex enforcement on zoom

6. **Start Map**
   - Render tiles via WMS GetMap
   - Ready for user interaction

---

## 4. Layer Toggle Rules (TOC Behavior)

### Per-Layer Toggle

When user clicks checkbox for a layer:

1. **Compute current scale** from map resolution
2. **Check layer's scale range** (min_scale, max_scale)
3. **If unchecking**: always allowed; set `visible = false`
4. **If checking**:
   - If **in scale range**: `visible = true`
   - If **out of scale range**: 
     - Option A (recommended): disable checkbox, show tooltip "Not visible at this scale"
     - Option B: allow check but layer stays invisible; show visual indicator
     - **Choose one behavior and stay consistent**

### Group Toggle (Optional But Recommended)

When user clicks group checkbox:

- Toggle all child layers
- Respect each layer's scale constraints
- If group partially visible, toggle all on or all off (deterministic)

### No UI Decoration Layers

- Credits/Attribution are NOT layers
- Display in UI footer (outside TOC)
- Never toggle-able

---

## 5. Identify (GetFeatureInfo) — REQUIRED

### 5.1 Trigger

**Single click on map** invokes identify:

- Capture coordinate
- Send WMS GetFeatureInfo request
- Parse response
- Show results in popup

### 5.2 Request Contract

```
SERVICE=WMS
REQUEST=GetFeatureInfo
QUERY_LAYERS=<wms_name>
LAYERS=<wms_name>
BBOX=<current view extent>
WIDTH=<map pixel width>
HEIGHT=<map pixel height>
I=<click x pixel>
J=<click y pixel>
INFO_FORMAT=application/json
FEATURE_COUNT=5
```

**WMS Base URL**: from `services.wms.base_url` in registry

**Format**: Use JSON if available; fallback to text/html if registry specifies

### 5.3 Response Rendering

Only display fields in layer's `identify_fields`:

```javascript
// Given layer definition:
// queryable: true
// identify_fields: ["NAME", "TYPE", "REGION"]

// Response from GetFeatureInfo (full):
// { properties: { NAME: "Addis", TYPE: "City", REGION: "Addis", POPULATION: 5000000, ID: 12345, GEOM: "..." } }

// Rendered (allowlisted):
// NAME: Addis
// TYPE: City
// REGION: Addis
// 
// (POPULATION, ID, GEOM are hidden)
```

**If no results**: Close popup or show "No features at this location"

**If multiple layers queryable**: Show results grouped by layer label

### 5.4 Error Handling

- WMS timeout (>5s): show timeout indicator, allow retry
- WMS error (400/500): show generic error, log to console
- Malformed response: log error, show "Could not read features"

---

## 6. Scale-Dependent Visibility (Roads/Towns) — REQUIRED

### 6.1 Per-Layer Scale Rule

Each layer defines `min_scale` and `max_scale` (cartographic denominator convention):

```
Visible when: max_scale ≤ current_scale ≤ min_scale
```

**Example**:
- `ethiopia_roads: min=50M, max=500k`
- At scale 1M: `500k ≤ 1M ≤ 50M` ✓ **VISIBLE**
- At scale 100k: `500k ≤ 100k ≤ 50M` ✗ **NOT VISIBLE**
- At scale 200M: `500k ≤ 200M ≤ 50M` ✗ **NOT VISIBLE**

### 6.2 Mutex Rule Enforcement

For each `scale_mutex_pairs` entry (e.g., `["ethiopia_roads", "tigray_roads_2006"]`):

- **At any zoom level**, at most one layer is visible
- If both layers are eligible at current scale (registry should prevent this), pick one deterministically
- Example priority: prefer "regional" (e.g., Tigray) at larger scales (zoomed in) over "national"

**Behavior on Zoom Change**:

```javascript
map.on('change:resolution', function() {
  // Recompute scale
  const scale = getScaleDenominator(map.getView().getResolution());
  
  // Update each layer's visibility based on scale
  for (const [layerId, layerDef] of Object.entries(layerDefs)) {
    const inRange = scale >= layerDef.max_scale && scale <= layerDef.min_scale;
    const shouldBeVisible = userToggledOn && inRange;
    layer.setVisible(shouldBeVisible);
  }
  
  // Enforce mutex pairs
  enforceScaleMutex();
});
```

### 6.3 UI Indication (Optional)

When a layer is zoomed-out-of-range:

- Option A: Disable checkbox (gray out)
- Option B: Show icon/badge "Not visible at this scale"
- Option C: Allow check but don't render; show visual indicator

**Pick one and apply consistently across all scale-constrained layers.**

---

## 7. Search UI (Phase 2: Deferred to Phase 3)

Registry contains `search: []` (empty array) for Phase 2.

**Frontend Behavior**:
- Do NOT display search input or results
- Optionally show disabled search box labeled: "Search (available Phase 3)"
- OR hide search entirely

**No Logic Required**:
- No auto-complete
- No fuzzy search
- No geography-aware search
- No population density ingestion/queries

---

## 8. Error Handling & Resilience

### 8.1 Registry Unavailable

```
Display full-page error:
┌─────────────────────────────────────┐
│ TSIRD Atlas - Registry Unavailable  │
│                                     │
│ Could not load map configuration.   │
│ Please try again later.             │
│                                     │
│ [Retry] button                      │
└─────────────────────────────────────┘
```

Do NOT show stack trace, internal URLs, or technical details.

### 8.2 WMS Endpoint Fails

Display banner on map:

```
⚠️ Map tiles unavailable. Retrying...
```

Allow user to click Retry. Continue attempting WMS requests with backoff.

### 8.3 Malformed WMS Response

Log error to browser console (developer-facing).

Show generic user message: "Could not load map tiles"

Do NOT leak error details to UI.

---

## 9. Acceptance Criteria (Stage 6 "Done")

Use this checklist to verify implementation completeness:

### A. Registry Compliance

- [ ] Only layers with `published: true` appear in TOC
- [ ] TOC order matches YAML order (categories → groups → layers)
- [ ] Default visible layers match registry `default_visible: true`
- [ ] Map center initializes to registry `atlas.center` (reprojected to view CRS)
- [ ] Map zoom initializes to registry `atlas.zoom`
- [ ] Map extent constrained to registry `atlas.extent` (reprojected)

### B. WMS Behavior

- [ ] All layers rendered via TileWMS (no WFS, no vector)
- [ ] WMS requests routed through proxy base URL (`/map/ogc`)
- [ ] Browser DevTools shows no WFS GetFeature calls
- [ ] Browser DevTools shows stable WMS GetMap params (FORMAT, STYLES, TRANSPARENT consistent)
- [ ] WMS requests include TILED=true for cache-friendly tiling

### C. Identify Behavior

- [ ] Single click on queryable layer opens popup
- [ ] Popup displays only fields in layer's `identify_fields` (allowlist enforced)
- [ ] Popup title is layer label from registry
- [ ] Non-queryable layers: click produces no popup
- [ ] No result message: "No features at this location"

### D. Scale Behavior

- [ ] Roads layer visible only at correct scales (e.g., 500k–50M)
- [ ] Tigray roads visible only at larger zoom (e.g., 500k–1)
- [ ] At overlap threshold, only one is visible (mutual exclusion enforced)
- [ ] Layer checkboxes disabled/marked when out of scale range at current zoom
- [ ] On zoom, visibility toggles smoothly (zoom → scale update → layer visibility update → mutex check)

### E. UI/UX

- [ ] No console errors (DevTools clean)
- [ ] Responsive layout (map responsive to container)
- [ ] Popup closes on second click or close button
- [ ] Group toggle (if implemented) toggles all child layers respecting scale rules
- [ ] Search box disabled or hidden (Phase 2)

### F. Error Resilience

- [ ] Registry load error shows friendly error page (no stack trace)
- [ ] WMS error shows banner; user can retry
- [ ] No leaked internal URLs or API endpoints in error messages

---

## 10. Implementation Roadmap

### Two-Milestone Approach (Risk Minimization)

This strategy keeps work decomposed and testable:

#### Milestone 1: Basic Map + TOC + Tiled Rendering

**Duration**: 50% of effort

**Deliverables**:
- Registry loading (RegistryLoader module)
- Map initialization (MapController module)
- Layer creation (LayerFactory module)
- TOC rendering (basic TOC from tocModel, no interactions yet)
- TileWMS layers rendering
- Per-layer toggle (basic, no scale yet)

**Tests**:
- Registry loads and normalizes
- Map initializes to correct center/zoom (reprojected)
- Extent constraint applied
- All published layers appear as TileWMS sources
- Layer checkboxes work (toggle visibility)
- No WFS calls occur

**Blockers**: None (foundation is self-contained)

---

#### Milestone 2: Scale Enforcement + Identify + Polish

**Duration**: 50% of effort

**Deliverables**:
- Scale-dependent visibility (per-layer rules)
- Scale mutex enforcement (roads/towns pairs)
- GetFeatureInfo on click (identify popup)
- Attribute allowlisting
- Scale-aware TOC (disable/mark out-of-range layers)
- Error pages and resilience

**Tests**:
- Scale rules enforce correctly (toggle at boundaries, mutex pairs never overlap)
- Identify popup shows, allowlist enforced
- No unauthorized attributes leaked
- TOC checkboxes disabled when out of scale
- Error cases handled gracefully

**Integration**: Builds on Milestone 1 foundation.

---

## 11. Known Limitations (Phase 2)

- **No Search**: `search: []` is empty; search deferred to Phase 3
- **No Custom Styling**: All layer styles from MapServer (no client-side style picker)
- **No Feature Editing**: Read-only (GetFeatureInfo only, no WFS)
- **No Offline**: Requires connectivity to WMS endpoint
- **No Print Export**: Phase 2 scope does not include printing
- **No Advanced Filtering**: Only layer visibility toggle available
- **No Basemap Picker**: Single basemap only (if any)

---

## 12. Deliverable: Code & Documentation

### Code

- **Location**: `ui/web/` or similar frontend directory
- **Structure**:
  - `index.html` (entry point)
  - `js/modules/` (RegistryLoader, MapController, LayerFactory, InteractionController)
  - `js/main.js` (orchestration)
  - `css/style.css` (styling)
  - `config/atlas-registry.yaml` (or `data/atlas-registry.json` if pre-built)
  - `package.json` (dependencies: OpenLayers 8+, build tooling)

### Documentation

- **File**: [STAGE6_FRONTEND.md](STAGE6_FRONTEND.md) (this document)
- **Content**:
  - Architecture overview (4 modules)
  - API contracts for each module
  - Initialization sequence
  - Scale/mutex enforcement logic
  - GetFeatureInfo popup rendering
  - Error handling patterns
  - Known limitations

---

## 13. Docker Integration

Frontend runs in Docker container within the Phase 2 stack:

```yaml
services:
  tsird-web:
    image: nginx:alpine
    ports: ["80:80"]
    volumes:
      - ./ui/web:/usr/share/nginx/html:ro
    depends_on:
      - tsird-edge  # (edge proxy)
```

**Nginx config**:
- Serves `index.html` and static assets
- Reverse proxies WMS requests to edge proxy (`/map/ogc` → `http://tsird-edge:8080/map/ogc`)
- CORS headers if needed (edge proxy already handles CORS)

**Access**: Browser → `http://localhost:18080/` (through edge proxy)

---

## 14. Authorization: Stage 6 Frozen

This STAGE6_FRONTEND.md is the **frozen specification** for OpenLayers client implementation in Phase 2.

**Approved by**:
- Registry-driven architecture (single source of truth) ✓
- WMS-first rendering (tiled, cache-friendly) ✓
- Scale mutual exclusion (roads/towns) ✓
- GetFeatureInfo with attribute allowlisting ✓
- Two-milestone implementation approach ✓
- Error resilience and friendly UX ✓

**Next Stages**: Phases 3+ (search, performance, scaling)

---

**✓ END OF STAGE 6 SPECIFICATION: FRONTEND IMPLEMENTATION CONTRACT FROZEN**

Implementation can now proceed with confidence that all contracts (registry, WMS, scale, identify) are locked and won't change without formal revision.
