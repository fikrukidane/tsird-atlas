BEGIN;

-- Development-only Sentinel-2 L2A moisture-evidence pilot.  The tables keep
-- compact, quality-accountable Tabia statistics returned by CDSE's
-- Statistical API; TSIRD does not retain raw Sentinel scenes for this pilot.
INSERT INTO tsird.drought_source_catalog
  (source_id, provider, product, access_method, license_summary, refresh_expectation, intended_use, enabled)
VALUES
  ('cdse-sentinel2-l2a-ndmi-pilot', 'Copernicus Data Space Ecosystem',
   'Sentinel-2 Level-2A B08/B11 masked NDMI pilot',
   'OAuth client credentials and Sentinel Hub Statistical API',
   'Copernicus terms and attribution; source-specific review required',
   'Manual development pilot only',
   'High-resolution vegetation-moisture evidence review', false)
ON CONFLICT (source_id) DO NOTHING;

CREATE TABLE IF NOT EXISTS tsird.drought_sentinel2_ndmi_run (
  run_id text PRIMARY KEY,
  source_id text NOT NULL REFERENCES tsird.drought_source_catalog(source_id),
  observation_start timestamptz NOT NULL,
  observation_end timestamptz NOT NULL,
  native_resolution text NOT NULL,
  mosaicking_order text NOT NULL,
  valid_scl_classes integer[] NOT NULL,
  min_valid_coverage_pct numeric NOT NULL CHECK (min_valid_coverage_pct > 0 AND min_valid_coverage_pct <= 100),
  pilot_tabia_limit integer NOT NULL CHECK (pilot_tabia_limit > 0 AND pilot_tabia_limit <= 20),
  source_retrieved_at timestamptz NOT NULL,
  processing_version text NOT NULL,
  status text NOT NULL CHECK (status IN ('development', 'degraded', 'failed')),
  notes text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tsird.drought_tabia_sentinel2_ndmi (
  run_id text NOT NULL REFERENCES tsird.drought_sentinel2_ndmi_run(run_id) ON DELETE CASCADE,
  tsird_tabia_id text NOT NULL REFERENCES tsird.tabia_identity(tsird_tabia_id),
  ndmi_mean numeric,
  ndmi_median numeric,
  valid_pixel_count integer NOT NULL CHECK (valid_pixel_count >= 0),
  grid_cell_count integer NOT NULL CHECK (grid_cell_count >= valid_pixel_count),
  coverage_pct numeric NOT NULL CHECK (coverage_pct >= 0 AND coverage_pct <= 100),
  quality_status text NOT NULL CHECK (quality_status IN ('ok', 'insufficient_evidence')),
  PRIMARY KEY (run_id, tsird_tabia_id)
);

CREATE INDEX IF NOT EXISTS drought_sentinel2_ndmi_run_observation_idx
  ON tsird.drought_sentinel2_ndmi_run (observation_end DESC, created_at DESC);

COMMIT;
