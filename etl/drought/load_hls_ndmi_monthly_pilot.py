"""Validate and load only a complete, bounded HLS monthly DEV pilot artifact."""
import csv
import json
import os
import sys
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values

SOURCE_ID = "nasa-hls-v2-ndmi-monthly-pilot"
MAX_PILOT_TABIAS = 20
QUALITY = {"ok", "insufficient_valid_pixel_count", "insufficient_observation_coverage", "insufficient_acquisition_count"}
PROFILES = {"strict", "adjacency_allowed"}
TIERS = {"adequate", "limited", "insufficient"}


def dsn():
    return " ".join(("host=tsird-postgis", "port=5432", f"dbname={os.environ['POSTGRES_DB']}",
                     f"user={os.environ['POSTGRES_USER']}", f"password={os.environ['POSTGRES_PASSWORD']}"))


def main():
    base = Path(sys.argv[1])
    manifest = json.loads(base.with_suffix(".manifest.json").read_text(encoding="utf-8"))
    with base.with_suffix(".csv").open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    required = {"run_id", "source_id", "observation_start", "observation_end", "native_resolution", "source_collections",
                "validity_mask", "coverage_definition", "min_valid_observation_coverage_pct", "min_valid_observation_pixels",
                "min_usable_acquisition_count", "pilot_tabia_limit", "source_retrieved_at", "processing_version", "publication_note"}
    if not required.issubset(manifest) or manifest.get("source_id") != SOURCE_ID or manifest.get("status") not in {"development", "degraded"}:
        raise ValueError("HLS monthly pilot manifest is incomplete or not development-only")
    if len(rows) != MAX_PILOT_TABIAS or int(manifest["pilot_tabia_limit"]) != MAX_PILOT_TABIAS:
        raise ValueError("HLS monthly pilot must contain exactly twenty Tabias")
    values, profile_values = [], []
    for row in rows:
        if not row["tsird_tabia_id"].startswith("tsird-tabia-v1-"):
            raise ValueError("non-canonical Tabia ID")
        valid, candidate = int(row["valid_observation_pixel_count"]), int(row["candidate_observation_pixel_count"])
        coverage, usable, observed = float(row["coverage_pct"]), int(row["usable_acquisition_count"]), int(row["candidate_acquisition_count"])
        if valid < 0 or candidate < valid or not 0 <= coverage <= 100 or usable > observed or row["quality_status"] not in QUALITY:
            raise ValueError("invalid HLS monthly pilot quality metadata")
        if row["quality_status"] == "ok" and (valid < int(manifest["min_valid_observation_pixels"]) or
            coverage < float(manifest["min_valid_observation_coverage_pct"]) or usable < int(manifest["min_usable_acquisition_count"])):
            raise ValueError("valid HLS row does not satisfy its evidence thresholds")
        values.append((manifest["run_id"], row["tsird_tabia_id"], row["ndmi_mean"] or None, row["ndmi_median"] or None,
                       valid, candidate, coverage, observed, usable, row["first_acquisition_at"] or None,
                       row["last_acquisition_at"] or None, row["median_acquisition_at"] or None, row["quality_status"]))
        for profile in PROFILES:
            prefix = f"{profile}_"
            required_profile = {f"{prefix}{field}" for field in (
                "ndmi_mean", "ndmi_median", "spatial_coverage_pct", "two_observation_coverage_pct",
                "median_valid_observation_count", "valid_spatial_pixel_count", "total_eligible_pixel_count",
                "valid_observation_pixel_count", "candidate_acquisition_count", "usable_acquisition_count",
                "adjacency_accepted_pixel_count", "first_acquisition_at", "last_acquisition_at",
                "median_acquisition_at", "evidence_tier")}
            if not required_profile.issubset(row):
                raise ValueError("HLS spatial-profile fields are missing")
            spatial, twice = float(row[f"{prefix}spatial_coverage_pct"]), float(row[f"{prefix}two_observation_coverage_pct"])
            spatial_pixels, total_pixels = int(row[f"{prefix}valid_spatial_pixel_count"]), int(row[f"{prefix}total_eligible_pixel_count"])
            profile_valid = int(row[f"{prefix}valid_observation_pixel_count"])
            profile_candidate, profile_usable = int(row[f"{prefix}candidate_acquisition_count"]), int(row[f"{prefix}usable_acquisition_count"])
            adjacency = int(row[f"{prefix}adjacency_accepted_pixel_count"])
            tier = row[f"{prefix}evidence_tier"]
            if (not 0 <= spatial <= 100 or not 0 <= twice <= 100 or spatial_pixels > total_pixels or
                profile_usable > profile_candidate or adjacency < 0 or tier not in TIERS):
                raise ValueError("invalid HLS spatial-profile metadata")
            profile_values.append((manifest["run_id"], row["tsird_tabia_id"], profile, row[f"{prefix}ndmi_mean"] or None,
                                   row[f"{prefix}ndmi_median"] or None, spatial, twice,
                                   row[f"{prefix}median_valid_observation_count"] or None, spatial_pixels, total_pixels,
                                   profile_valid, profile_candidate, profile_usable, adjacency,
                                   row[f"{prefix}first_acquisition_at"] or None, row[f"{prefix}last_acquisition_at"] or None,
                                   row[f"{prefix}median_acquisition_at"] or None, tier))
    with psycopg2.connect(dsn()) as conn, conn.cursor() as cur:
        cur.execute('''INSERT INTO tsird.drought_hls_ndmi_run
          (run_id, source_id, observation_start, observation_end, native_resolution, source_collections, validity_mask,
           coverage_definition, min_valid_observation_coverage_pct, min_valid_observation_pixels, min_usable_acquisition_count,
           tabia_count, source_retrieved_at, processing_version, status, notes, run_scope)
          VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
          ON CONFLICT (run_id) DO UPDATE SET source_retrieved_at=EXCLUDED.source_retrieved_at, status=EXCLUDED.status, notes=EXCLUDED.notes''',
          (manifest["run_id"], SOURCE_ID, manifest["observation_start"], manifest["observation_end"], manifest["native_resolution"],
           manifest["source_collections"], manifest["validity_mask"], manifest["coverage_definition"],
           manifest["min_valid_observation_coverage_pct"], manifest["min_valid_observation_pixels"],
           manifest["min_usable_acquisition_count"], manifest["pilot_tabia_limit"], manifest["source_retrieved_at"],
           manifest["processing_version"], manifest["status"], manifest["publication_note"], "technical_pilot"))
        execute_values(cur, '''INSERT INTO tsird.drought_tabia_hls_ndmi
          (run_id, tsird_tabia_id, ndmi_mean, ndmi_median, valid_observation_pixel_count, candidate_observation_pixel_count,
           coverage_pct, candidate_acquisition_count, usable_acquisition_count, first_acquisition_at, last_acquisition_at,
           median_acquisition_at, quality_status)
          VALUES %s ON CONFLICT (run_id, tsird_tabia_id) DO UPDATE SET ndmi_mean=EXCLUDED.ndmi_mean,
           ndmi_median=EXCLUDED.ndmi_median, valid_observation_pixel_count=EXCLUDED.valid_observation_pixel_count,
           candidate_observation_pixel_count=EXCLUDED.candidate_observation_pixel_count, coverage_pct=EXCLUDED.coverage_pct,
           candidate_acquisition_count=EXCLUDED.candidate_acquisition_count, usable_acquisition_count=EXCLUDED.usable_acquisition_count,
           first_acquisition_at=EXCLUDED.first_acquisition_at, last_acquisition_at=EXCLUDED.last_acquisition_at,
           median_acquisition_at=EXCLUDED.median_acquisition_at, quality_status=EXCLUDED.quality_status''', values)
        execute_values(cur, '''INSERT INTO tsird.drought_tabia_hls_ndmi_profile
          (run_id, tsird_tabia_id, mask_profile, ndmi_mean, ndmi_median, spatial_coverage_pct,
           two_observation_coverage_pct, median_valid_observation_count, valid_spatial_pixel_count,
           total_eligible_pixel_count, valid_observation_pixel_count, candidate_acquisition_count,
           usable_acquisition_count, adjacency_accepted_pixel_count, first_acquisition_at,
           last_acquisition_at, median_acquisition_at, evidence_tier)
          VALUES %s ON CONFLICT (run_id, tsird_tabia_id, mask_profile) DO UPDATE SET
           ndmi_mean=EXCLUDED.ndmi_mean, ndmi_median=EXCLUDED.ndmi_median,
           spatial_coverage_pct=EXCLUDED.spatial_coverage_pct,
           two_observation_coverage_pct=EXCLUDED.two_observation_coverage_pct,
           median_valid_observation_count=EXCLUDED.median_valid_observation_count,
           valid_spatial_pixel_count=EXCLUDED.valid_spatial_pixel_count,
           total_eligible_pixel_count=EXCLUDED.total_eligible_pixel_count,
           valid_observation_pixel_count=EXCLUDED.valid_observation_pixel_count,
           candidate_acquisition_count=EXCLUDED.candidate_acquisition_count,
           usable_acquisition_count=EXCLUDED.usable_acquisition_count,
           adjacency_accepted_pixel_count=EXCLUDED.adjacency_accepted_pixel_count,
           first_acquisition_at=EXCLUDED.first_acquisition_at, last_acquisition_at=EXCLUDED.last_acquisition_at,
           median_acquisition_at=EXCLUDED.median_acquisition_at, evidence_tier=EXCLUDED.evidence_tier''', profile_values)
    print(json.dumps({"valid": True, "run_id": manifest["run_id"], "artifact_status": manifest["status"], "rows": len(values)}, indent=2))


if __name__ == "__main__":
    main()
