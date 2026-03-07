# TSIRD Atlas

Geospatial data engineering system for normalizing heterogeneous vector and raster datasets to EPSG:4326, validating regional bounds, and publishing via OGC WMS/WFS. Built for Ethiopian spatial data with explicit focus on Tigray regional subsetting. This system handles CRS-inconsistent shapefiles, applies YAML-driven coordinate overrides, validates geometry integrity, quarantines malformed features, and exposes normalized layers through MapServer. Architecture is Docker-based with PostGIS storage and incremental pipeline orchestration in progress.

**Stack**: Python 3.11, GeoPandas, GDAL 3.8, PostGIS 16+3.4, MapServer 8.6, Docker Compose
**Status**: Private portfolio repository. Source datasets and credentials excluded.

---

## Core Capabilities

**Vector Processing**
- CRS detection and EPSG:4326 normalization with YAML override mechanism
- Geometry validation with automatic repair and quarantine logging
- Bounds anomaly detection (longitude/latitude range enforcement)
- Regional separation engine (Tigray vs Ethiopia-wide classification)

**Raster Integration**
- DEM and slope layer processing
- Web raster ingestion and tiling
- GDAL-based reprojection and clipping

**Publication Layer**
- MapServer WMS/WFS/WCS endpoints
- Multi-CRS support (EPSG:4326, 20137, 3857)
- PostGIS-backed layer serving

**Infrastructure**
- Docker Compose service orchestration
- PostGIS 16 with spatial indexing
- Audit trail generation (CSV + Markdown reports)
- Incremental pipeline orchestration (in progress)

---

## Architecture Overview

```
Raw Data (shapefiles/rasters)
            |
            v
Raw Inventory Audit
   - CRS detection
   - Geometry validity checks
   - Bounds anomaly detection
   - Audit reports (CSV/MD)
            |
            v
CRS Normalization (EPSG:4326)
   - YAML override catalog
   - Reprojection + repair
   - Quarantine invalid features
            |
            v
Regional Separation
   - Tigray vs Ethiopia-wide
   - Clip to regional bounds
   - Load into PostGIS (gold.*)
            |
            v
MapServer Publication
   - WMS/WFS/WCS
   - Multi-CRS handling
   - PostGIS-backed layers
```

---

## Engineering Principles

- **No manual fixes**: CRS overrides are YAML-defined; pipeline is reproducible.
- **Quarantine-first**: Invalid features are isolated with diagnostic context.
- **Explicit CRS handling**: Every layer's CRS is detected, assigned, and logged.
- **Bounds enforcement**: Longitude and latitude ranges are validated.
- **Auditable**: Each stage emits structured CSV/MD reports.
- **Containerized**: No host GIS dependencies.

---

## Current System Status

### Development Notes

**Frontend - OpenLayers Map Initialization**
- OpenLayers requires a DOM element with ID `map` as the map target
- The element must exist before `new ol.Map()` is called and have non-zero dimensions
- CSS must ensure the map container has explicit height/width (e.g., flexbox with `flex: 1` or `height: 100%`)
- If the target element is missing or has zero height, the map will not render
- See [STAGE6_FRONTEND.md](docs/phase2/STAGE6_FRONTEND.md#dom-requirements) for detailed requirements

**Frontend - WMS Endpoint Configuration**
- Default WMS endpoint: defined in `config/atlas-registry.yaml` → `services.wms.base_url`
- **Local Development**: Registry points to `http://localhost:18080/map/ogc` (edge proxy)
- **Environment Override**: Set `window.TSIRD_WMS_BASE_URL` before loading app to override registry value
  
  Example: Add to `index.html` before loading scripts:
  ```html
  <script>
    // Override WMS endpoint for custom dev environment
    window.TSIRD_WMS_BASE_URL = 'http://localhost:18080/map/ogc';
  </script>
  ```

- **Production**: Use absolute URL pointing to proxy/domain: `https://yourdomain.com/map/ogc`
- **Safety Guard**: RegistryLoader warns if `base_url` is relative (e.g., `/map/ogc`) and auto-resolves in dev mode
- **Verification**: Check DevTools Network tab → WMS GetMap requests should target MapServer port (18080), not frontend port (8001)

**Phase 2 v1 Default View + TOC Folder Behavior**
- Default map view is Tigray-focused (center/extent in `atlas-registry.yaml`).
- TOC always renders full category/group folder structure, even when groups are empty.
- Categories start collapsed except Map Elements + Administrative (Regional).
- Default-visible layers: Tabias, Towns, Tigray Roads 2006; others start OFF and de-emphasized.
- Credits panel is UI-only and lists attribution text from registry for currently visible layers.

### System Status

**Operational — v1.0.0 Production**
- Vector normalization pipeline (audit -> normalize -> separate)
- CRS override catalog (YAML)
- Geometry validation and quarantine model
- MapServer WMS/WFS publication
- PostGIS storage (gold schema)
- Audit reporting
- **Layer styling** — polygon hierarchy, muted categorical fills (Tigray zones, Ethiopia regions)
- **WMS GetLegendGraphic support** (LEGEND object + CLASS NAME attributes)
- **Legend UI** (inline legend display in TOC)
- **Phase 3 Atlas UI** — bilingual Woreda/Tabia gazetteer search, zoom-to-feature, orange highlight overlay, navigator map, distance/area measurement tools, persistent Display Settings panel
- **Cleaned TOC** — Ethiopia Administrative / Tigray State / Horn of Africa hierarchy
- **Bilingual labels** — NotoSansEthiopic for Tigrinya, Arial for English
- **FastAPI gazetteer** (`/map/api/gazetteer`) backed by PostGIS

**In Progress**
- Incremental orchestration
- Raster pipeline integration
- Automated health checks

**Not Implemented**
- Automated testing suite
- Real-time incremental updates
- Full WCS raster configuration

---

## Atlas Access

| Environment | URL |
|---|---|
| **Public** | https://lab.tigrayinsights.net |
| **Internal path** | https://lab.tigrayinsights.net/map/ |
| **Local development** | http://localhost:18080/map/ |

All atlas assets (UI, data, WMS OGC endpoint) are served under the `/map` path prefix.

**Operational verification:**
```bash
# Atlas UI
curl -I https://lab.tigrayinsights.net/map/
# Registry
curl https://lab.tigrayinsights.net/map/data/atlas-registry.json
# WMS
curl "https://lab.tigrayinsights.net/map/ogc?SERVICE=WMS&REQUEST=GetCapabilities"
```

---

## Quick Start

### Prerequisites
- Docker Engine 24+
- Docker Compose 2.20+
- 4GB RAM minimum
- Linux/macOS/Windows with WSL2

### Local Setup

```bash
# 1. Clone repository
git clone <repository-url>
cd tsird

# 2. Configure environment
cp .env.example .env.tsird
# Edit .env.tsird with your database password

# 3. Configure MapServer
# Edit infra/mapserver/mapfiles/tsird.map
# Replace YOUR_DB_PASSWORD with actual password

# 4. Start services
docker-compose up -d

# 5. Verify health
docker-compose ps
curl -s http://localhost:18080/cgi-bin/mapserv?SERVICE=WMS&REQUEST=GetCapabilities
```

**Note**: This portfolio repository excludes source datasets and credentials. See [docs/README.md](docs/README.md) for full documentation.

---

## Architecture

### Data Pipeline Stages

1. **Raw Inventory Audit** (`etl/raw_inventory_audit.py`)
   - Detects missing/incorrect CRS definitions
   - Validates geometry integrity
   - Generates audit logs

2. **CRS Normalization** (`etl/normalize_to_gold_4326.py`)
   - Reprojects to EPSG:4326
   - Repairs invalid geometries
   - Applies CRS overrides from audit

3. **Regional Separation** (`etl/separate_layers.py`)
   - Classifies layers as Tigray-only or Ethiopia-wide
   - Clips geometry to regional bounds
   - Loads PostGIS tables

4. **MapServer Integration** (`infra/mapserver/`)
   - Exposes WMS/WFS endpoints
   - Handles multi-CRS requests (EPSG:4326, 20137, 3857)
   - Serves raster (WCS) and vector (WFS) layers

### Directory Structure

```
tsird/
├── docker-compose.yml         # Service orchestration
├── .env.example               # Template configuration
├── etl/                       # Python ETL scripts
├── infra/
│   ├── mapserver/            # MapServer configs + Mapfiles
│   └── host-nginx/           # Edge proxy (optional)
├── db/init/                  # PostGIS initialization
├── docs/                     # Technical documentation
└── scripts/                  # Verification scripts
```

---

## Documentation

**Start here**: [docs/README.md](docs/README.md) — Complete documentation index

### Core Documents

- [**Architecture**](docs/TSIRD_ATLAS_PIPELINE_ARCHITECTURE.md) — System design, data flow, principles
- [**Operations Guide**](docs/TSIRD_OPERATIONS_GUIDE.md) — Running pipeline, monitoring, common tasks
- [**Flow Diagrams**](docs/TSIRD_PIPELINE_FLOW_DIAGRAM.md) — Visual workflows for each stage
- [**Troubleshooting**](docs/TSIRD_TROUBLESHOOTING.md) — Error diagnosis, recovery procedures

### Incident Reports (Historical)
- MapServer polygon/line rendering fixes (2026-02-19)
- Point layer symbol resolution (2026-02-19)
- Jupyter SQLite backend fixes (2026-02-20)

---

## Portfolio Notes

### What's Included
✅ Complete ETL pipeline code (Python + Docker)  
✅ MapServer configuration templates  
✅ Comprehensive technical documentation  
✅ Health check scripts and verification tools  

### What's Excluded (Intentionally)
❌ Raw source datasets (shapefiles, rasters in `/data`)  
❌ Processed outputs (`/data/gold`, `/data/staging`)  
❌ Database credentials (`.env.tsird` ignored)  
❌ Large binaries (backups, test outputs)  

**Rationale**: This is a **portfolio/architecture demonstration** showcasing data engineering patterns, not a deployable instance with live data. Full deployment requires local datasets and environment configuration.

---

## Key Features

- **Zero Manual Fixes**: All CRS corrections automated via override catalog
- **Quarantine Model**: Invalid layers isolated with full diagnostic logging
- **Geometry Validation**: 98% validity threshold with automatic repair
- **Reproducible Pipeline**: Idempotent operations; safe to re-run
- **Docker-First**: No host GIS dependencies (GDAL/PostGIS containerized)
- **Multi-CRS Support**: MapServer handles EPSG:4326, 20137, 3857 reprojection

---

## Development

### Running ETL Pipeline (Local Development)

```bash
# Enter ETL container
docker-compose exec etl-service bash

# Run individual stages
python etl/raw_inventory_audit.py
python etl/normalize_to_gold_4326.py
python etl/separate_layers.py

# Verify WMS endpoint
curl "http://localhost:18080/mapserv?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetMap&LAYERS=roads&WIDTH=400&HEIGHT=400&CRS=EPSG:4326&BBOX=36,12,40,16&FORMAT=image/png" > test.png
```

### Monitoring

```bash
# Service health
docker-compose ps
docker-compose logs -f tsird-postgis
docker-compose logs -f mapserver

# PostGIS connection
docker exec -it tsird-postgis psql -U tsird -d tsird -c "\dt gold.*"

# MapServer logs
docker-compose logs --tail=50 mapserver
```

---

## Release Checklist

**This repository is intentionally published without source data or secrets.**

### ✅ What's Included in This Portfolio Repo

- **Complete ETL pipeline code** (Python + GDAL in `etl/`, `Docker Projects/TSIRD-Atlas-Data-Pipeline/`)
- **Docker orchestration** (docker-compose.yml, Dockerfiles, service configs)
- **MapServer configuration** (mapfiles, templates, includes)
- **Comprehensive documentation** (2900+ lines in `docs/`)
- **Verification scripts** (WMS tests, health checks in `scripts/`)
- **Database schema** (PostGIS initialization in `db/init/`)
- **Configuration templates** (.env.example with placeholders)

### ❌ What's Intentionally Excluded

**Data Files** (Never Committed):
- Source shapefiles: `data/raw/*.shp,*.dbf,*.shx,*.prj`
- Raster files: `data/source/*.tif`
- Processed outputs: `data/gold/*`, `data/staging/*`
- Database backups: `backups/*.dump`, `backups/*.bak`
- Test artifacts: `tmp/*`

**Secrets & Credentials** (Gitignored):
- Real environment variables: `.env.tsird`
- Database passwords: Removed from `infra/mapserver/mapfiles/tsird.map` (replaced with `YOUR_DB_PASSWORD`)
- Connection strings: Sanitized; use `.env.example` as template

**Large Binaries**:
- Notebook checkpoints: `.ipynb_checkpoints/`
- Compiled artifacts: `__pycache__/`, `*.pyc`

### 🚀 How to Run This Pipeline Locally

**Prerequisites**:
1. Source datasets (Ethiopian shapefiles/rasters)
2. Actual credentials in `.env.tsird`
3. Docker Engine 24+ with 4GB RAM

**Steps**:
```bash
# 1. Clone repository
git clone https://github.com/fikrukidane/tsird-atlas.git
cd tsird-atlas

# 2. Configure environment
cp .env.example .env.tsird
# Edit .env.tsird: Set POSTGRES_PASSWORD=<your_password>

# 3. Configure MapServer
# Edit infra/mapserver/mapfiles/tsird.map
# Replace YOUR_DB_PASSWORD with actual password (2 locations)

# 4. Add source data (not included in repo)
# Place shapefiles in data/raw/
# Place rasters in data/source/

# 5. Start services
docker-compose up -d

# 6. Run ETL pipeline
docker-compose exec etl-service python etl/raw_inventory_audit.py
docker-compose exec etl-service python etl/normalize_to_gold_4326.py
docker-compose exec etl-service python etl/separate_layers.py

# 7. Verify WMS endpoint
curl "http://localhost:18080/mapserv?SERVICE=WMS&REQUEST=GetCapabilities"
```

### 📚 Where Documentation Lives

- **System architecture**: [docs/TSIRD_ATLAS_PIPELINE_ARCHITECTURE.md](docs/TSIRD_ATLAS_PIPELINE_ARCHITECTURE.md)
- **Operations runbook**: [docs/TSIRD_OPERATIONS_GUIDE.md](docs/TSIRD_OPERATIONS_GUIDE.md)
- **Flow diagrams**: [docs/TSIRD_PIPELINE_FLOW_DIAGRAM.md](docs/TSIRD_PIPELINE_FLOW_DIAGRAM.md)
- **Troubleshooting**: [docs/TSIRD_TROUBLESHOOTING.md](docs/TSIRD_TROUBLESHOOTING.md)
- **Documentation index**: [docs/README.md](docs/README.md)

### 🔒 Security Notes

- All passwords replaced with placeholders (`YOUR_DB_PASSWORD`, `your_secure_password_here`)
- `.env.tsird` (real secrets) is gitignored and never committed
- `.env.example` is the only environment file in the repository
- MapServer CONNECTION strings sanitized
- No production database dumps included

### 📦 Repository Size

- **Tracked files**: 109
- **Total size**: ~157 KB (code, docs, configs only)
- **No binaries**: All data files properly excluded

---

## License

**Private Portfolio Repository** — Not licensed for redistribution or commercial use.

---

## Contact

For questions about this data engineering pipeline architecture, please refer to the comprehensive documentation in [docs/](docs/) or review the incident reports for real-world troubleshooting examples.

**Project Context**: Production GIS pipeline built for Tigray regional spatial intelligence, demonstrating ETL design patterns, Docker orchestration, and OGC geospatial web services.
