#!/bin/bash
# tsird-verify-wms-proxy.sh
# Verification script for WMS proxy through port 18080
# Tests that nginx correctly proxies WMS GetCapabilities request to MapServer
#
# Exit codes:
#   0 = all checks passed
#   1 = one or more checks failed
#
# Usage: ./tsird-verify-wms-proxy.sh [base_url]
# Example: ./tsird-verify-wms-proxy.sh "http://127.0.0.1:18080"

set -e

BASE_URL="${1:-http://127.0.0.1:18080}"
WMS_ENDPOINT="${BASE_URL}/map/ogc"

HEADERS_FILE=$(mktemp)
RESPONSE_FILE=$(mktemp)

cleanup() {
  rm -f "$HEADERS_FILE" "$RESPONSE_FILE"
}
trap cleanup EXIT

echo "=========================================="
echo "WMS Proxy Verification"
echo "=========================================="
echo "Endpoint: $WMS_ENDPOINT"
echo ""

# Test GetCapabilities request
echo "[1/4] Sending GetCapabilities request..."
HTTP_CODE=$(curl -sS -D "$HEADERS_FILE" \
  "${WMS_ENDPOINT}?service=WMS&request=GetCapabilities&version=1.3.0" \
  > "$RESPONSE_FILE" 2>&1; echo $?)

if [ "$HTTP_CODE" -eq 0 ]; then
  echo "  ✓ Request completed"
else
  echo "  ✗ FAIL: curl exited with code $HTTP_CODE"
  cleanup
  exit 1
fi

# Check HTTP status code
echo "[2/4] Checking HTTP status code..."
STATUS=$(head -1 "$HEADERS_FILE" | awk '{print $2}')
if [ "$STATUS" = "200" ]; then
  echo "  ✓ HTTP 200 OK"
else
  echo "  ✗ FAIL: Expected HTTP 200, got $STATUS"
  echo "  Headers:"
  cat "$HEADERS_FILE" | head -10
  cleanup
  exit 1
fi

# Check Content-Type header
echo "[3/4] Checking Content-Type header..."
CONTENT_TYPE=$(grep -i "^content-type:" "$HEADERS_FILE" | cut -d' ' -f2- | tr -d '\r')
if echo "$CONTENT_TYPE" | grep -qi "xml"; then
  echo "  ✓ Content-Type contains 'xml': $CONTENT_TYPE"
else
  echo "  ✗ FAIL: Content-Type is not XML"
  echo "  Actual: $CONTENT_TYPE"
  cleanup
  exit 1
fi

# Check response contains WMS Capabilities XML
echo "[4/4] Checking WMS Capabilities XML structure..."
if grep -q "<WMS_Capabilities\|<WMT_MS_Capabilities" "$RESPONSE_FILE"; then
  echo "  ✓ Response contains WMS Capabilities XML"
else
  echo "  ✗ FAIL: Response does not contain WMS Capabilities XML"
  echo "  First 500 chars of response:"
  head -c 500 "$RESPONSE_FILE"
  echo ""
  cleanup
  exit 1
fi

# All checks passed
echo ""
echo "=========================================="
echo "✓ All verification checks PASSED"
echo "=========================================="
exit 0
