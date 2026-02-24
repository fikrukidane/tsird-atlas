# Phase 2 - Stage 3: Configuration Contract (Registry YAML)

**Generated**: 2026-02-24  
**Status**: ✓ CONFIGURATION CONTRACT FROZEN  
**Scope**: YAML Registry Schema & Validation Rules

---

## Overview

This document defines the **authoritative configuration contract** for TSIRD Phase 2: the YAML registry that serves as the single source of truth for what is publicly exposed via WMS.

**Key Principles**:
- Human-authored YAML (source of truth)
- Stable ordering semantics (array order = draw order)
- Strict referential integrity and uniqueness constraints
- Explicit separation: **canonical data CRS** (EPSG:4326 storage) vs **view CRS** (EPSG:3857 web)
- WMS-first only (WFS disabled Phase 2)

---

## 1. Design Goals

1. **Single Source of Truth**: Registry determines what is public; no hardcoded defaults in code
2. **WMS-First Architecture**: GetCapabilities, GetMap, GetFeatureInfo only; WFS disabled
3. **Human-Maintainable**: YAML syntax, readable structure, hand-edited by configuration authors
4. **Deterministic Startup**: Client behavior is reproducible from registry alone
5. **Referential Integrity**: No orphan layers, unique WMS names, validated cross-references
6. **Dual-Scale Support**: Roads and towns use non-overlapping scale ranges (mutual exclusion)
7. **Governance**: Published layers are immutable; new layers follow explicit validation

---

## 2. Canonical CRS vs View CRS

**Critical Distinction**:

| Aspect | Canonical CRS | View CRS |
|--------|---|---|
| **Definition** | Storage/data CRS | Web map display CRS |
| **Phase 2 Value** | `EPSG:4326` (WGS84 lat/lon) | `EPSG:3857` (Web Mercator) |
| **Where Used** | All data at rest (PostGIS, shapefiles) | OpenLayers map display, tile grid |
| **Registry Storage** | `atlas.canonical_crs` | `atlas.view_crs` |
| **Center Coordinate** | Stored in canonical_crs | Client transforms to view_crs for display |
| **Extent/Bbox** | Always in canonical_crs | Client reprojects on demand |
| **Immutable** | Yes (Phase 1 baseline) | Configurable (WEBMERCATOR for Phase 2) |

**Consequence for Implementation**:
- MapServer stores all layers in native CRS (mostly EPSG:4326, some EPSG:20137 utm)
- MapServer on-the-fly reproject to requested CRS (typically view_crs from registry)
- Client (OpenLayers) receives tiles in view_crs
- Client must transform registry center/extent to view_crs for initial display

**Registry Responsibility**: Declare both explicitly so client knows the transformation needed.

---

## 3. Top-Level YAML Schema

```yaml
version: "1.0"

atlas:
  id: "tsird_public_atlas"
  title: "Tigray Digital Web Atlas"
  description: "TSIRD Public Web Atlas (Phase 2)"
  
  # CRS Declaration
  canonical_crs: "EPSG:4326"     # Frozen: storage CRS (all gold data)
  view_crs: "EPSG:3857"          # Web map projection (Web Mercator)
  
  # Initial View
  center: [38.5, 13.5]           # [lon, lat] in canonical_crs
  zoom: 7                        # integer; client interprets per zoom strategy
  extent: [33.0, 3.0, 48.0, 15.5] # [minx, miny, maxx, maxy] in canonical_crs

services:
  wms:
    base_url: "/map/ogc"         # Path to MapServer WMS endpoint
    version: "1.3.0"             # OGC WMS specification version
    allowed_requests: ["GetCapabilities", "GetMap", "GetFeatureInfo"]
    formats:
      getmap: "image/png"
      featureinfo: "application/json"

ui:
  layer_order_policy: "registry_order"  # draw order = YAML sequence order
  legend:
    enabled: true
  identify:
    enabled: true

categories:
  - id: "cat_admin"
    label: "Administrative Boundaries"
    closed: false
    groups:
      - id: "grp_admin_ethiopia"
        label: "Ethiopia Administrative"
        layers: ["ethiopia_zones", "ethiopia_woredas"]
      - id: "grp_admin_tigray"
        label: "Tigray Administrative"
        layers: ["tigray_zones", "tigray_woredas"]

  - id: "cat_transport"
    label: "Transport"
    closed: false
    groups:
      - id: "grp_roads"
        label: "Roads (scale-aware)"
        layers: ["ethiopia_roads", "tigray_roads_2006"]

  - id: "cat_health"
    label: "Health"
    closed: true
    groups:
      - id: "grp_health_facilities"
        label: "Health Facilities (Tigray)"
        layers: ["tigray_health_facilities_2006"]

  # ... additional categories

layers:
  # Reference all layers here; groups reference by ID only
  ethiopia_zones:
    wms_name: "ethiopia_zones"
    label: "Ethiopia Zones"
    type: "vector"
    source: "postgis"
    geometry_type: "polygon"
    published: true
    default_visible: false
    queryable: true
    min_scale: 10000000
    max_scale: 250000
    identify_fields: ["NAME", "CODE", "AREA_SQ_KM"]
    attribution: "Source: Ethiopian Geospatial Authority"

  ethiopia_roads:
    wms_name: "ethiopia_roads"
    label: "Ethiopia Roads"
    type: "vector"
    source: "postgis"
    geometry_type: "linestring"
    published: true
    default_visible: true
    queryable: false
    min_scale: 50000000
    max_scale: 500000
    identify_fields: []
    attribution: "Source: Road Network Database"

  tigray_roads_2006:
    wms_name: "tigray_roads_2006"
    label: "Tigray Roads (2006)"
    type: "vector"
    source: "ogr"
    geometry_type: "linestring"
    published: true
    default_visible: true
    queryable: false
    min_scale: 500000
    max_scale: 1
    identify_fields: []
    attribution: "Source: TSIRD Phase 1 Digitization"

  tigray_health_facilities_2006:
    wms_name: "tigray_health_facilities_2006"
    label: "Health Facilities (Tigray)"
    type: "vector"
    source: "ogr"
    geometry_type: "point"
    published: true
    default_visible: false
    queryable: true
    min_scale: 5000000
    max_scale: 1
    identify_fields: ["NAME", "TYPE", "REGION"]
    attribution: "Source: TSIRD Health Survey 2006"

search: []
  # Population density search deferred to Phase 3
  # Phase 2 supports only layer-based navigation + identify

rules:
  scale_mutex_pairs:
    - ["ethiopia_roads", "tigray_roads_2006"]
```

---

## 4. Layer Metadata Contract

Every entry under `layers:` MUST conform to this contract:

### Required Keys

| Key | Type | Description | Constraints |
|-----|------|-------------|-------------|
| `wms_name` | string | MapServer LAYER NAME | Must match mapfile definition exactly; globally unique |
| `label` | string | UI display name | Human-readable, any length |
| `type` | enum | "vector" or "raster" | Frozen after creation |
| `source` | enum | "postgis", "ogr", or "geotiff" | Determines data access path |
| `geometry_type` | enum | "polygon", "linestring", "point", "raster" | Controls UI styling rules |
| `published` | boolean | True if layer is public | Immutable after first publish |
| `default_visible` | boolean | Visible at startup (if scale passes) | Can be toggled in UI |
| `queryable` | boolean | Enables GetFeatureInfo on click | Governs identify flow |
| `identify_fields` | array | Allowlist of attribute names | Non-empty if queryable=true; empty if queryable=false |
| `attribution` | string | Data source credit | Displayed in UI |

### Optional Keys

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `opacity` | number | 1.0 | Range [0.0–1.0]; layer transparency |
| `min_scale` | integer | none | Denominator scale (visible when zoomed in > this value) |
| `max_scale` | integer | none | Denominator scale (visible when zoomed out < this value) |
| `bbox` | array | none | [minx, miny, maxx, maxy] in canonical_crs; UI hint for zoom-to |
| `tags` | array | none | Arbitrary metadata tags |
| `legend` | object | none | legend.show (boolean), legend.url (string) |
| `metadata` | object | none | Key-value pairs; UI-facing only; no secrets |

### Scale Field Semantics

**Convention** (cartographic denominator):
- `min_scale: 10000000` means 1:10,000,000 (zoomed out; large area visible)
- `max_scale: 250000` means 1:250,000 (zoomed in; small area visible)
- **Visible when client scale ≥ max_scale AND ≤ min_scale** (inverted range)

**If both specified**: `min_scale > max_scale` is the rule.

Example:
```yaml
ethiopia_zones:
  min_scale: 10000000   # Visible when zoomed out to 1:10M or less
  max_scale: 250000     # Visible when zoomed in to 1:250K or more
```

**Implementation Note**: Client (OpenLayers) must map its zoom level to this scale denominator. The registry uses cartographic convention; client implementation may require scale→zoom transformation.

---

## 5. Mandatory Global Validation Constraints

### 5.1 Referential Integrity

**Rule**: Every layer ID in `categories[].groups[].layers[]` MUST exist as a key under `layers:`.

**Validation**:
```python
for category in registry['categories']:
    for group in category['groups']:
        for layer_id in group['layers']:
            assert layer_id in registry['layers'], f"Orphan layer {layer_id}"
```

**Failure**: Registry is invalid and cannot be deployed.

### 5.2 Unique WMS Layer Names

**Rule**: `layers[*].wms_name` MUST be globally unique.

**Validation**:
```python
wms_names = [layer['wms_name'] for layer in registry['layers'].values()]
assert len(wms_names) == len(set(wms_names)), "Duplicate wms_name detected"
```

**Failure**: WMS GetCapabilities would be ambiguous; rejected at validation.

### 5.3 Publication Rules

**Rule**:
- If `published: false`, the layer MUST NOT appear in any `groups[].layers[]` list.
- If `published: true` and later changed to `false`, it MUST be removed from all groups first.
- `published` is **immutable** after initial publication (governance).

**Validation**:
```python
unpublished_layers = {lid: l for lid, l in registry['layers'].items() if not l['published']}
for category in registry['categories']:
    for group in category['groups']:
        for layer_id in group['layers']:
            assert layer_id not in unpublished_layers, f"Unpublished {layer_id} in group"
```

### 5.4 Query Rules

**Rule**:
- If `queryable: false`, then `identify_fields: []` or omitted.
- If `queryable: true`, then `identify_fields` MUST be a non-empty list.
- Identify fields are a **strict allowlist**; UI MUST NOT display non-allowlisted attributes.

**Validation**:
```python
for lid, layer in registry['layers'].items():
    if layer['queryable']:
        assert len(layer.get('identify_fields', [])) > 0, f"{lid}: queryable but no identify_fields"
    else:
        assert layer.get('identify_fields', []) == [], f"{lid}: not queryable but has identify_fields"
```

### 5.5 Dual-Scale Mutual Exclusion (Roads/Towns)

**Rule**: Define scale-mutex pairs explicitly:

```yaml
rules:
  scale_mutex_pairs:
    - ["ethiopia_roads", "tigray_roads_2006"]
    - ["ethiopia_towns", "tigray_towns"]
```

**Validation** (for each pair A, B):
1. Both layers must have `min_scale` and `max_scale` defined.
2. Their visible ranges MUST NOT overlap:
   - A.min_scale ≥ B.max_scale OR A.max_scale ≤ B.min_scale
3. Preferably an exact handoff: A.max_scale == B.min_scale (no gap)

**Validation Code**:
```python
for layer_a, layer_b in registry['rules']['scale_mutex_pairs']:
    a = registry['layers'][layer_a]
    b = registry['layers'][layer_b]
    a_min, a_max = a['min_scale'], a['max_scale']
    b_min, b_max = b['min_scale'], b['max_scale']
    
    # Check non-overlap
    assert not (a_max < b_min and b_max < a_min), \
        f"Scales {layer_a}/{layer_b} overlap"
```

### 5.6 No Circular Nesting

**Rule**: Categories → Groups → Layers only. No cycles.
- Categories cannot reference categories.
- Groups cannot contain groups.
- Only forward references: category.groups[] → group.layers[].

### 5.7 Service Contract

**Rule**: `services.wms.allowed_requests` MUST be exactly:
```yaml
allowed_requests: ["GetCapabilities", "GetMap", "GetFeatureInfo"]
```

No WFS operations permitted. No deviations.

---

## 6. Startup Behavior (Registry-Driven)

### 6.1 Projection & View Setup

1. Client reads `atlas.canonical_crs` and `atlas.view_crs`
2. Map initialized with `view_crs` (e.g., EPSG:3857 Web Mercator)
3. Registry center `atlas.center` is stored in `canonical_crs`; client reprojects to `view_crs` for display
4. Registry extent used for bounds; client reprojects on demand

### 6.2 Initial Map State

```javascript
// Pseudocode: Client initialization from registry

const registry = loadYAML('atlas-registry.yaml');
const map = createMap({
  projection: registry.atlas.view_crs,
  center: reprojectPoint(registry.atlas.center, 
                         registry.atlas.canonical_crs, 
                         registry.atlas.view_crs),
  zoom: registry.atlas.zoom
});

// Add layers in registry order
for (const category of registry.categories) {
  for (const group of category.groups) {
    for (const layer_id of group.layers) {
      const layer = registry.layers[layer_id];
      map.addLayer({
        name: layer.wms_name,
        visible: layer.default_visible && passesScaleConstraint(layer, map.zoom),
        queryable: layer.queryable,
        identifyFields: layer.identify_fields
      });
    }
  }
}
```

### 6.3 Dynamic Layer Visibility

- **Startup**: Only layers with `default_visible: true` AND scale constraints pass
- **User Interaction**: Checkbox toggle changes visibility; scale constraints re-applied on zoom
- **Scale Handoff**: For dual-scale pairs, mutual exclusion enforced per `rules.scale_mutex_pairs`

### 6.4 Draw Order

**Order determined by YAML sequence**:
1. First category drawn first
2. Within category: first group drawn first
3. Within group: layers drawn in list order

Layers drawn in this order; last layer is on top.

---

## 7. Phase 2-Specific Decisions Encoded

The following frozen decisions are reflected in the registry:

### Health Category
- **Decision**: Include only `tigray_health_facilities_2006`
- **Registry Reflection**:
  ```yaml
  categories:
    - id: "cat_health"
      groups:
        - layers: ["tigray_health_facilities_2006"]
  ```
- **Implementation**: 9 legacy empty health groups are NOT included

### Roads (Dual-Scale)
- **Decision**: Scale-dependent mutual exclusion
- **Registry Reflection**:
  ```yaml
  layers:
    ethiopia_roads:
      min_scale: 50000000
      max_scale: 500000
    tigray_roads_2006:
      min_scale: 500000
      max_scale: 1
  
  rules:
    scale_mutex_pairs: [["ethiopia_roads", "tigray_roads_2006"]]
  ```

### Towns (Dual-Scale)
- **Decision**: Scale-dependent mutual exclusion (analogous to roads)
- **Registry Reflection**: Similar structure as roads

### Credits & Attribution
- **Decision**: Moved to UI shell (not a layer)
- **Registry Reflection**: `layers[*].attribution` field carries data source; UI displays in footer

### Search
- **Decision**: Deferred to Phase 3; population density excluded Phase 2
- **Registry Reflection**:
  ```yaml
  search: []  # Empty in Phase 2
  ```

### WMS-Only Services
- **Decision**: WFS disabled Phase 2
- **Registry Reflection**:
  ```yaml
  services:
    wms:
      allowed_requests: ["GetCapabilities", "GetMap", "GetFeatureInfo"]
  ```

---

## 8. Validation Checklist (Registry Deployment)

Before a registry YAML is deployed, the following must pass:

- [ ] Schema: All required keys present and typed correctly
- [ ] Referential Integrity: No orphan layer references
- [ ] Unique WMS Names: No duplicate wms_name values
- [ ] Publication Rules: All published layers exist in groups
- [ ] Query Rules: queryable true ↔ non-empty identify_fields
- [ ] Scale Mutex: Dual-scale pairs verified non-overlapping
- [ ] No Circular Nesting: Categories/Groups/Layers unidirectional
- [ ] Service Contract: allowed_requests unchanged (WMS-only)
- [ ] CRS Declaration: canonical_crs and view_crs both explicit
- [ ] Scale Convention: If min_scale exists, min_scale > max_scale holds
- [ ] Attribution: All layers include attribution string

---

## 9. Example: Minimal Phase 2 Registry Fragment

```yaml
version: "1.0"

atlas:
  id: "tsird_public_atlas"
  title: "Tigray Digital Web Atlas"
  canonical_crs: "EPSG:4326"
  view_crs: "EPSG:3857"
  center: [38.5, 13.5]
  zoom: 7
  extent: [33.0, 3.0, 48.0, 15.5]

services:
  wms:
    base_url: "/map/ogc"
    version: "1.3.0"
    allowed_requests: ["GetCapabilities", "GetMap", "GetFeatureInfo"]
    formats:
      getmap: "image/png"
      featureinfo: "application/json"

ui:
  layer_order_policy: "registry_order"

categories:
  - id: "cat_transport"
    label: "Transport"
    closed: false
    groups:
      - id: "grp_roads"
        label: "Roads"
        layers: ["ethiopia_roads", "tigray_roads_2006"]

layers:
  ethiopia_roads:
    wms_name: "ethiopia_roads"
    label: "Ethiopia Roads"
    type: "vector"
    source: "postgis"
    geometry_type: "linestring"
    published: true
    default_visible: true
    queryable: false
    min_scale: 50000000
    max_scale: 500000
    identify_fields: []
    attribution: "Source: Road Network Database"

  tigray_roads_2006:
    wms_name: "tigray_roads_2006"
    label: "Tigray Roads (2006)"
    type: "vector"
    source: "ogr"
    geometry_type: "linestring"
    published: true
    default_visible: true
    queryable: false
    min_scale: 500000
    max_scale: 1
    identify_fields: []
    attribution: "Source: TSIRD Phase 1"

search: []

rules:
  scale_mutex_pairs:
    - ["ethiopia_roads", "tigray_roads_2006"]
```

---

## 10. Authorization: Stage 3 Complete

This CONFIG_MODEL.md is the **frozen registry specification** for Phase 2.

**Approved by**:
- WMS-first principle ✓
- 5 locked technology decisions from Stage 2 ✓
- Referential integrity model ✓
- CRS delegation (canonical ↔ view) ✓

**Next Stage**: Stage 4 — Validation Policy
- Implement validator logic (constraint enforcement)
- Define deployment gates (validation must pass before registry goes live)
- Create validator tool (Python/Node.js script to pre-flight registry YAML)

---

**✓ END OF STAGE 3: CONFIGURATION CONTRACT FROZEN**
