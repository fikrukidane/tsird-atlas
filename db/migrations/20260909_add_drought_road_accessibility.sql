BEGIN;

INSERT INTO tsird.drought_source_catalog
  (source_id, provider, product, access_method, license_summary, refresh_expectation, intended_use)
VALUES
  ('tsird-tigray-roads', 'TSIRD local data', 'Tigray road network baseline',
   'Versioned local PostGIS source', 'Internal source; record source revision before publication',
   'Refresh when a reviewed road-network revision is available', 'Tabia all-weather-road proximity')
ON CONFLICT (source_id) DO NOTHING;

CREATE TABLE IF NOT EXISTS tsird.drought_road_accessibility_run (
  run_id text PRIMARY KEY,
  source_product text NOT NULL,
  main_road_definition text NOT NULL,
  boundary_set_version text NOT NULL,
  status text NOT NULL CHECK (status IN ('development', 'validated', 'published', 'degraded', 'failed')),
  source_feature_count integer NOT NULL,
  notes text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tsird.drought_tabia_road_accessibility (
  run_id text NOT NULL REFERENCES tsird.drought_road_accessibility_run(run_id) ON DELETE CASCADE,
  tsird_tabia_id text NOT NULL REFERENCES public.tigray_tabias_ws(tsird_tabia_id),
  nearest_all_weather_road_m double precision NOT NULL CHECK (nearest_all_weather_road_m >= 0),
  all_weather_road_intersects boolean NOT NULL,
  quality_status text NOT NULL CHECK (quality_status IN ('ok', 'unavailable')),
  PRIMARY KEY (run_id, tsird_tabia_id)
);

CREATE INDEX IF NOT EXISTS drought_tabia_road_accessibility_run_idx
  ON tsird.drought_tabia_road_accessibility (run_id, tsird_tabia_id);

COMMIT;
