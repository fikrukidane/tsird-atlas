"""Create conservative, draft-only January--August 2026 priority replays.

This fixed local development job reads the active Model Studio configuration
and retained final-CHIRPS, population, cropland and road-context evidence.
It does not forecast, publish, allocate assistance, or create IPC/food-security
classifications.  It makes the first rule matrix executable solely for
historical practitioner review.
"""
import json
import os
from datetime import timedelta

import psycopg2


BOUNDARY_VERSION = "tsird-tabias-v1"
MIN_COVERAGE_PCT = 90.0
REPLAY_MONTHS = tuple(range(1, 9))


def dsn():
    return " ".join(("host=tsird-postgis", "port=5432", f"dbname={os.environ['POSTGRES_DB']}",
                     f"user={os.environ['POSTGRES_USER']}", f"password={os.environ['POSTGRES_PASSWORD']}"))


def main():
    with psycopg2.connect(dsn()) as conn, conn.cursor() as cur:
        cur.execute("""
          SELECT configuration_id, version, configuration
          FROM tsird.drought_priority_model_configuration
          WHERE status = 'draft' AND active_for_review
          ORDER BY version DESC LIMIT 1
        """)
        active = cur.fetchone()
        if not active:
            raise ValueError("No active local Model Studio draft is available")
        configuration_id, configuration_version, configuration = active
        if isinstance(configuration, str):
            configuration = json.loads(configuration)
        profiles = configuration.get("monthly_profiles") or []
        if len(profiles) != 12:
            raise ValueError("The active Model Studio draft must contain 12 monthly profiles")

        cur.execute("""
          SELECT run_id, source_latest_month
          FROM tsird.drought_rainfall_run
          WHERE analysis_year = 2026 AND cardinality(season_months) = 1
            AND EXTRACT(MONTH FROM source_latest_month) = ANY(%s)
            AND status IN ('development', 'validated')
          ORDER BY source_latest_month
        """, (list(REPLAY_MONTHS),))
        rainfall_runs = cur.fetchall()
        if not rainfall_runs:
            raise ValueError("No retained January--August 2026 one-month final CHIRPS runs are available")

        def static_run(table, extra=""):
            cur.execute(f"""
              SELECT run_id FROM {table}
              WHERE status IN ('development', 'validated') AND boundary_set_version = %s {extra}
              ORDER BY created_at DESC LIMIT 1
            """, (BOUNDARY_VERSION,))
            value = cur.fetchone()
            return value[0] if value else None

        population_run = static_run("tsird.drought_population_run")
        cropland_run = static_run("tsird.drought_cropland_run")
        road_run = static_run("tsird.drought_road_accessibility_run", "AND run_id LIKE 'tsird-tigray-roads-2006-era-trra-proximity-%%'")
        if not all((population_run, cropland_run, road_run)):
            raise ValueError("Population, cropland, or accessibility-context baseline is unavailable")

        summaries = []
        for rainfall_run, source_month in rainfall_runs:
            month_number = source_month.month
            profile = profiles[month_number - 1]
            snapshot_id = f"sarsrp-historical-replay-v{configuration_version}-{rainfall_run}"
            valid_from = source_month.replace(day=1)
            valid_to = (valid_from + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            source_runs = json.dumps({"rainfall": rainfall_run, "population": population_run,
                                      "cropland": cropland_run, "accessibility_context": road_run})
            quality_gate = json.dumps({"kind": "historical_priority_replay", "minimum_rainfall_coverage_pct": MIN_COVERAGE_PCT,
                                       "outlook_used": False, "forecast": False, "automatic_publication": False,
                                       "evidence_policy": "rainfall plus static exposure/accessibility context"})
            methodology = json.dumps({
                "configuration_version": configuration_version,
                "target_month_profile": profile,
                "rules": {
                    "critical": "rainfall percentile <= 10 and either population or cropland decile >= 7",
                    "high": "rainfall percentile <= 20 and either population or cropland decile >= 7",
                    "moderate": "rainfall percentile <= 33",
                    "watch": "rainfall percentile > 33 with valid rainfall evidence",
                    "insufficient_evidence": f"rainfall coverage below {MIN_COVERAGE_PCT}% or unavailable"
                },
                "accessibility": "explanation tag only; it does not change the class",
                "outlook": "not used", "publication": "draft-only"
            })
            cur.execute("""
              INSERT INTO tsird.drought_priority_snapshot
                (snapshot_id, configuration_id, status, decision_kind, issued_at, evidence_cutoff_at,
                 valid_from, valid_to, boundary_set_version, source_run_ids, quality_gate, methodology, review_note)
              VALUES (%s, %s, 'draft', 'observed_stress_response_readiness', now(), %s::timestamptz,
                      %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb,
                      'Historical replay from retained evidence and active local draft. It is not an as-issued forecast or a published priority decision.')
              ON CONFLICT (snapshot_id) DO UPDATE SET
                source_run_ids = EXCLUDED.source_run_ids, quality_gate = EXCLUDED.quality_gate,
                methodology = EXCLUDED.methodology, review_note = EXCLUDED.review_note, created_at = now()
            """, (snapshot_id, configuration_id, source_month, valid_from, valid_to, BOUNDARY_VERSION,
                  source_runs, quality_gate, methodology))
            cur.execute("""
              WITH population AS (
                SELECT tsird_tabia_id, ntile(10) OVER (ORDER BY population_total) AS decile
                FROM tsird.drought_tabia_population WHERE run_id = %s AND quality_status = 'ok'
              ), cropland AS (
                SELECT tsird_tabia_id, ntile(10) OVER (ORDER BY cropland_pct) AS decile
                FROM tsird.drought_tabia_cropland WHERE run_id = %s AND quality_status = 'ok'
              ), evidence AS (
                SELECT r.*, p.decile AS population_decile, c.decile AS cropland_decile,
                       road.nearest_road_m, road.quality_status AS road_quality
                FROM tsird.drought_tabia_rainfall_condition r
                LEFT JOIN population p ON p.tsird_tabia_id = r.tsird_tabia_id
                LEFT JOIN cropland c ON c.tsird_tabia_id = r.tsird_tabia_id
                LEFT JOIN tsird.drought_tabia_road_accessibility road
                  ON road.tsird_tabia_id = r.tsird_tabia_id AND road.run_id = %s
                WHERE r.run_id = %s
              )
              INSERT INTO tsird.drought_priority_tabia_assessment
                (snapshot_id, tsird_tabia_id, rainfall_mm, rainfall_baseline_median_mm, rainfall_percentile,
                 rainfall_band, population_decile, cropland_decile, nearest_road_m, road_context,
                 evidence_state, rationale, assessment_kind, priority_class, priority_rank, planning_action,
                 triggered_rules, input_quality)
              SELECT %s, tsird_tabia_id, rainfall_mm, baseline_median_mm, percentile,
                CASE WHEN quality_status <> 'ok' OR coverage_pct < %s OR percentile IS NULL THEN 'unavailable'
                     WHEN percentile <= 10 THEN 'very_low' WHEN percentile <= 20 THEN 'low'
                     WHEN percentile <= 33 THEN 'watch' ELSE 'no_signal' END,
                population_decile, cropland_decile, nearest_road_m,
                CASE WHEN road_quality <> 'ok' THEN 'unavailable' WHEN nearest_road_m < 900 THEN 'near'
                     WHEN nearest_road_m < 5500 THEN 'intermediate' ELSE 'far' END,
                CASE WHEN quality_status = 'ok' AND coverage_pct >= %s THEN 'eligible_for_review'
                     WHEN quality_status = 'ok' THEN 'insufficient_coverage' ELSE 'unavailable' END,
                jsonb_build_object('kind','historical_priority_replay','configuration_id',%s,
                  'configuration_version',%s,'target_month',%s,'forecast',false,'outlook_used',false),
                'historical_priority_replay',
                CASE WHEN quality_status <> 'ok' OR coverage_pct < %s OR percentile IS NULL THEN 'insufficient_evidence'
                     WHEN percentile <= 10 AND (coalesce(population_decile,0) >= 7 OR coalesce(cropland_decile,0) >= 7) THEN 'critical'
                     WHEN percentile <= 20 AND (coalesce(population_decile,0) >= 7 OR coalesce(cropland_decile,0) >= 7) THEN 'high'
                     WHEN percentile <= 33 THEN 'moderate' ELSE 'watch' END,
                CASE WHEN quality_status <> 'ok' OR coverage_pct < %s OR percentile IS NULL THEN 0
                     WHEN percentile <= 10 AND (coalesce(population_decile,0) >= 7 OR coalesce(cropland_decile,0) >= 7) THEN 4
                     WHEN percentile <= 20 AND (coalesce(population_decile,0) >= 7 OR coalesce(cropland_decile,0) >= 7) THEN 3
                     WHEN percentile <= 33 THEN 2 ELSE 1 END,
                CASE WHEN quality_status <> 'ok' OR coverage_pct < %s OR percentile IS NULL THEN 'Do not rank; resolve evidence gap'
                     WHEN percentile <= 10 AND (coalesce(population_decile,0) >= 7 OR coalesce(cropland_decile,0) >= 7) THEN 'Immediate verification and coordinated response planning'
                     WHEN percentile <= 20 AND (coalesce(population_decile,0) >= 7 OR coalesce(cropland_decile,0) >= 7) THEN 'Targeted verification and Woreda planning review'
                     WHEN percentile <= 33 THEN 'Monitor closely and prepare contingency options'
                     ELSE 'Continue monitoring and verify evidence' END,
                jsonb_build_array(
                  CASE WHEN quality_status <> 'ok' OR coverage_pct < %s OR percentile IS NULL THEN 'Insufficient evidence: rainfall is unavailable or below coverage gate'
                       WHEN percentile <= 10 AND (coalesce(population_decile,0) >= 7 OR coalesce(cropland_decile,0) >= 7) THEN 'Critical: very low same-month rainfall and elevated exposure'
                       WHEN percentile <= 20 AND (coalesce(population_decile,0) >= 7 OR coalesce(cropland_decile,0) >= 7) THEN 'High: low same-month rainfall and elevated exposure'
                       WHEN percentile <= 33 THEN 'Moderate: rainfall is below the watch threshold'
                       ELSE 'Watch: valid rainfall evidence without an adverse rainfall threshold' END,
                  CASE WHEN road_quality = 'ok' AND nearest_road_m >= 5500 THEN 'Accessibility context: constrained (distance to mapped roads)'
                       WHEN road_quality = 'ok' THEN 'Accessibility context: mapped-road proximity available'
                       ELSE 'Accessibility context: unavailable' END),
                jsonb_build_object('rainfall_coverage_pct',coverage_pct,'rainfall_quality',quality_status,
                  'population_available',population_decile IS NOT NULL,'cropland_available',cropland_decile IS NOT NULL,
                  'accessibility_available',road_quality = 'ok')
              FROM evidence
              ON CONFLICT (snapshot_id, tsird_tabia_id) DO UPDATE SET
                rainfall_mm=EXCLUDED.rainfall_mm, rainfall_baseline_median_mm=EXCLUDED.rainfall_baseline_median_mm,
                rainfall_percentile=EXCLUDED.rainfall_percentile, rainfall_band=EXCLUDED.rainfall_band,
                population_decile=EXCLUDED.population_decile, cropland_decile=EXCLUDED.cropland_decile,
                nearest_road_m=EXCLUDED.nearest_road_m, road_context=EXCLUDED.road_context,
                evidence_state=EXCLUDED.evidence_state, rationale=EXCLUDED.rationale,
                assessment_kind=EXCLUDED.assessment_kind, priority_class=EXCLUDED.priority_class,
                priority_rank=EXCLUDED.priority_rank, planning_action=EXCLUDED.planning_action,
                triggered_rules=EXCLUDED.triggered_rules, input_quality=EXCLUDED.input_quality, created_at=now()
            """, (population_run, cropland_run, road_run, rainfall_run, snapshot_id, MIN_COVERAGE_PCT,
                  MIN_COVERAGE_PCT, configuration_id, configuration_version, month_number, MIN_COVERAGE_PCT,
                  MIN_COVERAGE_PCT, MIN_COVERAGE_PCT, MIN_COVERAGE_PCT))
            cur.execute("""
              SELECT priority_class, count(*) FROM tsird.drought_priority_tabia_assessment
              WHERE snapshot_id = %s AND assessment_kind = 'historical_priority_replay'
              GROUP BY priority_class ORDER BY priority_class
            """, (snapshot_id,))
            summaries.append({"snapshot_id": snapshot_id, "source_month": source_month.isoformat(),
                              "classes": dict(cur.fetchall())})
    print(json.dumps({"valid": True, "kind": "historical_priority_replay", "configuration_id": configuration_id,
                      "configuration_version": configuration_version, "snapshots": summaries}, default=str))


if __name__ == "__main__":
    main()
