BEGIN;

INSERT INTO tsird.drought_source_catalog
  (source_id, provider, product, access_method, license_summary, refresh_expectation, intended_use)
VALUES
  ('fao-wapor-v3', 'Food and Agriculture Organization of the United Nations',
   'WaPOR v3 Level 2 dekadal transpiration (T) and actual evapotranspiration and interception (AETI)',
   'Public FAO GISMGR v2 catalogue API and provider Cloud Optimized GeoTIFF subsets; no credential required',
   'Open FAO WaPOR access; retain provider/product attribution and verify terms before production publication',
   'Dekadal; near-real-time releases may later be replaced by provider final revisions',
   'Agricultural water-use and vegetation-water-use context; not crop extent, yield, food insecurity, or response priority')
ON CONFLICT (source_id) DO UPDATE SET
  product=EXCLUDED.product, access_method=EXCLUDED.access_method, license_summary=EXCLUDED.license_summary,
  refresh_expectation=EXCLUDED.refresh_expectation, intended_use=EXCLUDED.intended_use;

CREATE TABLE IF NOT EXISTS tsird.drought_wapor_run (
  run_id text PRIMARY KEY,
  source_id text NOT NULL REFERENCES tsird.drought_source_catalog(source_id),
  mapset_code text NOT NULL,
  aeti_mapset_code text NOT NULL,
  source_period_start date NOT NULL,
  source_period_end date NOT NULL,
  source_revision text NOT NULL CHECK (source_revision IN ('nrt', 'final', 'unknown')),
  native_resolution text NOT NULL,
  transpiration_raster_path text NOT NULL,
  aeti_raster_path text NOT NULL,
  transpiration_sha256 text NOT NULL,
  aeti_sha256 text NOT NULL,
  source_urls jsonb NOT NULL,
  source_retrieved_at timestamptz NOT NULL,
  status text NOT NULL CHECK (status IN ('development', 'validated', 'published', 'degraded', 'failed')),
  notes text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tsird.drought_tabia_wapor (
  run_id text NOT NULL REFERENCES tsird.drought_wapor_run(run_id) ON DELETE CASCADE,
  tsird_tabia_id text NOT NULL REFERENCES tsird.tabia_identity(tsird_tabia_id),
  transpiration_mm numeric,
  aeti_mm numeric,
  valid_pixel_count integer NOT NULL CHECK (valid_pixel_count >= 0),
  grid_cell_count integer NOT NULL CHECK (grid_cell_count >= 0),
  coverage_pct numeric NOT NULL CHECK (coverage_pct >= 0 AND coverage_pct <= 100),
  quality_status text NOT NULL CHECK (quality_status IN ('ok', 'insufficient_grid_coverage')),
  PRIMARY KEY (run_id, tsird_tabia_id)
);

CREATE INDEX IF NOT EXISTS drought_tabia_wapor_run_idx
  ON tsird.drought_tabia_wapor (run_id, tsird_tabia_id);

COMMIT;
