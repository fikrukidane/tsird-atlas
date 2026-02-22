# TSIRD Pipeline Flow Diagrams

**Version**: 1.0  
**Date**: 2026-02-21  
**Purpose**: Visual reference for pipeline stages, data movement, and system interactions

---

## Overall System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     TSIRD ATLAS DATA ENGINEERING SYSTEM                     │
└─────────────────────────────────────────────────────────────────────────────┘

EXTERNAL SOURCES (Read-Only)
│
├─ Shapefiles (vectors)          DEM/Slope Rasters       Mask Geometries
│  ├─ Boundaries                  ├─ et-dtm-2001.tif      └─ tigray_boundary.shp
│  ├─ Roads                       └─ et-slp-2001.tif
│  ├─ Health Facilities
│  ├─ Towns
│  ├─ Administrative units
│  └─ Land cover / Ecology
│
└─→ /work/data/raw/vectors/ (mounted in ETL container)
    └─→ raw_inventory_audit.py
        └─→ audit_inventory.{csv,md}

                                    ↓
    ┌───────────────────────────────────────────────────────────────────┐
    │ STAGE 1: RAW INVENTORY AUDIT                                      │
    │ • Detect CRS issues                                               │
    │ • Check geometry validity (sample report)                         │
    │ • Flag encoding problems                                          │
    │ • Report bounds sanity                                            │
    │ Output: audit_inventory.csv + markdown summary                    │
    └───────────────────────────────────────────────────────────────────┘

                                    ↓
    ┌───────────────────────────────────────────────────────────────────┐
    │ STAGE 2: CRS NORMALIZATION TO EPSG:4326                           │
    │ • Load crs_overrides.yml (explicit CRS assignments)               │
    │ • Read each raw layer                                             │
    │ • Reproject to 4326 (if needed)                                   │
    │ • Repair geometries (buffer(0) → make_valid)                      │
    │ • Check bounds [-180,180]×[-90,90]                                │
    │ • If valid ≥ 98% → GOLD ✓                                         │
    │ • Else → QUARANTINE, copy forensics                               │
    │ Output: gold/atlas_4326/ ✓ & normalized/quarantine/ ✗             │
    └───────────────────────────────────────────────────────────────────┘

                                    ↓
    ┌───────────────────────────────────────────────────────────────────┐
    │ STAGE 3: REGIONAL SEPARATION (Tigray vs Ethiopia-Wide)            │
    │ • Load classification_overrides.yml                               │
    │ • For each GOLD layer:                                            │
    │   ├─ If name in tigray_force → TIGRAY_ONLY                        │
    │   ├─ If name in ethiopia_force → ETHIOPIA_WIDE                    │
    │   └─ Else: Compute intersection ratio vs tigray_boundary mask     │
    │     ├─ ratio ≥ 0.95 → TIGRAY_ONLY (clip to mask)                  │
    │     └─ ratio < 0.95 → ETHIOPIA_WIDE (copy as-is)                  │
    │ Output: gold/tigray/ (clipped) & gold/ethiopia/ (full extent)     │
    └───────────────────────────────────────────────────────────────────┘

                                    ↓
    ┌───────────────────────────────────────────────────────────────────┐
    │ STAGE 4: MAPSERVER INTEGRATION                                    │
    │ • Generate or update includes/vectors_gold.map                    │
    │ • For each layer: create OGR LAYER block                          │
    │   ├─ CONNECTION = "/data/gold/atlas_4326/"                        │
    │   ├─ DATA = "{tigray|ethiopia}/{LayerName}"                       │
    │   ├─ PROJECTION = "init=epsg:4326" (inherited from MAP)           │
    │   └─ METADATA = WMS metadata + query fields                       │
    │ • Restart tsird-mapserver container                               │
    │ • Validate: GetCapabilities returns layer list                    │
    │ • Validate: GetMap returns real PNG (not error image)             │
    │ Output: WMS service @ /map/ogc endpoint                           │
    └───────────────────────────────────────────────────────────────────┘

                                    ↓
    ┌───────────────────────────────────────────────────────────────────┐
    │ WMS SERVICE EXPOSED                                               │
    │ • GetCapabilities: Layer list + SRS support                       │
    │ • GetMap: Render PNG/GeoTIFF for BBOX + layer selection           │
    │ • GetFeatureInfo: Query attributes by pixel                       │
    │ • WFS GetFeature: Download GeoJSON/GML                            │
    │ Endpoint: https://lab.tigrayinsights.net/map/ogc                  │
    └───────────────────────────────────────────────────────────────────┘

                                    ↓
    ┌───────────────────────────────────────────────────────────────────┐
    │ CLIENT APPLICATIONS                                               │
    │ • QGIS: Add WMS layer → visualize & analyze                       │
    │ • Web Viewer: Leaflet/OpenLayers → interactive dashboard          │
    │ • CLI Tools: curl GetFeatureInfo → extract data for scripts       │
    └───────────────────────────────────────────────────────────────────┘
```

---

## Stage 1: Raw Inventory Audit

```
raw_inventory_audit.py

For each .shp in /work/data/raw/vectors/
│
├─ Read shapefile (attempt UTF-8, fallback Latin1)
│  ├─ Error? Record error_type + message → audit_inventory.csv
│  └─ Success? Continue
│
├─ Extract metadata:
│  ├─ Feature count
│  ├─ CRS declaration (if any)
│  ├─ Bounds (minx, miny, maxx, maxy)
│  ├─ Geometry types (Point|LineString|Polygon|Multi*)
│  ├─ Geometry validity ratio (% valid per feature)
│  ├─ Empty geometry ratio
│  ├─ Z coordinates? (Has 3D?)
│  └─ Column names + count
│
├─ Flag anomalies:
│  ├─ Out-of-range bounds (e.g., CRS claims 4326 but bounds > 85°)
│  ├─ Inverted bounds (minx > maxx)
│  ├─ Nil geometries
│  ├─ Self-intersecting/overlapping geometries
│  └─ Encoding-induced string corruption
│
└─ Write CSV row + track for next stage

Output: audit_inventory.csv
├─ layer_name | read_ok | error_type | feature_count | crs_epsg
├─ bounds_flag | valid_geom_ratio | empty_geom_ratio | columns
└─ sample_invalid_reason | ...

Human-readable summary: audit_inventory.md
├─ Table 1: Layers by read status (OK / ERROR)
├─ Table 2: CRS distribution (EPSG:4326, EPSG:20137, etc.)
├─ Table 3: Geometry validity percentiles
├─ Table 4: Encoding issues
└─ Recommendations for next stage
```

---

## Stage 2: CRS Normalization

```
normalize_to_gold_4326.py

Input: audit_inventory.csv + raw layers + crs_overrides.yml

For each layer in raw/:
│
├─ 1. Read shapefile (with fallback encodings)
│     ├─ Deduplicate columns (append __2, __3 if duplicates)
│     └─ Store feature_count, source_crs
│
├─ 2. Determine ASSIGNED_CRS (interpretation)
│     │
│     ├─ Check crs_overrides.yml
│     │  ├─ Override found? Use it (e.g., TigrayRoadsIn2006 → EPSG:32637)
│     │  └─ No override? Continue
│     │
│     ├─ Check source CRS declaration
│     │  ├─ Valid EPSG? Use it
│     │  └─ Missing/Invalid? Continue
│     │
│     └─ Auto-detect from bounds
│        ├─ Bounds look geographic (±180/90)? Assume EPSG:4326
│        └─ Bounds huge or weird? QUARANTINE (CRS_MISSING_NO_OVERRIDE)
│
├─ 3. Reproject to EPSG:4326 (if not already)
│     ├─ assigned_crs == 4326? Skip reprojection
│     └─ Else: gdf.to_crs(epsg=4326) → may transform coordinates
│
├─ 4. Post-reprojection bounds check
│     ├─ All coords within [-180,180] × [-90,90]?
│     ├─ Yes? Continue
│     └─ No? QUARANTINE (OUT_OF_RANGE_FOR_4326 | ABSURD_BOUNDS)
│
├─ 5. Geometry validation & repair
│     │
│     ├─ Calculate valid_ratio_pre (% valid non-empty geometries)
│     │
│     ├─ If valid_ratio_pre < 0.98:
│     │  ├─ Try buffer(0) repair
│     │  ├─ Recalculate valid_ratio_post
│     │  │
│     │  └─ If still < 0.98:
│     │     ├─ Try shapely.make_valid()
│     │     ├─ Recalculate valid_ratio_post
│     │     │
│     │     └─ If STILL < 0.98:
│     │        └─ QUARANTINE (GEOM_INVALID_POST_REPAIR)
│     │
│     └─ Else: valid ratio sufficient, continue
│
├─ 6. Final column deduplication pass
│
└─ 7. Write output
      ├─ valid_ratio_post ≥ 0.98 → Write to gold/atlas_4326/{stem}.shp ✓
      └─ Else → Copy raw components to quarantine/{stem}/ + forensics ✗

Output: GOLD layers (EPSG:4326 canonical)
├─ All geometries >= 98% valid
├─ All bounds within ±180/90
└─ Ready for regional separation

Output: QUARANTINE layers (failed validation)
├─ quarantine/{layer_name}/{layer_name}.shp + sidecars
├─ quarantine/{layer_name}/diagnostics.json (full record)
└─ Operator can review + adjust crs_overrides.yml + retry

Output Report: normalization_report.csv
├─ layer_name | status | reason | source_crs | assigned_crs
├─ reprojected | bounds_flag | valid_ratio_pre | valid_ratio_post
├─ geometry_repaired | feature_count | deduped_columns | error
└─ ...

Output Report: normalization_report.md
├─ Summary: {total} layers, {gold} GOLD, {quarantine} QUARANTINE
├─ Quarantine reason frequencies
├─ Average geometry repair success rate
└─ Encoding issues encountered
```

---

## Stage 3: Regional Separation

```
separate_layers.py

Input: gold/atlas_4326/ (all layers EPSG:4326)
       gold/_masks/tigray_boundary.shp (clip geometry)
       classification_overrides.yml (forced assignments)

For each .shp in gold/atlas_4326/ (except bound01, bound02, bound03):
│
├─ 1. Check classification_overrides.yml
│     ├─ If layer name in tigray_force → SET CLASS = TIGRAY_ONLY
│     ├─ Else if layer name in ethiopia_force → SET CLASS = ETHIOPIA_WIDE
│     └─ Else → Continue to ratio calculation
│
├─ 2. Calculate intersection ratio (if not overridden)
│     │
│     ├─ Reproject layer + mask to EPSG:32637 (metric CRS)
│     │
│     ├─ Geometry type check:
│     │  ├─ POLYGON? → area_inside = intersection(layer, mask).area.sum()
│     │  │           → area_total = layer.area.sum()
│     │  │           → ratio = area_inside / area_total
│     │  │
│     │  ├─ LINESTRING? → length_inside = intersection(layer, mask).length.sum()
│     │  │               → length_total = layer.length.sum()
│     │  │               → ratio = length_inside / length_total
│     │  │
│     │  └─ POINT? → count_inside = layer.within(mask).sum()
│     │            → count_total = len(layer)
│     │            → ratio = count_inside / count_total
│     │
│     ├─ Compare to threshold (0.95)
│     │  ├─ ratio >= 0.95? → TIGRAY_ONLY
│     │  └─ ratio < 0.95? → ETHIOPIA_WIDE
│     │
│     └─ Record: (layer_name, class, ratio, geom_type, metric)
│
├─ 3. Write output
│     │
│     ├─ If TIGRAY_ONLY:
│     │  ├─ Clip geometries to mask boundary
│     │  ├─ Write to: gold/tigray/{stem}.shp
│     │  └─ Store clipped features
│     │
│     └─ If ETHIOPIA_WIDE:
│        ├─ Copy layer as-is (no clipping)
│        ├─ Write to: gold/ethiopia/{stem}.shp
│        └─ Store full-extent features
│
└─ 4. Report

Output: gold/tigray/ (Tigray-only, clipped)
├─ All layer geometries clipped to tigray_boundary mask
├─ Reduced geometry complexity (fewer features after clip)
└─ Ready for WMS exposure as "Tigray subset"

Output: gold/ethiopia/ (Ethiopia-wide, full extent)
├─ All layer geometries in full national extent
├─ Original complexity + features preserved
└─ Ready for WMS exposure as "Country-wide / full dataset"

Output Report: classification_report.csv
├─ layer_name | classification | ratio | geom_type | metric | override
└─ coverage_area_percent (for visibility)

Output Report: classification_report.md
├─ Summary: {tigray_only} layers clipped, {ethiopia_wide} layers kept
├─ Table: Layer classification with ratios
├─ List of overridden layers (forced assignments)
└─ Recommendations (e.g., if threshold seems off)
```

---

## Stage 4: MapServer Integration

```
Generated/Updated: includes/vectors_gold.map

Template (one LAYER per gold layer):

LAYER
  NAME "ethiopia_woredas"                    ← Unique identifier
  TYPE POLYGON                               ← POLYGON|LINESTRING|POINT|RASTER
  STATUS ON                                  ← Visible in WMS
  
  CONNECTIONTYPE OGR                         ← Use GDAL/OGR driver
  CONNECTION "/data/gold/atlas_4326/"        ← Base directory
  DATA "ethiopia/ethio_wereda"                ← Relative path, no .shp extension
  
  PROJECTION
    "init=epsg:4326"                         ← Can inherit from MAP; redundant if same
  END
  
  METADATA
    "wms_title" "Ethiopia - Woredas"         ← Display name in GetCapabilities
    "wms_srs" "EPSG:4326 EPSG:3857"          ← Supported SRS for client requests
    "wms_enable_request" "*"                 ← Allow all WMS verbs
    "wms_queryable" "true"                   ← Support GetFeatureInfo
    "wms_feature_info_mime_type" "text/plain" ← Attribute table format
    "gml_include_items" "col1,col2,col3"     ← Expose these columns to GML
    "wms_include_items" "col1,col2,col3"     ← Expose these columns to WMS
  END
  
  CLASS
    NAME "default"                           ← Style identifier
    STYLE
      OUTLINECOLOR 0 0 0                     ← Border color
      COLOR 200 100 50                       ← Fill color (RGB)
      OUTLINEWIDTH 1                         ← Border thickness (pixels)
    END
  END
END

Process:
│
├─ 1. Read classification_report.csv (tigray | ethiopia assignments)
│
├─ 2. For each layer:
│     ├─ Determine folder: egypt or tigray
│     ├─ Determine geometry type from layer
│     ├─ Generate appropriate STYLE (colors, widths)
│     └─ Build LAYER XML block
│
├─ 3. Append all LYR blocks to includes/vectors_gold.map
│
├─ 4. Copy tsird.map + includes/ to container:
│     └─ docker cp /host/infra/mapserver/mapfiles/* tsird-mapserver:/etc/mapserver/
│
├─ 5. Restart MapServer container:
│     └─ docker restart tsird-mapserver
│
├─ 6. Validate WMS endpoint:
│     ├─ curl GetCapabilities → grep <Layer> blocks → count should match
│     └─ Expected: 40+ layers, all with correct names
│
├─ 7. Spot-check a few GetMap requests:
│     └─ For each layer, request smallest BBOX → check output is real PNG (> 1KB)
│
└─ 8. If all checks pass: READY FOR CLIENT ACCESS ✓

Outputs:
├─ includes/vectors_gold.map (updated on host)
├─ Container mapfile synced + hot-reloaded
├─ WMS GetCapabilities returns all layers
└─ WMS GetMap returns renderable images (not error thumbnails)
```

---

## WMS Request Flow

```
Client (QGIS / Web Viewer)
│
├─ "Add WMS layer from https://lab.tigrayinsights.net/map/ogc"
│
└─ GetCapabilities request
   │
   ├─ Host Nginx (port 443 SSL)
   │  └─ Reverse proxy → localhost:TSIRD_EDGE_PORT
   │
   ├─ tsird-edge container (port 8080)
   │  └─ Route /map/ogc* → upstream tsird-mapserver:8000
   │
   └─ tsird-mapserver container (MapServer)
      │
      ├─ Read: /etc/mapserver/tsird.map
      ├─ Read: /etc/mapserver/includes/vectors_gold.map
      ├─ Parse all LAYER blocks
      ├─ Generate WMS Capabilities XML
      └─ HTTP 200 + XML response (30KB+)

Response includes:
├─ <Layer>ethiopia_boundary_level2</Layer>
├─ <Layer>ethiopia_woredas</Layer>
├─ <Layer>tigray_roads_2006</Layer>
├─ ... 40+ layers
├─ <SRS>EPSG:4326</SRS>
└─ <SRS>EPSG:3857</SRS>

Client now displays layer picker → user selects "ethiopia_woredas"

GetMap request
│
├─ BBOX=33.0,3.0,48.0,15.5 (EPSG:4326 coords)
├─ WIDTH=800 HEIGHT=600
├─ LAYERS=ethiopia_woredas
├─ FORMAT=image/png
│
└─ (Same routing as above)

MapServer:
├─ Load LAYER definition for ethiopia_woredas
├─ Open: /data/gold/atlas_4326/ethiopia/ethio_wereda.shp
├─ Clip features to BBOX
├─ Render: COLOR 200 100 50 polygons + OUTLINECOLOR 0 0 0 borders
├─ Output PNG at 800×600
└─ HTTP 200 + PNG image (~40-100 KB depending on feature density)

Client displays rendered map with woredas visible

Requests GetFeatureInfo (user clicks on a woreda polygon)
│
├─ Include QUERY_LAYERS=ethiopia_woredas
├─ X=400 Y=300 (pixel coords within the map image)
│
└─ MapServer looks up feature at that pixel location

IF found:
├─ Extract attributes from DBF (column values)
├─ Format as text/plain (one row per column)
├─ HTTP 200 + attribute text

IF not found:
└─ HTTP 200 + empty response

Client displays attribute popup (woreda name, population, etc.)
```

---

## Error Diagnosis Flow

```
User reports: "QGIS can connect to WMS but no layers render (blank map)"

Diagnosis checklist:
│
├─ Step 1: Check WMS GetCapabilities health
│  │
│  ├─ curl -v "https://lab.tigrayinsights.net/map/ogc?\
│  │   SERVICE=WMS&VERSION=1.3.0&REQUEST=GetCapabilities"
│  │
│  ├─ If HTTP 500 → Mapfile syntax error (check logs)
│  │  └─ docker logs tsird-mapserver | grep -i error
│  │
│  ├─ If HTTP 200 but tiny response (< 5KB) → Missing layers
│  │  └─ Check includes/vectors_gold.map exists and is included
│  │
│  └─ If HTTP 200 + 30KB+ XML → Capabilities OK, issue is GetMap
│
├─ Step 2: Test individual layer rendering
│  │
│  ├─ curl "https://lab.tigrayinsights.net/map/ogc?\
│  │   SERVICE=WMS&VERSION=1.3.0&REQUEST=GetMap&\
│  │   CRS=EPSG:4326&BBOX=33,3,48,15&WIDTH=800&HEIGHT=600&\
│  │   LAYERS=ethiopia_woredas&FORMAT=image/png"\
│  │   > test.png
│  │
│  ├─ If file size << 1 KB (typical error: ~542 bytes) → Rendering failed
│  │  └─ Likely cause: Bad layer configuration (wrong DATA path, wrong CRS)
│  │
│  ├─ file test.png → Shows PNG format?
│  │  ├─ If PNG → Valid image (may still be blank if bbox misses features)
│  │  └─ If tiny text → Error message from MapServer (check logs)
│  │
│  └─ If >> 100 KB → Layer loaded successfully, many features rendered
│
├─ Step 3: Check layer configuration
│  │
│  ├─ grep -n "NAME \"ethiopia_woredas\"" includes/vectors_gold.map
│  │  └─ Does layer definition exist?
│  │
│  ├─ grep -A 5 "NAME \"ethiopia_woredas\"" includes/vectors_gold.map
│  │  ├─ DATA line: Points to correct file path?
│  │  │  ├─ Correct: DATA "ethiopia/ethio_wereda"
│  │  │  └─ Wrong: DATA "ethio_wereda_4326_fixed" or "ethiopia_woredas_4326"
│  │  │
│  │  ├─ PROJECTION: Does it conflict with MAP PROJECTION?
│  │  │  ├─ Stale: "init=epsg:20137" (old UTM, wrong!)
│  │  │  ├─ Stale: "init=epsg:32637" (old UTM, wrong!)
│  │  │  └─ Correct: Omit or use "init=epsg:4326"
│  │  │
│  │  └─ Connection: Is CONNECTIONTYPE OGR and CONNECTION correct?
│  │     ├─ Correct: CONNECTION "/data/gold/atlas_4326/"
│  │     └─ Wrong: Old path or typo
│  │
│  └─ docker exec tsird-mapserver ls -la /data/gold/atlas_4326/ethiopia/
│     └─ Verify the actual shapefile exists in container
│
├─ Step 4: Check MapServer debug logs
│  │
│  ├─ docker logs tsird-mapserver | tail -50
│  │
│  └─ Look for:
│     ├─ "msOGRFileOpen failed" → File not found or permissions
│     ├─ "projectionObj not initialized" → PROJECTION block corrupt
│     ├─ "Cannot find symbol" → SYMBOL definition missing (point layers)
│     └─ "Parse error in OGR" → Shapefile corrupted or invalid
│
└─ Step 5: Recover
   │
   ├─ If DATA path wrong: Edit includes/vectors_gold.map, docker cp, docker restart
   ├─ If symbol missing: Add SYMBOL "circle" to tsird.map
   ├─ If PROJECTION wrong: Remove conflicting layer-level block
   └─ Re-test GetMap after each fix
```

---

## Data Quality Checkpoint Summary

```
┌────────────────────────┬──────────────────┬──────────────┬─────────────┐
│ Checkpoint             │ Metric/Threshold │ Pass Action  │ Fail Action │
├────────────────────────┼──────────────────┼──────────────┼─────────────┤
│ Audit: Read Success    │ No exception     │ Continue     │ Report      │
│ Audit: CRS Present     │ Any EPSG found   │ Continue     │ Report + OK │
│ Audit: Bounds Valid    │ Finite coords    │ Continue     │ Report      │
│ Audit: Geom Validity   │ ≥ 98% valid      │ Continue     │ Report      │
│                        │                  │              │             │
│ Normalize: CRS Known   │ Override or auto │ Continue     │ Quarantine  │
│ Normalize: Reproject   │ All in 4326      │ Continue     │ Quarantine  │
│ Normalize: Bounds 4326 │ Within ±180/90   │ Continue     │ Quarantine  │
│ Normalize: Geom Repair │ ≥ 98% valid post │ Continue     │ Quarantine  │
│ Normalize: Write GOLD  │ File persistence │ Move to next │ Error log   │
│                        │                  │              │             │
│ Separate: Mask Load    │ Valid boundary   │ Continue     │ Error + stop│
│ Separate: Ratio Calc   │ Finite ratio     │ Continue     │ Report      │
│ Separate: Clip/Copy    │ File write OK    │ Continue     │ Report      │
│                        │                  │              │             │
│ MapServer: Mapfile Syn │ Valid XML/MAP    │ Continue     │ Error log   │
│ MapServer: GetCapab    │ 40+ layers named │ Continue     │ Check map   │
│ MapServer: GetMap      │ PNG > 1 KB       │ READY ✓      │ Debug layer │
└────────────────────────┴──────────────────┴──────────────┴─────────────┘
```

