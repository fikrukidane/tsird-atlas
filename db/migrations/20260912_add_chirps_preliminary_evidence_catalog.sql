BEGIN;

INSERT INTO tsird.drought_source_catalog
  (source_id, provider, product, access_method, license_summary, refresh_expectation, intended_use)
VALUES
  ('chc-chirps-v3-preliminary', 'Climate Hazards Center', 'CHIRPS v3 preliminary pentad',
   'Public African preliminary pentad GeoTIFF archive', 'CHIRPS attribution and provider terms',
   'Pentadal, preliminary', 'Rapid observed rainfall accumulation; no drought or food-security classification')
ON CONFLICT (source_id) DO NOTHING;

COMMIT;
