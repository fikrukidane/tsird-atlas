"""Retrieve current Copernicus CLMS LST Daily Cycle 3 km V3 evidence.

This replaces the discontinued LST v2 hourly product.  It stores land-surface
temperature context only: it is never an air-temperature observation, a
drought class, or an operational trigger.
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

from cdse_ndvi_tabia_summary import (
    access_token, cdse_settings, fetch_tabias_and_bounds, item_at_timestamp,
    latest_item,
)
from publish_evidence_raster import publish_provider_band

PROCESS_URL = "https://sh.dataspace.copernicus.eu/api/v1/process"
COLLECTION = "7f175dfe-eee2-4c4c-93a6-db8072e76a44"
PRODUCT = "Copernicus CLMS LST Daily Cycle 3 km 10-daily V3"
NATIVE_RESOLUTION = "approximately 3 km, 10-daily"
REQUESTED_DEGREES = 0.03
MAX_CURRENT_AGE_DAYS = 20


def settings():
    """Reuse the reviewed CDSE OAuth contract while selecting LST V3."""
    original = os.environ.get("CDSE_NDVI_COLLECTION")
    os.environ["CDSE_NDVI_COLLECTION"] = os.environ.get("CDSE_LST_V3_COLLECTION", COLLECTION)
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
            if source.count == 3 and source.crs and source.crs.to_epsg() == 4326:
                return hashlib.sha256(target.read_bytes()).hexdigest()
        raise RuntimeError("existing CDSE LST V3 raster cache has unexpected structure")
    observed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    body = {
        "input": {
            "bounds": {"bbox": bounds, "properties": {"crs": "http://www.opengis.net/def/crs/EPSG/0/4326"}},
            "data": [{"type": f"byoc-{collection}", "dataFilter": {"timeRange": {
                "from": (observed - timedelta(days=2)).isoformat(),
                "to": (observed + timedelta(days=2)).isoformat(),
            }}}],
        },
        "output": {
            "width": math.ceil((bounds[2] - bounds[0]) / REQUESTED_DEGREES),
            "height": math.ceil((bounds[3] - bounds[1]) / REQUESTED_DEGREES),
            "responses": [{"identifier": "default", "format": {"type": "image/tiff"}}],
        },
        "evalscript": "//VERSION=3\\nfunction setup(){return {input:[\\\"MEDIAN\\\",\\\"FOBS\\\",\\\"dataMask\\\"],output:{bands:3,sampleType:\\\"FLOAT32\\\"}};}\\nfunction evaluatePixel(s){return [s.MEDIAN,s.FOBS,s.dataMask];}",
    }
    request = Request(
        PROCESS_URL, data=json.dumps(body).encode(), method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", "Accept": "image/tiff"},
    )
    temporary = target.with_suffix(".tif.part")
    try:
        with urlopen(request, timeout=300) as response, temporary.open("wb") as handle:
            while chunk := response.read(1024 * 1024):
                handle.write(chunk)
        with rasterio.open(temporary) as source:
            if source.count != 3 or source.crs is None or source.crs.to_epsg() != 4326:
                raise RuntimeError("CDSE LST V3 process response was not the expected raster")
        temporary.replace(target)
    finally:
        if temporary.exists():
            temporary.unlink()
    return hashlib.sha256(target.read_bytes()).hexdigest()


def tabia_stats(path, geometry):
    with rasterio.open(path) as source:
        data, _ = mask(source, [geometry], crop=True, filled=False)
    median, fobs, data_mask = data
    inside = ~np.ma.getmaskarray(median)
    raw_temperature = np.asarray(median.filled(np.nan))
    raw_observations = np.asarray(fobs.filled(np.nan))
    valid = inside & np.isfinite(raw_temperature) & (np.asarray(data_mask.filled(0)) > 0)
    count, cells = int(valid.sum()), int(inside.sum())
    coverage = round(100 * count / cells, 1) if cells else 0.0
    # The V3 source encoding is Celsius * 100: applying the documented
    # scale/offset yields Kelvin, so the Celsius value is raw / 100.  FOBS is
    # a 0--100 observation fraction.
    return {
        "lst_c_mean": round(float((raw_temperature[valid] / 100.0).mean()), 2) if count else None,
        "fobs_mean": round(float((raw_observations[valid] / 100.0).mean()), 3) if count else None,
        "valid_pixel_count": count,
        "grid_cell_count": cells,
        "coverage_pct": coverage,
        "quality_status": "ok" if count and coverage >= 90 else "insufficient_grid_coverage",
    }


def main():
    config, collection = settings()
    token = access_token(config)
    tabias, bounds = fetch_tabias_and_bounds()
    requested_stamp = os.environ.get("CDSE_OBSERVATION_TIMESTAMP")
    item, stamp = (item_at_timestamp(token, collection, bounds, requested_stamp)
                   if requested_stamp else latest_item(token, collection, bounds))
    observed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    age = (datetime.now(timezone.utc) - observed).total_seconds() / 86400
    status = "development" if age <= MAX_CURRENT_AGE_DAYS else "degraded"
    run_id = f"cdse-clms-lst-v3-{observed:%Y%m%dT%H%M%SZ}"
    root = Path("/data/drought")
    raw, outputs = root / "raw" / "cdse-clms-lst-v3", root / "outputs"
    raw.mkdir(parents=True, exist_ok=True)
    outputs.mkdir(parents=True, exist_ok=True)
    raster = raw / f"{run_id}.tif"
    checksum = retrieve(token, collection, bounds, stamp, raster)
    historical_only = os.environ.get("TSIRD_RETAIN_HISTORICAL_ONLY") == "1"
    if not historical_only:
        publish_provider_band(raster, root / "published" / "lst-current.tif", band=1, scale=0.01, offset=-273.15, mask_band=3)
    rows = []
    for tabia_id, tabia, woreda, geometry in tabias:
        row = {"tsird_tabia_id": tabia_id, "tabia_name_en": tabia, "woreda_name_en": woreda}
        row.update(tabia_stats(raster, geometry))
        rows.append(row)
    base = outputs / run_id
    with base.with_suffix(".csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)
    manifest = {
        "run_id": run_id, "status": status, "source_product": PRODUCT, "collection_id": collection,
        "observation_at": stamp, "native_resolution": NATIVE_RESOLUTION, "raster_path": str(raster),
        "raster_sha256": checksum, "source_retrieved_at": datetime.now(timezone.utc).isoformat(),
        "source_age_days": round(age, 1), "catalog_item_id": item.get("id"),
        "method": "CDSE Process API: 10-daily LST Daily Cycle V3 MEDIAN decoded to Celsius using the documented 1/100 scale and +273.15 K offset; FOBS retained as the mean source-observation fraction; Tabia zonal means on the provider grid.",
        "historical_retention_only": historical_only,
        "publication_note": "Development artifact only. Land-surface temperature is thermal context, not an air-temperature observation, drought class, food-security classification, forecast, allocation or response trigger.",
    }
    base.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"run_id": run_id, "status": status, "rows": len(rows), "raster_bytes": raster.stat().st_size}))


if __name__ == "__main__":
    try:
        main()
    except (HTTPError, URLError) as exc:
        raise SystemExit(f"CDSE LST V3 request failed: {type(exc).__name__} {getattr(exc, 'code', '')}".strip())
