BEGIN;
CREATE TABLE IF NOT EXISTS tsird.drought_rainfall_run (
  run_id text PRIMARY KEY,
  source_product text NOT NULL,
  source_version text NOT NULL,
  analysis_year integer NOT NULL,
  season_months smallint[] NOT NULL,
  baseline_year_start integer NOT NULL,
  baseline_year_end integer NOT NULL,
  source_latest_month date NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  status text NOT NULL CHECK (status IN ('development', 'validated', 'published')),
  notes text NOT NULL
);
CREATE TABLE IF NOT EXISTS tsird.drought_tabia_rainfall_condition (
  run_id text NOT NULL REFERENCES tsird.drought_rainfall_run(run_id),
  tsird_tabia_id text NOT NULL REFERENCES tsird.tabia_identity(tsird_tabia_id),
  rainfall_mm numeric,
  baseline_median_mm numeric,
  percentile numeric,
  condition_class text NOT NULL,
  grid_cell_count integer NOT NULL,
  coverage_pct numeric NOT NULL,
  quality_status text NOT NULL,
  PRIMARY KEY (run_id, tsird_tabia_id)
);
COMMIT;
