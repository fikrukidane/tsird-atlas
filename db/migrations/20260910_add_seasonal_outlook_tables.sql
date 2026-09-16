BEGIN;

-- A seasonal outlook is a provider-issued climate probability product, not a
-- Tabia forecast or a TSIRD food-security classification.  Runs deliberately
-- retain issue/validity dates and source geography so the UI can select only
-- upcoming or active releases by default.
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

-- The same table can hold provider-native grid cells and a transparent,
-- optional Woreda contextual summary.  It has no Tabia geography column by
-- design: a seasonal climate probability must not be turned into a Tabia
-- prediction by storage or display.
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

COMMIT;
