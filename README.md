# TSIRD Atlas – Tigray Spatial Intelligence & Resilience Dashboard

[![Status](https://img.shields.io/badge/status-production-green)]()
[![License](https://img.shields.io/badge/license-private-red)]()

A production-grade geospatial data engineering pipeline for processing Ethiopian spatial data, normalizing coordinate systems, and serving layers via OGC WMS/WFS.

---

## Overview

**TSIRD Atlas** is a Docker-based GIS ETL system that:
- Ingests raw shapefiles and rasters with inconsistent CRS definitions
- Validates and normalizes all layers to EPSG:4326 (WGS 84)
- Separates data by region (Ethiopia-wide vs Tigray-focused)
- Exposes validated layers through MapServer (WMS/WFS/WCS)
- Maintains full audit trails and quarantine logs for failed transformations

**Tech Stack**: Docker Compose, Python 3.11, GeoPandas, GDAL, PostGIS 16-3.4, MapServer 8.6.0

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

## License

**Private Portfolio Repository** — Not licensed for redistribution or commercial use.

---

## Contact

For questions about this data engineering pipeline architecture, please refer to the comprehensive documentation in [docs/](docs/) or review the incident reports for real-world troubleshooting examples.

**Project Context**: Production GIS pipeline built for Tigray regional spatial intelligence, demonstrating ETL design patterns, Docker orchestration, and OGC geospatial web services.
