from __future__ import annotations

import math
from pathlib import Path
import geopandas as gpd

GOLD_ROOT = Path("/work/data/gold/atlas_4326")
MASK_SHP = GOLD_ROOT / "_masks" / "tigray_boundary.shp"
PROJECT_ROOT = Path("/work/Docker Projects/TSIRD-Atlas-Data-Pipeline")
OVERRIDE_YAML = PROJECT_ROOT / "config" / "classification_overrides.yml"

OUT_ETH = GOLD_ROOT / "ethiopia"
OUT_TIG = GOLD_ROOT / "tigray"

THRESHOLD = 0.95
METRIC_CRS = "EPSG:32637"

def _safe_ratio(num: float, den: float) -> float | None:
    if den in (0, None):
        return None
    r = num / den
    return float(r) if math.isfinite(r) else None

def _load_overrides(path: Path) -> dict[str, set[str]]:
    tf, ef = [], []
    if not path.exists():
        return {"tigray_force": set(), "ethiopia_force": set()}
    mode = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("tigray_force:"):
            mode = "tigray"; continue
        if line.startswith("ethiopia_force:"):
            mode = "ethiopia"; continue
        if line.startswith("- "):
            v = line[2:].strip().strip("'\"")
            (tf if mode=="tigray" else ef if mode=="ethiopia" else []).append(v)
    return {"tigray_force": set(tf), "ethiopia_force": set(ef)}

def _rm_dir_files(d: Path):
    d.mkdir(parents=True, exist_ok=True)
    for f in d.glob("*"):
        if f.is_file():
            f.unlink()

def _write_shp(gdf: gpd.GeoDataFrame, out_dir: Path, stem: str):
    out_dir.mkdir(parents=True, exist_ok=True)
    out_shp = out_dir / f"{stem}.shp"
    for ext in [".shp",".shx",".dbf",".prj",".cpg",".qix",".fix",".sbn",".sbx"]:
        fp = out_dir / f"{stem}{ext}"
        if fp.exists():
            fp.unlink()
    gdf.to_file(out_shp, driver="ESRI Shapefile", encoding="UTF-8")

def main():
    overrides = _load_overrides(OVERRIDE_YAML)
    tigray_force = overrides["tigray_force"]
    ethiopia_force = overrides["ethiopia_force"]

    _rm_dir_files(OUT_ETH)
    _rm_dir_files(OUT_TIG)

    mask = gpd.read_file(MASK_SHP).set_crs(epsg=4326, allow_override=True)
    mask_geom = mask.union_all() if hasattr(mask, "union_all") else mask.unary_union

    shp_files = sorted(GOLD_ROOT.glob("*.shp"))
    counts = {"TIGRAY_ONLY": 0, "ETHIOPIA_WIDE": 0}

    for shp in shp_files:
        stem = shp.stem
        if stem.lower() in {"bound01","bound02","bound03"}:
            continue

        gdf = gpd.read_file(shp).set_crs(epsg=4326, allow_override=True)
        if len(gdf) == 0:
            continue

        # overrides first
        if stem in tigray_force:
            cls = "TIGRAY_ONLY"
        elif stem in ethiopia_force:
            cls = "ETHIOPIA_WIDE"
        else:
            gdfm = gdf.to_crs(METRIC_CRS)
            maskm = mask.to_crs(METRIC_CRS)
            mg = maskm.union_all() if hasattr(maskm, "union_all") else maskm.unary_union

            gt = set(map(str, gdf.geom_type.dropna().unique()))
            has_poly = any("Polygon" in t for t in gt)
            has_line = any("Line" in t for t in gt)

            if has_poly:
                total = float(gdfm.geometry.area.sum())
                inside = float(gdfm.geometry.intersection(mg).area.sum())
            elif has_line:
                total = float(gdfm.geometry.length.sum())
                inside = float(gdfm.geometry.intersection(mg).length.sum())
            else:
                total = float(len(gdfm))
                inside = float(gdfm.geometry.within(mg).sum())

            ratio = _safe_ratio(inside, total)
            cls = "TIGRAY_ONLY" if (ratio is not None and ratio >= THRESHOLD) else "ETHIOPIA_WIDE"

        if cls == "ETHIOPIA_WIDE":
            _write_shp(gdf, OUT_ETH, stem)
            counts["ETHIOPIA_WIDE"] += 1
        else:
            try:
                clipped = gpd.clip(gdf, mask_geom)
            except Exception:
                clipped = gdf.copy()
                clipped["geometry"] = clipped.geometry.intersection(mask_geom)
            _write_shp(clipped, OUT_TIG, stem)
            counts["TIGRAY_ONLY"] += 1

    print("Counts:", counts)
    print("Tigray layers:", [p.stem for p in sorted(OUT_TIG.glob("*.shp"))])

if __name__ == "__main__":
    main()
