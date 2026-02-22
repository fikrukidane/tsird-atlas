#!/usr/bin/env bash
set -euo pipefail

# End-to-end TSIRD Roads WMS verification for both EPSG:4326 and EPSG:20137
cd /opt/tigrayinsights/apps/tsird

WMS_BASE='http://127.0.0.1:18080/map/ogc'
CAPS_FILE=/tmp/tsird_caps.xml

echo "=========================================="
echo "TSIRD Roads WMS Verification"
echo "=========================================="

# Step 1: Query PostGIS for gold.roads metadata
echo ""
echo "Step 1: Checking PostGIS gold.roads..."
PG_INFO=$(docker compose --env-file .env.tsird exec -T tsird-postgis sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At -F"|" -c "SELECT COUNT(*),MIN(ST_SRID(geom)),MIN(GeometryType(geom)) FROM gold.roads;"')
echo "Result: $PG_INFO"

IFS='|' read -r ROWS SRID GEOMTYPE <<EOF
$PG_INFO
EOF

if [ "$ROWS" != "2268" ] || [ "$SRID" != "4326" ] || [ "$GEOMTYPE" != "MULTILINESTRING" ]; then
  echo "FAIL: Expected 2268|4326|MULTILINESTRING, got $PG_INFO"
  exit 1
fi
echo "✓ PostGIS: 2268 rows, SRID 4326, MULTILINESTRING"

# Step 2: GetCapabilities and verify TSIRD WMS
echo ""
echo "Step 2: Checking WMS GetCapabilities..."
curl -s --fail "${WMS_BASE}?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetCapabilities" -o "$CAPS_FILE"
if ! grep -q 'TSIRD WMS' "$CAPS_FILE"; then
  echo "FAIL: 'TSIRD WMS' not found in GetCapabilities"
  head -n 20 "$CAPS_FILE"
  exit 1
fi
echo "✓ GetCapabilities: TSIRD WMS found"

# Step 3: GetMap for EPSG:4326
echo ""
echo "Step 3: GetMap for EPSG:4326..."
IMG_4326=/tmp/roads_4326.png
BBOX_4326="33.0062466792,3.4069807586,47.9965680729,14.8872693890"

curl -s --fail "${WMS_BASE}?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetMap&LAYERS=roads&STYLES=&CRS=EPSG:4326&BBOX=${BBOX_4326}&WIDTH=1200&HEIGHT=800&FORMAT=image/png" -o "$IMG_4326"

sig=$(head -c8 "$IMG_4326" | od -An -tx1 | tr -d ' \n')
if [ "$sig" != "89504e470d0a1a0a" ]; then
  echo "FAIL: EPSG:4326 GetMap did not return PNG (signature=$sig)"
  echo "----- Response (first 25 lines) -----"
  head -n 25 "$IMG_4326" || true
  echo "----- End -----"
  exit 2
fi
echo "✓ GetMap EPSG:4326 returned PNG"
echo "  Image saved: $IMG_4326"

# Step 4: GetMap for EPSG:20137
echo ""
echo "Step 4: GetMap for EPSG:20137..."
IMG_20137=/tmp/roads_20137.png
BBOX_20137="-161882,376388,1495282,1645935"

curl -s --fail "${WMS_BASE}?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetMap&LAYERS=roads&STYLES=&CRS=EPSG:20137&BBOX=${BBOX_20137}&WIDTH=1200&HEIGHT=800&FORMAT=image/png" -o "$IMG_20137"

sig=$(head -c8 "$IMG_20137" | od -An -tx1 | tr -d ' \n')
if [ "$sig" != "89504e470d0a1a0a" ]; then
  echo "FAIL: EPSG:20137 GetMap did not return PNG (signature=$sig)"
  echo "----- Response (first 25 lines) -----"
  head -n 25 "$IMG_20137" || true
  echo "----- End -----"
  exit 2
fi
echo "✓ GetMap EPSG:20137 returned PNG"
echo "  Image saved: $IMG_20137"

# Final summary
echo ""
echo "=========================================="
echo "✓ ALL TESTS PASSED"
echo "=========================================="
echo "PostGIS: 2268|4326|MULTILINESTRING"
echo "WMS Capabilities: OK"
echo "GetMap EPSG:4326: OK → $IMG_4326"
echo "GetMap EPSG:20137: OK → $IMG_20137"
echo ""
exit 0
