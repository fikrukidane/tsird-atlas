BEGIN;

CREATE TABLE IF NOT EXISTS tsird.drought_preliminary_rainfall_run (
  run_id text PRIMARY KEY,
  source_product text NOT NULL,
  period_start date NOT NULL,
  period_end date NOT NULL,
  pentad_count smallint NOT NULL CHECK (pentad_count BETWEEN 1 AND 12),
  source_latest_at timestamptz,
  status text NOT NULL CHECK (status IN ('development', 'degraded', 'validated', 'published', 'failed')),
  notes text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tsird.drought_tabia_preliminary_rainfall (
  run_id text NOT NULL REFERENCES tsird.drought_preliminary_rainfall_run(run_id) ON DELETE CASCADE,
  tsird_tabia_id text NOT NULL REFERENCES tsird.tabia_identity(tsird_tabia_id),
  rainfall_mm numeric,
  grid_cell_count integer NOT NULL,
  coverage_pct numeric NOT NULL,
  quality_status text NOT NULL CHECK (quality_status IN ('ok', 'insufficient_grid_coverage')),
  PRIMARY KEY (run_id, tsird_tabia_id)
);

COMMIT;
