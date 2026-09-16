BEGIN;

-- Draft-only Tabia rows for transparent historical calibration inspection.
-- A row preserves component evidence but deliberately has no combined priority
-- class: calibration review must happen before a response-priority rule exists.
CREATE TABLE IF NOT EXISTS tsird.drought_priority_tabia_assessment (
  snapshot_id text NOT NULL REFERENCES tsird.drought_priority_snapshot(snapshot_id) ON DELETE CASCADE,
  tsird_tabia_id text NOT NULL REFERENCES tsird.tabia_identity(tsird_tabia_id),
  rainfall_mm numeric,
  rainfall_baseline_median_mm numeric,
  rainfall_percentile numeric,
  rainfall_band text NOT NULL CHECK (rainfall_band IN ('no_signal', 'watch', 'low', 'very_low', 'unavailable')),
  population_decile smallint CHECK (population_decile BETWEEN 1 AND 10),
  cropland_decile smallint CHECK (cropland_decile BETWEEN 1 AND 10),
  nearest_road_m double precision,
  road_context text NOT NULL CHECK (road_context IN ('near', 'intermediate', 'far', 'unavailable')),
  evidence_state text NOT NULL CHECK (evidence_state IN ('eligible_for_review', 'insufficient_coverage', 'unavailable')),
  rationale jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (snapshot_id, tsird_tabia_id)
);

CREATE INDEX IF NOT EXISTS drought_priority_tabia_assessment_snapshot_idx
  ON tsird.drought_priority_tabia_assessment (snapshot_id, rainfall_band);

COMMIT;
