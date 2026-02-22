#!/bin/bash
# TSIRD Vector Data Normalization to EPSG:4326
# Purpose: Reproject all raw shapefiles to canonical EPSG:4326 with geometry cleanup
# Input: data/raw/vectors/*.shp
# Output: data/normalized/vectors4326/*.shp (with _4326 suffix)
# Container: Uses tsird-etl container (has GDAL + writable /data mount)

set -eo pipefail  # Removed -u to allow unset variables temporarily for debugging

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
RAW_VECTORS_DIR="${PROJECT_ROOT}/data/raw/vectors"
NORMALIZED_VECTORS_DIR="${PROJECT_ROOT}/data/normalized/vectors4326"
CONTAINER_NAME="tsird-etl"

# Container-side paths
CONTAINER_RAW="/data/raw/vectors"
CONTAINER_NORMALIZED="/data/normalized/vectors4326"

# Ensure output directory exists on host
mkdir -p "$NORMALIZED_VECTORS_DIR"

# Create directory in container
docker exec "$CONTAINER_NAME" mkdir -p "$CONTAINER_NORMALIZED" 2>/dev/null || true

# Counters
TOTAL=0
SUCCESS=0
SKIPPED=0
FAILED=0

# Log file
NORMALIZE_LOG="${PROJECT_ROOT}/data/normalized/normalize_4326.log"
> "$NORMALIZE_LOG"

echo "=== TSIRD Vector Normalization to EPSG:4326 ==="
echo "Start time: $(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$NORMALIZE_LOG"
echo "Raw vectors: $RAW_VECTORS_DIR"
echo "Output: $NORMALIZED_VECTORS_DIR"
echo "Container: $CONTAINER_NAME"
echo ""

# Process each shapefile
for shp_file in "$RAW_VECTORS_DIR"/*.shp; do
  [ -f "$shp_file" ] || continue
  
  ((TOTAL++))
  basename=$(basename "$shp_file" .shp)
  output_basename="${basename}_4326"
  
  # Container paths
  container_shp="${CONTAINER_RAW}/${basename}.shp"
  container_output="${CONTAINER_NORMALIZED}/${output_basename}.shp"
  
  echo -n "[$TOTAL] Processing: $basename ... "
  
  # For shapefiles, layer name is typically the basename
  layer_name="$basename"
  
  # Detect CRS using ogrinfo with layer name (allow failures)
  set +e
  crs_code=$(docker exec "$CONTAINER_NAME" /bin/sh -c "
    ogrinfo -so '$container_shp' '$layer_name' 2>&1 | grep -oE 'EPSG\",[ ]*[0-9]+' | head -1 | grep -oE '[0-9]+'
  " 2>&1)
  crs_exit=$?
  set -e
  
  # Handle empty or failed detection
  if [ "$crs_exit" -ne 0 ] || [ -z "$crs_code" ]; then
    detected_crs="UNKNOWN"
  else
    detected_crs="EPSG:${crs_code}"
  fi
  
  # Run ogr2ogr based on detected CRS
  if [ "$detected_crs" = "UNKNOWN" ]; then
    echo "UNKNOWN_CRS"
    
    # Copy with validation only (no reprojection)
    set +e
    docker exec "$CONTAINER_NAME" /bin/sh -c "
      ogr2ogr -f 'ESRI Shapefile' \
        -lco ENCODING=UTF-8 \
        '$container_output' '$container_shp' \
        2>&1
    " >> "$NORMALIZE_LOG" 2>&1
    ogr_exit=$?
    set -e
    
    if [ "$ogr_exit" -eq 0 ]; then
      echo "  ✓ Copied (with validation) → $output_basename.shp"
      ((SUCCESS++))
      ((SKIPPED++))
    else
      echo "  ✗ FAILED"
      echo "$basename: ogr2ogr copy failed" >> "$NORMALIZE_LOG"
      ((FAILED++))
    fi
  
  elif [ "$detected_crs" = "EPSG:4326" ]; then
    echo "ALREADY_4326"
    
    # Validate and copy (no reprojection needed)
    set +e
    docker exec "$CONTAINER_NAME" /bin/sh -c "
      ogr2ogr -f 'ESRI Shapefile' \
        -lco ENCODING=UTF-8 \
        '$container_output' '$container_shp' \
        2>&1
    " >> "$NORMALIZE_LOG" 2>&1
    ogr_exit=$?
    set -e
    
    if [ "$ogr_exit" -eq 0 ]; then
      echo "  ✓ Validated and copied → $output_basename.shp"
      ((SUCCESS++))
    else
      echo "  ✗ FAILED"
      echo "$basename: ogr2ogr validation copy failed" >> "$NORMALIZE_LOG"
      ((FAILED++))
    fi
  
  else
    echo "Reprojecting from $detected_crs → EPSG:4326"
    
    # Reproject to EPSG:4326
    set +e
    docker exec "$CONTAINER_NAME" /bin/sh -c "
      ogr2ogr -f 'ESRI Shapefile' \
        -s_srs '$detected_crs' \
        -t_srs 'EPSG:4326' \
        -lco ENCODING=UTF-8 \
        '$container_output' '$container_shp' \
        2>&1
    " >> "$NORMALIZE_LOG" 2>&1
    ogr_exit=$?
    set -e
    
    if [ "$ogr_exit" -eq 0 ]; then
      echo "  ✓ Reprojected → $output_basename.shp"
      ((SUCCESS++))
    else
      echo "  ✗ FAILED"
      echo "$basename: ogr2ogr reprojection failed from $detected_crs" >> "$NORMALIZE_LOG"
      ((FAILED++))
    fi
  fi
done

echo ""
echo "=== Normalization Summary ==="
echo "Total processed: $TOTAL"
echo "Successful: $SUCCESS"
echo "Skipped (UNKNOWN_CRS): $SKIPPED"
echo "Failed: $FAILED"
echo "End time: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo ""
echo "Output directory: $NORMALIZED_VECTORS_DIR"
echo "Log file: $NORMALIZE_LOG"
echo ""

# Exit with failure if any failed
if [ "$FAILED" -gt 0 ]; then
  echo "⚠ Normalization completed with $FAILED failures. See log for details."
  exit 1
else
  echo "✓ Normalization complete!"
  exit 0
fi
