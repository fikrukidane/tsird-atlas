"""Retrieve one bounded CLMS SWI v4 raster and derive coarse Tabia summaries.

This deliberately retains the native coarse grid as an evidence raster.  The
Tabia figures are zonal context only; a 0.1 degree cell must never be described
as a Tabia-scale soil-water observation.
"""
import csv
import hashlib
import json
import math
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import numpy as np
import rasterio
from rasterio.mask import mask
from cdse_ndvi_tabia_summary import access_token, cdse_settings, fetch_tabias_and_bounds, latest_item, item_at_timestamp
from publish_evidence_raster import publish_provider_band

PROCESS_URL = "https://sh.dataspace.copernicus.eu/api/v1/process"
GRID = 0.1
MAX_AGE = 15

def get_settings():
    original = os.environ.get("CDSE_NDVI_COLLECTION")
    os.environ["CDSE_NDVI_COLLECTION"] = os.environ["CDSE_SWI_COLLECTION"]
    try:
        return cdse_settings()
    finally:
        if original is None:
            os.environ.pop("CDSE_NDVI_COLLECTION", None)
        else:
            os.environ["CDSE_NDVI_COLLECTION"] = original

def retrieve(token, collection, bounds, stamp, target):
    if target.exists():
        with rasterio.open(target) as source:
            if source.count == 5 and source.crs and source.crs.to_epsg() == 4326:
                return hashlib.sha256(target.read_bytes()).hexdigest()
        raise RuntimeError("existing CDSE SWI raster cache has unexpected structure")
    observed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    body = {
        "input": {
            "bounds": {"bbox": bounds, "properties": {"crs": "http://www.opengis.net/def/crs/EPSG/0/4326"}},
            "data": [{"type": f"byoc-{collection}", "dataFilter": {"timeRange": {
                "from": (observed - timedelta(days=1)).isoformat(), "to": (observed + timedelta(days=1)).isoformat()}}}],
        },
        "output": {"width": math.ceil((bounds[2] - bounds[0]) / GRID),
                   "height": math.ceil((bounds[3] - bounds[1]) / GRID),
                   "responses": [{"identifier": "default", "format": {"type": "image/tiff"}}]},
        "evalscript": "//VERSION=3\nfunction setup(){return {input:[\"SWI010\",\"SWI040\",\"SWI100\",\"QFLAG040\",\"dataMask\"],output:{bands:5,sampleType:\"FLOAT32\"}};}\nfunction evaluatePixel(s){return [s.SWI010,s.SWI040,s.SWI100,s.QFLAG040,s.dataMask];}",
    }
    request = Request(PROCESS_URL, data=json.dumps(body).encode(), method="POST", headers={
        "Authorization": f"Bearer {token}", "Content-Type": "application/json", "Accept": "image/tiff"})
    temporary = target.with_suffix(".tif.part")
    try:
        with urlopen(request, timeout=300) as response, temporary.open("wb") as handle:
            while chunk := response.read(1024 * 1024):
                handle.write(chunk)
        # A small Tigray response can still be a valid multi-band GeoTIFF;
        # validate the actual raster rather than guessing from file size.
        with rasterio.open(temporary) as source:
            if source.count != 5 or source.crs is None or source.crs.to_epsg() != 4326:
                raise RuntimeError("CDSE SWI raster has unexpected structure")
        temporary.replace(target)
    finally:
        if temporary.exists():
            temporary.unlink()
    return hashlib.sha256(target.read_bytes()).hexdigest()

def stats(path, geom):
    with rasterio.open(path) as source:
        data, _ = mask(source, [geom], crop=True, filled=False)
    swi010, swi040, swi100, qflag040, data_mask = data
    inside = ~np.ma.getmaskarray(swi040)
    # The SWI v4 and QFLAG bands are UINT8 values with scale 1/2.  Persist
    # physical percentage values, leaving the provider raster unchanged.
    values = [np.asarray(band.filled(np.nan)) / 2.0 for band in (swi010, swi040, swi100, qflag040)]
    valid = inside & np.isfinite(values[1]) & (np.asarray(data_mask.filled(0)) > 0)
    valid_count = int(valid.sum())
    cells = int(inside.sum())
    def mean(band):
        return round(float(band[valid].mean()), 3) if valid_count else None
    return {"swi010_mean": mean(values[0]), "swi040_mean": mean(values[1]), "swi100_mean": mean(values[2]),
            "qflag040_mean": mean(values[3]), "valid_pixel_count": valid_count, "grid_cell_count": cells,
            "coverage_pct": round(100 * valid_count / cells, 1) if cells else 0.0,
            "quality_status": "ok" if valid_count and 100 * valid_count / cells >= 90 else "insufficient_grid_coverage"}

def main():
    settings, collection = get_settings()
    token = access_token(settings)
    tabias, bounds = fetch_tabias_and_bounds()
    requested_stamp = os.environ.get("CDSE_OBSERVATION_TIMESTAMP")
    item, stamp = (item_at_timestamp(token, collection, bounds, requested_stamp)
                   if requested_stamp else latest_item(token, collection, bounds))
    observed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    age = (datetime.now(timezone.utc) - observed).total_seconds() / 86400
    status = "development" if age <= MAX_AGE else "degraded"
    run = f"cdse-clms-swi-v4-{observed:%Y%m%dT%H%M%SZ}"
    root = Path("/data/drought")
    raw = root / "raw" / "cdse-clms-swi-v4"; raw.mkdir(parents=True, exist_ok=True)
    outputs = root / "outputs"; outputs.mkdir(parents=True, exist_ok=True)
    raster = raw / f"{run}.tif"
    checksum = retrieve(token, collection, bounds, stamp, raster)
    publish_provider_band(raster, root / "published" / "swi040-current.tif", band=2,
                          scale=0.5, offset=0, mask_band=5)
    rows = []
    for tabia_id, tabia, woreda, geometry in tabias:
        row = {"tsird_tabia_id": tabia_id, "tabia_name_en": tabia, "woreda_name_en": woreda}
        row.update(stats(raster, geometry)); rows.append(row)
    base = outputs / run
    with base.with_suffix(".csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0]); writer.writeheader(); writer.writerows(rows)
    manifest = {"run_id": run, "status": status, "source_product": "Copernicus CLMS SWI 12.5 km 10-daily v4",
                "collection_id": collection, "observation_at": stamp, "native_resolution": "0.1 degree (about 12.5 km), 10-daily",
                "raster_path": str(raster), "raster_sha256": checksum, "source_retrieved_at": datetime.now(timezone.utc).isoformat(),
                "source_age_days": round(age, 1), "method": "Tabia zonal means: SWI010, SWI040, SWI100; raw SWI/QFLAG scaled as raw / 2",
                "publication_note": "Development artifact only. Coarse soil-water context, not a Tabia-scale observation or drought class."}
    base.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"run_id": run, "status": status, "rows": len(rows), "raster_bytes": raster.stat().st_size}))

if __name__ == "__main__":
    try:
        main()
    except (HTTPError, URLError) as exc:
        raise SystemExit(f"CDSE SWI request failed: {type(exc).__name__} {getattr(exc, 'code', '')}".strip())
