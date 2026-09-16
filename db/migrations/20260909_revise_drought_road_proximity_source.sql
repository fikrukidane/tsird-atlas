BEGIN;

ALTER TABLE tsird.drought_tabia_road_accessibility
  RENAME COLUMN nearest_all_weather_road_m TO nearest_road_m;
ALTER TABLE tsird.drought_tabia_road_accessibility
  RENAME COLUMN all_weather_road_intersects TO tigray_roads_2006_intersects;

INSERT INTO tsird.drought_source_catalog
  (source_id, provider, product, access_method, license_summary, refresh_expectation, intended_use)
VALUES
  ('tsird-tigray-roads-2006t', 'TSIRD local data', 'Tigray Roads 2006 (ERA + TRRA)',
   'Local published Atlas shapefile: data/gold/atlas_4326/TigrayRoads2006t.shp',
   'Internal source; record source revision before publication',
   'Refresh when a reviewed road-network revision is available',
   'Tabia straight-line proximity to mapped ERA and TRRA road-network features')
ON CONFLICT (source_id) DO UPDATE SET
  product=EXCLUDED.product, access_method=EXCLUDED.access_method, intended_use=EXCLUDED.intended_use;

COMMIT;
