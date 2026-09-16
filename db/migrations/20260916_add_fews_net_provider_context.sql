BEGIN;
CREATE TABLE IF NOT EXISTS tsird.drought_fews_net_context_run (
  run_id text PRIMARY KEY, issued_at date NOT NULL, valid_from date, valid_to date,
  source_url text NOT NULL, status text NOT NULL DEFAULT 'development',
  source_note text NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS tsird.drought_fews_net_context_feature (
  run_id text NOT NULL REFERENCES tsird.drought_fews_net_context_run(run_id) ON DELETE CASCADE,
  feature_id text NOT NULL, geometry geometry(Geometry,4326) NOT NULL, properties jsonb NOT NULL DEFAULT '{}'::jsonb,
  PRIMARY KEY (run_id, feature_id)
);
CREATE INDEX IF NOT EXISTS drought_fews_net_context_feature_geometry_idx ON tsird.drought_fews_net_context_feature USING gist(geometry);
COMMIT;
