BEGIN;

-- Keep the original 20-Tabia pilot immutable in meaning, while allowing a
-- separately labelled, all-Tabia DEV run.  This migration never touches a
-- production schema or a production release.
ALTER TABLE tsird.drought_sentinel2_ndmi_run
  RENAME COLUMN pilot_tabia_limit TO tabia_count;

ALTER TABLE tsird.drought_sentinel2_ndmi_run
  DROP CONSTRAINT IF EXISTS drought_sentinel2_ndmi_run_pilot_tabia_limit_check;

ALTER TABLE tsird.drought_sentinel2_ndmi_run
  ADD CONSTRAINT drought_sentinel2_ndmi_run_tabia_count_check
  CHECK (tabia_count > 0 AND tabia_count <= 748);

ALTER TABLE tsird.drought_sentinel2_ndmi_run
  ADD COLUMN IF NOT EXISTS run_scope text NOT NULL DEFAULT 'technical_pilot'
  CHECK (run_scope IN ('technical_pilot', 'full_development'));

INSERT INTO tsird.drought_source_catalog
  (source_id, provider, product, access_method, license_summary, refresh_expectation, intended_use, enabled)
VALUES
  ('cdse-sentinel2-l2a-ndmi-full-development', 'Copernicus Data Space Ecosystem',
   'Sentinel-2 Level-2A B08/B11 masked NDMI',
   'OAuth client credentials and Sentinel Hub Statistical API',
   'Copernicus terms and attribution; source-specific review required',
   'Manual DEV acquisition only; no schedule',
   'All-Tabia observed vegetation-moisture context review', false)
ON CONFLICT (source_id) DO NOTHING;

COMMIT;
