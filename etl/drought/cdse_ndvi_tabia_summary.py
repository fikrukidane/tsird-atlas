"""Retrieve one current CDSE CLMS NDVI raster and derive Tabia summaries.

The raster is retained at its requested near-native 300 m grid under the local
development data mount.  The accompanying Tabia values are zonal summaries,
not a replacement for the raster or a drought/food-security classification.
"""
import csv
import hashlib
import json
import math
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import numpy as np
import psycopg2
import rasterio
from rasterio.mask import mask
from publish_evidence_raster import publish_provider_band

CATALOG_SEARCH_URL = "https://sh.dataspace.copernicus.eu/catalog/v1/search"
PROCESS_URL = "https://sh.dataspace.copernicus.eu/api/v1/process"
PRODUCT = "Copernicus CLMS NDVI 300 m 10-daily v3"
NATIVE_RESOLUTION = "approximately 300 m, 10-daily"
# The CLMS source is geographic; this is a near-native 300 m request grid.
REQUESTED_DEGREES = 1 / 360
MAX_CURRENT_AGE_DAYS = 15


def dsn():
    return " ".join(("host=tsird-postgis", "port=5432", f"dbname={os.environ['POSTGRES_DB']}",
                     f"user={os.environ['POSTGRES_USER']}", f"password={os.environ['POSTGRES_PASSWORD']}"))


def cdse_settings():
    settings = {name: os.environ.get(name) for name in (
        "CDSE_OAUTH_CLIENT_ID", "CDSE_OAUTH_CLIENT_SECRET", "CDSE_OAUTH_TOKEN_URL", "CDSE_NDVI_COLLECTION")}
    if not all(settings.values()):
        raise RuntimeError("CDSE NDVI configuration is incomplete")
    collection = settings["CDSE_NDVI_COLLECTION"].strip()
    if collection.startswith("byoc-"):
        collection = collection[5:]
    if len(collection) != 36 or collection.count("-") != 4:
        raise RuntimeError("CDSE_NDVI_COLLECTION must be a CLMS BYOC UUID")
    return settings, collection


def access_token(settings):
    body = urlencode({"grant_type": "client_credentials", "client_id": settings["CDSE_OAUTH_CLIENT_ID"],
                      "client_secret": settings["CDSE_OAUTH_CLIENT_SECRET"]}).encode("utf-8")
    request = Request(settings["CDSE_OAUTH_TOKEN_URL"], data=body, method="POST",
                      headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"})
    with urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not payload.get("access_token"):
        raise RuntimeError("CDSE OAuth response omitted access token")
    return payload["access_token"]


def fetch_tabias_and_bounds():
    with psycopg2.connect(dsn()) as conn, conn.cursor() as cur:
        cur.execute('''SELECT i.tsird_tabia_id, t."TABIA", t."WEREDA", ST_AsGeoJSON(t.geometry)
                       FROM tigray_tabias_ws t JOIN tsird.tabia_identity i USING (tsird_tabia_id)
                       ORDER BY i.tsird_tabia_id''')
        tabias = [(row[0], row[1], row[2], json.loads(row[3])) for row in cur.fetchall()]
        cur.execute('''SELECT ST_XMin(ST_Extent(geometry)::box3d), ST_YMin(ST_Extent(geometry)::box3d),
                              ST_XMax(ST_Extent(geometry)::box3d), ST_YMax(ST_Extent(geometry)::box3d)
                       FROM tigray_tabias_ws''')
        left, bottom, right, top = cur.fetchone()
    # Small pad prevents edge clipping but is not a request for any broader product.
    return tabias, [float(left) - .02, float(bottom) - .02, float(right) + .02, float(top) + .02]


def latest_item(token, collection_id, bounds):
    end = datetime.now(timezone.utc)
    query = {"bbox": bounds, "datetime": f"{(end - timedelta(days=120)).isoformat()}/{end.isoformat()}",
             "collections": [f"byoc-{collection_id}"], "limit": 20,
             "fields": {"include": ["id", "properties.datetime", "properties.start_datetime", "properties.end_datetime"]}}
    request = Request(CATALOG_SEARCH_URL, data=json.dumps(query).encode("utf-8"), method="POST", headers={
        "Authorization": f"Bearer {token}", "Content-Type": "application/json", "Accept": "application/geo+json"})
    with urlopen(request, timeout=60) as response:
        payload = json.loads(response.read().decode("utf-8"))
    features = payload.get("features") or []
    if not features:
        raise RuntimeError("CDSE NDVI catalog returned no recent Tigray item")
    def timestamp(feature):
        props = feature.get("properties") or {}
        return props.get("datetime") or props.get("end_datetime") or props.get("start_datetime") or ""
    item = max(features, key=timestamp)
    stamp = timestamp(item)
    if not stamp:
        raise RuntimeError("CDSE NDVI catalog item has no observation timestamp")
    return item, stamp


def item_at_timestamp(token, collection_id, bounds, requested_stamp):
    """Select the catalog item nearest one requested source timestamp."""
    requested = datetime.fromisoformat(requested_stamp.replace("Z", "+00:00"))
    query = {"bbox": bounds,
             "datetime": f"{(requested - timedelta(days=2)).isoformat()}/{(requested + timedelta(days=2)).isoformat()}",
             "collections": [f"byoc-{collection_id}"], "limit": 100,
             "fields": {"include": ["id", "properties.datetime", "properties.start_datetime", "properties.end_datetime"]}}
    request = Request(CATALOG_SEARCH_URL, data=json.dumps(query).encode("utf-8"), method="POST", headers={
        "Authorization": f"Bearer {token}", "Content-Type": "application/json", "Accept": "application/geo+json"})
    with urlopen(request, timeout=60) as response:
        features = json.loads(response.read().decode("utf-8")).get("features") or []
    def timestamp(feature):
        props = feature.get("properties") or {}
        return props.get("datetime") or props.get("end_datetime") or props.get("start_datetime") or ""
    candidates = [(feature, timestamp(feature)) for feature in features if timestamp(feature)]
    if not candidates:
        raise RuntimeError("CDSE catalog has no item near requested observation timestamp")
    item, stamp = min(candidates, key=lambda candidate: abs((datetime.fromisoformat(candidate[1].replace("Z", "+00:00")) - requested).total_seconds()))
    return item, stamp


def retrieve_raster(token, collection_id, bounds, observation_stamp, target):
    if target.exists():
        # An interrupted runner handoff must not charge/download the same
        # bounded current raster again.  Reuse only a structurally valid cache.
        with rasterio.open(target) as raster:
            if raster.count == 3 and raster.crs and raster.crs.to_epsg() == 4326:
                return hashlib.sha256(target.read_bytes()).hexdigest()
        raise RuntimeError("existing CDSE NDVI raster cache has unexpected structure")
    observed = datetime.fromisoformat(observation_stamp.replace("Z", "+00:00"))
    # A 10-day product can be selected safely with a narrow window around its
    # catalog timestamp; mosaicking stays provider-side.
    request_body = {
        "input": {"bounds": {"bbox": bounds, "properties": {"crs": "http://www.opengis.net/def/crs/EPSG/0/4326"}},
                  "data": [{"type": f"byoc-{collection_id}", "dataFilter": {"timeRange": {
                      "from": (observed - timedelta(days=1)).isoformat(),
                      "to": (observed + timedelta(days=1)).isoformat()}}}]},
        "output": {"width": math.ceil((bounds[2] - bounds[0]) / REQUESTED_DEGREES),
                   "height": math.ceil((bounds[3] - bounds[1]) / REQUESTED_DEGREES),
                   "responses": [{"identifier": "default", "format": {"type": "image/tiff"}}]},
        "evalscript": "//VERSION=3\nfunction setup(){return {input:[\"NDVI\",\"QFLAG\",\"dataMask\"],output:{bands:3,sampleType:\"FLOAT32\"}};}\nfunction evaluatePixel(s){return [s.NDVI,s.QFLAG,s.dataMask];}"
    }
    request = Request(PROCESS_URL, data=json.dumps(request_body).encode("utf-8"), method="POST", headers={
        "Authorization": f"Bearer {token}", "Content-Type": "application/json", "Accept": "image/tiff"})
    with urlopen(request, timeout=300) as response, target.open("wb") as handle:
        while chunk := response.read(1024 * 1024):
            handle.write(chunk)
    if target.stat().st_size < 20_000:
        raise RuntimeError("CDSE NDVI raster was implausibly small")
    with rasterio.open(target) as raster:
        if raster.count != 3 or raster.crs is None or raster.crs.to_epsg() != 4326:
            raise RuntimeError("CDSE NDVI raster has unexpected structure")
    return hashlib.sha256(target.read_bytes()).hexdigest()


def summarize_tabia(raster_path, geometry):
    with rasterio.open(raster_path) as source:
        data, _ = mask(source, [geometry], crop=True, filled=False)
    ndvi, qflag, data_mask = data[0], data[1], data[2]
    inside = ~np.ma.getmaskarray(ndvi)
    # Convert masked raster bands to ordinary arrays before percentile-style
    # calculations; NumPy otherwise warns that it may ignore a mask.
    ndvi_values = np.asarray(ndvi.filled(np.nan))
    qflag_values = np.asarray(qflag.filled(np.nan))
    availability = np.asarray(data_mask.filled(0))
    valid = inside & np.isfinite(ndvi_values) & (availability > 0)
    # The CLMS NDVI v3 pixel encoding is scaled (physical NDVI = raw / 250 -
    # 0.08).  Retain the provider raster unchanged for provenance, but store
    # physical unitless NDVI in the Tabia summary rather than raw integers.
    values = ndvi_values[valid] / 250.0 - 0.08
    cells = int(inside.sum())
    valid_count = int(values.size)
    coverage = round(100 * valid_count / cells, 1) if cells else 0.0
    # QFLAG is retained as a diagnostic count only. Its product-specific
    # semantics are not converted into an unreviewed quality classification.
    flagged = int(np.asarray(qflag_values[valid] != 0).sum()) if valid_count else 0
    return {"ndvi_mean": round(float(values.mean()), 4) if valid_count else None,
            "ndvi_median": round(float(np.median(values)), 4) if valid_count else None,
            "valid_pixel_count": valid_count, "grid_cell_count": cells, "coverage_pct": coverage,
            "qflag_nonzero_count": flagged,
            "quality_status": "ok" if valid_count and coverage >= 90 else "insufficient_grid_coverage"}


def main():
    settings, collection_id = cdse_settings(); token = access_token(settings)
    tabias, bounds = fetch_tabias_and_bounds()
    requested_stamp = os.environ.get("CDSE_OBSERVATION_TIMESTAMP")
    item, stamp = (item_at_timestamp(token, collection_id, bounds, requested_stamp)
                   if requested_stamp else latest_item(token, collection_id, bounds))
    observation = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    source_age_days = (datetime.now(timezone.utc) - observation).total_seconds() / 86400
    artifact_status = "development" if source_age_days <= MAX_CURRENT_AGE_DAYS else "degraded"
    run_id = f"cdse-clms-ndvi-v3-{observation:%Y%m%dT%H%M%SZ}"
    root = Path("/data/drought"); raw = root / "raw" / "cdse-clms-ndvi-v3"; outputs = root / "outputs"
    raw.mkdir(parents=True, exist_ok=True); outputs.mkdir(parents=True, exist_ok=True)
    raster_path = raw / f"{run_id}.tif"
    checksum = retrieve_raster(token, collection_id, bounds, stamp, raster_path)
    pilot_only = os.environ.get("TSIRD_BASELINE_PILOT_ONLY") == "1"
    candidate_only = os.environ.get("TSIRD_SEASONAL_REFERENCE_CANDIDATE") == "1"
    if not pilot_only and not candidate_only:
        publish_provider_band(raster_path, root / "published" / "ndvi-current.tif", band=1,
                              scale=1 / 250, offset=-0.08, mask_band=3)
    rows = []
    for tabia_id, tabia, woreda, geometry in tabias:
        row = {"tsird_tabia_id": tabia_id, "tabia_name_en": tabia, "woreda_name_en": woreda}
        row.update(summarize_tabia(raster_path, geometry)); rows.append(row)
    base = outputs / run_id
    with base.with_suffix(".csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys()); writer.writeheader(); writer.writerows(rows)
    retrieved_at = datetime.now(timezone.utc).isoformat()
    manifest = {"run_id": run_id, "status": artifact_status, "source_product": PRODUCT,
                "collection_id": collection_id, "native_resolution": NATIVE_RESOLUTION,
                "requested_resolution_degrees": REQUESTED_DEGREES, "observation_timestamp": stamp,
                "raster_path": str(raster_path), "raster_sha256": checksum, "boundary_set_version": "tsird-tabias-v1",
                "included_tabias": len(rows), "source_retrieved_at": retrieved_at,
                "source_age_days": round(source_age_days, 1), "freshness_threshold_days": MAX_CURRENT_AGE_DAYS,
                "catalog_item_id": item.get("id"), "method": "CDSE Process API raster; Tabia pixel-centre zonal mean and median; raw NDVI scaled as raw / 250 - 0.08",
                "baseline_pilot_only": pilot_only,
                "seasonal_reference_candidate_only": candidate_only,
                "publication_note": ("Baseline pilot only. It is not a seasonal baseline, anomaly, drought or "
                                     "food-security classification, response priority, forecast, or published layer."
                                     if pilot_only else
                                     "Seasonal-reference candidate retrieval only. It is retained observed evidence for a "
                                     "versioned same-calendar-month comparison; it is not a forecast, drought or food-security "
                                     "classification, response priority, or published layer."
                                     if candidate_only else
                                     "Development artifact only. NDVI is not a drought or food-security classification.")}
    base.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"run_id": run_id, "status": artifact_status, "rows": len(rows),
                      "raster_bytes": raster_path.stat().st_size}, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (HTTPError, URLError) as exc:
        # Avoid printing response bodies, request headers, or token material.
        raise SystemExit(f"CDSE NDVI request failed: {type(exc).__name__} {getattr(exc, 'code', '')}".strip())
