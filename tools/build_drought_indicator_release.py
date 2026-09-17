#!/usr/bin/env python3
"""Build an automatically publishable TSIRD indicator-evidence release.

This builder is for observed/source-derived indicator summaries only.  It
never includes a priority replay, model configuration, FEWS NET geometry, raw
raster, source archive, or a development URL.  The resulting package is
``auto-validated`` only when every included source has usable Tabia evidence;
it is designed for the separate indicator pointer, not the reviewed release
pointer used by Priority Review.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from build_drought_production_release import (
    API_PATHS,
    WORKSPACE_PATHS,
    asset_record,
    public_rainfall_index,
    public_workspace_summary,
    request_json,
    write_json,
)


RELEASE_ID = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{6}Z-indicators$")
REQUIRED_INDICATORS = tuple(WORKSPACE_PATHS)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def compact_release_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ-indicators")


def observation_window(run: dict[str, Any]) -> tuple[str, str]:
    start = run.get("observation_start") or run.get("source_period_start") or run.get("period_start") or run.get("source_latest_month")
    end = run.get("observation_end") or run.get("source_period_end") or run.get("period_end") or run.get("source_latest_month")
    if not isinstance(start, str) or not isinstance(end, str):
        raise RuntimeError("indicator run lacks a source-observation window")
    return start[:10], end[:10]


def validate_workspace_inputs(payloads: dict[str, dict[str, Any]]) -> None:
    """Require a complete, usable six-stream Tabia workspace before publish.

    ``development`` identifies the local environment, not a quality grade. The
    per-Tabia quality flag and coverage therefore decide publishability here.
    A failed, unavailable, empty, or wholly invalid source holds the existing
    production indicator pointer in place.  ``degraded`` is retained as visible
    freshness context, rather than silently withholding the last technically
    sound Tabia evidence.
    """
    for indicator in REQUIRED_INDICATORS:
        payload = payloads[indicator]
        rows = payload.get("conditions") if indicator == "observed" else payload.get("summaries")
        run = payload.get("run")
        if not isinstance(run, dict) or not isinstance(rows, list) or not rows:
            raise RuntimeError(f"{indicator} has no complete retained Tabia evidence")
        if str(run.get("status", "")).lower() in {"failed", "unavailable"}:
            raise RuntimeError(f"{indicator} source state is not publishable: {run.get('status')}")
        usable = [
            row for row in rows
            if isinstance(row, dict)
            and str(row.get("quality_status", "")).lower() in {"ok", "validated"}
            and (row.get("coverage_pct") is None or float(row["coverage_pct"]) >= 90)
        ]
        if not usable:
            raise RuntimeError(f"{indicator} contains no quality-approved Tabia summaries")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-base", default="http://127.0.0.1:18080", help="development API origin")
    parser.add_argument("--output-root", type=Path, required=True, help="ignored local indicator-release root")
    parser.add_argument("--prepared-by", default="TSIRD automated indicator validation", help="release preparer identity")
    parser.add_argument("--release-id", default=None, help="optional UTC indicator release ID")
    args = parser.parse_args()

    release_id = args.release_id or compact_release_id()
    if not RELEASE_ID.fullmatch(release_id):
        print("ERROR: release ID must be a compact UTC timestamp ending in -indicators", file=sys.stderr)
        return 2
    release_dir = args.output_root / release_id
    if release_dir.exists():
        print(f"ERROR: release directory already exists: {release_dir}", file=sys.stderr)
        return 2

    try:
        workspace_payloads = {name: request_json(args.api_base, path) for name, path in WORKSPACE_PATHS.items()}
        validate_workspace_inputs(workspace_payloads)
        rainfall_payload = request_json(args.api_base, API_PATHS["drought-evidence-summary.json"])
    except RuntimeError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    rainfall_runs = rainfall_payload.get("runs")
    if not isinstance(rainfall_runs, list) or not rainfall_runs or not isinstance(rainfall_runs[0], dict):
        print("ERROR: final rainfall evidence index is incomplete", file=sys.stderr)
        return 2

    workspace = public_workspace_summary(workspace_payloads)
    rainfall = public_rainfall_index(rainfall_payload)
    latest_run = workspace_payloads["observed"].get("run")
    if not isinstance(latest_run, dict):
        print("ERROR: observed indicator run is incomplete", file=sys.stderr)
        return 2
    try:
        start, end = observation_window(latest_run)
    except RuntimeError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    boundary = (
        "Automatically published retained indicator evidence only. Each source is shown separately; "
        "it is not a combined drought class, food-security classification, forecast, allocation recommendation, or operational decision."
    )

    release_dir.mkdir(parents=True)
    written = {
        "drought-evidence-summary.json": write_json(release_dir / "drought-evidence-summary.json", rainfall),
        "drought-workspace-latest.json": write_json(release_dir / "drought-workspace-latest.json", workspace),
    }
    status = {
        "schema_version": "tsird-drought-automatic-indicator-release-status/v1",
        "environment": "development-to-production",
        "release_id": release_id,
        "release_state": "auto-validated",
        "release_channel": "indicator-evidence",
        "generated_at": utc_now(),
        "note": "Published automatically only after complete source-specific Tabia quality and coverage checks. The existing public indicator release remains current when checks fail.",
    }
    written["status.json"] = write_json(release_dir / "status.json", status)
    assets = [
        asset_record("drought-evidence-summary", "drought_evidence_summary", "drought-evidence-summary.json", written["drought-evidence-summary.json"], "TSIRD retained CHIRPS rainfall evidence index", start, end, rainfall.get("schema_version", "unknown"), boundary),
        asset_record("drought-workspace-latest", "vector_display_summary", "drought-workspace-latest.json", written["drought-workspace-latest.json"], "TSIRD retained Tabia indicator summaries", start, end, workspace.get("schema_version", "unknown"), boundary),
        asset_record("release-status", "public_status", "status.json", written["status.json"], "TSIRD automated indicator validator", start, end, status["schema_version"], "Publication provenance only; it is not a scientific certification or operational decision."),
    ]
    manifest = {
        "schema_version": "tsird-drought-production-release/v1",
        "release_id": release_id,
        "release_state": "auto-validated",
        "release_channel": "indicator-evidence",
        "prepared_by": args.prepared_by,
        "prepared_at": utc_now(),
        "previous_release_id": None,
        "public_scope": boundary,
        "assets": assets,
    }
    write_json(release_dir / "manifest.json", manifest)
    print(json.dumps({"release_directory": str(release_dir), "release_id": release_id, "assets": len(assets)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
