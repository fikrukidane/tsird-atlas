"""Create a local, development-only CHIRPS Tabia rainfall-condition artifact.

The worker retains source provenance and excludes boundary records marked for
review. It uses pixel-centre zonal summaries, records cell count/coverage, and
must not be used as a fine-scale or public drought product without review.
"""
import argparse, csv, hashlib, json, os, shutil, tempfile, urllib.request
from calendar import monthrange
from datetime import datetime, timezone
from pathlib import Path

import psycopg2
import numpy as np
import rasterio
from rasterio.mask import mask
from publish_evidence_raster import publish_rainfall_total

BASE_URL = "https://data.chc.ucsb.edu/products/CHIRPS/v3.0/monthly/global/tifs"
SOURCE_PRODUCT = "CHIRPS v3 monthly"
SOURCE_VERSION = "v3.0"


def dsn():
    return " ".join((
        "host=tsird-postgis", "port=5432", f"dbname={os.environ['POSTGRES_DB']}",
        f"user={os.environ['POSTGRES_USER']}", f"password={os.environ['POSTGRES_PASSWORD']}"))


def fetch_tabias():
    with psycopg2.connect(dsn()) as conn, conn.cursor() as cur:
        cur.execute("""
          SELECT i.tsird_tabia_id, t."TABIA", t."WEREDA", ST_AsGeoJSON(t.geometry)
          FROM tigray_tabias_ws t JOIN tsird.tabia_identity i USING (tsird_tabia_id)
          ORDER BY i.tsird_tabia_id
        """)
        return [(row[0], row[1], row[2], json.loads(row[3])) for row in cur.fetchall()]


def fetch_bounds():
    with psycopg2.connect(dsn()) as conn, conn.cursor() as cur:
        cur.execute("""
          SELECT ST_XMin(ST_Extent(geometry)::box3d), ST_YMin(ST_Extent(geometry)::box3d),
                 ST_XMax(ST_Extent(geometry)::box3d), ST_YMax(ST_Extent(geometry)::box3d)
          FROM tigray_tabias_ws
        """)
        left, bottom, right, top = cur.fetchone()
        return (float(left) - 0.05, float(bottom) - 0.05,
                float(right) + 0.05, float(top) + 0.05)


def chirps_url(year, month):
    return f"{BASE_URL}/chirps-v3.0.{year}.{month:02d}.tif"


def validate_source_raster(source, bounds):
    """Reject an HTTP error page, malformed file, or unexpected CHIRPS grid.

    This is deliberately a small acquisition gate, not a scientific validation.
    It protects the ETL from treating a transient provider response as rainfall.
    """
    if source.stat().st_size < 100_000:
        raise ValueError("download is implausibly small for a global CHIRPS GeoTIFF")
    with rasterio.open(source) as src:
        if src.count != 1 or src.crs is None or src.crs.to_epsg() != 4326:
            raise ValueError("download does not have the expected single-band EPSG:4326 grid")
        window = src.window(*bounds).round_offsets().round_lengths()
        if window.width <= 0 or window.height <= 0:
            raise ValueError("CHIRPS grid does not intersect the Atlas Tabia extent")


def download_source(url, bounds):
    """Download and verify one source file, returning its temporary path/receipt."""
    with tempfile.TemporaryDirectory() as temp_dir:
        source = Path(temp_dir) / "source.tif"
        request = urllib.request.Request(url, headers={"User-Agent": "TSIRD-Atlas-development/1.0"})
        with urllib.request.urlopen(request, timeout=180) as response, source.open("wb") as handle:
            shutil.copyfileobj(response, handle)
            receipt = {
                "url": url,
                "http_status": getattr(response, "status", 200),
                "content_length": response.headers.get("Content-Length"),
                "etag": response.headers.get("ETag"),
                "last_modified": response.headers.get("Last-Modified"),
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
            }
        validate_source_raster(source, bounds)
        receipt["byte_count"] = source.stat().st_size
        receipt["sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
        # Keep the temporary file alive only while the caller copies its clipped
        # derivative.  Raw provider files are intentionally not retained here.
        yield source, receipt


def cache_clip(cache_dir, year, month, bounds, refresh_source=False):
    target = cache_dir / f"chirps-v3.0.{year}.{month:02d}.tif"
    receipt_path = target.with_suffix(".source.json")
    if target.exists() and not refresh_source:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8")) if receipt_path.exists() else {
            "url": chirps_url(year, month), "cache_status": "legacy_cache_without_receipt"
        }
        receipt["cache_status"] = "reused"
        return target, receipt
    url = chirps_url(year, month)
    for source, receipt in download_source(url, bounds):
        with rasterio.open(source) as src:
            window = src.window(*bounds).round_offsets().round_lengths()
            data = src.read(window=window)
            profile = src.profile.copy()
            profile.update(height=data.shape[1], width=data.shape[2], transform=src.window_transform(window), compress="deflate")
            temporary_target = target.with_suffix(".tmp.tif")
            with rasterio.open(temporary_target, "w", **profile) as dst:
                dst.write(data)
            temporary_target.replace(target)
    receipt["cache_status"] = "refreshed" if refresh_source else "downloaded"
    receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    return target, receipt


def zonal_seasonal_mean(paths, geometry):
    """Return a seasonal rainfall depth from per-month spatial means.

    A raster cell contains a rainfall depth, not a contribution that can be
    added across a Tabia.  Summing all pixels made the old development output
    depend on Tabia area.  We instead compute the mean depth for each month
    and sum those means to obtain the seasonal depth in millimetres.
    """
    seasonal_depth, cells, usable = 0.0, 0, 0
    for path in paths:
        with rasterio.open(path) as src:
            clipped, _ = mask(src, [geometry], crop=True, filled=False)
            grid_mask = np.ma.getmaskarray(clipped[0])
            values = clipped[0].compressed()
            cells += int((~grid_mask).sum())
            if values.size:
                seasonal_depth += float(values.mean())
                usable += int(values.size)
    return seasonal_depth, usable, cells


def percentile(value, baseline):
    below = sum(item < value for item in baseline)
    equal = sum(item == value for item in baseline)
    return round(100 * (below + 0.5 * equal) / len(baseline), 1)


def condition(value):
    if value <= 10: return "exceptionally_dry"
    if value <= 20: return "drier_than_typical"
    if value < 80: return "typical_range"
    if value < 90: return "wetter_than_typical"
    return "exceptionally_wet"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--analysis-year", type=int, required=True)
    parser.add_argument("--months", default="6,7")
    parser.add_argument("--baseline-start", type=int, default=1991)
    parser.add_argument("--baseline-end", type=int, default=2020)
    parser.add_argument("--data-root", default="/data/drought")
    parser.add_argument("--refresh-current-source", action="store_true",
                        help="Re-download and verify current-period files before deriving the artifact")
    parser.add_argument("--defer-current-publish", action="store_true",
                        help="Write only the run-specific raster; a caller promotes it after validation and load")
    args = parser.parse_args()
    months = [int(item) for item in args.months.split(",")]
    if not months or min(months) < 1 or max(months) > 12: raise ValueError("months must be 1..12")
    root = Path(args.data_root); cache = root / "cache" / "tabia-extent-v1"; output = root / "outputs"
    cache.mkdir(parents=True, exist_ok=True); output.mkdir(parents=True, exist_ok=True)
    # Derive the padded clip extent from the current authoritative Atlas table.
    bounds = fetch_bounds()
    current_downloads = [cache_clip(cache, args.analysis_year, month, bounds,
                                    refresh_source=args.refresh_current_source) for month in months]
    current = [item[0] for item in current_downloads]
    # Retain a run-specific native-grid evidence raster for the historical
    # timeline as well as the stable current-map derivative.  This preserves
    # the exact source period selected by a user without changing the current
    # display when older history is backfilled.
    run_id = f"chirps-v3-{args.analysis_year}-{'-'.join(map(str, months))}-baseline-{args.baseline_start}-{args.baseline_end}"
    historical_raster = root / "published" / f"{run_id}.tif"
    publish_rainfall_total(current, historical_raster)
    if not args.defer_current_publish:
        publish_rainfall_total(current, root / "published" / "chirps-current-rainfall.tif")
    baseline = {year: [cache_clip(cache, year, month, bounds)[0] for month in months]
                for year in range(args.baseline_start, args.baseline_end + 1)}
    rows = []
    for tabia_id, name, woreda, geometry in fetch_tabias():
        observed, usable, total_cells = zonal_seasonal_mean(current, geometry)
        baseline_values = [zonal_seasonal_mean(paths, geometry)[0] for paths in baseline.values()]
        coverage = round(100 * usable / total_cells, 1) if total_cells else 0.0
        quality = "ok" if usable and coverage >= 90 else "insufficient_grid_coverage"
        record = {"tsird_tabia_id": tabia_id, "tabia_name_en": name, "woreda_name_en": woreda,
                  "rainfall_mm": round(observed, 2) if usable else None,
                  "baseline_median_mm": round(sorted(baseline_values)[len(baseline_values)//2], 2) if usable else None,
                  "percentile": percentile(observed, baseline_values) if usable else None,
                  "condition_class": condition(percentile(observed, baseline_values)) if usable else "unavailable",
                  "grid_cell_count": usable, "coverage_pct": coverage, "quality_status": quality}
        rows.append(record)
    with (output / f"{run_id}.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=rows[0].keys()); writer.writeheader(); writer.writerows(rows)
    manifest = {"run_id": run_id, "status": "development", "source_product": SOURCE_PRODUCT,
                "source_version": SOURCE_VERSION, "source_url_template": f"{BASE_URL}/chirps-v3.0.{{year}}.{{month}}.tif",
                "analysis_year": args.analysis_year, "months": months,
                "native_resolution": "0.05 degree CHIRPS grid, monthly rainfall total",
                "source_latest_month": f"{args.analysis_year}-{max(months):02d}-01",
                "baseline_years": [args.baseline_start, args.baseline_end],
                "boundary_set_version": "tsird-tabias-v1", "included_tabias": len(rows),
                "identity_note": "All canonical tsird_tabia_id records are included. Source T8ID duplicates remain review flags and are never used as join keys.",
                "method": "pixel-centre zonal means summed across months; coverage and cell count retained",
                "source_acquisition": {
                "current_period_refreshed": args.refresh_current_source,
                "current_publish_deferred": args.defer_current_publish,
                    "current_period_files": [item[1] for item in current_downloads],
                    "baseline_file_policy": "reused clipped cache where available",
                },
                "raster_path": str(historical_raster),
                "raster_sha256": hashlib.sha256(historical_raster.read_bytes()).hexdigest(),
                "observation_start": f"{args.analysis_year}-{min(months):02d}-01T00:00:00+00:00",
                "observation_end": f"{args.analysis_year}-{max(months):02d}-{monthrange(args.analysis_year, max(months))[1]:02d}T23:59:59+00:00",
                "publication_note": "Development artifact only; not a public drought product."}
    (output / f"{run_id}.manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"run_id": run_id, "rows": len(rows), "output": str(output)}, indent=2))


if __name__ == "__main__":
    main()
