"""Retain the fixed 2018--2025 seasonal-reference evidence matrix.

This is a manual, no-parameter development task.  It acquires one strict
same-calendar-month NDVI observation and the third WaPOR dekad for each slot.
It cannot publish a current layer, create priority classes, or schedule itself.
"""
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from seasonal_baseline_pilot import select_ndvi_timestamp
from cdse_ndvi_tabia_summary import access_token, cdse_settings, fetch_tabias_and_bounds

WORK_DIR = Path("/work/drought")
DATA_ROOT = Path("/data/drought")
CANDIDATE_YEARS = tuple(range(2018, 2026))
CANDIDATE_MONTHS = tuple(range(1, 13))
SLOTS = tuple((year, month) for year in CANDIDATE_YEARS for month in CANDIDATE_MONTHS)


def decode_run(output):
    start = output.find("{")
    if start < 0:
        raise RuntimeError("seasonal-reference child did not return a receipt")
    return json.JSONDecoder().raw_decode(output[start:])[0]["run_id"]


def invoke(script, loader, env):
    # Provider catalogue/COG delivery can have a short transient failure. One
    # bounded retry preserves the fixed matrix while avoiding a needless loss
    # of an otherwise available historical month.
    failure = None
    for attempt in range(2):
        try:
            summary = subprocess.run(["python3", str(WORK_DIR / script)], cwd=WORK_DIR, env=env,
                                     text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     check=True, timeout=3600)
            run_id = decode_run(summary.stdout)
            subprocess.run(["python3", str(WORK_DIR / loader), str(DATA_ROOT / "outputs" / run_id)], cwd=WORK_DIR,
                           env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           check=True, timeout=600)
            return run_id
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            failure = exc
            if attempt == 0:
                time.sleep(15)
    raise failure


def retained_candidate_run(run_id):
    """Reuse only an explicitly candidate/pilot-only manifest from a prior stopped run."""
    manifest_path = DATA_ROOT / "outputs" / f"{run_id}.manifest.json"
    if not manifest_path.is_file():
        return False
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return bool(manifest.get("seasonal_reference_candidate_only") or manifest.get("baseline_pilot_only"))


def main():
    _, collection = cdse_settings()
    _, bounds = fetch_tabias_and_bounds()
    token = access_token(cdse_settings()[0])
    results = []
    for year, month in SLOTS:
        ndvi = select_ndvi_timestamp(token, collection, bounds, year, month)
        ndvi_env = os.environ.copy()
        ndvi_env.update({"CDSE_OBSERVATION_TIMESTAMP": ndvi["observation_timestamp"],
                         "TSIRD_SEASONAL_REFERENCE_CANDIDATE": "1"})
        wapor_env = os.environ.copy()
        wapor_env.update({"WAPOR_PERIOD_START": f"{year:04d}-{month:02d}-21",
                          "TSIRD_SEASONAL_REFERENCE_CANDIDATE": "1"})
        ndvi_run_id = f"cdse-clms-ndvi-v3-{datetime.fromisoformat(ndvi['observation_timestamp'].replace('Z', '+00:00')):%Y%m%dT%H%M%SZ}"
        wapor_run_id = f"fao-wapor-v3-l2-{year:04d}{month:02d}-d3"
        try:
            ndvi_run = ndvi_run_id if retained_candidate_run(ndvi_run_id) else invoke("cdse_ndvi_tabia_summary.py", "load_cdse_ndvi_summary.py", ndvi_env)
            wapor_run = wapor_run_id if retained_candidate_run(wapor_run_id) else invoke("wapor_tabia_summary.py", "load_wapor_summary.py", wapor_env)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            raise RuntimeError(f"seasonal-reference history stopped at {year:04d}-{month:02d}; no later slot was attempted") from exc
        results.append({"year": year, "month": month, "ndvi_run_id": ndvi_run,
                        "ndvi_observation_timestamp": ndvi["observation_timestamp"], "wapor_run_id": wapor_run,
                        "wapor_period_start": f"{year:04d}-{month:02d}-21"})
    receipt = {
        "status": "completed_reference_build_required",
        "seasonal_reference_candidate_only": True,
        "candidate_period": "2018-2025",
        "fixed_years": list(CANDIDATE_YEARS), "fixed_months": list(CANDIDATE_MONTHS),
        "slot_count": len(results), "slots": results,
        "started_or_retrieved_at": datetime.now(timezone.utc).isoformat(),
        "next_step": "Build the separate candidate seasonal reference, review its coverage and seasonal plausibility, then expose observed relative-to-reference evidence. Do not change priority replay.",
    }
    target = DATA_ROOT / "outputs" / "seasonal-reference-history-receipt.json"
    target.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps({"status": receipt["status"], "slots": len(results), "receipt": target.name}, indent=2))


if __name__ == "__main__":
    main()
