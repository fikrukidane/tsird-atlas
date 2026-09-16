BEGIN;

-- A replay is a draft, observed-evidence planning exercise.  These fields are
-- intentionally separate from the original calibration evidence so a map can
-- state the configured rule and action behind a class without pretending that
-- it is a forecast, allocation, IPC phase, or food-security determination.
ALTER TABLE tsird.drought_priority_tabia_assessment
  ADD COLUMN IF NOT EXISTS assessment_kind text NOT NULL DEFAULT 'historical_calibration_preview'
    CHECK (assessment_kind IN ('historical_calibration_preview', 'historical_priority_replay')),
  ADD COLUMN IF NOT EXISTS priority_class text
    CHECK (priority_class IN ('critical', 'high', 'moderate', 'watch', 'insufficient_evidence')),
  ADD COLUMN IF NOT EXISTS priority_rank smallint
    CHECK (priority_rank BETWEEN 0 AND 4),
  ADD COLUMN IF NOT EXISTS planning_action text,
  ADD COLUMN IF NOT EXISTS triggered_rules jsonb NOT NULL DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS input_quality jsonb NOT NULL DEFAULT '{}'::jsonb;

CREATE INDEX IF NOT EXISTS drought_priority_tabia_assessment_replay_idx
  ON tsird.drought_priority_tabia_assessment (snapshot_id, assessment_kind, priority_rank DESC);

COMMIT;
