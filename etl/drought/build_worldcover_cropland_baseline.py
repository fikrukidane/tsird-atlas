"""Download only needed ESA WorldCover COGs and summarize 2021 cropland class 40 to Tabias."""
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import psycopg2
import rasterio
from rasterio.features import geometry_mask
from rasterio.mask import mask
import requests


SOURCE_ID = "esa-worldcover-2021-v200"
SOURCE_RELEASE = "WorldCover 2021 v200"
CROPLAND_CLASS = 40
SOURCE_ROOT = "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map"
TILES = ("N12E036", "N12E039")
SOURCE_PATH = Path("/data/drought/worldcover/2021-v200")
MIN_COVERAGE_PCT = 99.0


def dsn():
    return " ".join(("host=tsird-postgis", "port=5432", f"dbname={os.environ['POSTGRES_DB']}",
                     f"user={os.environ['POSTGRES_USER']}", f"password={os.environ['POSTGRES_PASSWORD']}"))


def source_url(tile):
    return f"{SOURCE_ROOT}/ESA_WorldCover_10m_2021_v200_{tile}_Map.tif"


def local_path(tile):
    return SOURCE_PATH / f"ESA_WorldCover_10m_2021_v200_{tile}_Map.tif"


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def download_once(tile):
    path = local_path(tile)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size > 1_000_000:
        return False
    partial = path.with_suffix(".tif.part")
    partial.unlink(missing_ok=True)
    with requests.get(source_url(tile), stream=True, timeout=(30, 900)) as response:
        response.raise_for_status()
        with partial.open("wb") as output:
            for block in response.iter_content(chunk_size=1024 * 1024):
                if block:
                    output.write(block)
    partial.replace(path)
    return True


def pixel_hectares(raster, row):
    """Approximate geographic-grid pixel area at a representative latitude."""
    latitude = raster.xy(row, raster.width // 2)[1]
    width_deg, height_deg = abs(raster.transform.a), abs(raster.transform.e)
    return (111_320 * width_deg * 110_574 * height_deg * max(0.01, abs(__import__('math').cos(__import__('math').radians(latitude)))) / 10_000)


def summarize_tabia(rasters, geometry):
    valid_pixels = total_pixels = cropland_pixels = 0
    cropland_hectares = 0.0
    for raster in rasters:
        try:
            data, transform = mask(raster, [geometry], crop=True, filled=False, all_touched=True)
        except ValueError:
            continue
        values = data[0]
        inside = geometry_mask([geometry], out_shape=values.shape, transform=transform, invert=True, all_touched=True)
        total_pixels += int(inside.sum())
        usable = inside & ~values.mask & (values.data != 0)
        valid_pixels += int(usable.sum())
        crops = usable & (values.data == CROPLAND_CLASS)
        cropland_pixels += int(crops.sum())
        for row in __import__('numpy').unique(__import__('numpy').where(crops)[0]):
            cropland_hectares += float(crops[row].sum()) * pixel_hectares(raster, int(row))
    coverage = 100.0 * valid_pixels / total_pixels if total_pixels else 0.0
    cropland_pct = 100.0 * cropland_pixels / valid_pixels if valid_pixels else 0.0
    quality = "ok" if coverage >= MIN_COVERAGE_PCT else ("insufficient_coverage" if valid_pixels else "unavailable")
    return cropland_pct, cropland_hectares, valid_pixels, total_pixels, coverage, quality


def main():
    downloaded = {tile: download_once(tile) for tile in TILES}
    paths = [local_path(tile) for tile in TILES]
    hashes = {tile: sha256(path) for tile, path in zip(TILES, paths)}
    run_id = f"esa-worldcover-2021-v200-cropland-{datetime.now(timezone.utc):%Y%m%d}"
    with rasterio.open(paths[0]) as first:
        if first.crs is None or first.crs.to_epsg() != 4326:
            raise ValueError("expected ESA WorldCover source in EPSG:4326")
    with psycopg2.connect(dsn()) as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*), coalesce(max(tsird_boundary_version), 'unknown') FROM public.tigray_tabias_ws")
        tabia_count, boundary_version = cur.fetchone()
        cur.execute("SELECT tsird_tabia_id, ST_AsGeoJSON(ST_MakeValid(geometry)) FROM public.tigray_tabias_ws ORDER BY tsird_tabia_id")
        tabias = cur.fetchall()
        with rasterio.open(paths[0]) as first, rasterio.open(paths[1]) as second:
            summaries = [(run_id, tabia_id, *summarize_tabia((first, second), json.loads(geometry_json))) for tabia_id, geometry_json in tabias]
        cur.execute("""
          INSERT INTO tsird.drought_cropland_run
            (run_id, source_id, source_year, source_release, source_urls, source_sha256, native_resolution,
             cropland_class, boundary_set_version, status, source_feature_note)
          VALUES (%s, %s, 2021, %s, %s::jsonb, %s::jsonb, '10 m', %s, %s, 'development', %s)
          ON CONFLICT (run_id) DO UPDATE SET source_sha256=EXCLUDED.source_sha256, status='development', created_at=now()
        """, (run_id, SOURCE_ID, SOURCE_RELEASE, json.dumps({tile: source_url(tile) for tile in TILES}), json.dumps(hashes),
              CROPLAND_CLASS, boundary_version, "ESA WorldCover class 40 share; 2021 reference land cover, not current cultivated area or food-security evidence."))
        cur.executemany("""
          INSERT INTO tsird.drought_tabia_cropland
            (run_id, tsird_tabia_id, cropland_pct, cropland_area_ha, valid_pixel_count, total_pixel_count, coverage_pct, quality_status)
          VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
          ON CONFLICT (run_id, tsird_tabia_id) DO UPDATE SET cropland_pct=EXCLUDED.cropland_pct, cropland_area_ha=EXCLUDED.cropland_area_ha,
            valid_pixel_count=EXCLUDED.valid_pixel_count, total_pixel_count=EXCLUDED.total_pixel_count, coverage_pct=EXCLUDED.coverage_pct, quality_status=EXCLUDED.quality_status
        """, summaries)
        cur.execute("""
          SELECT count(*), count(*) FILTER (WHERE quality_status='ok'), sum(cropland_area_ha),
            percentile_cont(ARRAY[0.2,0.4,0.6,0.8]) WITHIN GROUP (ORDER BY cropland_pct)
          FROM tsird.drought_tabia_cropland WHERE run_id=%s
        """, (run_id,))
        rows, usable, hectares, breaks = cur.fetchone()
        if rows != tabia_count or usable != tabia_count:
            raise ValueError(f"expected {tabia_count} usable Tabias, got {rows} rows / {usable} usable")
    print(json.dumps({"valid": True, "run_id": run_id, "downloaded": downloaded, "tabias": rows,
                      "cropland_area_ha": hectares, "cropland_pct_breaks": breaks, "source_sha256": hashes}, default=str))


if __name__ == "__main__":
    main()
