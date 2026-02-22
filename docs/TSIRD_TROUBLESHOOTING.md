# TSIRD System Troubleshooting Guide

**Version**: 1.0  
**Date**: 2026-02-21  
**Purpose**: Diagnostic procedures for common failures

---

## Table of Contents

1. [Quick Diagnostic Tree](#quick-diagnostic-tree)
2. [Error Catalog](#error-catalog)
3. [Lessons Learned](#lessons-learned--error-prevention)
4. [Terminal Debugging Commands](#terminal-debugging-commands)

---

## Quick Diagnostic Tree

Use this flowchart to quickly identify the problem category:

```
PROBLEM OBSERVED
│
├─ WMS SERVICE NOT RESPONDING
│  └─ → Go to: Problem #1 Service Down
│
├─ WMS RESPONDS BUT NO LAYERS VISIBLE
│  ├─ GetCapabilities returns layers OK?
│  │  ├─ YES → → Go to: Problem #2 Blank Map
│  │  └─ NO → → Go to: Problem #3 GetCapabilities Fails
│  │
│  └─ (OR) Test WMS GetMap manually
│     ├─ Output size >> 100 KB → Layer loaded, rendering issue
│     │  └─ → Go to: Problem #4 Point Layers Not Visible
│     ├─ Output size ~ 500 bytes → Error image
│     │  └─ → Go to: Problem #5 Tiny PNG Output
│     └─ Timeout error → → Go to: Problem #6 Hanging Requests
│
├─ PIPELINE SCRIPT CRASHES
│  ├─ normalize_to_gold_4326.py fails?
│  │  ├─ Encoding error → → Go to: Problem #7 Encoding Issues
│  │  ├─ CRS error → → Go to: Problem #8 CRS Override Missing
│  │  └─ Bounds error → → Go to: Problem #9 Out-of-Range Bounds
│  │
│  ├─ separate_layers.py fails?
│  │  ├─ Mask not found → → Go to: Problem #10 Missing Mask File
│  │  └─ Geometry error → → Go to: Problem #11 Geometry Clipping Failed
│  │
│  └─ raw_inventory_audit.py fails?
│     └─ → Go to: Problem #12 Audit Script Failure
│
├─ CONTAINER WON'T START
│  ├─ tsird-mapserver → → Go to: Problem #13 MapServer Startup Failure
│  ├─ tsird-postgis → → Go to: Problem #14 PostgreSQL Startup Failure
│  ├─ tsird-etl → → Go to: Problem #15 ETL Container Startup
│  └─ tsird-edge → → Go to: Problem #16 Edge Gateway Issues
│
├─ DATA NOT APPEARING IN GOLD FOLDER
│  ├─ Pipeline ran but gold/ still empty?
│  │  └─ → Go to: Problem #17 Pipeline Produces No Output
│  │
│  └─ Files exist but wrong location?
│     └─ → Go to: Problem #18 Files In Wrong Folder
│
├─ LAYERS SHOW IN QGIS BUT BLANK / NO FEATURES
│  ├─ Geometry valid but not rendering?
│  │  ├─ POLYGON/LINESTRING → → Go to: Problem #19 Polygon/Line Styling
│  │  └─ POINT → → Go to: Problem #4 Point Symbols Missing
│  │
│  └─ → Go to: Problem #20 CRS Reprojection Mismatch
│
└─ OTHER
   └─ → Go to: [Error Catalog](#error-catalog) for comprehensive list
```

---

## Error Catalog

### Problem #1: Service Down

**Symptom**: Connection refused on port 7080

**Diagnosis**: `docker-compose ps | grep tsird-edge`  
**Solution**: `docker-compose up -d && curl http://localhost:7080/map/health`

# If present but not running
docker-compose logs tsird-edge | tail -30

# If running, test direct container
docker-compose exec tsird-edge curl -v http://localhost:8080/map/health

# If that fails, check edge gateway config
docker-compose exec tsird-edge cat /etc/nginx/conf.d/* | head -50
```

**Solutions**:

```bash
# Bring up all services
docker-compose up -d

# Restart edge specifically
docker-compose restart tsird-edge

# Wait for health
sleep 5
docker-compose exec tsird-edge curl -f http://localhost:8080/map/health

# Test from host
curl http://localhost:7080/map/health

# If host test fails, check host Nginx config
sudo nginx -t  # Syntax check
sudo systemctl restart nginx

# Test again
curl https://lab.tigrayinsights.net/map/health
```

---

### Problem #2: Blank Map (GetCapabilities Works, GetMap Blank)

**Symptom**: 
- `curl GetCapabilities` returns 30KB+ XML with layers listed ✓
- `curl GetMap` returns PNG but it displays blank (no features visible)

**Root Causes**:
- Wrong BBOX (outside feature extent)
- Layers present but styled as transparent/white-on-white
- Raster layer has no data in requested bbox

**Diagnosis**:

```bash
# 1. Verify layer has features
docker-compose exec tsird-etl python -c "
import geopandas as gpd
gdf = gpd.read_file('/work/data/gold/atlas_4326/ethiopia/ethio_wereda.shp')
print(f'Features: {len(gdf)}')
print(f'Bounds: {gdf.total_bounds}')
"

# 2. Try GetMap with full extent BBOX
curl -s "http://localhost:7080/map/ogc?\
  SERVICE=WMS&VERSION=1.3.0&REQUEST=GetMap&\
  CRS=EPSG:4326&BBOX=33,3,48,15&WIDTH=800&HEIGHT=600&\
  LAYERS=ethiopia_woredas&FORMAT=image/png" \
  > test.png && file test.png

# 3. Check map styling
grep -A 15 "NAME \"ethiopia_woredas\"" \
  /opt/tigrayinsights/apps/tsird/infra/mapserver/mapfiles/includes/vectors_gold.map | \
  grep -E "COLOR|STYLE"

# If COLOR is 255,255,255 (white) → Features exist but invisible
```

**Solutions**:

```bash
# Option 1: Use correct BBOX
# Get correct bounds:
docker-compose exec tsird-etl python -c "
import geopandas as gpd
gdf = gpd.read_file('/work/data/gold/atlas_4326/ethiopia/ethio_wereda.shp')
print('BBOX: {},{},{},{}'.format(*gdf.total_bounds))
"
# Use returned coords in GetMap

# Option 2: Change styling (if white)
# Edit includes/vectors_gold.map
# Find the layer CLASS/STYLE and change COLOR to visible value
# Example: COLOR 200 100 50

# Option 3: Add background layer for context
# Add a base layer (e.g., coastline, neighboring countries) as reference
```

---

### Problem #3: GetCapabilities Returns Tiny Response

**Symptom**: `curl GetCapabilities` returns < 10 KB response (mostly error text)

**Root Causes**:
- Mapfile syntax error (prevents parsing)
- INCLUDE statement fails (vectors_gold.map missing)
- Missing or corrupted MAP block

**Diagnosis**:

```bash
# 1. Check mapfile syntax
docker-compose exec tsird-mapserver mapserv -v 2>&1 | head -20

# 2. Try to parse mapfile explicitly
docker-compose exec tsird-mapserver bash -c \
  'shp2img -m /etc/mapserver/tsird.map -o /tmp/test.png 2>&1 | head -20'

# 3. Check INCLUDE references
grep "INCLUDE" /opt/tigrayinsights/apps/tsird/infra/mapserver/mapfiles/tsird.map

# 4. Verify included file exists in container
docker-compose exec tsird-mapserver ls -la /etc/mapserver/includes/

# 5. Test XML validity
docker-compose logs tsird-mapserver | tail -100 | grep -E "ERROR|Parse|error"
```

**Solutions**:

```bash
# Fix 1: Mapfile syntax error
# Edit tsird.map, check for:
# - Mismatched { } or END statements
# - Quoted strings with unescaped quotes
# - Missing newlines before END
nano /opt/tigrayinsights/apps/tsird/infra/mapserver/mapfiles/tsird.map

# Validate locally (on host if mapserver installed)
mapserv -v 2>&1 | head

# Fix 2: Missing INCLUDE file
# Ensure includes/vectors_gold.map exists
ls -la /opt/tigrayinsights/apps/tsird/infra/mapserver/mapfiles/includes/

# If missing, create it or restore from backup

# Fix 3: Redeploy files
docker cp /opt/tigrayinsights/apps/tsird/infra/mapserver/mapfiles/* \
  tsird-mapserver:/etc/mapserver/

# Fix 4: Restart and retest
docker-compose restart tsird-mapserver
sleep 5
curl -s "http://localhost:7080/map/ogc?SERVICE=WMS&REQUEST=GetCapabilities" | wc -c
# Should now be > 30000
```

---

### Problem #4: Point Layers Not Visible

**Symptom**: 
- Point layers appear in GetCapabilities ✓
- GetMap returns real PNG (~30 KB) ✓
- But no visible points in the rendered image

**Root Causes**:
- SYMBOL not defined (common: SYMBOL 0)
- SYMBOL exists but wrong name in layer STYLE
- Point SIZE too small or transparent
- No features within requested BBOX

**Diagnosis**:

```bash
# 1. Check SYMBOL definitions
grep -E "SYMBOL|NAME" \
  /opt/tigrayinsights/apps/tsird/infra/mapserver/mapfiles/tsird.map | grep -A 1 "SYMBOL"

# 2. Check point layer STYLE
grep -B 5 -A 10 "NAME \"tigray_towns\"" \
  /opt/tigrayinsights/apps/tsird/infra/mapserver/mapfiles/includes/vectors_gold.map | \
  grep -E "STYLE|SYMBOL|SIZE|COLOR"

# 3. Count actual features
docker-compose exec tsird-etl python -c "
import geopandas as gpd
gdf = gpd.read_file('/work/data/gold/atlas_4326/tigray/Tigray_Towns.shp')
print(f'Total features: {len(gdf)}')
print(f'Bounds: {gdf.total_bounds}')
print(f'Types: {gdf.geom_type.unique()}')
"

# 4. Test GetMap with debug output
docker-compose exec tsird-mapserver bash -c \
  'MS_DEBUGLEVEL=5 mapserv QUERY_STRING="map=/etc/mapserver/tsird.map&\
   SERVICE=WMS&REQUEST=GetMap&\
   CRS=EPSG:4326&BBOX=12,36,15,40&WIDTH=800&HEIGHT=600&\
   LAYERS=tigray_towns&FORMAT=image/png" 2>&1 | grep -E "SYMBOL|shape|draw"'
```

**Solutions**:

```bash
# Solution 1: Add missing SYMBOLs (common)
# Edit tsird.map, in MAP block, after PROJECTION, add:

SYMBOL
  NAME "circle"
  TYPE ELLIPSE
  POINTS 1 1 END
END

SYMBOL
  NAME "square"
  TYPE VECTOR
  POINTS 0 0 0 1 1 1 1 0 0 0 END
END

# Solution 2: Fix layer STYLE
# Edit includes/vectors_gold.map, find point layer:
# Change: SYMBOL 0
# To:     SYMBOL "circle"
# And set SIZE (e.g., SIZE 8)

# Solution 3: Redeploy and restart
docker cp /opt/tigrayinsights/apps/tsird/infra/mapserver/mapfiles/* \
  tsird-mapserver:/etc/mapserver/
docker-compose restart tsird-mapserver
sleep 3

# Solution 4: Test again
curl -s "http://localhost:7080/map/ogc?\
  SERVICE=WMS&VERSION=1.3.0&REQUEST=GetMap&\
  CRS=EPSG:4326&BBOX=12,36,15,40&WIDTH=800&HEIGHT=600&\
  LAYERS=tigray_towns&FORMAT=image/png" | wc -c
# Should be > 50000 (real PNG with visible points)
```

---

### Problem #5: Tiny Error PNG (~500 bytes)

**Symptom**: GetMap returns PNG < 1 KB (is actually a tiny error image)

**Root Causes**:
- Layer DATA field points to non-existent file
- Layer PROJECTION conflicts with actual file CRS
- OGR cannot read the shapefile (permissions, corruption)

**Diagnosis**:

```bash
# 1. Check GetMap output
curl -s "http://localhost:7080/map/ogc?SERVICE=WMS&VERSION=1.3.0&\
  REQUEST=GetMap&CRS=EPSG:4326&BBOX=33,3,48,15&WIDTH=800&HEIGHT=600&\
  LAYERS=ethiopia_woredas&FORMAT=image/png" | wc -c
# If < 1000, it's an error image

# 2. Check MapServer error log
docker-compose logs tsird-mapserver | tail -50 | grep -E "ERROR|error|failed"

# Look for:
# - "msOGRFileOpen" → File not found
# - "Projection" → CRS mismatch
# - "Permission denied" → File permissions issue

# 3. Verify layer configuration
grep -A 8 "NAME \"ethiopia_woredas\"" \
  /opt/tigrayinsights/apps/tsird/infra/mapserver/mapfiles/includes/vectors_gold.map

# Check DATA line:
# Should be: DATA "ethiopia/ethio_wereda" (relative to CONNECTION base)
# NOT: DATA "ethio_wereda_4326_fixed" (old, corrupted name)

# 4. Verify file exists in container
docker-compose exec tsird-mapserver ls -lah /data/gold/atlas_4326/ethiopia/ethio_wereda.shp

# 5. Check file permissions
docker-compose exec tsird-mapserver stat /data/gold/atlas_4326/ethiopia/ethio_wereda.shp
```

**Solutions**:

```bash
# Solution 1: Fix DATA path
# Edit includes/vectors_gold.map
# Wrong paths are usually named with _4326 or _4326_fixed suffixes
# Old: DATA "ethio_wereda_4326_fixed"
# New: DATA "ethiopia/ethio_wereda"

# Solution 2: Remove layer-level PROJECTION if present
# Check for PROJECTION block inside the LAYER
# If present and conflicts with MAP projection, delete it
# (Especially if it says EPSG:20137 or EPSG:32637 when MAP is EPSG:4326)

# Solution 3: Fix file permissions
docker exec tsird-mapserver chmod 644 /data/gold/atlas_4326/ethiopia/ethio_wereda.*

# Solution 4: Verify file is not corrupted
docker-compose exec tsird-etl python -c "
import geopandas as gpd
gdf = gpd.read_file('/work/data/gold/atlas_4326/ethiopia/ethio_wereda.shp')
print(f'Read OK: {len(gdf)} features')
"

# Solution 5: Redeploy mapfile
docker cp /opt/tigrayinsights/apps/tsird/infra/mapserver/mapfiles/* \
  tsird-mapserver:/etc/mapserver/
docker-compose restart tsird-mapserver

# Solution 6: Retest
curl -s "http://localhost:7080/map/ogc?SERVICE=WMS&VERSION=1.3.0&\
  REQUEST=GetMap&CRS=EPSG:4326&BBOX=33,3,48,15&WIDTH=800&HEIGHT=600&\
  LAYERS=ethiopia_woredas&FORMAT=image/png" | wc -c
# Should now be > 40000
```

---

### Problem #6: GetMap Hanging / Timeout

**Symptom**: `curl GetMap` hangs for 30+ seconds then times out

**Root Causes**:
- Layer reading stalled (I/O hang)
- Geometry processing taking too long (complex/invalid shapes)
- MapServer deadlock or infinite loop
- Database connectivity issue

**Diagnosis**:

```bash
# 1. Try with timeout
timeout 5 curl -v "http://localhost:7080/map/ogc?..."
# If hangs past 5s, it's a server-side issue

# 2. Check MapServer logs for clues
docker-compose logs tsird-mapserver --tail=20

# 3. Monitor Docker container CPU/memory
docker stats tsird-mapserver --no-stream
# If CPU maxed or memory high, it's processing not I/O

# 4. Test single layer with smaller BBOX
curl -s --max-time 10 \
  "http://localhost:7080/map/ogc?SERVICE=WMS&VERSION=1.3.0&\
   REQUEST=GetMap&CRS=EPSG:4326&BBOX=12,36,13,37&WIDTH=100&HEIGHT=100&\
   LAYERS=tigray_schools_2006&FORMAT=image/png" | wc -c

# If still hangs, it's layer-specific

# 5. Check if shapefile is accessible
docker-compose exec tsird-mapserver ogrinfo /data/gold/atlas_4326/tigray/Tigray_Schools_2006.shp 2>&1 | head -10
```

**Solutions**:

```bash
# Solution 1: Restart MapServer (may clear deadlock)
docker-compose restart tsird-mapserver
sleep 5

# Solution 2: Increase WMS timeout in MapServer config
# (Not typically needed unless operations are legitimately slow)

# Solution 3: Recreate problematic layer
# If specific layer always hangs:
# - Run normalization again for that layer
# - Verify it's not corrupted in gold/

# Solution 4: Check data I/O performance
# If data is on slow disk, results may be slow but not hung
# Run the pipeline on faster storage if available
```

---

### Problem #7: Encoding Error (`UnicodeDecodeError`)

**Symptom**: 
```
UnicodeDecodeError: 'utf-8' codec can't decode byte 0xc9 in position 45: ...
```

**Root Causes**:
- Shapefile DBF header is Latin1, Cyrillic, or other non-UTF-8 encoding
- Raw data not cleaned before import

**Diagnosis**:

```bash
# Find which layer has encoding issues
grep -i "encoding" /work/reports/audit/normalization_report.csv

# Check the DBF file encoding
file -i /work/data/raw/vectors/problem_layer.dbf
# Look for "charset=" output

# Try reading with different encodings (Python)
docker-compose exec tsird-etl python << 'EOF'
import geopandas as gpd
try:
    gdf = gpd.read_file('/work/data/raw/vectors/problem_layer.shp')
    print("UTF-8: SUCCESS")
except Exception as e:
    print(f"UTF-8: FAILED - {e}")

try:
    gdf = gpd.read_file('/work/data/raw/vectors/problem_layer.shp', encoding='latin1')
    print("Latin1: SUCCESS")
except Exception as e:
    print(f"Latin1: FAILED - {e}")
EOF
```

**Solutions**:

```bash
# Solution 1: Use iconv to convert encoding (if known)
# Assuming CP1252 (Windows encoding)
iconv -f CP1252 -t UTF-8 \
  /work/data/raw/vectors/problem_layer.dbf > \
  /tmp/problem_layer_utf8.dbf

# Backup original
mv /work/data/raw/vectors/problem_layer.dbf \
  /work/data/raw/vectors/problem_layer.dbf.bak

# Replace
mv /tmp/problem_layer_utf8.dbf \
  /work/data/raw/vectors/problem_layer.dbf

# Solution 2: Add encoding override to Python script
# (Modify normalize_to_gold_4326.py to try more encodings)
# Or manually specify GPD read_file(encoding='latin1')

# Solution 3: Re-run pipeline
docker-compose exec tsird-etl python \
  /work/Docker\ Projects/TSIRD-Atlas-Data-Pipeline/scripts/normalize_to_gold_4326.py
```

---

### Problem #8: CRS Override Missing

**Symptom**: 
```
Layer quarantined with reason: "CRS_MISSING_NO_OVERRIDE"
```

**Root Causes**:
- Layer has no CRS declaration in metadata
- Bounds don't look geographic (assumed to be projected)
- CRS override not added to crs_overrides.yml

**Diagnosis**:

```bash
# 1. Check what CRS is in the raw layer
docker-compose exec tsird-etl python -c "
import geopandas as gpd
gdf = gpd.read_file('/work/data/raw/vectors/MyLayer.shp')
print(f'Declared CRS: {gdf.crs}')
print(f'Bounds: {gdf.total_bounds}')
"

# 2. Check if override exists
grep "MyLayer" /opt/tigrayinsights/apps/tsird/Docker\ Projects/TSIRD-Atlas-Data-Pipeline/config/crs_overrides.yml

# 3. Determine actual CRS (external knowledge)
# Check source documentation, project notes, or metadata files
```

**Solutions**:

```bash
# Solution 1: Add override to crs_overrides.yml
# Edit: /work/Docker Projects/TSIRD-Atlas-Data-Pipeline/config/crs_overrides.yml

nano /opt/tigrayinsights/apps/tsird/Docker\ Projects/TSIRD-Atlas-Data-Pipeline/config/crs_overrides.yml

# Add entry (ensure YAML formatting, 2-space indent):
# overrides:
#   MyLayer:
#     epsg: 32637  ← Use EPSG code for the actual CRS

# Common Ethiopian CRS codes:
# 20137 = Adindan UTM 37N (older projects)
# 32637 = WGS84 UTM 37N (common)
# 4326  = WGS84 Geographic (already 4326, shouldn't need override)

# Solution 2: Re-run normalization (will read the override)
docker-compose exec tsird-etl python \
  /work/Docker\ Projects/TSIRD-Atlas-Data-Pipeline/scripts/normalize_to_gold_4326.py

# Solution 3: Verify it moved to GOLD
grep "MyLayer" /work/reports/audit/normalization_report.csv | grep "GOLD"
```

---

### Problem #9: Out-of-Range Bounds

**Symptom**: 
```
Layer quarantined with reason: "OUT_OF_RANGE_FOR_4326" or "CRS_CLAIMS_4326_BUT_OUT_OF_RANGE"
```

**Root Causes**:
- Layer claims EPSG:4326 but coordinates are actually projected (e.g., UTM)
- Large coordinate values (>1e8) indicating wrong CRS
- Bounds beyond ±180 lon, ±90 lat

**Diagnosis**:

```bash
# 1. Check declared vs actual bounds
docker-compose exec tsird-etl python -c "
import geopandas as gpd
gdf = gpd.read_file('/work/data/raw/vectors/MyLayer.shp')
print(f'CRS: {gdf.crs}')
print(f'Bounds: {gdf.total_bounds}')
print(f'Max abs value: {max(abs(v) for v in gdf.total_bounds)}')
"

# 2. Determine actual CRS by analyzing bounds
# If bounds are like [400000, 800000, 500000, 900000]:
#   → Likely UTM or other projected CRS (not geographic)
# If bounds are like [33, 3, 48, 15]:
#   → Looks geographic (lon/lat)

# 3. Research the data source
# Check original documentation or metadata
```

**Solutions**:

```bash
# Solution 1: Add CRS override (most common fix)
# The layer likely has wrong CRS declaration; override it

nano /opt/tigrayinsights/apps/tsird/Docker\ Projects/TSIRD-Atlas-Data-Pipeline/config/crs_overrides.yml

# Add:
# overrides:
#   MyLayer:
#     epsg: 32637  # Or 20137, determine from bounds

# Solution 2: Re-run with override
docker-compose exec tsird-etl python \
  /work/Docker\ Projects/TSIRD-Atlas-Data-Pipeline/scripts/normalize_to_gold_4326.py

# Solution 3: Verify layer now in GOLD
ls /work/data/gold/atlas_4326/ | grep -i mylayer
```

---

### Problem #10: Missing Mask File

**Symptom**: 
```
separate_layers.py fails: FileNotFoundError: /work/data/gold/_masks/tigray_boundary.shp
```

**Root Causes**:
- Mask file not created during normalization
- Mask file deleted or moved
- Wrong path in separate_layers.py

**Diagnosis**:

```bash
# Check if mask exists
ls -la /work/data/gold/atlas_4326/_masks/

# If empty or missing:
find /work/data -name "*tigray*" -type f 2>/dev/null | head -20

# Check separate_layers.py for hardcoded path
grep "MASK_SHP" /opt/tigrayinsights/apps/tsird/Docker\ Projects/TSIRD-Atlas-Data-Pipeline/scripts/separate_layers.py
```

**Solutions**:

```bash
# Solution 1: Create _masks folder if missing
mkdir -p /work/data/gold/atlas_4326/_masks

# Solution 2: Check if mask exists in raw
ls /work/data/raw/vectors/*tigray*
ls /work/data/raw/vectors/bound*.shp

# Solution 3: Copy mask manually (if present in raw)
cp /work/data/raw/vectors/bound02.shp /work/data/gold/atlas_4326/_masks/
cp /work/data/raw/vectors/bound02.* /work/data/gold/atlas_4326/_masks/
mv /work/data/gold/atlas_4326/_masks/bound02.shp /work/data/gold/atlas_4326/_masks/tigray_boundary.shp

# Solution 4: Or run normalization to generate it
docker-compose exec tsird-etl python \
  /work/Docker\ Projects/TSIRD-Atlas-Data-Pipeline/scripts/normalize_to_gold_4326.py

# Solution 5: Re-run separation
docker-compose exec tsird-etl python \
  /work/Docker\ Projects/TSIRD-Atlas-Data-Pipeline/scripts/separate_layers.py
```

---

### Problem #11: Geometry Clipping Failed

**Symptom**: 
```
separate_layers.py error: Failed to clip geometry to mask boundary
```

**Root Causes**:
- Layer geometries invalid (self-intersecting, overlapping rings)
- Mask geometry invalid
- Too many complex geometries causing clipping to hang

**Diagnosis**:

```bash
# Test geometry validity
docker-compose exec tsird-etl python << 'EOF'
import geopandas as gpd
layer = gpd.read_file('/work/data/gold/atlas_4326/ethiopia/TroublesomeLayer.shp')
print(f'Valid: {layer.geometry.is_valid.sum()}/{len(layer)}')
print(f'Valid ratio: {layer.geometry.is_valid.sum() / len(layer):.2%}')

# Try clipping manually to see exact error
mask = gpd.read_file('/work/data/gold/atlas_4326/_masks/tigray_boundary.shp')
try:
    clipped = gpd.clip(layer, mask.geometry.unary_union)
    print("Clipping succeeded")
except Exception as e:
    print(f"Clipping failed: {e}")
EOF
```

**Solutions**:

```bash
# Solution 1: Repair geometries before separation
docker-compose exec tsird-etl python << 'EOF'
import geopandas as gpd
from shapely.geometry import shape

layer = gpd.read_file('/work/data/gold/atlas_4326/ethiopia/TroublesomeLayer.shp')
# Repair geometries
layer['geometry'] = layer.geometry.buffer(0)
layer.to_file('/work/data/gold/atlas_4326/ethiopia/TroublesomeLayer.shp', driver='ESRI Shapefile')
print("Repaired and saved")
EOF

# Solution 2: Re-run separation
docker-compose exec tsird-etl python \
  /work/Docker\ Projects/TSIRD-Atlas-Data-Pipeline/scripts/separate_layers.py

# Solution 3: If still failing, force to ETHIOPIA_WIDE
# Add layer to classification_overrides.yml
nano /opt/tigrayinsights/apps/tsird/Docker\ Projects/TSIRD-Atlas-Data-Pipeline/config/classification_overrides.yml

# Add to ethiopia_force (skip clipping):
# ethiopia_force:
#   - TroublesomeLayer
```

---

### Problem #12-16: Container Startup Failures

(Condensed: Container-specific issues)

**Problem #13: MapServer Exit Code 1**
```bash
docker-compose logs tsird-mapserver | tail -50
# Check for: mapfile syntax error, missing /etc/mapserver/tsird.map, permission denied

# Solution: Verify mapfile and redeploy
docker cp /opt/tigrayinsights/apps/tsird/infra/mapserver/mapfiles/* tsird-mapserver:/etc/mapserver/
docker-compose restart tsird-mapserver
```

**Problem #14: PostgreSQL Health Check Fails**
```bash
docker-compose exec tsird-postgis pg_isready -U tsird -d tsird -h localhost
# If fails: Check .env vars, disk space, permissions

# Solution:
docker-compose restart tsird-postgis
sleep 10
docker-compose exec tsird-postgis psql -U tsird -d tsird -c "SELECT 1"
```

**Problem #15: ETL Container Can't Read Data**
```bash
docker-compose logs tsird-etl | grep -i "permission\|mount\|error"

# Solution: Fix volume permissions
sudo chown -R 1000:1000 /work/data
sudo chmod -R 755 /work/data
```

---

### Problem #17: Pipeline Produces No Output

**Symptom**: Pipeline runs (no errors) but gold/ folder remains empty

**Root Causes**:
- No raw .shp files found
- All layers quarantined (masking silent failures)
- Output path wrong or permissions prevent writing

**Diagnosis**:

```bash
# Check raw input
ls /work/data/raw/vectors/*.shp | wc -l
# If 0, raw data not loaded

# Check normalization report
cat /work/reports/audit/normalization_report.md
# Look for: Total layers processed, Gold vs Quarantine counts

# Check for silent writes to wrong location
find /work -name "*atlas_4326*" -type d 2>/dev/null

# Check disk space
df -h /work
```

**Solutions**:

```bash
# Solution 1: Load raw data
# Copy shapefiles to /work/data/raw/vectors/

# Solution 2: Check normalization report details
# If all quarantined, fix CRS overrides or encoding issues (see above)

# Solution 3: Run normalization in debug mode
docker-compose exec tsird-etl python << 'EOF'
import sys
sys.path.insert(0, '/work/Docker Projects/TSIRD-Atlas-Data-Pipeline')
from scripts.normalize_to_gold_4326 import *

# Add debug prints
shp_files = sorted(VECTORS_RAW_ROOT.rglob("*.shp"))
print(f"Found {len(shp_files)} shapefiles")
for shp in shp_files[:3]:
    print(f"  - {shp}")
EOF

# Solution 4: Ensure permissions for output
chmod 777 /work/data/gold/
```

---

## Lessons Learned: Error Prevention

### Lesson 1: Wrong Layer Names in OGR DATA Field

**What Happened**: MapServer tried to read layer named `ethio_wereda_4326_fixed` from shapefile, but actual layer name is `ethio_wereda`

**Symptom**: Tiny error PNG (~500 bytes) from GetMap

**Why It Happened**: 
- During early pipeline iterations, intermediate layers were renamed with suffixes
- Mapfile was not updated with actual layer names
- No validation that OGR layer names matched shapefile contents

**Prevention**:
- Auto-validate mapfile by comparing DATA names to actual gdf layer names
- Store a manifest of actual layer names post-separation
- Use consistent naming convention (no suffixes in gold output)

---

### Lesson 2: Conflicting PROJECTION Blocks

**What Happened**: Layer-level PROJECTION block claimed EPSG:20137 (old UTM), but data was EPSG:4326

**Symptom**: Massive coordinate shift (e.g., 5.7° instead of 570,000m); features far outside map

**Why It Happened**: 
- Stale mapfile from earlier project phase
- Layer-level PROJECTION intended to override MAP PROJECTION (but wrong)
- No validation that layer and MAP projections were consistent

**Prevention**:
- Remove all layer-level PROJECTION blocks when MAP is canonical EPSG:4326
- Document in mapfile: "All OGR layers are EPSG:4326 canonical; MAP projection handles reprojection"
- Validate that all layers in same CRS before exposing via WMS

---

### Lesson 3: Missing SYMBOL Definitions for Points

**What Happened**: Point layers had `STYLE { SYMBOL 0 ... }` but no SYMBOL definitions registered in MAP

**Symptom**: Point layers visible in GetCapabilities, GetMap returns real PNG, but no visible points

**Why It Happened**: 
- SYMBOL definitions were not migrated from old mapfile template
- No validation that referenced SYMBOLs were registered
- Test coverage didn't include point layer rendering

**Prevention**:
- Create reusable SYMBOL library in MAP block (circle, square, triangle, etc.)
- Validate all referenced SYMBOLs exist before serving WMS
- Test rendering of all layer types (point, line, polygon) in CI/CD

---

### Lesson 4: Encoding Issues Silent in Python

**What Happened**: Shapefile DBF header is Latin1; Python read attempt fails with UnicodeDecodeError

**Symptom**: Layer quarantined with encoding error; operator doesn't know why

**Why It Happened**: 
- No pre-check for encoding before reading
- Script tried UTF-8 then failed, but didn't try Latin1 fallback

**Prevention**:
- Implement fallback encodings (UTF-8 → Latin1 → CP1252 → hex dump)
- Run audit script as first stage to flag encoding issues early
- Document source data encoding together with CRS

---

### Lesson 5: Quarantine Copying Forgetting Sidecars

**What Happened**: Failed layer copied to quarantine, but only .shp file; .dbf, .shx, .prj missing

**Symptom**: Operator reviews quarantine, tries to read layer, fails (incomplete shapefile)

**Why It Happened**: 
- Script used os.copy() instead of glob + copy all sidecar files
- No validation that all 5+ required shapefile components were copied

**Prevention**:
- Use glob pattern `layer_name.*` to copy all components
- Validate copied files include: .shp, .shx, .dbf, .prj, .cpg (if present)
- Create quarantine manifest JSON listing all copied files

---

### Lesson 6: Pipeline Re-runs Not Idempotent

**What Happened**: Second run of separate_layers.py creates duplicate folders (eth- iopia, ethiopia_duplicate, etc.)

**Why It Happened**: 
- Output directories not cleaned before run
- No validation that output didn't already exist

**Prevention**:
- Always clean output folder at start of pipeline stage (or use tmpdir strategy)
- Document idempotency expectations
- Test re-runs as part of CI/CD

---

## Terminal Debugging Commands

**Comprehensive command reference for rapid troubleshooting:**

```bash
# ============ CONTAINER STATUS ============

# Show all containers with status
docker-compose ps

# Show specific container health
docker-compose exec tsird-mapserver curl -fs http://localhost:8000/?SERVICE=WMS&REQUEST=GetCapabilities

# Check container resource usage
docker stats --no-stream

# ============ MAPSERVER DIAGNOSTICS ============

# Test WMS GetCapabilities
curl -s "http://localhost:7080/map/ogc?SERVICE=WMS&REQUEST=GetCapabilities" | head -30

# Count layers in response
curl -s "http://localhost:7080/map/ogc?SERVICE=WMS&REQUEST=GetCapabilities" | grep -o '<wms:Layer' | wc -l

# Test GetMap (single layer)
curl -s "http://localhost:7080/map/ogc?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetMap&\
  CRS=EPSG:4326&BBOX=33,3,48,15&WIDTH=800&HEIGHT=600&\
  LAYERS=ethiopia_woredas&FORMAT=image/png" > /tmp/test.png && file /tmp/test.png

# Check PNG size (indicates error)
curl -s "http://localhost:7080/map/ogc?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetMap&\
  CRS=EPSG:4326&BBOX=33,3,48,15&WIDTH=800&HEIGHT=600&\
  LAYERS=ethiopia_woredas&FORMAT=image/png" | wc -c

# MapServer debug output
docker-compose exec tsird-mapserver bash -c \
  'MS_DEBUGLEVEL=5 mapserv QUERY_STRING="map=/etc/mapserver/tsird.map&\
   SERVICE=WMS&REQUEST=GetMap&CRS=EPSG:4326&BBOX=33,3,48,15&WIDTH=800&HEIGHT=600&\
   LAYERS=ethiopia_woredas&FORMAT=image/png" 2>&1 | head -100'

# ============ DATA DIAGNOSTICS ============

# Check gold folder structure
ls -lah /work/data/gold/atlas_4326/

# Count layers by type
ls /work/data/gold/tigray/*.shp | wc -l
ls /work/data/gold/ethiopia/*.shp | wc -l

# Inspect shapefile with Python
docker-compose exec tsird-etl python -c "
import geopandas as gpd
gdf = gpd.read_file('/work/data/gold/atlas_4326/ethiopia/ethio_wereda.shp')
print(f'Features: {len(gdf)}')
print(f'Bounds: {gdf.total_bounds}')
print(f'CRS: {gdf.crs}')
print(f'Geometry types: {set(gdf.geom_type)}')
print(f'Valid: {gdf.geometry.is_valid.sum()}/{len(gdf)}')
"

# ============ PIPELINE REPORTS ============

# Show recent pipeline status
cat /work/reports/audit/normalization_report.md

# Count GOLD vs QUARANTINE
grep "status" /work/reports/audit/normalization_report.csv | sort | uniq -c

# List quarantined layers
ls /work/data/normalized/quarantine/

# ============ DATABASE ============

# PostgreSQL health
docker-compose exec tsird-postgis pg_isready -U tsird

# Check PostGIS version
docker-compose exec tsird-postgis psql -U tsird -d tsird -c "SELECT PostGIS_Version();"

# ============ LOGS ============

# Tail MapServer logs
docker-compose logs tsird-mapserver -f --tail=50

# Search logs for errors
docker-compose logs | grep -i "error\|failed\|permission"

# Save logs to file
docker-compose logs > /tmp/tsird_logs_$(date +%Y%m%d_%H%M%S).txt

# ============ FILE/PERMISSION ============

# Check data directory ownership
ls -la /work/data/ | head -20

# Fix permissions
sudo chown -R 1000:1000 /work/data
sudo chmod -R 755 /work/data

# Verify shapefile components exist
ls -la /work/data/gold/atlas_4326/ethiopia/ethio_wereda.*
```

---

## Recovery Procedures

### Full System Reset

```bash
# If everything is broken and you need to start fresh:

# 1. Back up current state (if possible)
tar -czf /backups/tsird_broken_$(date +%Y%m%d_%H%M%S).tar.gz \
  /work/data /work/reports /opt/tigrayinsights/apps/tsird/infra/mapserver

# 2. Stop and remove containers (keeps data volumes)
docker-compose stop
docker-compose rm -f

# 3. Restart from scratch
docker-compose up -d

# 4. Re-run full pipeline
docker-compose exec tsird-etl bash -c \
  'cd /work/Docker\ Projects/TSIRD-Atlas-Data-Pipeline && \
   python scripts/raw_inventory_audit.py && \
   python scripts/normalize_to_gold_4326.py && \
   python scripts/separate_layers.py'

# 5. Validate
curl -s "http://localhost:7080/map/health" | jq .
```

### Database Reset (Danger!)

```bash
# ONLY if PostGIS is corrupted and other attempts failed

# 1. Stop db
docker-compose stop tsird-postgis

# 2. Remove volume (WARNING: deletes all data!)
docker volume rm tsird-pgdata

# 3. Start fresh
docker-compose up -d tsird-postgis

# 4. Re-initialize with init scripts
docker-compose exec tsird-postgis bash /docker-entrypoint-initdb.d/01-init.sql

# 5. Reload gold layers (if needed)
docker-compose exec tsird-etl python \
  /work/Docker\ Projects/TSIRD-Atlas-Data-Pipeline/scripts/normalize_to_gold_4326.py
```

