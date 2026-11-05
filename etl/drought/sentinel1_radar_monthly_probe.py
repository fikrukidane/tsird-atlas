"""Discover a safe completed-month Sentinel-1 GRD candidate for DEV only.

The probe reads catalogue metadata only.  It never downloads radar pixels,
creates a public artifact, or accepts a date, URL, query, or command from n8n.
"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import psycopg2

from cdse_ndvi_tabia_summary import access_token, fetch_tabias_and_bounds
from sentinel2_ndmi_statistical_pilot import STATISTICS_CRS, STATISTICS_URL, settings

STAC_URL = "https://stac.dataspace.copernicus.eu/v1/search"
SOURCE_ID = "cdse-sentinel1-grd-monthly-development"
OUTPUT = Path("/data/drought/outputs/sentinel1-radar-monthly-probe.json")


def completed_month(now: datetime) -> tuple[datetime, datetime]:
    end = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    start = datetime(end.year - (end.month == 1), 12 if end.month == 1 else end.month - 1, 1, tzinfo=timezone.utc)
    return start, end


def dsn() -> str:
    import os
    return " ".join(("host=tsird-postgis", "port=5432", f"dbname={os.environ['POSTGRES_DB']}",
                     f"user={os.environ['POSTGRES_USER']}", f"password={os.environ['POSTGRES_PASSWORD']}"))


def scenes(bounds, start, end):
    body = {
        "collections": ["sentinel-1-grd"], "bbox": bounds,
        "datetime": f"{start.isoformat().replace('+00:00', 'Z')}/{end.isoformat().replace('+00:00', 'Z')}",
        "limit": 100,
    }
    request = Request(STAC_URL, data=json.dumps(body).encode("utf-8"), method="POST",
                      headers={"Content-Type": "application/json", "Accept": "application/geo+json"})
    with urlopen(request, timeout=90) as response:
        payload = json.loads(response.read().decode("utf-8"))
    features = payload.get("features") if isinstance(payload, dict) else None
    if not isinstance(features, list):
        raise RuntimeError("Sentinel-1 STAC response did not contain features")
    def eligible(item):
        if not isinstance(item, dict) or not item.get("id"):
            return False
        properties = item.get("properties") or {}
        polarisations = set(properties.get("sar:polarizations") or [])
        return (properties.get("sar:instrument_mode") == "IW"
                and {"VV", "VH"}.issubset(polarisations)
                and properties.get("sat:orbit_state") == "descending")

    return sorted((item for item in features if eligible(item)), key=lambda item: item["id"])


def fingerprint(items) -> str:
    parts = [f"{item.get('id')}|{(item.get('properties') or {}).get('datetime', '')}" for item in items]
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


def retained_fingerprint(start: datetime, end: datetime):
    with psycopg2.connect(dsn()) as conn, conn.cursor() as cur:
        cur.execute("""SELECT source_fingerprint, run_id FROM tsird.drought_sentinel1_radar_run
                       WHERE source_id=%s AND observation_start=%s AND observation_end=%s
                         AND status IN ('development','degraded')
                       ORDER BY created_at DESC LIMIT 1""", (SOURCE_ID, start, end))
        return cur.fetchone()


def processing_candidate_available(start: datetime, end: datetime) -> bool:
    """Ensure the catalogue scene can actually be served by the configured API.

    The STAC catalogue can list a newly published product before that product is
    usable through the processing service.  One small, unpersisted Tabia request
    prevents a full 748-Tabia run from retrying an unavailable provider path.
    """
    with psycopg2.connect(dsn()) as conn, conn.cursor() as cur:
        cur.execute('''SELECT ST_AsGeoJSON(ST_Transform(t.geometry, 32637))
                       FROM tigray_tabias_ws t JOIN tsird.tabia_identity i USING (tsird_tabia_id)
                       ORDER BY i.tsird_tabia_id LIMIT 1''')
        row = cur.fetchone()
    if not row:
        raise RuntimeError("no canonical Tabia is available for the Sentinel-1 processing gate")
    timestamp = lambda value: value.isoformat().replace("+00:00", "Z")
    body = {
        "input": {
            "bounds": {"geometry": json.loads(row[0]), "properties": {"crs": STATISTICS_CRS}},
            "data": [{"type": "sentinel-1-grd", "dataFilter": {
                "timeRange": {"from": timestamp(start), "to": timestamp(end)},
                "acquisitionMode": "IW", "polarization": "DV", "orbitDirection": "DESCENDING",
            }}],
        },
        "aggregation": {
            "timeRange": {"from": timestamp(start), "to": timestamp(end)},
            "aggregationInterval": {"of": "P1M"}, "resx": 30, "resy": 30,
            "evalscript": '''//VERSION=3
function setup() { return { input: [{ bands: ["VV", "dataMask"] }], output: [{ id: "vv", bands: 1, sampleType: "FLOAT32" }, { id: "dataMask", bands: 1 }] }; }
function evaluatePixel(sample) { return { vv: [sample.VV], dataMask: [sample.dataMask] }; }''',
        },
    }
    request = Request(STATISTICS_URL, data=json.dumps(body).encode("utf-8"), method="POST", headers={
        "Authorization": f"Bearer {access_token(settings())}", "Content-Type": "application/json",
    })
    try:
        with urlopen(request, timeout=150) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code >= 500:
            return False
        raise
    try:
        stats = payload["data"][0]["outputs"]["vv"]["bands"]["B0"]["stats"]
        return int(stats.get("sampleCount") or 0) > int(stats.get("noDataCount") or 0)
    except (IndexError, KeyError, TypeError, ValueError):
        return False


def main() -> int:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    try:
        _, bounds = fetch_tabias_and_bounds()
        start, end = completed_month(datetime.now(timezone.utc))
        items = scenes(bounds, start, end)
        if not items:
            result = {"workflow": "sentinel1-radar-monthly-probe", "status": "degraded",
                      "reason": "CDSE STAC returned no Sentinel-1 IW dual-polarisation scene for the eligible completed month",
                      "observation_start": start.isoformat(), "observation_end": end.isoformat(), "scene_count": 0}
        else:
            candidate = fingerprint(items)
            existing = retained_fingerprint(start, end)
            current = existing and existing[0] == candidate
            processable = current or processing_candidate_available(start, end)
            status = "current" if current else ("ready" if processable else "degraded")
            reason = ("completed-month scene fingerprint is already retained" if current else
                      "completed-month Sentinel-1 scene fingerprint is new or revised" if processable else
                      "CDSE STAC lists eligible Sentinel-1 scenes, but the configured Statistical API returned no processable pixels for the fixed DEV quality gate")
            result = {"workflow": "sentinel1-radar-monthly-probe", "status": status,
                      "reason": reason,
                      "observation_start": start.isoformat(), "observation_end": end.isoformat(),
                      "scene_count": len(items), "source_fingerprint": candidate,
                      "retained_run_id": existing[1] if existing else None,
                      "product": "Sentinel-1 GRD IW dual-polarisation", "source_id": SOURCE_ID}
    except (HTTPError, URLError, TimeoutError) as exc:
        result = {"workflow": "sentinel1-radar-monthly-probe", "status": "unavailable",
                  "reason": f"CDSE Sentinel-1 catalogue request failed: {type(exc).__name__}"}
    except (RuntimeError, ValueError, OSError, psycopg2.Error) as exc:
        result = {"workflow": "sentinel1-radar-monthly-probe", "status": "unavailable",
                  "reason": f"Sentinel-1 probe configuration or response was invalid: {type(exc).__name__}"}
    OUTPUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result))
    return 0 if result["status"] != "unavailable" else 1


if __name__ == "__main__":
    raise SystemExit(main())
