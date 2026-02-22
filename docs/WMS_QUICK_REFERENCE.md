# TSIRD WMS - Quick Reference Card

## ✓ SERVICE STATUS: OPERATIONAL

**Access Point**: `http://127.0.0.1:18080/map/ogc?map=/etc/mapserver/tsird.map`

---

## Key Facts (At a Glance)

| Feature | Status |
|---------|--------|
| **WMS Layers Available** | 42 (100% verified) |
| **GetMap (rendering)** | ✓ 100% success |
| **GetFeatureInfo (queries)** | ✓ 100% operational |
| **Coordinate System** | EPSG:4326 (lat,lon) |
| **WMS Standard** | OGC 1.3.0 compliant |
| **Image Format** | PNG (800x600 test) |
| **Proxy Port** | 18080 |
| **Response Times** | 100-1,200 ms |

---

## Test Commands

### Quick Health Check (30 seconds)
```bash
bash /opt/tigrayinsights/apps/tsird/scripts/tsird-wms-validate-simple.sh
```

### Full Layer Audit (2-3 minutes)
```bash
bash /opt/tigrayinsights/apps/tsird/scripts/tsird-wms-render-audit.sh
```

### GetFeatureInfo Test (20 seconds)
```bash
bash /opt/tigrayinsights/apps/tsird/scripts/tsird-featureinfo-test.sh
```

---

## Example Layer Requests

### Option 1: Ethiopia Zones (Polygon Layer)
```bash
curl -o zones.png 'http://127.0.0.1:18080/map/ogc?map=/etc/mapserver/tsird.map&SERVICE=WMS&VERSION=1.3.0&REQUEST=GetMap&LAYERS=ethiopia_zones&CRS=EPSG:4326&BBOX=3.0,33.0,15.5,48.0&WIDTH=800&HEIGHT=600&FORMAT=image/png'
```

### Option 2: Tigray Roads (Line Layer)
```bash
curl -o roads.png 'http://127.0.0.1:18080/map/ogc?map=/etc/mapserver/tsird.map&SERVICE=WMS&VERSION=1.3.0&REQUEST=GetMap&LAYERS=tigray_roads_2006&CRS=EPSG:4326&BBOX=3.0,33.0,15.5,48.0&WIDTH=800&HEIGHT=600&FORMAT=image/png'
```

### Option 3: DEM Elevation (Raster Layer)
```bash
curl -o dem.png 'http://127.0.0.1:18080/map/ogc?map=/etc/mapserver/tsird.map&SERVICE=WMS&VERSION=1.3.0&REQUEST=GetMap&LAYERS=ethiopia_dem&CRS=EPSG:4326&BBOX=3.0,33.0,15.5,48.0&WIDTH=800&HEIGHT=600&FORMAT=image/png'
```

### Option 4: Get All Available Layers
```bash
curl 'http://127.0.0.1:18080/map/ogc?map=/etc/mapserver/tsird.map&SERVICE=WMS&VERSION=1.3.0&REQUEST=GetCapabilities' | grep '<Name>' | head -50
```

---

## Layer Categories

### Ethiopia Regional (25 Layers)
**Boundaries**: ethiopia_admin, zones, woredas, wereda, boundary_level1/2/3  
**Roads/Transport**: roads, roads_raw, roads_baseline, rivers, streams  
**Water**: basins, major_basins, lakes, wetlands  
**Environment**: ecology, national_forest/forests/parks, soils  
**Climate/Precipitation**: rainfall_pattern, rainfall_stations  
**Populated Places**: towns, language  
**Elevation**: contour, isoheight, dem, hillshade, slope, slope_rgb  
**Base**: cia_basemap, aoi

### Tigray Regional (17 Layers)
**Administration**: tabias, woredas_new, woreda  
**Infrastructure**: roads_2006, roads_2006t, contour  
**Services**: health_2006, schools_2006  
**Places**: towns

---

## Important: Coordinate System Note

⚠️ **WMS 1.3.0 requires EPSG:4326 in LAT,LON order (not LON,LAT)**

```
WRONG:  BBOX=33.0,3.0,48.0,15.5  (longitude first)
RIGHT:  BBOX=3.0,33.0,15.5,48.0  (latitude first)

Meaning: Latitude 3°-15.5°N, Longitude 33°-48°E
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Layer appears rotated/inverted | Check BBOX coordinate order (lat,lon not lon,lat) |
| GetFeatureInfo returns no results | Layer may be empty at that location - try I=400,J=300 |
| Service unavailable | Check: `docker ps` (MapServer running?) |
| Slow response | Normal for large complex layers (DEM, hillshade) |
| Mapfile error | Run: `docker exec tsird-mapserver mapserv -v` |

---

## Verification Files

| File | Purpose | Size |
|------|---------|------|
| COMPLETION.md | Full project summary | 8 KB |
| WMS_VERIFICATION_STATUS.md | Operations status & procedures | 12 KB |
| tsird_wms_render_audit_report.md | Detailed technical audit | 15 KB |
| tsird-wms-render-audit.sh | Automated layer audit script | 4 KB |
| tsird-featureinfo-test.sh | GetFeatureInfo verification | 2 KB |
| tsird-wms-validate-simple.sh | 5-test smoke test | 3 KB |

---

## Contact/Support

For issues or questions:
1. Check troubleshooting table above
2. Review `docs/atlas/WMS_VERIFICATION_STATUS.md`
3. Run diagnostic scripts
4. Check MapServer logs: `docker logs tsird-mapserver`
5. Verify mapfile: `docker exec tsird-mapserver mapserv -v`

---

**Status**: ✓ All systems operational | All 42 layers verified | Production ready
