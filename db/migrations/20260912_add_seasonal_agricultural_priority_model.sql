BEGIN;

-- This schema stores only transparent, reviewable model definitions and future
-- draft-result provenance. It does not calculate a score, assign an IPC phase,
-- or permit automatic publication.
CREATE TABLE IF NOT EXISTS tsird.drought_priority_model_configuration (
  configuration_id text PRIMARY KEY,
  model_name text NOT NULL DEFAULT 'Seasonal Agricultural Stress & Response Priority',
  version integer NOT NULL CHECK (version > 0),
  status text NOT NULL CHECK (status IN ('draft', 'published', 'retired')),
  purpose text NOT NULL,
  geography_scope text NOT NULL DEFAULT 'tabia_with_woreda_rollup',
  horizon_months smallint NOT NULL DEFAULT 3 CHECK (horizon_months BETWEEN 1 AND 3),
  configuration jsonb NOT NULL,
  rationale text NOT NULL,
  created_by text NOT NULL DEFAULT 'local-development',
  created_at timestamptz NOT NULL DEFAULT now(),
  reviewed_by text,
  reviewed_at timestamptz,
  published_by text,
  published_at timestamptz,
  CHECK ((status <> 'published') OR (published_by IS NOT NULL AND published_at IS NOT NULL)),
  UNIQUE (model_name, version)
);

-- A published definition is a permanent record. A changed rule must become a
-- new draft/version, preserving reproducibility of any future priority result.
CREATE OR REPLACE FUNCTION tsird.prevent_published_priority_model_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF TG_OP = 'DELETE' AND OLD.status = 'published' THEN
    RAISE EXCEPTION 'Published priority model configurations cannot be deleted';
  END IF;
  IF TG_OP = 'UPDATE' AND OLD.status = 'published' THEN
    RAISE EXCEPTION 'Published priority model configurations cannot be modified; create a new draft version';
  END IF;
  RETURN COALESCE(NEW, OLD);
END;
$$;

DROP TRIGGER IF EXISTS drought_priority_model_configuration_immutable_published
  ON tsird.drought_priority_model_configuration;
CREATE TRIGGER drought_priority_model_configuration_immutable_published
  BEFORE UPDATE OR DELETE ON tsird.drought_priority_model_configuration
  FOR EACH ROW EXECUTE FUNCTION tsird.prevent_published_priority_model_mutation();

-- A snapshot may be created only by a later fixed runner endpoint. The result
-- is deliberately draft-only at this stage; no column represents a famine,
-- hunger, or IPC classification.
CREATE TABLE IF NOT EXISTS tsird.drought_priority_snapshot (
  snapshot_id text PRIMARY KEY,
  configuration_id text NOT NULL REFERENCES tsird.drought_priority_model_configuration(configuration_id),
  status text NOT NULL CHECK (status IN ('draft', 'reviewed', 'published', 'superseded', 'failed')),
  decision_kind text NOT NULL CHECK (decision_kind IN ('three_month_outlook', 'observed_stress_response_readiness')),
  issued_at timestamptz NOT NULL,
  evidence_cutoff_at timestamptz NOT NULL,
  valid_from date NOT NULL,
  valid_to date NOT NULL,
  boundary_set_version text NOT NULL,
  source_run_ids jsonb NOT NULL DEFAULT '{}'::jsonb,
  quality_gate jsonb NOT NULL DEFAULT '{}'::jsonb,
  methodology jsonb NOT NULL DEFAULT '{}'::jsonb,
  review_note text,
  reviewed_by text,
  reviewed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (valid_to >= valid_from),
  CHECK ((decision_kind = 'three_month_outlook') OR status <> 'published')
);

CREATE INDEX IF NOT EXISTS drought_priority_snapshot_current_idx
  ON tsird.drought_priority_snapshot (status, valid_from, valid_to, issued_at DESC);

-- Initial foundation definition: intentionally draft-only and non-executable.
-- Components requiring unbuilt seasonal baselines are explicitly disabled;
-- this record documents the proposed configuration rather than smuggling in a
-- score before calibration and practitioner review.
INSERT INTO tsird.drought_priority_model_configuration (
  configuration_id, version, status, purpose, configuration, rationale
) VALUES (
  'sarsrp-v0-1-foundation',
  1,
  'draft',
  'Transparent three-month Tabia-first agricultural-stress and response-planning aid; not a food-security classification.',
  '{
    "decision_window": {"horizon_months": 3, "starts": "first_day_of_next_month", "timezone": "Africa/Addis_Ababa"},
    "outlook_policy": {"required_for_three_month_outlook": true, "fallback_kind": "observed_stress_response_readiness", "woreda_context_only": true},
    "observed_stress": {
      "rainfall": {"enabled": true, "standardization": "tabia_same_month_chirps_1991_2020_median_and_percentile", "weight": null},
      "ndvi": {"enabled": false, "reason": "seasonal baseline pending validation", "weight": null},
      "wapor": {"enabled": false, "reason": "same_dekad baseline and crop-calendar review pending", "weight": null},
      "swi": {"enabled": false, "reason": "coarse context only; cannot discriminate Tabia priority", "weight": null},
      "thermal": {"enabled": false, "reason": "provider-compatible historical baseline unavailable", "weight": null}
    },
    "exposure": {
      "population": {"enabled": true, "standardization": "separate_tabia_decile", "reference": "WorldPop baseline"},
      "cropland": {"enabled": true, "standardization": "separate_tabia_decile", "reference": "ESA WorldCover 2021 baseline"},
      "road_proximity": {"enabled": true, "role": "response_access_tag_only", "reference": "ERAA/TRRA historical roads"}
    },
    "sensitivity": {
      "terrain": {"enabled": false, "reason": "direction and thresholds require practitioner review"},
      "soil": {"enabled": false, "reason": "source attributes and scale require practitioner review"}
    },
    "publication": {"automatic": false, "admin_review_required": true, "result_classes": 10}
  }'::jsonb,
  'Initial non-executable foundation. It records agreed scope and exclusions before calibration, source-baseline work, outlook approval, and practitioner review.'
) ON CONFLICT (configuration_id) DO NOTHING;

COMMIT;
