"""Build monthly January--August 2026 CHIRPS evidence through the normal path.

Each month is a separate observed-rainfall run: its native Tigray grid,
Tabia summary, baseline comparison, validation, database load, and evidence
catalogue entry stay linked.  The script is development-only and must be run
manually; it creates no schedule or decision product.
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
                               stderr=subprocess.STDOUT, timeout=7200)
    if completed.returncode:
        message = next((line for line in reversed(completed.stdout.splitlines()) if line.strip()), "unknown local processing error")
        raise RuntimeError(message[:300])
    return completed.stdout


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--months", type=months, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    plan = [{"month": f"{year}-{month:02d}", "run_id": f"chirps-v3-{year}-{month}-baseline-1991-2020"}
            for year, month in args.months]
    if args.dry_run:
        print(json.dumps({"development_only": True, "plan": plan}, indent=2))
        return
    completed, failures = [], []
    for year, month in args.months:
        base = ROOT / "outputs" / f"chirps-v3-{year}-{month}-baseline-1991-2020"
        try:
            run(["python3", str(WORK / "chirps_tabia_summary.py"), "--analysis-year", str(year),
                 "--months", str(month), "--baseline-start", "1991", "--baseline-end", "2020",
                 "--data-root", str(ROOT), "--refresh-current-source"])
            run(["python3", str(WORK / "validate_artifact.py"), str(base)])
            run(["python3", str(WORK / "load_chirps_summary.py"), str(base)])
            run(["python3", str(WORK / "catalog_evidence_raster.py"), "chirps", str(base)])
            completed.append({"month": f"{year}-{month:02d}", "run_id": base.name})
        except Exception as exc:
            failures.append({"month": f"{year}-{month:02d}", "error": str(exc)})
    print(json.dumps({"development_only": True, "completed": completed, "failures": failures}, indent=2))
    if failures:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
