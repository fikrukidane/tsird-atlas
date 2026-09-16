"""Build a non-classified recent-rainfall Tabia summary from CHIRPS prelim pentads.

The artifact reports observed 6-pentad accumulation only.  It intentionally
does not assign a drought class: a comparable historical pentad baseline must
be built and scientifically reviewed before relative labels are allowed.
"""
import csv
import argparse
import hashlib
import json
import os
import re
import shutil
import tempfile
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import psycopg2
import rasterio
from rasterio.mask import mask
from publish_evidence_raster import publish_rainfall_total

INDEX_URL = "https://data.chc.ucsb.edu/products/CHIRPS/v3.0/prelim/pentads/africa/tifs/"
FILE_URL = INDEX_URL + "chirps-v3.0.{year}.{month:02d}.{pentad}.tif"
PENTAD_RE = re.compile(r"chirps-v3\.0\.(\d{4})\.(\d{2})\.([1-6])\.tif")
PENTADS = 6


def dsn():
    return " ".join(("host=tsird-postgis", "port=5432", f"dbname={os.environ['POSTGRES_DB']}",
                     f"user={os.environ['POSTGRES_USER']}", f"password={os.environ['POSTGRES_PASSWORD']}"))


def pentad_start(year, month, pentad):
    return date(year, month, 1 if pentad == 1 else (pentad - 1) * 5 + 1)


def previous_pentad(item):
    year, month, pentad = item
    if pentad > 1:
        return year, month, pentad - 1
    if month > 1:
        return year, month - 1, 6
    return year - 1, 12, 6


def fetch_tabias():
    with psycopg2.connect(dsn()) as conn, conn.cursor() as cur:
        cur.execute('''SELECT i.tsird_tabia_id, t."TABIA", t."WEREDA", ST_AsGeoJSON(t.geometry)
                       FROM tigray_tabias_ws t JOIN tsird.tabia_identity i USING (tsird_tabia_id)
                       ORDER BY i.tsird_tabia_id''')
        return [(row[0], row[1], row[2], json.loads(row[3])) for row in cur.fetchall()]


def fetch_bounds():
    with psycopg2.connect(dsn()) as conn, conn.cursor() as cur:
        cur.execute('''SELECT ST_XMin(ST_Extent(geometry)::box3d), ST_YMin(ST_Extent(geometry)::box3d),
                              ST_XMax(ST_Extent(geometry)::box3d), ST_YMax(ST_Extent(geometry)::box3d)
                       FROM tigray_tabias_ws''')
        left, bottom, right, top = cur.fetchone()
        return float(left) - .05, float(bottom) - .05, float(right) + .05, float(top) + .05


def retrieve_clipped(item, bounds, cache):
    year, month, pentad = item
    target = cache / f"chirps-v3-prelim.{year}.{month:02d}.{pentad}.tif"
    url = FILE_URL.format(year=year, month=month, pentad=pentad)
    with tempfile.TemporaryDirectory() as temporary:
        source = Path(temporary) / "source.tif"
        request = urllib.request.Request(url, headers={"User-Agent": "TSIRD-Atlas-development/1.0"})
        with urllib.request.urlopen(request, timeout=180) as response, source.open("wb") as handle:
            shutil.copyfileobj(response, handle)
            receipt = {"url": url, "http_status": getattr(response, "status", 200),
                       "etag": response.headers.get("ETag"), "last_modified": response.headers.get("Last-Modified"),
                       "retrieved_at": datetime.now(timezone.utc).isoformat()}
        if source.stat().st_size < 100_000:
            raise RuntimeError("CHIRPS preliminary file was implausibly small")
        with rasterio.open(source) as src:
            if src.count != 1 or src.crs is None or src.crs.to_epsg() != 4326:
                raise RuntimeError("CHIRPS preliminary file has unexpected raster structure")
            window = src.window(*bounds).round_offsets().round_lengths()
            data = src.read(window=window)
            profile = src.profile.copy(); profile.update(height=data.shape[1], width=data.shape[2],
                transform=src.window_transform(window), compress="deflate")
            with rasterio.open(target, "w", **profile) as destination:
                destination.write(data)
        receipt.update(byte_count=source.stat().st_size, sha256=hashlib.sha256(source.read_bytes()).hexdigest())
    return target, receipt


def zonal_total(paths, geometry):
    total, cells, usable = 0.0, 0, 0
    for path in paths:
        with rasterio.open(path) as src:
            clipped, _ = mask(src, [geometry], crop=True, filled=False)
            grid_mask = np.ma.getmaskarray(clipped[0]); values = clipped[0].compressed()
            cells += int((~grid_mask).sum())
            if values.size:
                total += float(values.mean()); usable += int(values.size)
    return total, usable, cells


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--end-year", type=int)
    parser.add_argument("--end-month", type=int, choices=range(1, 13))
    parser.add_argument("--end-pentad", type=int, choices=range(1, 7))
    args = parser.parse_args()
    explicit_end = (args.end_year, args.end_month, args.end_pentad)
    if any(value is not None for value in explicit_end) and any(value is None for value in explicit_end):
        raise ValueError("end year, month, and pentad must be supplied together")
    root = Path("/data/drought"); cache = root / "cache" / "prelim-tabia-extent-v1"; output = root / "outputs"
    cache.mkdir(parents=True, exist_ok=True); output.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(urllib.request.Request(INDEX_URL, headers={"User-Agent": "TSIRD-Atlas-development/1.0"}), timeout=60) as response:
        listed = response.read().decode("utf-8", errors="replace")
    latest = explicit_end if all(value is not None for value in explicit_end) else max(tuple(map(int, match.groups())) for match in PENTAD_RE.finditer(listed))
    selected = [latest]
    while len(selected) < PENTADS:
        selected.append(previous_pentad(selected[-1]))
    selected.reverse()
    bounds = fetch_bounds()
    downloads = [retrieve_clipped(item, bounds, cache) for item in selected]
    paths = [item[0] for item in downloads]
    rows = []
    for tabia_id, name, woreda, geometry in fetch_tabias():
        rainfall, usable, cells = zonal_total(paths, geometry)
        coverage = round(100 * usable / cells, 1) if cells else 0.0
        rows.append({"tsird_tabia_id": tabia_id, "tabia_name_en": name, "woreda_name_en": woreda,
                     "rainfall_mm": round(rainfall, 2) if usable else None, "grid_cell_count": usable,
                     "coverage_pct": coverage, "quality_status": "ok" if usable and coverage >= 90 else "insufficient_grid_coverage"})
    start = pentad_start(*selected[0]); end_year, end_month, end_pentad = selected[-1]
    end = date(end_year, end_month, min(end_pentad * 5, 28 if end_month == 2 else 30 if end_month in {4,6,9,11} else 31))
    run_id = f"chirps-v3-prelim-{selected[0][0]}{selected[0][1]:02d}{selected[0][2]}-to-{end_year}{end_month:02d}{end_pentad}"
    historical_raster = root / "published" / f"{run_id}.tif"
    publish_rainfall_total(paths, historical_raster)
    publish_rainfall_total(paths, root / "published" / "chirps-rapid-rainfall.tif")
    base = output / run_id
    with base.with_suffix('.csv').open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys()); writer.writeheader(); writer.writerows(rows)
    manifest = {"run_id": run_id, "status": "development", "source_product": "CHIRPS v3 preliminary pentad, Africa subset",
                "source_version": "v3.0", "native_resolution": "0.05 degree CHIRPS grid", "period_start": start.isoformat(),
                "period_end": end.isoformat(), "selected_pentads": [{"year": y, "month": m, "pentad": p} for y,m,p in selected],
                "boundary_set_version": "tsird-tabias-v1", "included_tabias": len(rows),
                "method": "six completed preliminary pentad pixel-centre zonal means summed; observed accumulation only",
                "raster_path": str(historical_raster), "raster_sha256": hashlib.sha256(historical_raster.read_bytes()).hexdigest(),
                "publication_note": "Development artifact only. No anomaly or drought classification is assigned.",
                "source_acquisition": [item[1] for item in downloads]}
    base.with_suffix('.manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(json.dumps({"run_id": run_id, "rows": len(rows), "period": [start.isoformat(), end.isoformat()]}, indent=2))


if __name__ == '__main__':
    main()
