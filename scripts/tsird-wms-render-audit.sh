#!/bin/bash
# tsird-wms-render-audit.sh
# Deterministic WMS layer render audit script
# Pulls all layers from GetCapabilities and tests GetMap rendering
# Exit code: 0 if all layers pass, 1 if any fail

WMS_URL="${1:-http://127.0.0.1:18080/map/ogc?map=/etc/mapserver/tsird.map}"
AUDIT_DIR="/tmp/tsird_render_audit"
BBOX="3.0,33.0,15.5,48.0"  # lat,lon order for EPSG:4326
CRS="EPSG:4326"
VERSION="1.3.0"

mkdir -p "$AUDIT_DIR"

echo "=========================================="
echo "TSIRD WMS Render Audit"
echo "=========================================="
echo "WMS URL: $WMS_URL"
echo "CRS: $CRS, BBOX: $BBOX"
echo "Output: $AUDIT_DIR"
echo ""

# Get GetCapabilities
CAPS=$(curl -sS "${WMS_URL}&service=WMS&request=GetCapabilities&version=${VERSION}")

# Extract all layer names (including parent), filter out non-data layers
ALL_NAMES=$(echo "$CAPS" | grep -o '<Name>[^<]*</Name>' | sed 's/<Name>//;s/<\/Name>//')

# Keep only layers that are queryable/renderable (skip parent "tsird" and service-level)
LAYER_NAMES=$(echo "$ALL_NAMES" | grep -v '^tsird$' | sort -u)

PASS_COUNT=0
FAIL_COUNT=0
declare -a RESULTS

echo "[TEST] Testing GetMap for each layer..."
echo ""

while IFS= read -r layer; do
  [ -z "$layer" ] && continue
  
  # Skip service-level entries
  if [ "$layer" = "WMS" ] || [ "$layer" = "tsird" ]; then
    continue
  fi

  png_file="$AUDIT_DIR/${layer}.png"
  
  # Request GetMap
  http_code=$(curl -sS -w "%{http_code}" -o "$png_file" \
    "${WMS_URL}&service=WMS&version=${VERSION}&request=GetMap&layers=${layer}&crs=${CRS}&bbox=${BBOX}&width=800&height=600&styles=&format=image/png")
  
  # Check result
  status="FAIL"
  reason=""
  
  if [ "$http_code" != "200" ]; then
    status="FAIL"
    reason="HTTP ${http_code}"
  elif [ ! -f "$png_file" ]; then
    status="FAIL"
    reason="No response file"
  elif grep -q "ServiceException" "$png_file" 2>/dev/null; then
    status="FAIL"
    # Extract exception message
    exc=$(grep -o '<ServiceException[^>]*>[^<]*' "$png_file" | sed 's/<ServiceException[^>]*>//' | head -1 || echo "Unknown error")
    reason="Exception: ${exc:0:50}"
  elif ! file "$png_file" | grep -q "PNG image"; then
    status="FAIL"
    size=$(stat -c%s "$png_file" 2>/dev/null || stat -f%z "$png_file" 2>/dev/null || echo "0")
    reason="Not PNG (${size}b)"
  else
    size=$(stat -c%s "$png_file" 2>/dev/null || stat -f%z "$png_file" 2>/dev/null || echo "0")
    if [ "$size" -lt 1024 ]; then
      status="FAIL"
      reason="Blank/small (${size}b)"
    else
      status="PASS"
      reason="OK"
    fi
  fi
  
  # Store result
  RESULTS+=("$layer|$status|$reason")
  
  if [ "$status" = "PASS" ]; then
    echo "  [✓] $layer"
    ((PASS_COUNT++))
  else
    echo "  [✗] $layer → $reason"
    ((FAIL_COUNT++))
  fi
done <<< "$LAYER_NAMES"

echo ""
echo "=========================================="
echo "Render Audit Results"
echo "=========================================="
echo "Total Layers: $((PASS_COUNT + FAIL_COUNT))"
echo "Passed: $PASS_COUNT"
echo "Failed: $FAIL_COUNT"
echo ""

if [ $FAIL_COUNT -gt 0 ]; then
  echo "[DETAILED RESULTS]"
  echo "Layer | Status | Details"
  echo "------|--------|--------"
  for result in "${RESULTS[@]}"; do
    IFS='|' read -r layer status reason <<< "$result"
    printf "%-35s | %-6s | %s\n" "$layer" "$status" "$reason"
  done
  echo ""
  echo "FAILED LAYERS:"
  for result in "${RESULTS[@]}"; do
    IFS='|' read -r layer status reason <<< "$result"
    if [ "$status" = "FAIL" ]; then
      echo "  - $layer: $reason"
    fi
  done
  exit 1
else
  echo "✓ All layers render successfully!"
  exit 0
fi
