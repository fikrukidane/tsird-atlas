# TSIRD Architecture (Phase 1)
**System:** TSIRD – Tigray Spatial Intelligence & Resilience Dashboard  
**Deployment:** `https://lab.tigrayinsights.net/map` (path-based routing)  
**Date:** 2026-02-14  
**Standard:** Docker-first, reproducible, production-style GIS data engineering

---

## 1. Production VPS Context (Non-Negotiable)

**Server**
- OS: Ubuntu 24.04 LTS
- Host: Production-structured from day one
- SSH: Key auth enabled
- UFW: only `22, 80, 443` allowed
- Docker installed and verified
- Nginx installed and working
- SSL via Certbot active for: `lab.tigrayinsights.net`

**Routing**
- Path-based routing (NOT subdomains)
- All apps deployed under: `https://lab.tigrayinsights.net/<app>`
- TSIRD must be under: `https://lab.tigrayinsights.net/map`

**Security / Exposure**
- Containers must NOT expose public ports directly
- All services must be reverse-proxied through **host Nginx**
- Compose must use internal networking only (no default network assumptions)
- No host-level GIS dependencies (everything runs in containers)

**Naming conventions (hard requirement)**
- Services/containers: `tsird-*`
- Docker network: `tsird-network`
- Environment file naming convention: `.env.tsird` (documented for later use)

---

## 2. Architectural Goals (Portfolio-Grade)

TSIRD must demonstrate:
- Raster + vector spatial analytics
- Multi-source ETL (GDAL + Python + PostGIS)
- Raster/vector hybrid modeling (accessibility: roads + terrain penalty raster)
- Spatial indexing & performance tuning
- OGC publishing (WMS/WFS) via MapServer
- Clean separation: data / processing / serving / UI
- Reproducibility via Docker Compose + documented runbooks
- Incremental data updates and run lineage

---

## 3. Edge Contract (Routing + Health)

TSIRD is mounted under `/map` and must preserve path integrity end-to-end.

### 3.1 External interface (Host Nginx → TSIRD)
**Public entrypoint**
- `https://lab.tigrayinsights.net/map/`

**Host Nginx requirement**
- Host Nginx proxies `/map/` to TSIRD’s internal edge gateway on localhost:
  - `127.0.0.1:<EDGE_PORT>` (served by container `tsird-edge`)

> Only `tsird-edge` may bind to `127.0.0.1`. No other TSIRD service binds to host.

### 3.2 Internal routes (within TSIRD)
Inside TSIRD, `tsird-edge` routes traffic to upstreams:

| Public Path | Purpose | Upstream |
|---|---|---|
| `/map/` | Web UI (viewer + dashboard shell) | `tsird-web:8080` |
| `/map/ogc` | OGC services (WMS/WFS) | `tsird-mapserver:8000` |
| `/map/health` | Aggregated health (edge-level) | `tsird-edge` checks upstream health |
| `/map/version` | Build metadata (optional) | `tsird-edge` static JSON |

### 3.3 Health contract (required)
Health checks must be implemented for:
- `tsird-postgis`
- `tsird-mapserver`
- `tsird-etl`

Minimum definitions:
- **PostGIS healthy**: `pg_isready` succeeds and DB accepts connections.
- **MapServer healthy**: HTTP endpoint responds OR WMS GetCapabilities succeeds quickly.
- **ETL healthy**: runtime ok + can reach PostGIS + can read/write mounted data directories.

---

## 4. Logical Architecture Diagram

```mermaid
flowchart LR
  A[External Data Sources<br/>Admin boundaries<br/>Roads<br/>Health facilities<br/>Population grids<br/>DEM/NDVI/Fires] --> B[ETL Layer<br/>tsird-etl<br/>GDAL + Python]
  B --> C[(PostGIS<br/>tsird-postgis<br/>vectors + derived tables)]
  B --> D[(Raster Store<br/>COGs/GeoTIFFs/MBTiles<br/>mounted data dir)]
  C --> E[MapServer OGC<br/>tsird-mapserver<br/>WMS/WFS]
  D --> E
  E --> F[TSIRD Edge Gateway<br/>tsird-edge<br/>/map routing]
  G[Web UI Viewer<br/>tsird-web] --> F
  F --> H[Host Nginx (SSL)<br/>lab.tigrayinsights.net]
  H --> I[Users / Browsers]

```
