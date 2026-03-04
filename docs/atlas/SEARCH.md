# TSIRD Atlas Search Functionality

## Overview

The search feature allows users to find and navigate to Tigray administrative units (Woredas and Tabias) directly from the Table of Contents panel.

## Architecture

The search is implemented as a **client-side, WMS-only** solution:

1. **Prebuilt JSON Index** - A static JSON file containing feature names and bounding boxes
2. **No WFS Required** - Index is generated offline from shapefiles
3. **No Database Queries** - All search happens in the browser
4. **Fast Autocomplete** - Instant results as user types

## Components

### 1. Search Index Generator

**Location:** `tools/build_search_index.py`

Reads shapefiles and creates the JSON index:

```bash
# Regenerate search index
cd /opt/tigrayinsights/apps/tsird
python3 tools/build_search_index.py
```

**Input Shapefiles:**
- `infra/mapserver/shapefiles/TigrayNewWoredas.shp` - 48 Woreda boundaries
- `infra/mapserver/shapefiles/TigraiTabiasNew.shp` - 748 Tabia boundaries

**Output:**
- `ui/web/data/search-index.json`

### 2. Search Index Format

```json
{
  "version": "1.0",
  "generated": "2026-02-21T10:30:00Z",
  "stats": {
    "woredas": 47,
    "tabias": 748,
    "total": 795
  },
  "features": [
    {
      "id": "woreda_1",
      "type": "woreda",
      "name": "Enderta",
      "name_norm": "enderta",
      "parent": null,
      "zone": "South Eastern",
      "bbox_4326": [39.1, 13.2, 39.5, 13.6],
      "centroid_4326": [39.3, 13.4]
    },
    {
      "id": "tabia_1",
      "type": "tabia",
      "name": "Adi Gudema",
      "name_norm": "adi gudema",
      "parent": "Enderta",
      "zone": "South Eastern",
      "bbox_4326": [39.2, 13.3, 39.3, 13.4],
      "centroid_4326": [39.25, 13.35]
    }
  ]
}
```

### 3. Registry Configuration

```yaml
# config/atlas-registry.yaml
ui:
  search:
    enabled: true
    index_url: data/search-index.json
```

### 4. Frontend Components

**RegistryLoader.js:**
- Extracts `ui.search` config from registry
- Exposes `atlasConfig.search.enabled` and `atlasConfig.search.index_url`

**InteractionController.js:**
- `loadSearchIndex(url)` - Fetches and stores the index
- `_renderSearchBox(container)` - Creates search input and dropdown
- `_searchFeatures(query)` - Prefix + substring matching, max 10 results
- `_selectSearchResult(feature)` - Zooms to feature extent
- `_highlightExtent(extent)` - Orange overlay, auto-removes after 2s

**main.js:**
- Calls `interaction.loadSearchIndex()` if search is enabled in registry

## User Experience

1. User types in search box (min 2 characters)
2. Results appear instantly (woredas first, then tabias)
3. Each result shows name + type badge (WOREDA/TABIA)
4. Clicking result:
   - Map zooms to fit feature bounding box
   - Orange highlight appears briefly (2 seconds)
   - Search dropdown closes

## Zoom Constraints

- **Woredas:** maxZoom = 11 (regional view)
- **Tabias:** maxZoom = 13 (local view)

## Updating the Index

When administrative boundaries change:

```bash
# 1. Update shapefiles in infra/mapserver/shapefiles/

# 2. Regenerate index
cd /opt/tigrayinsights/apps/tsird
python3 tools/build_search_index.py

# 3. Rebuild web container (copies new JSON)
docker compose build web
docker compose up -d web
```

## Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| Search box not appearing | `ui.search.enabled: false` | Set to `true` in registry |
| No results | Index not loaded | Check console for fetch errors |
| Wrong locations | Index out of sync | Regenerate index from shapefiles |
| Zoom too close/far | Bbox coordinates wrong | Check shapefile projection (must be 4326) |

## Dependencies

- **pyshp** (Python): For reading shapefiles in index generator
- **OpenLayers**: For zoom, fit, and highlight overlay
