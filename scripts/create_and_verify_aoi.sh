#!/usr/bin/env bash
set -euo pipefail

cd /opt/tigrayinsights/apps/tsird

echo "=========================================="
echo "TSIRD AOI Ethiopia Setup"
echo "=========================================="

# Step 1: Create gold.aoi_ethiopia table
echo ""
echo "Step 1: Creating gold.aoi_ethiopia table..."
docker compose --env-file .env.tsird exec -T tsird-postgis sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1' << 'SQL'
DROP TABLE IF EXISTS gold.aoi_ethiopia CASCADE;

CREATE TABLE gold.aoi_ethiopia (
    aoi_id SERIAL PRIMARY KEY,
    name TEXT,
    geom geometry(Polygon, 4326)
);

CREATE INDEX idx_aoi_ethiopia_geom ON gold.aoi_ethiopia USING GIST(geom);

INSERT INTO gold.aoi_ethiopia (name, geom)
VALUES (
    'Ethiopia',
    ST_GeomFromText('POLYGON((32.99 3.40, 47.99 3.40, 47.99 14.89, 32.99 14.89, 32.99 3.40))', 4326)
);

SELECT COUNT(*) as rows, MIN(ST_SRID(geom)) as srid, MIN(GeometryType(geom)) as geom_type FROM gold.aoi_ethiopia;
SQL

echo "✓ Table created and Ethiopia AOI inserted"

# Step 2: Verify table
echo ""
echo "Step 2: Verifying table..."
PG_CHECK=$(docker compose --env-file .env.tsird exec -T tsird-postgis sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At -c "SELECT COUNT(*) FROM gold.aoi_ethiopia;"')
if [ "$PG_CHECK" != "1" ]; then
  echo "FAIL: Expected 1 row, got $PG_CHECK"
  exit 1
fi
echo "✓ gold.aoi_ethiopia has 1 row"

# Step 3: Update mapfile with aoi layer (idempotent)
echo ""
echo "Step 3: Adding aoi layer to mapfile..."
if ! grep -q 'NAME "aoi"' infra/mapserver/mapfiles/tsird.map; then
  # Remove final END, add layer, restore END
  head -n -1 infra/mapserver/mapfiles/tsird.map > /tmp/tsird_map_tmp.map
  
  cat >> /tmp/tsird_map_tmp.map << 'MAPLAYER'
  LAYER
  NAME "aoi"
  TYPE POLYGON
  STATUS ON
  CONNECTIONTYPE POSTGIS
  CONNECTION "host=tsird-postgis dbname=tsird user=tsird password=change_me_strong port=5432"
  DATA "geom FROM gold.aoi_ethiopia USING UNIQUE aoi_id USING SRID=4326"
  METADATA
    "wms_title" "Area of Interest"
    "wms_enable_request" "*"
    "wms_srs" "EPSG:4326 EPSG:20137 EPSG:3857"
  END
  CLASS
    STYLE
      COLOR 255 255 0
      OPACITY 50
    END
  END
  END

END
MAPLAYER
  
  mv /tmp/tsird_map_tmp.map infra/mapserver/mapfiles/tsird.map
  echo "✓ Mapfile updated with aoi layer"
else
  echo "✓ aoi layer already exists"
fi

# Step 4: Restart MapServer
echo ""
echo "Step 4: Restarting tsird-mapserver..."
docker compose --env-file .env.tsird restart tsird-mapserver > /dev/null 2>&1
sleep 3
echo "✓ MapServer restarted"

# Step 5: Verify GetCapabilities
echo ""
echo "Step 5: Verifying GetCapabilities..."
CAPS=/tmp/tsird_caps_aoi.xml
curl -s --fail "http://127.0.0.1:18080/map/ogc?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetCapabilities" -o "$CAPS"
if ! grep -q '<Name>aoi</Name>' "$CAPS"; then
  echo "FAIL: <Name>aoi</Name> not found in GetCapabilities"
  head -n 30 "$CAPS"
  exit 1
fi
echo "✓ GetCapabilities includes aoi layer"

# Step 6: GetMap for EPSG:4326
echo ""
echo "Step 6: GetMap for EPSG:4326..."
IMG_4326=/tmp/aoi_4326.png
BBOX_4326="32.99,3.40,47.99,14.89"
curl -s --fail "http://127.0.0.1:18080/map/ogc?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetMap&LAYERS=aoi&STYLES=&CRS=EPSG:4326&BBOX=${BBOX_4326}&WIDTH=512&HEIGHT=512&FORMAT=image/png" -o "$IMG_4326"
sig=$(head -c8 "$IMG_4326" | od -An -tx1 | tr -d ' \n')
if [ "$sig" != "89504e470d0a1a0a" ]; then
  echo "FAIL: EPSG:4326 GetMap did not return PNG (signature=$sig)"
  head -n 25 "$IMG_4326"
  exit 1
fi
echo "✓ GetMap EPSG:4326 returned PNG → $IMG_4326"

# Step 7: GetMap for EPSG:20137
echo ""
echo "Step 7: GetMap for EPSG:20137..."
IMG_20137=/tmp/aoi_20137.png
BBOX_20137="-161882,376388,1495282,1645935"
curl -s --fail "http://127.0.0.1:18080/map/ogc?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetMap&LAYERS=aoi&STYLES=&CRS=EPSG:20137&BBOX=${BBOX_20137}&WIDTH=512&HEIGHT=512&FORMAT=image/png" -o "$IMG_20137"
sig=$(head -c8 "$IMG_20137" | od -An -tx1 | tr -d ' \n')
if [ "$sig" != "89504e470d0a1a0a" ]; then
  echo "FAIL: EPSG:20137 GetMap did not return PNG (signature=$sig)"
  head -n 25 "$IMG_20137"
  exit 1
fi
echo "✓ GetMap EPSG:20137 returned PNG → $IMG_20137"

echo ""
echo "=========================================="
echo "✓ ALL TESTS PASSED"
echo "=========================================="
echo "PostGIS table: gold.aoi_ethiopia (1 row)"
echo "WMS layer: aoi (yellow transparent polygon)"
echo "CRS supported: EPSG:4326, EPSG:20137, EPSG:3857"
echo ""
exit 0
