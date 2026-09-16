"""Build a review-required Tabia seasonal reference from retained candidate evidence.

The reference is an observed same-calendar-month median and central range. It
is deliberately separate from Model Studio and Priority Replay. Historical
observations are later compared leave-one-year-out in the API, avoiding a
reference that contains the value being interpreted.
"""
import json
import os
from datetime import datetime, timezone

import psycopg2

REFERENCE_ID = "tsird-seasonal-reference-2018-2025-v1"
MINIMUM_VALID_YEARS = 6


def dsn():
    return " ".join(("host=tsird-postgis", "port=5432", f"dbname={os.environ['POSTGRES_DB']}",
                     f"user={os.environ['POSTGRES_USER']}", f"password={os.environ['POSTGRES_PASSWORD']}"))


def main():
    with psycopg2.connect(dsn()) as conn, conn.cursor() as cur:
        cur.execute("""
          INSERT INTO tsird.drought_seasonal_reference_run
            (reference_id, candidate_start_year, candidate_end_year, method_version, minimum_valid_years, status, notes)
          VALUES (%s, 2018, 2025, 'same-month-median-p20-p80.v1', %s, 'candidate_review_required', %s)
          ON CONFLICT (reference_id) DO UPDATE SET method_version=EXCLUDED.method_version,
            minimum_valid_years=EXCLUDED.minimum_valid_years, status=EXCLUDED.status, notes=EXCLUDED.notes, created_at=now()
        """, (REFERENCE_ID, MINIMUM_VALID_YEARS,
               "Observed evidence reference only: 2018-2025 same-calendar-month median and P20/P80; minimum six quality-approved years. It is not a forecast, priority class, drought classification, or Model Studio input."))
        cur.execute("DELETE FROM tsird.drought_tabia_ndvi_seasonal_reference WHERE reference_id=%s", (REFERENCE_ID,))
        cur.execute("""
          INSERT INTO tsird.drought_tabia_ndvi_seasonal_reference
            (reference_id, tsird_tabia_id, calendar_month, valid_year_count, median_value, p20_value, p80_value)
          SELECT %s, tsird_tabia_id, calendar_month, valid_year_count, median_value, p20_value, p80_value
          FROM (
            SELECT n.tsird_tabia_id, EXTRACT(MONTH FROM r.observation_end)::int AS calendar_month,
                   count(*)::int AS valid_year_count,
                   percentile_cont(0.5) WITHIN GROUP (ORDER BY n.ndvi_mean) AS median_value,
                   percentile_cont(0.2) WITHIN GROUP (ORDER BY n.ndvi_mean) AS p20_value,
                   percentile_cont(0.8) WITHIN GROUP (ORDER BY n.ndvi_mean) AS p80_value
            FROM tsird.drought_tabia_ndvi n JOIN tsird.drought_ndvi_run r USING (run_id)
            WHERE EXTRACT(YEAR FROM r.observation_end) BETWEEN 2018 AND 2025
              AND r.status IN ('development', 'degraded', 'validated')
              AND (r.seasonal_reference_candidate_only OR r.notes LIKE 'Baseline pilot only%%')
              AND n.quality_status='ok' AND n.coverage_pct >= 90 AND n.ndvi_mean IS NOT NULL
            GROUP BY n.tsird_tabia_id, EXTRACT(MONTH FROM r.observation_end)
          ) summary WHERE valid_year_count >= %s
        """, (REFERENCE_ID, MINIMUM_VALID_YEARS))
        ndvi_rows = cur.rowcount
        cur.execute("DELETE FROM tsird.drought_tabia_wapor_seasonal_reference WHERE reference_id=%s", (REFERENCE_ID,))
        cur.execute("""
          INSERT INTO tsird.drought_tabia_wapor_seasonal_reference
            (reference_id, tsird_tabia_id, calendar_month, valid_year_count, median_transpiration_mm, p20_transpiration_mm, p80_transpiration_mm)
          SELECT %s, tsird_tabia_id, calendar_month, valid_year_count, median_value, p20_value, p80_value
          FROM (
            SELECT w.tsird_tabia_id, EXTRACT(MONTH FROM r.source_period_end)::int AS calendar_month,
                   count(*)::int AS valid_year_count,
                   percentile_cont(0.5) WITHIN GROUP (ORDER BY w.transpiration_mm) AS median_value,
                   percentile_cont(0.2) WITHIN GROUP (ORDER BY w.transpiration_mm) AS p20_value,
                   percentile_cont(0.8) WITHIN GROUP (ORDER BY w.transpiration_mm) AS p80_value
            FROM tsird.drought_tabia_wapor w JOIN tsird.drought_wapor_run r USING (run_id)
            WHERE EXTRACT(YEAR FROM r.source_period_end) BETWEEN 2018 AND 2025
              AND r.status IN ('development', 'degraded', 'validated')
              AND (r.seasonal_reference_candidate_only OR r.notes LIKE 'Baseline pilot only%%')
              AND w.quality_status='ok' AND w.coverage_pct >= 90 AND w.transpiration_mm IS NOT NULL
            GROUP BY w.tsird_tabia_id, EXTRACT(MONTH FROM r.source_period_end)
          ) summary WHERE valid_year_count >= %s
        """, (REFERENCE_ID, MINIMUM_VALID_YEARS))
        wapor_rows = cur.rowcount
    receipt = {"status": "candidate_review_required", "reference_id": REFERENCE_ID,
               "candidate_period": "2018-2025", "minimum_valid_years": MINIMUM_VALID_YEARS,
               "ndvi_reference_rows": ndvi_rows, "wapor_reference_rows": wapor_rows,
               "built_at": datetime.now(timezone.utc).isoformat(),
               "next_step": "Review coverage and seasonal plausibility before treating relative-to-reference values as planning evidence. This reference cannot enable priority scoring."}
    with open("/data/drought/outputs/seasonal-reference-build-receipt.json", "w", encoding="utf-8") as handle:
        json.dump(receipt, handle, indent=2)
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
