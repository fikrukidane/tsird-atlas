"""Validate and load a development-only CDSE NDVI Tabia summary."""
import csv
import json
import os
import sys
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values


def dsn():
    return " ".join(("host=tsird-postgis", "port=5432", f"dbname={os.environ['POSTGRES_DB']}",
                     f"user={os.environ['POSTGRES_USER']}", f"password={os.environ['POSTGRES_PASSWORD']}"))


def main():
    base = Path(sys.argv[1]); manifest = json.loads(base.with_suffix(".manifest.json").read_text(encoding="utf-8"))
    with base.with_suffix(".csv").open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    needed = {"run_id", "collection_id", "raster_path", "raster_sha256", "observation_timestamp", "source_retrieved_at"}
    if not needed.issubset(manifest) or not rows or manifest.get("status") not in {"development", "degraded"}:
        raise ValueError("NDVI artifact is incomplete or not a development artifact")
    values = []
    for row in rows:
        if not row["tsird_tabia_id"].startswith("tsird-tabia-v1-"):
            raise ValueError("non-canonical Tabia ID")
        coverage, valid, cells = float(row["coverage_pct"]), int(row["valid_pixel_count"]), int(row["grid_cell_count"])
        if not 0 <= coverage <= 100 or valid < 0 or cells < valid:
            raise ValueError("invalid NDVI coverage metadata")
        values.append((manifest["run_id"], row["tsird_tabia_id"], row["ndvi_mean"] or None, row["ndvi_median"] or None,
                       valid, cells, coverage, int(row["qflag_nonzero_count"]), row["quality_status"]))
    with psycopg2.connect(dsn()) as conn, conn.cursor() as cur:
        cur.execute('''INSERT INTO tsird.drought_ndvi_run
          (run_id, source_product, collection_id, observation_start, observation_end, native_resolution,
           requested_resolution_degrees, raster_path, raster_sha256, source_retrieved_at, status, notes,
           seasonal_reference_candidate_only)
          VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
          ON CONFLICT (run_id) DO UPDATE SET created_at=now(), raster_path=EXCLUDED.raster_path,
            raster_sha256=EXCLUDED.raster_sha256, source_retrieved_at=EXCLUDED.source_retrieved_at,
            status=EXCLUDED.status, notes=EXCLUDED.notes,
            seasonal_reference_candidate_only=EXCLUDED.seasonal_reference_candidate_only''',
          (manifest["run_id"], manifest["source_product"], manifest["collection_id"], manifest["observation_timestamp"],
           manifest["observation_timestamp"], manifest["native_resolution"], manifest["requested_resolution_degrees"],
           manifest["raster_path"], manifest["raster_sha256"], manifest["source_retrieved_at"], manifest["status"], manifest["publication_note"],
           bool(manifest.get("seasonal_reference_candidate_only"))))
        execute_values(cur, '''INSERT INTO tsird.drought_tabia_ndvi
          (run_id, tsird_tabia_id, ndvi_mean, ndvi_median, valid_pixel_count, grid_cell_count, coverage_pct,
           qflag_nonzero_count, quality_status) VALUES %s
          ON CONFLICT (run_id, tsird_tabia_id) DO UPDATE SET ndvi_mean=EXCLUDED.ndvi_mean,
           ndvi_median=EXCLUDED.ndvi_median, valid_pixel_count=EXCLUDED.valid_pixel_count,
           grid_cell_count=EXCLUDED.grid_cell_count, coverage_pct=EXCLUDED.coverage_pct,
           qflag_nonzero_count=EXCLUDED.qflag_nonzero_count, quality_status=EXCLUDED.quality_status''', values)
    print(json.dumps({"valid": True, "run_id": manifest["run_id"], "artifact_status": manifest["status"], "rows": len(values)}, indent=2))


if __name__ == "__main__":
    main()
