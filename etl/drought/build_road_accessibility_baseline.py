"""Build a transparent Tabia proximity baseline from ERA/TRRA Tigray Roads 2006."""
import json
import os
import subprocess
from datetime import datetime, timezone

import psycopg2


SOURCE_PATH = "/data/gold/atlas_4326/TigrayRoads2006t.shp"
SOURCE_TABLE = "staging.tigray_roads_2006t_src"
ROAD_DEFINITION = "Nearest ERA or TRRA-owned feature in the local published Tigray Roads 2006 layer; straight-line distance from a Tabia point-on-surface, not travel time, road quality, seasonal passability, or humanitarian access."
OFFICIAL_ROAD_OWNERS = ("ERA", "TRRA")


def dsn():
    return " ".join(("host=tsird-postgis", "port=5432", f"dbname={os.environ['POSTGRES_DB']}",
                     f"user={os.environ['POSTGRES_USER']}", f"password={os.environ['POSTGRES_PASSWORD']}"))


def import_source():
    """Replace the local staging copy from the exact Atlas-published road layer."""
    pg = " ".join(("PG:host=tsird-postgis", "port=5432", f"dbname={os.environ['POSTGRES_DB']}",
                   f"user={os.environ['POSTGRES_USER']}", f"password={os.environ['POSTGRES_PASSWORD']}"))
    subprocess.run([
        "ogr2ogr", "-f", "PostgreSQL", pg, SOURCE_PATH,
        "-nln", SOURCE_TABLE, "-overwrite", "-nlt", "PROMOTE_TO_MULTI",
        "-lco", "GEOMETRY_NAME=geom", "-lco", "FID=source_gid",
    ], check=True, stdout=subprocess.DEVNULL)


def main():
    import_source()
    run_id = f"tsird-tigray-roads-2006-era-trra-proximity-{datetime.now(timezone.utc):%Y%m%d}"
    with psycopg2.connect(dsn()) as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*), coalesce(max(tsird_boundary_version), 'unknown') FROM public.tigray_tabias_ws")
        tabia_count, boundary_version = cur.fetchone()
        cur.execute(f"SELECT count(*) FROM {SOURCE_TABLE} WHERE geom IS NOT NULL AND upper(trim(owner)) = ANY(%s)", (list(OFFICIAL_ROAD_OWNERS),))
        road_count = cur.fetchone()[0]
        if not road_count:
            raise ValueError("no Tigray Roads 2006 features found")
        cur.execute("""
          INSERT INTO tsird.drought_road_accessibility_run
            (run_id, source_product, main_road_definition, boundary_set_version, status, source_feature_count, notes)
          VALUES (%s, %s, %s, %s, 'development', %s, %s)
          ON CONFLICT (run_id) DO UPDATE SET created_at=now(), status='development',
            source_feature_count=EXCLUDED.source_feature_count, notes=EXCLUDED.notes
        """, (run_id, "TSIRD Tigray Roads 2006 (ERA + TRRA)", ROAD_DEFINITION, boundary_version, road_count,
              "Development baseline only. Uses mapped ERA and TRRA features in TigrayRoads2006t; distance is not travel time, road condition, seasonal passability, or humanitarian access."))
        cur.execute("""
          WITH source_roads AS (
            SELECT ST_Transform(geom, 32637) AS geom
            FROM staging.tigray_roads_2006t_src
            WHERE geom IS NOT NULL AND upper(trim(owner)) = ANY(%s)
          ), tabias AS (
            SELECT tsird_tabia_id, geometry, ST_Transform(ST_PointOnSurface(geometry), 32637) AS representative_point
            FROM public.tigray_tabias_ws
          ), measurements AS (
            SELECT t.tsird_tabia_id,
                   ST_Distance(t.representative_point, nearest.geom) AS nearest_m,
                   EXISTS (SELECT 1 FROM source_roads r WHERE ST_Intersects(ST_Transform(t.geometry, 32637), r.geom)) AS intersects_road
            FROM tabias t
            CROSS JOIN LATERAL (
              SELECT geom FROM source_roads ORDER BY t.representative_point <-> geom LIMIT 1
            ) nearest
          )
          INSERT INTO tsird.drought_tabia_road_accessibility
            (run_id, tsird_tabia_id, nearest_road_m, tigray_roads_2006_intersects, quality_status)
          SELECT %s, tsird_tabia_id, nearest_m, intersects_road, 'ok' FROM measurements
          ON CONFLICT (run_id, tsird_tabia_id) DO UPDATE SET
            nearest_road_m=EXCLUDED.nearest_road_m,
            tigray_roads_2006_intersects=EXCLUDED.tigray_roads_2006_intersects,
            quality_status=EXCLUDED.quality_status
        """, (list(OFFICIAL_ROAD_OWNERS), run_id))
        cur.execute("SELECT count(*), percentile_cont(ARRAY[0.1,0.2,0.4,0.6,0.8,0.9]) WITHIN GROUP (ORDER BY nearest_road_m) FROM tsird.drought_tabia_road_accessibility WHERE run_id=%s", (run_id,))
        rows, percentiles = cur.fetchone()
        if rows != tabia_count:
            raise ValueError(f"expected {tabia_count} Tabias, loaded {rows}")
    print(json.dumps({"valid": True, "run_id": run_id, "tabias": rows, "era_trra_features": road_count, "nearest_road_m_percentiles": percentiles}, default=str))


if __name__ == "__main__":
    main()
