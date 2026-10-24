"""Build a bounded, development-only Sentinel-2 L2A NDMI pilot artifact.

The Copernicus Data Space Statistical API performs the imagery calculation and
polygon aggregation.  This script retains only compact Tabia statistics and a
redacted manifest--never raw scenes, OAuth material, or a provider response
body.  It is intentionally limited to twenty deterministic Tabias and has no
publish or schedule path.
"""
import argparse
import csv
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import psycopg2

from cdse_ndvi_tabia_summary import access_token

STATISTICS_URL = "https://sh.dataspace.copernicus.eu/statistics/v1"
SOURCE_ID = "cdse-sentinel2-l2a-ndmi-pilot"
PRODUCT = "Copernicus Sentinel-2 Level-2A surface reflectance"
NATIVE_RESOLUTION = "20 m (B11/SCL grid; B08 resampled by provider)"
PROCESSING_VERSION = "tsird-s2-ndmi-statistical-pilot.v1"
PILOT_TABIA_LIMIT = 20
MIN_VALID_COVERAGE_PCT = 70.0
VALID_SCL_CLASSES = (4, 5)  # vegetation and bare-soil classes; cloud/shadow/water excluded


def dsn():
    return " ".join(("host=tsird-postgis", "port=5432", f"dbname={os.environ['POSTGRES_DB']}",
                     f"user={os.environ['POSTGRES_USER']}", f"password={os.environ['POSTGRES_PASSWORD']}"))


def settings():
    values = {name: os.environ.get(name) for name in (
        "CDSE_OAUTH_CLIENT_ID", "CDSE_OAUTH_CLIENT_SECRET", "CDSE_OAUTH_TOKEN_URL")}
    if not all(values.values()):
        raise RuntimeError("CDSE Sentinel-2 pilot configuration is incomplete")
    return values


def pilot_tabias():
    """Choose a repeatable technical sample without claiming it is representative."""
    with psycopg2.connect(dsn()) as conn, conn.cursor() as cur:
        cur.execute('''SELECT i.tsird_tabia_id, t."TABIA", t."WEREDA", ST_AsGeoJSON(t.geometry)
                       FROM tigray_tabias_ws t JOIN tsird.tabia_identity i USING (tsird_tabia_id)
                       ORDER BY md5(i.tsird_tabia_id)
                       LIMIT %s''', (PILOT_TABIA_LIMIT,))
        return [(row[0], row[1], row[2], json.loads(row[3])) for row in cur.fetchall()]


def completed_window(now):
    """A fixed 30-day UTC window ending five complete days before this run."""
    end = datetime(now.year, now.month, now.day, tzinfo=timezone.utc) - timedelta(days=5)
    return end - timedelta(days=30), end


def evalscript():
    return f'''//VERSION=3
function setup() {{
  return {{
    input: [{{bands:["B08", "B11", "SCL", "dataMask"]}}],
    output: [
      {{id:"ndmi", bands:1, sampleType:"FLOAT32"}},
      {{id:"dataMask", bands:1, sampleType:"UINT8"}}
    ]
  }};
}}
function evaluatePixel(sample) {{
  const validClass = sample.SCL === 4 || sample.SCL === 5;
  const denominator = sample.B08 + sample.B11;
  const valid = sample.dataMask === 1 && validClass && denominator > 0;
  return {{ndmi:[valid ? (sample.B08 - sample.B11) / denominator : 0], dataMask:[valid ? 1 : 0]}};
}}'''


def request_body(geometry, start, end):
    return {
        "input": {
            "bounds": {"geometry": geometry, "properties": {"crs": "http://www.opengis.net/def/crs/EPSG/0/4326"}},
            "data": [{"type": "sentinel-2-l2a", "dataFilter": {"mosaickingOrder": "leastCC"}}],
        },
        "aggregation": {
            "timeRange": {"from": start.isoformat().replace("+00:00", "Z"), "to": end.isoformat().replace("+00:00", "Z")},
            "aggregationInterval": {"of": "P30D"},
            "evalscript": evalscript(),
            "resx": 20,
            "resy": 20,
        },
        "calculations": {"ndmi": {"statistics": {"default": {"percentiles": {"k": [50]}}}}},
    }


def statistics(token, geometry, start, end):
    request = Request(STATISTICS_URL, data=json.dumps(request_body(geometry, start, end)).encode("utf-8"), method="POST",
                      headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", "Accept": "application/json"})
    with urlopen(request, timeout=120) as response:
        payload = json.loads(response.read().decode("utf-8"))
    data = payload.get("data") or []
    if len(data) != 1:
        raise RuntimeError("Sentinel-2 statistics response did not contain one 30-day interval")
    try:
        return data[0]["outputs"]["ndmi"]["bands"]["B0"]["stats"]
    except (KeyError, TypeError) as exc:
        raise RuntimeError("Sentinel-2 statistics response omitted NDMI statistics") from exc


def parse_statistics(stats):
    total = int(stats.get("sampleCount", 0))
    missing = int(stats.get("noDataCount", total))
    valid = max(0, total - missing)
    coverage = round(100 * valid / total, 1) if total else 0.0
    percentiles = stats.get("percentiles") or {}
    median = percentiles.get("50.0", percentiles.get("50"))
    return {
        "ndmi_mean": round(float(stats["mean"]), 4) if valid and stats.get("mean") is not None else None,
        "ndmi_median": round(float(median), 4) if valid and median is not None else None,
        "valid_pixel_count": valid,
        "grid_cell_count": total,
        "coverage_pct": coverage,
        "quality_status": "ok" if valid and coverage >= MIN_VALID_COVERAGE_PCT else "insufficient_evidence",
    }


def main():
    parser = argparse.ArgumentParser(description="Run the bounded development Sentinel-2 NDMI pilot")
    parser.add_argument("--dry-run", action="store_true", help="validate the fixed request contract without OAuth or data access")
    args = parser.parse_args()
    start, end = completed_window(datetime.now(timezone.utc))
    if args.dry_run:
        print(json.dumps({"source_id": SOURCE_ID, "product": PRODUCT, "observation_start": start.isoformat(),
                          "observation_end": end.isoformat(), "pilot_tabia_limit": PILOT_TABIA_LIMIT,
                          "native_resolution": NATIVE_RESOLUTION, "valid_scl_classes": list(VALID_SCL_CLASSES),
                          "min_valid_coverage_pct": MIN_VALID_COVERAGE_PCT, "request_contract": request_body({"type": "Polygon", "coordinates": []}, start, end)}, indent=2))
        return
    token = access_token(settings())
    tabias = pilot_tabias()
    if not tabias:
        raise RuntimeError("No canonical Tabias are available for the Sentinel-2 pilot")
    run_id = f"cdse-s2-l2a-ndmi-pilot-{start:%Y%m%d}-{end:%Y%m%d}"
    rows = []
    for tabia_id, tabia, woreda, geometry in tabias:
        row = {"tsird_tabia_id": tabia_id, "tabia_name_en": tabia, "woreda_name_en": woreda}
        row.update(parse_statistics(statistics(token, geometry, start, end)))
        rows.append(row)
    root = Path("/data/drought/outputs")
    root.mkdir(parents=True, exist_ok=True)
    base = root / run_id
    with base.with_suffix(".csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    retrieved = datetime.now(timezone.utc).isoformat()
    status = "development" if any(row["quality_status"] == "ok" for row in rows) else "degraded"
    manifest = {
        "run_id": run_id, "source_id": SOURCE_ID, "source_product": PRODUCT, "status": status,
        "observation_start": start.isoformat(), "observation_end": end.isoformat(), "native_resolution": NATIVE_RESOLUTION,
        "mosaicking_order": "leastCC", "valid_scl_classes": list(VALID_SCL_CLASSES),
        "min_valid_coverage_pct": MIN_VALID_COVERAGE_PCT, "pilot_tabia_limit": PILOT_TABIA_LIMIT,
        "included_tabias": len(rows), "source_retrieved_at": retrieved, "processing_version": PROCESSING_VERSION,
        "method": "CDSE Sentinel Hub Statistical API; Sentinel-2 L2A B08/B11 NDMI at 20 m with SCL 4/5 and dataMask only; one least-cloudy 30-day mosaic per Tabia.",
        "publication_note": "Development-only technical pilot. It is not a drought or food-security classification, forecast, allocation rule, composite score, or public release.",
        "geoinfotech_acknowledgement": "The educational index-selection framing refers to Geoinfotech's Spatial Indices Analysis explainer shared with TSIRD on 2026-10-24. Geoinfotech does not supply imagery, validation, or results.",
    }
    base.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"run_id": run_id, "status": status, "rows": len(rows), "quality_ok_rows": sum(row["quality_status"] == "ok" for row in rows)}, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (HTTPError, URLError) as exc:
        raise SystemExit(f"Sentinel-2 Statistical API request failed: {type(exc).__name__} {getattr(exc, 'code', '')}".strip())
