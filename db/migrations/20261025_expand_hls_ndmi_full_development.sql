BEGIN;

-- Preserve the 20-Tabia feasibility pilot while allowing a separately labelled
-- complete DEV artifact.  This migration is additive in meaning and never
-- creates a production release or publication path.
ALTER TABLE tsird.drought_hls_ndmi_run
  RENAME COLUMN pilot_tabia_limit TO tabia_count;

ALTER TABLE tsird.drought_hls_ndmi_run
  DROP CONSTRAINT IF EXISTS drought_hls_ndmi_run_pilot_tabia_limit_check;

ALTER TABLE tsird.drought_hls_ndmi_run
  ADD CONSTRAINT drought_hls_ndmi_run_tabia_count_check
  CHECK (tabia_count > 0 AND tabia_count <= 748);

ALTER TABLE tsird.drought_hls_ndmi_run
  ADD COLUMN IF NOT EXISTS run_scope text NOT NULL DEFAULT 'technical_pilot'
  CHECK (run_scope IN ('technical_pilot', 'full_development'));

ALTER TABLE tsird.drought_tabia_hls_ndmi
  DROP CONSTRAINT IF EXISTS drought_tabia_hls_ndmi_quality_status_check;

ALTER TABLE tsird.drought_tabia_hls_ndmi
  ADD CONSTRAINT drought_tabia_hls_ndmi_quality_status_check
  CHECK (quality_status IN ('ok', 'limited_observation_coverage',
                            'insufficient_valid_pixel_count',
                            'insufficient_observation_coverage',
                            'insufficient_acquisition_count'));

INSERT INTO tsird.drought_source_catalog
  (source_id, provider, product, access_method, license_summary,
   refresh_expectation, intended_use, enabled)
VALUES
  ('nasa-hls-v2-ndmi-monthly-full-development', 'NASA LP DAAC / Earthdata Cloud',
   'Harmonized Landsat and Sentinel-2 (HLS) v2.0 L30/S30 surface reflectance',
   'CMR-STAC discovery and authenticated COG range reads using an Earthdata token',
   'NASA Earthdata / LP DAAC terms and required HLS attribution; source-specific review required',
   'Manual DEV all-Tabia acquisition only; no schedule',
   'All-Tabia monthly vegetation-moisture evidence review', false)
ON CONFLICT (source_id) DO NOTHING;

COMMIT;
