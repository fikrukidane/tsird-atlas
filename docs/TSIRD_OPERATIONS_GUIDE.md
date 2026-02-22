# TSIRD Atlas Data Engineering: Operations Guide

**Version**: 1.0  
**Date**: 2026-02-21  
**Audience**: DevOps, GIS Data Stewards, ETL Operators

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Running the Pipeline](#running-the-pipeline)
3. [Monitoring & Health Checks](#monitoring--health-checks)
4. [Common Operations](#common-operations)
5. [Log Inspection](#log-inspection)
6. [Troubleshooting](#troubleshooting)

---

## Quick Start

### Prerequisites

- Docker + Docker Compose
- Host Nginx configured for `lab.tigrayinsights.net/map`
- `.env.tsird` with credentials
- Raw data in `/work/data/raw/vectors/`

### Environment Setup

**File**: `.env.tsird` (in `/opt/tigrayinsights/apps/tsird`)

```bash
# PostgreSQL
POSTGRES_DB=tsird
POSTGRES_USER=tsird
POSTGRES_PASSWORD=change_me_strong_password_here

# MapServer
MS_MAPFILE=/etc/mapserver/tsird.map

# TSIRD Edge Gateway
TSIRD_EDGE_PORT=7080  # localhost only

# Optional: Slack/email alerts
ALERT_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

### Verify Basic Setup

```bash
cd /opt/tigrayinsights/apps/tsird
docker-compose config --quiet
docker-compose up -d
docker-compose ps  # Expected: all "running"
curl http://localhost:7080/map/health  # Expected: {"status": "ok"}
```

---

## Running the Pipeline

### Full Pipeline Execution

```bash
# Enter ETL container
docker-compose exec tsird-etl bash

# Stage 1: Raw Inventory Audit
python /work/Docker\ Projects/TSIRD-Atlas-Data-Pipeline/scripts/raw_inventory_audit.py
# Output: audit_inventory.{csv,md}

# Stage 2: CRS Normalization
python /work/Docker\ Projects/TSIRD-Atlas-Data-Pipeline/scripts/normalize_to_gold_4326.py
# Output: gold/atlas_4326/, quarantine/, normalization_report.{csv,md}
# Check report: How many GOLD vs QUARANTINE?

# IF quarantined layers need fixing:
#   a. Review diagnostic JSON in quarantine/{layer_name}/
#   b. Add override to config/crs_overrides.yml or config/classification_overrides.yml
#   c. Re-run normalize_to_gold_4326.py (it will retry quarantined layers)

# 4. Run Stage 3: Regional Separation (Tigray vs Ethiopia-wide)
python /work/Docker\ Projects/TSIRD-Atlas-Data-Pipeline/scripts/separate_layers.py

# OUTPUTS:
# - /work/data/gold/tigray/ (clipped Tigray-only layers)
# - /work/data/gold/ethiopia/ (full-extent Ethiopia-wide layers)
# - /work/reports/separation/classification_report.csv
# - /work/reports/separation/classification_report.md

# Review: How many TIGRAY_ONLY vs ETHIOPIA_WIDE?
# Example: "18 TIGRAY_ONLY (clipped) | 22 ETHIOPIA_WIDE (full)"

# 5. Exit container
exit
```

### Single-Stage Execution (Debugging / Incremental)
# Stage 3: Regional Separation
python /work/Docker\ Projects/TSIRD-Atlas-Data-Pipeline/scripts/separate_layers.py
# Output: gold/tigray/, gold/ethiopia/, classification_report.{csv,md}

# Stage 4: Update MapServer
exit  # Exit container
docker cp /opt/tigrayinsights/apps/tsird/infra/mapserver/mapfiles/* tsird-mapserver:/etc/mapserver/
docker-compose restart tsird-mapserver
curl "http://localhost:7080/map/ogc?SERVICE=WMS&REQUEST=GetCapabilities" | grep -c "<Layer"
# Expected: 40+ layers
```

### Single-Stage Execution

```bash
# Rerun normalization only
docker-compose exec tsird-etl python /work/Docker\ Projects/TSIRD-Atlas-Data-Pipeline/scripts/normalize_to_gold_4326.py
```

---

## Monitoring & Health Checks

```bash
# Container status
docker-compose ps

# PostGIS
docker-compose exec tsird-postgis pg_isready -U tsird -d tsird

# MapServer layer count
curl -s "http://localhost:7080/map/ogc?SERVICE=WMS&REQUEST=GetCapabilities" | grep -c "<wms:Layer"
# Expected: >35

# MapServer GetMap test (check PNG size)
curl -s "http://localhost:7080/map/ogc?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetMap&CRS=EPSG:4326&BBOX=33,3,48,15&WIDTH=800&HEIGHT=600&LAYERS=ethiopia_woredas&FORMAT=image/png" | wc -c
# Expected: >40000 (not ~500)

# Health endpoint
curl -s http://localhost:7080/map/health | jq .

# Watch logs
docker-compose logs -f tsird-mapserver
```

---

## Common Operations

### Adding New Raw Data

**Scenario**: External team provides updated roads shapefile

```bash
# 1. Copy new .shp files to raw data directory
cp roads_updated.shp roads_updated.shx roads_updated.dbf \
  /work/data/raw/vectors/

# 2. Run full pipeline (audits old + new together)
docker-compose exec tsird-etl bash -c \
  'cd /work/Docker\ Projects/TSIRD-Atlas-Data-Pipeline && \
   python scripts/raw_inventory_audit.py && \
   python scripts/normalize_to_gold_4326.py && \
   python scripts/separate_layers.py'

# 3. Review reports to confirm new layer processed correctly
cat /work/reports/audit/normalization_report.md

# 4. Update MapServer (if necessary)
docker cp /opt/tigrayinsights/apps/tsird/infra/mapserver/mapfiles/* \
  tsird-mapserver:/etc/mapserver/
docker-compose restart tsird-mapserver

# 5. Validate
curl -s "http://localhost:7080/map/ogc?SERVICE=WMS&REQUEST=GetCapabilities" \
  | grep "roads_updated"  # Should find "roads_updated" in layer list
```

### Fixing a Quarantined Layer

**Scenario**: Layer failed validation; need to add CRS override and retry

```bash
# 1. Check what caused the quarantine
cat /work/data/normalized/quarantine/my_layer/diagnostics.json | jq .reason

# Example reason: "CRS_MISSING_NO_OVERRIDE"

# 2. Add override to crs_overrides.yml
nano /opt/tigrayinsights/apps/tsird/Docker\ Projects/TSIRD-Atlas-Data-Pipeline/config/crs_overrides.yml

# Add line:
# my_layer:
#   epsg: 32637   # Corrected CRS

# 3. Re-run normalization (it will retry all quarantined layers)
docker-compose exec tsird-etl python \
  /work/Docker\ Projects/TSIRD-Atlas-Data-Pipeline/scripts/normalize_to_gold_4326.py

# 4. Verify
grep "my_layer" /work/reports/audit/normalization_report.csv | grep "GOLD"
# Should show status = GOLD now
```

### Forcing a Layer to Tigray-Only Classification

**Scenario**: Layer crosses boundary but should be Tigray-focused

```bash
# 1. Edit classification overrides
nano /opt/tigrayinsights/apps/tsird/Docker\ Projects/TSIRD-Atlas-Data-Pipeline/config/classification_overrides.yml

# Add line (ensure YAML indent is exactly 2 spaces):
# tigray_force:
#   - MyTigrayLayer
#   - AnotherTigrayLayer

# 2. Re-run separation
docker-compose exec tsird-etl python \
  /work/Docker\ Projects/TSIRD-Atlas-Data-Pipeline/scripts/separate_layers.py

# 3. Verify
ls /work/data/gold/tigray/ | grep MyTigrayLayer
# Should see MyTigrayLayer.shp in tigray/ folder
```

### Manually Trigger Full WMS Restart

```bash
# Restart MapServer (reloads all mapfiles without losing data)
docker-compose restart tsird-mapserver

# Wait for healthy
sleep 5
docker-compose exec tsird-mapserver curl -fs \
  "http://localhost/?map=/etc/mapserver/tsird.map&SERVICE=WMS&REQUEST=GetCapabilities" \
  > /dev/null && echo "MapServer ready" || echo "MapServer failed"
```

### Export Layer to GeoJSON (WFS)

```bash
# Get all features from a layer as GeoJSON
curl -s "http://localhost:7080/map/ogc?\
  SERVICE=WFS&VERSION=2.0.0&REQUEST=GetFeature&\
  TYPENAME=ts:ethiopia_woredas&\
  OUTPUTFORMAT=application/json" \
  > ethiopia_woredas.geojson

# Use QGIS or other tools to analyze the GeoJSON file
```

---

## Log Inspection

### Pipeline Execution Logs

```bash
# Stage 1 output (audit)
cat /work/reports/audit/audit_inventory.md

# Stage 2 output (normalization)
cat /work/reports/audit/normalization_report.md
# Key metrics: How many GOLD? Why quarantined?

# Stage 3 output (separation)
cat /work/reports/separation/classification_report.md
# Key metrics: Tigray vs Ethiopia split
```

### Container Application Logs

```bash
# PostgreSQL
docker-compose logs tsird-postgis --tail=100

# MapServer (verbose CRS + OGR debug info)
docker-compose logs tsird-mapserver --tail=100 | grep -E "ERROR|CRS|OGR"

# ETL container (Python output)
docker-compose logs tsird-etl --tail=50

# Edge gateway (routing info)
docker-compose logs tsird-edge --tail=50
```

### MapServer Diagnostic Query

```bash
# Enable debug logging and test a layer
docker-compose exec tsird-mapserver bash -c \
  'MS_DEBUGLEVEL=5 mapserv QUERY_STRING="map=/etc/mapserver/tsird.map&\
   SERVICE=WMS&REQUEST=GetMap&\
   CRS=EPSG:4326&BBOX=33,3,48,15&WIDTH=800&HEIGHT=600&\
   LAYERS=ethiopia_woredas&FORMAT=image/png" 2>&1 | head -50'

# Look for:
# - "msOGRFileOpen succeeded" → File found ✓
# - "msOGRFileOpen failed" → File not found ✗
# - "Projection" → CRS applied ✓
# - "shapes" count → Number of features loaded
```

---

## Troubleshooting

### Problem: "QGIS connects to WMS but layers blank"

**Diagnosis**:

```bash
# 1. Check GetCapabilities
curl -s "http://localhost:7080/map/ogc?SERVICE=WMS&REQUEST=GetCapabilities" \
  | head -20

# 2. If tiny response (< 5KB) → Mapfile error
docker-compose logs tsird-mapserver | tail -50

# 3. If 30KB+ response → Capabilities OK, check GetMap
curl -s "http://localhost:7080/map/ogc?SERVICE=WMS&VERSION=1.3.0&\
  REQUEST=GetMap&CRS=EPSG:4326&BBOX=33,3,48,15&WIDTH=800&HEIGHT=600&\
  LAYERS=ethiopia_woredas&FORMAT=image/png" | wc -c

# 4. If < 1000 bytes → Error image, not real PNG
#    Likely: Wrong DATA path or PROJECTION conflict
```

**Resolution**:

```bash
# Re-check includes/vectors_gold.map for errors
grep -n "ethiopia_woredas" /opt/tigrayinsights/apps/tsird/infra/mapserver/mapfiles/includes/vectors_gold.map

# Verify DATA path matches actual gold folder structure
ls -la /work/data/gold/atlas_4326/ethiopia/ | grep ethio_wereda

# If path wrong, edit mapfile:
# OLD: DATA "ethio_wereda_4326_fixed"
# NEW: DATA "ethiopia/ethio_wereda"

# Restart and retest
docker-compose restart tsird-mapserver
sleep 3
docker cp /opt/tigrayinsights/apps/tsird/infra/mapserver/mapfiles/* tsird-mapserver:/etc/mapserver/
```

---

### Problem: "normalize_to_gold_4326.py crashes with encoding error"

**Error Message**: `UnicodeDecodeError: 'utf-8' codec can't decode bytes...`

**Cause**: Shapefile DBF header uses non-UTF-8 encoding (Latin1, CP1252, etc.)

**Resolution**:

```bash
# The script already tries UTF-8 then Latin1 fallback
# If it still fails, the encoding is unknown

# Option 1: Use iconv to convert the DBF file
iconv -f CP1252 -t UTF-8 /work/data/raw/vectors/problem_layer.dbf \
  > /work/data/raw/vectors/problem_layer_utf8.dbf

# Rename and retry
mv /work/data/raw/vectors/problem_layer.dbf \
  /work/data/raw/vectors/problem_layer_backup.dbf
mv /work/data/raw/vectors/problem_layer_utf8.dbf \
  /work/data/raw/vectors/problem_layer.dbf

# Re-run normalization
docker-compose exec tsird-etl python \
  /work/Docker\ Projects/TSIRD-Atlas-Data-Pipeline/scripts/normalize_to_gold_4326.py
```

---

### Problem: "Point layers not visible in MapServer"

**Symptom**: QGIS can see point layers in WMS capabilities, but they don't render (blank space)

**Cause**: SYMBOL definitions missing in mapfile

**Resolution**:

```bash
# 1. Check if SYMBOL definitions exist
grep "SYMBOL" /opt/tigrayinsights/apps/tsird/infra/mapserver/mapfiles/tsird.map

# 2. If no "circle" or "square", add them to tsird.map
# In the MAP block, after PROJECTION and before INCLUDE, add:

cat >> /opt/tigrayinsights/apps/tsird/infra/mapserver/mapfiles/tsird.map << 'EOF'

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
EOF

# 3. In includes/vectors_gold.map, update point layer STYLE blocks:
# OLD: SYMBOL 0
# NEW: SYMBOL "circle"

# 4. Deploy and restart
docker cp /opt/tigrayinsights/apps/tsird/infra/mapserver/mapfiles/* tsird-mapserver:/etc/mapserver/
docker-compose restart tsird-mapserver

# 5. Test
curl -s "http://localhost:7080/map/ogc?SERVICE=WMS&VERSION=1.3.0&\
  REQUEST=GetMap&CRS=EPSG:4326&BBOX=12,36,15,40&WIDTH=800&HEIGHT=600&\
  LAYERS=tigray_towns&FORMAT=image/png" | wc -c
# Should now be ~30KB (real PNG), not ~500 bytes
```

---

### Problem: "GOLD folder is empty, pipeline produces no output"

**Cause**: Raw data wasn't discovered, or all layers quarantined

**Resolution**:

```bash
# 1. Check raw directory
ls -la /work/data/raw/vectors/*.shp | wc -l

# If 0 files:
#   → Copy raw data and re-run audit
#   → Ensure mount is correct in docker-compose.yml

# If files exist:
#   → Check audit report
cat /work/reports/audit/normalization_report.md

# If all quarantined, review reasons:
cat /work/reports/audit/normalization_report.csv | grep "QUARANTINE"

# Fix issues via crs_overrides.yml and retry
```

---

### Problem: "Getting permission denied errors in container"

**Symptom**: `Permission denied: '/work/data/gold/atlas_4326/...`

**Cause**: Volume ownership mismatch (container UID ≠ host UID)

**Resolution**:

```bash
# 1. Check current permissions
ls -la /work/data/gold/

# 2. Fix ownership (use host UID 1000 if typical dev, or root 0)
sudo chown -R 1000:1000 /work/data/

# 3. Ensure read+write for everyone in group
sudo chmod -R 755 /work/data/raw/
sudo chmod -R 755 /work/data/gold/
sudo chmod -R 755 /work/data/normalized/

# 4. Restart containers
docker-compose restart tsird-etl

# 5. Retry pipeline
docker-compose exec tsird-etl python \
  /work/Docker\ Projects/TSIRD-Atlas-Data-Pipeline/scripts/normalize_to_gold_4326.py
```

---

## Backup & Recovery

### Backup Gold Layer Data

```bash
# Snapshot current gold outputs
tar -czf /backups/tsird_gold_$(date +%Y%m%d_%H%M%S).tar.gz \
  /work/data/gold/atlas_4326/

# Backup pipeline reports
tar -czf /backups/tsird_reports_$(date +%Y%m%d_%H%M%S).tar.gz \
  /work/reports/

# Backup mapfile configuration
tar -czf /backups/tsird_mapfiles_$(date +%Y%m%d_%H%M%S).tar.gz \
  /opt/tigrayinsights/apps/tsird/infra/mapserver/

# Store in safe location (NAS, cloud storage, etc.)
```

### Restore from Backup

```bash
# Extract gold layers
tar -xzf /backups/tsird_gold_YYYYMMDD_HHMMSS.tar.gz -C /

# Extract reports
tar -xzf /backups/tsird_reports_YYYYMMDD_HHMMSS.tar.gz -C /

# Extract mapfiles
tar -xzf /backups/tsird_mapfiles_YYYYMMDD_HHMMSS.tar.gz -C /

# Restart MapServer to reload
docker-compose restart tsird-mapserver

# Verify WMS
curl -s "http://localhost:7080/map/ogc?SERVICE=WMS&REQUEST=GetCapabilities" \
  | grep -c <wms:Layer
```

---

## Runbook Summary

### Daily Check (5 min)

```bash
docker-compose ps  # All healthy?
curl http://localhost:7080/map/health | jq .  # All green?
```

### Weekly Full Test (15 min)

```bash
# Test WMS rendering
curl -s "http://localhost:7080/map/ogc?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetMap&\
  CRS=EPSG:4326&BBOX=33,3,48,15&WIDTH=800&HEIGHT=600&\
  LAYERS=ethiopia_woredas,tigray_schools_2006&FORMAT=image/png" \
  > /tmp/test_render.png
file /tmp/test_render.png  # Should be PNG image
```

### Monthly Full Audit (1 hour)

```bash
# Re-run entire pipeline
docker-compose exec tsird-etl bash -c \
  'cd /work/Docker\ Projects/TSIRD-Atlas-Data-Pipeline && \
   python scripts/raw_inventory_audit.py && \
   python scripts/normalize_to_gold_4326.py && \
   python scripts/separate_layers.py'

# Review reports for anomalies
cat /work/reports/audit/normalization_report.md

# Backup current state
tar -czf /backups/tsird_full_$(date +%Y%m%d).tar.gz \
  /work/data/gold /work/reports /opt/tigrayinsights/apps/tsird/infra/mapserver
```

