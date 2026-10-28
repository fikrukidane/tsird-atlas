BEGIN;

-- DEV-only provenance for the second HLS feasibility pilot.  This keeps the
-- original observation-weighted pilot intact and records the scientifically
-- relevant, pixel-level monthly support for each mask profile separately.
CREATE TABLE IF NOT EXISTS tsird.drought_tabia_hls_ndmi_profile (
  run_id text NOT NULL REFERENCES tsird.drought_hls_ndmi_run(run_id) ON DELETE CASCADE,
  tsird_tabia_id text NOT NULL REFERENCES tsird.tabia_identity(tsird_tabia_id),
  mask_profile text NOT NULL CHECK (mask_profile IN ('strict', 'adjacency_allowed')),
  ndmi_mean numeric,
  ndmi_median numeric,
  spatial_coverage_pct numeric NOT NULL CHECK (spatial_coverage_pct >= 0 AND spatial_coverage_pct <= 100),
  two_observation_coverage_pct numeric NOT NULL CHECK (two_observation_coverage_pct >= 0 AND two_observation_coverage_pct <= 100),
  median_valid_observation_count numeric,
  valid_spatial_pixel_count integer NOT NULL CHECK (valid_spatial_pixel_count >= 0),
  total_eligible_pixel_count integer NOT NULL CHECK (total_eligible_pixel_count >= valid_spatial_pixel_count),
  valid_observation_pixel_count integer NOT NULL CHECK (valid_observation_pixel_count >= 0),
  candidate_acquisition_count integer NOT NULL CHECK (candidate_acquisition_count >= 0),
  usable_acquisition_count integer NOT NULL CHECK (usable_acquisition_count >= 0 AND usable_acquisition_count <= candidate_acquisition_count),
  adjacency_accepted_pixel_count integer NOT NULL CHECK (adjacency_accepted_pixel_count >= 0),
  first_acquisition_at timestamptz,
  last_acquisition_at timestamptz,
  median_acquisition_at timestamptz,
  evidence_tier text NOT NULL CHECK (evidence_tier IN ('adequate', 'limited', 'insufficient')),
  PRIMARY KEY (run_id, tsird_tabia_id, mask_profile)
);

COMMIT;
