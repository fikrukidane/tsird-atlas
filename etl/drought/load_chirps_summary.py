"""Load one validated development CHIRPS artifact into local TSIRD analytics."""
import argparse, csv, json, os
from pathlib import Path
import psycopg2
from psycopg2.extras import Json, execute_values

def dsn():
    return " ".join(("host=tsird-postgis", "port=5432", f"dbname={os.environ['POSTGRES_DB']}",
                     f"user={os.environ['POSTGRES_USER']}", f"password={os.environ['POSTGRES_PASSWORD']}"))

def main():
    parser = argparse.ArgumentParser(); parser.add_argument("artifact_base")
    args = parser.parse_args(); base = Path(args.artifact_base)
    manifest = json.loads(base.with_suffix('.manifest.json').read_text(encoding='utf-8'))
    with base.with_suffix('.csv').open(encoding='utf-8') as handle: rows = list(csv.DictReader(handle))
    values = [(manifest['run_id'], row['tsird_tabia_id'], row['rainfall_mm'] or None,
               row['baseline_median_mm'] or None, row['percentile'] or None,
               row['condition_class'], int(row['grid_cell_count']), row['coverage_pct'],
               row['quality_status']) for row in rows]
    quality_counts = {}
    class_counts = {}
    for row in rows:
        quality_counts[row['quality_status']] = quality_counts.get(row['quality_status'], 0) + 1
        class_counts[row['condition_class']] = class_counts.get(row['condition_class'], 0) + 1
    with psycopg2.connect(dsn()) as conn, conn.cursor() as cur:
        cur.execute("""INSERT INTO tsird.drought_rainfall_run
          (run_id, source_product, source_version, analysis_year, season_months,
           baseline_year_start, baseline_year_end, source_latest_month, status, notes)
          VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'development',%s)
          ON CONFLICT (run_id) DO UPDATE SET created_at=now(), status='development', notes=EXCLUDED.notes""",
          (manifest['run_id'], manifest['source_product'], manifest['source_version'],
           manifest['analysis_year'], manifest['months'], manifest['baseline_years'][0],
           manifest['baseline_years'][1], manifest['source_latest_month'], manifest['publication_note']))
        cur.execute("""INSERT INTO tsird.drought_artifact_registry
          (artifact_id, artifact_type, source_id, run_id, status, valid_from,
           native_resolution, geography_scope, boundary_set_version,
           quality_summary, provenance)
          VALUES (%s, 'observed_rainfall', 'chc-chirps-v3', %s, 'development', %s,
                  %s, 'Tabia zonal summary', %s, %s, %s)
          ON CONFLICT (artifact_id) DO UPDATE SET
            ingested_at=now(), valid_from=EXCLUDED.valid_from,
            quality_summary=EXCLUDED.quality_summary, provenance=EXCLUDED.provenance,
            status='development'""",
          (f"observed-rainfall--{manifest['run_id']}", manifest['run_id'],
           manifest['source_latest_month'], '0.05 degree CHIRPS grid',
           manifest['boundary_set_version'],
           Json({'record_count': len(rows), 'quality_counts': quality_counts, 'class_counts': class_counts}),
           Json({'source_product': manifest['source_product'], 'source_version': manifest['source_version'],
                 'source_url_template': manifest['source_url_template'], 'method': manifest['method'],
                 'source_acquisition': manifest['source_acquisition'],
                 'publication_note': manifest['publication_note']})))
        execute_values(cur, """INSERT INTO tsird.drought_tabia_rainfall_condition
          (run_id, tsird_tabia_id, rainfall_mm, baseline_median_mm, percentile,
           condition_class, grid_cell_count, coverage_pct, quality_status)
          VALUES %s ON CONFLICT (run_id, tsird_tabia_id) DO UPDATE SET
          rainfall_mm=EXCLUDED.rainfall_mm, baseline_median_mm=EXCLUDED.baseline_median_mm,
          percentile=EXCLUDED.percentile, condition_class=EXCLUDED.condition_class,
          grid_cell_count=EXCLUDED.grid_cell_count, coverage_pct=EXCLUDED.coverage_pct,
          quality_status=EXCLUDED.quality_status""", values)
    print(f"loaded {len(values)} rows for {manifest['run_id']}")

if __name__ == '__main__': main()
