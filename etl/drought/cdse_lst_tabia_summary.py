"""Retrieve one bounded CLMS LST v2 raster and derive evidence summaries.

This is thermal context, kept separate from drought and food-security labels.
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
GRID = 0.05  # Provider product is approximately 5 km.
MAX_AGE = 7


def settings():
    original = os.environ.get("CDSE_NDVI_COLLECTION")
    os.environ["CDSE_NDVI_COLLECTION"] = os.environ["CDSE_LST_COLLECTION"]
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
        raise RuntimeError("existing CDSE LST raster cache has unexpected structure")
    observed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    body = {"input": {"bounds": {"bbox": bounds, "properties": {"crs": "http://www.opengis.net/def/crs/EPSG/0/4326"}},
            "data": [{"type": f"byoc-{collection}", "dataFilter": {"timeRange": {
                "from": (observed - timedelta(hours=2)).isoformat(), "to": (observed + timedelta(hours=2)).isoformat()}}}]},
            "output": {"width": math.ceil((bounds[2] - bounds[0]) / GRID), "height": math.ceil((bounds[3] - bounds[1]) / GRID),
                       "responses": [{"identifier": "default", "format": {"type": "image/tiff"}}]},
            "evalscript": "//VERSION=3\nfunction setup(){return {input:[\"LST\",\"ERRORBAR\",\"PPP\",\"QFLAG\",\"dataMask\"],output:{bands:5,sampleType:\"FLOAT32\"}};}\nfunction evaluatePixel(s){return [s.LST,s.ERRORBAR,s.PPP,s.QFLAG,s.dataMask];}"}
    request = Request(PROCESS_URL, data=json.dumps(body).encode(), method="POST", headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", "Accept": "image/tiff"})
    temporary = target.with_suffix(".tif.part")
    try:
        with urlopen(request, timeout=300) as response, temporary.open("wb") as handle:
            while chunk := response.read(1024 * 1024):
                handle.write(chunk)
        with rasterio.open(temporary) as source:
            if source.count != 5 or source.crs is None or source.crs.to_epsg() != 4326:
                raise RuntimeError("CDSE LST process response was not the expected raster")
        temporary.replace(target)
    finally:
        if temporary.exists():
            temporary.unlink()
    return hashlib.sha256(target.read_bytes()).hexdigest()


def tabia_stats(path, geometry):
    with rasterio.open(path) as source:
        data, _ = mask(source, [geometry], crop=True, filled=False)
    lst, errorbar, ppp, qflag, data_mask = data
    inside = ~np.ma.getmaskarray(lst)
    raw_lst = np.asarray(lst.filled(np.nan))
    raw_errorbar = np.asarray(errorbar.filled(np.nan))
    values = [raw_lst / 100.0, raw_errorbar / 100.0, np.asarray(ppp.filled(np.nan)), np.asarray(qflag.filled(np.nan))]
    valid = inside & np.isfinite(values[0]) & (np.asarray(data_mask.filled(0)) > 0)
    count, cells = int(valid.sum()), int(inside.sum())
    def mean(array): return round(float(array[valid].mean()), 2) if count else None
    return {"lst_c_mean": mean(values[0]), "errorbar_c_mean": mean(values[1]), "ppp_mean": mean(values[2]), "qflag_mean": mean(values[3]),
            "valid_pixel_count": count, "grid_cell_count": cells, "coverage_pct": round(100 * count / cells, 1) if cells else 0.0,
            "quality_status": "ok" if count and 100 * count / cells >= 90 else "insufficient_grid_coverage"}


def main():
    config, collection = settings(); token = access_token(config)
    tabias, bounds = fetch_tabias_and_bounds(); requested_stamp = os.environ.get("CDSE_OBSERVATION_TIMESTAMP")
    item, stamp = (item_at_timestamp(token, collection, bounds, requested_stamp)
                   if requested_stamp else latest_item(token, collection, bounds))
    observed = datetime.fromisoformat(stamp.replace("Z", "+00:00")); age = (datetime.now(timezone.utc) - observed).total_seconds() / 86400
    status = "development" if age <= MAX_AGE else "degraded"; run_id = f"cdse-clms-lst-v2-{observed:%Y%m%dT%H%M%SZ}"
    root = Path("/data/drought"); raw = root / "raw" / "cdse-clms-lst-v2"; outputs = root / "outputs"
    raw.mkdir(parents=True, exist_ok=True); outputs.mkdir(parents=True, exist_ok=True)
    raster = raw / f"{run_id}.tif"; checksum = retrieve(token, collection, bounds, stamp, raster)
    publish_provider_band(raster, root / "published" / "lst-current.tif", band=1,
                          scale=0.01, offset=0, mask_band=5)
    rows = []
    for tabia_id, tabia, woreda, geometry in tabias:
        row = {"tsird_tabia_id": tabia_id, "tabia_name_en": tabia, "woreda_name_en": woreda}; row.update(tabia_stats(raster, geometry)); rows.append(row)
    base = outputs / run_id
    with base.with_suffix(".csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0]); writer.writeheader(); writer.writerows(rows)
    manifest = {"run_id": run_id, "status": status, "source_product": "Copernicus CLMS LST 5 km hourly v2", "collection_id": collection,
                "observation_at": stamp, "native_resolution": "approximately 5 km, hourly", "raster_path": str(raster), "raster_sha256": checksum,
                "source_retrieved_at": datetime.now(timezone.utc).isoformat(), "source_age_days": round(age, 1),
                "method": "Tabia zonal means: LST, ERRORBAR, PPP, QFLAG; LST and ERRORBAR raw values scaled /100 to degrees Celsius",
                "publication_note": "Development artifact only. Land-surface temperature is thermal context, not an air-temperature observation, drought class, or food-security prediction."}
    base.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"run_id": run_id, "status": status, "rows": len(rows), "raster_bytes": raster.stat().st_size}))


if __name__ == "__main__":
    try:
        main()
    except (HTTPError, URLError) as exc:
        raise SystemExit(f"CDSE LST request failed: {type(exc).__name__} {getattr(exc, 'code', '')}".strip())
