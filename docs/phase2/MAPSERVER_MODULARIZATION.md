# Phase 2 - Stage 5: MapServer Modularization & Publication Contract

**Generated**: 2026-02-24  
**Status**: ✓ MAPSERVER PUBLICATION CONTRACT FROZEN  
**Scope**: Mapfile Refactoring, Layer Lifecycle, Publication Governance

---

## Overview

This document defines how MapServer mapfiles are structured, maintained, and synchronized with the Phase 2 registry (`atlas-registry.yaml`).

**Core Principle**: Registry state is the single source of truth for publication. MapServer mirrors registry state via file inclusion and layer STATUS settings.

**Critical Rule**: If `published: true` in registry, layer MUST have `STATUS ON` in mapfile. If `published: false`, layer MUST be excluded from master mapfile and absent from GetCapabilities.

---

## 1. Publication Rule (Authoritative)

### Phase 2 Publication Model

For each layer in `atlas-registry.yaml`:

#### If `published: true`

The corresponding MapServer `LAYER` block:
- **MUST exist** in mapfiles
- **MUST be included** in the master mapfile (`tsird.map`)
- **MUST have** `STATUS ON`
- **WILL appear** in WMS GetCapabilities response
- **IS public** (accessible via HTTPS proxy from Stage 2)

#### If `published: false`

The corresponding MapServer `LAYER` block:
- **MUST NOT be included** in the master mapfile
- **MAY exist** in a holding file (e.g., `90_private_or_off.map`, for reference)
- **MUST NOT have** `STATUS ON` (or must be in separate non-included file)
- **WILL NOT appear** in GetCapabilities
- **IS hidden** (not accessible to WMS clients)

### Anti-Pattern Prevention

This rule prevents:
- **Accidental public exposure**: Layer forgotten in registry still appears in GetCapabilities
- **Zombie layers**: Old test/sample layers left in mapfile
- **Publication drift**: Registry and mapfile becoming out of sync

---

## 2. Mapfile Inclusion Model

### Master Mapfile Structure

**File**: `infra/mapserver/mapfiles/tsird.map` (master entry point)

**Structure** (no inline layers):

```mapfile
# tsird.map — Master map configuration
# Purpose: WMS service root
# NO inline LAYER definitions allowed

MAP
  NAME "tsird_wms"
  SIZE 256 256
  EXTENT 33.0 3.0 48.0 15.5
  PROJECTION
    "init=epsg:4326"
  END
  
  # Global includes
  INCLUDE "00_globals.map"
  INCLUDE "01_outputformats.map"
  INCLUDE "02_web_metadata.map"
  
  # Thematic layer includes (published layers ONLY)
  INCLUDE "includes/layers_administrative.map"
  INCLUDE "includes/layers_transport.map"
  INCLUDE "includes/layers_health.map"
  INCLUDE "includes/layers_terrain.map"
  INCLUDE "includes/layers_rasters.map"
  
  # Layer order is determined by include order + array order within each file
  
END
```

**Key Rules**:
1. **Master mapfile contains ONLY configuration and INCLUDE statements**
2. **NO Layer definitions inline** (enforces modularization)
3. **Thematic includes are ordered** (affects WMS GetCapabilities layer list order)
4. **Include files are named after layer groups or themes**

### Thematic Include Files

**Naming Convention**: `layers_<category>.map`

**Example**: `includes/layers_transport.map`

```mapfile
# layers_transport.map
# Contains all transport-related published layers
# Status: published layers only (published: true in registry)

LAYER
  NAME "ethiopia_roads"
  TYPE LINE
  STATUS ON
  ...
  MINSCALEDENOM 500000
  MAXSCALEDENOM 50000000
  ...
END

LAYER
  NAME "tigray_roads_2006"
  TYPE LINE
  STATUS ON
  ...
  MINSCALEDENOM 1
  MAXSCALEDENOM 500000
  ...
END
```

**Layer File Organization**:

```
infra/mapserver/mapfiles/
├── tsird.map                    (master)
├── 00_globals.map               (PROJECTION, FONTS, WEB defaults)
├── 01_outputformats.map         (PNG, JPEG formats)
├── 02_web_metadata.map          (WMS metadata, PROJECTION 3857)
├── includes/
│   ├── layers_administrative.map  (ethiopia_zones, tigray_zones, etc.)
│   ├── layers_transport.map       (ethiopia_roads, tigray_roads_2006, etc.)
│   ├── layers_health.map          (tigray_health_facilities_2006)
│   ├── layers_terrain.map         (DEM, slope, hillshade)
│   ├── layers_rasters.map         (imagery, basemaps)
│   ├── 90_private_or_deprecated.map (unpublished layers, for reference only)
│   └── ...
└── ...
```

### Global Configuration Files

**00_globals.map**: Shared settings
```mapfile
# Projection, font paths, coordinate order
PROJECTION "init=epsg:4326" END
EXTENT 33.0 3.0 48.0 15.5
```

**01_outputformats.map**: Image formats
```mapfile
OUTPUTFORMAT
  NAME "png"
  DRIVER "AGG/PNG"
  MIMETYPE "image/png"
  ...
END
```

**02_web_metadata.map**: WMS 1.3.0 service metadata
```mapfile
WEB
  METADATA
    "wms_title" "Tigray Digital Web Atlas"
    "wms_onlineresource" "http://atlas.tigrayinsights.net/map/ogc?"
    "wms_srs" "EPSG:4326 EPSG:3857"
    ...
  END
END
```

---

## 3. Layer Lifecycle Model

### Adding a New Dataset (Future-Proof Workflow)

**Step 1: Data Exists in Gold Store**
- Dataset ingested via Phase 1 ETL
- At rest in EPSG:4326 (canonical_crs)
- Stored in PostGIS or OGR shapefiles under `/data/gold/`

**Step 2: Create MapServer LAYER Block**
- Add LAYER definition to appropriate thematic include file
- Set `STATUS ON`
- Define MINSCALEDENOM / MAXSCALEDENOM from registry
- Configure DATA connection (PostGIS or OGR)
- Add METADATA (wms_title, wms_include_items, etc.)
- No hardcoded labels or attributes; all from registry

Example:
```mapfile
LAYER
  NAME "ethiopia_kebeles"
  TYPE POLYGON
  STATUS ON
  CONNECTIONTYPE POSTGIS
  CONNECTION "..."
  DATA "geometry from gold.administrative"
  
  MINSCALEDENOM 100000
  MAXSCALEDENOM 1000000
  
  CLASS
    STYLE
      COLOR 200 200 255
      OUTLINECOLOR 0 0 0
    END
  END
  
  METADATA
    "wms_title" "Ethiopia Kebeles"
    "wms_include_items" "NAME, POPULATION"
  END
END
```

**Step 3: Add Registry Entry**
- Add layer definition to `config/atlas-registry.yaml`
- Set `published: true`
- Define scale thresholds matching mapfile
- List identify_fields (curated attributes)
- Add to appropriate category/group

```yaml
layers:
  ethiopia_kebeles:
    wms_name: "ethiopia_kebeles"
    label: "Ethiopia Kebeles"
    type: "vector"
    source: "postgis"
    geometry_type: "polygon"
    published: true
    default_visible: false
    queryable: true
    min_scale: 1000000
    max_scale: 100000
    identify_fields: ["NAME", "POPULATION"]
    attribution: "Source: ..."
```

**Step 4: Validate & Test**
```bash
# Run registry validator (Stage 4)
validator config/atlas-registry.yaml

# Run integration tests
pytest tests/wms_integration_test.py

# Smoke test: Verify GetCapabilities
curl "http://localhost:8080/map/ogc?SERVICE=WMS&REQUEST=GetCapabilities" | grep "ethiopia_kebeles"

# Smoke test: GetMap
curl "http://localhost:8080/map/ogc?SERVICE=WMS&REQUEST=GetMap&LAYERS=ethiopia_kebeles&..." > test.png

# Smoke test: GetFeatureInfo
curl "http://localhost:8080/map/ogc?SERVICE=WMS&REQUEST=GetFeatureInfo&QUERY_LAYERS=ethiopia_kebeles&..." | head -20
```

**Step 5: Commit**
```bash
git add infra/mapserver/mapfiles/includes/layers_administrative.map
git add config/atlas-registry.yaml
git commit -m "Add ethiopia_kebeles layer (published, queryable)"
```

Layer is now public.

### Deprecating a Layer

**Step 1: Mark Unpublished in Registry**
```yaml
layers:
  old_layer_id:
    published: false
    ...
```

**Step 2: Remove from Mapfile**
- Remove LAYER block from thematic include file, OR
- Move to `90_private_or_deprecated.map` (not included in master)

**Step 3: Validate & Test**
```bash
validator config/atlas-registry.yaml

# Verify layer absent from GetCapabilities
curl "..." | grep -i "old_layer_id"  # Should be empty
```

**Step 4: Commit**
```bash
git add config/atlas-registry.yaml
git add infra/mapserver/mapfiles/includes/90_private_or_deprecated.map
git commit -m "Deprecate old_layer_id (set published: false)"
```

Layer is now hidden.

---

## 4. Scale Mutex Enforcement (Transport/Towns)

### MapServer-Level Enforcement

For dual-scale layers, MapServer enforces mutual exclusion at the LAYER level:

```mapfile
# layers_transport.map

LAYER
  NAME "ethiopia_roads"
  TYPE LINE
  STATUS ON
  ...
  MINSCALEDENOM 500000    # Visible when zoomed OUT to 1:500k or less
  MAXSCALEDENOM 50000000  # Visible when zoomed IN to 1:50M or more
END

LAYER
  NAME "tigray_roads_2006"
  TYPE LINE
  STATUS ON
  ...
  MINSCALEDENOM 1         # Visible to maximum zoom
  MAXSCALEDENOM 500000    # Visible when zoomed IN to 1:500k or more
END
```

**How It Works**:

At render time, MapServer checks layer scale constraints:

```
Client requests: GetMap with SCALE=1000000 (1:1M)

MapServer evaluates:
  ethiopia_roads:   MINSCALEDENOM=500000 ≤ 1000000 ≤ MAXSCALEDENOM=50000000 ✓ VISIBLE
  tigray_roads_2006: MINSCALEDENOM=1 ≤ 1000000 ≤ MAXSCALEDENOM=500000 ✗ NOT VISIBLE
  
Result: Only ethiopia_roads rendered
```

At different scale:

```
Client requests: SCALE=250000 (1:250k, zoomed in)

MapServer evaluates:
  ethiopia_roads:   MINSCALEDENOM=500000 ≤ 250000 ≤ MAXSCALEDENOM=50000000 ✗ NOT VISIBLE
  tigray_roads_2006: MINSCALEDENOM=1 ≤ 250000 ≤ MAXSCALEDENOM=500000 ✓ VISIBLE
  
Result: Only tigray_roads_2006 rendered
```

**Registry Alignment**:

Both registry and mapfile MUST have matching scale values:

```yaml
# atlas-registry.yaml
layers:
  ethiopia_roads:
    min_scale: 50000000
    max_scale: 500000
  tigray_roads_2006:
    min_scale: 500000
    max_scale: 1

rules:
  scale_mutex_pairs:
    - ["ethiopia_roads", "tigray_roads_2006"]
```

**Validator (Stage 4) ensures**:
- MapServer scales match registry scales (cross-file check, optional enhancement)
- Scale pairs do not overlap (validator Rule 6)
- Both layers in pair have scales defined

---

## 5. GetCapabilities Contract

### What GetCapabilities Must Contain

When client requests `SERVICE=WMS&REQUEST=GetCapabilities`:

MapServer returns XML listing all LAYER blocks with `STATUS ON` in the master mapfile.

**Expected Output** (Phase 2):

```xml
<WMS_Capabilities>
  <Capability>
    <Request>
      <GetCapabilities ... />
      <GetMap ... />
      <GetFeatureInfo ... />
    </Request>
    
    <Layer>
      <Name>root</Name>
      <Layer>
        <Name>ethiopia_zones</Name>
        <Title>Ethiopia Zones</Title>
        <SRS>EPSG:4326 EPSG:3857</SRS>
        <BoundingBox ... />
      </Layer>
      <Layer>
        <Name>ethiopia_roads</Name>
        <Title>Ethiopia Roads</Title>
        ...
      </Layer>
      <Layer>
        <Name>tigray_roads_2006</Name>
        <Title>Tigray Roads (2006)</Title>
        ...
      </Layer>
      <!-- All other published layers -->
    </Layer>
  </Capability>
</WMS_Capabilities>
```

### Acceptance Test: GetCapabilities

**Manual Verification**:

```bash
# Fetch GetCapabilities
curl -s "http://localhost:8080/map/ogc?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetCapabilities" > capabilities.xml

# Check: No orphan layers (not in registry)
grep -o '<Name>[^<]*</Name>' capabilities.xml | wc -l
# Should match registry layer count

# Check: No internal or deprecated layers
grep -E "(SAMPLE_GRID|deprecated|legacy|old_)" capabilities.xml
# Should be empty

# Check: No health indicator placeholders
grep -i "health_indicator" capabilities.xml
# Should only have tigray_health_facilities_2006

# Check: Exact layer name matches
grep "<Name>ethiopia_zones</Name>" capabilities.xml  # Should exist
grep "<Name>tigray_health_facilities_2006</Name>" capabilities.xml  # Should exist
```

**Automated Test**:

```python
def test_getcapabilities_only_published_layers():
    """Verify GetCapabilities contains only published layers."""
    registry = load_yaml('atlas-registry.yaml')
    published_wms_names = {
        layer['wms_name'] for layer_id, layer in registry['layers'].items()
        if layer['published']
    }
    
    capabilities = get_capabilities_xml()
    layer_names = set(re.findall(r'<Name>([^<]+)</Name>', capabilities))
    
    # Capabilities names should match published registry names
    assert layer_names == published_wms_names, f"Mismatch: {layer_names ^ published_wms_names}"
```

---

## 6. Identify Contract (GetFeatureInfo)

### GetFeatureInfo for Queryable Layers

For layers with `queryable: true` in registry:

MapServer returns feature attributes via GetFeatureInfo,**restricted to identify_fields allowlist**.

### MapServer Configuration (Queryable=True)

```mapfile
LAYER
  NAME "tigray_health_facilities_2006"
  TYPE POINT
  STATUS ON
  ...
  
  METADATA
    "wms_include_items" "NAME,TYPE,REGION"  # Allowlist (from registry identify_fields)
  END
  
  TEMPLATE "query_template.html"  # Or JSON for application/json responses
END
```

### MapServer Configuration (Queryable=False)

```mapfile
LAYER
  NAME "ethiopia_roads"
  TYPE LINE
  STATUS ON
  ...
  
  # No TEMPLATE defined, no wms_include_items
  # GetFeatureInfo returns empty or error
END
```

### Acceptance Test: GetFeatureInfo

**Manual Verification**:

```bash
# Query a health facility (queryable=true)
curl -s "http://localhost:8080/map/ogc?SERVICE=WMS&REQUEST=GetFeatureInfo&QUERY_LAYERS=tigray_health_facilities_2006&I=128&J=128&..." > response.json

# Check: Only allowlisted fields returned
jq '.properties | keys' response.json
# Should include: NAME, TYPE, REGION (from registry identify_fields)
# Should NOT include: internal IDs, geometry data, full record

# Query a road layer (queryable=false)
curl -s "http://localhost:8080/map/ogc?SERVICE=WMS&REQUEST=GetFeatureInfo&QUERY_LAYERS=ethiopia_roads&I=128&J=128&..." 
# Should return empty, error, or 400 (not queryable)
```

**Automated Test**:

```python
def test_identify_allowlist_enforcement():
    """Verify GetFeatureInfo returns only allowlisted fields."""
    registry = load_yaml('atlas-registry.yaml')
    layer_config = registry['layers']['tigray_health_facilities_2006']
    
    # Query a feature
    features = query_getfeatureinfo(layer_config['wms_name'], x=128, y=128)
    
    # Check attributes
    for feature in features:
        returned_keys = set(feature.properties.keys())
        allowlist = set(layer_config['identify_fields'])
        
        assert returned_keys <= allowlist, f"Unauthorized fields: {returned_keys - allowlist}"
```

---

## 7. Security Implication (Important)

### Publication Model as Security Boundary

**Before Stage 5**:
- Registry governs logical publication (what's listed)
- Proxy enforces access control (rate limiting, allowlist)
- MapServer is internal (unreachable, only via proxy)

**After Stage 5**:
- Registry publication state is mirrored in MapServer STATUS
- MapFile STATUS=ON is the runtime publication state
- **There is NO hidden layer safety net**: Any layer included in master mapfile is accessible if:
  - STATUS ON
  - Included in master mapfile
  - Client can reach the proxy

**Design Rationale**:
- Registry is source of truth
- MapServer mirrors it faithfully
- Proxy is enforcement boundary
- This is **intentional and acceptable for Phase 2**

**Consequence**:
- Mistakes in registry or mapfile = mistakes in exposure
- Validator (Stage 4) is critical to prevent errors
- Manual review (Gate E in Stage 4) is mandatory before production

---

## 8. Stage 5 Completion Criteria (Acceptance Checklist)

Use this **8-point checklist** to verify Stage 5 is complete:

```
Stage 5 Acceptance Checklist
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✓ CRITERION 1: No Inline Layers
  ☐ Master mapfile (tsird.map) contains ONLY:
    - MAP-level configuration
    - INCLUDE statements
    - NO LAYER definitions
  
✓ CRITERION 2: Published Layer Status
  ☐ Every layer with published: true in registry has STATUS ON in mapfile
  ☐ Every layer with published: false is absent from master mapfile
  ☐ (Unpublished layers may exist in 90_private_or_deprecated.map for reference)

✓ CRITERION 3: No Unpublished in GetCapabilities
  ☐ Run: curl GetCapabilities
  ☐ Verify: No layer with published: false appears in response
  ☐ Verify: NO orphan layers (not in registry)
  ☐ Verify: NO SAMPLE_GRID or test layers
  ☐ Verify: NO legacy health indicators (only tigray_health_facilities_2006)

✓ CRITERION 4: Scale Enforcement
  ☐ For each scale_mutex_pair in registry:
    - Both layers present in mapfile
    - MapServer MINSCALEDENOM/MAXSCALEDENOM match registry values
    - Ranges do NOT overlap (tested in Stage 4 validator)
    - Mutual exclusion enforced at render time

✓ CRITERION 5: Layer Count Identity
  ☐ count(registry published layers) == count(GetCapabilities layers)
  ☐ Test: python -c "print(len([l for l in registry['layers'].values() if l['published']]))"
  ☐ Compare to: GetCapabilities layer count
  ☐ Must be equal

✓ CRITERION 6: No Data Changes
  ☐ No modifications to Phase 1 ETL output
  ☐ No changes to /data/gold/ contents
  ☐ Gold data remains in EPSG:4326 canonical storage
  ☐ MapServer and registry modifications only

✓ CRITERION 7: Thematic Organization
  ☐ Mapfile includes are organized by category/theme:
    - layers_administrative.map
    - layers_transport.map
    - layers_health.map
    - layers_terrain.map
    - layers_rasters.map
  ☐ Each file contains only published layers from that theme
  ☐ Include order matches registry category order (for GetCapabilities layer sequence)

✓ CRITERION 8: All Tests Pass
  ☐ Registry validator: pytest tests/test_validator.py (all 9 rules)
  ☐ WMS integration: pytest tests/test_wms_integration.py
    - GetCapabilities smoke test
    - GetMap smoke test
    - GetFeatureInfo smoke test
    - Scale mutex enforcement test
  ☐ Manual verification checklist complete (above)
```

---

## 9. Layer Lifecycle Examples

### Example 1: Add Ethiopia Kebeles

**Files to modify**:
1. `infra/mapserver/mapfiles/includes/layers_administrative.map`
2. `config/atlas-registry.yaml`

**Action 1: Mapfile**
```mapfile
# Add to layers_administrative.map

LAYER
  NAME "ethiopia_kebeles"
  TYPE POLYGON
  STATUS ON
  CONNECTIONTYPE POSTGIS
  CONNECTION "..."
  DATA "geometry from gold.administrative where level='kebele'"
  
  CLASS
    STYLE
      COLOR 220 240 220
      OUTLINECOLOR 100 100 100
      WIDTH 1
    END
  END
  
  METADATA
    "wms_title" "Ethiopia Kebeles"
    "wms_include_items" "NAME,KEBELE_ID,POPULATION"
  END
  
  MINSCALEDENOM 50000
  MAXSCALEDENOM 500000
END
```

**Action 2: Registry**
```yaml
# Add to config/atlas-registry.yaml

layers:
  ethiopia_kebeles:
    wms_name: "ethiopia_kebeles"
    label: "Ethiopia Kebeles"
    type: "vector"
    source: "postgis"
    geometry_type: "polygon"
    published: true
    default_visible: false
    queryable: true
    min_scale: 500000
    max_scale: 50000
    identify_fields: ["NAME", "KEBELE_ID", "POPULATION"]
    attribution: "Source: Ethiopian Geospatial Authority"
```

**Add to category/group**:
```yaml
categories:
  - id: "cat_admin"
    label: "Administrative Boundaries"
    groups:
      - id: "grp_admin_ethiopia"
        label: "Ethiopia Administrative"
        layers: ["ethiopia_zones", "ethiopia_woredas", "ethiopia_kebeles"]  # NEW
```

**Test**:
```bash
validator config/atlas-registry.yaml  # Should pass
pytest tests/  # Should pass
curl "...GetCapabilities" | grep ethiopia_kebeles  # Should exist
```

### Example 2: Deprecate Old Survey Layer

**Files to modify**:
1. `config/atlas-registry.yaml`
2. `infra/mapserver/mapfiles/includes/90_private_or_deprecated.map` (move LAYER here)
3. `infra/mapserver/mapfiles/includes/layers_health.map` (remove LAYER)

**Action 1: Registry**
```yaml
# In atlas-registry.yaml, update layer to unpublished

layers:
  old_health_survey_2000:
    published: false  # WAS: true
    ...
```

**Action 2: Remove from active category/group**
```yaml
# Remove reference from any group:
categories:
  - id: "cat_health"
    groups:
      - layers: ["tigray_health_facilities_2006"]  # old_health_survey_2000 removed
```

**Action 3: Move mapfile LAYER block**
```mapfile
# Remove from layers_health.map

# Add to 90_private_or_deprecated.map (for archive/reference, not included in master)
LAYER
  NAME "old_health_survey_2000"
  TYPE POINT
  STATUS ON  # Doesn't matter; not included in master
  ...
END
```

**Test**:
```bash
validator config/atlas-registry.yaml  # Should pass
curl "...GetCapabilities" | grep old_health_survey_2000  # Should NOT exist
```

---

## 10. Commit Message Template

**For layer additions**:
```
Add <layer_name> layer (published, <queryable or not queryable>)

- Add <layer_id> to layers_<category>.map (MapServer)
- Add <layer_id> to atlas-registry.yaml (registry)
- Add <layer_id> to cat_<category>/grp_<group> (category mapping)
- Scale thresholds: min_scale=X max_scale=Y (cartographic convention)
- Identify fields: [FIELD1, FIELD2, ...] (if queryable)
```

**For layer changes**:
```
Update <layer_name> layer: <change description>

- Modify <layer_id> in layers_<category>.map (reason)
- Update <layer_id> in atlas-registry.yaml (reason)
- Validator passes, test suite passes
```

**For layer deprecation**:
```
Deprecate <layer_name> layer (set published: false)

- Remove <layer_id> from layers_<category>.map include
- Move LAYER block to 90_private_or_deprecated.map (for reference)
- Update <layer_id> to published: false in atlas-registry.yaml
- Remove <layer_id> from category/group mappings
```

---

## 11. Implementation Roadmap

**Phase 2 Scope (this stage)**:
1. [x] Define publication rule and mapfile structure
2. [x] Document layer lifecycle
3. [x] Specify scale enforcement (mutex pairs)
4. [x] Define GetCapabilities contract
5. [x] Define Identify contract
6. [x] Provide acceptance checklist
7. ✓ Ready to refactor

**Phase 2 Implementation (Stage 5 work)**:
1. Refactor mapfiles into thematic includes
2. Move all published layers to master includes
3. Archive unpublished layers in 90_private_or_deprecated.map
4. Update 02_web_metadata.map for EPSG:3857 (view_crs) support
5. Verify GetCapabilities output
6. Run full test suite (Criterion 8)

**Phase 2 Deployment (after Stage 5)**:
1. Deploy refactored mapfiles to production
2. Verify GetCapabilities (Criterion 3)
3. Final manual review (Gate D/E from Stage 4)
4. Proceed to Stage 6 (Frontend Implementation)

---

**✓ END OF STAGE 5: MAPSERVER PUBLICATION CONTRACT FROZEN**

**Next Stage**: Stage 6 — Frontend Implementation (OpenLayers + Registry Consumer)

Use the **8-point acceptance checklist** above as the definitive completion gate for Stage 5.
