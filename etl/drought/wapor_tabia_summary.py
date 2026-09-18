"""Acquire one bounded FAO WaPOR v3 dekad and derive Tabia water-use context.

This retrieves only the Tigray window of the provider COGs.  Transpiration is
the headline vegetation-water-use measure; AETI is retained as supporting
context.  The dekadal products are expressed as daily means in mm/day (not
10-day totals). Neither product is treated as current crop extent, yield,
drought, or food-security classification.
"""
import csv
import hashlib
import json
import os
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import psycopg2
import rasterio
import requests
from rasterio.mask import mask
from rasterio.windows import from_bounds

from publish_evidence_raster import publish_provider_band

CATALOG_BASE = "https://data.apps.fao.org/gismgr/api/v2/catalog/workspaces/WAPOR-3/mapsets"
T_MAPSET = "L2-T-D"
AETI_MAPSET = "L2-AETI-D"
SOURCE_ID = "fao-wapor-v3"
MAX_CURRENT_AGE_DAYS = 25
MIN_COVERAGE_PCT = 90.0
PERIOD_RE = re.compile(r"\.(\d{4})-(\d{2})-D([123])$")


def dsn():
    return " ".join(("host=tsird-postgis", "port=5432", f"dbname={os.environ['POSTGRES_DB']}",
                     f"user={os.environ['POSTGRES_USER']}", f"password={os.environ['POSTGRES_PASSWORD']}"))


def request_json(url):
    response = requests.get(url, timeout=(30, 120))
    response.raise_for_status()
    payload = response.json()
    return payload.get("response", payload)


def catalogue_items(mapset):
    """Read all paginated provider records without accepting a caller URL."""
    url = f"{CATALOG_BASE}/{mapset}/rasters"
    items = []
    while url:
        response = request_json(url)
        items.extend(response.get("items") or [])
        next_links = [link.get("href") for link in response.get("links") or [] if link.get("rel") == "next"]
        url = next_links[0] if next_links else None
    return items


def parse_period(code):
    match = PERIOD_RE.search(code or "")
    if not match:
        return None
    year, month, dekad = map(int, match.groups())
    start_day = (dekad - 1) * 10 + 1
    start = date(year, month, start_day)
    if dekad == 1:
        end = date(year, month, 10)
    elif dekad == 2:
        end = date(year, month, 20)
    else:
        next_month = date(year + (month == 12), 1 if month == 12 else month + 1, 1)
        end = next_month - timedelta(days=1)
    return start, end


def latest_pair():
    t_items = {item.get("code"): item for item in catalogue_items(T_MAPSET) if parse_period(item.get("code"))}
    aeti_items = {item.get("code"): item for item in catalogue_items(AETI_MAPSET) if parse_period(item.get("code"))}
    candidates = []
    for t_code, t_item in t_items.items():
        period = parse_period(t_code)
        if not period:
            continue
        suffix = t_code.split(f"WAPOR-3.{T_MAPSET}.", 1)[-1]
        aeti_code = f"WAPOR-3.{AETI_MAPSET}.{suffix}"
        aeti_item = aeti_items.get(aeti_code)
        if aeti_item and t_item.get("downloadUrl") and aeti_item.get("downloadUrl"):
            candidates.append((period[1], period[0], t_item, aeti_item))
    if not candidates:
        raise RuntimeError("FAO WaPOR catalogue has no matching T/AETI dekadal pair")
    _, start, transpiration, aeti = max(candidates, key=lambda entry: entry[0])
    return start, parse_period(transpiration["code"])[1], transpiration, aeti


def pair_at_period_start(requested_start):
    """Return the exact paired provider dekad requested for a history run."""
    t_items = {item.get("code"): item for item in catalogue_items(T_MAPSET) if parse_period(item.get("code"))}
    aeti_items = {item.get("code"): item for item in catalogue_items(AETI_MAPSET) if parse_period(item.get("code"))}
    for t_code, t_item in t_items.items():
        period = parse_period(t_code)
        if not period or period[0] != requested_start:
            continue
        suffix = t_code.split(f"WAPOR-3.{T_MAPSET}.", 1)[-1]
        aeti_item = aeti_items.get(f"WAPOR-3.{AETI_MAPSET}.{suffix}")
        if aeti_item and t_item.get("downloadUrl") and aeti_item.get("downloadUrl"):
            return period[0], period[1], t_item, aeti_item
    raise RuntimeError("FAO WaPOR catalogue has no matching T/AETI pair for the requested dekad")


def fetch_tabias_and_bounds():
    with psycopg2.connect(dsn()) as conn, conn.cursor() as cur:
        cur.execute('''SELECT i.tsird_tabia_id, t."TABIA", t."WEREDA", ST_AsGeoJSON(ST_MakeValid(t.geometry))
                       FROM tigray_tabias_ws t JOIN tsird.tabia_identity i USING (tsird_tabia_id)
                       ORDER BY i.tsird_tabia_id''')
        tabias = [(row[0], row[1], row[2], json.loads(row[3])) for row in cur.fetchall()]
        cur.execute('''SELECT ST_XMin(ST_Extent(geometry)::box3d), ST_YMin(ST_Extent(geometry)::box3d),
                              ST_XMax(ST_Extent(geometry)::box3d), ST_YMax(ST_Extent(geometry)::box3d)
                       FROM tigray_tabias_ws''')
        left, bottom, right, top = cur.fetchone()
    return tabias, (float(left) - .02, float(bottom) - .02, float(right) + .02, float(top) + .02)


def clip_cog(url, target, bounds):
    """Use COG range requests and write only the local Tigray window."""
    if target.exists():
        with rasterio.open(target) as source:
            if source.count == 1 and source.crs:
                return sha256(target), float(source.scales[0] or 1.0), source.crs.to_string()
        raise RuntimeError("existing WaPOR cache has unexpected raster structure")
    temporary = target.with_suffix(target.suffix + ".part")
    temporary.unlink(missing_ok=True)
    try:
        with rasterio.open(url) as source:
            window = from_bounds(*bounds, transform=source.transform).round_offsets().round_lengths()
            window = window.intersection(rasterio.windows.Window(0, 0, source.width, source.height))
            if window.width <= 0 or window.height <= 0:
                raise RuntimeError("WaPOR source does not intersect the Tigray bounds")
            values = source.read(1, window=window)
            transform = source.window_transform(window)
            profile = source.profile.copy()
            profile.update(width=values.shape[1], height=values.shape[0], transform=transform,
                           compress="deflate", tiled=True)
            target.parent.mkdir(parents=True, exist_ok=True)
            with rasterio.open(temporary, "w", **profile) as destination:
                destination.write(values, 1)
                destination.scales = [float(source.scales[0] or 1.0)]
        temporary.replace(target)
    finally:
        if temporary.exists():
            temporary.unlink()
    with rasterio.open(target) as source:
        if source.count != 1 or source.crs is None:
            raise RuntimeError("saved WaPOR subset has unexpected raster structure")
        return sha256(target), float(source.scales[0] or 1.0), source.crs.to_string()


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def summary_value(source, geometry, scale):
    values, _ = mask(source, [geometry], crop=True, filled=False)
    band = values[0]
    inside = ~np.ma.getmaskarray(band)
    # WaPOR COGs can use integer storage; promote the raw data before adding
    # a NaN-style missing representation, rather than asking masked arrays to
    # put NaN into their integer fill value.
    raw = np.asarray(band.data, dtype="float64")
    valid = inside & np.isfinite(raw)
    if source.nodata is not None:
        valid &= raw != source.nodata
    cells = int(inside.sum())
    valid_count = int(valid.sum())
    mean = round(float((raw[valid] * scale).mean()), 3) if valid_count else None
    return mean, valid_count, cells


def main():
    requested_start = os.environ.get("WAPOR_PERIOD_START")
    period_start, period_end, t_item, aeti_item = (
        pair_at_period_start(date.fromisoformat(requested_start)) if requested_start else latest_pair()
    )
    tabias, bounds = fetch_tabias_and_bounds()
    run_id = f"fao-wapor-v3-l2-{period_start:%Y%m}-d{((period_start.day - 1) // 10) + 1}"
    root = Path("/data/drought")
    raw_dir = root / "raw" / "fao-wapor-v3"
    t_path = raw_dir / f"{run_id}-transpiration.tif"
    aeti_path = raw_dir / f"{run_id}-aeti.tif"
    t_hash, t_scale, t_crs = clip_cog(t_item["downloadUrl"], t_path, bounds)
    aeti_hash, aeti_scale, aeti_crs = clip_cog(aeti_item["downloadUrl"], aeti_path, bounds)
    if t_crs != aeti_crs:
        raise RuntimeError("WaPOR T and AETI CRS differ")
    pilot_only = os.environ.get("TSIRD_BASELINE_PILOT_ONLY") == "1"
    candidate_only = os.environ.get("TSIRD_SEASONAL_REFERENCE_CANDIDATE") == "1"
    historical_only = os.environ.get("TSIRD_RETAIN_HISTORICAL_ONLY") == "1"
    if not pilot_only and not candidate_only and not historical_only:
        publish_provider_band(t_path, root / "published" / "wapor-transpiration-current.tif", band=1,
                              scale=t_scale, offset=0, mask_band=None)
    rows = []
    with rasterio.open(t_path) as t_source, rasterio.open(aeti_path) as aeti_source:
        for tabia_id, tabia, woreda, geometry in tabias:
            transpiration, valid, cells = summary_value(t_source, geometry, t_scale)
            aeti, aeti_valid, aeti_cells = summary_value(aeti_source, geometry, aeti_scale)
            coverage = round(100 * min(valid, aeti_valid) / max(cells, aeti_cells), 1) if max(cells, aeti_cells) else 0.0
            rows.append({"tsird_tabia_id": tabia_id, "tabia_name_en": tabia, "woreda_name_en": woreda,
                         "transpiration_mm": transpiration, "aeti_mm": aeti,
                         "valid_pixel_count": min(valid, aeti_valid), "grid_cell_count": max(cells, aeti_cells),
                         "coverage_pct": coverage,
                         "quality_status": "ok" if transpiration is not None and aeti is not None and coverage >= MIN_COVERAGE_PCT else "insufficient_grid_coverage"})
    age = (datetime.now(timezone.utc).date() - period_end).days
    status = "development" if age <= MAX_CURRENT_AGE_DAYS else "degraded"
    outputs = root / "outputs"; outputs.mkdir(parents=True, exist_ok=True)
    base = outputs / run_id
    with base.with_suffix(".csv").open("w", newline="", encoding="utf-8") as destination:
        writer = csv.DictWriter(destination, fieldnames=rows[0].keys()); writer.writeheader(); writer.writerows(rows)
    manifest = {"run_id": run_id, "status": status, "source_id": SOURCE_ID,
                "source_product": "FAO WaPOR v3 Level 2 dekadal Transpiration (T) with AETI context",
                "mapset_code": T_MAPSET, "aeti_mapset_code": AETI_MAPSET,
                "source_period_start": period_start.isoformat(), "source_period_end": period_end.isoformat(),
                "source_revision": "unknown", "native_resolution": "approximately 100 m, dekadal composite (mm/day)",
                "raster_paths": {"transpiration": str(t_path), "aeti": str(aeti_path)},
                "raster_sha256": {"transpiration": t_hash, "aeti": aeti_hash},
                "source_urls": {"transpiration": t_item["downloadUrl"], "aeti": aeti_item["downloadUrl"]},
                "source_retrieved_at": datetime.now(timezone.utc).isoformat(), "source_age_days": age,
                "included_tabias": len(rows), "boundary_set_version": "tsird-tabias-v1",
                "method": "Provider COG subsets clipped to Tigray bounds; pixel-centre Tabia zonal means; source scale retained from GeoTIFF metadata.",
                "baseline_pilot_only": pilot_only,
                "seasonal_reference_candidate_only": candidate_only,
                "historical_retention_only": historical_only,
                "publication_note": ("Baseline pilot only. Transpiration is vegetation water-use context and AETI "
                                     "includes evaporation/interception; neither is a baseline, current crop extent, "
                                     "yield, drought, food-security classification, response priority, forecast, or published layer."
                                     if pilot_only else
                                     "Seasonal-reference candidate retrieval only. Transpiration and AETI are retained observed "
                                     "evidence for a versioned same-calendar-month comparison; they are not a forecast, drought or "
                                     "food-security classification, response priority, or published layer."
                                     if candidate_only else
                                     "Development artifact only. Transpiration is vegetation water-use context and AETI includes evaporation/interception. Neither is current crop extent, yield, drought, food insecurity, or response priority.")}
    base.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"run_id": run_id, "status": status, "rows": len(rows), "source_period_end": period_end.isoformat()}, indent=2))


if __name__ == "__main__":
    main()
