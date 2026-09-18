"""Build bounded monthly/decadal retained evidence from January 2026 onward.

This is local-development processing only.  It preserves each Tigray-bounded
provider raster, derives its matching 748-Tabia summary, and updates the shared
catalogue.  It does not create a priority score, publication, or schedule.
"""
import argparse
import json
import os
import subprocess
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen

from cdse_ndvi_tabia_summary import CATALOG_SEARCH_URL, access_token, cdse_settings, fetch_tabias_and_bounds


WORK = Path("/work/drought")
ROOT = Path("/data/drought")
CDSE = {
    "ndvi": ("cdse_ndvi_tabia_summary.py", "load_cdse_ndvi_summary.py", "ndvi", "2026-01-21T00:00:00Z"),
    "swi": ("cdse_swi_tabia_summary.py", "load_cdse_swi_summary.py", "swi", "2026-01-21T12:00:00Z"),
    "lst": ("cdse_lst_tabia_summary.py", "load_cdse_lst_summary.py", "lst", "2026-01-21T12:00:00Z"),
}


def months(value):
    result = []
    for token in value.split(","):
        year, month = map(int, token.strip().split("-"))
        if year != 2026 or not 1 <= month <= 12:
            raise argparse.ArgumentTypeError("months must be 2026-MM values")
        result.append((year, month))
    return result


def stamp(template, year, month):
    return f"{year}-{month:02d}" + template[7:]


def run(command, environment):
    result = subprocess.run(command, cwd=WORK, env=environment, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            timeout=1800)
    if result.returncode:
        last_line = next((line for line in reversed(result.stdout.splitlines()) if line.strip()), "unknown local processing error")
        raise RuntimeError(last_line[:300])
    return result.stdout


def run_id_from(output):
    start = output.find("{")
    if start < 0:
        raise RuntimeError("summary did not return a run identifier")
    return json.JSONDecoder().raw_decode(output[start:])[0]["run_id"]


def cdse_settings_for(kind):
    """Read the configured collection for one indicator without exposing it."""
    original = os.environ.get("CDSE_NDVI_COLLECTION")
    os.environ["CDSE_NDVI_COLLECTION"] = os.environ[{
        "ndvi": "CDSE_NDVI_COLLECTION", "swi": "CDSE_SWI_COLLECTION", "lst": "CDSE_LST_COLLECTION",
    }[kind]]
    try:
        return cdse_settings()
    finally:
        if original is None:
            os.environ.pop("CDSE_NDVI_COLLECTION", None)
        else:
            os.environ["CDSE_NDVI_COLLECTION"] = original


def catalog_stamps(token, collection, bounds, start, end):
    query = {
        "bbox": bounds, "datetime": f"{start.isoformat()}/{end.isoformat()}",
        "collections": [f"byoc-{collection}"], "limit": 100,
        "fields": {"include": ["properties.datetime", "properties.start_datetime", "properties.end_datetime"]},
    }
    request = Request(CATALOG_SEARCH_URL, data=json.dumps(query).encode(), method="POST", headers={
        "Authorization": f"Bearer {token}", "Content-Type": "application/json", "Accept": "application/geo+json"})
    with urlopen(request, timeout=60) as response:
        features = json.loads(response.read().decode()).get("features") or []
    return sorted({(feature.get("properties") or {}).get("datetime") or
                   (feature.get("properties") or {}).get("end_datetime") or
                   (feature.get("properties") or {}).get("start_datetime")
                   for feature in features} - {None})


def resolved_cdse_stamp(kind, year, month, token, collection, bounds):
    """Choose a real provider timestamp close to the 21st, never synthesize one."""
    desired = datetime(year, month, 21, 12, tzinfo=timezone.utc)
    nearby = catalog_stamps(token, collection, bounds, desired - timedelta(days=2), desired + timedelta(days=2))
    if not nearby:
        end = datetime(year + (month == 12), 1 if month == 12 else month + 1, 1, tzinfo=timezone.utc)
        nearby = catalog_stamps(token, collection, bounds, datetime(year, month, 1, tzinfo=timezone.utc), end)
    if not nearby:
        raise RuntimeError(f"no {kind} provider timestamp is available for {year}-{month:02d}")
    return min(nearby, key=lambda item: abs(datetime.fromisoformat(item.replace("Z", "+00:00")) - desired))


def process_cdse(kind, year, month, observation_timestamp):
    summary, loader, catalogue_kind, template = CDSE[kind]
    environment = os.environ.copy()
    environment["CDSE_OBSERVATION_TIMESTAMP"] = observation_timestamp
    environment["TSIRD_RETAIN_HISTORICAL_ONLY"] = "1"
    output = run(["python3", str(WORK / summary)], environment)
    run_id = run_id_from(output)
    base = ROOT / "outputs" / run_id
    run(["python3", str(WORK / loader), str(base)], environment)
    run(["python3", str(WORK / "catalog_evidence_raster.py"), catalogue_kind, str(base)], environment)
    return run_id


def process_wapor(year, month):
    # Retain the third dekad: it gives one complete monthly-end agricultural
    # water-use snapshot and avoids manufacturing a monthly aggregation.
    period_start = date(year, month, 21)
    environment = os.environ.copy()
    environment["WAPOR_PERIOD_START"] = period_start.isoformat()
    environment["TSIRD_RETAIN_HISTORICAL_ONLY"] = "1"
    output = run(["python3", str(WORK / "wapor_tabia_summary.py")], environment)
    run_id = run_id_from(output)
    base = ROOT / "outputs" / run_id
    run(["python3", str(WORK / "load_wapor_summary.py"), str(base)], environment)
    run(["python3", str(WORK / "catalog_evidence_raster.py"), "wapor", str(base)], environment)
    return run_id


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--kind", choices=("ndvi", "swi", "lst", "wapor", "all"), required=True)
    parser.add_argument("--months", type=months, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    kinds = tuple(CDSE) + ("wapor",) if args.kind == "all" else (args.kind,)
    plan = [{"kind": kind, "month": f"{year}-{month:02d}"} for kind in kinds for year, month in args.months]
    if args.dry_run:
        print(json.dumps({"development_only": True, "plan": plan}, indent=2)); return
    complete, failures = [], []
    bounds = None
    cdse = {}
    for kind in kinds:
        if kind == "wapor":
            continue
        config, collection = cdse_settings_for(kind)
        if bounds is None:
            _, bounds = fetch_tabias_and_bounds()
        cdse[kind] = (access_token(config), collection)
    for item in plan:
        year, month = map(int, item["month"].split("-"))
        try:
            if item["kind"] == "wapor":
                run_id = process_wapor(year, month)
                complete.append({**item, "run_id": run_id})
            else:
                token, collection = cdse[item["kind"]]
                observation_timestamp = resolved_cdse_stamp(item["kind"], year, month, token, collection, bounds)
                run_id = process_cdse(item["kind"], year, month, observation_timestamp)
                complete.append({**item, "source_timestamp": observation_timestamp, "run_id": run_id})
        except Exception as exc:
            failures.append({**item, "error": str(exc)})
    # A backfill must never leave an older retained observation as the stable
    # native display. Rebuild the requested current paths from the same
    # observation-date rule used by the dashboard and MapServer Tabia layers.
    if complete:
        for kind in kinds:
            run(["python3", str(WORK / "sync_current_evidence.py"), "--kind", kind, "--apply"], os.environ.copy())
    print(json.dumps({"development_only": True, "completed": complete, "failures": failures}, indent=2))
    if failures:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
