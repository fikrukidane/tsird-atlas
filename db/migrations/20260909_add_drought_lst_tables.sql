BEGIN;

CREATE TABLE IF NOT EXISTS tsird.drought_lst_run (
  run_id text PRIMARY KEY,
  source_product text NOT NULL,
  collection_id text NOT NULL,
  observation_at timestamptz NOT NULL,
  native_resolution text NOT NULL,
  raster_path text NOT NULL,
  raster_sha256 text NOT NULL,
  source_retrieved_at timestamptz NOT NULL,
  status text NOT NULL CHECK (status IN ('development','degraded','validated','published','failed')),
  notes text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tsird.drought_tabia_lst (
  run_id text NOT NULL REFERENCES tsird.drought_lst_run(run_id) ON DELETE CASCADE,
  tsird_tabia_id text NOT NULL REFERENCES tsird.tabia_identity(tsird_tabia_id),
  lst_c_mean numeric,
  errorbar_c_mean numeric,
  ppp_mean numeric,
  valid_pixel_count integer NOT NULL,
  grid_cell_count integer NOT NULL,
  coverage_pct numeric NOT NULL,
  qflag_mean numeric,
  quality_status text NOT NULL CHECK (quality_status IN ('ok','insufficient_grid_coverage')),
  PRIMARY KEY (run_id, tsird_tabia_id)
);

COMMIT;
