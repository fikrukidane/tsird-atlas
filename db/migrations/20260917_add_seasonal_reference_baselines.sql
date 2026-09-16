BEGIN;

ALTER TABLE tsird.drought_ndvi_run
  ADD COLUMN IF NOT EXISTS seasonal_reference_candidate_only boolean NOT NULL DEFAULT false;
ALTER TABLE tsird.drought_wapor_run
  ADD COLUMN IF NOT EXISTS seasonal_reference_candidate_only boolean NOT NULL DEFAULT false;

CREATE TABLE IF NOT EXISTS tsird.drought_seasonal_reference_run (
  reference_id text PRIMARY KEY,
  candidate_start_year integer NOT NULL,
  candidate_end_year integer NOT NULL,
  method_version text NOT NULL,
  minimum_valid_years integer NOT NULL,
  status text NOT NULL CHECK (status IN ('candidate_review_required', 'validated', 'retired')),
  notes text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tsird.drought_tabia_ndvi_seasonal_reference (
  reference_id text NOT NULL REFERENCES tsird.drought_seasonal_reference_run(reference_id) ON DELETE CASCADE,
  tsird_tabia_id text NOT NULL REFERENCES tsird.tabia_identity(tsird_tabia_id),
  calendar_month integer NOT NULL CHECK (calendar_month BETWEEN 1 AND 12),
  valid_year_count integer NOT NULL,
  median_value numeric NOT NULL,
  p20_value numeric NOT NULL,
  p80_value numeric NOT NULL,
  PRIMARY KEY (reference_id, tsird_tabia_id, calendar_month)
);

CREATE TABLE IF NOT EXISTS tsird.drought_tabia_wapor_seasonal_reference (
  reference_id text NOT NULL REFERENCES tsird.drought_seasonal_reference_run(reference_id) ON DELETE CASCADE,
  tsird_tabia_id text NOT NULL REFERENCES tsird.tabia_identity(tsird_tabia_id),
  calendar_month integer NOT NULL CHECK (calendar_month BETWEEN 1 AND 12),
  valid_year_count integer NOT NULL,
  median_transpiration_mm numeric NOT NULL,
  p20_transpiration_mm numeric NOT NULL,
  p80_transpiration_mm numeric NOT NULL,
  PRIMARY KEY (reference_id, tsird_tabia_id, calendar_month)
);

CREATE INDEX IF NOT EXISTS drought_ndvi_seasonal_reference_lookup_idx
  ON tsird.drought_tabia_ndvi_seasonal_reference (tsird_tabia_id, calendar_month, reference_id);
CREATE INDEX IF NOT EXISTS drought_wapor_seasonal_reference_lookup_idx
  ON tsird.drought_tabia_wapor_seasonal_reference (tsird_tabia_id, calendar_month, reference_id);

COMMIT;
