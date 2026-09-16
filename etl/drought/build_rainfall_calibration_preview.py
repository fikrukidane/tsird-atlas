"""Build a draft-only historical rainfall/readiness calibration preview.

This intentionally does not calculate a composite priority, train a model,
publish a snapshot, or claim a historical forecast. It joins retained final
CHIRPS Tabia evidence with the approved static exposure/context baselines so
practitioners can inspect proposed rainfall-band thresholds before calibration.
"""
import json
import os
from datetime import timedelta

import psycopg2


CONFIGURATION_ID = "sarsrp-v0-1-foundation"
BOUNDARY_VERSION = "tsird-tabias-v1"
MIN_COVERAGE_PCT = 90.0


def dsn():
    return " ".join(("host=tsird-postgis", "port=5432", f"dbname={os.environ['POSTGRES_DB']}",
                     f"user={os.environ['POSTGRES_USER']}", f"password={os.environ['POSTGRES_PASSWORD']}"))


def main():
    with psycopg2.connect(dsn()) as conn, conn.cursor() as cur:
        cur.execute("""
          SELECT configuration_id
          FROM tsird.drought_priority_model_configuration
          WHERE configuration_id = %s AND status = 'draft'
        """, (CONFIGURATION_ID,))
        if not cur.fetchone():
            raise ValueError("The required draft calibration configuration is unavailable")

        cur.execute("""
          SELECT run_id, source_latest_month
          FROM tsird.drought_rainfall_run
          WHERE analysis_year = 2026 AND cardinality(season_months) = 1
            AND status IN ('development', 'validated')
          ORDER BY source_latest_month
        """)
        rainfall_runs = cur.fetchall()
        if not rainfall_runs:
            raise ValueError("No 2026 one-month final CHIRPS runs are available for calibration preview")

        cur.execute("""
          SELECT run_id FROM tsird.drought_population_run
          WHERE status IN ('development', 'validated') AND boundary_set_version = %s
          ORDER BY created_at DESC LIMIT 1
        """, (BOUNDARY_VERSION,))
        population_run = cur.fetchone()
        cur.execute("""
          SELECT run_id FROM tsird.drought_cropland_run
          WHERE status IN ('development', 'validated') AND boundary_set_version = %s
          ORDER BY created_at DESC LIMIT 1
        """, (BOUNDARY_VERSION,))
        cropland_run = cur.fetchone()
        cur.execute("""
          SELECT run_id FROM tsird.drought_road_accessibility_run
          WHERE status IN ('development', 'validated') AND boundary_set_version = %s
            AND run_id LIKE 'tsird-tigray-roads-2006-era-trra-proximity-%%'
          ORDER BY created_at DESC LIMIT 1
        """, (BOUNDARY_VERSION,))
        road_run = cur.fetchone()
        if not population_run or not cropland_run or not road_run:
            raise ValueError("One or more required static exposure/context baselines are unavailable")
        population_run, cropland_run, road_run = population_run[0], cropland_run[0], road_run[0]

        summaries = []
        for rainfall_run, source_month in rainfall_runs:
            snapshot_id = f"sarsrp-calibration-preview-{rainfall_run}"
            valid_from = (source_month.replace(day=1) + timedelta(days=32)).replace(day=1)
            valid_to = (valid_from + timedelta(days=123)).replace(day=1) - timedelta(days=1)
            source_runs = json.dumps({"rainfall": rainfall_run, "population": population_run,
                                      "cropland": cropland_run, "roads": road_run})
            quality_gate = json.dumps({"kind": "historical_calibration_preview", "minimum_rainfall_coverage_pct": MIN_COVERAGE_PCT,
                                       "outlook_used": False, "automatic_publication": False})
            methodology = json.dumps({"rainfall_bands": {"very_low": "percentile <= 10", "low": "percentile > 10 and <= 20", "watch": "percentile > 20 and <= 33", "no_signal": "percentile > 33"},
                                      "exposure": "population and cropland retained as separate local deciles", "road": "context tag only", "composite_priority": "not_calculated"})
            cur.execute("""
              INSERT INTO tsird.drought_priority_snapshot
                (snapshot_id, configuration_id, status, decision_kind, issued_at, evidence_cutoff_at,
                 valid_from, valid_to, boundary_set_version, source_run_ids, quality_gate, methodology, review_note)
              VALUES (%s, %s, 'draft', 'observed_stress_response_readiness', now(), %s::timestamptz,
                      %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb,
                      'Historical calibration preview only. It is not an as-issued forecast or a priority result.')
              ON CONFLICT (snapshot_id) DO UPDATE SET
                source_run_ids = EXCLUDED.source_run_ids, quality_gate = EXCLUDED.quality_gate,
                methodology = EXCLUDED.methodology, review_note = EXCLUDED.review_note, created_at = now()
            """, (snapshot_id, CONFIGURATION_ID, source_month, valid_from, valid_to, BOUNDARY_VERSION,
                  source_runs, quality_gate, methodology))
            cur.execute("""
              WITH population AS (
                SELECT tsird_tabia_id, ntile(10) OVER (ORDER BY population_total) AS decile
                FROM tsird.drought_tabia_population
                WHERE run_id = %s AND quality_status = 'ok'
              ), cropland AS (
                SELECT tsird_tabia_id, ntile(10) OVER (ORDER BY cropland_pct) AS decile
                FROM tsird.drought_tabia_cropland
                WHERE run_id = %s AND quality_status = 'ok'
              )
              INSERT INTO tsird.drought_priority_tabia_assessment
                (snapshot_id, tsird_tabia_id, rainfall_mm, rainfall_baseline_median_mm, rainfall_percentile,
                 rainfall_band, population_decile, cropland_decile, nearest_road_m, road_context,
                 evidence_state, rationale)
              SELECT %s, r.tsird_tabia_id, r.rainfall_mm, r.baseline_median_mm, r.percentile,
                CASE
                  WHEN r.quality_status <> 'ok' OR r.coverage_pct < %s OR r.percentile IS NULL THEN 'unavailable'
                  WHEN r.percentile <= 10 THEN 'very_low'
                  WHEN r.percentile <= 20 THEN 'low'
                  WHEN r.percentile <= 33 THEN 'watch'
                  ELSE 'no_signal'
                END,
                p.decile, c.decile, road.nearest_road_m,
                CASE
                  WHEN road.quality_status <> 'ok' THEN 'unavailable'
                  WHEN road.nearest_road_m < 900 THEN 'near'
                  WHEN road.nearest_road_m < 5500 THEN 'intermediate'
                  ELSE 'far'
                END,
                CASE WHEN r.quality_status = 'ok' AND r.coverage_pct >= %s THEN 'eligible_for_review'
                     WHEN r.quality_status = 'ok' THEN 'insufficient_coverage' ELSE 'unavailable' END,
                jsonb_build_object('kind', 'historical_calibration_preview', 'composite_priority', 'not_calculated',
                  'rainfall_rule', 'same-month CHIRPS 1991-2020 percentile', 'outlook_used', false)
              FROM tsird.drought_tabia_rainfall_condition r
              LEFT JOIN population p ON p.tsird_tabia_id = r.tsird_tabia_id
              LEFT JOIN cropland c ON c.tsird_tabia_id = r.tsird_tabia_id
              LEFT JOIN tsird.drought_tabia_road_accessibility road
                ON road.tsird_tabia_id = r.tsird_tabia_id AND road.run_id = %s
              WHERE r.run_id = %s
              ON CONFLICT (snapshot_id, tsird_tabia_id) DO UPDATE SET
                rainfall_mm = EXCLUDED.rainfall_mm, rainfall_baseline_median_mm = EXCLUDED.rainfall_baseline_median_mm,
                rainfall_percentile = EXCLUDED.rainfall_percentile, rainfall_band = EXCLUDED.rainfall_band,
                population_decile = EXCLUDED.population_decile, cropland_decile = EXCLUDED.cropland_decile,
                nearest_road_m = EXCLUDED.nearest_road_m, road_context = EXCLUDED.road_context,
                evidence_state = EXCLUDED.evidence_state, rationale = EXCLUDED.rationale, created_at = now()
            """, (population_run, cropland_run, snapshot_id, MIN_COVERAGE_PCT, MIN_COVERAGE_PCT, road_run, rainfall_run))
            cur.execute("""
              SELECT count(*), count(*) FILTER (WHERE evidence_state = 'eligible_for_review'),
                     count(*) FILTER (WHERE rainfall_band = 'very_low'),
                     count(*) FILTER (WHERE rainfall_band = 'low'),
                     count(*) FILTER (WHERE rainfall_band = 'watch')
              FROM tsird.drought_priority_tabia_assessment WHERE snapshot_id = %s
            """, (snapshot_id,))
            total, eligible, very_low, low, watch = cur.fetchone()
            summaries.append({"snapshot_id": snapshot_id, "source_month": source_month.isoformat(), "tabias": total,
                              "eligible_for_review": eligible, "very_low": very_low, "low": low, "watch": watch})
    print(json.dumps({"valid": True, "configuration_id": CONFIGURATION_ID,
                      "kind": "historical_calibration_preview", "snapshots": summaries}, default=str))


if __name__ == "__main__":
    main()
