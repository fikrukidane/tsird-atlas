BEGIN;

ALTER TABLE tsird.drought_tabia_preliminary_rainfall
  ADD COLUMN IF NOT EXISTS baseline_median_mm numeric,
  ADD COLUMN IF NOT EXISTS provisional_percentile numeric,
  ADD COLUMN IF NOT EXISTS comparison_status text;

COMMIT;
