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
import warnings
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import psycopg2
import rasterio
import requests
from rasterio.features import geometry_mask
from rasterio.mask import mask
from rasterio.transform import from_origin
from rasterio.warp import Resampling, reproject, transform_geom

SOURCE_ID = "nasa-hls-v2-ndmi-monthly-pilot"
PRODUCT = "NASA HLS v2.0 L30/S30 harmonized surface reflectance"
PROCESSING_VERSION = "tsird-hls-ndmi-monthly-pilot.v2-spatial-coverage"
CMR_STAC_SEARCH_URL = "https://cmr.earthdata.nasa.gov/stac/LPCLOUD/search"
HLS_COLLECTIONS = {
    "HLSS30_2.0": {"sensor": "Sentinel-2 MSI", "nir": "B8A", "swir": "B11", "qa": "Fmask"},
    "HLSL30_2.0": {"sensor": "Landsat 8/9 OLI", "nir": "B05", "swir": "B06", "qa": "Fmask"},
}
PILOT_TABIA_LIMIT = 20
MONTHLY_LATENCY_DAYS = 5
MIN_SPATIAL_COVERAGE_PCT = 70.0
MIN_LIMITED_SPATIAL_COVERAGE_PCT = 30.0
MIN_VALID_OBSERVATION_PIXELS = 30
MIN_USABLE_ACQUISITIONS = 2
ANALYSIS_CRS = "EPSG:6933"
ANALYSIS_RESOLUTION_METERS = 30.0
# Fmask bits: cloud, adjacent cloud/shadow, cloud shadow, snow/ice, water.
# High aerosol (binary 11 in bits 6--7) is also excluded.
# Operational mode allows the HLS 150 m "adjacent to cloud/shadow" buffer
# (bit 2) but reports every accepted pixel.  NASA says users may retain that
# buffer where data loss is a concern.  Cloud, cloud shadow, snow/ice, water,
# fill/saturation, and high aerosol stay excluded in both profiles.
STRICT_EXCLUDED_FMASK_BITS = 0b00111110
OPERATIONAL_EXCLUDED_FMASK_BITS = 0b00111010
HIGH_AEROSOL_BITS = 0b11000000


def dsn():
    return " ".join(("host=tsird-postgis", "port=5432", f"dbname={os.environ['POSTGRES_DB']}",
                     f"user={os.environ['POSTGRES_USER']}", f"password={os.environ['POSTGRES_PASSWORD']}"))


def completed_month(now):
    """Return the most recent calendar month with a five-day provider margin."""
    first_of_this_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    # Do not ask for the immediately preceding month during the provider's
    # declared five-day publication margin.  This prevents a 1--5 November
    # run from treating October as complete before HLS is expected to have
    # indexed all of its scenes.
    if now.day <= MONTHLY_LATENCY_DAYS:
        end = (first_of_this_month - timedelta(days=1)).replace(day=1)
    else:
        end = first_of_this_month
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


def analysis_grid(geometry):
    """Return a fixed 30 m equal-area grid and the pixels inside this Tabia."""
    projected = transform_geom("EPSG:4326", ANALYSIS_CRS, geometry, precision=8)
    min_x, min_y, max_x, max_y = bounds(projected)
    left = np.floor(min_x / ANALYSIS_RESOLUTION_METERS) * ANALYSIS_RESOLUTION_METERS
    top = np.ceil(max_y / ANALYSIS_RESOLUTION_METERS) * ANALYSIS_RESOLUTION_METERS
    width = max(1, int(np.ceil((max_x - left) / ANALYSIS_RESOLUTION_METERS)))
    height = max(1, int(np.ceil((top - min_y) / ANALYSIS_RESOLUTION_METERS)))
    transform = from_origin(left, top, ANALYSIS_RESOLUTION_METERS, ANALYSIS_RESOLUTION_METERS)
    inside = geometry_mask([projected], out_shape=(height, width), transform=transform, invert=True)
    if not inside.any():
        raise RuntimeError("HLS analysis grid contains no Tabia pixels")
    return transform, inside


def reproject_to_analysis_grid(values, source_transform, source_crs, grid_transform, grid_shape):
    destination = np.full(grid_shape, np.nan, dtype=np.float32)
    reproject(
        source=values.astype(np.float32), destination=destination,
        src_transform=source_transform, src_crs=source_crs, src_nodata=np.nan,
        dst_transform=grid_transform, dst_crs=ANALYSIS_CRS, dst_nodata=np.nan,
        resampling=Resampling.nearest,
    )
    return destination


def scene_grids(item, geometry, token, grid_transform, grid_shape):
    """Return strict and adjacency-allowed monthly NDMI grids for one scene."""
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
                nir_data, cropped_transform = mask(nir, [projected], crop=True, filled=False)
                swir_data, _ = mask(swir, [projected], crop=True, filled=False)
                qa_data, _ = mask(qa, [projected], crop=True, filled=False)
    except ValueError as exc:
        # CMR-STAC selects on a geographic bounding box.  At an HLS tile edge
        # that can yield a scene whose actual pixel grid has no overlap with a
        # small Tabia.  It is not a failed acquisition and must not abort the
        # entire bounded pilot; it contributes neither pixels nor NDMI values.
        if "do not overlap raster" in str(exc).lower():
            return None
        raise RuntimeError("HLS pixel-window extraction failed") from exc
    except rasterio.errors.RasterioError as exc:
        raise RuntimeError("HLS COG range read failed") from exc
    if nir_data.shape != swir_data.shape or nir_data.shape != qa_data.shape:
        raise RuntimeError("HLS granule bands do not share a grid")
    nir_values = np.asarray(nir_data[0].filled(-9999), dtype=np.float32)
    swir_values = np.asarray(swir_data[0].filled(-9999), dtype=np.float32)
    qa_values = np.asarray(qa_data[0].filled(255), dtype=np.uint8)
    inside = ~np.ma.getmaskarray(nir_data[0])
    denominator = nir_values + swir_values
    basic_valid = (inside & (nir_values > -9999) & (swir_values > -9999) &
                   (nir_values < 12000) & (swir_values < 12000) & (denominator > 0) &
                   (qa_values != 255) & ((qa_values & HIGH_AEROSOL_BITS) != HIGH_AEROSOL_BITS))
    strict_valid = basic_valid & ((qa_values & STRICT_EXCLUDED_FMASK_BITS) == 0)
    operational_valid = basic_valid & ((qa_values & OPERATIONAL_EXCLUDED_FMASK_BITS) == 0)
    ndmi = np.full(nir_values.shape, np.nan, dtype=np.float32)
    ndmi[basic_valid] = ((nir_values[basic_valid] - swir_values[basic_valid]) /
                         denominator[basic_valid]).astype(np.float32)
    strict = ndmi.copy(); strict[~strict_valid] = np.nan
    operational = ndmi.copy(); operational[~operational_valid] = np.nan
    adjacent_accepted = np.full(nir_values.shape, np.nan, dtype=np.float32)
    adjacent_accepted[operational_valid & ~strict_valid] = 1.0
    return {
        "strict": reproject_to_analysis_grid(strict, cropped_transform, nir.crs, grid_transform, grid_shape),
        "adjacency_allowed": reproject_to_analysis_grid(operational, cropped_transform, nir.crs, grid_transform, grid_shape),
        "adjacency_accepted": reproject_to_analysis_grid(adjacent_accepted, cropped_transform, nir.crs, grid_transform, grid_shape),
    }


def profile_summary(scene_grids, candidate_acquisition_count, inside, profile):
    stack = np.stack([scene[profile] for scene in scene_grids]) if scene_grids else np.empty((0, *inside.shape))
    counts = np.isfinite(stack).sum(axis=0) if stack.size else np.zeros(inside.shape, dtype=np.int16)
    accepted = inside & (counts >= 1)
    twice = inside & (counts >= 2)
    total = int(inside.sum())
    valid_spatial = int(accepted.sum())
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        composite = np.nanmedian(stack, axis=0) if stack.size else np.full(inside.shape, np.nan)
    values = composite[accepted]
    coverage = round(100 * valid_spatial / total, 1)
    twice_coverage = round(100 * int(twice.sum()) / total, 1)
    valid_observations = int(counts[inside].sum())
    usable = int(sum(np.isfinite(scene[profile][inside]).any() for scene in scene_grids))
    if valid_spatial < MIN_VALID_OBSERVATION_PIXELS or usable < MIN_USABLE_ACQUISITIONS:
        tier = "insufficient"
    elif coverage < MIN_LIMITED_SPATIAL_COVERAGE_PCT:
        tier = "insufficient"
    elif coverage < MIN_SPATIAL_COVERAGE_PCT:
        tier = "limited"
    else:
        tier = "adequate"
    return {
        "ndmi_mean": round(float(values.mean()), 4) if values.size else None,
        "ndmi_median": round(float(np.median(values)), 4) if values.size else None,
        "spatial_coverage_pct": coverage,
        "two_observation_coverage_pct": twice_coverage,
        "median_valid_observation_count": round(float(np.median(counts[accepted])), 1) if accepted.any() else None,
        "valid_spatial_pixel_count": valid_spatial,
        "total_eligible_pixel_count": total,
        "valid_observation_pixel_count": valid_observations,
        "candidate_acquisition_count": candidate_acquisition_count,
        "usable_acquisition_count": usable,
        "evidence_tier": tier,
    }


def summarize_tabia(geometry, start, end, token):
    items = stac_items(geometry, start, end)
    grid_transform, inside = analysis_grid(geometry)
    scenes, usable_dates = [], {"strict": [], "adjacency_allowed": []}
    for item in items:
        result = scene_grids(item, geometry, token, grid_transform, inside.shape)
        if result is None:
            continue
        scenes.append(result)
        observed_at = acquired_at(item)
        for profile in usable_dates:
            if np.isfinite(result[profile][inside]).any():
                usable_dates[profile].append(observed_at)
    profiles = {profile: profile_summary(scenes, len(items), inside, profile) for profile in usable_dates}
    for profile, dates in usable_dates.items():
        ordered = sorted(dates)
        profiles[profile].update({
            "first_acquisition_at": ordered[0].isoformat() if ordered else None,
            "last_acquisition_at": ordered[-1].isoformat() if ordered else None,
            "median_acquisition_at": ordered[len(ordered) // 2].isoformat() if ordered else None,
            "adjacency_accepted_pixel_count": int(sum(np.isfinite(scene["adjacency_accepted"][inside]).sum() for scene in scenes)) if profile == "adjacency_allowed" else 0,
        })
    return profiles


def main():
    parser = argparse.ArgumentParser(description="Run the bounded DEV-only HLS monthly NDMI pilot")
    parser.add_argument("--dry-run", action="store_true", help="print the contract without database or Earthdata access")
    args = parser.parse_args()
    start, end = completed_month(datetime.now(timezone.utc))
    if args.dry_run:
        print(json.dumps({"source_id": SOURCE_ID, "source_collections": list(HLS_COLLECTIONS),
                          "observation_start": start.isoformat(), "observation_end": end.isoformat(),
                          "tabia_limit": PILOT_TABIA_LIMIT, "native_resolution": "30 m",
                          "minimums": {"adequate_spatial_coverage_pct": MIN_SPATIAL_COVERAGE_PCT,
                                       "limited_spatial_coverage_pct": MIN_LIMITED_SPATIAL_COVERAGE_PCT,
                                       "valid_observation_pixels": MIN_VALID_OBSERVATION_PIXELS,
                                       "usable_acquisitions": MIN_USABLE_ACQUISITIONS},
                          "cmr_stac_request": {"collections": list(HLS_COLLECTIONS), "datetime": "completed calendar month", "limit": 250}}, indent=2))
        return
    token = earthdata_token()
    tabias = pilot_tabias()
    rows = []
    for tabia_id, tabia, woreda, geometry in tabias:
        row = {"tsird_tabia_id": tabia_id, "tabia_name_en": tabia, "woreda_name_en": woreda}
        profiles = summarize_tabia(geometry, start, end, token)
        primary = profiles["adjacency_allowed"]
        # Legacy pilot columns now explicitly carry the primary spatial result;
        # the full strict/operational comparison is stored in profile_* fields.
        row.update({
            "ndmi_mean": primary["ndmi_mean"], "ndmi_median": primary["ndmi_median"],
            "valid_observation_pixel_count": primary["valid_spatial_pixel_count"],
            "candidate_observation_pixel_count": primary["total_eligible_pixel_count"],
            "coverage_pct": primary["spatial_coverage_pct"],
            "candidate_acquisition_count": primary["candidate_acquisition_count"],
            "usable_acquisition_count": primary["usable_acquisition_count"],
            "first_acquisition_at": primary["first_acquisition_at"],
            "last_acquisition_at": primary["last_acquisition_at"],
            "median_acquisition_at": primary["median_acquisition_at"],
            "quality_status": "ok" if primary["evidence_tier"] == "adequate" else "insufficient_observation_coverage",
        })
        for profile, values in profiles.items():
            for key, value in values.items():
                row[f"{profile}_{key}"] = value
        rows.append(row)
    run_id = f"nasa-hls-ndmi-monthly-pilot-{start:%Y%m}-spatial-v2"
    root = Path("/data/drought/outputs"); root.mkdir(parents=True, exist_ok=True); base = root / run_id
    with base.with_suffix(".csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys()); writer.writeheader(); writer.writerows(rows)
    retrieved = datetime.now(timezone.utc).isoformat()
    status = "development"
    manifest = {
        "run_id": run_id, "source_id": SOURCE_ID, "source_product": PRODUCT, "status": status,
        "observation_start": start.isoformat(), "observation_end": end.isoformat(), "native_resolution": "30 m",
        "source_collections": list(HLS_COLLECTIONS),
        "validity_mask": "Strict profile excludes Fmask cloud, adjacent cloud/shadow, cloud shadow, snow/ice, water, high aerosol, fill, saturation and zero denominator. Operational profile retains adjacent-to-cloud/shadow pixels but reports them separately; all other exclusions remain.",
        "coverage_definition": "Spatial coverage is the percentage of 30 m equal-area Tabia pixels with at least one valid observation in the completed calendar month. Two-observation coverage is reported separately. It is not an observation-weighted coverage and no gap filling or temporal interpolation is used.",
        "min_valid_observation_coverage_pct": MIN_SPATIAL_COVERAGE_PCT,
        "min_valid_observation_pixels": MIN_VALID_OBSERVATION_PIXELS,
        "min_usable_acquisition_count": MIN_USABLE_ACQUISITIONS,
        "pilot_tabia_limit": PILOT_TABIA_LIMIT, "included_tabias": len(rows), "source_retrieved_at": retrieved,
        "processing_version": PROCESSING_VERSION,
        "method": "CMR-STAC discovery; authenticated HLS v2 COG range reads; paired NIR/SWIR1 NDMI per valid observation; then per-pixel monthly NDMI medians on a 30 m equal-area grid before Tabia statistics. Strict and adjacency-allowed Fmask profiles are compared. No temporal interpolation, gap filling, or long-window composite.",
        "publication_note": "Development-only HLS monthly feasibility pilot. Not a drought, food-security, priority, forecast, allocation, response, or public release product.",
        "geoinfotech_acknowledgement": "The educational index-selection framing refers to Geoinfotech's Spatial Indices Analysis explainer shared with TSIRD on 2026-10-24. Geoinfotech does not supply HLS data, validate the method, or endorse TSIRD results.",
    }
    base.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"run_id": run_id, "status": status, "rows": len(rows),
                      "adequate_primary_rows": sum(row["adjacency_allowed_evidence_tier"] == "adequate" for row in rows),
                      "limited_primary_rows": sum(row["adjacency_allowed_evidence_tier"] == "limited" for row in rows)}, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # Never echo URLs, provider responses, geometry, or authentication material.
        raise SystemExit(f"HLS monthly NDMI pilot failed: {type(exc).__name__}: {str(exc)[:240]}")
