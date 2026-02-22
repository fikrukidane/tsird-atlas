from __future__ import annotations

import json
import math
import traceback
from datetime import datetime, timezone
from pathlib import Path


# --- Ensure project root is on sys.path ---
import sys
PROJECT_ROOT = Path("/work/Docker Projects/TSIRD-Atlas-Data-Pipeline")
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
# -------------------------------------------

import pandas as pd
import geopandas as gpd


def _df_to_md_table(df: pd.DataFrame) -> str:
    """Render a DataFrame as a simple GitHub-flavored markdown table without tabulate."""
    if df is None or len(df) == 0:
        return "_None_"
    cols = list(df.columns)
    # header
    lines = []
    lines.append("| " + " | ".join(str(c) for c in cols) + " |")
    lines.append("| " + " | ".join(["---"] * len(cols)) + " |")
    # rows
    for _, row in df.iterrows():
        vals = []
        for c in cols:
            v = row[c]
            s = "" if pd.isna(v) else str(v)
            s = s.replace("\n", " ").replace("\r", " ")
            vals.append(s)
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


# Locked constants
from config.paths import VECTORS_RAW_ROOT, AUDIT_ROOT


def _safe_float(x):
    try:
        if x is None:
            return None
        v = float(x)
        return v if math.isfinite(v) else None
    except Exception:
        return None


def _crs_to_text(crs_obj) -> str | None:
    if crs_obj is None:
        return None
    try:
        epsg = crs_obj.to_epsg()
        if epsg is not None:
            return f"EPSG:{epsg}"
    except Exception:
        pass
    try:
        return crs_obj.to_wkt()
    except Exception:
        try:
            return str(crs_obj)
        except Exception:
            return None


def _bounds_flag(bounds, crs_text: str | None) -> str | None:
    if bounds is None:
        return "NO_BOUNDS"
    minx, miny, maxx, maxy = bounds
    vals = [_safe_float(v) for v in (minx, miny, maxx, maxy)]
    if any(v is None for v in vals):
        return "NONFINITE_BOUNDS"

    minx, miny, maxx, maxy = vals
    if minx > maxx or miny > maxy:
        return "INVERTED_BOUNDS"

    spanx = maxx - minx
    spany = maxy - miny
    if spanx == 0 and spany == 0:
        return "ZERO_EXTENT"

    if crs_text == "EPSG:4326":
        if (minx < -180 or maxx > 180 or miny < -90 or maxy > 90):
            return "OUT_OF_RANGE_FOR_4326"
        return None

    if crs_text is None:
        if (minx >= -180 and maxx <= 180 and miny >= -90 and maxy <= 90):
            return "CRS_MISSING_BUT_BOUNDS_LOOK_GEOGRAPHIC"
        if any(abs(v) > 1e8 for v in (minx, miny, maxx, maxy)):
            return "ABSURD_MAGNITUDE_BOUNDS"
        return None

    if any(abs(v) > 1e8 for v in (minx, miny, maxx, maxy)):
        return "ABSURD_MAGNITUDE_BOUNDS"
    return None


def _read_layer(shp_path: Path) -> dict:
    rec = {
        "path": str(shp_path),
        "layer_name": shp_path.stem,
        "read_ok": False,
        "error_type": None,
        "error_message": None,
        "traceback": None,
        "feature_count": None,
        "geom_types": None,
        "crs_text": None,
        "crs_epsg": None,
        "bounds_minx": None,
        "bounds_miny": None,
        "bounds_maxx": None,
        "bounds_maxy": None,
        "bounds_flag": None,
        "valid_geom_ratio": None,
        "empty_geom_ratio": None,
        "has_z": None,
        "sample_invalid_reason": None,
        "columns": None,
    }

    try:
        gdf = gpd.read_file(shp_path)
        rec["read_ok"] = True
        rec["feature_count"] = int(len(gdf))

        crs = gdf.crs
        rec["crs_text"] = _crs_to_text(crs)
        try:
            rec["crs_epsg"] = crs.to_epsg() if crs is not None else None
        except Exception:
            rec["crs_epsg"] = None

        try:
            b = gdf.total_bounds
            rec["bounds_minx"], rec["bounds_miny"], rec["bounds_maxx"], rec["bounds_maxy"] = map(_safe_float, b)
            rec["bounds_flag"] = _bounds_flag(b, rec["crs_text"])
        except Exception:
            rec["bounds_flag"] = "BOUNDS_FAILED"

        try:
            gt = sorted(set([str(x) for x in gdf.geom_type.dropna().unique()]))
            rec["geom_types"] = "|".join(gt) if gt else None
        except Exception:
            rec["geom_types"] = None

        try:
            rec["columns"] = json.dumps(list(gdf.columns))
        except Exception:
            rec["columns"] = None

        geom = gdf.geometry
        if geom is not None and len(gdf) > 0:
            empty = geom.is_empty.fillna(True)
            rec["empty_geom_ratio"] = float(empty.sum() / len(gdf))
            try:
                valid = geom.is_valid.fillna(False) & (~empty)
                rec["valid_geom_ratio"] = float(valid.sum() / len(gdf))
            except Exception:
                rec["valid_geom_ratio"] = None

            try:
                sample = geom.dropna().head(200)
                hasz = False
                for g in sample:
                    if g is None or getattr(g, "is_empty", False):
                        continue
                    if getattr(g, "has_z", False):
                        hasz = True
                        break
                rec["has_z"] = bool(hasz)
            except Exception:
                rec["has_z"] = None

            try:
                bad = gdf.loc[~geom.is_empty & ~geom.is_valid].head(1)
                if len(bad) == 1:
                    from shapely.validation import explain_validity
                    rec["sample_invalid_reason"] = explain_validity(bad.geometry.iloc[0])
            except Exception:
                rec["sample_invalid_reason"] = None

        return rec

    except Exception as e:
        rec["error_type"] = type(e).__name__
        rec["error_message"] = str(e)
        rec["traceback"] = traceback.format_exc(limit=5)
        return rec


def main():
    AUDIT_ROOT.mkdir(parents=True, exist_ok=True)

    shp_files = sorted(VECTORS_RAW_ROOT.rglob("*.shp"))
    if not shp_files:
        raise SystemExit(f"No .shp files found under {VECTORS_RAW_ROOT}")

    rows = [_read_layer(p) for p in shp_files]
    df = pd.DataFrame(rows).sort_values(["read_ok", "path"], ascending=[False, True])

    csv_out = AUDIT_ROOT / "raw_inventory.csv"
    md_out = AUDIT_ROOT / "raw_inventory.md"
    df.to_csv(csv_out, index=False)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    total = len(df)
    ok = int(df["read_ok"].sum())
    failed = total - ok
    missing_crs = int(df["crs_text"].isna().sum())
    bounds_flagged = int(df["bounds_flag"].notna().sum())

    top_errors = (
        df.loc[~df["read_ok"], ["error_type", "error_message"]]
        .fillna("")
        .value_counts()
        .head(10)
        .reset_index(name="count")
    )
    top_flags = (
        df.loc[df["bounds_flag"].notna(), ["bounds_flag"]]
        .value_counts()
        .head(10)
        .reset_index(name="count")
        .rename(columns={"bounds_flag": "flag"})
    )

    md = []
    md.append("# TSIRD Raw Vector Inventory")
    md.append("")
    md.append(f"- Generated (UTC): **{now}**")
    md.append(f"- Raw vectors root: `{VECTORS_RAW_ROOT}`")
    md.append(f"- Total shapefiles found: **{total}**")
    md.append(f"- Read OK: **{ok}**")
    md.append(f"- Read failed: **{failed}**")
    md.append(f"- Missing CRS: **{missing_crs}**")
    md.append(f"- Bounds flagged: **{bounds_flagged}**")
    md.append("")
    md.append("## Most common read failures (top 10)")
    md.append("")
    md.append("_None_" if len(top_errors) == 0 else _df_to_md_table(top_errors))
    md.append("")
    md.append("## Most common bounds flags (top 10)")
    md.append("")
    md.append("_None_" if len(top_flags) == 0 else _df_to_md_table(top_flags))
    md.append("")

    md_out.write_text("\n".join(md), encoding="utf-8")

    print(f"Wrote: {csv_out}")
    print(f"Wrote: {md_out}")


if __name__ == "__main__":
    main()