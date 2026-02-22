from __future__ import annotations

import sys
import math
import json
import shutil
import traceback
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import geopandas as gpd

# Ensure project root is on sys.path (script-safe)
PROJECT_ROOT = Path("/work/Docker Projects/TSIRD-Atlas-Data-Pipeline")
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.paths import VECTORS_RAW_ROOT, GOLD_ROOT, DATA_ROOT, AUDIT_ROOT
from config.crs_override_loader import load_crs_overrides


QUARANTINE_ROOT = DATA_ROOT / "normalized" / "quarantine"
REPORT_CSV = AUDIT_ROOT / "normalization_report.csv"
REPORT_MD = AUDIT_ROOT / "normalization_report.md"


def _safe_float(x):
    try:
        v = float(x)
        return v if math.isfinite(v) else None
    except Exception:
        return None


def _bounds_flag_4326(bounds) -> str | None:
    if bounds is None:
        return "NO_BOUNDS"
    minx, miny, maxx, maxy = bounds
    vals = [_safe_float(v) for v in (minx, miny, maxx, maxy)]
    if any(v is None for v in vals):
        return "NONFINITE_BOUNDS"
    minx, miny, maxx, maxy = vals
    if (minx < -180 or maxx > 180 or miny < -90 or maxy > 90):
        return "OUT_OF_RANGE_FOR_4326"
    return None


def _absurd_magnitude(bounds) -> bool:
    if bounds is None:
        return False
    minx, miny, maxx, maxy = bounds
    vals = [_safe_float(v) for v in (minx, miny, maxx, maxy)]
    if any(v is None for v in vals):
        return True
    return any(abs(v) > 1e8 for v in vals)


def _valid_ratio(gdf: gpd.GeoDataFrame) -> float | None:
    if gdf is None or len(gdf) == 0 or gdf.geometry is None:
        return None
    geom = gdf.geometry
    empty = geom.is_empty.fillna(True)
    try:
        valid = geom.is_valid.fillna(False) & (~empty)
        return float(valid.sum() / len(gdf))
    except Exception:
        return None



def _dedupe_columns(gdf: gpd.GeoDataFrame) -> tuple[gpd.GeoDataFrame, list[tuple[str,str]]]:
    """
    Ensure GeoDataFrame has unique column names.
    Returns (gdf, renames_applied) where renames are (old, new) pairs in order.
    """
    cols = list(gdf.columns)
    seen = {}
    new_cols = []
    renames = []
    for c in cols:
        base = str(c)
        if base not in seen:
            seen[base] = 1
            new_cols.append(base)
        else:
            seen[base] += 1
            new_name = f"{base}__{seen[base]}"
            new_cols.append(new_name)
            renames.append((base, new_name))
    if cols != new_cols:
        gdf = gdf.copy()
        gdf.columns = new_cols
    return gdf, renames


def _try_read(shp: Path) -> tuple[gpd.GeoDataFrame | None, str | None]:
    # Try default read
    try:
        return gpd.read_file(shp), None
    except UnicodeDecodeError:
        # Try latin1 for DBF encoding issues
        try:
            return gpd.read_file(shp, encoding="latin1"), "latin1"
        except Exception as e:
            return None, f"FAILED_LATIN1:{type(e).__name__}:{e}"
    except Exception as e:
        return None, f"FAILED:{type(e).__name__}:{e}"


def _ensure_clean_dir(path: Path):
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)



def _make_valid_geoms(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Stronger geometry repair using shapely.make_valid when available.
    """
    try:
        from shapely import make_valid
    except Exception:
        try:
            from shapely.validation import make_valid  # fallback name
        except Exception:
            return gdf

    gdf = gdf.copy()
    gdf["geometry"] = gdf.geometry.apply(lambda g: make_valid(g) if g is not None else None)
    return gdf


def _write_shapefile(gdf: gpd.GeoDataFrame, out_dir: Path, layer_name: str):
    """
    Writes an ESRI Shapefile as a folder of component files in out_dir/layer_name.*
    We write to a temp folder then move into place for atomic-ish behavior.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    tmp = out_dir / f".tmp_{layer_name}"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True, exist_ok=True)

    out_shp = tmp / f"{layer_name}.shp"
    gdf.to_file(out_shp, driver="ESRI Shapefile", encoding="UTF-8")

    # Move temp outputs into final directory, removing any prior layer files
    # Remove existing layer components
    for ext in [".shp",".shx",".dbf",".prj",".cpg",".qix",".fix",".sbn",".sbx"]:
        f = out_dir / f"{layer_name}{ext}"
        if f.exists():
            f.unlink()

    # Move everything from tmp to out_dir
    for f in tmp.iterdir():
        target = out_dir / f.name
        if target.exists():
            target.unlink()
        f.replace(target)

    shutil.rmtree(tmp, ignore_errors=True)


def main():
    AUDIT_ROOT.mkdir(parents=True, exist_ok=True)
    GOLD_ROOT.mkdir(parents=True, exist_ok=True)
    QUARANTINE_ROOT.mkdir(parents=True, exist_ok=True)

    overrides = load_crs_overrides()

    shp_files = sorted(VECTORS_RAW_ROOT.rglob("*.shp"))
    if not shp_files:
        raise SystemExit(f"No .shp files found under {VECTORS_RAW_ROOT}")

    rows = []
    run_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")

    for shp in shp_files:
        layer = shp.stem
        rec = {
            "run_utc": run_utc,
            "layer_name": layer,
            "raw_path": str(shp),
            "status": None,                 # GOLD | QUARANTINE
            "reason": None,                 # why quarantined (or None)
            "read_encoding": None,          # None | latin1 | FAILED...
            "source_crs": None,
            "assigned_crs": None,           # EPSG used for interpreting source
            "reprojected_to_4326": None,
            "bounds_flag_post4326": None,
            "valid_ratio_pre": None,
            "valid_ratio_post": None,
            "geometry_repaired": None,
            "feature_count": None,
            "deduped_columns": None,
            "dedupe_renames": None,
            "error": None,
        }

        try:
            gdf, enc = _try_read(shp)
            rec["read_encoding"] = enc
            if gdf is None:
                rec["status"] = "QUARANTINE"
                rec["reason"] = "READ_FAILED"
                rec["error"] = enc
                rows.append(rec)
                continue

            # Dedupe columns deterministically (prevents GeoDataFrame duplicate-column errors)
            gdf, renames = _dedupe_columns(gdf)
            rec["deduped_columns"] = bool(renames)
            rec["dedupe_renames"] = json.dumps(renames) if renames else None

            rec["feature_count"] = int(len(gdf))
            rec["source_crs"] = str(gdf.crs) if gdf.crs is not None else None

            # Determine assigned CRS (interpretation CRS)
            # Explicit overrides always win (even if source CRS exists but is wrong)
            assigned_epsg = None

            if layer in overrides:
                assigned_epsg = int(overrides[layer])
                gdf = gdf.set_crs(epsg=assigned_epsg, allow_override=True)
            elif gdf.crs is not None and gdf.crs.to_epsg() is not None:
                assigned_epsg = int(gdf.crs.to_epsg())
            else:
                # If CRS missing: allow EPSG:4326 only if bounds are already geographic-ish
                b = gdf.total_bounds if len(gdf) else None
                if b is not None:
                    minx, miny, maxx, maxy = b
                    if (minx >= -180 and maxx <= 180 and miny >= -90 and maxy <= 90):
                        assigned_epsg = 4326
                        gdf = gdf.set_crs(epsg=4326, allow_override=True)

            if assigned_epsg is None:
                rec["status"] = "QUARANTINE"
                rec["reason"] = "CRS_MISSING_NO_OVERRIDE"
                rows.append(rec)
                continue

            # Dedupe columns deterministically (prevents GeoDataFrame duplicate-column errors)
            gdf, renames = _dedupe_columns(gdf)
            rec["deduped_columns"] = bool(renames)
            rec["dedupe_renames"] = json.dumps(renames) if renames else None

            rec["assigned_crs"] = f"EPSG:{assigned_epsg}"

            # Bounds sanity before reprojection
            if _absurd_magnitude(gdf.total_bounds if len(gdf) else None) and assigned_epsg == 4326:
                rec["status"] = "QUARANTINE"
                rec["reason"] = "ABSURD_BOUNDS_CLAIMS_4326"
                rows.append(rec)
                continue

            # Dedupe columns deterministically (prevents GeoDataFrame duplicate-column errors)
            gdf, renames = _dedupe_columns(gdf)
            rec["deduped_columns"] = bool(renames)
            rec["dedupe_renames"] = json.dumps(renames) if renames else None

            # Reproject to 4326 if needed
            if assigned_epsg != 4326:
                gdf = gdf.to_crs(epsg=4326)
                rec["reprojected_to_4326"] = True
            else:
                rec["reprojected_to_4326"] = False

            # Post-reprojection bounds check
            rec["bounds_flag_post4326"] = _bounds_flag_4326(gdf.total_bounds if len(gdf) else None)
            if rec["bounds_flag_post4326"] is not None:
                rec["status"] = "QUARANTINE"
                if rec["assigned_crs"] == "EPSG:4326" and rec["bounds_flag_post4326"] == "OUT_OF_RANGE_FOR_4326":
                    rec["reason"] = "CRS_CLAIMS_4326_BUT_OUT_OF_RANGE"
                else:
                    rec["reason"] = f"BOUNDS_{rec['bounds_flag_post4326']}"
                rows.append(rec)
                continue

            # Dedupe columns deterministically (prevents GeoDataFrame duplicate-column errors)
            gdf, renames = _dedupe_columns(gdf)
            rec["deduped_columns"] = bool(renames)
            rec["dedupe_renames"] = json.dumps(renames) if renames else None

            # Geometry validation / repair
            rec["valid_ratio_pre"] = _valid_ratio(gdf)
            rec["geometry_repaired"] = False

            if rec["valid_ratio_pre"] is not None and rec["valid_ratio_pre"] < 0.98:
                # Attempt repair (buffer(0))
                try:
                    gdf["geometry"] = gdf.geometry.buffer(0)
                    rec["geometry_repaired"] = True
                except Exception as e:
                    rec["status"] = "QUARANTINE"
                    rec["reason"] = "GEOM_REPAIR_FAILED"
                    rec["error"] = f"{type(e).__name__}:{e}"
                    rows.append(rec)
                    continue

            rec["valid_ratio_post"] = _valid_ratio(gdf)

            # If still below threshold, try stronger make_valid
            if rec["valid_ratio_post"] is not None and rec["valid_ratio_post"] < 0.98:
                gdf2 = _make_valid_geoms(gdf)
                vr2 = _valid_ratio(gdf2)
                if vr2 is not None and vr2 >= 0.98:
                    gdf = gdf2
                    rec["valid_ratio_post"] = vr2
                    rec["geometry_repaired"] = True
                else:
                    rec["status"] = "QUARANTINE"
                    rec["reason"] = "GEOM_INVALID_POST_REPAIR"
                    rows.append(rec)
                    continue

            # Dedupe columns deterministically (prevents GeoDataFrame duplicate-column errors)
            gdf, renames = _dedupe_columns(gdf)
            rec["deduped_columns"] = bool(renames)
            rec["dedupe_renames"] = json.dumps(renames) if renames else None

            # Write GOLD shapefile
            _write_shapefile(gdf, GOLD_ROOT, layer)
            rec["status"] = "GOLD"
            rows.append(rec)

        except Exception as e:
            rec["status"] = "QUARANTINE"
            rec["reason"] = "UNHANDLED_EXCEPTION"
            rec["error"] = f"{type(e).__name__}:{e}"
            rows.append(rec)

    df = pd.DataFrame(rows)
    df.to_csv(REPORT_CSV, index=False)

    # simple markdown summary (no tabulate)
    total = len(df)
    gold = int((df["status"] == "GOLD").sum())
    q = total - gold
    md = []
    md.append("# TSIRD Normalization Report (to EPSG:4326)")
    md.append("")
    md.append(f"- Run (UTC): **{run_utc}**")
    md.append(f"- Input root: `{VECTORS_RAW_ROOT}`")
    md.append(f"- Gold output: `{GOLD_ROOT}`")
    md.append(f"- Quarantine: `{QUARANTINE_ROOT}`")
    md.append(f"- Total layers: **{total}**")
    md.append(f"- Gold: **{gold}**")
    md.append(f"- Quarantined: **{q}**")
    md.append("")
    md.append("## Quarantine reasons (counts)")
    md.append("")
    reason_counts = df[df["status"] == "QUARANTINE"]["reason"].value_counts().reset_index()
    reason_counts.columns = ["reason", "count"]
    if len(reason_counts) == 0:
        md.append("_None_")
    else:
        md.append("| reason | count |")
        md.append("| --- | --- |")
        for _, r in reason_counts.iterrows():
            md.append(f"| {r['reason']} | {r['count']} |")
    md.append("")

    REPORT_MD.write_text("\n".join(md), encoding="utf-8")

    # Quarantine handling: copy raw shapefile component set into quarantine folder for visibility
    # (We only copy when status == QUARANTINE and the raw exists)
    for _, r in df[df["status"] == "QUARANTINE"].iterrows():
        shp = Path(r["raw_path"])
        layer = r["layer_name"]
        if not shp.exists():
            continue
        # copy all sidecars sharing the stem
        for f in shp.parent.glob(layer + ".*"):
            target_dir = QUARANTINE_ROOT / layer
            target_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, target_dir / f.name)

    print(f"Wrote: {REPORT_CSV}")
    print(f"Wrote: {REPORT_MD}")
    print(f"Gold layers: {gold}/{total}")
    if q:
        print(f"Quarantined: {q} (see report + {QUARANTINE_ROOT})")


if __name__ == "__main__":
    main()
