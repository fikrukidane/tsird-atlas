#!/bin/bash
# TSIRD Vector Normalization to EPSG:4326 - Simplified Version
# Uses tsird-etl container (has GDAL + writable /data mount)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
 RAW_VECTORS_DIR="${PROJECT_ROOT}/data/raw/vectors"
NORMALIZED_VECTORS_DIR="${PROJECT_ROOT}/data/normalized/vectors4326"

mkdir -p "$NORMALIZED_VECTORS_DIR"
docker exec tsird-etl mkdir -p /data/normalized/vectors4326 2>/dev/null || true

LOG="${PROJECT_ROOT}/data/normalized/normalize_4326.log"
> "$LOG"

echo "=== TSIRD Vector Normalization to EPSG:4326 ==="
echo "Start: $(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$LOG"
echo ""

TOTAL=0
SUCCESS=0
FAILED=0

for shp in "$RAW_VECTORS_DIR"/*.shp; do
  [ -f "$shp" ] || continue
  
  base=$(basename "$shp" .shp)
  TOTAL=$((TOTAL + 1))
  
  echo -n "[$TOTAL] $base ... "
  
  # Use gdalsrsinfo for robust CRS detection
  epsg=$(docker exec tsird-etl gdalsrsinfo "/data/raw/vectors/${base}.shp" 2>/dev/null | grep -oP 'EPSG:\d+' | head -1 || echo "UNKNOWN")
  
  if [ "$epsg" = "UNKNOWN" ] || [ -z "$epsg" ]; then
    echo "UNKNOWN_CRS - copying as-is"
    epsg_flag=""
  elif [ "$epsg" = "EPSG:4326" ]; then
    echo "Already EPSG:4326 - copying"
    epsg_flag=""
  else
    echo "Reprojecting $epsg → EPSG:4326"
    epsg_flag="-t_srs EPSG:4326"
  fi
  
  # Run ogr2ogr
  if docker exec tsird-etl ogr2ogr -f "ESRI Shapefile" \
      $epsg_flag \
      -lco ENCODING=UTF-8 \
      "/data/normalized/vectors4326/${base}_4326.shp" \
      "/data/raw/vectors/${base}.shp" \
      >> "$LOG" 2>&1; then
    echo "  ✓ Success"
    SUCCESS=$((SUCCESS + 1))
  else
    echo "  ✗ FAILED"
    FAILED=$((FAILED + 1))
  fi
done

echo ""
echo "=== Summary ==="
echo "Total: $TOTAL | Success: $SUCCESS | Failed: $FAILED"
echo "Output: $NORMALIZED_VECTORS_DIR"
echo "Log: $LOG"

[ "$FAILED" -gt 0 ] && exit 1 || exit 0
