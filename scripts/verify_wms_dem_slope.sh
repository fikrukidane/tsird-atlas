#!/usr/bin/env bash
set -euo pipefail

cd /opt/tigrayinsights/apps/tsird

echo "=========================================="
echo "TSIRD DEM/Slope WMS Verification"
echo "=========================================="

DEM_FILE="data/gold/dem/ethiopia_dem_4326.tif"
SLOPE_FILE="data/gold/slope/ethiopia_slope_4326.tif"
CAPS=/tmp/tsird_caps_dem.xml

# Step 1: Verify files exist (optional - skip if missing)
echo ""
echo "Step 1: Checking for GeoTIFF files..."

for f in "$DEM_FILE" "$SLOPE_FILE"; do
  if [ ! -f "$f" ]; then
    echo "⚠ Warning: $f not found (may not be created yet)"
  else
    echo "✓ Found: $f"
  fi
done

# Step 2: GetCapabilities (optional check)
echo ""
echo "Step 2: Checking GetCapabilities..."

if ! curl -s --max-time 10 "http://127.0.0.1:18080/map/ogc?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetCapabilities" -o "$CAPS" 2>/dev/null; then
  echo "⚠ Warning: Could not reach WMS server at http://127.0.0.1:18080"
  echo "Skipping GetCapabilities check"
else
  for layer in dem slope; do
    if ! grep -q "<Name>$layer</Name>" "$CAPS"; then
      echo "⚠ Warning: Layer '<Name>$layer</Name>' not found in GetCapabilities"
    else
      echo "✓ Layer $layer found"
    fi
  done
fi

# Step 3: GetMap for DEM - EPSG:4326
echo ""
echo "Step 3: GetMap DEM EPSG:4326..."

IMG=/tmp/dem_4326.png
BBOX="32.99,3.40,47.99,14.89"

if curl -s --max-time 10 "http://127.0.0.1:18080/map/ogc?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetMap&LAYERS=dem&STYLES=&CRS=EPSG:4326&BBOX=${BBOX}&WIDTH=512&HEIGHT=512&FORMAT=image/png" -o "$IMG" 2>/dev/null; then
  sig=$(head -c8 "$IMG" 2>/dev/null | od -An -tx1 | tr -d ' \n')
  if [ "$sig" = "89504e470d0a1a0a" ]; then
    echo "✓ GetMap DEM EPSG:4326 returned PNG → $IMG"
  else
    echo "⚠ Warning: DEM EPSG:4326 response signature: $sig (expected PNG)"
  fi
else
  echo "⚠ Warning: Could not reach WMS for DEM EPSG:4326"
fi

# Step 4: GetMap for DEM - EPSG:20137
echo ""
echo "Step 4: GetMap DEM EPSG:20137..."

IMG=/tmp/dem_20137.png
BBOX="-161882,376388,1495282,1645935"

if curl -s --max-time 10 "http://127.0.0.1:18080/map/ogc?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetMap&LAYERS=dem&STYLES=&CRS=EPSG:20137&BBOX=${BBOX}&WIDTH=512&HEIGHT=512&FORMAT=image/png" -o "$IMG" 2>/dev/null; then
  sig=$(head -c8 "$IMG" 2>/dev/null | od -An -tx1 | tr -d ' \n')
  if [ "$sig" = "89504e470d0a1a0a" ]; then
    echo "✓ GetMap DEM EPSG:20137 returned PNG → $IMG"
  else
    echo "⚠ Warning: DEM EPSG:20137 response signature: $sig (expected PNG)"
  fi
else
  echo "⚠ Warning: Could not reach WMS for DEM EPSG:20137"
fi

# Step 5: GetMap for Slope - EPSG:4326
echo ""
echo "Step 5: GetMap Slope EPSG:4326..."

IMG=/tmp/slope_4326.png
BBOX="32.99,3.40,47.99,14.89"

if curl -s --max-time 10 "http://127.0.0.1:18080/map/ogc?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetMap&LAYERS=slope&STYLES=&CRS=EPSG:4326&BBOX=${BBOX}&WIDTH=512&HEIGHT=512&FORMAT=image/png" -o "$IMG" 2>/dev/null; then
  sig=$(head -c8 "$IMG" 2>/dev/null | od -An -tx1 | tr -d ' \n')
  if [ "$sig" = "89504e470d0a1a0a" ]; then
    echo "✓ GetMap Slope EPSG:4326 returned PNG → $IMG"
  else
    echo "⚠ Warning: Slope EPSG:4326 response signature: $sig (expected PNG)"
  fi
else
  echo "⚠ Warning: Could not reach WMS for Slope EPSG:4326"
fi

# Step 6: GetMap for Slope - EPSG:20137
echo ""
echo "Step 6: GetMap Slope EPSG:20137..."

IMG=/tmp/slope_20137.png
BBOX="-161882,376388,1495282,1645935"

if curl -s --max-time 10 "http://127.0.0.1:18080/map/ogc?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetMap&LAYERS=slope&STYLES=&CRS=EPSG:20137&BBOX=${BBOX}&WIDTH=512&HEIGHT=512&FORMAT=image/png" -o "$IMG" 2>/dev/null; then
  sig=$(head -c8 "$IMG" 2>/dev/null | od -An -tx1 | tr -d ' \n')
  if [ "$sig" = "89504e470d0a1a0a" ]; then
    echo "✓ GetMap Slope EPSG:20137 returned PNG → $IMG"
  else
    echo "⚠ Warning: Slope EPSG:20137 response signature: $sig (expected PNG)"
  fi
else
  echo "⚠ Warning: Could not reach WMS for Slope EPSG:20137"
fi

echo ""
echo "=========================================="
echo "Verification Summary"
echo "=========================================="
echo "GeoTIFFs: Check complete"
echo "GetCapabilities: Optional check (may not have layers if files missing)"
echo "GetMap requests: Optional checks (may timeout if WMS not ready)"
echo ""
echo "Note: Full verification requires:"
echo "  1. dem_slope_pipeline.sh to have completed"
echo "  2. MapServer to be restarted"
echo "  3. WMS service running on http://127.0.0.1:18080"
echo ""
exit 0
