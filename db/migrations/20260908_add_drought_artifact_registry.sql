BEGIN;

-- Operational metadata only: source secrets stay in n8n credentials or local
-- environment files, never in this registry.
CREATE TABLE IF NOT EXISTS tsird.drought_source_catalog (
  source_id text PRIMARY KEY,
  provider text NOT NULL,
  product text NOT NULL,
  access_method text NOT NULL,
  license_summary text NOT NULL,
  refresh_expectation text NOT NULL,
  intended_use text NOT NULL,
  enabled boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tsird.drought_artifact_registry (
  artifact_id text PRIMARY KEY,
  artifact_type text NOT NULL CHECK (artifact_type IN (
    'observed_rainfall', 'seasonal_outlook', 'road_accessibility',
    'humanitarian_access', 'assistance_coverage', 'food_security_pressure'
  )),
  source_id text NOT NULL REFERENCES tsird.drought_source_catalog(source_id),
  run_id text NOT NULL,
  status text NOT NULL CHECK (status IN ('development', 'validated', 'published', 'degraded', 'failed', 'superseded')),
  valid_from timestamptz,
  valid_to timestamptz,
  ingested_at timestamptz NOT NULL DEFAULT now(),
  native_resolution text NOT NULL,
  geography_scope text NOT NULL,
  boundary_set_version text,
  quality_summary jsonb NOT NULL DEFAULT '{}'::jsonb,
  provenance jsonb NOT NULL DEFAULT '{}'::jsonb,
  reviewer text,
  reviewed_at timestamptz,
  supersedes_artifact_id text REFERENCES tsird.drought_artifact_registry(artifact_id),
  UNIQUE (artifact_type, run_id)
);

CREATE INDEX IF NOT EXISTS drought_artifact_registry_current_idx
  ON tsird.drought_artifact_registry (artifact_type, status, valid_to DESC);

INSERT INTO tsird.drought_source_catalog
  (source_id, provider, product, access_method, license_summary, refresh_expectation, intended_use)
VALUES
  ('chc-chirps-v3', 'Climate Hazards Center', 'CHIRPS v3 rainfall', 'Open file retrieval', 'Cite provider and product terms', 'Preliminary pentad; final monthly', 'Observed rainfall anomaly'),
  ('igad-icpac-monitoring', 'ICPAC / IGAD', 'Climate monitoring products', 'Portal or documented service', 'Confirm product-specific terms', 'Product-specific', 'Regional monitoring cross-check'),
  ('igad-icpac-seasonal', 'ICPAC / IGAD', 'Seasonal outlook', 'Published seasonal product', 'Confirm product-specific terms', 'Seasonal', 'Native-scale outlook probabilities'),
  ('fao-wapor-v3', 'FAO', 'WaPOR v3', 'Open API', 'FAO WaPOR terms and attribution', 'Near-real-time product cadence', 'Agricultural water/vegetation stress'),
  ('fews-net-fdw', 'FEWS NET', 'Data Warehouse / Livelihoods Explorer', 'API with permission-aware retrieval', 'Use only permitted source series', 'Series-specific', 'Markets and livelihood context'),
  ('wfp-logistics-cluster', 'WFP Logistics Cluster', 'Physical access constraints', 'Human-reviewed published operational product', 'Confirm source terms and sensitivity', 'Event-driven', 'Dated physical access constraints')
ON CONFLICT (source_id) DO NOTHING;
COMMIT;
