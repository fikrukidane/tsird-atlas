"""Build one fixed, full-coverage DEV Sentinel-2 NDMI evidence artifact.

The Copernicus Data Space Statistical API calculates the cloud- and
shadow-masked B08/B11 NDMI and polygon statistics.  Only compact statistics
and a redacted manifest are retained.  This has no schedule, no retry loop and
no route to production or public-release assets.
"""
import csv
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import psycopg2

from cdse_ndvi_tabia_summary import access_token
from sentinel2_ndmi_statistical_pilot import (
    MIN_VALID_COVERAGE_PCT, PRODUCT, STATISTICS_CRS,
    STATISTICS_URL, VALID_SCL_CLASSES, parse_statistics, settings,
)

SOURCE_ID = "cdse-sentinel2-l2a-ndmi-full-development"
PROCESSING_VERSION = "tsird-s2-ndmi-statistical-full-dev.v2"
TABIA_COUNT = 748
WINDOW_DAYS = 90
ANALYTICAL_RESOLUTION_METERS = 25
NATIVE_RESOLUTION = "25 m (full-coverage analytical grid; B11/SCL native grid is 20 m)"
REQUEST_INTERVAL_SECONDS = 5
MAX_RATE_LIMIT_RETRIES = 6
MAX_RETRY_AFTER_SECONDS = 120


def dsn():
    return " ".join(("host=tsird-postgis", "port=5432", f"dbname={os.environ['POSTGRES_DB']}",
                     f"user={os.environ['POSTGRES_USER']}", f"password={os.environ['POSTGRES_PASSWORD']}"))


def full_tabias():
    """Return exactly the canonical regional set, ordered for a reproducible run."""
    with psycopg2.connect(dsn()) as conn, conn.cursor() as cur:
        cur.execute('''SELECT i.tsird_tabia_id, t."TABIA", t."WEREDA", ST_AsGeoJSON(ST_Transform(t.geometry, 32637))
                       FROM tigray_tabias_ws t JOIN tsird.tabia_identity i USING (tsird_tabia_id)
                       ORDER BY i.tsird_tabia_id''')
        rows = [(row[0], row[1], row[2], json.loads(row[3])) for row in cur.fetchall()]
    if len(rows) != TABIA_COUNT:
        raise RuntimeError(f"Expected exactly {TABIA_COUNT} canonical Tabias, found {len(rows)}")
    return rows


def completed_window(now):
    """A fixed 90-day UTC review window ending five completed days before run."""
    end = datetime(now.year, now.month, now.day, tzinfo=timezone.utc) - timedelta(days=5)
    return end - timedelta(days=WINDOW_DAYS), end


def evalscript():
    return '''//VERSION=3
function setup() {
  return {
    input: [{bands:["B08", "B11", "SCL", "dataMask"]}],
    output: [
      {id:"ndmi", bands:1, sampleType:"FLOAT32"},
      {id:"dataMask", bands:1, sampleType:"UINT8"}
    ]
  };
}
function evaluatePixel(sample) {
  const validClass = sample.SCL === 4 || sample.SCL === 5;
  const denominator = sample.B08 + sample.B11;
  const valid = sample.dataMask === 1 && validClass && denominator > 0;
  return {ndmi:[valid ? (sample.B08 - sample.B11) / denominator : 0], dataMask:[valid ? 1 : 0]};
}'''


def request_body(geometry, start, end):
    return {
        "input": {
            "bounds": {"geometry": geometry, "properties": {"crs": STATISTICS_CRS}},
            "data": [{"type": "sentinel-2-l2a", "dataFilter": {"mosaickingOrder": "leastCC"}}],
        },
        "aggregation": {
            "timeRange": {"from": start.isoformat().replace("+00:00", "Z"), "to": end.isoformat().replace("+00:00", "Z")},
            "aggregationInterval": {"of": "P90D"}, "evalscript": evalscript(),
            "resx": ANALYTICAL_RESOLUTION_METERS, "resy": ANALYTICAL_RESOLUTION_METERS,
        },
        "calculations": {"ndmi": {"statistics": {"default": {"percentiles": {"k": [50]}}}}},
    }


def statistics(token, geometry, start, end):
    request = Request(STATISTICS_URL, data=json.dumps(request_body(geometry, start, end)).encode("utf-8"), method="POST",
                      headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", "Accept": "application/json"})
    for attempt in range(MAX_RATE_LIMIT_RETRIES + 1):
        try:
            with urlopen(request, timeout=120) as response:
                payload = json.loads(response.read().decode("utf-8"))
            break
        except HTTPError as exc:
            if exc.code != 429 or attempt >= MAX_RATE_LIMIT_RETRIES:
                raise
            # CDSE documents Retry-After in milliseconds.  Respect it without
            # retaining a provider body or retrying an entire regional run.
            try:
                wait_seconds = float(exc.headers.get("Retry-After", "0")) / 1000
            except (TypeError, ValueError):
                wait_seconds = 0
            wait_seconds = min(MAX_RETRY_AFTER_SECONDS, max(REQUEST_INTERVAL_SECONDS, wait_seconds))
            print(json.dumps({"rate_limited": True, "retry_in_seconds": wait_seconds, "attempt": attempt + 1}), flush=True)
            time.sleep(wait_seconds)
    data = payload.get("data") or []
    if len(data) != 1:
        raise RuntimeError("Sentinel-2 statistics response did not contain one 90-day interval")
    try:
        return data[0]["outputs"]["ndmi"]["bands"]["B0"]["stats"]
    except (KeyError, TypeError) as exc:
        raise RuntimeError("Sentinel-2 statistics response omitted NDMI statistics") from exc


def main():
    start, end = completed_window(datetime.now(timezone.utc))
    token = access_token(settings())
    tabias = full_tabias()
    run_id = f"cdse-s2-l2a-ndmi-full-dev-{start:%Y%m%d}-{end:%Y%m%d}"
    rows = []
    for position, (tabia_id, tabia, woreda, geometry) in enumerate(tabias, start=1):
        row = {"tsird_tabia_id": tabia_id, "tabia_name_en": tabia, "woreda_name_en": woreda}
        row.update(parse_statistics(statistics(token, geometry, start, end)))
        rows.append(row)
        if position % 25 == 0:
            print(json.dumps({"progress": position, "of": TABIA_COUNT}), flush=True)
        if position < TABIA_COUNT:
            time.sleep(REQUEST_INTERVAL_SECONDS)
    root = Path("/data/drought/outputs")
    root.mkdir(parents=True, exist_ok=True)
    base = root / run_id
    with base.with_suffix(".csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader(); writer.writerows(rows)
    retrieved = datetime.now(timezone.utc).isoformat()
    status = "development" if any(row["quality_status"] == "ok" for row in rows) else "degraded"
    manifest = {
        "run_id": run_id, "source_id": SOURCE_ID, "run_scope": "full_development", "source_product": PRODUCT,
        "status": status, "observation_start": start.isoformat(), "observation_end": end.isoformat(),
        "native_resolution": NATIVE_RESOLUTION, "mosaicking_order": "leastCC", "valid_scl_classes": list(VALID_SCL_CLASSES),
        "min_valid_coverage_pct": MIN_VALID_COVERAGE_PCT, "tabia_count": TABIA_COUNT,
        "request_interval_seconds": REQUEST_INTERVAL_SECONDS, "max_rate_limit_retries": MAX_RATE_LIMIT_RETRIES,
        "source_retrieved_at": retrieved, "processing_version": PROCESSING_VERSION,
        "method": "CDSE Sentinel Hub Statistical API; Sentinel-2 L2A B08/B11 NDMI at 20 m with SCL 4/5 and dataMask only; one least-cloudy 90-day mosaic per Tabia.",
        "publication_note": "Development-only observed surface-condition context. Not a drought, food-security, priority, forecast, allocation, or response decision product.",
        "geoinfotech_acknowledgement": "The educational index-selection framing refers to Geoinfotech's Spatial Indices Analysis explainer shared with TSIRD on 2026-10-24. Geoinfotech does not supply imagery, validation, or results.",
    }
    base.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"run_id": run_id, "status": status, "rows": len(rows), "quality_ok_rows": sum(row["quality_status"] == "ok" for row in rows)}))


if __name__ == "__main__":
    try:
        main()
    except HTTPError as exc:
        detail = "no safe provider detail"
        try:
            response = json.loads(exc.read().decode("utf-8", errors="replace"))
            if isinstance(response, dict): detail = str(response.get("message") or response.get("reason") or response.get("error") or detail)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            pass
        raise SystemExit(f"Sentinel-2 Statistical API request failed: HTTP {exc.code}; {detail[:300]}")
    except URLError as exc:
        raise SystemExit(f"Sentinel-2 Statistical API request failed: {type(exc).__name__}")
