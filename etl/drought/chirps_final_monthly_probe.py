"""Find the newest completed, provider-available CHIRPS final month.

This is a bounded discovery gate.  It never downloads a raster, does not
accept a date from n8n, and writes a redacted local receipt that can determine
whether the fixed final-month refresh endpoint is allowed to run.
"""
import json
import os
import urllib.error
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

import psycopg2

BASE_URL = "https://data.chc.ucsb.edu/products/CHIRPS/v3.0/monthly/global/tifs"
OUTPUT = Path("/data/drought/outputs/chirps-v3-final-monthly-probe.json")
BASELINE_START, BASELINE_END = 1991, 2020
MAX_MONTHS_TO_CHECK = 6


def dsn():
    return " ".join(("host=tsird-postgis", "port=5432", f"dbname={os.environ['POSTGRES_DB']}",
                     f"user={os.environ['POSTGRES_USER']}", f"password={os.environ['POSTGRES_PASSWORD']}"))


def prior_months(today: date):
    year, month = today.year, today.month
    for _ in range(MAX_MONTHS_TO_CHECK):
        month -= 1
        if month == 0:
            year, month = year - 1, 12
        yield year, month


def url_for(year, month):
    return f"{BASE_URL}/chirps-v3.0.{year}.{month:02d}.tif"


def provider_available(url):
    request = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "TSIRD-Atlas-development/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status == 200, {"http_status": response.status,
                                             "content_length": response.headers.get("Content-Length"),
                                             "last_modified": response.headers.get("Last-Modified")}
    except urllib.error.HTTPError as error:
        return False, {"http_status": error.code}
    except (urllib.error.URLError, TimeoutError) as error:
        return False, {"error": type(error).__name__}


def retained(run_id):
    manifest = Path("/data/drought/outputs") / f"{run_id}.manifest.json"
    raster = Path("/data/drought/published") / f"{run_id}.tif"
    if not manifest.is_file() or not raster.is_file():
        return False
    try:
        with psycopg2.connect(dsn()) as conn, conn.cursor() as cur:
            cur.execute("SELECT EXISTS (SELECT 1 FROM tsird.drought_rainfall_run WHERE run_id=%s)", (run_id,))
            return bool(cur.fetchone()[0])
    except psycopg2.Error:
        return False


def main():
    receipt = {"workflow": "chirps-final-monthly-probe", "status": "unavailable",
               "checked_at": datetime.now(timezone.utc).isoformat(), "checked_months": []}
    for year, month in prior_months(datetime.now(timezone.utc).date()):
        url = url_for(year, month)
        available, evidence = provider_available(url)
        receipt["checked_months"].append({"year": year, "month": month, "available": available, **evidence})
        if not available:
            continue
        run_id = f"chirps-v3-{year}-{month}-baseline-{BASELINE_START}-{BASELINE_END}"
        receipt.update({"analysis_year": year, "month": month, "run_id": run_id,
                        "source_url": url, "provider": evidence})
        receipt["status"] = "current" if retained(run_id) else "ready"
        receipt["reason"] = ("latest provider-available final month is already retained and loaded"
                             if receipt["status"] == "current"
                             else "latest provider-available final month is not yet retained")
        break
    else:
        receipt["reason"] = "no provider-available completed final month found in the bounded lookback"
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
