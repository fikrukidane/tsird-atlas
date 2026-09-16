BEGIN;

-- A single local-development configuration may be selected for the draft
-- Priority Review calculation.  This is not publication: snapshots remain
-- draft-only until a later review/publishing workflow exists.
ALTER TABLE tsird.drought_priority_model_configuration
  ADD COLUMN IF NOT EXISTS active_for_review boolean NOT NULL DEFAULT false;

UPDATE tsird.drought_priority_model_configuration
SET active_for_review = true
WHERE configuration_id = 'sarsrp-v0-1-foundation'
  AND NOT EXISTS (
    SELECT 1 FROM tsird.drought_priority_model_configuration WHERE active_for_review
  );

CREATE UNIQUE INDEX IF NOT EXISTS drought_priority_model_configuration_one_active_review_idx
  ON tsird.drought_priority_model_configuration ((active_for_review))
  WHERE active_for_review;

COMMIT;
