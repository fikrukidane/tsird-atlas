BEGIN;

-- This deliberately narrow seed supports the explicitly approved public
-- *prototype* only. It stores synthetic values on actual Woreda boundaries;
-- it stores no provider grid, Tabia forecast, live-scoring output, survey
-- response, credential, or external source connection.
CREATE SCHEMA IF NOT EXISTS tsird;

CREATE TABLE IF NOT EXISTS tsird.drought_source_catalog (
  source_id text PRIMARY KEY,
  provider text NOT NULL,
  product text NOT NULL,
  access_method text NOT NULL,
  license_summary text NOT NULL,
  refresh_expectation text NOT NULL,
  intended_use text NOT NULL,
  enabled boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tsird.drought_seasonal_outlook_run (
  run_id text PRIMARY KEY,
  source_id text NOT NULL REFERENCES tsird.drought_source_catalog(source_id),
  variable text NOT NULL CHECK (variable IN ('seasonal_rainfall', 'seasonal_temperature')),
  source_product text NOT NULL,
  source_version text,
  issued_at timestamptz NOT NULL,
  valid_from date NOT NULL,
  valid_to date NOT NULL,
  lead_start_months smallint NOT NULL CHECK (lead_start_months >= 0),
  lead_end_months smallint NOT NULL CHECK (lead_end_months >= lead_start_months),
  native_resolution text NOT NULL,
  native_crs text NOT NULL DEFAULT 'EPSG:4326',
  geography_scope text NOT NULL,
  source_url text NOT NULL,
  source_checksum text,
  status text NOT NULL CHECK (status IN ('development', 'validated', 'published', 'degraded', 'failed', 'superseded')),
  quality_summary jsonb NOT NULL DEFAULT '{}'::jsonb,
  provenance jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (valid_to >= valid_from),
  UNIQUE (source_id, variable, issued_at, valid_from, valid_to)
);

CREATE TABLE IF NOT EXISTS tsird.drought_seasonal_outlook_feature (
  run_id text NOT NULL REFERENCES tsird.drought_seasonal_outlook_run(run_id) ON DELETE CASCADE,
  feature_id text NOT NULL,
  representation text NOT NULL CHECK (representation IN ('native_grid', 'woreda_context')),
  provider_area_id text,
  woreda_gid text,
  below_normal_probability numeric(5,4),
  near_normal_probability numeric(5,4),
  above_normal_probability numeric(5,4),
  coverage_pct numeric(5,2),
  quality_status text NOT NULL DEFAULT 'ok' CHECK (quality_status IN ('ok', 'insufficient_coverage', 'degraded', 'unavailable')),
  geometry geometry(Geometry, 4326) NOT NULL,
  PRIMARY KEY (run_id, feature_id, representation),
  CHECK (below_normal_probability IS NULL OR below_normal_probability BETWEEN 0 AND 1),
  CHECK (near_normal_probability IS NULL OR near_normal_probability BETWEEN 0 AND 1),
  CHECK (above_normal_probability IS NULL OR above_normal_probability BETWEEN 0 AND 1),
  CHECK (coverage_pct IS NULL OR coverage_pct BETWEEN 0 AND 100)
);

CREATE INDEX IF NOT EXISTS drought_seasonal_outlook_run_current_idx
  ON tsird.drought_seasonal_outlook_run (variable, status, valid_from, valid_to, issued_at DESC);
CREATE INDEX IF NOT EXISTS drought_seasonal_outlook_feature_geometry_idx
  ON tsird.drought_seasonal_outlook_feature USING GIST (geometry);

INSERT INTO tsird.drought_source_catalog
  (source_id, provider, product, access_method, license_summary, refresh_expectation, intended_use)
VALUES
  ('tsird-public-experimental-outlook-v1',
   'TSIRD review prototype',
   'Synthetic Woreda seasonal-rainfall context',
   'Versioned SQL fixture',
   'Synthetic content; no provider data or licence claim',
   'No automatic refresh',
   'Review-only interface prototype')
ON CONFLICT (source_id) DO NOTHING;

INSERT INTO tsird.drought_seasonal_outlook_run (
  run_id, source_id, variable, source_product, source_version, issued_at,
  valid_from, valid_to, lead_start_months, lead_end_months, native_resolution,
  native_crs, geography_scope, source_url, source_checksum, status,
  quality_summary, provenance
)
VALUES (
  'synthetic-seasonal-outlook-review-20261018',
  'tsird-public-experimental-outlook-v1',
  'seasonal_rainfall',
  'Synthetic Woreda review context',
  'synthetic-v1',
  '2026-10-18T12:00:00Z',
  '2026-11-01', '2027-01-31', 1, 3,
  'Woreda context only', 'EPSG:4326',
  'Synthetic Woreda context for Tigray review only',
  'urn:tsird:experimental-outlook:20261018',
  'synthetic-woreda-review-fixture-v1', 'degraded',
  '{"review_only": true, "synthetic": true, "provider_issued": false, "publication_allowed": true, "woreda_context_only": true}',
  '{"purpose": "public interface prototype", "not_a_forecast": true, "not_for_operational_or_response_use": true, "no_provider_connection": true, "no_tabia_prediction": true}'
)
ON CONFLICT (run_id) DO NOTHING;

-- The values are deterministic demonstration values. They are deliberately
-- attached only to complete Woreda geometries; no synthetic grid cells are
-- retained or exposed by this migration.
WITH ordered_woredas AS (
  SELECT gid::text AS woreda_gid, geometry,
         row_number() OVER (ORDER BY gid)::int AS ordinal
  FROM tigray_woredas_ws
), probabilities AS (
  SELECT woreda_gid, geometry,
    CASE ordinal % 4 WHEN 0 THEN 0.45 WHEN 1 THEN 0.25 WHEN 2 THEN 0.20 ELSE 0.30 END AS below_p,
    CASE ordinal % 4 WHEN 0 THEN 0.35 WHEN 1 THEN 0.50 WHEN 2 THEN 0.55 ELSE 0.40 END AS near_p,
    CASE ordinal % 4 WHEN 0 THEN 0.20 WHEN 1 THEN 0.25 WHEN 2 THEN 0.25 ELSE 0.30 END AS above_p
  FROM ordered_woredas
)
INSERT INTO tsird.drought_seasonal_outlook_feature (
  run_id, feature_id, representation, provider_area_id, woreda_gid,
  below_normal_probability, near_normal_probability, above_normal_probability,
  coverage_pct, quality_status, geometry
)
SELECT
  'synthetic-seasonal-outlook-review-20261018',
  'synthetic-woreda-' || woreda_gid,
  'woreda_context',
  'synthetic-woreda-context-' || woreda_gid,
  woreda_gid,
  below_p, near_p, above_p,
  100, 'degraded', geometry
FROM probabilities
ON CONFLICT (run_id, feature_id, representation) DO NOTHING;

COMMIT;
