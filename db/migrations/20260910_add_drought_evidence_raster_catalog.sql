BEGIN;

INSERT INTO tsird.drought_source_catalog
  (source_id, provider, product, access_method, license_summary, refresh_expectation, intended_use)
VALUES
  ('cdse-clms-ndvi-v3', 'Copernicus Data Space Ecosystem', 'CLMS NDVI v3', 'OAuth client credentials and Process API', 'Copernicus terms and attribution', '10-daily', 'Vegetation-condition evidence'),
  ('cdse-clms-swi-v4', 'Copernicus Data Space Ecosystem', 'CLMS SWI v4', 'OAuth client credentials and Process API', 'Copernicus terms and attribution', '10-daily', 'Coarse soil-water context'),
  ('cdse-clms-lst-v2', 'Copernicus Data Space Ecosystem', 'CLMS LST v2', 'OAuth client credentials and Process API', 'Copernicus terms and attribution', 'Hourly source; retained snapshots', 'Thermal context')
ON CONFLICT (source_id) DO NOTHING;

CREATE TABLE IF NOT EXISTS tsird.drought_evidence_raster (
  evidence_id text PRIMARY KEY,
  source_id text NOT NULL REFERENCES tsird.drought_source_catalog(source_id),
  run_id text NOT NULL,
  evidence_kind text NOT NULL CHECK (evidence_kind IN ('rainfall', 'rapid_rainfall', 'ndvi', 'swi', 'lst', 'wapor_transpiration')),
  observation_start timestamptz NOT NULL,
  observation_end timestamptz NOT NULL,
  native_resolution text NOT NULL,
  raster_paths jsonb NOT NULL,
  raster_sha256 jsonb NOT NULL,
  boundary_set_version text,
  status text NOT NULL CHECK (status IN ('development', 'degraded', 'validated', 'published')),
  quality_summary jsonb NOT NULL DEFAULT '{}'::jsonb,
  provenance jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (source_id, run_id)
);

CREATE INDEX IF NOT EXISTS drought_evidence_raster_timeline_idx
  ON tsird.drought_evidence_raster (source_id, observation_end DESC, created_at DESC);

COMMIT;
