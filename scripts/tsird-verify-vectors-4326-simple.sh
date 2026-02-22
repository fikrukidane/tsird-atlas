#!/bin/bash
# TSIRD Vector Verification - Simplified
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
NORM_DIR="${PROJECT_ROOT}/data/normalized/vectors4326"
DOCS_DIR="${PROJECT_ROOT}/docs/atlas"

mkdir -p "$DOCS_DIR"

MD="${DOCS_DIR}/normalize_report_4326.md"
CSV="${DOCS_DIR}/normalize_report_4326.csv"

echo "=== TSIRD Vector Verification ===" 
echo "Start: $(date -u +%Y-%m-%dT%H:%M:%SZ)"

# CSV header  
echo "layer,source_file,source_crs,normalized_file,normalized_crs,feature_count,extent,status,notes" > "$CSV"

# MD header
cat > "$MD" << 'EOF'
# Vector Normalization Report (EPSG:4326)

## Layer Details

| Layer | Source CRS | Norm. CRS | Features | Extent | Status |
|-------|------------|-----------|----------|--------|--------|
EOF

OK=0
ERR=0

for shp in "$NORM_DIR"/*_4326.shp; do
  [ -f "$shp" ] || continue
  
  base=$(basename "$shp" _4326.shp)
  info=$(docker exec tsird-etl ogrinfo -so "/data/normalized/vectors4326/$(basename "$shp")" "$(basename "$shp" .shp)" 2>&1 || echo "ERROR")
  
  features=$(echo "$info" | grep -oP 'Feature Count: \K\d+' || echo "0")
  extent=$(echo "$info" | grep -oP 'Extent: \K[^\n]+' | head -1 || echo "UNKNOWN")
  epsg=$(echo "$info" | grep -oP 'EPSG",\K\d+' || echo "UNK")
  
  if [ "$epsg" != "UNK" ]; then
    norm_crs="EPSG:$epsg"
  else
    norm_crs="UNKNOWN"
  fi
  
  # Get source CRS
  src_info=$(docker exec tsird-etl ogrinfo -so "/data/raw/vectors/${base}.shp" "$base" 2>&1 || echo "ERROR")
  src_epsg=$(echo "$src_info" | grep -oP 'EPSG",\K\d+' || echo "UNK")
  
  if [ "$src_epsg" != "UNK" ]; then
    src_crs="EPSG:$src_epsg"
  else
    src_crs="UNKNOWN"
  fi
  
  # Status
  if [ "$features" = "0" ]; then
    status="WARN"
    notes="No features"
    ERR=$((ERR + 1))
  elif [ "$norm_crs" = "UNKNOWN" ]; then
    status="WARN"
    notes="CRS unknown"
    ERR=$((ERR + 1))
  else
    status="OK"
    notes=""
    OK=$((OK + 1))
  fi
  
  # Write CSV
  echo "\"$base\",\"${base}.shp\",\"$src_crs\",\"$(basename "$shp")\",\"$norm_crs\",\"$features\",\"${extent:0:60}\",\"$status\",\"$notes\"" >> "$CSV"
  
  # Write MD
  echo "| $base | $src_crs | $norm_crs | $features | ${extent:0:50} | $status |" >> "$MD"
  
  echo "[ $status ] $base: $features features, CRS=$norm_crs"
done

# MD footer
cat >> "$MD" << EOF

## Summary

- **Total**: $((OK + ERR))
- **OK**: $OK
- **Warnings/Errors**: $ERR

Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)
EOF

echo ""
echo "=== Summary ==="
echo "OK: $OK | Errors: $ERR"
echo "Reports: $MD, $CSV"
