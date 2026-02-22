#!/bin/bash
# tsird-wms-validate.sh - Comprehensive WMS validation for TSIRD MapServer GetFeatureInfo
# Tests map parsing, GetCapabilities, GetMap, and GetFeatureInfo functionality
# Usage: ./tsird-wms-validate.sh [wms_url] [layer_name] [info_format]
# Example: ./tsird-wms-validate.sh "http://127.0.0.1:18080/map/ogc" "ethiopia_zones" "text/plain"

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

# Configuration
WMS_URL="${1:-http://127.0.0.1:18080/map/ogc?map=/etc/mapserver/tsird.map}"
TEST_LAYER="${2:-ethiopia_zones}"
INFO_FORMAT="${3:-text/plain}"

# Reference CRS, version, and raw extent (minX, minY, maxX, maxY)
REF_CRS="EPSG:4326"
WMS_VERSION="1.3.0"
MIN_X=33.0
MIN_Y=3.0
MAX_X=48.0
MAX_Y=15.5

# Build BBOX with correct coordinate order based on CRS and VERSION
MAP_EXTENT=$(build_bbox "$MIN_X" "$MIN_Y" "$MAX_X" "$MAX_Y" "$REF_CRS" "$WMS_VERSION")

# Test result tracking
TESTS_PASSED=0
TESTS_FAILED=0

echo "=========================================="
echo "TSIRD WMS Validation Test Suite"
echo "=========================================="
echo "WMS URL: $WMS_URL"
echo "Test Layer: $TEST_LAYER"
echo "Info Format: $INFO_FORMAT"
echo "CRS: $REF_CRS"
echo "WMS Version: $WMS_VERSION"
echo "Map Extent (auto-formatted): $MAP_EXTENT"
echo ""

# Helper functions
log_test() {
  echo "[TEST] $1"
}

log_pass() {
  echo "  [✓ PASS] $1"
  ((TESTS_PASSED++))
}

log_fail() {
  echo "  [✗ FAIL] $1"
  ((TESTS_FAILED++))
}

log_info() {
  echo "  [i] $1"
}

# Test 1: MapServer connectivity
log_test "MapServer connectivity"
HTTP_HEADERS=$(mktemp)
HTTP_RESPONSE=$(mktemp)
curl -sS -D "$HTTP_HEADERS" "${WMS_URL}&service=WMS&request=GetCapabilities&version=1.3.0" > "$HTTP_RESPONSE" 2>&1

# Extract HTTP status code from first line of headers (e.g., "HTTP/1.1 200 OK")
HTTP_STATUS=$(head -1 "$HTTP_HEADERS" | awk '{print $2}')

# Check for HTTP 200 AND (valid XML tag OR XML content-type header)
if [ "$HTTP_STATUS" = "200" ] && \
   (grep -q '<WMS_Capabilities\|<WMT_MS_Capabilities' "$HTTP_RESPONSE" 2>/dev/null || \
    grep -qi 'content-type.*xml' "$HTTP_HEADERS" 2>/dev/null); then
  log_pass "MapServer responds to GetCapabilities"
else
  log_fail "MapServer not responding at $WMS_URL (HTTP $HTTP_STATUS)"
  rm "$HTTP_HEADERS" "$HTTP_RESPONSE"
  exit 1
fi
rm "$HTTP_HEADERS"

# Test 2: GetCapabilities request
log_test "GetCapabilities parsing"
GETCAP_RESPONSE="$HTTP_RESPONSE"

# Check for valid WMS XML
if grep -q "WMS_Capabilities" "$GETCAP_RESPONSE"; then
  log_pass "Valid WMS GetCapabilities response"
else
  log_fail "Invalid GetCapabilities response"
  rm "$GETCAP_RESPONSE"
  exit 1
fi

# Test 3: Layer advertisement
log_test "Layer advertisement in GetCapabilities"
if grep -q "<Name>$TEST_LAYER</Name>" "$GETCAP_RESPONSE"; then
  log_pass "Layer '$TEST_LAYER' advertised in GetCapabilities"
else
  log_fail "Layer '$TEST_LAYER' not found in GetCapabilities"
  rm "$GETCAP_RESPONSE"
  exit 1
fi

# Test 4: CRS advertisement
log_test "CRS advertisement"
if grep -q "EPSG:4326" "$GETCAP_RESPONSE"; then
  log_pass "EPSG:4326 advertised in WMS"
else
  log_fail "EPSG:4326 not advertised in WMS"
fi

if grep -q "EPSG:3857" "$GETCAP_RESPONSE"; then
  log_pass "EPSG:3857 advertised in WMS"
else
  log_fail "EPSG:3857 not advertised in WMS"
fi

rm "$GETCAP_RESPONSE"

# Test 5: GetMap request (basic rendering test)
log_test "GetMap request (WMS 1.3.0 with CRS parameter)"
MAP_RESPONSE=$(mktemp)
curl -s "${WMS_URL}&service=WMS&version=1.3.0&request=GetMap&layers=${TEST_LAYER}&crs=${REF_CRS}&bbox=${MAP_EXTENT}&width=256&height=256&format=image/png" > "$MAP_RESPONSE"

if file "$MAP_RESPONSE" | grep -q "PNG image"; then
  log_pass "GetMap returns valid PNG image"
  log_info "Image size: $(stat -c%s "$MAP_RESPONSE" 2>/dev/null || stat -f%z "$MAP_RESPONSE") bytes"
else
  LOG_CONTENT=$(head -c 200 "$MAP_RESPONSE" | head -c 100)
  log_fail "GetMap did not return valid PNG (got: $LOG_CONTENT...)"
fi

rm "$MAP_RESPONSE"

# Test 6: GetFeatureInfo request (main test)
log_test "GetFeatureInfo request (WMS 1.3.0 with I/J parameters)"
GFI_RESPONSE=$(mktemp)

# WMS 1.3.0 uses I/J for pixel coordinates (default: center of image)
QUERY_LAYERS_PARAM="&query_layers=${TEST_LAYER}"

# Request GetFeatureInfo with click at image center
curl -s -G \
  --data-urlencode "service=WMS" \
  --data-urlencode "version=1.3.0" \
  --data-urlencode "request=GetFeatureInfo" \
  --data-urlencode "layers=${TEST_LAYER}" \
  --data-urlencode "query_layers=${TEST_LAYER}" \
  --data-urlencode "crs=${REF_CRS}" \
  --data-urlencode "bbox=${MAP_EXTENT}" \
  --data-urlencode "width=256" \
  --data-urlencode "height=256" \
  --data-urlencode "i=128" \
  --data-urlencode "j=128" \
  --data-urlencode "info_format=${INFO_FORMAT}" \
  "${WMS_URL}" > "$GFI_RESPONSE"

if [ -s "$GFI_RESPONSE" ]; then
  log_pass "GetFeatureInfo returns non-empty response"
  log_info "Response size: $(stat -c%s "$GFI_RESPONSE" 2>/dev/null || stat -f%z "$GFI_RESPONSE") bytes"
  
  # Test 7: GetFeatureInfo content validation (layer-specific)
  log_test "GetFeatureInfo attribute validation"
  
  case "$TEST_LAYER" in
    "ethiopia_zones")
      if grep -qi "ZONES\|AREA\|PERIMETER" "$GFI_RESPONSE"; then
        log_pass "Found expected fields: ZONES, AREA, PERIMETER"
      else
        log_fail "Expected fields not found in GetFeatureInfo response"
      fi
      ;;
    "ethiopia_woredas")
      if grep -qi "W_NAME\|Pop_04\|Pop_Den" "$GFI_RESPONSE"; then
        log_pass "Found expected fields: W_NAME, Pop_04, Pop_Den"
      else
        log_fail "Expected fields not found in GetFeatureInfo response"
      fi
      ;;
    "ethiopia_admin")
      if grep -qi "NAME1\|NAME2\|COUNTRY" "$GFI_RESPONSE"; then
        log_pass "Found expected fields: NAME1, NAME2, COUNTRY"
      else
        log_fail "Expected fields not found in GetFeatureInfo response"
      fi
      ;;
    *)
      log_info "Layer-specific validation not defined for $TEST_LAYER"
      ;;
  esac
  
  # Test 8: Inspect GetFeatureInfo output
  log_test "GetFeatureInfo output inspection"
  log_info "First 300 chars of response:"
  head -c 300 "$GFI_RESPONSE" | sed 's/^/    /'
  
else
  log_fail "GetFeatureInfo returned empty response"
fi

rm "$GFI_RESPONSE"

# Test 9: Multiple format support
log_test "Alternative GetFeatureInfo formats"
for fmt in "text/plain" "text/html" "application/json"; do
  ALT_RESPONSE=$(mktemp)
  HTTP_CODE=$(curl -s -w "%{http_code}" -o "$ALT_RESPONSE" \
    "${WMS_URL}&service=WMS&version=1.3.0&request=GetFeatureInfo&layers=${TEST_LAYER}&query_layers=${TEST_LAYER}&crs=${REF_CRS}&bbox=${MAP_EXTENT}&width=256&height=256&i=128&j=128&info_format=${fmt}")
  
  if [ "$HTTP_CODE" = "200" ] && [ -s "$ALT_RESPONSE" ]; then
    log_pass "Format $fmt supported"
  else
    log_fail "Format $fmt returned HTTP $HTTP_CODE or empty response"
  fi
  rm "$ALT_RESPONSE"
done

echo ""
echo "=========================================="
echo "Test Results Summary"
echo "=========================================="
echo "Passed: $TESTS_PASSED"
echo "Failed: $TESTS_FAILED"
echo "Total:  $(($TESTS_PASSED + $TESTS_FAILED))"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
  echo "✓ All tests passed!"
  exit 0
else
  echo "✗ Some tests failed. Review output above."
  exit 1
fi
