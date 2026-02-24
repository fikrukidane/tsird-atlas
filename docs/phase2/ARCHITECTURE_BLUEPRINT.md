# Phase 2 - Stage 2: Architecture Blueprint
**Generated**: 2026-02-24  
**Status**: ✓ ARCHITECTURE FREEZE COMPLETE — Locked & Approved

---

## Executive Summary

This document defines the **final, frozen architecture** for TSIRD Phase 2: Public Web Atlas. All critical technology decisions have been locked. The architecture is **WMS-first**, **YAML-registry-driven**, **WFS-disabled**, and **cache-forward-ready**.

**5 Locked Technology Decisions**:
1. **Frontend**: OpenLayers 8+ (WMS-first, tiled WMS preferred)
2. **Registry Format**: YAML (authoritative), JSON artifact generated
3. **OGC Services**: WMS only (WFS disabled Phase 2)
4. **Rate Limits**: 1 req/s GetCapabilities (burst 3), 20 req/s GetMap (burst 60), 5 req/s GetFeatureInfo (burst 10)
5. **MapCache**: Deferred to Phase 3 (Tier 3 reserved, cache-friendly patterns enforced)

---

## 1. System Topology (5-Tier Layered Architecture)

**Tier 1**: OpenLayers 8+ Client (HTTPS only)
**Tier 2**: NGINX Edge Proxy (WMS-only allowlist, rate limiting 1/20/5 req/s)
**Tier 3**: MapCache (RESERVED - Phase 3)
**Tier 4**: MapServer 8.6 (WMS GetCapabilities/GetMap/GetFeatureInfo, WFS disabled)
**Tier 5**: PostGIS + OGR Shapefiles + GeoTIFF Rasters

---

## 2. Component Responsibilities

### Tier 1: OpenLayers (LOCKED)
- WMS-first rendering (tiled GetMap, 256×256)
- Table of Contents (layer visibility management)
- Feature identify (WMS GetFeatureInfo)
- Search interface
- No direct PostGIS access

### Tier 2: NGINX Edge Proxy
- HTTPS termination
- WMS-only allowlist (blocks WFS)
- Rate limiting: 1/s GetCapabilities, 20/s GetMap, 5/s GetFeatureInfo
- Size validation (WIDTH/HEIGHT ≤ 2048)
- CORS headers (atlas origin only)

### Tier 4: MapServer 8.6
- WMS 1.3.0 service (GetCapabilities, GetMap, GetFeatureInfo)
- Query PostGIS tables
- Read OGR shapefiles
- Read GeoTIFF rasters
- Attribute filtering (whitelist only)

### Tier 5: Data Layer
- PostGIS 16-3.4 (gold.roads, gold.aoi_ethiopia)
- OGR Shapefiles (/data/gold/atlas_4326/, 32 layers, EPSG:4326)
- GeoTIFF Rasters (/data/gold/{dem,slope,rasters_web}/)

---

## 3. Registry Configuration (YAML - LOCKED)

**File**: `config/atlas-registry.yaml`
**Format**: YAML (authoritative source)
**Consumption**: Parsed server-side, JSON artifact generated for browser

---

## 4. Data Flows

### GetMap Flow (Tile Rendering)
Client → OpenLayers (tiled WMS request) → NGINX (validate, rate limit) → MapServer (render PNG) → Browser cache

### GetFeatureInfo Flow (Identify)
Client click → OpenLayers → NGINX (rate limit) → MapServer (query) → Popup display

---

## 5. Security Model (4-Layer Defense)

**Layer 1**: Network (only HTTPS port exposed)
**Layer 2**: Proxy (WMS-only allowlist, rate limiting, request validation)
**Layer 3**: Service (read-only filesystem, SELECT-only DB user, attribute filtering)
**Layer 4**: Data (no ALTER/DROP privileges, parameterized queries)

---

## 6. Technology Stack (FINAL FREEZE)

| Component | Technology | Status |
|-----------|-----------|--------|
| Frontend | OpenLayers 8+ | ✓ LOCKED |
| Rendering | WMS-first (tiled GetMap) | ✓ LOCKED |
| Registry | YAML → JSON | ✓ LOCKED |
| Proxy | NGINX 1.25+ | ✓ Fixed |
| Service | MapServer 8.6 | ✓ Fixed |
| Database | PostGIS 16-3.4 | ✓ Fixed |
| Cache | MapCache 1.14+ (Phase 3) | ✗ Deferred |

---

## 7. OGC Service Status (LOCKED)

| Operation | Status | Rate Limit |
|-----------|--------|-----------|
| WMS GetCapabilities | ✓ ENABLED | 1 req/s (burst 3) |
| WMS GetMap | ✓ ENABLED | 20 req/s (burst 60) |
| WMS GetFeatureInfo | ✓ ENABLED | 5 req/s (burst 10) |
| WFS GetFeature | ✗ DISABLED | - |
| WFS DescribeFeatureType | ✗ DISABLED | - |

---

## 8. Performance Targets (Phase 2)

| Metric | Target |
|--------|--------|
| GetCapabilities | < 500ms |
| GetMap (cold) | < 1000ms |
| GetMap (warm) | < 50ms |
| GetFeatureInfo | < 500ms |

---

## 11. Stage 2 Freeze Checklist

✓ Network topology (5-tier, isolated)  
✓ Component responsibilities (clear per tier)  
✓ Data flows (GetMap, GetFeatureInfo documented)  
✓ Security boundaries (4-layer defense)  
✓ Technology stack LOCKED (OpenLayers, YAML, WMS-only, rate limits)  
✓ All 5 TBD decisions LOCKED

---

**✓ END OF STAGE 2: ARCHITECTURE FREEZE COMPLETE**

Next: Stage 3 - Configuration Contract Design
