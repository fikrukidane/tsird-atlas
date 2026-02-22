#!/bin/bash
set -euo pipefail

# README:
# Inventory script for TSIRD vector layers.
#
# This script runs ogrinfo inside the tsird-mapserver container to gather
# metadata on all shapefiles in /data/raw/vectors.
#
# Outputs:
#   - docs/atlas/vector_field_inventory.md (human-readable report)
#   - docs/atlas/vector_field_inventory.csv (one row per field)
#
# Usage: ./scripts/tsird-vector-field-inventory.sh
#
# Requirements:
#   - Docker container "tsird-mapserver" running
#   - ogrinfo available in the container

CONTAINER="tsird-mapserver"
VECTOR_DIR="/data/raw/vectors"

unset CPL_DEBUG

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MARKDOWN_REPORT="${SCRIPT_DIR}/docs/atlas/vector_field_inventory.md"
CSV_REPORT="${SCRIPT_DIR}/docs/atlas/vector_field_inventory.csv"

mkdir -p "$(dirname "${MARKDOWN_REPORT}")"
mkdir -p "$(dirname "${CSV_REPORT}")"

# Initialize outputs (idempotent)
cat > "${CSV_REPORT}" << 'CSVHEADER'
layer_id,shp_file,geom_type,feature_count,crs,extent,field_name,field_type
CSVHEADER

cat > "${MARKDOWN_REPORT}" << 'MDHEADER'
# TSIRD Vector Field Inventory

Comprehensive inventory of all vector layers in the TSIRD system.

## Layers

MDHEADER

csv_escape() {
    local value="$1"
    value="${value//\"/\"\"}"
    if [[ "$value" =~ [,\"] ]]; then
        echo "\"$value\""
    else
        echo "$value"
    fi
}

docker exec "${CONTAINER}" sh -c "find '${VECTOR_DIR}' -maxdepth 1 -name '*.shp' -type f -print0 | sort -z" \
    | while IFS= read -r -d '' shp_path; do
    shp_file="${shp_path##*/}"
    layer_id="${shp_file%.shp}"

    ogrinfo_output=$(docker exec "${CONTAINER}" /bin/sh -lc "unset CPL_DEBUG; ogrinfo -so \"${shp_path}\" \"${layer_id}\"" </dev/null 2>&1) || {
        echo "Warning: failed to read ${shp_file}" >&2
        continue
    }

    if echo "${ogrinfo_output}" | grep -q "^ERROR\|unable to open"; then
        echo "Warning: failed to read ${shp_file}" >&2
        continue
    fi

    geom_type=$(echo "${ogrinfo_output}" | awk '/^Geometry:/{print $2; exit}')
    feature_count=$(echo "${ogrinfo_output}" | awk '/^Feature Count:/{print $3; exit}')
    extent=$(echo "${ogrinfo_output}" | awk '/^Extent:/{sub(/^Extent: /, ""); print; exit}')
    crs=$(echo "${ogrinfo_output}" | awk '/^Layer SRS WKT:/{getline; print; exit}')

    geom_type="${geom_type:-Unknown}"
    feature_count="${feature_count:-0}"
    extent="${extent:-Unknown}"
    if [[ -z "${crs}" ]]; then
        crs="(unknown)"
    fi

    cat >> "${MARKDOWN_REPORT}" << LAYER_MD
### ${layer_id}

| Property | Value |
|----------|-------|
| File | \`${shp_file}\` |
| Geometry | ${geom_type} |
| Features | ${feature_count} |
| Extent | \`${extent}\` |
| CRS | \`${crs}\` |

**Fields:**

LAYER_MD

    fields=$(printf '%s\n' "${ogrinfo_output}" | grep -E '^[A-Za-z0-9_]+: (String|Integer|Integer64|Real|Date|DateTime)')

    if [[ -n "${fields}" ]]; then
        echo "\`\`\`" >> "${MARKDOWN_REPORT}"
        echo "${fields}" >> "${MARKDOWN_REPORT}"
        echo "\`\`\`" >> "${MARKDOWN_REPORT}"
        echo "" >> "${MARKDOWN_REPORT}"

        while IFS= read -r field_line; do
            [[ -z "${field_line}" ]] && continue

            field_name="${field_line%%:*}"
            field_type="${field_line#*: }"
            field_type="${field_type%% *}"

            # Trim leading/trailing whitespace without xargs.
            field_name="${field_name#${field_name%%[![:space:]]*}}"
            field_name="${field_name%${field_name##*[![:space:]]}}"
            field_type="${field_type#${field_type%%[![:space:]]*}}"
            field_type="${field_type%${field_type##*[![:space:]]}}"

            echo "$(csv_escape "${layer_id}")",\
"$(csv_escape "${shp_file}")",\
"$(csv_escape "${geom_type}")",\
"$(csv_escape "${feature_count}")",\
"$(csv_escape "${crs}")",\
"$(csv_escape "${extent}")",\
"$(csv_escape "${field_name}")",\
"$(csv_escape "${field_type}")" >> "${CSV_REPORT}"
        done <<< "${fields}"
    else
        echo "(no fields)" >> "${MARKDOWN_REPORT}"
        echo "" >> "${MARKDOWN_REPORT}"
    fi

done

cat >> "${MARKDOWN_REPORT}" << 'MD_FOOTER'
---
_Inventory generated on DATE_PLACEHOLDER_
MD_FOOTER

# Replace the date placeholder without non-standard tools.
current_date=$(date '+%Y-%m-%d %H:%M:%S')
sed -i "s/DATE_PLACEHOLDER/${current_date}/" "${MARKDOWN_REPORT}"

echo "Inventory complete"
echo "Markdown: ${MARKDOWN_REPORT}"
echo "CSV: ${CSV_REPORT}"
