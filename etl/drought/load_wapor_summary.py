"""Validate and load a local FAO WaPOR development artifact."""
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
    base = Path(sys.argv[1])
    manifest = json.loads(base.with_suffix(".manifest.json").read_text(encoding="utf-8"))
    rows = list(csv.DictReader(base.with_suffix(".csv").open(encoding="utf-8")))
    required = {"run_id", "source_product", "mapset_code", "aeti_mapset_code", "source_period_start", "source_period_end", "native_resolution", "raster_paths", "raster_sha256", "source_urls", "source_retrieved_at", "status", "publication_note"}
    if not rows or not required.issubset(manifest) or manifest["status"] not in {"development", "degraded"}:
        raise ValueError("WaPOR artifact is incomplete")
    values = []
    for row in rows:
        if not row["tsird_tabia_id"].startswith("tsird-tabia-v1-"):
            raise ValueError("WaPOR artifact has a non-canonical Tabia ID")
        coverage = float(row["coverage_pct"]); valid = int(row["valid_pixel_count"]); cells = int(row["grid_cell_count"])
        if not 0 <= coverage <= 100 or valid < 0 or cells < valid:
            raise ValueError("WaPOR artifact has invalid coverage metadata")
        values.append((manifest["run_id"], row["tsird_tabia_id"], row["transpiration_mm"] or None, row["aeti_mm"] or None, valid, cells, coverage, row["quality_status"]))
    with psycopg2.connect(dsn()) as conn, conn.cursor() as cur:
        cur.execute('''INSERT INTO tsird.drought_wapor_run
          (run_id,source_id,mapset_code,aeti_mapset_code,source_period_start,source_period_end,source_revision,native_resolution,
           transpiration_raster_path,aeti_raster_path,transpiration_sha256,aeti_sha256,source_urls,source_retrieved_at,status,notes,
           seasonal_reference_candidate_only)
          VALUES (%s,'fao-wapor-v3',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s)
          ON CONFLICT (run_id) DO UPDATE SET transpiration_raster_path=EXCLUDED.transpiration_raster_path,
          aeti_raster_path=EXCLUDED.aeti_raster_path, transpiration_sha256=EXCLUDED.transpiration_sha256,
          aeti_sha256=EXCLUDED.aeti_sha256, native_resolution=EXCLUDED.native_resolution,
          source_retrieved_at=EXCLUDED.source_retrieved_at, status=EXCLUDED.status, notes=EXCLUDED.notes,
          seasonal_reference_candidate_only=EXCLUDED.seasonal_reference_candidate_only''',
          (manifest["run_id"], manifest["mapset_code"], manifest["aeti_mapset_code"], manifest["source_period_start"], manifest["source_period_end"], manifest["source_revision"], manifest["native_resolution"], manifest["raster_paths"]["transpiration"], manifest["raster_paths"]["aeti"], manifest["raster_sha256"]["transpiration"], manifest["raster_sha256"]["aeti"], json.dumps(manifest["source_urls"]), manifest["source_retrieved_at"], manifest["status"], manifest["publication_note"], bool(manifest.get("seasonal_reference_candidate_only"))))
        execute_values(cur, '''INSERT INTO tsird.drought_tabia_wapor
          (run_id,tsird_tabia_id,transpiration_mm,aeti_mm,valid_pixel_count,grid_cell_count,coverage_pct,quality_status)
          VALUES %s ON CONFLICT (run_id,tsird_tabia_id) DO UPDATE SET transpiration_mm=EXCLUDED.transpiration_mm,
          aeti_mm=EXCLUDED.aeti_mm,valid_pixel_count=EXCLUDED.valid_pixel_count,grid_cell_count=EXCLUDED.grid_cell_count,
          coverage_pct=EXCLUDED.coverage_pct,quality_status=EXCLUDED.quality_status''', values)
    print(json.dumps({"valid": True, "run_id": manifest["run_id"], "artifact_status": manifest["status"], "rows": len(values)}))


if __name__ == "__main__":
    main()
