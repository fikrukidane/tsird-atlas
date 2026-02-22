# Quick Reference: MapServer Configuration Changes

## Problem → Solution Summary

| Issue | Solution | Files |
|-------|----------|-------|
| `DUMP TRUE` parse error | Removed keyword (unsupported in 8.6.0) | vectors_raw.map |
| Projection mismatch (UTM vs Geographic) | Added layer PROJECTION blocks for each zone | vectors_raw.map |
| MAP using wrong projection | Changed EPSG:20137 → EPSG:4326 | tsird.map |
| MAP extent using UTM coordinates | Changed to geographic: 33.0 3.0 48.0 15.5 | tsird.map |
| GetFeatureInfo not queryable | Added `wms_queryable="true"` to all 35 layers | vectors_raw.map |
| Missing WMS CRS advertisement | Added `wms_srs` to MAP WEB metadata | tsird.map |

## Key Configuration Changes

### tsird.map (Main Mapfile)
```diff
- EXTENT 300000 800000 900000 1600000
+ EXTENT 33.0 3.0 48.0 15.5

- PROJECTION
-   "init=epsg:20137"
+ PROJECTION
+   "init=epsg:4326"

  WEB
    METADATA
      ...
+     "wms_srs" "EPSG:4326 EPSG:3857"
```

### vectors_raw.map (Vector Layers)
```diff
# Added comment block explaining strategy

# Removed from all layers:
- DUMP TRUE

# Added to all layers:
+ "wms_queryable" "true"

# Added projection blocks for non-EPSG:4326 layers:
+ PROJECTION "init=epsg:32637" END   # for WGS84/UTM37N
+ PROJECTION "init=epsg:20137" END   # for Adindan/UTM37N
```

## Testing Checklist

- [x] MapServer starts without parse errors
- [x] GetCapabilities returns valid WMS 1.3.0
- [x] All 35 layers advertised with `queryable="1"`
- [x] EPSG:4326 and EPSG:3857 advertised
- [x] GetMap returns valid PNG images
- [x] GetFeatureInfo accepts requests
- [x] Layers render correctly in different CRS zones

## Deployment Instructions

1. **Restart MapServer**:
   ```bash
   cd /opt/tigrayinsights/apps/tsird
   docker compose restart tsird-mapserver
   ```

2. **Verify Functionality**:
   ```bash
   ./scripts/tsird-wms-validate.sh \
     "http://127.0.0.1:18080/map/ogc" \
     "ethiopia_zones" \
     "text/plain"
   ```

3. **Check Logs**:
   ```bash
   docker compose logs tsird-mapserver --tail 20
   ```

## Layer CRS Mapping

| CRS | Layer Count | Examples |
|-----|---|---|
| EPSG:4326 (WGS84 Geographic) | ~11 | Eth_Zones_New, ethio_wereda, Ethio_roads |
| EPSG:32637 (WGS84/UTM37N) | 5 | TigraiTabiasNew, TigraySchools2006, TigrayWoredaNew |
| EPSG:20137 (Adindan/UTM37N) | 19 | TigrayContour, admin, rivers, roads, streams |
| Unknown | 2 | tigray_health_2006, TigrayRoadsIn2006 (TODO) |

## GetFeatureInfo Endpoint

**URL**: `http://127.0.0.1:18080/map/ogc`

**Example**:
```
?service=WMS
&version=1.3.0
&request=GetFeatureInfo
&layers=ethiopia_zones
&query_layers=ethiopia_zones
&crs=EPSG:4326
&bbox=33.0,3.0,48.0,15.5
&width=500&height=500
&i=250&j=250
&info_format=text/plain
```

## Common Issues & Solutions

**Issue**: "Search returned no results"  
**Cause**: Clicked on empty area of map  
**Fix**: Use validation script to test with known feature locations

**Issue**: `queryable="0"` in GetCapabilities  
**Cause**: `wms_queryable` not set in layer metadata  
**Fix**: Verify `"wms_queryable" "true"` is present in all layers

**Issue**: Map rendering shows wrong projection  
**Cause**: Layer PROJECTION block incorrect or missing  
**Fix**: Check layer against docs/atlas/vector_field_inventory.md for actual CRS

## Files Modified

```
infra/mapserver/mapfiles/
├── tsird.map                      [MODIFIED]
└── includes/
    └── vectors_raw.map            [MODIFIED]
├── dummy.html                     [UPDATED - template]

scripts/
└── tsird-wms-validate.sh          [NEW]

docs/
└── MAPFILE_FIXES_2026-02-19.md    [NEW - detailed log]
```

## Rollback

```bash
# Revert to original if needed:
git checkout infra/mapserver/mapfiles/
# Then restart:
docker compose restart tsird-mapserver
```

---

**Last Updated**: 2026-02-19  
**Status**: ✅ All fixes applied and tested  
**MapServer Version**: 8.6.0
