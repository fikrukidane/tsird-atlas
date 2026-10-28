"""Validate and load a bounded, development-only Sentinel-2 NDMI pilot."""
import csv
import json
import os
import sys
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values

SOURCE_ID = "cdse-sentinel2-l2a-ndmi-pilot"
MAX_PILOT_TABIAS = 20


def dsn():
    return " ".join(("host=tsird-postgis", "port=5432", f"dbname={os.environ['POSTGRES_DB']}",
                     f"user={os.environ['POSTGRES_USER']}", f"password={os.environ['POSTGRES_PASSWORD']}"))


def main():
    base = Path(sys.argv[1])
    manifest = json.loads(base.with_suffix(".manifest.json").read_text(encoding="utf-8"))
    with base.with_suffix(".csv").open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    required = {"run_id", "source_id", "observation_start", "observation_end", "native_resolution", "mosaicking_order",
                "valid_scl_classes", "min_valid_coverage_pct", "pilot_tabia_limit", "source_retrieved_at", "processing_version"}
    if not required.issubset(manifest) or manifest.get("source_id") != SOURCE_ID or manifest.get("status") not in {"development", "degraded"}:
        raise ValueError("Sentinel-2 NDMI pilot manifest is incomplete or not development-only")
    if not rows or len(rows) > MAX_PILOT_TABIAS or int(manifest["pilot_tabia_limit"]) > MAX_PILOT_TABIAS:
        raise ValueError("Sentinel-2 NDMI pilot exceeds its approved Tabia limit")
    values = []
    for row in rows:
        if not row["tsird_tabia_id"].startswith("tsird-tabia-v1-"):
            raise ValueError("non-canonical Tabia ID")
        valid, total, coverage = int(row["valid_pixel_count"]), int(row["grid_cell_count"]), float(row["coverage_pct"])
        if valid < 0 or total < valid or not 0 <= coverage <= 100 or row["quality_status"] not in {"ok", "insufficient_evidence"}:
            raise ValueError("invalid Sentinel-2 NDMI quality metadata")
        if row["quality_status"] == "ok" and (not row["ndmi_mean"] or coverage < float(manifest["min_valid_coverage_pct"])):
            raise ValueError("valid Sentinel-2 NDMI row does not satisfy coverage rule")
        values.append((manifest["run_id"], row["tsird_tabia_id"], row["ndmi_mean"] or None, row["ndmi_median"] or None,
                       valid, total, coverage, row["quality_status"]))
    with psycopg2.connect(dsn()) as conn, conn.cursor() as cur:
        cur.execute('''INSERT INTO tsird.drought_sentinel2_ndmi_run
          (run_id, source_id, observation_start, observation_end, native_resolution, mosaicking_order,
           valid_scl_classes, min_valid_coverage_pct, tabia_count, source_retrieved_at,
           processing_version, status, notes, run_scope)
          VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
          ON CONFLICT (run_id) DO UPDATE SET source_retrieved_at=EXCLUDED.source_retrieved_at,
            status=EXCLUDED.status, notes=EXCLUDED.notes''',
          (manifest["run_id"], SOURCE_ID, manifest["observation_start"], manifest["observation_end"],
           manifest["native_resolution"], manifest["mosaicking_order"], manifest["valid_scl_classes"],
           manifest["min_valid_coverage_pct"], manifest["pilot_tabia_limit"], manifest["source_retrieved_at"],
           manifest["processing_version"], manifest["status"], manifest["publication_note"], "technical_pilot"))
        execute_values(cur, '''INSERT INTO tsird.drought_tabia_sentinel2_ndmi
          (run_id, tsird_tabia_id, ndmi_mean, ndmi_median, valid_pixel_count, grid_cell_count, coverage_pct, quality_status)
          VALUES %s ON CONFLICT (run_id, tsird_tabia_id) DO UPDATE SET ndmi_mean=EXCLUDED.ndmi_mean,
          ndmi_median=EXCLUDED.ndmi_median, valid_pixel_count=EXCLUDED.valid_pixel_count,
          grid_cell_count=EXCLUDED.grid_cell_count, coverage_pct=EXCLUDED.coverage_pct, quality_status=EXCLUDED.quality_status''', values)
    print(json.dumps({"valid": True, "run_id": manifest["run_id"], "artifact_status": manifest["status"], "rows": len(values)}, indent=2))


if __name__ == "__main__":
    main()
