"""Attach a provisional final-history baseline to a CHIRPS preliminary run.

Current preliminary pentads are compared with the matching final CHIRPS pentad
windows for 1991-2020.  This is a monitoring comparison, not an official
drought classification: the source maturity differs and the output must retain
that limitation.
"""
import hashlib
import json
import os
import shutil
import tempfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import psycopg2
from psycopg2.extras import execute_values
import rasterio
from rasterio.mask import mask

from chirps_prelim_tabia_summary import FILE_URL as PRELIM_URL, INDEX_URL, PENTAD_RE, previous_pentad, fetch_bounds, fetch_tabias

FINAL_URL = "https://data.chc.ucsb.edu/products/CHIRPS/v3.0/pentads/africa/tifs/chirps-v3.0.{year}.{month:02d}.{pentad}.tif"
BASELINE_YEARS = range(1991, 2021)


def dsn():
    return " ".join(("host=tsird-postgis", "port=5432", f"dbname={os.environ['POSTGRES_DB']}",
                     f"user={os.environ['POSTGRES_USER']}", f"password={os.environ['POSTGRES_PASSWORD']}"))


def download_final(item, bounds, cache):
    year, month, pentad = item
    target = cache / f"chirps-v3-final.{year}.{month:02d}.{pentad}.tif"
    receipt = target.with_suffix('.source.json')
    if target.exists() and receipt.exists():
        return target, json.loads(receipt.read_text(encoding='utf-8'))
    url = FINAL_URL.format(year=year, month=month, pentad=pentad)
    with tempfile.TemporaryDirectory() as temporary:
        raw = Path(temporary) / 'source.tif'
        request = urllib.request.Request(url, headers={'User-Agent': 'TSIRD-Atlas-development/1.0'})
        with urllib.request.urlopen(request, timeout=180) as response, raw.open('wb') as handle:
            shutil.copyfileobj(response, handle)
            metadata = {'url': url, 'http_status': getattr(response, 'status', 200),
                        'etag': response.headers.get('ETag'), 'last_modified': response.headers.get('Last-Modified'),
                        'retrieved_at': datetime.now(timezone.utc).isoformat()}
        if raw.stat().st_size < 100_000:
            raise RuntimeError(f'implausibly small final CHIRPS file: {year}-{month}-{pentad}')
        with rasterio.open(raw) as src:
            if src.count != 1 or src.crs is None or src.crs.to_epsg() != 4326:
                raise RuntimeError('unexpected final CHIRPS raster structure')
            window = src.window(*bounds).round_offsets().round_lengths(); data = src.read(window=window)
            profile = src.profile.copy(); profile.update(height=data.shape[1], width=data.shape[2], transform=src.window_transform(window), compress='deflate')
            with rasterio.open(target, 'w', **profile) as destination: destination.write(data)
        metadata.update(byte_count=raw.stat().st_size, sha256=hashlib.sha256(raw.read_bytes()).hexdigest())
    receipt.write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    return target, metadata


def zonal_sum(paths, geometry):
    total = 0.0
    for path in paths:
        with rasterio.open(path) as src:
            values = mask(src, [geometry], crop=True, filled=False)[0].compressed()
            if not values.size: return None
            total += float(values.mean())
    return total


def main():
    with urllib.request.urlopen(urllib.request.Request(INDEX_URL, headers={'User-Agent': 'TSIRD-Atlas-development/1.0'}), timeout=60) as response:
        latest = max(tuple(map(int, m.groups())) for m in PENTAD_RE.finditer(response.read().decode('utf-8', errors='replace')))
    selected = [latest]
    while len(selected) < 6: selected.append(previous_pentad(selected[-1]))
    selected.reverse()
    root = Path('/data/drought'); cache = root / 'cache' / 'prelim-final-baseline-v1'; output = root / 'outputs'
    cache.mkdir(parents=True, exist_ok=True); output.mkdir(parents=True, exist_ok=True)
    bounds = fetch_bounds()
    baseline_paths, receipts = {}, []
    for year in BASELINE_YEARS:
        paths = []
        for _, month, pentad in selected:
            path, receipt = download_final((year, month, pentad), bounds, cache); paths.append(path); receipts.append(receipt)
        baseline_paths[year] = paths
    tabias = fetch_tabias()
    with psycopg2.connect(dsn()) as conn, conn.cursor() as cur:
        cur.execute('''SELECT run_id FROM tsird.drought_preliminary_rainfall_run
                       WHERE status='development' ORDER BY period_end DESC, created_at DESC LIMIT 1''')
        run_id = cur.fetchone()[0]
        updates = []
        for tabia_id, _, _, geometry in tabias:
            history = [zonal_sum(paths, geometry) for paths in baseline_paths.values()]
            history = [value for value in history if value is not None]
            if len(history) < 25:
                updates.append((None, None, 'insufficient_historical_grid_coverage', run_id, tabia_id)); continue
            cur.execute('SELECT rainfall_mm FROM tsird.drought_tabia_preliminary_rainfall WHERE run_id=%s AND tsird_tabia_id=%s', (run_id, tabia_id))
            current = cur.fetchone()[0]
            percentile = round(100 * (sum(value < float(current) for value in history) + .5 * sum(value == float(current) for value in history)) / len(history), 1) if current is not None else None
            updates.append((round(float(np.median(history)), 2), percentile, 'provisional_preliminary_vs_final', run_id, tabia_id))
        execute_values(cur, '''UPDATE tsird.drought_tabia_preliminary_rainfall AS target SET
          baseline_median_mm=data.baseline_median_mm, provisional_percentile=data.provisional_percentile,
          comparison_status=data.comparison_status FROM (VALUES %s) AS data
          (baseline_median_mm, provisional_percentile, comparison_status, run_id, tsird_tabia_id)
          WHERE target.run_id=data.run_id AND target.tsird_tabia_id=data.tsird_tabia_id''', updates)
    manifest = {'run_id': run_id, 'status': 'development', 'baseline_years': [1991, 2020],
                'selected_pentad_positions': [{'month': month, 'pentad': pentad} for _, month, pentad in selected],
                'method': 'current preliminary six-pentad accumulation compared with matching final CHIRPS windows',
                'limitation': 'Provisional comparison only; preliminary and final sources differ. No drought class assigned.',
                'source_file_count': len(receipts), 'created_at': datetime.now(timezone.utc).isoformat()}
    (output / f'{run_id}.prelim-baseline.manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(json.dumps({'run_id': run_id, 'tabias': len(tabias), 'source_files': len(receipts)}, indent=2))


if __name__ == '__main__': main()
