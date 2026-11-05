"""Validate and load exactly one full DEV Sentinel-1 radar evidence artifact."""
import csv
import json
import os
import sys
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values

SOURCE_ID = "cdse-sentinel1-grd-monthly-development"
TABIA_COUNT = 748


def dsn():
    return " ".join(("host=tsird-postgis", "port=5432", f"dbname={os.environ['POSTGRES_DB']}", f"user={os.environ['POSTGRES_USER']}", f"password={os.environ['POSTGRES_PASSWORD']}"))


def main():
    base = Path(sys.argv[1]); manifest = json.loads(base.with_suffix(".manifest.json").read_text(encoding="utf-8"))
    with base.with_suffix(".csv").open(encoding="utf-8") as handle: rows = list(csv.DictReader(handle))
    required = {"run_id", "source_id", "status", "observation_start", "observation_end", "native_resolution", "orbit_direction", "polarizations", "terrain_correction", "source_scene_count", "source_fingerprint", "min_valid_coverage_pct", "min_usable_scene_count", "tabia_count", "source_retrieved_at", "processing_version", "publication_note"}
    if not required.issubset(manifest) or manifest["source_id"] != SOURCE_ID or manifest["status"] not in {"development", "degraded"}: raise ValueError("Sentinel-1 manifest is incomplete")
    if len(rows) != TABIA_COUNT or int(manifest["tabia_count"]) != TABIA_COUNT: raise ValueError("Sentinel-1 artifact must contain exactly 748 Tabias")
    values=[]; ids=set()
    for row in rows:
        tabia_id=row["tsird_tabia_id"]
        if not tabia_id.startswith("tsird-tabia-v1-") or tabia_id in ids: raise ValueError("non-canonical or duplicate Tabia ID")
        ids.add(tabia_id); valid=int(row["valid_pixel_count"]); total=int(row["grid_cell_count"]); coverage=float(row["coverage_pct"]); quality=row["quality_status"]
        if valid < 0 or total < valid or not 0 <= coverage <= 100 or quality not in {"ok", "limited_coverage", "insufficient_evidence"}: raise ValueError("invalid Sentinel-1 quality metadata")
        if quality == "ok" and (not row["vv_db_median"] or not row["vh_db_median"] or coverage < float(manifest["min_valid_coverage_pct"])): raise ValueError("adequate Sentinel-1 row fails quality gate")
        values.append((manifest["run_id"], tabia_id, row["vv_db_median"] or None, row["vh_db_median"] or None, valid, total, coverage, int(row["contributing_scene_count"]), quality))
    with psycopg2.connect(dsn()) as conn, conn.cursor() as cur:
        cur.execute('''INSERT INTO tsird.drought_sentinel1_radar_run (run_id, source_id, observation_start, observation_end, native_resolution, orbit_direction, polarizations, terrain_correction, source_scene_count, source_fingerprint, min_valid_coverage_pct, min_usable_scene_count, tabia_count, source_retrieved_at, processing_version, status, notes) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (run_id) DO UPDATE SET source_retrieved_at=EXCLUDED.source_retrieved_at, status=EXCLUDED.status, notes=EXCLUDED.notes''', (manifest["run_id"], SOURCE_ID, manifest["observation_start"], manifest["observation_end"], manifest["native_resolution"], manifest["orbit_direction"], manifest["polarizations"], manifest["terrain_correction"], manifest["source_scene_count"], manifest["source_fingerprint"], manifest["min_valid_coverage_pct"], manifest["min_usable_scene_count"], manifest["tabia_count"], manifest["source_retrieved_at"], manifest["processing_version"], manifest["status"], manifest["publication_note"]))
        execute_values(cur, '''INSERT INTO tsird.drought_tabia_sentinel1_radar (run_id, tsird_tabia_id, vv_db_median, vh_db_median, valid_pixel_count, grid_cell_count, coverage_pct, contributing_scene_count, quality_status) VALUES %s ON CONFLICT (run_id, tsird_tabia_id) DO UPDATE SET vv_db_median=EXCLUDED.vv_db_median, vh_db_median=EXCLUDED.vh_db_median, valid_pixel_count=EXCLUDED.valid_pixel_count, grid_cell_count=EXCLUDED.grid_cell_count, coverage_pct=EXCLUDED.coverage_pct, contributing_scene_count=EXCLUDED.contributing_scene_count, quality_status=EXCLUDED.quality_status''', values)
    print(json.dumps({"valid": True, "run_id": manifest["run_id"], "artifact_status": manifest["status"], "rows": len(values)}))


if __name__ == "__main__": main()
