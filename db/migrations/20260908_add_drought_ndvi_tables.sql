BEGIN;

CREATE TABLE IF NOT EXISTS tsird.drought_ndvi_run (
  run_id text PRIMARY KEY,
  source_product text NOT NULL,
  collection_id text NOT NULL,
  observation_start timestamptz NOT NULL,
  observation_end timestamptz NOT NULL,
  native_resolution text NOT NULL,
  requested_resolution_degrees numeric NOT NULL,
  raster_path text NOT NULL,
  raster_sha256 text NOT NULL,
  source_retrieved_at timestamptz NOT NULL,
  status text NOT NULL CHECK (status IN ('development', 'degraded', 'validated', 'published', 'failed')),
  notes text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tsird.drought_tabia_ndvi (
  run_id text NOT NULL REFERENCES tsird.drought_ndvi_run(run_id) ON DELETE CASCADE,
  tsird_tabia_id text NOT NULL REFERENCES tsird.tabia_identity(tsird_tabia_id),
  ndvi_mean numeric,
  ndvi_median numeric,
  valid_pixel_count integer NOT NULL,
  grid_cell_count integer NOT NULL,
  coverage_pct numeric NOT NULL,
  qflag_nonzero_count integer NOT NULL,
  quality_status text NOT NULL CHECK (quality_status IN ('ok', 'insufficient_grid_coverage')),
  PRIMARY KEY (run_id, tsird_tabia_id)
);

COMMIT;
