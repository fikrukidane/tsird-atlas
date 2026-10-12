#!/usr/bin/env python3
"""Generate the production Atlas registry without development-only layers."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "ui" / "web" / "data" / "atlas-registry.json"
OUTPUT = ROOT / "infra" / "production-public-web" / "data" / "atlas-registry.json"
PUBLIC_DROUGHT_RASTERS = [
    "tigray_drought_chirps_raw_public",
    "tigray_drought_chirps_rapid_raw_public",
    "tigray_drought_ndvi_raw_public",
    "tigray_drought_swi_raw_public",
    "tigray_drought_lst_raw_public",
    "tigray_drought_wapor_raw_public",
]


def is_development_drought_layer(layer_id: str, record: object | None = None) -> bool:
    if layer_id.endswith("_dev") and layer_id.startswith("tigray_drought_"):
        return True
    return isinstance(record, dict) and str(record.get("wms_name", "")).endswith("_dev")


def main() -> int:
    registry = json.loads(SOURCE.read_text(encoding="utf-8"))
    layers = registry.get("layers")
    categories = registry.get("categories")
    if not isinstance(layers, dict) or not isinstance(categories, list):
        raise RuntimeError("Atlas registry structure is invalid")
    removed = {layer_id for layer_id, record in layers.items() if is_development_drought_layer(layer_id, record)}
    for layer_id in removed:
        layers.pop(layer_id, None)
    for category in categories:
        if not isinstance(category, dict):
            continue
        for group in category.get("groups", []):
            if not isinstance(group, dict) or not isinstance(group.get("layers"), list):
                continue
            group["layers"] = [layer_id for layer_id in group["layers"] if layer_id not in removed]
            if group.get("id") == "grp_rainfall":
                group["layers"] = PUBLIC_DROUGHT_RASTERS + [
                    layer_id for layer_id in group["layers"] if layer_id not in PUBLIC_DROUGHT_RASTERS
                ]
                group["label"] = "Rainfall and retained indicator grids"
    unknown = [layer_id for category in categories if isinstance(category, dict) for group in category.get("groups", []) if isinstance(group, dict) for layer_id in group.get("layers", []) if layer_id not in layers]
    if unknown:
        raise RuntimeError(f"production registry references unknown layer(s): {', '.join(sorted(set(unknown)))}")
    if any(is_development_drought_layer(layer_id, record) for layer_id, record in layers.items()):
        raise RuntimeError("production registry still contains a development drought layer")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT.relative_to(ROOT)} without {len(removed)} development drought layers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
