"""Read-only evidence gate for the TSIRD seasonal-stress draft model.

This module deliberately does not calculate a score, write a snapshot, or
start a download.  It inspects the latest local evidence runs and returns a
redacted, JSON-safe account of what may and may not be used in a reviewed
monthly draft.  The gate exists so a stale or degraded provider artifact never
silently becomes a decision product.
"""
import json
import os
from datetime import date, datetime, timezone

import psycopg2


EXPECTED_BOUNDARY_VERSION = "tsird-tabias-v1"
ELIGIBLE_TABIA_COVERAGE_PCT = 90.0


def dsn():
    return " ".join(("host=tsird-postgis", "port=5432", f"dbname={os.environ['POSTGRES_DB']}",
                     f"user={os.environ['POSTGRES_USER']}", f"password={os.environ['POSTGRES_PASSWORD']}"))


def iso(value):
    return value.isoformat() if value is not None else None


def age_days(value, today):
    if value is None:
        return None
    if isinstance(value, datetime):
        value = value.date()
    return (today - value).days


def quality_summary(cursor, table, run_id, has_coverage=True):
    """Count rows only; no Tabia values are returned from the readiness gate."""
    coverage = "coalesce(round(avg(coverage_pct)::numeric, 2), 0)::float" if has_coverage else "100.0::float"
    cursor.execute(f"""
        SELECT count(*)::integer,
               count(*) FILTER (WHERE quality_status = 'ok')::integer,
               {coverage}
        FROM {table}
        WHERE run_id = %s
    """, (run_id,))
    rows, usable, coverage = cursor.fetchone()
    return {"tabias": rows, "usable_tabias": usable, "mean_coverage_pct": coverage}


def latest(cursor, sql):
    cursor.execute(sql)
    return cursor.fetchone()


def retained_month_inventory(cursor, table, run_table, date_column):
    """Describe retained local observations without treating them as a normal."""
    cursor.execute(f"""
        SELECT count(DISTINCT r.run_id)::integer,
               count(DISTINCT date_trunc('month', r.{date_column}))::integer,
               min(r.{date_column})::date,
               max(r.{date_column})::date,
               coalesce(array_agg(DISTINCT to_char(r.{date_column}, 'YYYY-MM')
                                  ORDER BY to_char(r.{date_column}, 'YYYY-MM')), ARRAY[]::text[])
        FROM {table} item
        JOIN {run_table} r USING (run_id)
        WHERE r.status IN ('development', 'degraded', 'validated', 'published')
    """)
    runs, months, first, latest_observation, calendar_months = cursor.fetchone()
    return {
        "retained_runs": runs,
        "retained_months": months,
        "first_observation": iso(first),
        "latest_observation": iso(latest_observation),
        "calendar_months": calendar_months,
        "is_validated_seasonal_baseline": False,
        "note": "Retained observations only; not a validated same-calendar-month seasonal baseline.",
    }


def source_result(source_id, role, run, observation_date, freshness_days, quality=None,
                  boundary_version=None, required_for_draft=False, baseline_ready=None, extra=None,
                  expected_tabias=None):
    today = date.today()
    result = {
        "source_id": source_id,
        "role": role,
        "required_for_draft": required_for_draft,
        "run_id": run[0] if run else None,
        "run_status": run[1] if run else "unavailable",
        "observation_date": iso(observation_date),
        "age_days": age_days(observation_date, today),
        "freshness_threshold_days": freshness_days,
        "quality": quality,
        "boundary_set_version": boundary_version,
        "baseline_ready": baseline_ready,
        "state": "unavailable",
        "reasons": [],
    }
    if extra:
        result.update(extra)
    if not run:
        result["reasons"].append("No local run is available.")
        return result
    if run[1] in {"failed", "degraded"}:
        result["reasons"].append(f"Latest run is {run[1]}.")
    if freshness_days is not None and result["age_days"] is not None and result["age_days"] > freshness_days:
        result["reasons"].append(f"Observation is older than the {freshness_days}-day freshness policy.")
    if quality and (quality["tabias"] == 0 or quality["usable_tabias"] == 0):
        result["reasons"].append("No Tabia summaries meet the source quality rule.")
    if quality and expected_tabias and quality["tabias"] < expected_tabias:
        result["reasons"].append(f"Only {quality['tabias']} of {expected_tabias} canonical Tabias have a source summary.")
    if quality and quality["tabias"] and quality["mean_coverage_pct"] < ELIGIBLE_TABIA_COVERAGE_PCT:
        result["reasons"].append("Mean Tabia coverage is below the readiness policy.")
    if boundary_version and boundary_version != EXPECTED_BOUNDARY_VERSION:
        result["reasons"].append("Boundary-set version does not match the current model contract.")
    if baseline_ready is False:
        result["reasons"].append("A validated seasonal baseline is not available.")
    if not result["reasons"]:
        result["state"] = "usable"
    elif run[1] == "degraded":
        result["state"] = "degraded"
    elif result["age_days"] is not None and freshness_days is not None and result["age_days"] > freshness_days:
        result["state"] = "stale"
    else:
        result["state"] = "incomplete"
    return result


def build_readiness_report():
    """Inspect local evidence in a read-only transaction and return the gate."""
    with psycopg2.connect(dsn()) as conn:
        conn.set_session(readonly=True, autocommit=False)
        with conn.cursor() as cur:
            cur.execute("""
                SELECT count(*)::integer, count(*) FILTER (WHERE review_required)::integer,
                       coalesce(max(boundary_set_version), 'unknown')
                FROM tsird.tabia_identity
            """)
            identity_rows, review_required_tabias, identity_version = cur.fetchone()

            rainfall = latest(cur, """
                SELECT run_id, status, source_latest_month, created_at
                FROM tsird.drought_rainfall_run
                ORDER BY source_latest_month DESC, cardinality(season_months) DESC, created_at DESC LIMIT 1
            """)
            rapid = latest(cur, """
                SELECT run_id, status, period_end, created_at
                FROM tsird.drought_preliminary_rainfall_run ORDER BY period_end DESC, created_at DESC LIMIT 1
            """)
            ndvi = latest(cur, """
                SELECT run_id, status, observation_end::date, created_at
                FROM tsird.drought_ndvi_run ORDER BY observation_end DESC, created_at DESC LIMIT 1
            """)
            swi = latest(cur, """
                SELECT run_id, status, observation_at::date, created_at
                FROM tsird.drought_swi_run ORDER BY observation_at DESC, created_at DESC LIMIT 1
            """)
            wapor = latest(cur, """
                SELECT run_id, status, source_period_end, created_at, source_revision
                FROM tsird.drought_wapor_run ORDER BY source_period_end DESC, created_at DESC LIMIT 1
            """)
            population = latest(cur, """
                SELECT run_id, status, population_year, boundary_set_version, created_at
                FROM tsird.drought_population_run ORDER BY created_at DESC LIMIT 1
            """)
            cropland = latest(cur, """
                SELECT run_id, status, source_year, boundary_set_version, created_at
                FROM tsird.drought_cropland_run ORDER BY created_at DESC LIMIT 1
            """)
            roads = latest(cur, """
                SELECT run_id, status, source_feature_count, boundary_set_version, created_at
                FROM tsird.drought_road_accessibility_run
                WHERE run_id LIKE 'tsird-tigray-roads-2006-era-trra-proximity-%'
                ORDER BY created_at DESC LIMIT 1
            """)
            baseline_inventory = {
                "ndvi": retained_month_inventory(cur, "tsird.drought_tabia_ndvi", "tsird.drought_ndvi_run", "observation_end"),
                "wapor": retained_month_inventory(cur, "tsird.drought_tabia_wapor", "tsird.drought_wapor_run", "source_period_end"),
            }

            sources = [
                source_result("chc-chirps-v3-final", "core observed rainfall", rainfall,
                              rainfall[2] if rainfall else None, 45,
                              quality_summary(cur, "tsird.drought_tabia_rainfall_condition", rainfall[0]) if rainfall else None,
                              required_for_draft=True, expected_tabias=identity_rows),
                source_result("chc-chirps-v3-preliminary", "rapid supporting rainfall", rapid,
                              rapid[2] if rapid else None, 10,
                              quality_summary(cur, "tsird.drought_tabia_preliminary_rainfall", rapid[0]) if rapid else None,
                              expected_tabias=identity_rows),
                source_result("cdse-clms-ndvi-v3", "core vegetation evidence", ndvi,
                              ndvi[2] if ndvi else None, 20,
                              quality_summary(cur, "tsird.drought_tabia_ndvi", ndvi[0]) if ndvi else None,
                              required_for_draft=True, baseline_ready=False, expected_tabias=identity_rows),
                source_result("cdse-clms-swi-v4", "coarse soil-water context", swi,
                              swi[2] if swi else None, 20,
                              quality_summary(cur, "tsird.drought_tabia_swi", swi[0]) if swi else None,
                              expected_tabias=identity_rows),
                source_result("fao-wapor-v3", "supporting agricultural water-use", wapor,
                              wapor[2] if wapor else None, 25,
                              quality_summary(cur, "tsird.drought_tabia_wapor", wapor[0]) if wapor else None,
                              baseline_ready=False,
                              extra={"source_revision": wapor[4] if wapor else None}, expected_tabias=identity_rows),
                source_result("worldpop-global-2025-r2025a-v1", "population exposure baseline", population,
                              None, None,
                              quality_summary(cur, "tsird.drought_tabia_population", population[0]) if population else None,
                              population[3] if population else None,
                              extra={"reference_year": population[2] if population else None}, expected_tabias=identity_rows),
                source_result("esa-worldcover-2021-v200", "cropland exposure baseline", cropland,
                              None, None,
                              quality_summary(cur, "tsird.drought_tabia_cropland", cropland[0]) if cropland else None,
                              cropland[3] if cropland else None,
                              extra={"reference_year": cropland[2] if cropland else None}, expected_tabias=identity_rows),
                source_result("tsird-tigray-roads-2006-era-trra", "road-proximity response tag", roads,
                              None, None,
                              quality_summary(cur, "tsird.drought_tabia_road_accessibility", roads[0], has_coverage=False) if roads else None,
                              roads[3] if roads else None,
                              extra={"source_feature_count": roads[2] if roads else None}, expected_tabias=identity_rows),
            ]

    required_failures = [item for item in sources if item["required_for_draft"] and item["state"] != "usable"]
    capped = any(item["source_id"] in {"cdse-clms-ndvi-v3", "fao-wapor-v3"} and item["state"] != "usable" for item in sources)
    reasons = [
        "No decision score, food-security classification, or automated publication is enabled in this development gate.",
        "A reviewed NDVI and WaPOR seasonal baseline is required before any class above Watch can be proposed.",
    ]
    if review_required_tabias:
        reasons.append(
            f"{review_required_tabias} of {identity_rows} Tabia identities retain a duplicate-source-T8ID review flag; "
            "the canonical tsird_tabia_id remains unique and all records must be processed."
        )
    if required_failures:
        reasons.extend(f"{item['source_id']}: {reason}" for item in required_failures for reason in item["reasons"])
    status = "not_ready" if required_failures else "draft_evidence_only"
    return {
        "schema_version": "tsird-seasonal-stress-readiness.v1",
        "environment": "development",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "read_only": True,
        "model": "Seasonal Agricultural Stress & Response Priority",
        "boundary": {"expected_version": EXPECTED_BOUNDARY_VERSION, "identity_version": identity_version,
                     "canonical_tabias": identity_rows,
                     "duplicate_source_t8id_review_required": review_required_tabias},
        "decision": {
            "status": status,
            "draft_matrix_allowed": not required_failures,
            "publication_allowed": False,
            "maximum_observed_stress_class": "Watch" if capped else "Not evaluated",
            "reasons": reasons,
        },
        "sources": sources,
        "policy": {
            "minimum_mean_tabia_coverage_pct": ELIGIBLE_TABIA_COVERAGE_PCT,
            "final_rainfall_freshness_days": 45,
            "rapid_rainfall_freshness_days": 10,
            "ndvi_freshness_days": 20,
            "swi_freshness_days": 20,
            "wapor_freshness_days": 25,
        },
        "seasonal_baseline_preflight": {
            "status": "not_ready",
            "purpose": "Inventory local evidence before proposing a reviewed seasonal-baseline acquisition plan.",
            "retained_evidence": baseline_inventory,
            "next_safe_action": "The 2018–2025 candidate history and separate observed reference are retained for review. Keep this gate not ready until experts validate the period, same-calendar-month method, quality rule, and intended model use.",
            "not_an_action": "Does not query provider archives, download data, calculate anomalies, or change the priority replay.",
        },
    }


if __name__ == "__main__":
    print(json.dumps(build_readiness_report(), sort_keys=True))
