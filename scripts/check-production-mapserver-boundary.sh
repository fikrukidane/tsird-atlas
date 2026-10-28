#!/usr/bin/env bash
# Verify that the production MapServer publication set cannot advertise
# development-only drought layers.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
base="$root/infra/mapserver/mapfiles"
production="$root/infra/production-mapserver/mapfiles"

require_same() {
  local expected="$1"
  local actual="$2"
  if ! cmp -s "$expected" "$actual"; then
    echo "FAIL: production mapfile copy is out of sync: $actual" >&2
    exit 1
  fi
}

require_same "$base/tsird.map" "$production/tsird.map"
test -s "$production/dummy.html"
require_same \
  "$base/includes/drought_public_rasters.map" \
  "$production/includes/drought_public_rasters.map"
require_same \
  "$base/includes/vectors_public.map" \
  "$production/includes/vectors_gold.map"

if grep -Eqi 'tigray_drought_.*_dev|hls_ndmi|sentinel2_ndmi' "$production"/includes/*.map; then
  echo "FAIL: development drought layer found in production MapServer publication set" >&2
  exit 1
fi

echo "PASS: production MapServer publication set contains no development drought layers."
