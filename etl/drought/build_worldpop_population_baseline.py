"""Download the cited WorldPop raster once and summarize it to canonical Tabias."""
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


SOURCE_ID = "worldpop-global-2025-r2025a-v1"
SOURCE_RELEASE = "R2025A v1 (alpha)"
SOURCE_URL = "https://data.worldpop.org/GIS/Population/Global_2015_2030/R2025A/2025/ETH/v1/100m/constrained/eth_pop_2025_CN_100m_R2025A_v1.tif"
POPULATION_YEAR = 2025
SOURCE_PATH = Path("/data/drought/worldpop/raw/eth_pop_2025_CN_100m_R2025A_v1.tif")
MIN_COVERAGE_PCT = 99.0


def dsn():
    return " ".join(("host=tsird-postgis", "port=5432", f"dbname={os.environ['POSTGRES_DB']}",
                     f"user={os.environ['POSTGRES_USER']}", f"password={os.environ['POSTGRES_PASSWORD']}"))


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def download_once():
    SOURCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if SOURCE_PATH.exists() and SOURCE_PATH.stat().st_size > 1_000_000:
        return False
    partial = SOURCE_PATH.with_suffix(".tif.part")
    partial.unlink(missing_ok=True)
    with requests.get(SOURCE_URL, stream=True, timeout=(30, 900)) as response:
        response.raise_for_status()
        with partial.open("wb") as output:
            for block in response.iter_content(chunk_size=1024 * 1024):
                if block:
                    output.write(block)
    partial.replace(SOURCE_PATH)
    return True


def main():
    downloaded = download_once()
    source_hash = sha256(SOURCE_PATH)
    run_id = f"worldpop-eth-2025-r2025a-v1-{datetime.now(timezone.utc):%Y%m%d}"
    with rasterio.open(SOURCE_PATH) as raster, psycopg2.connect(dsn()) as conn, conn.cursor() as cur:
        if raster.crs is None or raster.crs.to_epsg() != 4326:
            raise ValueError("expected WorldPop source in EPSG:4326")
        cur.execute("SELECT count(*), coalesce(max(tsird_boundary_version), 'unknown') FROM public.tigray_tabias_ws")
        tabia_count, boundary_version = cur.fetchone()
        cur.execute("""
          SELECT tsird_tabia_id, ST_AsGeoJSON(ST_MakeValid(geometry)), ST_Area(ST_MakeValid(geometry)::geography) / 1000000.0
          FROM public.tigray_tabias_ws ORDER BY tsird_tabia_id
        """)
        summaries = []
        for tabia_id, geometry_json, area_sq_km in cur.fetchall():
            geometry = json.loads(geometry_json)
            data, clipped_transform = mask(raster, [geometry], crop=True, filled=False, all_touched=True)
            values = data[0]
            inside = geometry_mask([geometry], out_shape=values.shape,
                                   transform=clipped_transform, invert=True, all_touched=True)
            total_pixels = int(inside.sum())
            # WorldPop constrained counts use nodata outside their modeled
            # settlement footprint. Within the Ethiopia raster extent these
            # cells mean zero estimated people, not absent Tabia coverage.
            # Preserve source-footprint semantics while retaining a complete
            # reporting denominator for every Tabia inside the source extent.
            estimated = values.data[inside & ~values.mask]
            valid_pixels = total_pixels
            coverage = 100.0 if total_pixels else 0.0
            total = float(estimated.sum()) if estimated.size else 0.0
            density = total / area_sq_km if area_sq_km else 0.0
            quality = "ok" if coverage >= MIN_COVERAGE_PCT else ("insufficient_coverage" if valid_pixels else "unavailable")
            summaries.append((run_id, tabia_id, total, density, valid_pixels, total_pixels, coverage, quality))
        if len(summaries) != tabia_count:
            raise ValueError(f"expected {tabia_count} Tabias, got {len(summaries)}")
        cur.execute("""
          INSERT INTO tsird.drought_population_run
            (run_id, source_id, population_year, source_release, source_url, source_sha256,
             native_resolution, boundary_set_version, status, source_feature_note)
          VALUES (%s, %s, %s, %s, %s, %s, '3 arc-seconds (~100 m)', %s, 'development', %s)
          ON CONFLICT (run_id) DO UPDATE SET source_sha256=EXCLUDED.source_sha256,
            status='development', created_at=now()
        """, (run_id, SOURCE_ID, POPULATION_YEAR, SOURCE_RELEASE, SOURCE_URL, source_hash,
              boundary_version, "WorldPop constrained population count estimate, people per pixel; alpha release, not an official census."))
        cur.executemany("""
          INSERT INTO tsird.drought_tabia_population
            (run_id, tsird_tabia_id, population_total, people_per_sq_km, valid_pixel_count,
             total_pixel_count, coverage_pct, quality_status)
          VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
          ON CONFLICT (run_id, tsird_tabia_id) DO UPDATE SET
            population_total=EXCLUDED.population_total, people_per_sq_km=EXCLUDED.people_per_sq_km,
            valid_pixel_count=EXCLUDED.valid_pixel_count, total_pixel_count=EXCLUDED.total_pixel_count,
            coverage_pct=EXCLUDED.coverage_pct, quality_status=EXCLUDED.quality_status
        """, summaries)
        cur.execute("""
          SELECT count(*), count(*) FILTER (WHERE quality_status='ok'),
            sum(population_total), percentile_cont(ARRAY[0.2,0.4,0.6,0.8]) WITHIN GROUP (ORDER BY population_total)
          FROM tsird.drought_tabia_population WHERE run_id=%s
        """, (run_id,))
        rows, usable, total_population, breaks = cur.fetchone()
    print(json.dumps({"valid": rows == tabia_count and usable == tabia_count, "run_id": run_id,
                      "downloaded": downloaded, "tabias": rows, "usable_tabias": usable,
                      "total_population": total_population, "population_breaks": breaks,
                      "source_sha256": source_hash}, default=str))


if __name__ == "__main__":
    main()
