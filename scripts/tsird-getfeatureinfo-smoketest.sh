#!/bin/bash
set -euo pipefail

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

BASE_URL="http://127.0.0.1:18080/map/ogc"
LAYER="ethiopia_zones"
EXPECTED_FIELD="ZONES"
LAYER="$(printf '%s' "$LAYER" | tr -d '\r\n' | xargs)"

CAPS_URL="${BASE_URL}?SERVICE=WMS&REQUEST=GetCapabilities"
LAYER_NAMES=$(curl -fsS "${CAPS_URL}" \
    | grep -Eo '<Name>[^<]+' \
    | sed 's/<Name>//')
if ! printf '%s\n' "${LAYER_NAMES}" | grep -Fxq "${LAYER}"; then
    echo "Layer not found in GetCapabilities: ${LAYER}" >&2
    exit 1
fi

echo "GetCapabilities OK: ${LAYER}"

# Define raw extent (minX, minY, maxX, maxY in lon,lat)
MIN_X=33.0
MIN_Y=3.0
MAX_X=48.0
MAX_Y=15.5
CRS="EPSG:4326"
VERSION="1.3.0"

# Build BBOX with correct coordinate order based on CRS and VERSION
bbox=$(build_bbox "$MIN_X" "$MIN_Y" "$MAX_X" "$MAX_Y" "$CRS" "$VERSION")
width=800
height=600
i=400
j=300

GFI_URL="${BASE_URL}?SERVICE=WMS&VERSION=${VERSION}&REQUEST=GetFeatureInfo&CRS=${CRS}&BBOX=${bbox}&WIDTH=${width}&HEIGHT=${height}&LAYERS=${LAYER}&QUERY_LAYERS=${LAYER}&I=${i}&J=${j}&INFO_FORMAT=text/plain"
echo "GetFeatureInfo URL: ${GFI_URL}"
response=$(curl -sS "${GFI_URL}")

echo "${response}" | head -60

if echo "${response}" | grep -q "${EXPECTED_FIELD}"; then
    echo "OK"
else
    echo "Missing expected field: ${EXPECTED_FIELD}" >&2
    exit 1
fi
