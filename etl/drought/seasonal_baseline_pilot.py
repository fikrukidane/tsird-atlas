"""Run the fixed TSIRD seasonal-baseline technical pilot, and nothing more.

The matrix is deliberately embedded here: callers cannot choose dates, source
URLs, paths, models, or publication behaviour. It retains technical pilot
artifacts only and fails closed if a required provider record cannot be read.
"""
import json
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen

from cdse_ndvi_tabia_summary import CATALOG_SEARCH_URL, access_token, cdse_settings, fetch_tabias_and_bounds

WORK_DIR = Path("/work/drought")
DATA_ROOT = Path("/data/drought")
PILOT_YEARS = (2018, 2021, 2025)
PILOT_MONTHS = (2, 8, 11)
PILOT_SLOTS = tuple((year, month) for year in PILOT_YEARS for month in PILOT_MONTHS)


def record_timestamp(feature):
    properties = feature.get("properties") or {}
    return properties.get("datetime") or properties.get("end_datetime") or properties.get("start_datetime")


def select_ndvi_timestamp(token, collection, bounds, year, month):
    start = datetime(year, month, 1, tzinfo=timezone.utc)
    next_month = datetime(year + (month == 12), 1 if month == 12 else month + 1, 1, tzinfo=timezone.utc)
    # CDSE treats an end-at-midnight bound as inclusive. Keep the requested
    # target month strict so a first-of-next-month observation is never
    # silently labelled as a same-calendar-month pilot record.
    end = next_month - timedelta(microseconds=1)
    query = {
        "bbox": bounds,
        "datetime": f"{start.isoformat()}/{end.isoformat()}",
        "collections": [f"byoc-{collection}"],
        "limit": 100,
        "fields": {"include": ["id", "properties.datetime", "properties.start_datetime", "properties.end_datetime"]},
    }
    request = Request(CATALOG_SEARCH_URL, data=json.dumps(query).encode("utf-8"), method="POST", headers={
        "Authorization": f"Bearer {token}", "Content-Type": "application/json", "Accept": "application/geo+json"})
    with urlopen(request, timeout=60) as response:
        features = json.loads(response.read().decode("utf-8")).get("features") or []
    candidates = [(feature, record_timestamp(feature)) for feature in features if record_timestamp(feature)]
    if not candidates:
        raise RuntimeError(f"CDSE NDVI has no selectable record for fixed pilot slot {year:04d}-{month:02d}")
    item, timestamp = max(candidates, key=lambda candidate: candidate[1])
    observed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    if observed.year != year or observed.month != month:
        raise RuntimeError(f"CDSE NDVI returned an out-of-month record for fixed pilot slot {year:04d}-{month:02d}")
    return {"catalog_item_id": item.get("id"), "observation_timestamp": timestamp}


def decode_run(output):
    start = output.find("{")
    if start < 0:
        raise RuntimeError("pilot child did not return a run receipt")
    return json.JSONDecoder().raw_decode(output[start:])[0]["run_id"]


def invoke(script, loader, env):
    summary = subprocess.run(["python3", str(WORK_DIR / script)], cwd=WORK_DIR, env=env,
                             text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             check=True, timeout=3600)
    run_id = decode_run(summary.stdout)
    subprocess.run(["python3", str(WORK_DIR / loader), str(DATA_ROOT / "outputs" / run_id)], cwd=WORK_DIR,
                   env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                   check=True, timeout=600)
    return run_id


def main():
    settings, collection = cdse_settings()
    _, bounds = fetch_tabias_and_bounds()
    token = access_token(settings)
    results = []
    for year, month in PILOT_SLOTS:
        ndvi = select_ndvi_timestamp(token, collection, bounds, year, month)
        ndvi_env = os.environ.copy()
        ndvi_env.update({"CDSE_OBSERVATION_TIMESTAMP": ndvi["observation_timestamp"], "TSIRD_BASELINE_PILOT_ONLY": "1"})
        wapor_env = os.environ.copy()
        wapor_env.update({"WAPOR_PERIOD_START": f"{year:04d}-{month:02d}-21", "TSIRD_BASELINE_PILOT_ONLY": "1"})
        try:
            ndvi_run = invoke("cdse_ndvi_tabia_summary.py", "load_cdse_ndvi_summary.py", ndvi_env)
            wapor_run = invoke("wapor_tabia_summary.py", "load_wapor_summary.py", wapor_env)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            raise RuntimeError(f"fixed pilot stopped at {year:04d}-{month:02d}; no later slot was attempted") from exc
        results.append({"year": year, "month": month, "ndvi": {**ndvi, "run_id": ndvi_run},
                        "wapor": {"period_start": f"{year:04d}-{month:02d}-21", "run_id": wapor_run}})
    receipt = {
        "status": "completed_review_required", "baseline_pilot_only": True,
        "candidate_period": "2018-2025", "fixed_years": list(PILOT_YEARS), "fixed_months": list(PILOT_MONTHS),
        "slots": results, "started_or_retrieved_at": datetime.now(timezone.utc).isoformat(),
        "next_step": "Review source records, quality, coverage and storage before any bounded history retrieval. Do not calculate a baseline or alter priority replay.",
    }
    target = DATA_ROOT / "outputs" / "seasonal-baseline-pilot-receipt.json"
    target.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps({"status": receipt["status"], "slots": len(results), "receipt": target.name}, indent=2))


if __name__ == "__main__":
    main()
