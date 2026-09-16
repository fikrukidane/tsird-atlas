"""Validate and load a development-only SWI Tabia summary."""
import csv
import json
import os
import sys
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values


def dsn():
    return f"host=tsird-postgis port=5432 dbname={os.environ['POSTGRES_DB']} user={os.environ['POSTGRES_USER']} password={os.environ['POSTGRES_PASSWORD']}"


base = Path(sys.argv[1])
manifest = json.loads(base.with_suffix('.manifest.json').read_text())
rows = list(csv.DictReader(base.with_suffix('.csv').open()))
if manifest.get('status') not in {'development', 'degraded'} or not rows:
    raise ValueError('invalid SWI artifact')
values = [(manifest['run_id'], r['tsird_tabia_id'], r['swi010_mean'] or None, r['swi040_mean'] or None,
           r['swi100_mean'] or None, int(r['valid_pixel_count']), int(r['grid_cell_count']),
           float(r['coverage_pct']), r['qflag040_mean'] or None, r['quality_status']) for r in rows]
with psycopg2.connect(dsn()) as conn, conn.cursor() as cur:
    cur.execute('''INSERT INTO tsird.drought_swi_run
      (run_id,source_product,collection_id,observation_at,native_resolution,raster_path,raster_sha256,source_retrieved_at,status,notes)
      VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
      ON CONFLICT (run_id) DO UPDATE SET status=EXCLUDED.status,raster_path=EXCLUDED.raster_path,
      raster_sha256=EXCLUDED.raster_sha256,source_retrieved_at=EXCLUDED.source_retrieved_at,notes=EXCLUDED.notes''',
      (manifest['run_id'],manifest['source_product'],manifest['collection_id'],manifest['observation_at'],manifest['native_resolution'],manifest['raster_path'],manifest['raster_sha256'],manifest['source_retrieved_at'],manifest['status'],manifest['publication_note']))
    execute_values(cur, '''INSERT INTO tsird.drought_tabia_swi
      (run_id,tsird_tabia_id,swi010_mean,swi040_mean,swi100_mean,valid_pixel_count,grid_cell_count,coverage_pct,qflag040_mean,quality_status) VALUES %s
      ON CONFLICT (run_id,tsird_tabia_id) DO UPDATE SET swi010_mean=EXCLUDED.swi010_mean,swi040_mean=EXCLUDED.swi040_mean,swi100_mean=EXCLUDED.swi100_mean,valid_pixel_count=EXCLUDED.valid_pixel_count,grid_cell_count=EXCLUDED.grid_cell_count,coverage_pct=EXCLUDED.coverage_pct,qflag040_mean=EXCLUDED.qflag040_mean,quality_status=EXCLUDED.quality_status''', values)
print(json.dumps({'valid': True, 'run_id': manifest['run_id'], 'artifact_status': manifest['status'], 'rows': len(values)}))
