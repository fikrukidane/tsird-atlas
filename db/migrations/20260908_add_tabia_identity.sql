-- TSIRD canonical identity for the currently loaded Tabia boundary release.
-- Source T8ID is retained unchanged: the supplied dataset does not make it unique.

BEGIN;

CREATE SCHEMA IF NOT EXISTS tsird;

CREATE TABLE IF NOT EXISTS tsird.tabia_identity (
  tsird_tabia_id text PRIMARY KEY,
  boundary_set_version text NOT NULL,
  source_feature_id integer NOT NULL,
  source_t8id text,
  source_name_en text,
  source_woreda_en text,
  geometry_fingerprint text NOT NULL,
  source_t8id_occurrences integer NOT NULL,
  review_required boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (boundary_set_version, source_feature_id)
);

ALTER TABLE tigray_tabias_ws ADD COLUMN IF NOT EXISTS tsird_tabia_id text;
ALTER TABLE tigray_tabias_ws ADD COLUMN IF NOT EXISTS tsird_boundary_version text;

WITH prepared AS (
  SELECT gid, COALESCE("T8ID", '') AS source_t8id,
    COALESCE("TABIA", '') AS source_name_en,
    COALESCE("WEREDA", '') AS source_woreda_en,
    md5(encode(ST_AsEWKB(geometry), 'hex')) AS geometry_fingerprint,
    count(*) OVER (PARTITION BY "T8ID") AS source_t8id_occurrences
  FROM tigray_tabias_ws
)
UPDATE tigray_tabias_ws tabia
SET tsird_tabia_id = 'tsird-tabia-v1-' || md5(concat_ws('|',
      'TigraiTabiasNew', prepared.source_t8id,
      upper(btrim(prepared.source_name_en)), upper(btrim(prepared.source_woreda_en)),
      prepared.geometry_fingerprint)),
    tsird_boundary_version = 'tsird-tabias-v1'
FROM prepared WHERE tabia.gid = prepared.gid;

ALTER TABLE tigray_tabias_ws ALTER COLUMN tsird_tabia_id SET NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS tigray_tabias_ws_tsird_tabia_id_key
  ON tigray_tabias_ws (tsird_tabia_id);
CREATE INDEX IF NOT EXISTS tigray_tabias_ws_source_t8id_idx
  ON tigray_tabias_ws ("T8ID");

WITH prepared AS (
  SELECT gid AS source_feature_id, tsird_tabia_id,
    tsird_boundary_version AS boundary_set_version,
    COALESCE("T8ID", '') AS source_t8id,
    COALESCE("TABIA", '') AS source_name_en,
    COALESCE("WEREDA", '') AS source_woreda_en,
    md5(encode(ST_AsEWKB(geometry), 'hex')) AS geometry_fingerprint,
    count(*) OVER (PARTITION BY "T8ID") AS source_t8id_occurrences
  FROM tigray_tabias_ws
)
INSERT INTO tsird.tabia_identity (
  tsird_tabia_id, boundary_set_version, source_feature_id, source_t8id,
  source_name_en, source_woreda_en, geometry_fingerprint,
  source_t8id_occurrences, review_required
)
SELECT tsird_tabia_id, boundary_set_version, source_feature_id, source_t8id,
  source_name_en, source_woreda_en, geometry_fingerprint,
  source_t8id_occurrences, source_t8id_occurrences > 1
FROM prepared
ON CONFLICT (tsird_tabia_id) DO UPDATE SET
  boundary_set_version = EXCLUDED.boundary_set_version,
  source_feature_id = EXCLUDED.source_feature_id,
  source_t8id = EXCLUDED.source_t8id,
  source_name_en = EXCLUDED.source_name_en,
  source_woreda_en = EXCLUDED.source_woreda_en,
  geometry_fingerprint = EXCLUDED.geometry_fingerprint,
  source_t8id_occurrences = EXCLUDED.source_t8id_occurrences,
  review_required = EXCLUDED.review_required;

COMMIT;
