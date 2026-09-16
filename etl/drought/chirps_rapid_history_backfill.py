"""Retain real CHIRPS preliminary six-pentad evidence windows for 2026 history.

This is a manual local-development backfill. Each requested endpoint uses six
completed provider pentads, retains its native Tigray grid, and loads Tabia
totals through the normal validation path. It does not calculate an anomaly or
assign a drought class.
"""
import argparse
import json
import subprocess
from pathlib import Path


WORK = Path("/work/drought")
ROOT = Path("/data/drought")


def months(value):
    result = []
    for token in value.split(","):
        year, month = map(int, token.strip().split("-"))
        if year != 2026 or not 1 <= month <= 12:
            raise argparse.ArgumentTypeError("months must be 2026-MM values")
        result.append((year, month))
    return result


def run(command):
    completed = subprocess.run(command, cwd=WORK, text=True, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, timeout=3600)
    if completed.returncode:
        message = next((line for line in reversed(completed.stdout.splitlines()) if line.strip()), "unknown local processing error")
        raise RuntimeError(message[:300])
    return completed.stdout


def run_id(output):
    start = output.find("{")
    if start < 0:
        raise RuntimeError("rapid-rain summary did not return a run identifier")
    return json.JSONDecoder().raw_decode(output[start:])[0]["run_id"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--months", type=months, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    plan = [{"month": f"{year}-{month:02d}", "end_pentad": 6} for year, month in args.months]
    if args.dry_run:
        print(json.dumps({"development_only": True, "plan": plan}, indent=2)); return
    completed, failures = [], []
    for year, month in args.months:
        try:
            summary = run(["python3", str(WORK / "chirps_prelim_tabia_summary.py"), "--end-year", str(year),
                           "--end-month", str(month), "--end-pentad", "6"])
            identifier = run_id(summary)
            base = ROOT / "outputs" / identifier
            run(["python3", str(WORK / "validate_artifact.py"), str(base)])
            run(["python3", str(WORK / "load_chirps_prelim_summary.py"), str(base)])
            run(["python3", str(WORK / "catalog_evidence_raster.py"), "rapid", str(base)])
            completed.append({"month": f"{year}-{month:02d}", "run_id": identifier})
        except Exception as exc:
            failures.append({"month": f"{year}-{month:02d}", "error": str(exc)})
    print(json.dumps({"development_only": True, "completed": completed, "failures": failures}, indent=2))
    if failures:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
