#!/bin/bash
# tsird-wms-validate-simple.sh
# Simplified WMS validation for TSIRD MapServer testing
# Tests GetCapabilities, GetMap, and GetFeatureInfo with corrected WMS 1.3.0 BBOX order

set -e

# Helper function to build BBOX based on CRS and VERSION
# For WMS 1.3.0 with EPSG:4326, BBOX must be in lat,lon order (minLat,minLon,maxLat,maxLon)
# For other CRS or versions, BBOX is in lon,lat order (minX,minY,maxX,maxY)
build_bbox() {
  local minX="$1" minY="$2" maxX="$3" maxY="$4"
  local crs="${5:-EPSG:4326}"
  local version="${6:-1.3.0}"
  
  if [ "$crs" = "EPSG:4326" ] && [ "$version" = "1.3.0" ]; then
    # WMS 1.3.0 with geographic CRS requires lat,lon order
    echo "${minY},${minX},${maxY},${maxX}"
  else
    # All other cases use lon,lat order
    echo "${minX},${minY},${maxX},${maxY}"
  fi
}

WMS_URL="${1:-http://127.0.0.1:18080/map/ogc?map=/etc/mapserver/tsird.map}"
TEST_LAYER="${2:-ethiopia_zones}"
INFO_FORMAT="${3:-text/plain}"

# Reference CRS and raw extent (minX, minY, maxX, maxY)
REF_CRS="EPSG:4326"
WMS_VERSION="1.3.0"
MIN_X=33.0
MIN_Y=3.0
MAX_X=48.0
MAX_Y=15.5

# Build BBOX with correct coordinate order
BBOX=$(build_bbox "$MIN_X" "$MIN_Y" "$MAX_X" "$MAX_Y" "$REF_CRS" "$WMS_VERSION")

TESTS_PASSED=0
TESTS_FAILED=0

echo "=========================================="
echo "TSIRD WMS Validation Test Suite (Simplified)"
echo "=========================================="
echo "WMS URL: $WMS_URL"
echo "Test Layer: $TEST_LAYER"
echo "CRS: $REF_CRS"
echo "WMS Version: $WMS_VERSION"
echo "BBOX (auto-formatted): $BBOX"
echo ""

#============================================
# Test 1: GetCapabilities
#============================================
echo "[TEST 1] GetCapabilities"
CAPS=$(curl -sS "${WMS_URL}&service=WMS&request=GetCapabilities&version=1.3.0")

if echo "$CAPS" | grep -q "<WMS_Capabilities"; then
  echo "  [✓ PASS] Valid WMS XML"
  ((++TESTS_PASSED))
else
  echo "  [✗ FAIL] Invalid response"
  ((++TESTS_FAILED))
  exit 1
fi

if echo "$CAPS" | grep -q "<Name>$TEST_LAYER</Name>"; then
  echo "  [✓ PASS] Layer '$TEST_LAYER' advertised"
  ((++TESTS_PASSED))
else
  echo "  [✗ FAIL] Layer not found"
  ((++TESTS_FAILED))
  exit 1
fi

#============================================
# Test 2: GetMap
#============================================
echo "[TEST 2] GetMap"
MAP_IMG=$(mktemp)
curl -sS "${WMS_URL}&service=WMS&version=${WMS_VERSION}&request=GetMap&layers=${TEST_LAYER}&crs=${REF_CRS}&bbox=${BBOX}&width=256&height=256&format=image/png" > "$MAP_IMG"

if file "$MAP_IMG" | grep -q "PNG image"; then
  echo "  [✓ PASS] GetMap returns PNG"
  ((++TESTS_PASSED))
else
  echo "  [✗ FAIL] Invalid PNG response"
  ((++TESTS_FAILED))
fi
rm "$MAP_IMG"

#============================================
# Test 3: GetFeatureInfo (with lat,lon BBOX)
#============================================
echo "[TEST 3] GetFeatureInfo (WMS ${WMS_VERSION} with ${REF_CRS})"
GFI=$(curl -sS "${WMS_URL}&service=WMS&version=${WMS_VERSION}&request=GetFeatureInfo&layers=${TEST_LAYER}&query_layers=${TEST_LAYER}&crs=${REF_CRS}&bbox=${BBOX}&width=800&height=600&i=400&j=300&info_format=${INFO_FORMAT}")

if [ -n "$GFI" ]; then
  echo "  [✓ PASS] GetFeatureInfo returns response"
  ((++TESTS_PASSED))
else
  echo  "  [✗ FAIL] Empty response"
  ((++TESTS_FAILED))
  exit 1
fi

# Check for expected fields based on layer
case "$TEST_LAYER" in
  "ethiopia_zones")
    if echo "$GFI" | grep -qi "ZONES\|AREA\|PERIMETER"; then
      echo "  [✓ PASS] Found expected fields (ZONES, AREA, PERIMETER)"
      ((++TESTS_PASSED))
    else
      echo "  [✗ FAIL] Expected fields not found"
      ((++TESTS_FAILED))
    fi
    ;;
  *)
    echo "  [i] Layer-specific validation skipped for $TEST_LAYER"
    ;;
esac

echo ""
echo "GetFeatureInfo response (first 20 lines):"
echo "$GFI" | head -20

#============================================
# Summary
#============================================
echo ""
echo "=========================================="
echo "Test Results"
echo "=========================================="
echo "Passed: $TESTS_PASSED"
echo "Failed: $TESTS_FAILED"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
  echo "✓ ALL TESTS PASSED"
  exit 0
else
  echo "✗ SOME TESTS FAILED"
  exit 1
fi
