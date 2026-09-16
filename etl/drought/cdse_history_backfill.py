"""Bounded local history backfill for retained Copernicus evidence.

This is deliberately not a continuous archive or a scheduled task.  It picks
at most a small number of evenly distributed source timestamps from the recent
provider catalog, derives the normal source-specific Tabia artifact for each,
and loads it through the same validators/loaders as a standard refresh.
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen

from cdse_ndvi_tabia_summary import CATALOG_SEARCH_URL, access_token, cdse_settings, fetch_tabias_and_bounds

WORK_DIR = Path("/work/drought")
DATA_ROOT = Path("/data/drought")
SCRIPTS = {
    "ndvi": ("cdse_ndvi_tabia_summary.py", "load_cdse_ndvi_summary.py", "CDSE_NDVI_COLLECTION"),
    "swi": ("cdse_swi_tabia_summary.py", "load_cdse_swi_summary.py", "CDSE_SWI_COLLECTION"),
    "lst": ("cdse_lst_tabia_summary.py", "load_cdse_lst_summary.py", "CDSE_LST_COLLECTION"),
}


def settings_for(kind):
    original = os.environ.get("CDSE_NDVI_COLLECTION")
    os.environ["CDSE_NDVI_COLLECTION"] = os.environ[SCRIPTS[kind][2]]
    try:
        return cdse_settings()
    finally:
        if original is None:
            os.environ.pop("CDSE_NDVI_COLLECTION", None)
        else:
            os.environ["CDSE_NDVI_COLLECTION"] = original


def catalog_timestamps(token, collection, bounds, days):
    now = datetime.now(timezone.utc)
    query = {"bbox": bounds, "datetime": f"{(now - timedelta(days=days)).isoformat()}/{now.isoformat()}",
             "collections": [f"byoc-{collection}"], "limit": 100,
             "fields": {"include": ["properties.datetime", "properties.start_datetime", "properties.end_datetime"]}}
    request = Request(CATALOG_SEARCH_URL, data=json.dumps(query).encode(), method="POST", headers={
        "Authorization": f"Bearer {token}", "Content-Type": "application/json", "Accept": "application/geo+json"})
    with urlopen(request, timeout=60) as response:
        features = json.loads(response.read().decode()).get("features") or []
    stamps = set()
    for feature in features:
        props = feature.get("properties") or {}
        stamp = props.get("datetime") or props.get("end_datetime") or props.get("start_datetime")
        if stamp:
            stamps.add(stamp)
    return sorted(stamps)


def evenly_spaced(items, count):
    if len(items) <= count:
        return items
    indices = {round(index * (len(items) - 1) / (count - 1)) for index in range(count)}
    return [items[index] for index in sorted(indices)]


def json_result(output):
    start = output.find("{")
    if start < 0:
        raise ValueError("summary did not report a JSON run record")
    return json.JSONDecoder().raw_decode(output[start:])[0]


def run(kind, stamps):
    script, loader, _ = SCRIPTS[kind]
    completed = []
    for stamp in stamps:
        environment = os.environ.copy()
        environment["CDSE_OBSERVATION_TIMESTAMP"] = stamp
        summary = subprocess.run(["python3", str(WORK_DIR / script)], cwd=WORK_DIR, env=environment,
                                 text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True, timeout=1800)
        run_id = json_result(summary.stdout)["run_id"]
        subprocess.run(["python3", str(WORK_DIR / loader), str(DATA_ROOT / "outputs" / run_id)], cwd=WORK_DIR,
                       env=environment, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True, timeout=600)
        completed.append(run_id)
    return completed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--kind", choices=tuple(SCRIPTS), required=True)
    parser.add_argument("--count", type=int, default=4, choices=range(2, 6))
    parser.add_argument("--days", type=int, default=120, choices=range(30, 366))
    args = parser.parse_args()
    config, collection = settings_for(args.kind)
    _, bounds = fetch_tabias_and_bounds()
    stamps = evenly_spaced(catalog_timestamps(access_token(config), collection, bounds, args.days), args.count)
    if len(stamps) < 2:
        raise RuntimeError("provider catalog has fewer than two retained timestamps for bounded history")
    run_ids = run(args.kind, stamps)
    print(json.dumps({"kind": args.kind, "source_timestamps": len(stamps), "run_ids": run_ids}))


if __name__ == "__main__":
    main()
