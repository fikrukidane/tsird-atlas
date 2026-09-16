"""Validate a tabular Drought Intelligence artifact before local ingestion.

This guard intentionally validates structure and disclosure, not scientific
truth.  Scientific review remains a named human gate before an artifact can be
promoted beyond development.
"""
import argparse
import csv
import json
import sys
from pathlib import Path

REQUIRED_MANIFEST = {
    "run_id", "status", "source_product", "source_version", "source_url_template",
    "analysis_year", "months", "baseline_years", "boundary_set_version",
    "included_tabias", "method", "publication_note", "source_latest_month",
    "source_acquisition",
}
REQUIRED_PRELIMINARY_MANIFEST = {
    "run_id", "status", "source_product", "source_version", "native_resolution",
    "period_start", "period_end", "selected_pentads", "boundary_set_version",
    "included_tabias", "method", "publication_note", "source_acquisition",
}
REQUIRED_COLUMNS = {
    "tsird_tabia_id", "rainfall_mm", "baseline_median_mm", "percentile",
    "condition_class", "grid_cell_count", "coverage_pct", "quality_status",
}
VALID_CLASSES = {"exceptionally_dry", "drier_than_typical", "typical_range",
                 "wetter_than_typical", "exceptionally_wet", "unavailable"}


def fail(message):
    print(f"INVALID: {message}", file=sys.stderr)
    raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact_base", help="CSV/manifest base path, without suffix")
    args = parser.parse_args()
    base = Path(args.artifact_base)
    manifest_path = base.with_suffix(".manifest.json")
    csv_path = base.with_suffix(".csv")
    if not manifest_path.is_file() or not csv_path.is_file():
        fail("both .csv and .manifest.json files are required")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    preliminary = manifest.get("source_product", "").startswith("CHIRPS v3 preliminary")
    required_manifest = REQUIRED_PRELIMINARY_MANIFEST if preliminary else REQUIRED_MANIFEST
    missing = required_manifest - set(manifest)
    if missing:
        fail(f"manifest missing: {', '.join(sorted(missing))}")
    if manifest["status"] not in {"development", "validated"}:
        fail("only development or validated artifacts may be loaded locally")
    acquisition = manifest["source_acquisition"]
    receipts = acquisition if preliminary else acquisition.get("current_period_files") if isinstance(acquisition, dict) else None
    if not isinstance(receipts, list) or not receipts:
        fail("manifest has no current-period source acquisition receipt")
    for receipt in receipts:
        if not receipt.get("url") or receipt.get("http_status") != 200:
            fail("current-period source acquisition was not confirmed by the provider")
    with csv_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    required_columns = {"tsird_tabia_id", "rainfall_mm", "grid_cell_count", "coverage_pct", "quality_status"} if preliminary else REQUIRED_COLUMNS
    if not rows or not required_columns.issubset(rows[0]):
        fail("CSV is empty or missing required columns")
    seen = set()
    for number, row in enumerate(rows, start=2):
        tabia_id = row["tsird_tabia_id"]
        if not tabia_id.startswith("tsird-tabia-v1-") or tabia_id in seen:
            fail(f"row {number} has a missing or duplicate canonical Tabia ID")
        seen.add(tabia_id)
        if not preliminary and row["condition_class"] not in VALID_CLASSES:
            fail(f"row {number} has an unknown condition class")
        try:
            coverage = float(row["coverage_pct"])
            cells = int(row["grid_cell_count"])
        except ValueError:
            fail(f"row {number} has non-numeric coverage or cell count")
        if not 0 <= coverage <= 100 or cells < 0:
            fail(f"row {number} has invalid coverage or cell count")
        if row["quality_status"] == "ok" and (not row["rainfall_mm"] or (not preliminary and not row["percentile"])):
            fail(f"row {number} marks incomplete values as quality ok")
    print(json.dumps({"valid": True, "run_id": manifest["run_id"], "rows": len(rows),
                      "status": manifest["status"]}, indent=2))


if __name__ == "__main__":
    main()
