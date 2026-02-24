# WMS 1.3.0 EPSG:4326 Axis Order Issue

## Problem

GetMap requests were returning blank images when using WMS 1.3.0 with EPSG:4326 (Geographic CRS).

### Symptoms
- GetCapabilities works (returns XML) ✅
- GetMap requests return PNG with correct headers but **blank/transparent images** ❌
- MapServer logs show: `msOGRFileNextShape: Returning MS_DONE (no more shapes)`

### Root Cause

**WMS 1.3.0 changed BBOX axis ordering to follow EPSG specifications.**

- **WMS 1.1.1** (old): Always uses (minX, minY, maxX, maxY) = (minLon, minLat, maxLon, maxLat)
- **WMS 1.3.0** (new): Uses values **in EPSG axis order**
  - EPSG:4326 defines axes as **[Latitude, Longitude]**
  - So BBOX must be: (minLat, minLon, maxLat, maxLon) — **swapped!**
  - EPSG:3857 defines axes as **[Easting, Northing]** 
  - So BBOX stays: (minE, minN, maxE, maxN)

### Example

Requesting Ethiopia (lon 33-48, lat 3-15.5):

**Incorrect (WMS 1.1.1 style):**
```
BBOX=33,3,48,15.5  ← (minLon, minLat, maxLon, maxLat)
CRS=EPSG:4326
VERSION=1.1.0
→ MapServer: spatial filter = min [33, 3] max [48, 15.5] ✅ WORKS
```

**Correct (WMS 1.3.0 style):**
```
BBOX=3,33,15.5,48  ← (minLat, minLon, maxLat, maxLon)  
CRS=EPSG:4326
VERSION=1.3.0
→ MapServer: spatial filter = min [3, 33] max [15.5, 48] ✅ WORKS
```

**What was happening (user's error):**
```
BBOX=33,3,48,15.5  ← (minLon, minLat, maxLon, maxLat) WMS 1.1.1 order
CRS=EPSG:4326
VERSION=1.3.0
→ MapServer interprets as: min [33, 3] max [48, 15.5]
→ Spatial filter queries data in wrong region: latitude 33-48, longitude 3-15.5
→ No features found: NO MORE SHAPES ❌ BLANK MAP
```

## Solution

OpenLayers must be configured to use WMS 1.3.0 with proper axis order handling for geographic CRSs.

### Code Fix (LayerFactory.js)

```javascript
const source = new ol.source.ImageWMS({
  url: this.wmsBaseUrl,
  params: { /* ... */ },
  serverType: 'mapserver',
  wmsVersion: '1.3.0'  // ← CRITICAL: Enables automatic axis order handling
});
```

**What `wmsVersion: '1.3.0'` does:**
1. Tells OpenLayers to send `VERSION=1.3.0` in WMS params
2. Tells OpenLayers to automatically **reorder BBOX to (y,x) for geographic CRSs**
3. When transforming extent from EPSG:3857 → EPSG:4326, OL reorders to (lat, lon)

### How OpenLayers Handles This

When making a GetMap request for a geographic CRS with WMS 1.3.0:

```
1. Map view extent in EPSG:3857: [E_min, N_min, E_max, N_max]
2. Transform to EPSG:4326: [lon, lat, lon, lat]
3. With wmsVersion='1.3.0':
   a. Detect CRS is geographic (EPSG:4326)
   b. Reorder to axis order [lat, lon, lat, lon]
   c. Send: BBOX=lat_min,lon_min,lat_max,lon_max
4. MapServer receives correct order and queries all data ✅
```

## Testing

### Test Command (Correct Axis Order)
```bash
# Correct for WMS 1.3.0 with EPSG:4326
curl -s "http://localhost:18080/map/ogc?SERVICE=WMS&REQUEST=GetMap&VERSION=1.3.0&LAYERS=ethiopia_zones&CRS=EPSG:4326&BBOX=3,33,15.5,48&WIDTH=800&HEIGHT=600&FORMAT=image/png" -o /tmp/map.png && wc -c /tmp/map.png
# Expected: ~71KB (image with data)

# Wrong axis order (will be blank)
curl -s "http://localhost:18080/map/ogc?SERVICE=WMS&REQUEST=GetMap&VERSION=1.3.0&LAYERS=ethiopia_zones&CRS=EPSG:4326&BBOX=33,3,48,15.5&WIDTH=800&HEIGHT=600&FORMAT=image/png" -o /tmp/map_blank.png && wc -c /tmp/map_blank.png
# Expected: ~2.1KB (blank/transparent PNG)
```

### File Sizes
- **Blank image** (no data): ~2,168 bytes (PNG with transparent pixels)
- **Image with data** (correct axis order): ~71,707 bytes (rendered features visible)

## WMS Specification References

- **WMS 1.1.1 Specification**: BBOX always (minX, minY, maxX, maxY)
  - See: http://www.opengeospatial.org/standards/wms (deprecated)

- **WMS 1.3.0 Specification**: BBOX follows **CRS axis order**
  - See: https://portal.ogc.org/files/?artifact_id=14416
  - Section 6.7.6: "For geographic CRS, the order of coordinates in BBox, CRS and other quantities is driven by the axis order of the CRS."

## Browser Developer Tools Check

When frontend is loaded, open DevTools Network tab and check a GetMap request:

**Good (WMS 1.3.0 with geographic CRS axis order):**
```
GET /map/ogc?SERVICE=WMS&VERSION=1.3.0&LAYERS=ethiopia_zones&CRS=EPSG:4326&BBOX=3,33,15.5,48&WIDTH=...
```

**Bad (Old WMS 1.1.1 order):**
```
GET /map/ogc?SERVICE=WMS&VERSION=1.3.0&LAYERS=ethiopia_zones&CRS=EPSG:4326&BBOX=33,3,48,15.5&WIDTH=...
```

Note the BBOX parameter — first two values should be latitude range (3-15.5), not longitude range (33-48).

## Additional Notes

- This issue **only affects geographic CRSs** (EPSG:4326, EPSG:4269, etc.)
- Projected CRSs (EPSG:3857, EPSG:2193, etc.) are unaffected because their axis order is already (X, Y)
- OpenLayers handles this automatically when `wmsVersion: '1.3.0'` is configured
- MapServer correctly implements WMS 1.3.0 axis order handling

## Commits

- **a9f3c8e** (or later): Added `wmsVersion: '1.3.0'` to ImageWMS source in LayerFactory.js
