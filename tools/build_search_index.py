#!/usr/bin/env python3
"""
Build search index for Tigray Woredas and Tabias.

This script reads shapefiles and generates a JSON search index for the
TSIRD Atlas frontend search functionality.

Usage:
    python3 tools/build_search_index.py

Output:
    ui/web/data/search-index.json

Dependencies:
    - pyshp (pip install pyshp)

Author: TSIRD Atlas Team
Date: 2026-03-04
"""

import json
import os
import sys
import unicodedata
from pathlib import Path

# Check for pyshp
try:
    import shapefile
except ImportError:
    print("ERROR: pyshp is required but not installed.")
    print("Install it with: pip install pyshp")
    sys.exit(1)


def normalize_text(text):
    """Normalize text for search matching."""
    if not text:
        return ""
    # Normalize unicode, lowercase, strip whitespace
    text = unicodedata.normalize('NFKD', str(text))
    text = text.lower().strip()
    # Remove extra whitespace
    text = ' '.join(text.split())
    return text


def get_bbox(shape):
    """Get bounding box from shape object."""
    if shape.shapeType == shapefile.NULL:
        return None
    return list(shape.bbox)  # [minx, miny, maxx, maxy]


def get_centroid(bbox):
    """Calculate centroid from bounding box."""
    if not bbox:
        return None
    return [
        (bbox[0] + bbox[2]) / 2,  # lon
        (bbox[1] + bbox[3]) / 2   # lat
    ]


def read_woredas(shp_path):
    """Read woredas shapefile and extract search data."""
    features = []
    
    print(f"Reading woredas from: {shp_path}")
    
    try:
        sf = shapefile.Reader(str(shp_path))
    except Exception as e:
        print(f"ERROR: Cannot read shapefile: {e}")
        return features
    
    # Get field names
    field_names = [f[0] for f in sf.fields[1:]]  # Skip DeletionFlag
    print(f"  Fields: {field_names}")
    
    # Find required fields
    wereda_idx = None
    zone_idx = None
    
    for i, name in enumerate(field_names):
        if name.upper() == 'WEREDA':
            wereda_idx = i
        elif name.upper() in ('ZONE_NAME', 'ZONES', 'ZONE'):
            zone_idx = i
    
    if wereda_idx is None:
        print("  WARNING: WEREDA field not found")
        return features
    
    print(f"  Found WEREDA at index {wereda_idx}")
    if zone_idx is not None:
        print(f"  Found zone field at index {zone_idx}")
    
    # Process records
    for i, (shape, rec) in enumerate(zip(sf.shapes(), sf.records())):
        wereda_name = rec[wereda_idx] if wereda_idx is not None else None
        zone_name = rec[zone_idx] if zone_idx is not None else None
        
        if not wereda_name:
            continue
        
        bbox = get_bbox(shape)
        if not bbox:
            continue
        
        feature = {
            "id": f"woreda_{i}",
            "type": "woreda",
            "name": str(wereda_name).strip(),
            "name_norm": normalize_text(wereda_name),
            "zone": str(zone_name).strip() if zone_name else None,
            "bbox_4326": bbox,
            "centroid_4326": get_centroid(bbox)
        }
        features.append(feature)
    
    print(f"  Extracted {len(features)} woredas")
    return features


def read_tabias(shp_path):
    """Read tabias shapefile and extract search data."""
    features = []
    
    print(f"Reading tabias from: {shp_path}")
    
    try:
        sf = shapefile.Reader(str(shp_path))
    except Exception as e:
        print(f"ERROR: Cannot read shapefile: {e}")
        return features
    
    # Get field names
    field_names = [f[0] for f in sf.fields[1:]]  # Skip DeletionFlag
    print(f"  Fields: {field_names}")
    
    # Find required fields
    tabia_idx = None
    wereda_idx = None
    zone_idx = None
    
    for i, name in enumerate(field_names):
        if name.upper() == 'TABIA':
            tabia_idx = i
        elif name.upper() == 'WEREDA':
            wereda_idx = i
        elif name.upper() in ('ZONES', 'ZONE_NAME', 'ZONE'):
            zone_idx = i
    
    if tabia_idx is None:
        print("  WARNING: TABIA field not found")
        return features
    
    print(f"  Found TABIA at index {tabia_idx}")
    if wereda_idx is not None:
        print(f"  Found WEREDA at index {wereda_idx}")
    
    # Process records
    for i, (shape, rec) in enumerate(zip(sf.shapes(), sf.records())):
        tabia_name = rec[tabia_idx] if tabia_idx is not None else None
        wereda_name = rec[wereda_idx] if wereda_idx is not None else None
        zone_name = rec[zone_idx] if zone_idx is not None else None
        
        if not tabia_name:
            continue
        
        bbox = get_bbox(shape)
        if not bbox:
            continue
        
        feature = {
            "id": f"tabia_{i}",
            "type": "tabia",
            "name": str(tabia_name).strip(),
            "name_norm": normalize_text(tabia_name),
            "parent": str(wereda_name).strip() if wereda_name else None,
            "zone": str(zone_name).strip() if zone_name else None,
            "bbox_4326": bbox,
            "centroid_4326": get_centroid(bbox)
        }
        features.append(feature)
    
    print(f"  Extracted {len(features)} tabias")
    return features


def main():
    # Determine paths
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent
    
    # Shapefile paths
    woredas_shp = repo_root / "data" / "gold" / "atlas_4326" / "TigrayNewWoredas.shp"
    tabias_shp = repo_root / "data" / "gold" / "atlas_4326" / "TigraiTabiasNew.shp"
    
    # Output path
    output_path = repo_root / "ui" / "web" / "data" / "search-index.json"
    
    print("=" * 60)
    print("TSIRD Atlas Search Index Builder")
    print("=" * 60)
    print(f"Repo root: {repo_root}")
    print()
    
    # Validate input files
    if not woredas_shp.exists():
        print(f"ERROR: Woredas shapefile not found: {woredas_shp}")
        sys.exit(1)
    
    if not tabias_shp.exists():
        print(f"ERROR: Tabias shapefile not found: {tabias_shp}")
        sys.exit(1)
    
    # Read data
    woredas = read_woredas(woredas_shp)
    tabias = read_tabias(tabias_shp)
    
    # Combine and sort
    all_features = woredas + tabias
    
    # Sort by type (woredas first), then by name
    all_features.sort(key=lambda f: (0 if f["type"] == "woreda" else 1, f["name_norm"]))
    
    # Build index structure
    index = {
        "version": "1.0",
        "generated": "2026-03-04",
        "stats": {
            "woredas": len(woredas),
            "tabias": len(tabias),
            "total": len(all_features)
        },
        "features": all_features
    }
    
    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Write output
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(index, f, indent=2, ensure_ascii=False)
    
    print()
    print("=" * 60)
    print(f"SUCCESS: Generated {output_path}")
    print(f"  Woredas: {len(woredas)}")
    print(f"  Tabias: {len(tabias)}")
    print(f"  Total features: {len(all_features)}")
    print("=" * 60)


if __name__ == "__main__":
    main()
