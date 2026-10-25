"""Build a bounded, DEV-only monthly HLS NDMI feasibility artifact.

This collector reads only the windows required for twenty deterministic Tabias
from NASA HLS v2 Cloud Optimized GeoTIFFs.  It retains compact statistics and
provenance only: never a raw scene, an access token, a provider URL, or a
regional raster.  It is deliberately not a drought classification, forecast,
or publication path.
"""
import argparse
import contextlib
import csv
import json
import os
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import psycopg2
import rasterio
import requests
from rasterio.mask import mask
from rasterio.warp import transform_geom

SOURCE_ID = "nasa-hls-v2-ndmi-monthly-pilot"
PRODUCT = "NASA HLS v2.0 L30/S30 harmonized surface reflectance"
PROCESSING_VERSION = "tsird-hls-ndmi-monthly-pilot.v1"
CMR_STAC_SEARCH_URL = "https://cmr.earthdata.nasa.gov/stac/LPCLOUD/search"
HLS_COLLECTIONS = {
    "HLSS30_2.0": {"sensor": "Sentinel-2 MSI", "nir": "B8A", "swir": "B11", "qa": "Fmask"},
    "HLSL30_2.0": {"sensor": "Landsat 8/9 OLI", "nir": "B05", "swir": "B06", "qa": "Fmask"},
}
PILOT_TABIA_LIMIT = 20
MONTHLY_LATENCY_DAYS = 5
MIN_VALID_OBSERVATION_COVERAGE_PCT = 70.0
MIN_VALID_OBSERVATION_PIXELS = 30
MIN_USABLE_ACQUISITIONS = 2
# Fmask bits: cloud, adjacent cloud/shadow, cloud shadow, snow/ice, water.
# High aerosol (binary 11 in bits 6--7) is also excluded.
EXCLUDED_FMASK_BITS = 0b00111110
HIGH_AEROSOL_BITS = 0b11000000


def dsn():
    return " ".join(("host=tsird-postgis", "port=5432", f"dbname={os.environ['POSTGRES_DB']}",
                     f"user={os.environ['POSTGRES_USER']}", f"password={os.environ['POSTGRES_PASSWORD']}"))


def completed_month(now):
    """Return the most recent calendar month with a five-day provider margin."""
    candidate = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if candidate.day <= MONTHLY_LATENCY_DAYS:
        candidate = candidate.replace(day=1)
    else:
        candidate = candidate.replace(day=1)
    end = candidate
    if end.month == 1:
        start = end.replace(year=end.year - 1, month=12)
    else:
        start = end.replace(month=end.month - 1)
    return start, end


def earthdata_token():
    token = os.environ.get("EARTHDATA_TOKEN", "").strip()
    if not token:
        raise RuntimeError("HLS pilot requires EARTHDATA_TOKEN in the local DEV runner environment")
    return token


def pilot_tabias():
    """Take five repeatable Tabias from each area quartile, not a regional sample."""
    with psycopg2.connect(dsn()) as conn, conn.cursor() as cur:
        cur.execute('''WITH ranked AS (
                         SELECT i.tsird_tabia_id, t."TABIA", t."WEREDA", ST_AsGeoJSON(t.geometry),
                                ntile(4) OVER (ORDER BY ST_Area(ST_Transform(t.geometry, 32637))) AS area_quartile
                         FROM tigray_tabias_ws t JOIN tsird.tabia_identity i USING (tsird_tabia_id)
                       ), sampled AS (
                         SELECT *, row_number() OVER (PARTITION BY area_quartile ORDER BY md5(tsird_tabia_id)) AS sample_rank
                         FROM ranked
                       )
                       SELECT tsird_tabia_id, "TABIA", "WEREDA", st_asgeojson
                       FROM sampled WHERE sample_rank <= 5 ORDER BY area_quartile, tsird_tabia_id''')
        rows = cur.fetchall()
    if len(rows) != PILOT_TABIA_LIMIT:
        raise RuntimeError("HLS pilot could not select exactly twenty canonical Tabias")
    return [(row[0], row[1], row[2], json.loads(row[3])) for row in rows]


def bounds(geometry):
    coordinates = []
    def visit(value):
        if isinstance(value, (int, float)):
            return
        if len(value) == 2 and all(isinstance(item, (int, float)) for item in value):
            coordinates.append(value)
        else:
            for item in value:
                visit(item)
    visit(geometry["coordinates"])
    xs, ys = zip(*coordinates)
    return [min(xs), min(ys), max(xs), max(ys)]


def stac_items(geometry, start, end):
    body = {
        "collections": list(HLS_COLLECTIONS),
        "bbox": bounds(geometry),
        "datetime": f"{start.isoformat().replace('+00:00', 'Z')}/{end.isoformat().replace('+00:00', 'Z')}",
        "limit": 250,
    }
    try:
        response = requests.post(CMR_STAC_SEARCH_URL, json=body, timeout=90)
        response.raise_for_status()
        features = response.json().get("features") or []
    except (requests.RequestException, ValueError) as exc:
        raise RuntimeError("NASA CMR-STAC discovery failed") from exc
    unique = {feature.get("id"): feature for feature in features if feature.get("id") and feature.get("collection") in HLS_COLLECTIONS}
    return list(unique.values())


def asset_href(item, key):
    for name, asset in (item.get("assets") or {}).items():
        if name.lower() == key.lower() and isinstance(asset, dict) and isinstance(asset.get("href"), str):
            return asset["href"]
    raise RuntimeError("HLS granule omitted a required band or Fmask asset")


def acquired_at(item):
    stamp = (item.get("properties") or {}).get("datetime")
    if not isinstance(stamp, str):
        raise RuntimeError("HLS granule omitted its acquisition time")
    return datetime.fromisoformat(stamp.replace("Z", "+00:00"))


def scene_values(item, geometry, token):
    collection = item.get("collection")
    if collection not in HLS_COLLECTIONS:
        raise RuntimeError("HLS granule has an unexpected collection")
    bands = HLS_COLLECTIONS[collection]
    headers = f"Authorization: Bearer {token}"
    try:
        with rasterio.Env(GDAL_HTTP_HEADERS=headers, GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR"):
            with contextlib.ExitStack() as stack:
                nir = stack.enter_context(rasterio.open("/vsicurl/" + asset_href(item, bands["nir"])))
                swir = stack.enter_context(rasterio.open("/vsicurl/" + asset_href(item, bands["swir"])))
                qa = stack.enter_context(rasterio.open("/vsicurl/" + asset_href(item, bands["qa"])))
                if nir.crs != swir.crs or nir.crs != qa.crs:
                    raise RuntimeError("HLS granule bands do not share a CRS")
                projected = transform_geom("EPSG:4326", nir.crs, geometry, precision=8)
                nir_data, _ = mask(nir, [projected], crop=True, filled=False)
                swir_data, _ = mask(swir, [projected], crop=True, filled=False)
                qa_data, _ = mask(qa, [projected], crop=True, filled=False)
    except (rasterio.errors.RasterioError, ValueError) as exc:
        raise RuntimeError("HLS COG range read failed") from exc
    if nir_data.shape != swir_data.shape or nir_data.shape != qa_data.shape:
        raise RuntimeError("HLS granule bands do not share a grid")
    nir_values = np.asarray(nir_data[0].filled(-9999), dtype=np.float32)
    swir_values = np.asarray(swir_data[0].filled(-9999), dtype=np.float32)
    qa_values = np.asarray(qa_data[0].filled(255), dtype=np.uint8)
    inside = ~np.ma.getmaskarray(nir_data[0])
    denominator = nir_values + swir_values
    valid = (inside & (nir_values > -9999) & (swir_values > -9999) &
             (nir_values < 12000) & (swir_values < 12000) & (denominator > 0) &
             (qa_values != 255) & ((qa_values & EXCLUDED_FMASK_BITS) == 0) &
             ((qa_values & HIGH_AEROSOL_BITS) != HIGH_AEROSOL_BITS))
    values = ((nir_values[valid] - swir_values[valid]) / denominator[valid]).astype(np.float32)
    return int(inside.sum()), values


def summarize_tabia(geometry, start, end, token):
    items = stac_items(geometry, start, end)
    values, usable_dates = [], []
    candidate_pixels = 0
    for item in items:
        cells, ndmi = scene_values(item, geometry, token)
        candidate_pixels += cells
        if ndmi.size:
            values.append(ndmi)
            usable_dates.append(acquired_at(item))
    combined = np.concatenate(values) if values else np.array([], dtype=np.float32)
    valid = int(combined.size)
    coverage = round(100 * valid / candidate_pixels, 1) if candidate_pixels else 0.0
    if valid < MIN_VALID_OBSERVATION_PIXELS:
        quality = "insufficient_valid_pixel_count"
    elif coverage < MIN_VALID_OBSERVATION_COVERAGE_PCT:
        quality = "insufficient_observation_coverage"
    elif len(usable_dates) < MIN_USABLE_ACQUISITIONS:
        quality = "insufficient_acquisition_count"
    else:
        quality = "ok"
    ordered_dates = sorted(usable_dates)
    return {
        "ndmi_mean": round(float(combined.mean()), 4) if valid else None,
        "ndmi_median": round(float(np.median(combined)), 4) if valid else None,
        "valid_observation_pixel_count": valid,
        "candidate_observation_pixel_count": candidate_pixels,
        "coverage_pct": coverage,
        "candidate_acquisition_count": len(items),
        "usable_acquisition_count": len(usable_dates),
        "first_acquisition_at": ordered_dates[0].isoformat() if ordered_dates else None,
        "last_acquisition_at": ordered_dates[-1].isoformat() if ordered_dates else None,
        "median_acquisition_at": ordered_dates[len(ordered_dates) // 2].isoformat() if ordered_dates else None,
        "quality_status": quality,
    }


def main():
    parser = argparse.ArgumentParser(description="Run the bounded DEV-only HLS monthly NDMI pilot")
    parser.add_argument("--dry-run", action="store_true", help="print the contract without database or Earthdata access")
    args = parser.parse_args()
    start, end = completed_month(datetime.now(timezone.utc))
    if args.dry_run:
        print(json.dumps({"source_id": SOURCE_ID, "source_collections": list(HLS_COLLECTIONS),
                          "observation_start": start.isoformat(), "observation_end": end.isoformat(),
                          "tabia_limit": PILOT_TABIA_LIMIT, "native_resolution": "30 m",
                          "minimums": {"coverage_pct": MIN_VALID_OBSERVATION_COVERAGE_PCT,
                                       "valid_observation_pixels": MIN_VALID_OBSERVATION_PIXELS,
                                       "usable_acquisitions": MIN_USABLE_ACQUISITIONS},
                          "cmr_stac_request": {"collections": list(HLS_COLLECTIONS), "datetime": "completed calendar month", "limit": 250}}, indent=2))
        return
    token = earthdata_token()
    tabias = pilot_tabias()
    rows = []
    for tabia_id, tabia, woreda, geometry in tabias:
        row = {"tsird_tabia_id": tabia_id, "tabia_name_en": tabia, "woreda_name_en": woreda}
        row.update(summarize_tabia(geometry, start, end, token))
        rows.append(row)
    run_id = f"nasa-hls-ndmi-monthly-pilot-{start:%Y%m}"
    root = Path("/data/drought/outputs"); root.mkdir(parents=True, exist_ok=True); base = root / run_id
    with base.with_suffix(".csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys()); writer.writeheader(); writer.writerows(rows)
    retrieved = datetime.now(timezone.utc).isoformat()
    status = "development" if any(row["quality_status"] == "ok" for row in rows) else "degraded"
    manifest = {
        "run_id": run_id, "source_id": SOURCE_ID, "source_product": PRODUCT, "status": status,
        "observation_start": start.isoformat(), "observation_end": end.isoformat(), "native_resolution": "30 m",
        "source_collections": list(HLS_COLLECTIONS),
        "validity_mask": "Exclude Fmask cloud, adjacent cloud/shadow, cloud shadow, snow/ice, water, high aerosol, fill, saturation and zero denominator.",
        "coverage_definition": "valid observation pixels divided by candidate observation pixels across all queried HLS acquisitions; it is not a gap-filled spatial composite coverage.",
        "min_valid_observation_coverage_pct": MIN_VALID_OBSERVATION_COVERAGE_PCT,
        "min_valid_observation_pixels": MIN_VALID_OBSERVATION_PIXELS,
        "min_usable_acquisition_count": MIN_USABLE_ACQUISITIONS,
        "pilot_tabia_limit": PILOT_TABIA_LIMIT, "included_tabias": len(rows), "source_retrieved_at": retrieved,
        "processing_version": PROCESSING_VERSION,
        "method": "CMR-STAC discovery; authenticated HLS v2 COG range reads; per-acquisition NDMI from harmonized narrow NIR and SWIR1, then Tabia observation-level mean and median. No temporal interpolation or long-window composite.",
        "publication_note": "Development-only HLS monthly feasibility pilot. Not a drought, food-security, priority, forecast, allocation, response, or public release product.",
        "geoinfotech_acknowledgement": "The educational index-selection framing refers to Geoinfotech's Spatial Indices Analysis explainer shared with TSIRD on 2026-10-24. Geoinfotech does not supply HLS data, validate the method, or endorse TSIRD results.",
    }
    base.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"run_id": run_id, "status": status, "rows": len(rows),
                      "quality_ok_rows": sum(row["quality_status"] == "ok" for row in rows)}, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # Never echo URLs, provider responses, geometry, or authentication material.
        raise SystemExit(f"HLS monthly NDMI pilot failed: {type(exc).__name__}: {str(exc)[:240]}")
