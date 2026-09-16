"""Validate and load a development-only CHIRPS preliminary rainfall summary."""
import csv
import json
import os
import sys
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values


def dsn():
    return " ".join(("host=tsird-postgis", "port=5432", f"dbname={os.environ['POSTGRES_DB']}",
                     f"user={os.environ['POSTGRES_USER']}", f"password={os.environ['POSTGRES_PASSWORD']}"))


def main():
    base = Path(sys.argv[1])
    manifest = json.loads(base.with_suffix('.manifest.json').read_text(encoding='utf-8'))
    with base.with_suffix('.csv').open(encoding='utf-8') as handle:
        rows = list(csv.DictReader(handle))
    required = {'run_id', 'period_start', 'period_end', 'source_acquisition', 'publication_note'}
    if not required.issubset(manifest) or not rows:
        raise ValueError('preliminary artifact has no valid manifest or rows')
    if manifest['status'] != 'development' or not manifest['source_acquisition']:
        raise ValueError('only source-receipted development artifacts may be loaded')
    values = []
    for row in rows:
        if not row['tsird_tabia_id'].startswith('tsird-tabia-v1-'):
            raise ValueError('non-canonical Tabia ID')
        coverage = float(row['coverage_pct']); cells = int(row['grid_cell_count'])
        if not 0 <= coverage <= 100 or cells < 0:
            raise ValueError('invalid coverage metadata')
        values.append((manifest['run_id'], row['tsird_tabia_id'], row['rainfall_mm'] or None,
                       cells, coverage, row['quality_status']))
    with psycopg2.connect(dsn()) as conn, conn.cursor() as cur:
        cur.execute('''INSERT INTO tsird.drought_preliminary_rainfall_run
          (run_id, source_product, period_start, period_end, pentad_count, source_latest_at, status, notes)
          VALUES (%s,%s,%s,%s,%s,%s,'development',%s)
          ON CONFLICT (run_id) DO UPDATE SET created_at=now(), status='development', notes=EXCLUDED.notes''',
          (manifest['run_id'], manifest['source_product'], manifest['period_start'], manifest['period_end'],
           len(manifest['selected_pentads']), manifest['source_acquisition'][-1]['retrieved_at'], manifest['publication_note']))
        execute_values(cur, '''INSERT INTO tsird.drought_tabia_preliminary_rainfall
          (run_id, tsird_tabia_id, rainfall_mm, grid_cell_count, coverage_pct, quality_status) VALUES %s
          ON CONFLICT (run_id, tsird_tabia_id) DO UPDATE SET rainfall_mm=EXCLUDED.rainfall_mm,
          grid_cell_count=EXCLUDED.grid_cell_count, coverage_pct=EXCLUDED.coverage_pct, quality_status=EXCLUDED.quality_status''', values)
    print(json.dumps({'valid': True, 'run_id': manifest['run_id'], 'rows': len(values)}, indent=2))


if __name__ == '__main__':
    main()
