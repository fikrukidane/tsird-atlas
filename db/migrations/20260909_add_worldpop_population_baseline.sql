BEGIN;

INSERT INTO tsird.drought_source_catalog
  (source_id, provider, product, access_method, license_summary, refresh_expectation, intended_use)
VALUES
  ('worldpop-global-2025-r2025a-v1', 'WorldPop', 'Ethiopia constrained population counts, 2025, 100 m, R2025A v1',
   'Open GeoTIFF download from WorldPop', 'CC BY 4.0; retain provider attribution and release status',
   'Refresh when a reviewed WorldPop release is available', 'Tabia population baseline; not a census or hazard-exposure estimate')
ON CONFLICT (source_id) DO UPDATE SET
  product=EXCLUDED.product, access_method=EXCLUDED.access_method, license_summary=EXCLUDED.license_summary,
  refresh_expectation=EXCLUDED.refresh_expectation, intended_use=EXCLUDED.intended_use;

CREATE TABLE IF NOT EXISTS tsird.drought_population_run (
  run_id text PRIMARY KEY,
  source_id text NOT NULL REFERENCES tsird.drought_source_catalog(source_id),
  population_year integer NOT NULL,
  source_release text NOT NULL,
  source_url text NOT NULL,
  source_sha256 text NOT NULL,
  native_resolution text NOT NULL,
  boundary_set_version text NOT NULL,
  status text NOT NULL CHECK (status IN ('development', 'validated', 'published', 'degraded', 'failed')),
  source_feature_note text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tsird.drought_tabia_population (
  run_id text NOT NULL REFERENCES tsird.drought_population_run(run_id) ON DELETE CASCADE,
  tsird_tabia_id text NOT NULL REFERENCES public.tigray_tabias_ws(tsird_tabia_id),
  population_total double precision NOT NULL CHECK (population_total >= 0),
  people_per_sq_km double precision NOT NULL CHECK (people_per_sq_km >= 0),
  valid_pixel_count integer NOT NULL CHECK (valid_pixel_count >= 0),
  total_pixel_count integer NOT NULL CHECK (total_pixel_count >= 0),
  coverage_pct double precision NOT NULL CHECK (coverage_pct >= 0 AND coverage_pct <= 100),
  quality_status text NOT NULL CHECK (quality_status IN ('ok', 'insufficient_coverage', 'unavailable')),
  PRIMARY KEY (run_id, tsird_tabia_id)
);

CREATE INDEX IF NOT EXISTS drought_tabia_population_run_idx
  ON tsird.drought_tabia_population (run_id, tsird_tabia_id);

COMMIT;
