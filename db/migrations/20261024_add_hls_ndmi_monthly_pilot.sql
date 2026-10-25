BEGIN;

-- DEV-only HLS monthly vegetation-moisture pilot.  This deliberately uses
-- separate tables so neither the original Sentinel-2 experiment nor a later
-- HLS result can be mistaken for the other.
INSERT INTO tsird.drought_source_catalog
  (source_id, provider, product, access_method, license_summary, refresh_expectation, intended_use, enabled)
VALUES
  ('nasa-hls-v2-ndmi-monthly-pilot', 'NASA LP DAAC / Earthdata Cloud',
   'Harmonized Landsat and Sentinel-2 (HLS) v2.0 L30/S30 surface reflectance',
   'CMR-STAC discovery and authenticated COG range reads using an Earthdata token',
   'NASA Earthdata / LP DAAC terms and required HLS attribution; source-specific review required',
   'Manual DEV 20-Tabia feasibility pilot only; no schedule',
   'Monthly cloud- and shadow-masked vegetation-moisture evidence feasibility review', false)
ON CONFLICT (source_id) DO NOTHING;

CREATE TABLE IF NOT EXISTS tsird.drought_hls_ndmi_run (
  run_id text PRIMARY KEY,
  source_id text NOT NULL REFERENCES tsird.drought_source_catalog(source_id),
  observation_start timestamptz NOT NULL,
  observation_end timestamptz NOT NULL,
  native_resolution text NOT NULL,
  source_collections text[] NOT NULL,
  validity_mask text NOT NULL,
  coverage_definition text NOT NULL,
  min_valid_observation_coverage_pct numeric NOT NULL CHECK (min_valid_observation_coverage_pct > 0 AND min_valid_observation_coverage_pct <= 100),
  min_valid_observation_pixels integer NOT NULL CHECK (min_valid_observation_pixels > 0),
  min_usable_acquisition_count integer NOT NULL CHECK (min_usable_acquisition_count > 0),
  pilot_tabia_limit integer NOT NULL CHECK (pilot_tabia_limit > 0 AND pilot_tabia_limit <= 20),
  source_retrieved_at timestamptz NOT NULL,
  processing_version text NOT NULL,
  status text NOT NULL CHECK (status IN ('development', 'degraded', 'failed')),
  notes text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tsird.drought_tabia_hls_ndmi (
  run_id text NOT NULL REFERENCES tsird.drought_hls_ndmi_run(run_id) ON DELETE CASCADE,
  tsird_tabia_id text NOT NULL REFERENCES tsird.tabia_identity(tsird_tabia_id),
  ndmi_mean numeric,
  ndmi_median numeric,
  valid_observation_pixel_count integer NOT NULL CHECK (valid_observation_pixel_count >= 0),
  candidate_observation_pixel_count integer NOT NULL CHECK (candidate_observation_pixel_count >= valid_observation_pixel_count),
  coverage_pct numeric NOT NULL CHECK (coverage_pct >= 0 AND coverage_pct <= 100),
  candidate_acquisition_count integer NOT NULL CHECK (candidate_acquisition_count >= 0),
  usable_acquisition_count integer NOT NULL CHECK (usable_acquisition_count >= 0 AND usable_acquisition_count <= candidate_acquisition_count),
  first_acquisition_at timestamptz,
  last_acquisition_at timestamptz,
  median_acquisition_at timestamptz,
  quality_status text NOT NULL CHECK (quality_status IN ('ok', 'insufficient_valid_pixel_count', 'insufficient_observation_coverage', 'insufficient_acquisition_count')),
  PRIMARY KEY (run_id, tsird_tabia_id)
);

CREATE INDEX IF NOT EXISTS drought_hls_ndmi_run_observation_idx
  ON tsird.drought_hls_ndmi_run (observation_end DESC, created_at DESC);

COMMIT;
