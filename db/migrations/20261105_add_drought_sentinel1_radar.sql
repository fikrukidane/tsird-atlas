BEGIN;

-- Development-only Sentinel-1 radar evidence.  This is intentionally a
-- separate observed-backscatter product: it has no drought, flood, soil
-- moisture, food-security, allocation or priority classification semantics.
INSERT INTO tsird.drought_source_catalog
  (source_id, provider, product, access_method, license_summary,
   refresh_expectation, intended_use, enabled)
VALUES
  ('cdse-sentinel1-grd-monthly-development', 'Copernicus Data Space Ecosystem',
   'Sentinel-1 GRD IW dual-polarisation monthly radar backscatter',
   'CDSE STAC discovery and Sentinel Hub Statistical API using runner-held OAuth credentials',
   'Copernicus Sentinel data terms and required attribution; source-specific review required',
   'Daily DEV source check; acquire a new or revised completed month only',
   'All-weather radar surface-condition evidence review', false)
ON CONFLICT (source_id) DO NOTHING;

CREATE TABLE IF NOT EXISTS tsird.drought_sentinel1_radar_run (
  run_id text PRIMARY KEY,
  source_id text NOT NULL REFERENCES tsird.drought_source_catalog(source_id),
  observation_start timestamptz NOT NULL,
  observation_end timestamptz NOT NULL,
  native_resolution text NOT NULL,
  orbit_direction text NOT NULL,
  polarizations text[] NOT NULL,
  terrain_correction text NOT NULL,
  source_scene_count integer NOT NULL CHECK (source_scene_count >= 0),
  source_fingerprint text NOT NULL,
  min_valid_coverage_pct numeric NOT NULL CHECK (min_valid_coverage_pct > 0 AND min_valid_coverage_pct <= 100),
  min_usable_scene_count integer NOT NULL CHECK (min_usable_scene_count > 0),
  tabia_count integer NOT NULL CHECK (tabia_count > 0 AND tabia_count <= 748),
  source_retrieved_at timestamptz NOT NULL,
  processing_version text NOT NULL,
  status text NOT NULL CHECK (status IN ('development', 'degraded', 'failed')),
  notes text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tsird.drought_tabia_sentinel1_radar (
  run_id text NOT NULL REFERENCES tsird.drought_sentinel1_radar_run(run_id) ON DELETE CASCADE,
  tsird_tabia_id text NOT NULL REFERENCES tsird.tabia_identity(tsird_tabia_id),
  vv_db_median numeric,
  vh_db_median numeric,
  valid_pixel_count integer NOT NULL CHECK (valid_pixel_count >= 0),
  grid_cell_count integer NOT NULL CHECK (grid_cell_count >= valid_pixel_count),
  coverage_pct numeric NOT NULL CHECK (coverage_pct >= 0 AND coverage_pct <= 100),
  contributing_scene_count integer NOT NULL CHECK (contributing_scene_count >= 0),
  quality_status text NOT NULL CHECK (quality_status IN ('ok', 'limited_coverage', 'insufficient_evidence')),
  PRIMARY KEY (run_id, tsird_tabia_id)
);

CREATE INDEX IF NOT EXISTS drought_sentinel1_radar_run_observation_idx
  ON tsird.drought_sentinel1_radar_run (observation_end DESC, created_at DESC);

COMMIT;
