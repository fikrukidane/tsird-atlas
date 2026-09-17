"""
TSIRD Gazetteer API
Endpoint: GET /gazetteer?q=<search text>
Returns bilingual woreda/tabia search results from PostGIS.
"""
import json
import logging
import os
import asyncio
import re
import urllib.error
import urllib.request
from pathlib import Path
from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import asyncpg

app = FastAPI(title="TSIRD Gazetteer API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

DB_DSN = (
    f"postgresql://{os.environ['POSTGRES_USER']}:{os.environ['POSTGRES_PASSWORD']}"
    f"@tsird-postgis:5432/{os.environ['POSTGRES_DB']}"
)
DROUGHT_RUNNER_CONTROL_URL = os.environ.get(
    "DROUGHT_RUNNER_CONTROL_URL", "http://tsird-drought-runner:8090/control"
)
DROUGHT_RUNNER_READINESS_URL = os.environ.get(
    "DROUGHT_RUNNER_READINESS_URL", "http://tsird-drought-runner:8090/readiness"
)
EVIDENCE_DATA_ROOT = Path("/data/drought")
# Production may expose one approved, compact release from this read-only root.
# The development runner and n8n are never mounted here.  Until a future
# publisher writes an approved current.json pointer, these public-release
# endpoints intentionally report that no release is available.
PUBLIC_DROUGHT_RELEASE_ROOT = Path(
    os.environ.get("DROUGHT_PUBLIC_RELEASE_ROOT", "/data/drought/production-releases")
)
# Indicator evidence has a separate, automatically maintained pointer beneath
# the same read-only release mount.  Priority/replay releases never use it.
PUBLIC_DROUGHT_INDICATOR_RELEASE_ROOT = Path(
    os.environ.get(
        "DROUGHT_PUBLIC_INDICATOR_RELEASE_ROOT",
        str(PUBLIC_DROUGHT_RELEASE_ROOT / "indicators"),
    )
)
PUBLIC_RELEASE_ID_PATTERN = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{6}Z(?:-[a-z0-9][a-z0-9-]*)?$"
)
# This is intentionally an allow-list.  The API never accepts a filesystem
# path from the browser; it can serve only a catalogue row for an evidence
# source that is part of this development dashboard.
EVIDENCE_RASTER_SOURCES = {
    "rainfall": "chc-chirps-v3",
    "rapid": "chc-chirps-v3-preliminary",
    "ndvi": "cdse-clms-ndvi-v3",
    "swi": "cdse-clms-swi-v4",
    "lst": "cdse-clms-lst-v2",
    "wapor": "fao-wapor-v3",
}
# A fixed, documented shortlist for the candidate-reference workshop. These
# identifiers are never treated as a representative sample or as priority
# labels; they merely make the Scenario Laboratory reproducible.
SCENARIO_LAB_CASES = [
    ("wetter western agricultural candidate", "tsird-tabia-v1-4200d2f495591e46aee632f9529f6f6f"),
    ("central-highland candidate", "tsird-tabia-v1-bb1bb6abba4d5339d1dcd1edc9523621"),
    ("central-highland candidate", "tsird-tabia-v1-1038952382778b3bcd0ef8ddccfc2286"),
    ("central-highland candidate", "tsird-tabia-v1-aa5feb253d22529965fc500be3aea8d2"),
    ("eastern low-rainfall candidate", "tsird-tabia-v1-6eb37762cec5def0f9dc6fff92040be6"),
    ("eastern low-rainfall candidate", "tsird-tabia-v1-17952c819634151a4ccc69c84d68a047"),
    ("eastern low-rainfall candidate", "tsird-tabia-v1-f66b7786ed9d8920e50d71fb3f244be7"),
    ("eastern low-rainfall candidate", "tsird-tabia-v1-c60f39cb151191880531ea8a2e57a248"),
    ("eastern low-rainfall candidate", "tsird-tabia-v1-759596e82712e7cf443ae29940fc66dc"),
    ("southern / southeastern candidate", "tsird-tabia-v1-d66d8cda8de6842bed9f97f33f34136c"),
    ("southern / southeastern candidate", "tsird-tabia-v1-96b818e8fa59beedbaad9aa6909c162b"),
    ("southern / southeastern candidate", "tsird-tabia-v1-5867970055894a1ea96772db58c0be5a"),
    ("southern / southeastern candidate", "tsird-tabia-v1-85f6934d7f652f364c0a3bb3b3c7068b"),
    ("southern / southeastern candidate", "tsird-tabia-v1-4e774f1b9c641d7ab42d3eb17748380b"),
    ("apparently severe 2026 divergence", "tsird-tabia-v1-980e6ba52d5a8c2633f77bd1f7f0433e"),
    ("contradictory evidence", "tsird-tabia-v1-7236df874adfef3db91ebfcf8ce33777"),
]
SCENARIO_LAB_CASE_SQL = """
  WITH selected AS (
    SELECT tabia_id, ord::int AS ord
    FROM unnest($1::text[]) WITH ORDINALITY AS selected(tabia_id, ord)
  )
  SELECT json_build_object('cases', coalesce(json_agg(json_build_object(
    'tsird_tabia_id', t.tsird_tabia_id,
    'tabia_name', t."TABIA",
    'woreda_name', t."WEREDA",
    'rainfall_mm', r.rainfall_mm,
    'rainfall_percentile', r.percentile,
    'ndvi_value', n.ndvi_mean,
    'ndvi_reference_median', nr.median_value,
    'ndvi_deviation_pct', CASE WHEN nr.median_value > 0 THEN 100 * (n.ndvi_mean - nr.median_value) / nr.median_value END,
    'ndvi_reference_year_count', nr.valid_year_count,
    'wapor_value', w.transpiration_mm,
    'wapor_reference_median', wr.median_transpiration_mm,
    'wapor_deviation_pct', CASE WHEN wr.median_transpiration_mm > 0 THEN 100 * (w.transpiration_mm - wr.median_transpiration_mm) / wr.median_transpiration_mm END,
    'wapor_reference_year_count', wr.valid_year_count,
    'source_quality', json_build_object('rainfall', r.quality_status, 'ndvi', n.quality_status, 'wapor', w.quality_status)
  ) ORDER BY selected.ord), '[]'::json))
  FROM selected
  JOIN tigray_tabias_ws t ON t.tsird_tabia_id = selected.tabia_id
  LEFT JOIN tsird.drought_tabia_rainfall_condition r ON r.tsird_tabia_id=t.tsird_tabia_id
    AND r.run_id='chirps-v3-2026-8-baseline-1991-2020'
  LEFT JOIN tsird.drought_tabia_ndvi n ON n.tsird_tabia_id=t.tsird_tabia_id
    AND n.run_id='cdse-clms-ndvi-v3-20260821T000000Z'
  LEFT JOIN tsird.drought_tabia_ndvi_seasonal_reference nr ON nr.tsird_tabia_id=t.tsird_tabia_id
    AND nr.reference_id='tsird-seasonal-reference-2018-2025-v1' AND nr.calendar_month=8
  LEFT JOIN tsird.drought_tabia_wapor w ON w.tsird_tabia_id=t.tsird_tabia_id
    AND w.run_id='fao-wapor-v3-l2-202608-d3'
  LEFT JOIN tsird.drought_tabia_wapor_seasonal_reference wr ON wr.tsird_tabia_id=t.tsird_tabia_id
    AND wr.reference_id='tsird-seasonal-reference-2018-2025-v1' AND wr.calendar_month=8
"""
# NDVI and WaPOR historical snapshots are retained in their source-specific
# run tables.  Candidate seasonal-reference runs deliberately do not publish a
# generic raster-catalogue record, so the read-only history map must enumerate
# those bounded Tabia summaries separately.  This remains an allow-list: no
# browser-provided table or filesystem path is accepted.
HISTORICAL_TABIA_RUN_SQL = {
    "ndvi": """
      SELECT r.run_id, 'ndvi'::text AS evidence_kind, r.observation_start,
             r.observation_end, r.native_resolution, r.status,
             json_build_object(
               'retained_tabias', count(n.tsird_tabia_id),
               'usable_tabias', count(n.tsird_tabia_id) FILTER (
                 WHERE n.quality_status='ok' AND n.coverage_pct >= 90
               )
             ) AS quality_summary,
             json_build_object(
               'seasonal_reference_candidate_only', r.seasonal_reference_candidate_only,
               'reference_period', CASE WHEN r.seasonal_reference_candidate_only
                 THEN '2018-2025 candidate reference' END
             ) AS provenance
      FROM tsird.drought_ndvi_run r
      LEFT JOIN tsird.drought_tabia_ndvi n USING (run_id)
      WHERE r.status IN ('development', 'degraded', 'validated')
      GROUP BY r.run_id
      ORDER BY r.observation_end DESC, r.created_at DESC
    """,
    "wapor": """
      SELECT r.run_id, 'wapor'::text AS evidence_kind, r.source_period_start AS observation_start,
             r.source_period_end AS observation_end, r.native_resolution, r.status,
             json_build_object(
               'retained_tabias', count(w.tsird_tabia_id),
               'usable_tabias', count(w.tsird_tabia_id) FILTER (
                 WHERE w.quality_status='ok' AND w.coverage_pct >= 90
               )
             ) AS quality_summary,
             json_build_object(
               'seasonal_reference_candidate_only', r.seasonal_reference_candidate_only,
               'reference_period', CASE WHEN r.seasonal_reference_candidate_only
                 THEN '2018-2025 candidate reference' END
             ) AS provenance
      FROM tsird.drought_wapor_run r
      LEFT JOIN tsird.drought_tabia_wapor w USING (run_id)
      WHERE r.status IN ('development', 'degraded', 'validated')
      GROUP BY r.run_id
      ORDER BY r.source_period_end DESC, r.created_at DESC
    """,
}
EVIDENCE_FEATURE_SQL = {
    "rainfall": """SELECT json_build_object('type','FeatureCollection','features',coalesce(json_agg(json_build_object(
      'type','Feature','geometry',ST_AsGeoJSON(t.geometry)::json,'properties',json_build_object(
      'tsird_tabia_id', c.tsird_tabia_id, 'value', c.rainfall_mm, 'baseline_median_mm', c.baseline_median_mm,
      'percentile', c.percentile, 'condition_class', c.condition_class, 'coverage_pct', c.coverage_pct,
      'quality_status', c.quality_status))), '[]'::json)) AS payload
      FROM tsird.drought_tabia_rainfall_condition c JOIN tigray_tabias_ws t USING (tsird_tabia_id) WHERE c.run_id=$1""",
    "rapid": """SELECT json_build_object('type','FeatureCollection','features',coalesce(json_agg(json_build_object(
      'type','Feature','geometry',ST_AsGeoJSON(t.geometry)::json,'properties',json_build_object(
      'tsird_tabia_id', p.tsird_tabia_id, 'value', p.rainfall_mm, 'baseline_median_mm', p.baseline_median_mm,
      'percentile', p.provisional_percentile, 'comparison_status', p.comparison_status, 'coverage_pct', p.coverage_pct,
      'quality_status', p.quality_status))), '[]'::json)) AS payload
      FROM tsird.drought_tabia_preliminary_rainfall p JOIN tigray_tabias_ws t USING (tsird_tabia_id) WHERE p.run_id=$1""",
    "ndvi": """SELECT json_build_object('type','FeatureCollection','features',coalesce(json_agg(json_build_object(
      'type','Feature','geometry',ST_AsGeoJSON(t.geometry)::json,'properties',json_build_object(
      'tsird_tabia_id', n.tsird_tabia_id, 'value', n.ndvi_mean, 'coverage_pct', n.coverage_pct,
      'quality_status', n.quality_status, 'reference_median', reference.median_value,
      'reference_deviation_pct', CASE WHEN reference.median_value > 0 THEN 100 * (n.ndvi_mean-reference.median_value)/reference.median_value END,
      'reference_year_count', reference.valid_year_count, 'reference_status', CASE WHEN reference.valid_year_count IS NULL THEN 'unavailable' ELSE 'candidate_review_required' END))), '[]'::json)) AS payload
      FROM tsird.drought_tabia_ndvi n JOIN tsird.drought_ndvi_run r USING (run_id) JOIN tigray_tabias_ws t USING (tsird_tabia_id)
      LEFT JOIN LATERAL (
        SELECT count(*)::int AS valid_year_count, percentile_cont(0.5) WITHIN GROUP (ORDER BY n2.ndvi_mean) AS median_value
        FROM tsird.drought_tabia_ndvi n2 JOIN tsird.drought_ndvi_run r2 USING (run_id)
        WHERE n2.tsird_tabia_id=n.tsird_tabia_id AND EXTRACT(YEAR FROM r2.observation_end) BETWEEN 2018 AND 2025
          AND EXTRACT(MONTH FROM r2.observation_end)=EXTRACT(MONTH FROM r.observation_end)
          AND r2.status IN ('development','degraded','validated') AND (r2.seasonal_reference_candidate_only OR r2.notes LIKE 'Baseline pilot only%%')
          AND n2.quality_status='ok' AND n2.coverage_pct >= 90 AND n2.ndvi_mean IS NOT NULL
          AND (EXTRACT(YEAR FROM r.observation_end) NOT BETWEEN 2018 AND 2025 OR EXTRACT(YEAR FROM r2.observation_end) <> EXTRACT(YEAR FROM r.observation_end))
        HAVING count(*) >= 6
      ) reference ON true WHERE n.run_id=$1""",
    "swi": """SELECT json_build_object('type','FeatureCollection','features',coalesce(json_agg(json_build_object(
      'type','Feature','geometry',ST_AsGeoJSON(t.geometry)::json,'properties',json_build_object(
      'tsird_tabia_id', s.tsird_tabia_id, 'value', s.swi040_mean, 'coverage_pct', s.coverage_pct,
      'quality_status', s.quality_status))), '[]'::json)) AS payload
      FROM tsird.drought_tabia_swi s JOIN tigray_tabias_ws t USING (tsird_tabia_id) WHERE s.run_id=$1""",
    "lst": """SELECT json_build_object('type','FeatureCollection','features',coalesce(json_agg(json_build_object(
      'type','Feature','geometry',ST_AsGeoJSON(t.geometry)::json,'properties',json_build_object(
      'tsird_tabia_id', l.tsird_tabia_id, 'value', l.lst_c_mean, 'coverage_pct', l.coverage_pct,
      'quality_status', l.quality_status))), '[]'::json)) AS payload
      FROM tsird.drought_tabia_lst l JOIN tigray_tabias_ws t USING (tsird_tabia_id) WHERE l.run_id=$1""",
    "wapor": """SELECT json_build_object('type','FeatureCollection','features',coalesce(json_agg(json_build_object(
      'type','Feature','geometry',ST_AsGeoJSON(t.geometry)::json,'properties',json_build_object(
      'tsird_tabia_id', w.tsird_tabia_id, 'value', w.transpiration_mm, 'coverage_pct', w.coverage_pct,
      'quality_status', w.quality_status, 'reference_median', reference.median_value,
      'reference_deviation_pct', CASE WHEN reference.median_value > 0 THEN 100 * (w.transpiration_mm-reference.median_value)/reference.median_value END,
      'reference_year_count', reference.valid_year_count, 'reference_status', CASE WHEN reference.valid_year_count IS NULL THEN 'unavailable' ELSE 'candidate_review_required' END))), '[]'::json)) AS payload
      FROM tsird.drought_tabia_wapor w JOIN tsird.drought_wapor_run r USING (run_id) JOIN tigray_tabias_ws t USING (tsird_tabia_id)
      LEFT JOIN LATERAL (
        SELECT count(*)::int AS valid_year_count, percentile_cont(0.5) WITHIN GROUP (ORDER BY w2.transpiration_mm) AS median_value
        FROM tsird.drought_tabia_wapor w2 JOIN tsird.drought_wapor_run r2 USING (run_id)
        WHERE w2.tsird_tabia_id=w.tsird_tabia_id AND EXTRACT(YEAR FROM r2.source_period_end) BETWEEN 2018 AND 2025
          AND EXTRACT(MONTH FROM r2.source_period_end)=EXTRACT(MONTH FROM r.source_period_end)
          AND r2.status IN ('development','degraded','validated') AND (r2.seasonal_reference_candidate_only OR r2.notes LIKE 'Baseline pilot only%%')
          AND w2.quality_status='ok' AND w2.coverage_pct >= 90 AND w2.transpiration_mm IS NOT NULL
          AND (EXTRACT(YEAR FROM r.source_period_end) NOT BETWEEN 2018 AND 2025 OR EXTRACT(YEAR FROM r2.source_period_end) <> EXTRACT(YEAR FROM r.source_period_end))
        HAVING count(*) >= 6
      ) reference ON true WHERE w.run_id=$1""",
}

# Seasonal outlooks are provider-issued climate probabilities.  These queries
# intentionally contain no Tabia join: the platform may retain a native grid
# and an explicitly derived Woreda context, but never a fabricated Tabia
# forecast layer.
DROUGHT_SEASONAL_OUTLOOK_RUNS_SQL = """
  SELECT run_id, source_id, variable, source_product, source_version, issued_at,
         valid_from, valid_to, lead_start_months, lead_end_months,
         native_resolution, native_crs, geography_scope, source_url, status,
         quality_summary, provenance
  FROM tsird.drought_seasonal_outlook_run
  WHERE status NOT IN ('failed', 'superseded')
  ORDER BY
    CASE WHEN valid_from <= CURRENT_DATE AND valid_to >= CURRENT_DATE THEN 0
         WHEN valid_from > CURRENT_DATE THEN 1 ELSE 2 END,
    valid_from ASC, issued_at DESC
"""

DROUGHT_SEASONAL_OUTLOOK_FEATURE_SQL = """
  SELECT json_build_object('type', 'FeatureCollection', 'features',
    coalesce(json_agg(json_build_object(
      'type', 'Feature',
      'geometry', ST_AsGeoJSON(geometry)::json,
      'properties', json_build_object(
        'feature_id', feature_id,
        'representation', representation,
        'provider_area_id', provider_area_id,
        'woreda_gid', woreda_gid,
        'below_normal_probability', below_normal_probability,
        'near_normal_probability', near_normal_probability,
        'above_normal_probability', above_normal_probability,
        'coverage_pct', coverage_pct,
        'quality_status', quality_status
      )
    )), '[]'::json)
  ) AS payload
  FROM tsird.drought_seasonal_outlook_feature
  WHERE run_id = $1 AND representation = $2
"""

SEARCH_SQL = """
WITH q AS (SELECT trim($1) AS query),
woredas AS (
  SELECT
    'woreda' AS type,
    gid::text AS id,
    "WEREDA"    AS name_en,
    woreda_tig  AS name_ti,
    ARRAY[
      ST_XMin(ST_Envelope(geometry)),
      ST_YMin(ST_Envelope(geometry)),
      ST_XMax(ST_Envelope(geometry)),
      ST_YMax(ST_Envelope(geometry))
    ] AS bbox,
    CASE
      WHEN lower("WEREDA") = lower((SELECT query FROM q))
        OR lower(woreda_tig) = lower((SELECT query FROM q)) THEN 1
      WHEN lower("WEREDA") LIKE lower((SELECT query FROM q)) || '%'
        OR lower(woreda_tig) LIKE lower((SELECT query FROM q)) || '%' THEN 2
      ELSE 3
    END AS rank
  FROM tigray_woredas_ws
  WHERE "WEREDA" ILIKE '%' || (SELECT query FROM q) || '%'
     OR woreda_tig ILIKE '%' || (SELECT query FROM q) || '%'
),
tabias AS (
  SELECT
    'tabia' AS type,
    tsird_tabia_id AS id,
    "TABIA"    AS name_en,
    tabia_tig  AS name_ti,
    ARRAY[
      ST_XMin(ST_Envelope(geometry)),
      ST_YMin(ST_Envelope(geometry)),
      ST_XMax(ST_Envelope(geometry)),
      ST_YMax(ST_Envelope(geometry))
    ] AS bbox,
    CASE
      WHEN lower("TABIA") = lower((SELECT query FROM q))
        OR lower(tabia_tig) = lower((SELECT query FROM q)) THEN 1
      WHEN lower("TABIA") LIKE lower((SELECT query FROM q)) || '%'
        OR lower(tabia_tig) LIKE lower((SELECT query FROM q)) || '%' THEN 2
      ELSE 3
    END AS rank
  FROM tigray_tabias_ws
  WHERE "TABIA" ILIKE '%' || (SELECT query FROM q) || '%'
     OR tabia_tig ILIKE '%' || (SELECT query FROM q) || '%'
)
SELECT type, id, name_en, name_ti, bbox
FROM (SELECT * FROM woredas UNION ALL SELECT * FROM tabias) s
ORDER BY rank, name_en
LIMIT 15
"""

# This is intentionally limited to known TSIRD administrative boundaries. It
# supports map fit/highlight for an identified record, not generic data export.
BOUNDARY_SQL = {
    "tabia": """
      SELECT gid, tsird_tabia_id, "TABIA" AS name_en, tabia_tig AS name_ti,
        "WEREDA" AS parent_name_en,
        ARRAY[ST_XMin(ST_Envelope(geometry)), ST_YMin(ST_Envelope(geometry)),
              ST_XMax(ST_Envelope(geometry)), ST_YMax(ST_Envelope(geometry))] AS bbox,
        ST_AsGeoJSON(geometry)::json AS geometry
      FROM tigray_tabias_ws WHERE tsird_tabia_id = $1
    """,
    "woreda": """
      SELECT gid, "WEREDA" AS name_en, woreda_tig AS name_ti,
        NULL::text AS parent_name_en,
        ARRAY[ST_XMin(ST_Envelope(geometry)), ST_YMin(ST_Envelope(geometry)),
              ST_XMax(ST_Envelope(geometry)), ST_YMax(ST_Envelope(geometry))] AS bbox,
        ST_AsGeoJSON(geometry)::json AS geometry
      FROM tigray_woredas_ws WHERE gid = $1
    """,
}

# Development-only artifact route. It is intentionally separate from a future
# published-artifact endpoint so a browser can never mistake an in-review run
# for operational intelligence.
DROUGHT_DEVELOPMENT_OBSERVED_SQL = """
WITH latest_run AS (
  SELECT run_id, source_product, source_version, analysis_year, season_months,
         baseline_year_start, baseline_year_end, source_latest_month, status, notes
  FROM tsird.drought_rainfall_run
  WHERE status = 'development'
  -- Prefer the established seasonal product when several artifacts share the
  -- same latest source month.  This keeps the API aligned with the current
  -- MapServer layer; monthly runs remain available through /runs.
  ORDER BY source_latest_month DESC, cardinality(season_months) DESC, created_at DESC
  LIMIT 1
), artifact AS (
  SELECT artifact_id, native_resolution, geography_scope, quality_summary, provenance
  FROM tsird.drought_artifact_registry
  WHERE artifact_type = 'observed_rainfall' AND status = 'development'
    AND run_id = (SELECT run_id FROM latest_run)
)
SELECT
  (SELECT row_to_json(latest_run) FROM latest_run) AS run,
  (SELECT row_to_json(artifact) FROM artifact) AS artifact,
  COALESCE(json_agg(row_to_json(condition) ORDER BY condition.tabia_name_en)
    FILTER (WHERE condition.tsird_tabia_id IS NOT NULL), '[]'::json) AS conditions
FROM (
  SELECT c.tsird_tabia_id, t."TABIA" AS tabia_name_en, t."WEREDA" AS woreda_name_en,
         c.rainfall_mm, c.baseline_median_mm, c.percentile, c.condition_class,
         c.grid_cell_count, c.coverage_pct, c.quality_status
  FROM tsird.drought_tabia_rainfall_condition c
  JOIN latest_run r USING (run_id)
  JOIN tigray_tabias_ws t USING (tsird_tabia_id)
  ORDER BY t."TABIA"
  LIMIT $1
) condition
"""

# Historical runs are intentionally exposed separately from ``latest``.  A
# browser asking for the current development view must never accidentally
# receive a backfilled month merely because it was imported more recently.
DROUGHT_DEVELOPMENT_OBSERVED_RUNS_SQL = """
SELECT r.run_id, r.source_product, r.source_version, r.analysis_year,
       r.season_months, r.baseline_year_start, r.baseline_year_end,
       r.source_latest_month, r.status, r.notes, r.created_at,
       count(c.tsird_tabia_id)::integer AS record_count,
       count(c.tsird_tabia_id) FILTER (WHERE c.quality_status = 'ok')::integer AS usable_count
FROM tsird.drought_rainfall_run r
LEFT JOIN tsird.drought_tabia_rainfall_condition c USING (run_id)
WHERE r.status = 'development'
GROUP BY r.run_id
ORDER BY r.source_latest_month DESC, r.created_at DESC
LIMIT $1
"""

DROUGHT_DEVELOPMENT_OBSERVED_BY_RUN_SQL = """
WITH selected_run AS (
  SELECT run_id, source_product, source_version, analysis_year, season_months,
         baseline_year_start, baseline_year_end, source_latest_month, status, notes
  FROM tsird.drought_rainfall_run
  WHERE status = 'development' AND run_id = $1
  LIMIT 1
), artifact AS (
  SELECT artifact_id, native_resolution, geography_scope, quality_summary, provenance
  FROM tsird.drought_artifact_registry
  WHERE artifact_type = 'observed_rainfall' AND status = 'development'
    AND run_id = (SELECT run_id FROM selected_run)
)
SELECT
  (SELECT row_to_json(selected_run) FROM selected_run) AS run,
  (SELECT row_to_json(artifact) FROM artifact) AS artifact,
  COALESCE(json_agg(row_to_json(condition) ORDER BY condition.tabia_name_en)
    FILTER (WHERE condition.tsird_tabia_id IS NOT NULL), '[]'::json) AS conditions
FROM (
  SELECT c.tsird_tabia_id, t."TABIA" AS tabia_name_en, t."WEREDA" AS woreda_name_en,
         c.rainfall_mm, c.baseline_median_mm, c.percentile, c.condition_class,
         c.grid_cell_count, c.coverage_pct, c.quality_status
  FROM tsird.drought_tabia_rainfall_condition c
  JOIN selected_run r USING (run_id)
  JOIN tigray_tabias_ws t USING (tsird_tabia_id)
  ORDER BY t."TABIA"
  LIMIT $2
) condition
"""

DROUGHT_DEVELOPMENT_OBSERVED_GEOJSON_BY_RUN_SQL = """
WITH selected_run AS (
  SELECT run_id
  FROM tsird.drought_rainfall_run
  WHERE status = 'development' AND run_id = $1
  LIMIT 1
)
SELECT json_build_object(
  'type', 'FeatureCollection',
  'features', COALESCE(json_agg(json_build_object(
    'type', 'Feature',
    'id', c.tsird_tabia_id,
    'geometry', ST_AsGeoJSON(t.geometry)::json,
    'properties', json_build_object(
      'tsird_tabia_id', c.tsird_tabia_id,
      'tabia_name_en', t."TABIA",
      'woreda_name_en', t."WEREDA",
      'rainfall_mm', c.rainfall_mm,
      'baseline_median_mm', c.baseline_median_mm,
      'percentile', c.percentile,
      'condition_class', c.condition_class,
      'grid_cell_count', c.grid_cell_count,
      'coverage_pct', c.coverage_pct,
      'quality_status', c.quality_status
    )
  ) ORDER BY t."TABIA"), '[]'::json)
) AS feature_collection
FROM tsird.drought_tabia_rainfall_condition c
JOIN selected_run r USING (run_id)
JOIN tigray_tabias_ws t USING (tsird_tabia_id)
"""

DROUGHT_DEVELOPMENT_PRELIMINARY_SQL = """
WITH latest_run AS (
  SELECT run_id, source_product, period_start, period_end, pentad_count,
         source_latest_at, status, notes
  FROM tsird.drought_preliminary_rainfall_run
  WHERE status = 'development'
  ORDER BY period_end DESC, created_at DESC
  LIMIT 1
)
SELECT
  (SELECT row_to_json(latest_run) FROM latest_run) AS run,
  COALESCE(json_agg(row_to_json(summary) ORDER BY summary.tabia_name_en)
    FILTER (WHERE summary.tsird_tabia_id IS NOT NULL), '[]'::json) AS summaries
FROM (
  SELECT p.tsird_tabia_id, t."TABIA" AS tabia_name_en, t."WEREDA" AS woreda_name_en,
         p.rainfall_mm, p.baseline_median_mm, p.provisional_percentile,
         p.comparison_status, p.grid_cell_count, p.coverage_pct, p.quality_status
  FROM tsird.drought_tabia_preliminary_rainfall p
  JOIN latest_run r USING (run_id)
  JOIN tigray_tabias_ws t USING (tsird_tabia_id)
  ORDER BY t."TABIA"
  LIMIT $1
) summary
"""

DROUGHT_DEVELOPMENT_NDVI_SQL = """
WITH latest_run AS (
 SELECT run_id, source_product, observation_start, observation_end, native_resolution, status, notes
 FROM tsird.drought_ndvi_run ORDER BY observation_end DESC, created_at DESC LIMIT 1
)
SELECT (SELECT row_to_json(latest_run) FROM latest_run) AS run,
 COALESCE(json_agg(row_to_json(summary) ORDER BY summary.tabia_name_en) FILTER (WHERE summary.tsird_tabia_id IS NOT NULL), '[]'::json) AS summaries
FROM (SELECT n.tsird_tabia_id, t."TABIA" AS tabia_name_en, t."WEREDA" AS woreda_name_en,
 n.ndvi_mean, n.ndvi_median, n.valid_pixel_count, n.grid_cell_count, n.coverage_pct, n.qflag_nonzero_count, n.quality_status
 FROM tsird.drought_tabia_ndvi n JOIN latest_run r USING (run_id) JOIN tigray_tabias_ws t USING (tsird_tabia_id)
 ORDER BY t."TABIA" LIMIT $1) summary
"""

DROUGHT_DEVELOPMENT_SWI_SQL = """
WITH latest_run AS (
 SELECT run_id, source_product, observation_at AS observation_start, observation_at AS observation_end, native_resolution, status, notes
 FROM tsird.drought_swi_run ORDER BY observation_at DESC, created_at DESC LIMIT 1
)
SELECT (SELECT row_to_json(latest_run) FROM latest_run) AS run,
 COALESCE(json_agg(row_to_json(summary) ORDER BY summary.tabia_name_en) FILTER (WHERE summary.tsird_tabia_id IS NOT NULL), '[]'::json) AS summaries
FROM (SELECT s.tsird_tabia_id, t."TABIA" AS tabia_name_en, t."WEREDA" AS woreda_name_en,
 s.swi010_mean, s.swi040_mean, s.swi100_mean, s.qflag040_mean, s.valid_pixel_count, s.grid_cell_count, s.coverage_pct, s.quality_status
 FROM tsird.drought_tabia_swi s JOIN latest_run r USING (run_id) JOIN tigray_tabias_ws t USING (tsird_tabia_id)
 ORDER BY t."TABIA" LIMIT $1) summary
"""

DROUGHT_DEVELOPMENT_LST_SQL = """
WITH latest_run AS (
 SELECT run_id, source_product, observation_at AS observation_start, observation_at AS observation_end, native_resolution, status, notes
 FROM tsird.drought_lst_run ORDER BY observation_at DESC, created_at DESC LIMIT 1
)
SELECT (SELECT row_to_json(latest_run) FROM latest_run) AS run,
 COALESCE(json_agg(row_to_json(summary) ORDER BY summary.tabia_name_en) FILTER (WHERE summary.tsird_tabia_id IS NOT NULL), '[]'::json) AS summaries
FROM (SELECT l.tsird_tabia_id, t."TABIA" AS tabia_name_en, t."WEREDA" AS woreda_name_en, l.lst_c_mean, l.errorbar_c_mean, l.ppp_mean, l.qflag_mean, l.valid_pixel_count, l.grid_cell_count, l.coverage_pct, l.quality_status
 FROM tsird.drought_tabia_lst l JOIN latest_run r USING (run_id) JOIN tigray_tabias_ws t USING (tsird_tabia_id)
 ORDER BY t."TABIA" LIMIT $1) summary
"""

DROUGHT_DEVELOPMENT_WAPOR_SQL = """
WITH latest_run AS (
 SELECT run_id, source_id AS source_product, source_period_start, source_period_end, source_revision, native_resolution, status, notes
 FROM tsird.drought_wapor_run ORDER BY source_period_end DESC, created_at DESC LIMIT 1
)
SELECT (SELECT row_to_json(latest_run) FROM latest_run) AS run,
 COALESCE(json_agg(row_to_json(summary) ORDER BY summary.tabia_name_en) FILTER (WHERE summary.tsird_tabia_id IS NOT NULL), '[]'::json) AS summaries
FROM (SELECT w.tsird_tabia_id, t."TABIA" AS tabia_name_en, t."WEREDA" AS woreda_name_en,
 w.transpiration_mm, w.aeti_mm, w.valid_pixel_count, w.grid_cell_count, w.coverage_pct, w.quality_status
 FROM tsird.drought_tabia_wapor w JOIN latest_run r USING (run_id) JOIN tigray_tabias_ws t USING (tsird_tabia_id)
 ORDER BY t."TABIA" LIMIT $1) summary
"""

# Whitelisted per-Tabia evidence histories.  These intentionally return source
# timestamps and quality state with each value so the browser cannot draw a
# false continuous series across missing/degraded observations.
DROUGHT_HISTORY_SQL = {
    "rainfall": """
      SELECT r.run_id, r.source_latest_month::timestamptz AS observation_at, r.status,
             '0.05 degree CHIRPS grid, monthly rainfall total'::text AS native_resolution,
             c.rainfall_mm AS value, c.baseline_median_mm AS expected_median,
             c.percentile AS percentile, '1991–2020 CHIRPS monthly climatology'::text AS baseline_label,
             'ready'::text AS baseline_status, c.coverage_pct, c.quality_status
      FROM tsird.drought_tabia_rainfall_condition c JOIN tsird.drought_rainfall_run r USING (run_id)
      WHERE c.tsird_tabia_id = $1 AND r.status IN ('development', 'validated', 'published')
      ORDER BY r.source_latest_month
    """,
    "rapid": """
      SELECT r.run_id, r.period_end::timestamptz AS observation_at, r.status,
             '0.05 degree CHIRPS preliminary grid, six-pentad accumulation'::text AS native_resolution,
             p.rainfall_mm AS value, p.baseline_median_mm AS expected_median,
             p.provisional_percentile AS percentile, 'Stored final-rainfall comparison'::text AS baseline_label,
             CASE WHEN p.comparison_status = 'provisional_preliminary_vs_final' THEN 'provisional' ELSE 'unavailable' END AS baseline_status,
             p.coverage_pct, p.quality_status
      FROM tsird.drought_tabia_preliminary_rainfall p JOIN tsird.drought_preliminary_rainfall_run r USING (run_id)
      WHERE p.tsird_tabia_id = $1 AND r.status IN ('development', 'degraded', 'validated', 'published')
      ORDER BY r.period_end
    """,
    "ndvi": """
      SELECT r.run_id, r.observation_end AS observation_at, r.status, r.native_resolution,
             n.ndvi_mean AS value, reference.median_value AS expected_median, reference.percentile,
             CASE WHEN reference.valid_year_count IS NULL THEN 'Seasonal reference unavailable'
                  WHEN EXTRACT(YEAR FROM r.observation_end) BETWEEN 2018 AND 2025 THEN '2018–2025 same-calendar-month candidate reference; selected historical year excluded'
                  ELSE '2018–2025 same-calendar-month candidate reference' END AS baseline_label,
             CASE WHEN reference.valid_year_count IS NULL THEN 'unavailable' ELSE 'candidate_review_required' END AS baseline_status,
             n.coverage_pct, n.quality_status
      FROM tsird.drought_tabia_ndvi n JOIN tsird.drought_ndvi_run r USING (run_id)
      LEFT JOIN LATERAL (
        SELECT count(*)::int AS valid_year_count,
               percentile_cont(0.5) WITHIN GROUP (ORDER BY n2.ndvi_mean) AS median_value,
               100.0 * count(*) FILTER (WHERE n2.ndvi_mean <= n.ndvi_mean) / NULLIF(count(*), 0) AS percentile
        FROM tsird.drought_tabia_ndvi n2 JOIN tsird.drought_ndvi_run r2 USING (run_id)
        WHERE n2.tsird_tabia_id=n.tsird_tabia_id
          AND EXTRACT(YEAR FROM r2.observation_end) BETWEEN 2018 AND 2025
          AND EXTRACT(MONTH FROM r2.observation_end)=EXTRACT(MONTH FROM r.observation_end)
          AND r2.status IN ('development', 'degraded', 'validated')
          AND (r2.seasonal_reference_candidate_only OR r2.notes LIKE 'Baseline pilot only%%')
          AND n2.quality_status='ok' AND n2.coverage_pct >= 90 AND n2.ndvi_mean IS NOT NULL
          AND (EXTRACT(YEAR FROM r.observation_end) NOT BETWEEN 2018 AND 2025 OR EXTRACT(YEAR FROM r2.observation_end) <> EXTRACT(YEAR FROM r.observation_end))
        HAVING count(*) >= 6
      ) reference ON true
      WHERE n.tsird_tabia_id = $1 AND r.status IN ('development', 'degraded') ORDER BY r.observation_end
    """,
    "swi": """
      SELECT r.run_id, r.observation_at, r.status, r.native_resolution,
             s.swi040_mean AS value, NULL::numeric AS expected_median, NULL::numeric AS percentile,
             'Seasonal baseline not yet loaded'::text AS baseline_label, 'unavailable'::text AS baseline_status,
             s.coverage_pct, s.quality_status
      FROM tsird.drought_tabia_swi s JOIN tsird.drought_swi_run r USING (run_id)
      WHERE s.tsird_tabia_id = $1 AND r.status IN ('development', 'degraded') ORDER BY r.observation_at
    """,
    "lst": """
      SELECT r.run_id, r.observation_at, r.status, r.native_resolution,
             l.lst_c_mean AS value, NULL::numeric AS expected_median, NULL::numeric AS percentile,
             'Seasonal baseline not yet loaded'::text AS baseline_label, 'unavailable'::text AS baseline_status,
             l.coverage_pct, l.quality_status
      FROM tsird.drought_tabia_lst l JOIN tsird.drought_lst_run r USING (run_id)
      WHERE l.tsird_tabia_id = $1 AND r.status IN ('development', 'degraded') ORDER BY r.observation_at
    """,
    "wapor": """
      SELECT r.run_id, r.source_period_end::timestamptz AS observation_at, r.status, r.native_resolution,
             w.transpiration_mm AS value, reference.median_value AS expected_median, reference.percentile,
             CASE WHEN reference.valid_year_count IS NULL THEN 'Seasonal reference unavailable'
                  WHEN EXTRACT(YEAR FROM r.source_period_end) BETWEEN 2018 AND 2025 THEN '2018–2025 same-calendar-month candidate reference; selected historical year excluded'
                  ELSE '2018–2025 same-calendar-month candidate reference' END AS baseline_label,
             CASE WHEN reference.valid_year_count IS NULL THEN 'unavailable' ELSE 'candidate_review_required' END AS baseline_status,
             w.coverage_pct, w.quality_status
      FROM tsird.drought_tabia_wapor w JOIN tsird.drought_wapor_run r USING (run_id)
      LEFT JOIN LATERAL (
        SELECT count(*)::int AS valid_year_count,
               percentile_cont(0.5) WITHIN GROUP (ORDER BY w2.transpiration_mm) AS median_value,
               100.0 * count(*) FILTER (WHERE w2.transpiration_mm <= w.transpiration_mm) / NULLIF(count(*), 0) AS percentile
        FROM tsird.drought_tabia_wapor w2 JOIN tsird.drought_wapor_run r2 USING (run_id)
        WHERE w2.tsird_tabia_id=w.tsird_tabia_id
          AND EXTRACT(YEAR FROM r2.source_period_end) BETWEEN 2018 AND 2025
          AND EXTRACT(MONTH FROM r2.source_period_end)=EXTRACT(MONTH FROM r.source_period_end)
          AND r2.status IN ('development', 'degraded', 'validated')
          AND (r2.seasonal_reference_candidate_only OR r2.notes LIKE 'Baseline pilot only%%')
          AND w2.quality_status='ok' AND w2.coverage_pct >= 90 AND w2.transpiration_mm IS NOT NULL
          AND (EXTRACT(YEAR FROM r.source_period_end) NOT BETWEEN 2018 AND 2025 OR EXTRACT(YEAR FROM r2.source_period_end) <> EXTRACT(YEAR FROM r.source_period_end))
        HAVING count(*) >= 6
      ) reference ON true
      WHERE w.tsird_tabia_id = $1 AND r.status IN ('development', 'degraded') ORDER BY r.source_period_end
    """,
}

HISTORY_METADATA = {
    "rainfall": {"label": "Final monthly rainfall total", "unit": "mm", "source": "CHIRPS v3"},
    "rapid": {"label": "Rapid preliminary rainfall total", "unit": "mm", "source": "CHIRPS v3 preliminary"},
    "ndvi": {"label": "NDVI mean", "unit": "unitless", "source": "Copernicus CLMS NDVI v3"},
    "swi": {"label": "SWI-040 mean", "unit": "%", "source": "Copernicus CLMS SWI v4"},
    "lst": {"label": "LST mean", "unit": "°C", "source": "Copernicus CLMS LST v2"},
    "wapor": {"label": "Transpiration mean", "unit": "mm per dekad", "source": "FAO WaPOR v3 Level 2"},
}


def _read_approved_public_drought_release(
    release_root: Path = PUBLIC_DROUGHT_RELEASE_ROOT,
    allowed_states: set[str] | None = None,
):
    """Read the one publisher-selected, immutable public release.

    This deliberately supports only a pointer plus an approved manifest under
    the configured release root.  It never accepts a browser path, release ID
    or filesystem location, and it cannot expose development artifacts merely
    because they are present on a shared local mount.
    """
    allowed_states = allowed_states or {"approved"}
    pointer_path = release_root / "current.json"
    try:
        pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
        release_id = pointer.get("release_id")
        if not isinstance(release_id, str) or not PUBLIC_RELEASE_ID_PATTERN.fullmatch(release_id):
            raise ValueError("current release ID is invalid")
        root = release_root.resolve()
        release_dir = (root / release_id).resolve(strict=True)
        if release_dir.parent != root:
            raise ValueError("current release directory is outside the configured root")
        manifest = json.loads((release_dir / "manifest.json").read_text(encoding="utf-8"))
        if manifest.get("schema_version") != "tsird-drought-production-release/v1":
            raise ValueError("current release schema is unsupported")
        if manifest.get("release_id") != release_id or manifest.get("release_state") not in allowed_states:
            raise ValueError("current release state is not permitted for this public route")
        assets = manifest.get("assets")
        if not isinstance(assets, list):
            raise ValueError("current release assets are invalid")
        asset_map = {}
        for asset in assets:
            if not isinstance(asset, dict):
                raise ValueError("current release asset is invalid")
            asset_id = asset.get("asset_id")
            relative_path = asset.get("relative_path")
            if not isinstance(asset_id, str) or not isinstance(relative_path, str):
                raise ValueError("current release asset metadata is incomplete")
            if asset_id in asset_map:
                raise ValueError("current release has duplicate asset IDs")
            candidate = (release_dir / relative_path).resolve(strict=True)
            if candidate.parent != release_dir or not candidate.is_file():
                raise ValueError("current release asset path is unsafe or missing")
            asset_map[asset_id] = (asset, candidate)
        return pointer, manifest, asset_map
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="No approved public drought release is available")
    except (OSError, ValueError, json.JSONDecodeError):
        logging.exception("Public drought release read error")
        raise HTTPException(status_code=503, detail="Approved public drought release is unavailable")


@app.get("/drought/public/release")
async def public_drought_release():
    """Return redacted metadata for the selected approved public release only."""
    pointer, manifest, asset_map = _read_approved_public_drought_release()
    return {
        "schema_version": "tsird-drought-public-release.v1",
        "release_id": manifest["release_id"],
        "activated_at": pointer.get("activated_at"),
        "previous_release_id": pointer.get("previous_release_id"),
        "public_scope": manifest.get("public_scope"),
        "assets": [
            {
                "asset_id": asset_id,
                "kind": asset.get("kind"),
                "source": asset.get("source"),
                "source_observation_start": asset.get("source_observation_start"),
                "source_observation_end": asset.get("source_observation_end"),
                "retrieved_at": asset.get("retrieved_at"),
                "processing_version": asset.get("processing_version"),
                "quality_state": asset.get("quality_state"),
                "interpretation_boundary": asset.get("interpretation_boundary"),
                "url": f"/map/api/drought/public/release/assets/{asset_id}",
            }
            for asset_id, (asset, _) in asset_map.items()
        ],
    }


@app.get("/drought/public/release/assets/{asset_id}")
async def public_drought_release_asset(asset_id: str):
    """Serve an allow-listed JSON/GeoJSON asset from the approved release."""
    _, _, asset_map = _read_approved_public_drought_release()
    if asset_id not in asset_map:
        raise HTTPException(status_code=404, detail="Unknown public drought release asset")
    _, path = asset_map[asset_id]
    media_type = "application/geo+json" if path.suffix == ".geojson" else "application/json"
    return FileResponse(
        path,
        media_type=media_type,
        headers={"Cache-Control": "no-cache, max-age=0, must-revalidate"},
    )


@app.get("/drought/public/indicators")
async def public_drought_indicators_release():
    """Return the current auto-validated indicator package only.

    This intentionally has a distinct pointer/root from reviewed Priority
    Replay releases, so source-derived indicator refreshes cannot advance or
    replace a replay/model product.
    """
    pointer, manifest, asset_map = _read_approved_public_drought_release(
        PUBLIC_DROUGHT_INDICATOR_RELEASE_ROOT,
        {"auto-validated"},
    )
    if manifest.get("release_channel") != "indicator-evidence":
        raise HTTPException(status_code=503, detail="Indicator release channel is invalid")
    return {
        "schema_version": "tsird-drought-public-indicator-release.v1",
        "release_id": manifest["release_id"],
        "activated_at": pointer.get("activated_at"),
        "previous_release_id": pointer.get("previous_release_id"),
        "public_scope": manifest.get("public_scope"),
        "assets": [
            {
                "asset_id": asset_id,
                "kind": asset.get("kind"),
                "source": asset.get("source"),
                "source_observation_start": asset.get("source_observation_start"),
                "source_observation_end": asset.get("source_observation_end"),
                "retrieved_at": asset.get("retrieved_at"),
                "processing_version": asset.get("processing_version"),
                "quality_state": asset.get("quality_state"),
                "interpretation_boundary": asset.get("interpretation_boundary"),
                "url": f"/map/api/drought/public/indicators/assets/{asset_id}",
            }
            for asset_id, (asset, _) in asset_map.items()
        ],
    }


@app.get("/drought/public/indicators/assets/{asset_id}")
async def public_drought_indicator_release_asset(asset_id: str):
    """Serve an allow-listed asset from the automatic indicator package."""
    _, manifest, asset_map = _read_approved_public_drought_release(
        PUBLIC_DROUGHT_INDICATOR_RELEASE_ROOT,
        {"auto-validated"},
    )
    if manifest.get("release_channel") != "indicator-evidence" or asset_id not in asset_map:
        raise HTTPException(status_code=404, detail="Unknown public indicator-release asset")
    _, path = asset_map[asset_id]
    return FileResponse(
        path,
        media_type="application/geo+json" if path.suffix == ".geojson" else "application/json",
        headers={"Cache-Control": "no-cache, max-age=0, must-revalidate"},
    )


# These routes adapt only the approved release package to the shared Atlas
# dashboard's read-only display contracts. They never query development data,
# raw raster storage, n8n, or the local runner.
def _public_release_json(asset_id: str):
    _, _, asset_map = _read_approved_public_drought_release()
    record = asset_map.get(asset_id)
    if not record:
        raise HTTPException(status_code=404, detail="Approved public drought asset is unavailable")
    _, path = record
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        logging.exception("Approved public drought JSON asset read error")
        raise HTTPException(status_code=503, detail="Approved public drought asset is unreadable")


def _public_indicator_release_json(asset_id: str):
    """Read a JSON asset only from the automatic retained-indicator pointer."""
    _, _, asset_map = _read_approved_public_drought_release(
        PUBLIC_DROUGHT_INDICATOR_RELEASE_ROOT,
        {"auto-validated"},
    )
    record = asset_map.get(asset_id)
    if not record:
        raise HTTPException(status_code=404, detail="Automatic public indicator asset is unavailable")
    _, path = record
    if path.suffix.lower() != ".json":
        raise HTTPException(status_code=404, detail="Automatic public indicator asset is not JSON")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logging.exception("Automatic public drought indicator JSON asset read error")
        raise HTTPException(status_code=503, detail="Automatic public indicator asset is unreadable")


def _public_workspace_indicator(indicator: str):
    workspace = _public_indicator_release_json("drought-workspace-latest")
    indicators = workspace.get("indicators") if isinstance(workspace, dict) else None
    payload = indicators.get(indicator) if isinstance(indicators, dict) else None
    if not isinstance(payload, dict) or not isinstance(payload.get("run"), dict) or not isinstance(payload.get("summaries"), list):
        raise HTTPException(status_code=404, detail="Indicator is not included in the approved public release")
    return payload


def _public_dashboard_run(raw: dict, indicator: str) -> dict:
    period_end = raw.get("source_period_end") or raw.get("observation_end") or raw.get("period_end")
    analysis_year = raw.get("analysis_year")
    if not analysis_year and isinstance(period_end, str) and len(period_end) >= 4:
        analysis_year = int(period_end[:4])
    return {**raw, "run_id": raw.get("run_id") or f"public-{indicator}-latest", "status": raw.get("status") or "approved retained evidence", "analysis_year": analysis_year or 2026, "season_months": raw.get("season_months") or [], "source_latest_month": raw.get("source_latest_month") or period_end, "native_resolution": raw.get("native_resolution") or "Tabia summary", "baseline_year_start": raw.get("baseline_year_start") or 1991, "baseline_year_end": raw.get("baseline_year_end") or 2020}


def _public_quality_summary(rows: list[dict]) -> dict:
    quality_counts: dict[str, int] = {}
    class_counts: dict[str, int] = {}
    for row in rows:
        quality = str(row.get("quality_status") or "unavailable")
        quality_counts[quality] = quality_counts.get(quality, 0) + 1
        condition = str(row.get("condition_class") or "unavailable")
        class_counts[condition] = class_counts.get(condition, 0) + 1
    return {"quality_counts": quality_counts, "class_counts": class_counts}


@app.get("/drought/public/dashboard/overview")
async def public_drought_dashboard_overview():
    observed = _public_workspace_indicator("observed")
    areas = []
    for row in observed["summaries"][:3]:
        if not isinstance(row, dict) or not isinstance(row.get("tsird_tabia_id"), str) or not isinstance(row.get("tabia_name_en"), str):
            continue
        boundary = {"type": "tabia", "id": row["tsird_tabia_id"], "label": row["tabia_name_en"]}
        areas.append({"id": row["tsird_tabia_id"], "name_en": row["tabia_name_en"], "name_ti": "", "context_en": row.get("woreda_name_en") or "Tigray", "observed": {"boundary": boundary}, "vulnerability": {"boundary": boundary}})
    return {"schema_version": "tsird-public-drought-dashboard/v1", "status": "approved_release", "title": "TSIRD Drought Intelligence", "geographic_note": "Approved retained evidence workspace. Indicators remain separate and exploratory; this page is not an official forecast, food-security classification, allocation recommendation, or operational decision product.", "sources": [{"id": "approved-release", "label": "Approved retained evidence", "role": "evidence", "provider": "TSIRD", "resolution": "Tabia summaries", "note": "Released evidence is read-only in production."}], "areas": areas}


@app.get("/drought/public/dashboard/indicator/{indicator}")
async def public_drought_dashboard_indicator(indicator: str):
    if indicator not in {"observed", "rapid", "vegetation", "soil_water", "thermal", "water_use"}:
        raise HTTPException(status_code=404, detail="Unknown public dashboard indicator")
    payload = _public_workspace_indicator(indicator)
    rows = [row for row in payload["summaries"] if isinstance(row, dict)]
    run = _public_dashboard_run(payload["run"], indicator)
    if indicator == "observed":
        return {"schema_version": "tsird-public-observed-rainfall/v1", "environment": "approved_release", "run": run, "artifact": {"native_resolution": run["native_resolution"], "quality_summary": _public_quality_summary(rows)}, "conditions": rows}
    return {"schema_version": f"tsird-public-{indicator}/v1", "environment": "approved_release", "run": run, "summaries": rows}


@app.get("/drought/public/dashboard/observed-rainfall/runs")
async def public_drought_dashboard_observed_runs():
    return {"schema_version": "tsird-public-observed-runs/v1", "runs": []}


@app.get("/drought/public/dashboard/evidence/{indicator}/runs")
async def public_drought_dashboard_evidence_runs(indicator: str):
    aliases = {"rainfall": "observed", "rapid": "rapid", "ndvi": "vegetation", "swi": "soil_water", "lst": "thermal", "wapor": "water_use"}
    release_indicator = aliases.get(indicator)
    if not release_indicator:
        raise HTTPException(status_code=404, detail="Unknown public evidence indicator")
    payload = _public_workspace_indicator(release_indicator)
    return {"schema_version": "tsird-public-evidence-runs/v1", "runs": [_public_dashboard_run(payload["run"], release_indicator)]}


@app.get("/drought/public/dashboard/history/{indicator}/{tabia_id}")
async def public_drought_dashboard_history(indicator: str, tabia_id: str):
    fields = {
        "rainfall": ("observed", "rainfall_mm", "Final rainfall", "mm"),
        "rapid": ("rapid", "rainfall_mm", "Rapid rainfall", "mm"),
        "ndvi": ("vegetation", "ndvi_mean", "Vegetation", "NDVI"),
        "swi": ("soil_water", "swi040_mean", "Soil water", "%"),
        "lst": ("thermal", "lst_c_mean", "Land-surface temperature", "°C"),
        "wapor": ("water_use", "transpiration_mm", "Crop water use", "mm/day"),
    }
    detail = fields.get(indicator)
    if not detail:
        raise HTTPException(status_code=404, detail="Unknown public evidence indicator")
    release_indicator, value_field, label, unit = detail
    payload = _public_workspace_indicator(release_indicator)
    row = next((item for item in payload["summaries"] if isinstance(item, dict) and item.get("tsird_tabia_id") == tabia_id), None)
    if not row:
        raise HTTPException(status_code=404, detail="Tabia is not included in the approved release")
    run = _public_dashboard_run(payload["run"], release_indicator)
    baseline = row.get("baseline_median_mm") if indicator == "rainfall" else None
    point = {"run_id": run["run_id"], "observation_at": run.get("observation_end") or run.get("source_period_end") or run.get("period_end") or "not recorded", "value": row.get(value_field), "expected_median": baseline, "percentile": row.get("percentile"), "baseline_status": "available" if baseline is not None else "unavailable", "baseline_label": "CHIRPS 1991–2020 reference" if baseline is not None else "Not included in this release", "quality_status": row.get("quality_status") or "unavailable", "native_resolution": run["native_resolution"], "status": run["status"]}
    return {"schema_version": "tsird-public-evidence-history/v1", "environment": "approved_release", "indicator": indicator, "metadata": {"label": label, "unit": unit}, "tabia": {"tabia_name_en": row.get("tabia_name_en") or "Tabia", "woreda_name_en": row.get("woreda_name_en") or "Tigray"}, "points": [point]}


@app.get("/drought/public/dashboard/priority/replays")
async def public_drought_dashboard_priority_replays():
    return _public_release_json("priority-replay-summary")


@app.get("/drought/public/dashboard/priority/previews")
async def public_drought_dashboard_priority_previews():
    """The approved release exposes retained replay snapshots, not draft previews."""
    return {"previews": []}


@app.get("/drought/public/dashboard/geometry")
async def public_drought_dashboard_geometry():
    index = _public_release_json("priority-replay-summary")
    replay = next((item for item in index.get("replays", []) if isinstance(item, dict) and isinstance(item.get("asset_id"), str)), None)
    if not replay:
        raise HTTPException(status_code=404, detail="Approved public Tabia geometry is unavailable")
    return _public_release_json(replay["asset_id"])


@app.get("/drought/public/dashboard/priority/replays/{snapshot_id}/features")
async def public_drought_dashboard_priority_replay_features(snapshot_id: str):
    index = _public_release_json("priority-replay-summary")
    replay = next((item for item in index.get("replays", []) if isinstance(item, dict) and item.get("snapshot_id") == snapshot_id), None)
    if not replay or not isinstance(replay.get("asset_id"), str):
        raise HTTPException(status_code=404, detail="Approved public replay snapshot is unavailable")
    return _public_release_json(replay["asset_id"])


@app.get("/drought/public/dashboard/fews-net/runs")
async def public_drought_dashboard_fews_runs():
    return _public_release_json("fews-net-context-index")


@app.get("/drought/public/dashboard/fews-net/runs/{run_id}/features")
async def public_drought_dashboard_fews_features(run_id: str):
    index = _public_release_json("fews-net-context-index")
    run = next((item for item in index.get("runs", []) if isinstance(item, dict) and item.get("run_id") == run_id), None)
    if not run or not isinstance(run.get("asset_id"), str):
        raise HTTPException(status_code=404, detail="Approved provider context issue is unavailable")
    return _public_release_json(run["asset_id"])


@app.get("/drought/public/dashboard/model-configuration")
async def public_drought_dashboard_model_configuration():
    return {"schema_version": "tsird-public-model-information/v1", "configuration": {"version": "read-only", "configuration": {"factors": []}}, "editing_available": False, "selection_note": "Production presents retained replay evidence only. Configuration editing and activation remain in development."}


@app.get("/drought/public/dashboard/model-readiness")
async def public_drought_dashboard_model_readiness():
    return {"schema_version": "tsird-public-model-readiness/v1", "status": "not_ready", "decision": {"status": "not-ready"}, "selection_note": "Retrospective evidence review only; production cannot score, forecast, publish or activate a model."}


@app.get("/drought/public/dashboard/seasonal-outlook/active")
async def public_drought_dashboard_outlook_active(variable: str = Query("seasonal_rainfall")):
    return {"schema_version": "tsird-public-seasonal-outlook/v1", "available": False, "variable": variable, "reason": "No reviewed seasonal outlook is included in this approved evidence release."}


@app.get("/drought/public/dashboard/seasonal-outlook/runs")
async def public_drought_dashboard_outlook_runs(variable: str = Query("seasonal_rainfall")):
    return {"schema_version": "tsird-public-seasonal-outlook/v1", "variable": variable, "runs": []}


@app.get("/gazetteer")
async def gazetteer(q: str = Query(..., min_length=1, max_length=100)):
    try:
        conn = await asyncpg.connect(DB_DSN)
        rows = await conn.fetch(SEARCH_SQL, q.strip())
        await conn.close()
        results = []
        for row in rows:
            bbox = list(row["bbox"]) if row["bbox"] else None
            results.append({
                "type": row["type"],
                "id": row["id"],
                "name_en": row["name_en"] or "",
                "name_ti": row["name_ti"] or "",
                "bbox": bbox
            })
        return results
    except Exception as e:
        import logging
        logging.error(f"Gazetteer query error: {e}")
        return []

@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/drought/development/control")
async def drought_development_control():
    """Proxy a redacted local runner snapshot through the same-origin API."""
    def read_control():
        with urllib.request.urlopen(DROUGHT_RUNNER_CONTROL_URL, timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))
    try:
        return await asyncio.to_thread(read_control)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        raise HTTPException(status_code=503, detail="Local drought control service unavailable")


@app.get("/drought/development/model-readiness")
async def drought_development_model_readiness():
    """Proxy the redacted, read-only seasonal-stress evidence gate."""
    def read_readiness():
        with urllib.request.urlopen(DROUGHT_RUNNER_READINESS_URL, timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))
    try:
        return await asyncio.to_thread(read_readiness)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        raise HTTPException(status_code=503, detail="Local model-readiness service unavailable")


@app.get("/drought/development/priority/model-configuration")
async def drought_development_priority_model_configuration():
    """Return the active local draft definition used by Priority Review."""
    try:
        conn = await asyncpg.connect(DB_DSN)
        try:
            row = await conn.fetchrow("""
                SELECT configuration_id, model_name, version, status, active_for_review, purpose,
                       geography_scope, horizon_months, configuration, rationale,
                       created_at, reviewed_by, reviewed_at, published_by, published_at
                FROM tsird.drought_priority_model_configuration
                WHERE status IN ('draft', 'published')
                ORDER BY active_for_review DESC, CASE status WHEN 'published' THEN 0 ELSE 1 END,
                         version DESC, created_at DESC
                LIMIT 1
            """)
        finally:
            await conn.close()
    except Exception:
        logging.exception("Development priority-model configuration query error")
        raise HTTPException(status_code=503, detail="Development priority model configuration unavailable")
    if not row:
        raise HTTPException(status_code=404, detail="No development priority model configuration is available")
    configuration = dict(row)
    if isinstance(configuration.get("configuration"), str):
        configuration["configuration"] = json.loads(configuration["configuration"])
    return {
        "schema_version": "tsird-seasonal-agricultural-priority-model.v1",
        "environment": "development",
        "read_only": False,
        "editing_available": True,
        "configuration": configuration,
        "selection_note": "This is the local active draft definition for Priority Review. Saving creates a new version; it does not publish a priority score or food-security classification.",
    }


@app.get("/drought/development/priority/scenario-laboratory/cases")
async def drought_development_priority_scenario_laboratory_cases():
    """Return only the documented, review-only August 2026 discussion cases.

    This endpoint intentionally has no write path and no score/class field. It
    gives the Model Studio laboratory a bounded evidence packet for exploring
    transparent assumptions without changing Priority Replay.
    """
    case_ids = [case_id for _, case_id in SCENARIO_LAB_CASES]
    try:
        conn = await asyncpg.connect(DB_DSN)
        try:
            payload = await conn.fetchval(SCENARIO_LAB_CASE_SQL, case_ids)
        finally:
            await conn.close()
    except Exception:
        logging.exception("Scenario laboratory case query error")
        raise HTTPException(status_code=503, detail="Scenario laboratory evidence is unavailable")
    decoded = json.loads(payload) if isinstance(payload, str) else payload
    cases = (decoded or {}).get("cases", [])
    for case, (group, _) in zip(cases, SCENARIO_LAB_CASES):
        case["review_group"] = group
    return {
        "schema_version": "tsird-candidate-reference-scenario-laboratory.v1",
        "environment": "development",
        "snapshot": "August 2026 retained evidence",
        "reference": "2018-2025 candidate same-calendar-month reference",
        "selection_note": "A purposefully selected plausibility sample, not a representative estimate or priority result.",
        "safeguard": "Sliders alter only a client-side discussion signal. They do not save, calculate Priority Replay, forecast, classify food security, or recommend allocation.",
        "cases": cases,
    }


@app.post("/drought/development/priority/model-configuration")
async def save_drought_development_priority_model_configuration(
    payload: dict = Body(...),
):
    """Save a versioned local-development configuration for Priority Review.

    The browser may save only a bounded, transparent rule matrix.  This route
    never publishes a decision product and is intentionally local-development
    only until real administrator authentication is introduced.
    """
    configuration = payload.get("configuration")
    if not isinstance(configuration, dict):
        raise HTTPException(status_code=422, detail="configuration must be an object")
    profiles = configuration.get("monthly_profiles")
    factors = configuration.get("factors")
    rules = configuration.get("priority_rules")
    if not isinstance(profiles, list) or len(profiles) != 12:
        raise HTTPException(status_code=422, detail="configuration requires 12 monthly profiles")
    if not isinstance(factors, list) or not factors or not isinstance(rules, list) or not rules:
        raise HTTPException(status_code=422, detail="configuration requires factors and priority rules")
    if len(factors) > 16 or len(rules) > 12:
        raise HTTPException(status_code=422, detail="configuration matrix is too large")
    activate = bool(payload.get("activate_for_review", True))
    rationale = str(payload.get("rationale") or "Local Model Studio draft; thresholds require practitioner review.").strip()[:2000]
    purpose = str(payload.get("purpose") or "Transparent seasonal agricultural-stress and response-planning aid; not a food-security classification.").strip()[:1000]
    try:
        conn = await asyncpg.connect(DB_DSN)
        try:
            async with conn.transaction():
                version = await conn.fetchval("""
                    SELECT coalesce(max(version), 0) + 1
                    FROM tsird.drought_priority_model_configuration
                    WHERE model_name = 'Seasonal Agricultural Stress & Response Priority'
                """)
                configuration_id = f"sarsrp-v0-1-draft-{version}"
                if activate:
                    await conn.execute("UPDATE tsird.drought_priority_model_configuration SET active_for_review = false WHERE active_for_review")
                await conn.execute("""
                    INSERT INTO tsird.drought_priority_model_configuration
                      (configuration_id, model_name, version, status, purpose, geography_scope,
                       horizon_months, configuration, rationale, created_by, active_for_review)
                    VALUES ($1, 'Seasonal Agricultural Stress & Response Priority', $2, 'draft',
                            $3, 'tabia_with_woreda_rollup', $4, $5::jsonb, $6,
                            'local-model-studio', $7)
                """, configuration_id, version, purpose, int(configuration.get("horizon_months", 3)),
                     json.dumps(configuration), rationale, activate)
        finally:
            await conn.close()
    except HTTPException:
        raise
    except Exception:
        logging.exception("Development priority-model configuration save error")
        raise HTTPException(status_code=503, detail="Development priority model configuration could not be saved")
    return {"saved": True, "configuration_id": configuration_id, "version": version,
            "active_for_review": activate,
            "next_step": "The next priority-runner job will read this active draft; saving alone does not calculate or publish a map."}


@app.get("/drought/development/priority/calibration-previews")
async def drought_development_priority_calibration_previews():
    """List aggregate, draft-only historical calibration previews.

    The endpoint returns no priority score or individual Tabia results. It is a
    compact review inventory for the Priority workspace and makes the
    no-forecast/no-publication status explicit.
    """
    try:
        conn = await asyncpg.connect(DB_DSN)
        try:
            rows = await conn.fetch("""
                SELECT s.snapshot_id, r.source_latest_month,
                       count(a.tsird_tabia_id)::integer AS tabias,
                       count(*) FILTER (WHERE a.evidence_state = 'eligible_for_review')::integer AS eligible_for_review,
                       count(*) FILTER (WHERE a.rainfall_band = 'very_low')::integer AS very_low,
                       count(*) FILTER (WHERE a.rainfall_band = 'low')::integer AS low,
                       count(*) FILTER (WHERE a.rainfall_band = 'watch')::integer AS watch
                FROM tsird.drought_priority_snapshot s
                JOIN tsird.drought_rainfall_run r ON r.run_id = s.source_run_ids ->> 'rainfall'
                JOIN tsird.drought_priority_tabia_assessment a ON a.snapshot_id = s.snapshot_id
                WHERE s.status = 'draft'
                  AND s.decision_kind = 'observed_stress_response_readiness'
                  AND a.rationale ->> 'kind' = 'historical_calibration_preview'
                GROUP BY s.snapshot_id, r.source_latest_month
                ORDER BY r.source_latest_month DESC
            """)
        finally:
            await conn.close()
    except Exception:
        logging.exception("Development priority calibration-preview query error")
        raise HTTPException(status_code=503, detail="Development priority calibration previews unavailable")
    return {
        "schema_version": "tsird-seasonal-agricultural-priority-calibration-preview.v1",
        "environment": "development",
        "read_only": True,
        "selection_note": "Historical calibration previews use retained evidence only. They are not as-issued forecasts, priority scores, or published decision products.",
        "previews": [dict(row) for row in rows],
    }


@app.get("/drought/development/priority/historical-replays")
async def drought_development_priority_historical_replays():
    """List draft-only, retained-evidence historical priority replays."""
    try:
        conn = await asyncpg.connect(DB_DSN)
        try:
            rows = await conn.fetch("""
                SELECT s.snapshot_id, s.configuration_id, c.version AS configuration_version,
                       r.source_latest_month,
                       count(a.tsird_tabia_id)::integer AS tabias,
                       count(*) FILTER (WHERE a.priority_class = 'critical')::integer AS critical,
                       count(*) FILTER (WHERE a.priority_class = 'high')::integer AS high,
                       count(*) FILTER (WHERE a.priority_class = 'moderate')::integer AS moderate,
                       count(*) FILTER (WHERE a.priority_class = 'watch')::integer AS watch,
                       count(*) FILTER (WHERE a.priority_class = 'insufficient_evidence')::integer AS insufficient_evidence
                FROM tsird.drought_priority_snapshot s
                JOIN tsird.drought_priority_model_configuration c ON c.configuration_id = s.configuration_id
                JOIN tsird.drought_rainfall_run r ON r.run_id = s.source_run_ids ->> 'rainfall'
                JOIN tsird.drought_priority_tabia_assessment a ON a.snapshot_id = s.snapshot_id
                WHERE s.status = 'draft' AND a.assessment_kind = 'historical_priority_replay'
                GROUP BY s.snapshot_id, s.configuration_id, c.version, r.source_latest_month
                ORDER BY r.source_latest_month DESC
            """)
        finally:
            await conn.close()
    except Exception:
        logging.exception("Development priority replay query error")
        raise HTTPException(status_code=503, detail="Development priority replays unavailable")
    return {
        "schema_version": "tsird-seasonal-agricultural-priority-replay.v1",
        "environment": "development", "read_only": True,
        "selection_note": "Historical replays apply the active local draft to retained evidence. They are not as-issued forecasts or published decision products.",
        "replays": [dict(row) for row in rows],
    }


@app.get("/drought/development/priority/historical-replays/{snapshot_id}/features")
async def drought_development_priority_historical_replay_features(snapshot_id: str):
    """Return one draft replay as explainable Tabia GeoJSON, never a forecast."""
    try:
        conn = await asyncpg.connect(DB_DSN)
        try:
            payload = await conn.fetchval("""
                SELECT json_build_object('type', 'FeatureCollection', 'features',
                  coalesce(json_agg(json_build_object(
                    'type', 'Feature', 'geometry', ST_AsGeoJSON(t.geometry)::json,
                    'properties', json_build_object(
                      'tsird_tabia_id', a.tsird_tabia_id, 'tabia_name_en', t."TABIA", 'woreda_name_en', t."WEREDA",
                      'priority_class', a.priority_class, 'priority_rank', a.priority_rank,
                      'planning_action', a.planning_action, 'triggered_rules', a.triggered_rules,
                      'rainfall_percentile', a.rainfall_percentile, 'rainfall_mm', a.rainfall_mm,
                      'baseline_median_mm', a.rainfall_baseline_median_mm, 'population_decile', a.population_decile,
                      'cropland_decile', a.cropland_decile, 'accessibility_context', a.road_context,
                      'evidence_state', a.evidence_state, 'input_quality', a.input_quality
                    )) ORDER BY t."TABIA"), '[]'::json))
                FROM tsird.drought_priority_tabia_assessment a
                JOIN tsird.drought_priority_snapshot s ON s.snapshot_id = a.snapshot_id
                JOIN tigray_tabias_ws t USING (tsird_tabia_id)
                WHERE a.snapshot_id = $1 AND s.status = 'draft'
                  AND a.assessment_kind = 'historical_priority_replay'
            """, snapshot_id)
        finally:
            await conn.close()
    except Exception:
        logging.exception("Development priority replay feature query error")
        raise HTTPException(status_code=503, detail="Development priority replay unavailable")
    decoded = json.loads(payload) if isinstance(payload, str) else payload
    if not decoded or not decoded.get("features"):
        raise HTTPException(status_code=404, detail="Development priority replay unavailable")
    return {
        "schema_version": "tsird-seasonal-agricultural-priority-replay.v1", "environment": "development",
        "snapshot_kind": "historical_priority_replay",
        "selection_note": "Draft historical planning replay using retained evidence and an active Model Studio definition; not a forecast or published decision.",
        **decoded,
    }


@app.get("/drought/development/priority/calibration-previews/{snapshot_id}/features")
async def drought_development_priority_calibration_preview_features(snapshot_id: str):
    """Return one draft calibration preview as Tabia GeoJSON, never as a score."""
    try:
        conn = await asyncpg.connect(DB_DSN)
        try:
            payload = await conn.fetchval("""
                SELECT json_build_object('type', 'FeatureCollection', 'features',
                  coalesce(json_agg(json_build_object(
                    'type', 'Feature', 'geometry', ST_AsGeoJSON(t.geometry)::json,
                    'properties', json_build_object(
                      'tsird_tabia_id', a.tsird_tabia_id, 'tabia_name_en', t."TABIA",
                      'woreda_name_en', t."WEREDA", 'rainfall_band', a.rainfall_band,
                      'rainfall_percentile', a.rainfall_percentile, 'rainfall_mm', a.rainfall_mm,
                      'baseline_median_mm', a.rainfall_baseline_median_mm,
                      'population_decile', a.population_decile, 'cropland_decile', a.cropland_decile,
                      'road_context', a.road_context, 'evidence_state', a.evidence_state
                    )) ORDER BY t."TABIA"), '[]'::json))
                FROM tsird.drought_priority_tabia_assessment a
                JOIN tsird.drought_priority_snapshot s ON s.snapshot_id = a.snapshot_id
                JOIN tigray_tabias_ws t USING (tsird_tabia_id)
                WHERE a.snapshot_id = $1 AND s.status = 'draft'
                  AND a.rationale ->> 'kind' = 'historical_calibration_preview'
            """, snapshot_id)
        finally:
            await conn.close()
    except Exception:
        logging.exception("Development priority calibration-preview feature query error")
        raise HTTPException(status_code=503, detail="Development priority calibration preview unavailable")
    decoded = json.loads(payload) if isinstance(payload, str) else payload
    if not decoded or not decoded.get("features"):
        raise HTTPException(status_code=404, detail="Development priority calibration preview unavailable")
    return {
        "schema_version": "tsird-seasonal-agricultural-priority-calibration-preview.v1",
        "environment": "development",
        "snapshot_kind": "historical_calibration_preview",
        "selection_note": "Rainfall percentile calibration evidence with separate exposure/road context; not a priority score or forecast.",
        **decoded,
    }


async def _evidence_rows(source_key: str, run_id: str | None = None):
    """Return catalogue-only metadata for one allow-listed evidence source."""
    source_id = EVIDENCE_RASTER_SOURCES.get(source_key)
    if not source_id:
        raise HTTPException(status_code=404, detail="Unknown development evidence source")
    query = """
      SELECT run_id, evidence_kind, observation_start, observation_end,
             native_resolution, status, quality_summary, provenance, raster_paths
      FROM tsird.drought_evidence_raster
      WHERE source_id = $1
    """
    values = [source_id]
    if run_id is not None:
        query += " AND run_id = $2"
        values.append(run_id)
    query += " ORDER BY observation_end DESC, created_at DESC"
    try:
        conn = await asyncpg.connect(DB_DSN)
        try:
            return await conn.fetch(query, *values)
        finally:
            await conn.close()
    except HTTPException:
        raise
    except Exception:
        logging.exception("Development evidence catalogue query error")
        raise HTTPException(status_code=503, detail="Development evidence catalogue is unavailable")


async def _historical_tabia_rows(source_key: str, run_id: str | None = None):
    """Return bounded NDVI/WaPOR history metadata, including candidate runs."""
    query = HISTORICAL_TABIA_RUN_SQL.get(source_key)
    if not query:
        return None
    if run_id is not None:
        # Wrap the fixed query rather than interpolating browser input into it.
        query = f"SELECT * FROM ({query}) retained_history WHERE run_id = $1"
    try:
        conn = await asyncpg.connect(DB_DSN)
        try:
            return await conn.fetch(query, run_id) if run_id is not None else await conn.fetch(query)
        finally:
            await conn.close()
    except Exception:
        logging.exception("Development Tabia history query error")
        raise HTTPException(status_code=503, detail="Development evidence history is unavailable")


def _decode_catalogue_value(value):
    return json.loads(value) if isinstance(value, str) else value


def _catalogue_record(source_key: str, row):
    """Serialize only non-sensitive catalogue fields and a fixed raster URL."""
    return {
        "run_id": row["run_id"],
        "evidence_kind": row["evidence_kind"],
        "observation_start": row["observation_start"].isoformat(),
        "observation_end": row["observation_end"].isoformat(),
        "native_resolution": row["native_resolution"],
        "status": row["status"],
        "quality_summary": _decode_catalogue_value(row["quality_summary"]),
        "provenance": _decode_catalogue_value(row["provenance"]),
        "native_raster_url": f"/map/api/drought/development/evidence/{source_key}/runs/{row['run_id']}/raster/primary",
    }


def _historical_tabia_record(row):
    """Serialize a source-run history record without exposing raster paths."""
    return {
        "run_id": row["run_id"],
        "evidence_kind": row["evidence_kind"],
        "observation_start": row["observation_start"].isoformat(),
        "observation_end": row["observation_end"].isoformat(),
        "native_resolution": row["native_resolution"],
        "status": row["status"],
        "quality_summary": _decode_catalogue_value(row["quality_summary"]),
        "provenance": _decode_catalogue_value(row["provenance"]),
        # Candidate history has no generic raster-publication record. The
        # supported product is its Tabia summary, not a raw-raster download.
        "native_raster_url": None,
    }


@app.get("/drought/development/evidence/{source_key}/runs")
async def development_evidence_runs(source_key: str):
    """List retained historical native-raster records without source paths."""
    historical_rows = await _historical_tabia_rows(source_key)
    rows = historical_rows if historical_rows is not None else await _evidence_rows(source_key)
    return {
        "schema_version": "tsird-drought-evidence-raster-catalogue.v1",
        "environment": "development",
        "selection_note": "Retained provider evidence, not a forecast, drought class, or priority product.",
        "runs": [
            _historical_tabia_record(row) if historical_rows is not None else _catalogue_record(source_key, row)
            for row in rows
        ],
    }


@app.get("/drought/development/evidence/{source_key}/runs/{run_id}/raster/{role}")
async def development_evidence_raster(source_key: str, run_id: str, role: str):
    """Serve one catalogue-addressed retained raster from the local read-only mount."""
    if role not in {"primary", "aeti"} or (role == "aeti" and source_key != "wapor"):
        raise HTTPException(status_code=404, detail="Unknown development evidence raster role")
    rows = await _evidence_rows(source_key, run_id)
    if not rows:
        raise HTTPException(status_code=404, detail="Development evidence raster is unavailable")
    paths = _decode_catalogue_value(rows[0]["raster_paths"])
    candidate = Path((paths or {}).get(role, ""))
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(EVIDENCE_DATA_ROOT.resolve(strict=True))
    except (FileNotFoundError, RuntimeError, ValueError):
        # Do not expose host paths or implementation details.
        raise HTTPException(status_code=404, detail="Development evidence raster is unavailable")
    if resolved.suffix.lower() not in {".tif", ".tiff"}:
        raise HTTPException(status_code=404, detail="Development evidence raster is unavailable")
    return FileResponse(resolved, media_type="image/tiff", filename=f"{source_key}-{run_id}.tif")


@app.get("/drought/development/evidence/{source_key}/runs/{run_id}/features")
async def development_evidence_features(source_key: str, run_id: str):
    """Return one retained Tabia-average snapshot as bounded GeoJSON."""
    if source_key not in EVIDENCE_FEATURE_SQL:
        raise HTTPException(status_code=404, detail="Unknown development evidence source")
    # Candidate NDVI/WaPOR history is intentionally not a generic raster
    # catalogue publication.  Both paths remain fixed source allow-lists and
    # return only the pre-aggregated Tabia summary geometry.
    historical_rows = await _historical_tabia_rows(source_key, run_id)
    catalogue_rows = historical_rows if historical_rows is not None else await _evidence_rows(source_key, run_id)
    if not catalogue_rows:
        raise HTTPException(status_code=404, detail="Development evidence snapshot is unavailable")
    try:
        conn = await asyncpg.connect(DB_DSN)
        try:
            payload = await conn.fetchval(EVIDENCE_FEATURE_SQL[source_key], run_id)
        finally:
            await conn.close()
    except Exception:
        logging.exception("Development evidence feature query error")
        raise HTTPException(status_code=503, detail="Development evidence snapshot is unavailable")
    decoded = json.loads(payload) if isinstance(payload, str) else payload
    if not decoded or not decoded.get("features"):
        raise HTTPException(status_code=404, detail="Development evidence snapshot is unavailable")
    return decoded


def _decode_json_value(value):
    return json.loads(value) if isinstance(value, str) else value


@app.get("/drought/development/fews-net-context/runs")
async def development_fews_net_context_runs():
    """List retained FEWS NET provider issues; never present them as TSIRD results."""
    try:
        conn = await asyncpg.connect(DB_DSN)
        try:
            rows = await conn.fetch("""SELECT r.run_id, r.issued_at, r.source_url, r.source_note, count(f.feature_id)::integer AS feature_count
              FROM tsird.drought_fews_net_context_run r LEFT JOIN tsird.drought_fews_net_context_feature f USING(run_id)
              WHERE r.status='development' GROUP BY r.run_id ORDER BY r.issued_at DESC""")
        finally: await conn.close()
    except Exception:
        logging.exception("FEWS NET context run query error")
        raise HTTPException(status_code=503, detail="FEWS NET provider context unavailable")
    return {"schema_version":"tsird-fews-net-context.v1","environment":"development",
      "selection_note":"Provider-issued, IPC-compatible context at native FSC geography; not a TSIRD/Tabia food-security classification or priority input.",
      "runs":[dict(row) for row in rows]}


@app.get("/drought/development/fews-net-context/runs/{run_id}/features")
async def development_fews_net_context_features(run_id: str):
    try:
        conn = await asyncpg.connect(DB_DSN)
        try:
            payload = await conn.fetchval("""SELECT json_build_object('type','FeatureCollection','features',coalesce(json_agg(json_build_object(
              'type','Feature','id',feature_id,'geometry',ST_AsGeoJSON(geometry)::json,'properties',properties)),'[]'::json))
              FROM tsird.drought_fews_net_context_feature WHERE run_id=$1""", run_id)
        finally: await conn.close()
    except Exception:
        logging.exception("FEWS NET context feature query error")
        raise HTTPException(status_code=503, detail="FEWS NET provider context unavailable")
    decoded = _decode_json_value(payload)
    if not decoded or not decoded.get("features"): raise HTTPException(status_code=404, detail="FEWS NET provider issue unavailable")
    return decoded


@app.get("/drought/development/fews-net-context/runs/{run_id}/tabias/{tabia_id}")
async def development_fews_net_context_for_tabia(run_id: str, tabia_id: str):
    """Return native provider features intersecting one Tabia, without downscaling them."""
    try:
        conn = await asyncpg.connect(DB_DSN)
        try:
            tabia = await conn.fetchrow(
                'SELECT "TABIA" AS tabia_name_en, "WEREDA" AS woreda_name_en FROM tigray_tabias_ws WHERE tsird_tabia_id=$1', tabia_id)
            rows = await conn.fetch("""SELECT feature_id, properties
                FROM tsird.drought_fews_net_context_feature f
                JOIN tigray_tabias_ws t ON ST_Intersects(f.geometry, t.geometry)
                WHERE f.run_id=$1 AND t.tsird_tabia_id=$2 ORDER BY feature_id""", run_id, tabia_id)
        finally: await conn.close()
    except Exception:
        logging.exception("FEWS NET context Tabia intersection error")
        raise HTTPException(status_code=503, detail="FEWS NET provider context unavailable")
    if not tabia:
        raise HTTPException(status_code=404, detail="Unknown Tabia ID")
    return {
        "schema_version": "tsird-fews-net-context.v1", "environment": "development",
        "selection_note": "Intersecting provider-native FSC areas are context only; no classification is transferred to the Tabia.",
        "tabia": dict(tabia), "features": [dict(row) for row in rows],
    }


def _seasonal_outlook_lifecycle(row):
    """Classify a provider release by its declared validity, never import time."""
    from datetime import date
    today = date.today()
    if row["valid_from"] > today:
        return "upcoming"
    if row["valid_to"] >= today:
        return "active"
    return "archived"


def _seasonal_outlook_record(row):
    return {
        "run_id": row["run_id"],
        "source_id": row["source_id"],
        "variable": row["variable"],
        "source_product": row["source_product"],
        "source_version": row["source_version"],
        "issued_at": row["issued_at"].isoformat(),
        "valid_from": row["valid_from"].isoformat(),
        "valid_to": row["valid_to"].isoformat(),
        "lead_start_months": row["lead_start_months"],
        "lead_end_months": row["lead_end_months"],
        "native_resolution": row["native_resolution"],
        "native_crs": row["native_crs"],
        "geography_scope": row["geography_scope"],
        "source_url": row["source_url"],
        "status": row["status"],
        "lifecycle": _seasonal_outlook_lifecycle(row),
        "quality_summary": _decode_json_value(row["quality_summary"]),
        "provenance": _decode_json_value(row["provenance"]),
    }


async def _seasonal_outlook_rows(variable: str | None = None):
    query = DROUGHT_SEASONAL_OUTLOOK_RUNS_SQL
    values = []
    if variable:
        if variable not in {"seasonal_rainfall", "seasonal_temperature"}:
            raise HTTPException(status_code=404, detail="Unknown seasonal outlook variable")
        query = query.replace("WHERE status NOT IN", "WHERE variable = $1 AND status NOT IN")
        values.append(variable)
    try:
        conn = await asyncpg.connect(DB_DSN)
        try:
            return await conn.fetch(query, *values)
        finally:
            await conn.close()
    except Exception:
        logging.exception("Development seasonal-outlook query error")
        raise HTTPException(status_code=503, detail="Development seasonal outlook service unavailable")


@app.get("/drought/development/seasonal-outlook/runs")
async def development_seasonal_outlook_runs(variable: str = Query("seasonal_rainfall")):
    """List provider outlook releases, including archive state derived from valid dates."""
    rows = await _seasonal_outlook_rows(variable)
    return {
        "schema_version": "tsird-seasonal-outlook.v1",
        "environment": "development",
        "selection_note": "Provider-issued climate probabilities only; not a Tabia forecast, food-security forecast, or priority score.",
        "runs": [_seasonal_outlook_record(row) for row in rows],
    }


@app.get("/drought/development/seasonal-outlook/active")
async def development_active_seasonal_outlook(variable: str = Query("seasonal_rainfall")):
    """Return only the active release, otherwise the nearest upcoming release.

    An expired release is never returned as current.  The browser receives an
    explicit no-data status until a reviewed provider asset has been loaded.
    """
    rows = await _seasonal_outlook_rows(variable)
    active_or_upcoming = next((row for row in rows if _seasonal_outlook_lifecycle(row) in {"active", "upcoming"}), None)
    if not active_or_upcoming:
        return {
            "schema_version": "tsird-seasonal-outlook.v1",
            "environment": "development",
            "available": False,
            "variable": variable,
            "reason": "No reviewed active or upcoming provider outlook is loaded.",
        }
    return {
        "schema_version": "tsird-seasonal-outlook.v1",
        "environment": "development",
        "available": True,
        "run": _seasonal_outlook_record(active_or_upcoming),
    }


@app.get("/drought/development/seasonal-outlook/runs/{run_id}/features")
async def development_seasonal_outlook_features(
        run_id: str,
        representation: str = Query("native_grid")):
    """Return one bounded provider-native or Woreda-context probability map."""
    if representation not in {"native_grid", "woreda_context"}:
        raise HTTPException(status_code=404, detail="Unknown seasonal outlook representation")
    try:
        conn = await asyncpg.connect(DB_DSN)
        try:
            exists = await conn.fetchval(
                "SELECT EXISTS (SELECT 1 FROM tsird.drought_seasonal_outlook_run WHERE run_id = $1)", run_id)
            if not exists:
                raise HTTPException(status_code=404, detail="Seasonal outlook release is unavailable")
            payload = await conn.fetchval(DROUGHT_SEASONAL_OUTLOOK_FEATURE_SQL, run_id, representation)
        finally:
            await conn.close()
    except HTTPException:
        raise
    except Exception:
        logging.exception("Development seasonal-outlook feature query error")
        raise HTTPException(status_code=503, detail="Development seasonal outlook is unavailable")
    decoded = _decode_json_value(payload)
    if not decoded or not decoded.get("features"):
        raise HTTPException(status_code=404, detail="Seasonal outlook representation is unavailable")
    return decoded


@app.get("/drought/development/observed-rainfall/latest")
async def development_observed_rainfall(limit: int = Query(100, ge=1, le=748)):
    """Expose the latest local development rainfall artifact with its provenance."""
    try:
        conn = await asyncpg.connect(DB_DSN)
        try:
            row = await conn.fetchrow(DROUGHT_DEVELOPMENT_OBSERVED_SQL, limit)
        finally:
            await conn.close()
    except Exception:
        import logging
        logging.exception("Development drought artifact query error")
        raise HTTPException(status_code=503, detail="Development artifact service unavailable")
    if not row or not row["run"]:
        raise HTTPException(status_code=404, detail="No development observed-rainfall artifact is available")
    def decode_json(value):
        # asyncpg returns PostgreSQL json/jsonb values as strings unless a
        # codec is registered. Decode them here so the browser receives an
        # actual artifact object/array, never JSON text inside JSON.
        return json.loads(value) if isinstance(value, str) else value

    return {
        "schema_version": "tsird-drought-observed-rainfall.v1",
        "environment": "development",
        "run": decode_json(row["run"]),
        "artifact": decode_json(row["artifact"]),
        "conditions": decode_json(row["conditions"]),
    }


@app.get("/drought/development/observed-rainfall/runs")
async def development_observed_rainfall_runs(limit: int = Query(36, ge=1, le=60)):
    """List available development evidence snapshots without returning their payloads."""
    try:
        conn = await asyncpg.connect(DB_DSN)
        try:
            rows = await conn.fetch(DROUGHT_DEVELOPMENT_OBSERVED_RUNS_SQL, limit)
        finally:
            await conn.close()
    except Exception:
        import logging
        logging.exception("Development rainfall-run listing error")
        raise HTTPException(status_code=503, detail="Development artifact service unavailable")
    return {
        "schema_version": "tsird-drought-observed-rainfall-runs.v1",
        "environment": "development",
        "selection_note": "Snapshots are archived observations, not an as-issued forecast replay.",
        "runs": [dict(row) for row in rows],
    }


@app.get("/drought/development/observed-rainfall/runs/{run_id}")
async def development_observed_rainfall_run(run_id: str, limit: int = Query(748, ge=1, le=748)):
    """Return one deliberate historical evidence snapshot by its opaque run ID."""
    try:
        conn = await asyncpg.connect(DB_DSN)
        try:
            row = await conn.fetchrow(DROUGHT_DEVELOPMENT_OBSERVED_BY_RUN_SQL, run_id, limit)
        finally:
            await conn.close()
    except Exception:
        import logging
        logging.exception("Development rainfall-run query error")
        raise HTTPException(status_code=503, detail="Development artifact service unavailable")
    if not row or not row["run"]:
        raise HTTPException(status_code=404, detail="Development observed-rainfall snapshot is unavailable")

    def decode_json(value):
        return json.loads(value) if isinstance(value, str) else value

    return {
        "schema_version": "tsird-drought-observed-rainfall.v1",
        "environment": "development",
        "snapshot_kind": "archived_observation",
        "selection_note": "This is a historical evidence snapshot. It is not proof that every source was available at an earlier decision date.",
        "run": decode_json(row["run"]),
        "artifact": decode_json(row["artifact"]),
        "conditions": decode_json(row["conditions"]),
    }


@app.get("/drought/development/observed-rainfall/runs/{run_id}/features")
async def development_observed_rainfall_run_features(run_id: str):
    """Return one selected historical rainfall snapshot as bounded Tabia GeoJSON."""
    try:
        conn = await asyncpg.connect(DB_DSN)
        try:
            payload = await conn.fetchval(DROUGHT_DEVELOPMENT_OBSERVED_GEOJSON_BY_RUN_SQL, run_id)
        finally:
            await conn.close()
    except Exception:
        import logging
        logging.exception("Development rainfall-run GeoJSON query error")
        raise HTTPException(status_code=503, detail="Development artifact service unavailable")
    if not payload:
        raise HTTPException(status_code=404, detail="Development observed-rainfall snapshot is unavailable")
    return json.loads(payload) if isinstance(payload, str) else payload


@app.get("/drought/development/preliminary-rainfall/latest")
async def development_preliminary_rainfall(limit: int = Query(748, ge=1, le=748)):
    """Expose rapid preliminary rainfall separately from final classification."""
    try:
        conn = await asyncpg.connect(DB_DSN)
        try:
            row = await conn.fetchrow(DROUGHT_DEVELOPMENT_PRELIMINARY_SQL, limit)
        finally:
            await conn.close()
    except Exception:
        import logging
        logging.exception("Development preliminary rainfall query error")
        raise HTTPException(status_code=503, detail="Development preliminary rainfall service unavailable")
    if not row or not row["run"]:
        raise HTTPException(status_code=404, detail="No development preliminary-rainfall artifact is available")
    def decode_json(value):
        return json.loads(value) if isinstance(value, str) else value
    return {"schema_version": "tsird-drought-preliminary-rainfall.v1", "environment": "development",
            "run": decode_json(row["run"]), "summaries": decode_json(row["summaries"])}

@app.get("/drought/development/ndvi/latest")
async def development_ndvi(limit: int = Query(748, ge=1, le=748)):
    try:
        conn = await asyncpg.connect(DB_DSN)
        try: row = await conn.fetchrow(DROUGHT_DEVELOPMENT_NDVI_SQL, limit)
        finally: await conn.close()
    except Exception:
        logging.exception("Development NDVI artifact query error")
        raise HTTPException(status_code=503, detail="Development NDVI artifact service unavailable")
    if not row or not row["run"]: raise HTTPException(status_code=404, detail="No development NDVI artifact is available")
    decode = lambda value: json.loads(value) if isinstance(value, str) else value
    return {"schema_version":"tsird-drought-ndvi.v1", "environment":"development", "run":decode(row["run"]), "summaries":decode(row["summaries"])}


@app.get("/drought/development/swi/latest")
async def development_swi(limit: int = Query(748, ge=1, le=748)):
    """Expose coarse SWI context separately from a drought classification."""
    try:
        conn = await asyncpg.connect(DB_DSN)
        try:
            row = await conn.fetchrow(DROUGHT_DEVELOPMENT_SWI_SQL, limit)
        finally:
            await conn.close()
    except Exception:
        logging.exception("Development SWI artifact query error")
        raise HTTPException(status_code=503, detail="Development SWI artifact service unavailable")
    if not row or not row["run"]:
        raise HTTPException(status_code=404, detail="No development SWI artifact is available")
    decode = lambda value: json.loads(value) if isinstance(value, str) else value
    return {"schema_version": "tsird-drought-swi.v1", "environment": "development",
            "run": decode(row["run"]), "summaries": decode(row["summaries"])}


@app.get("/drought/development/lst/latest")
async def development_lst(limit: int = Query(748, ge=1, le=748)):
    """Expose land-surface-temperature context separately from drought labels."""
    try:
        conn = await asyncpg.connect(DB_DSN)
        try: row = await conn.fetchrow(DROUGHT_DEVELOPMENT_LST_SQL, limit)
        finally: await conn.close()
    except Exception:
        logging.exception("Development LST artifact query error")
        raise HTTPException(status_code=503, detail="Development LST artifact service unavailable")
    if not row or not row["run"]: raise HTTPException(status_code=404, detail="No development LST artifact is available")
    decode = lambda value: json.loads(value) if isinstance(value, str) else value
    return {"schema_version": "tsird-drought-lst.v1", "environment": "development", "run": decode(row["run"]), "summaries": decode(row["summaries"])}


@app.get("/drought/development/wapor/latest")
async def development_wapor(limit: int = Query(748, ge=1, le=748)):
    """Expose FAO WaPOR water-use context separately from crop or drought claims."""
    try:
        conn = await asyncpg.connect(DB_DSN)
        try: row = await conn.fetchrow(DROUGHT_DEVELOPMENT_WAPOR_SQL, limit)
        finally: await conn.close()
    except Exception:
        logging.exception("Development WaPOR artifact query error")
        raise HTTPException(status_code=503, detail="Development WaPOR artifact service unavailable")
    if not row or not row["run"]:
        raise HTTPException(status_code=404, detail="No development WaPOR artifact is available")
    decode = lambda value: json.loads(value) if isinstance(value, str) else value
    return {"schema_version": "tsird-drought-wapor.v1", "environment": "development", "run": decode(row["run"]), "summaries": decode(row["summaries"])}


@app.get("/drought/development/history/{indicator}/{tabia_id}")
async def development_history(indicator: str, tabia_id: str):
    """Return one Tabia's retained evidence points; no interpolation or score."""
    sql = DROUGHT_HISTORY_SQL.get(indicator)
    if not sql:
        raise HTTPException(status_code=404, detail="Unknown development evidence indicator")
    try:
        conn = await asyncpg.connect(DB_DSN)
        try:
            tabia = await conn.fetchrow('SELECT "TABIA" AS tabia_name_en, "WEREDA" AS woreda_name_en FROM tigray_tabias_ws WHERE tsird_tabia_id = $1', tabia_id)
            rows = await conn.fetch(sql, tabia_id)
        finally:
            await conn.close()
    except Exception:
        logging.exception("Development evidence history query error")
        raise HTTPException(status_code=503, detail="Development evidence history service unavailable")
    if not tabia:
        raise HTTPException(status_code=404, detail="Unknown Tabia ID")
    return {"schema_version": "tsird-drought-evidence-history.v1", "environment": "development",
            "indicator": indicator, "metadata": HISTORY_METADATA[indicator], "tabia": dict(tabia),
            "points": [dict(row) for row in rows]}


@app.get("/boundaries/{boundary_type}/{boundary_id}")
async def boundary(boundary_type: str, boundary_id: str):
    """Return one known administrative boundary for map fit/highlight."""
    sql = BOUNDARY_SQL.get(boundary_type)
    if not sql:
        raise HTTPException(status_code=404, detail="Unknown boundary type")
    if boundary_type == "woreda":
        try:
            lookup_id = int(boundary_id)
        except ValueError:
            raise HTTPException(status_code=422, detail="Woreda boundary ID must be numeric")
    else:
        lookup_id = boundary_id
    try:
        conn = await asyncpg.connect(DB_DSN)
        try:
            row = await conn.fetchrow(sql, lookup_id)
        finally:
            await conn.close()
    except Exception:
        import logging
        logging.exception("Boundary query error")
        raise HTTPException(status_code=503, detail="Boundary service unavailable")
    if not row:
        raise HTTPException(status_code=404, detail="Boundary not found")
    return {
        "type": boundary_type,
        "id": row["tsird_tabia_id"] if boundary_type == "tabia" else str(row["gid"]),
        "name_en": row["name_en"] or "",
        "name_ti": row["name_ti"] or "",
        "parent_name_en": row["parent_name_en"] or "",
        "bbox": list(row["bbox"]) if row["bbox"] else None,
        "geometry": row["geometry"],
    }
