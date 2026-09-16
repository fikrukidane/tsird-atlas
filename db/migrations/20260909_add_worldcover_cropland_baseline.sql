BEGIN;

INSERT INTO tsird.drought_source_catalog
  (source_id, provider, product, access_method, license_summary, refresh_expectation, intended_use)
VALUES
  ('esa-worldcover-2021-v200', 'ESA WorldCover', 'WorldCover 2021 v200 land cover, cropland class 40, 10 m',
   'Public ESA WorldCover 3 by 3 degree Cloud Optimized GeoTIFF tiles',
   'CC BY 4.0; retain ESA WorldCover and Copernicus attribution',
   'Static 2021 reference baseline; replace only after reviewed source selection',
   'Tabia cropland-share baseline; not current cultivated area, production, food insecurity, or priority')
ON CONFLICT (source_id) DO UPDATE SET
  product=EXCLUDED.product, access_method=EXCLUDED.access_method, license_summary=EXCLUDED.license_summary,
  refresh_expectation=EXCLUDED.refresh_expectation, intended_use=EXCLUDED.intended_use;

CREATE TABLE IF NOT EXISTS tsird.drought_cropland_run (
  run_id text PRIMARY KEY,
  source_id text NOT NULL REFERENCES tsird.drought_source_catalog(source_id),
  source_year integer NOT NULL,
  source_release text NOT NULL,
  source_urls jsonb NOT NULL,
  source_sha256 jsonb NOT NULL,
  native_resolution text NOT NULL,
  cropland_class integer NOT NULL,
  boundary_set_version text NOT NULL,
  status text NOT NULL CHECK (status IN ('development', 'validated', 'published', 'degraded', 'failed')),
  source_feature_note text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tsird.drought_tabia_cropland (
  run_id text NOT NULL REFERENCES tsird.drought_cropland_run(run_id) ON DELETE CASCADE,
  tsird_tabia_id text NOT NULL REFERENCES public.tigray_tabias_ws(tsird_tabia_id),
  cropland_pct double precision NOT NULL CHECK (cropland_pct >= 0 AND cropland_pct <= 100),
  cropland_area_ha double precision NOT NULL CHECK (cropland_area_ha >= 0),
  valid_pixel_count integer NOT NULL CHECK (valid_pixel_count >= 0),
  total_pixel_count integer NOT NULL CHECK (total_pixel_count >= 0),
  coverage_pct double precision NOT NULL CHECK (coverage_pct >= 0 AND coverage_pct <= 100),
  quality_status text NOT NULL CHECK (quality_status IN ('ok', 'insufficient_coverage', 'unavailable')),
  PRIMARY KEY (run_id, tsird_tabia_id)
);

CREATE INDEX IF NOT EXISTS drought_tabia_cropland_run_idx
  ON tsird.drought_tabia_cropland (run_id, tsird_tabia_id);

COMMIT;
