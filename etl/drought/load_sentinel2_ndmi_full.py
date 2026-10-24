"""Validate and load exactly one all-Tabia DEV Sentinel-2 NDMI artifact."""
import csv
import json
import os
import sys
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values

SOURCE_ID = "cdse-sentinel2-l2a-ndmi-full-development"
TABIA_COUNT = 748


def dsn():
    return " ".join(("host=tsird-postgis", "port=5432", f"dbname={os.environ['POSTGRES_DB']}",
                     f"user={os.environ['POSTGRES_USER']}", f"password={os.environ['POSTGRES_PASSWORD']}"))


def main():
    base = Path(sys.argv[1])
    manifest = json.loads(base.with_suffix(".manifest.json").read_text(encoding="utf-8"))
    with base.with_suffix(".csv").open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    required = {"run_id", "source_id", "run_scope", "observation_start", "observation_end", "native_resolution",
                "mosaicking_order", "valid_scl_classes", "min_valid_coverage_pct", "tabia_count", "source_retrieved_at", "processing_version"}
    if (not required.issubset(manifest) or manifest.get("source_id") != SOURCE_ID or
            manifest.get("run_scope") != "full_development" or manifest.get("status") not in {"development", "degraded"}):
        raise ValueError("Sentinel-2 NDMI full-development manifest is incomplete")
    if len(rows) != TABIA_COUNT or int(manifest["tabia_count"]) != TABIA_COUNT:
        raise ValueError("Sentinel-2 NDMI full development run must contain exactly 748 Tabias")
    ids = set(); values = []
    for row in rows:
        tabia_id = row["tsird_tabia_id"]
        if not tabia_id.startswith("tsird-tabia-v1-") or tabia_id in ids: raise ValueError("non-canonical or duplicate Tabia ID")
        ids.add(tabia_id)
        valid, total, coverage = int(row["valid_pixel_count"]), int(row["grid_cell_count"]), float(row["coverage_pct"])
        if valid < 0 or total < valid or not 0 <= coverage <= 100 or row["quality_status"] not in {"ok", "insufficient_evidence"}:
            raise ValueError("invalid Sentinel-2 NDMI quality metadata")
        if row["quality_status"] == "ok" and (not row["ndmi_mean"] or coverage < float(manifest["min_valid_coverage_pct"])):
            raise ValueError("valid Sentinel-2 NDMI row does not satisfy coverage rule")
        values.append((manifest["run_id"], tabia_id, row["ndmi_mean"] or None, row["ndmi_median"] or None, valid, total, coverage, row["quality_status"]))
    with psycopg2.connect(dsn()) as conn, conn.cursor() as cur:
        cur.execute('''INSERT INTO tsird.drought_sentinel2_ndmi_run
          (run_id, source_id, observation_start, observation_end, native_resolution, mosaicking_order,
           valid_scl_classes, min_valid_coverage_pct, tabia_count, source_retrieved_at, processing_version, status, notes, run_scope)
          VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
          ON CONFLICT (run_id) DO UPDATE SET source_retrieved_at=EXCLUDED.source_retrieved_at, status=EXCLUDED.status, notes=EXCLUDED.notes''',
          (manifest["run_id"], SOURCE_ID, manifest["observation_start"], manifest["observation_end"], manifest["native_resolution"],
           manifest["mosaicking_order"], manifest["valid_scl_classes"], manifest["min_valid_coverage_pct"], manifest["tabia_count"],
           manifest["source_retrieved_at"], manifest["processing_version"], manifest["status"], manifest["publication_note"], manifest["run_scope"]))
        execute_values(cur, '''INSERT INTO tsird.drought_tabia_sentinel2_ndmi
          (run_id, tsird_tabia_id, ndmi_mean, ndmi_median, valid_pixel_count, grid_cell_count, coverage_pct, quality_status)
          VALUES %s ON CONFLICT (run_id, tsird_tabia_id) DO UPDATE SET ndmi_mean=EXCLUDED.ndmi_mean,
          ndmi_median=EXCLUDED.ndmi_median, valid_pixel_count=EXCLUDED.valid_pixel_count, grid_cell_count=EXCLUDED.grid_cell_count,
          coverage_pct=EXCLUDED.coverage_pct, quality_status=EXCLUDED.quality_status''', values)
    print(json.dumps({"valid": True, "run_id": manifest["run_id"], "artifact_status": manifest["status"], "rows": len(values)}))


if __name__ == "__main__":
    main()
