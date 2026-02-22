# TSIRD Atlas Data Engineering Pipeline: Comprehensive Architecture

**Version:** 1.0  
**Date:** 2026-02-21  
**Status:** Production  
**Audience:** GIS Engineers, Data Engineers, DevOps, Future Maintainers

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture Principles](#architecture-principles)
3. [High-Level Data Flow](#high-level-data-flow)
4. [Directory Architecture](#directory-architecture)
5. [Docker Services](#docker-services)
6. [Pipeline Stages](#pipeline-stages)
7. [Data Quality Framework](#data-quality-framework)
8. [MapServer Integration](#mapserver-integration)

---

## System Overview

Production-grade geospatial ETL system that ingests raw vector/raster data, normalizes to EPSG:4326, separates by region, and exposes via OGC WMS/WFS.

**Key Characteristics:**
- **Reproducible**: Deterministic operations, logged decisions, no manual fixes
- **CRS-Safe**: Explicit overrides only; all outputs EPSG:4326
- **Geometry-Validated**: 98% validity threshold with automated repair/quarantine
- **Auditable**: CSV/Markdown reports at each stage
- **Self-Contained**: Docker-based; no host GIS dependencies
- **Regional Separation**: Ethiopia-wide vs Tigray-only classification with clipping

---

## Architecture Principles

### 1. **Separation of Concerns**

```
Data Storage          Pipeline Logic         MapServer Config       Audit/Reports
├── raw/              ├── scripts/            ├── mapfiles/          ├── csv
├── normalized/       ├── config/             ├── includes/          └── markdown
└── gold/             └── notebooks/          └── styles/
```

- **Data Storage** (`/work/data`): Immutable sources, finalized outputs
- **Pipeline Logic** (`/work/Docker Projects/TSIRD-Atlas-Data-Pipeline`): Scripts, configs, notebooks
- **MapServer Config** (`/opt/tigrayinsights/apps/tsird/infra/mapserver`): WMS mapfiles
- **Audit Outputs** (`reports/audit`): CSV/Markdown reports

### 2. **Quarantine Model**

Failed layers automatically quarantined with full diagnostics; prevents corrupted data from reaching production.

```
gold/atlas_4326/        ← Validated layers only
normalized/quarantine/  ← Failed layers + diagnostics
```

### 3. **CRS Canonicalization**

All outputs guaranteed EPSG:4326. Automatic reprojection; explicit overrides via YAML.

### 4. **No Manual Fixes**

All problems captured, logged, and auto-repaired or quarantined. Corrections require YAML config updates.

---

## High-Level Data Flow

```
┌──────────────────────────────────────────────────────────────────┐
│  EXTERNAL DATA SOURCES (raw/)                                    │
│  • Admin boundaries (bound01, bound02, bound03)                  │
│  • Woreda/Zone/Regions (ethio_wereda, Eth_Zones_New)             │
│  • Roads (TigrayRoadsIn2006, Ethio_roads)                        │
│  • Health facilities (TigrayHealth2006, ethiopia_hospitals)      │
│  • Towns/Cities (Tigray_Towns, ethiopia_towns)                   │
│  • Environmental (et-dtm-2001, et-slp-2001, isoheight, lakes)   │
│  • Landcover (Eth_ecology, soils)                                │
└──────────────────────────────────────────────────────────────────┘
                            │
                            ↓
        ┌───────────────────────────────────────┐
        │  STAGE 1: RAW INVENTORY AUDIT          │
        │  (raw_inventory_audit.py)              │
        │                                       │
        │  • Detect missing CRS                 │
        │  • Flag invalid geometry              │
        │  • Check bounds sanity                │
        │  • Report encoding issues             │
        │  → audit_inventory.csv/md             │
        └───────────────────────────────────────┘
                            │
                            ↓
        ┌───────────────────────────────────────┐
        │  STAGE 2: CRS NORMALIZATION            │
        │  (normalize_to_gold_4326.py)           │
        │                                       │
        │  • Load CRS overrides (YAML)          │
        │  • Reproject to EPSG:4326             │
        │  • Repair geometry (buffer(0))        │
        │  • Deduplicate columns                │
        │  • ✓ 98% validity → GOLD              │
        │  • ✗ <98% validity → QUARANTINE       │
        │  → normalization_report.csv/md        │
        └───────────────────────────────────────┘
                            │
                ┌───────────┴───────────┐
                ↓                       ↓
            GOLD             QUARANTINE
            ↓                ↓
    gold/atlas_4326/   normalized/quarantine/
    ├── ethiopia/      (forensics + copies
    ├── tigray/        of failed layers)
    ├── _masks/
    └── *.shp          
                            │
                            ↓
        ┌───────────────────────────────────────┐
        │  STAGE 3: REGIONAL SEPARATION          │
        │  (separate_layers.py)                  │
        │                                       │
        │  • Load tigray_boundary mask          │
        │  • Calculate intersection ratio       │
        │  • Apply classification overrides     │
        │  • Threshold: 0.95 coverage           │
        │  • Clip Tigray-only to boundary       │
        │  → classification report              │
        └───────────────────────────────────────┘
                            │
                ┌───────────┴───────────┐
                ↓                       ↓
           TIGRAY_ONLY         ETHIOPIA_WIDE
           ↓                   ↓
        gold/tigray/      gold/ethiopia/
        (clipped)         (whole country)
                            │
                            ↓
        ┌───────────────────────────────────────┐
        │  STAGE 4: MAPSERVER INTEGRATION        │
        │                                       │
        │  • Generate OGR layer configs         │
        │    (auto from separate_layers report) │
        │  • Expose via tsird.map               │
        │  • WMS/WFS capabilities computed      │
        │  • GetCapabilities + GetMap testing   │
        └───────────────────────────────────────┘
                            │
                            ↓
        ┌───────────────────────────────────────┐
        │  WMS SERVICE (MapServer)               │
        │  https://lab.tigrayinsights.net/map/  │
        │                                       │
        │  → GetCapabilities (layer listing)    │
        │  → GetMap (PNG/GeoTIFF rendering)     │
        │  → GetFeatureInfo (attribute queries) │
        │  → WFS (GeoJSON/GML download)         │
        └───────────────────────────────────────┘
                            │
                            ↓
        ┌───────────────────────────────────────┐
        │  WEB/GIS CLIENT (QGIS, Leaflet, etc.) │
        │  Visualizes and analyzes data         │
        └───────────────────────────────────────┘
```

---

## Directory Architecture

### Root Level: `/work/data`

```
/work/data/
├── raw/                        ← Source of truth (read-only after initial load)
│   ├── vectors/                ← Raw shapefiles from external sources
│   │   ├── bound01.shp
│   │   ├── ethio_wereda.shp
│   │   ├── TigrayRoadsIn2006.shp
│   │   ├── et-dtm-2001.tif    ← Raster DEM
│   │   └── ...
│   ├── rasters/                ← All rasters (DEMs, slopes, indices)
│   └── _metadata/              ← Source provenance docs
│
├── normalized/                 ← Intermediate processing state
│   ├── quarantine/             ← Rejected layers (failed validation)
│   │   ├── BadLayer1/          ← Each failed layer in own folder
│   │   │   ├── BadLayer1.shp   ← Copy of raw files
│   │   │   ├── BadLayer1.shx
│   │   │   └── BadLayer1.dbf
│   │   └── BadLayer2/
│   │
│   └── _temp/                  ← Scratch space (cleaned between runs)
│
└── gold/                        ← Canon output (read by MapServer)
    └── atlas_4326/             ← EPSG:4326 canonical layer set
        ├── _masks/             ← Clipping geometries
        │   ├── tigray_boundary.shp
        │   └── bound03.shp     ← Why not used for separation (see rationale)
        │
        ├── ethiopia/           ← Ethiopia-wide layers (no clip)
        │   ├── ethio_wereda.shp
        │   ├── Eth_Zones_New.shp
        │   ├── ethio_roads.shp
        │   ├── ethiopia_boundary_level2.shp
        │   └── ... 20+ additional layers
        │
        └── tigray/             ← Tigray-only layers (clipped)
            ├── TigrayRoadsIn2006.shp    ← Clipped to tigray_boundary
            ├── TigrayHealth2006.shp
            ├── Tigray_Towns.shp
            ├── TigraiTabiasNew.shp
            └── ... additional Tigray-specific layers
```

### Pipeline Project: `/work/Docker Projects/TSIRD-Atlas-Data-Pipeline`

```
TSIRD-Atlas-Data-Pipeline/
├── config/
│   ├── __init__.py
│   ├── paths.py                ← Architectural constants (immutable paths)
│   ├── crs_override_loader.py  ← Load CRS YAML, return override dict
│   ├── crs_overrides.yml       ← CRS assignments (e.g., layer → EPSG)
│   │   └── Example:
│   │       overrides:
│   │         TigrayRoadsIn2006:
│   │           epsg: 32637       # UTM 37N (actual source CRS)
│   │         ethio_wereda:
│   │           epsg: 20137       # Adindan UTM 37N
│   │
│   └── classification_overrides.yml ← Force regional assignment
│       └── Example:
│           tigray_force:            # Always TIGRAY_ONLY if present
│             - TigraiTabiasNew
│           ethiopia_force: []       # (for future overrides)
│
├── scripts/
│   ├── raw_inventory_audit.py      ← STAGE 1: Structural audit
│   ├── normalize_to_gold_4326.py    ← STAGE 2: CRS + geometry fix
│   └── separate_layers.py           ← STAGE 3: Regional split
│
├── notebooks/                       ← Interactive analysis / dry-runs
│   └── (exploratory only; not part of pipeline)
│
└── reports/
    ├── audit/
    │   ├── audit_inventory.csv      ← Raw layer metadata
    │   ├── audit_inventory.md       ← Human-readable summary
    │   ├── normalization_report.csv ← CRS fix results
    │   └── normalization_report.md  ← Status per layer
    │
    └── separation/
        ├── classification_report.csv ← Ethiopia vs Tigray split
        └── classification_report.md
```

### MapServer Config: `/opt/tigrayinsights/apps/tsird/infra/mapserver`

```
mapserver/
└── mapfiles/
    ├── tsird.map                    ← Main WMS mapfile
    │   ├── MAP block (EXTENT, CRS, WEB)
    │   ├── SYMBOL definitions ("circle", "square" for point layers)
    │   ├── LAYER definitions (PostGIS, OGR, Raster)
    │   └── INCLUDE "includes/vectors_gold.map"
    │
    └── includes/
        └── vectors_gold.map         ← Auto-generated or manual
            ├── ~40 OGR LAYER blocks
            ├── Each layer:
            │   ├── DATA "path/to/gold/tigray/LayerName.shp"
            │   ├── EPSG:4326 PROJECTION (inherited from MAP)
            │   ├── CLASS/STYLE definitions
            │   └── METADATA (wms_title, wms_srs, etc.)
            │
            └── SYMBOL definitions for all point layers
```

---

## Docker Services

### Service: `tsird-postgis`

**Image**: `postgis/postgis:16-3.4`  
**Purpose**: Vector storage and derived tables  
**Volumes**: `tsird-pgdata` (persistent), `./db/init` (init scripts)  
**Health Check**: `pg_isready -U $POSTGRES_USER -d $POSTGRES_DB`  
**Network**: Internal only (`tsird-network`)

---

### Service: `tsird-mapserver`

**Image**: `camptocamp/mapserver:8.6.0`  
**Purpose**: OGC WMS/WFS endpoint  
**Volumes**: `./infra/mapserver/mapfiles`, `./data` (read-only)  
**Environment**: `MS_DEBUGLEVEL=5`, `MS_ERRORFILE=stderr`, `CPL_DEBUG=ON`  
**Health Check**: `curl GetCapabilities && grep WMS_Capabilities`  
**Network**: Internal only; proxied via `tsird-edge`

---

### Service: `tsird-web`

**Image**: Built from `./ui/web/Dockerfile`  
**Purpose**: Web viewer/dashboard  
**Ports**: `8080` internal

---

### Service: `tsird-etl`

**Image**: Built from `./etl/Dockerfile`  
**Purpose**: Execute pipeline scripts  
**Volumes**: `./data` (read/write)  
**Health Check**: `etl_healthcheck.sh` (DB + data dir access)  
**Execution**: Idle container; manual/orchestrated trigger

---

### Service: `tsird-edge`

**Image**: Built from `./infra/edge/Dockerfile`  
**Purpose**: Internal routing gateway  
**Ports**: `127.0.0.1:${TSIRD_EDGE_PORT}:8080` (localhost only)  
**Routing**: `/map/` → web, `/map/ogc` → mapserver, `/map/health` → aggregated status  
**Network**: `tsird-network`

---

## Pipeline Stages

### Stage 1: Raw Inventory Audit

**Script**: `raw_inventory_audit.py`  
**Input**: All `.shp` files in `/work/data/raw/vectors/`  
**Output**: `reports/audit/audit_inventory.{csv,md}`

**Purpose**: Structural inspection before processing; detect problems early.

**Checks Performed**:

| Check | Detects | Action |
|-------|---------|--------|
| **Read Success** | File corruption, encoding issues | Report error; mark for investigation |
| **CRS Presence** | Missing CRS declaration | Report; may auto-assign if bounds suggest 4326 |
| **CRS Validity** | Invalid EPSG codes | Flag in report |
| **Bounds Sanity** | Out-of-range coordinates for claimed CRS | INVERTED_BOUNDS, OUT_OF_RANGE_FOR_4326, ABSURD_MAGNITUDE |
| **Geometry Validity** | Invalid/empty/degenerate geometries | Report % valid; sample invalid reason |
| **Geometry Types** | Mixed or unexpected types | Report (e.g., "Polygon\|LineString") |
| **Feature Count** | Empty layers | Flag for quarantine consideration |
| **Column Duplication** | Shapefile DBF header issues | Report rename operations needed |
| **Z Coordinates** | 3D geometries (not typically needed) | Flag for reduction if present |

**Audit Report Example**:
```
path,layer_name,read_ok,error_type,crs_epsg,bounds_flag,valid_geom_ratio,columns
/data/raw/vectors/ethio_wereda.shp,ethio_wereda,True,,20137,,0.98,"[... 15 column names ...]"
/data/raw/vectors/bad_layer.shp,bad_layer,False,GDALError,,,,"[UnicodeDecodeError: UTF-8]"
```

**Output Statistics**:
- Total layers inventoried
- Read failures (by error type)
- CRS distribution (EPSG codes found)
- Geometry validity percentiles
- Encoding issues (UTF-8, Latin1, failures)

---

### Stage 2: CRS Normalization to EPSG:4326

**Script**: `normalize_to_gold_4326.py`  
**Input**: `raw/vectors/*.shp`, `crs_overrides.yml`  
**Output**: GOLD (`gold/atlas_4326/`), QUARANTINE (`normalized/quarantine/`), reports

**Workflow**: Read → Assign CRS (override/declared/auto-detect) → Reproject → Validate bounds → Repair geometry (buffer(0) → make_valid) → Dedupe columns → Write GOLD or QUARANTINE

**Threshold**: ≥98% valid geometries required for GOLD status.

---

### Stage 3: Regional Separation (Tigray vs Ethiopia-Wide)

**Script**: `separate_layers.py`  
**Input**: GOLD layers (`gold/atlas_4326/`), clipping mask, `classification_overrides.yml`  
**Output**: `gold/tigray/` (clipped), `gold/ethiopia/` (full extent), reports

**Logic**: Check overrides → Compute intersection ratio (0.95 threshold) → Classify as TIGRAY_ONLY or ETHIOPIA_WIDE → Clip or copy accordingly

**Ratio Calculation**: POLYGON (area), LINESTRING (length), POINT (count) intersection with Tigray boundary in metric CRS (EPSG:32637).

**Classification Logic**:

```
For each GOLD layer:
  
  1. Check classification_overrides.yml
     ├─ If layer in tigray_force → TIGRAY_ONLY (skip threshold check)
     └─ Else if layer in ethiopia_force → ETHIOPIA_WIDE (skip threshold check)
  
  2. If not overridden, compute intersection ratio
     ├─ Reproject layer + mask to EPSG:32637 (metric CRS, UTM)
     ├─ Calculate coverage:
     │  ├─ If POLYGON: area_inside / area_total
     │  ├─ If LINESTRING: length_inside / length_total
     │  └─ If POINT: count_inside / count_total
     ├─ Compare ratio to threshold (0.95)
     └─ Decision:
        ├─ ratio ≥ 0.95 → TIGRAY_ONLY (clip to boundary)
        └─ ratio < 0.95 → ETHIOPIA_WIDE (keep as-is)
  
  3. Write output
     ├─ TIGRAY_ONLY: Clip geometries to mask, write to gold/tigray/
     └─ ETHIOPIA_WIDE: Copy to gold/ethiopia/
```

**Why Threshold = 0.95?**

This balance:
- **0.95 threshold**: Captures layers with 95%+ content inside Tigray (high confidence)
- **Higher (0.99)**: Risks missing Tigray-heavy layers that cross boundary
- **Lower (0.90)**: Creates false positives (e.g., country-wide roads that happen to pass through Tigray)

**Why bound03 is not used for separation**:

`bound03` is a _single regional boundary polygon_ used in early prototypes. However:
- It lacks administrative hierarchy (woredas, tabia, kebeles)
- `tigray_boundary` is explicitly derived from verified administrative sources
- Mask-based separation is cleaner than hardcoded regional polygon logic

**Classification Overrides Rationale**:

Some layers are obviously Tigray or Ethiopia-wide without needing threshold calculation:
- `TigraiTabiasNew` → Explicitly Tigray tabias → force TIGRAY_ONLY
- (Future): If a country-wide layer accidentally reads as 96% inside Tigray due to clipping issues → force ETHIOPIA_WIDE

**Output Summary Example**:

```
Total layers in gold/: 42
TIGRAY_ONLY: 18
  ├─ TigrayRoadsIn2006 (ratio: 0.99, metric: length)
  ├─ TigrayHealth2006 (ratio: 0.98, metric: point count)
  ├─ Tigray_Towns (ratio: 0.97, metric: point count)
  └─ ... 15 more
  
ETHIOPIA_WIDE: 24
  ├─ ethio_wereda (ratio: 0.23, metric: area - contains all woredas)
  ├─ ethio_roadsmain (ratio: 0.34, metric: length)
  ├─ ethiopia_hospitals (ratio: 0.42, metric: point count)
  └─ ... 21 more
```

---

### Stage 4: MapServer Integration

**Inputs**:
- Gold layers: `gold/atlas_4326/*.shp`
- Classification report: `classification_report.csv`
- Existing mapfile: `infra/mapserver/mapfiles/tsird.map`

**Outputs**:
- Updated mapfile: `includes/vectors_gold.map` (can be auto-generated or manually maintained)
- WMS service: `https://lab.tigrayinsights.net/map/ogc`

**MapFile Structure**:

```mapfile
MAP
  NAME "tsird"
  PROJECTI
    "init=epsg:4326"
  END
  
  SYMBOL
    NAME "circle"
    TYPE ELLIPSE
    POINTS 1 1 END
  END
  
  # For each GOLD layer:
  LAYER
    NAME "ethiopia_woredas"
    TYPE POLYGON
    STATUS ON
    CONNECTIONTYPE OGR
    CONNECTION "/data/gold/atlas_4326/"
    DATA "ethiopia/ethio_wereda"  ← Key: correct folder + layer name
    
    PROJECTION
      "init=epsg:4326"            ← Inherited from MAP, can be redundant
    END
    
    METADATA
      "wms_title" "Ethiopia - Woredas"
      "wms_srs" "EPSG:4326 EPSG:3857"
      "wms_enable_request" "*"
      "wms_queryable" "true"
      "wms_include_items" "column1,column2,column3"  ← For GetFeatureInfo
    END
    
    CLASS
      STYLE
        COLOR 200 100 50
        OUTLINECOLOR 0 0 0
        OUTLINEWIDTH 1
      END
    END
  END
  
  # ... 40+ layer definitions
END
```

**Why Incorrect PROJECTION blocks caused blank WMS**:

- Stale mapfiles had layer-level PROJECTION blocks with EPSG:20137 or EPSG:32637
- MapServer interpreted: "Layer is in UTM 37N; repro to MAP's EPSG:4326"
- Result: Massive coordinate shifts (e.g., 570000m → 5.7°); geometries far outside AOI
- GetMap returned empty raster (~542 byte error PNG)
- Solution: Remove all layer-level PROJECTION blocks; rely on MAP-level EPSG:4326

**WMS Capabilities**:

```
GetCapabilities → Lists all layers + supported SRS
GetMap           → Render PNG/GeoTIFF for bbox + layers
GetFeatureInfo   → Query attributes by pixel
WFS GetFeature   → Download GeoJSON/GML
```

---

## Data Quality Framework

### Validity Thresholds

| Metric | Threshold | Action if Below | Action if At/Above |
|--------|-----------|-----------------|-------------------|
| **Geometry Validity** | 98% | Repair (buffer→make_valid) | Pass to GOLD |
| **Regional Coverage** (Tigray) | 95% | Classify ETHIOPIA_WIDE | Classify TIGRAY_ONLY |
| **Bounds Sanity** | [-180,180] × [-90,90] for 4326 | Quarantine | Pass forward |

### Repair Operations

**Step 1: buffer(0)**
- Graceful fix for self-intersecting polygons
- Minimal geometry modification
- Fast; works for ~80% of invalidity issues

**Step 2: shapely.make_valid()**
- Stronger fix; may convert invalid ring to valid multipart
- Slower; only applied if buffer(0) insufficient
- Last attempted before quarantine

**Step 3: Quarantine**
- If valid ratio still < 98% post-repair, layer goes to quarantine
- Operator must review raw data and determine fix strategy

### Exception Tracking

Every stage produces a CSV report with:
- **layer_name**: Identifier for tracing
- **status**: GOLD | QUARANTINE | (in-progress)
- **reason**: Code explaining decision (CRS_MISSING, GEOM_INVALID, etc.)
- **error**: Full exception message (if applicable)
- **traceback**: Python traceback for debugging

---

## MapServer Integration

### OGR Connection String Format

```
CONNECTIONTYPE OGR
CONNECTION "/data/gold/atlas_4326/"
DATA "tigray/TigrayRoadsIn2006"    ← Relative to CONNECTION root
```

**Key Points**:
- `CONNECTION` points to base directory
- `DATA` is relative path and layer name (no .shp extension)
- MapServer reads `.shp` → `.dbf` → `.shx` → `.prj` automatically

### WMS Service Health

**Endpoint**: `http://tsird-mapserver:8000/?map=/etc/mapserver/tsird.map&SERVICE=WMS&REQUEST=GetCapabilities`

**Health Check Interpretation**:
- ✅ HTTP 200 + `<WMS_Capabilities>` in response → Healthy
- ❌ HTTP 200 + tiny error PNG (~542 bytes) → Layer misconfiguration
- ❌ HTTP 500 → Mapfile syntax error or missing file reference
- ❌ Timeout → Mapfile parsing stalled or data I/O issue

### GetMap Request Examples

**Render Ethiopia boundaries at EPSG:4326**:
```
GET /ogc?
  map=/etc/mapserver/tsird.map
  SERVICE=WMS
  VERSION=1.3.0
  REQUEST=GetMap
  CRS=EPSG:4326
  BBOX=33.0,3.0,48.0,15.5
  WIDTH=800&HEIGHT=600
  LAYERS=ethiopia_boundary_level2
  FORMAT=image/png
```

**GetFeatureInfo (query attributes)**:
```
GET /ogc?
  ... (same as above, but with INFO_FORMAT=text/plain)
  QUERY_LAYERS=ethiopia_woredas
  X=400&Y=300
```

---

## Future Automation: n8n Orchestration

### Pipeline Trigger Concept

```
n8n Webhook
  ↓ (triggered by: schedule, dataset drop, manual button)
  ├─ Check data/raw for new shapefiles
  ├─ Run raw_inventory_audit.py
  ├─ Run normalize_to_gold_4326.py
  ├─ Run separate_layers.py
  ├─ Generate vectors_gold.map (optional: auto-template)
  ├─ Docker restart tsird-mapserver
  ├─ Test WMS GetCapabilities
  ├─ Send health report Slack
  └─ Mark run as PASS | FAIL

Artifact: status.json with counts
  {
    "run_utc": "2026-02-22T10:30:00Z",
    "total_layers": 42,
    "gold_layers": 40,
    "quarantined_layers": 2,
    "tigray_only": 18,
    "ethiopia_wide": 22,
    "wms_health": "PASS",
    "error_summary": "..."
  }
```

### Dataset Drop-In Design

Replace `/work/data/raw/vectors/` with new ZIP/TAR archive:
1. ETL detects change (file hash or timestamp)
2. Extracts to temp dir
3. Validates all new layers via raw_inventory_audit
4. If all pass → promote to raw/ (atomic swap)
5. If any fail → quarantine separately; alert operator
6. Run full pipeline to regenerate gold/ + MapServer config

---

## Conclusion

The TSIRD Atlas Data Engineering Pipeline achieves reproducibility, auditability, and data quality through:

1. **Structured stages**: Audit → Normalize → Separate → Expose
2. **Zero manual intervention**: Every decision is logged; all fixes go through YAML config
3. **Quarantine model**: Failed data never silently enters production
4. **CRS canonicalization**: All outputs EPSG:4326; no surprises downstream
5. **Regional separation**: Clean Ethiopia vs Tigray split; easily extendable to other regions

This design supports both current operations and future automation via orchestration tools (n8n, Airflow, etc.).

