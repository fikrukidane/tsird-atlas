BEGIN;

-- FOBS is a V3 source-observation fraction, not the v2 PPP field.  Retaining
-- it separately avoids re-labelling a different provider diagnostic.
ALTER TABLE tsird.drought_tabia_lst
  ADD COLUMN IF NOT EXISTS fobs_mean numeric;

COMMIT;
