#!/bin/bash
# TSIRD Vector Data Verification for EPSG:4326
# Purpose: Validate normalized shapefiles and generate reports
# Input: data/normalized/vectors4326/*.shp
# Output: docs/atlas/normalize_report_4326.md, docs/atlas/normalize_report_4326.csv
# Container: Runs GDAL tools inside tsird-mapserver via docker exec

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
NORMALIZED_VECTORS_DIR="${PROJECT_ROOT}/data/normalized/vectors4326"
DOCS_ATLAS_DIR="${PROJECT_ROOT}/docs/atlas"
CONTAINER_NAME="tsird-etl"

# Container-side paths
CONTAINER_NORMALIZED="/data/normalized/vectors4326"
CONTAINER_RAW="/data/raw/vectors"

# Report files
REPORT_MD="${DOCS_ATLAS_DIR}/normalize_report_4326.md"
REPORT_CSV="${DOCS_ATLAS_DIR}/normalize_report_4326.csv"

# Ensure output directory exists
mkdir -p "$DOCS_ATLAS_DIR"

# Initialize reports
> "$REPORT_MD"
> "$REPORT_CSV"

echo "=== TSIRD Vector Verification for EPSG:4326 ==="
echo "Start time: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "Normalized vectors: $NORMALIZED_VECTORS_DIR"
echo "Reports: $REPORT_MD, $REPORT_CSV"
echo ""

# Write CSV header
echo "layer,source_file,source_crs,normalized_file,normalized_crs,feature_count,extent,status,notes" > "$REPORT_CSV"

# Write MD header
cat > "$REPORT_MD" << 'EOF'
# Vector Normalization Report (EPSG:4326)

Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)

## Summary

Verification of normalized vector datasets (reprojected to EPSG:4326).

## Layer Details

| Layer | Source File | Source CRS | Norm. File | Norm. CRS | Features | Extent | Status | Notes |
|-------|------------|------------|------------|-----------|----------|--------|--------|-------|
EOF

TOTAL=0
OK_COUNT=0
ERROR_COUNT=0

# Process each normalized shapefile
for shp_file in "$NORMALIZED_VECTORS_DIR"/*_4326.shp; do
  [ -f "$shp_file" ] || continue
  
  ((TOTAL++))
  basename=$(basename "$shp_file")
  source_basename=$(basename "$shp_file" _4326.shp)
  source_file="${PROJECT_ROOT}/data/raw/vectors/${source_basename}.shp"
  
  # Container paths
  container_norm="${CONTAINER_NORMALIZED}/${basename}"
  container_src="${CONTAINER_RAW}/${source_basename}.shp"
  
  # Get metadata from normalized file using ogrinfo inside container
  metadata=$(docker exec "$CONTAINER_NAME" /bin/sh -c "
    ogrinfo -so '$container_norm' 2>&1
  " 2>&1 || echo "ERROR")
  
  # Extract feature count
  feature_count=$(echo "$metadata" | grep -oE "Feature Count: [0-9]+" | grep -oE "[0-9]+" 2>/dev/null || echo "0")
  [ -z "$feature_count" ] && feature_count="0"
  
  # Extract extent
  extent=$(echo "$metadata" | grep -E "^\s+Extent:" | head -1 || echo "UNKNOWN")
  extent=$(echo "$extent" | sed 's/^\s*Extent:\s*//' || echo "UNKNOWN")
  
  # Verify CRS is EPSG:4326
  crs_line=$(echo "$metadata" | grep -E "(EPSG|4326)" | head -1 || echo "")
  if echo "$crs_line" | grep -q "4326"; then
    normalized_crs="EPSG:4326"
    crs_check="✓"
  else
    normalized_crs="UNKNOWN"
    crs_check="✗"
  fi
  
  # Detect source CRS
  if [ -f "$source_file" ]; then
    source_metadata=$(docker exec "$CONTAINER_NAME" /bin/sh -c "
      ogrinfo -so '$container_src' 2>&1
    " 2>&1 || echo "ERROR")
    source_crs=$(echo "$source_metadata" | grep -oE "EPSG:[0-9]+" | head -1 || echo "UNKNOWN")
    [ -z "$source_crs" ] && source_crs="UNKNOWN"
  else
    source_crs="N/A"
  fi
  
  # Determine status
  status="OK"
  notes=""
  
  if [ "$feature_count" = "0" ]; then
    status="WARN"
    notes="No features found"
    ((ERROR_COUNT++))
  elif [ "$normalized_crs" != "EPSG:4326" ]; then
    status="ERROR"
    notes="CRS verification failed: $crs_check"
    ((ERROR_COUNT++))
  else
    ((OK_COUNT++))
  fi
  
  # Truncate extent for display (CSV and MD)
  extent_short=$(echo "$extent" | cut -c1-60)
  
  # Append to CSV (escape quotes)
  echo "\"$source_basename\",\"${source_basename}.shp\",\"$source_crs\",\"$basename\",\"$normalized_crs\",\"$feature_count\",\"$extent_short\",\"$status\",\"$notes\"" >> "$REPORT_CSV"
  
  # Append to MD table (escape pipes)
  extent_md=$(echo "$extent_short" | sed 's/|/\\|/g')
  echo "| $source_basename | ${source_basename}.shp | $source_crs | $basename | $normalized_crs | $feature_count | $extent_md | $status | $notes |" >> "$REPORT_MD"
  
  echo "[$TOTAL] $source_basename: $status (features: $feature_count, CRS: $normalized_crs)"
done

# Add footer to MD report
now=$(date -u +%Y-%m-%dT%H:%M:%SZ)
cat >> "$REPORT_MD" << EOF

## Summary Statistics

- **Total Layers**: $TOTAL
- **OK**: $OK_COUNT
- **Errors/Warnings**: $ERROR_COUNT

End Time: $now

## Notes

- Source CRS detection based on .prj file inspection via ogrinfo
- Normalized CRS verified in output shapefiles
- Feature counts and extents from ogrinfo -so (summary-only, lightweight)
- Status = OK if all checks pass
- Status = WARN if geometry or feature count issues detected
- Status = ERROR if CRS verification failed

EOF

echo ""
echo "=== Verification Summary ==="
echo "Total layers verified: $TOTAL"
echo "OK: $OK_COUNT"
echo "Errors/Warnings: $ERROR_COUNT"
echo ""
echo "Reports generated:"
echo "  - Markdown: $REPORT_MD"
echo "  - CSV: $REPORT_CSV"
echo ""
echo "End time: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
