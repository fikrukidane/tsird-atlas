#!/usr/bin/env python3
"""Build one local-only compact TSIRD drought evidence release from read-only API outputs.

The script never downloads source rasters, contacts a production system, or
changes database state. It writes an unapproved `validated` release that must
pass the companion validator and receive a separate human approval before any
future publisher can stage it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


API_PATHS = {
    "drought-evidence-summary.json": "/map/api/drought/development/evidence/rainfall/runs",
    "priority-replay-summary.json": "/map/api/drought/development/priority/historical-replays",
    "fews-net-context.json": "/map/api/drought/development/fews-net-context/runs",
}
REPLAY_PATH = "/map/api/drought/development/priority/historical-replays/{snapshot_id}/features"
FEWS_PATH = "/map/api/drought/development/fews-net-context/runs/{run_id}/features"
RELEASE_ID = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{6}Z(?:-[a-z0-9][a-z0-9-]*)?$")
REPLAY_CODE_BY_CLASS = {"critical": "C1", "high": "C2", "moderate": "C3", "watch": "C4"}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def compact_release_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")


def request_json(api_base: str, path: str) -> dict[str, Any]:
    url = f"{api_base.rstrip('/')}{path}"
    try:
        with urlopen(url, timeout=30) as response:  # noqa: S310 -- fixed local API base is an explicit input
            if response.status != 200:
                raise RuntimeError(f"{url} returned HTTP {response.status}")
            data = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
        raise RuntimeError(f"could not read required development API payload {path}: {error}") from error
    if not isinstance(data, dict):
        raise RuntimeError(f"development API payload {path} is not a JSON object")
    return data


def write_json(path: Path, data: dict[str, Any]) -> tuple[int, str]:
    encoded = (json.dumps(data, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n").encode("utf-8")
    path.write_bytes(encoded)
    return len(encoded), hashlib.sha256(encoded).hexdigest()


def observation_window(run: dict[str, Any], fallback: str) -> tuple[str, str]:
    start = run.get("observation_start") or run.get("source_latest_month") or run.get("issued_at") or fallback
    end = run.get("observation_end") or run.get("source_latest_month") or run.get("issued_at") or fallback
    return str(start)[:10], str(end)[:10]


def public_replay_geometry(payload: dict[str, Any]) -> dict[str, Any]:
    """Remove internal decision/action wording from a public replay geometry.

    The public release can retain observations and a neutral retrospective draft
    code, but must never ship a planning action, a priority label/rank, or
    rule text that could be read as an instruction.
    """
    features = payload.get("features")
    if payload.get("type") != "FeatureCollection" or not isinstance(features, list):
        raise RuntimeError("priority replay feature payload is not a FeatureCollection")
    allowed = {
        "tsird_tabia_id", "tabia_name_en", "woreda_name_en", "rainfall_mm",
        "baseline_median_mm", "rainfall_percentile", "population_decile",
        "cropland_decile", "accessibility_context", "evidence_state", "input_quality",
    }
    public_features = []
    for feature in features:
        if not isinstance(feature, dict) or not isinstance(feature.get("properties"), dict):
            raise RuntimeError("priority replay feature is malformed")
        properties = feature["properties"]
        public_properties = {key: properties[key] for key in allowed if key in properties}
        draft_class = properties.get("priority_class")
        public_properties["retrospective_draft_code"] = REPLAY_CODE_BY_CLASS.get(
            draft_class, "insufficient-evidence"
        )
        public_properties["interpretation_note"] = (
            "Retrospective retained evidence only; no operational recommendation."
        )
        public_features.append({
            "type": "Feature",
            "geometry": feature.get("geometry"),
            "properties": public_properties,
        })
    return {
        "type": "FeatureCollection",
        "schema_version": "tsird-public-retrospective-evidence-replay/v1",
        "source_snapshot_kind": payload.get("snapshot_kind"),
        "interpretation_boundary": (
            "Retrospective evidence replay only; not a forecast, official classification, "
            "allocation recommendation, or operational decision."
        ),
        "features": public_features,
    }


def public_replay_summary(payload: dict[str, Any]) -> dict[str, Any]:
    """Publish historical counts under neutral draft codes only."""
    replays = payload.get("replays")
    if not isinstance(replays, list):
        raise RuntimeError("priority replay index has no replay list")
    public_replays = []
    for replay in replays:
        if not isinstance(replay, dict):
            raise RuntimeError("priority replay index contains an invalid replay")
        public_replays.append({
            key: replay.get(key)
            for key in ("snapshot_id", "configuration_id", "configuration_version", "source_latest_month", "tabias")
        } | {
            "C1": replay.get("critical", 0),
            "C2": replay.get("high", 0),
            "C3": replay.get("moderate", 0),
            "C4": replay.get("watch", 0),
            "insufficient_evidence": replay.get("insufficient_evidence", 0),
        })
    return {
        "schema_version": "tsird-public-retrospective-evidence-replay-index/v1",
        "interpretation_boundary": (
            "Retrospective evidence replay only; C1-C4 are neutral stored draft codes, "
            "not priority decisions, forecasts, or operational recommendations."
        ),
        "replays": public_replays,
    }


def public_rainfall_index(payload: dict[str, Any]) -> dict[str, Any]:
    """Retain compact source metadata without a development raster URL."""
    runs = payload.get("runs")
    if not isinstance(runs, list):
        raise RuntimeError("rainfall evidence index has no run list")
    public_runs = []
    for run in runs:
        if not isinstance(run, dict):
            raise RuntimeError("rainfall evidence index contains an invalid run")
        provenance = run.get("provenance") if isinstance(run.get("provenance"), dict) else {}
        public_runs.append({
            key: run.get(key)
            for key in ("run_id", "evidence_kind", "native_resolution", "observation_start", "observation_end", "quality_summary")
        } | {
            "source_product": provenance.get("source_product"),
            "method": provenance.get("method"),
            "interpretation_boundary": "Retained rainfall evidence only; it does not create a drought class or combined score.",
        })
    return {"schema_version": "tsird-public-rainfall-evidence-index/v1", "runs": public_runs}


def asset_record(
    asset_id: str,
    kind: str,
    filename: str,
    file_info: tuple[int, str],
    source: str,
    start: str,
    end: str,
    processing_version: str,
    boundary: str,
) -> dict[str, Any]:
    size, checksum = file_info
    return {
        "asset_id": asset_id,
        "kind": kind,
        "relative_path": filename,
        "byte_size": size,
        "sha256": checksum,
        "source": source,
        "source_observation_start": start,
        "source_observation_end": end,
        "retrieved_at": utc_now(),
        "processing_version": processing_version,
        "quality_state": "validated",
        "interpretation_boundary": boundary,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-base", default="http://127.0.0.1:18080", help="development API origin")
    parser.add_argument("--output-root", type=Path, required=True, help="ignored local release root")
    parser.add_argument("--prepared-by", required=True, help="local preparer identity recorded in the manifest")
    parser.add_argument("--release-id", default=None, help="optional UTC release ID; defaults to current UTC time")
    args = parser.parse_args()

    release_id = args.release_id or compact_release_id()
    if not RELEASE_ID.fullmatch(release_id):
        print("ERROR: release ID must be compact UTC timestamp, optionally followed by lowercase suffix", file=sys.stderr)
        return 2
    release_dir = args.output_root / release_id
    if release_dir.exists():
        print(f"ERROR: release directory already exists: {release_dir}", file=sys.stderr)
        return 2

    payloads = {filename: request_json(args.api_base, path) for filename, path in API_PATHS.items()}
    replays = payloads["priority-replay-summary.json"].get("replays")
    fews_runs = payloads["fews-net-context.json"].get("runs")
    rainfall_runs = payloads["drought-evidence-summary.json"].get("runs")
    if not isinstance(replays, list) or not replays:
        print("ERROR: priority replay index has no retained replay", file=sys.stderr)
        return 2
    if not isinstance(fews_runs, list) or not fews_runs:
        print("ERROR: FEWS NET context index has no retained issue", file=sys.stderr)
        return 2
    if not isinstance(rainfall_runs, list) or not rainfall_runs:
        print("ERROR: rainfall evidence index has no retained run", file=sys.stderr)
        return 2

    latest_replay = replays[0]
    latest_fews = fews_runs[0]
    replay_id = latest_replay.get("snapshot_id")
    fews_id = latest_fews.get("run_id")
    if not isinstance(replay_id, str) or not isinstance(fews_id, str):
        print("ERROR: retained replay or FEWS NET issue is missing its ID", file=sys.stderr)
        return 2
    payloads["priority-replay-latest.geojson"] = request_json(args.api_base, REPLAY_PATH.format(snapshot_id=replay_id))
    payloads["fews-net-context-latest.geojson"] = request_json(args.api_base, FEWS_PATH.format(run_id=fews_id))

    # Build a public-facing shape before writing any release file. The compact
    # release must not contain development API links, source-raster pointers,
    # operational planning actions, priority labels/ranks, or trigger text.
    payloads["drought-evidence-summary.json"] = public_rainfall_index(
        payloads["drought-evidence-summary.json"]
    )
    payloads["priority-replay-summary.json"] = public_replay_summary(
        payloads["priority-replay-summary.json"]
    )
    payloads["priority-replay-latest.geojson"] = public_replay_geometry(
        payloads["priority-replay-latest.geojson"]
    )

    release_dir.mkdir(parents=True)
    written = {filename: write_json(release_dir / filename, payload) for filename, payload in payloads.items()}

    rainfall_start, rainfall_end = observation_window(rainfall_runs[0], "1970-01-01")
    replay_start, replay_end = observation_window(latest_replay, "1970-01-01")
    fews_start, fews_end = observation_window(latest_fews, "1970-01-01")
    common_boundary = "Experimental retained evidence only; not an official forecast, food-security classification, allocation recommendation, or operational decision product."
    assets = [
        asset_record("drought-evidence-summary", "drought_evidence_summary", "drought-evidence-summary.json", written["drought-evidence-summary.json"], "TSIRD retained CHIRPS rainfall evidence index", rainfall_start, rainfall_end, payloads["drought-evidence-summary.json"].get("schema_version", "unknown"), f"{common_boundary} It does not create a drought class or combined score."),
        asset_record("priority-replay-summary", "priority_replay_summary", "priority-replay-summary.json", written["priority-replay-summary.json"], "TSIRD retained historical replay index", replay_start, replay_end, payloads["priority-replay-summary.json"].get("schema_version", "unknown"), "Historical replay from retained evidence; not an as-issued forecast, official classification, allocation recommendation, or operational decision."),
        asset_record("priority-replay-latest", "priority_replay_summary", "priority-replay-latest.geojson", written["priority-replay-latest.geojson"], "TSIRD retained historical replay GeoJSON", replay_start, replay_end, payloads["priority-replay-latest.geojson"].get("schema_version", "unknown"), "Historical replay geometry and stored draft evidence trace; not an as-issued forecast, official classification, allocation recommendation, or operational decision."),
        asset_record("fews-net-context-index", "fews_net_native_context", "fews-net-context.json", written["fews-net-context.json"], "FEWS NET retained Ethiopia provider issue index", fews_start, fews_end, payloads["fews-net-context.json"].get("schema_version", "unknown"), "Provider-native external context only; no provider classification is transferred to a Tabia and it does not affect TSIRD scoring."),
        asset_record("fews-net-context-latest", "fews_net_native_context", "fews-net-context-latest.geojson", written["fews-net-context-latest.geojson"], "FEWS NET retained Ethiopia provider-native FSC geometry", fews_start, fews_end, payloads["fews-net-context-latest.geojson"].get("schema_version", "unknown"), "Provider-native external context only; no provider classification is transferred to a Tabia and it does not affect TSIRD scoring."),
    ]
    status = {
        "schema_version": "tsird-drought-production-release-status/v1",
        "environment": "local-staging",
        "release_id": release_id,
        "state": "validated",
        "generated_at": utc_now(),
        "note": "Local staging release only. It is not uploaded, served or approved for promotion.",
        "latest_replay_snapshot_id": replay_id,
        "latest_fews_net_run_id": fews_id,
    }
    written["status.json"] = write_json(release_dir / "status.json", status)
    assets.append(asset_record("release-status", "public_status", "status.json", written["status.json"], "TSIRD local release builder", replay_start, replay_end, status["schema_version"], "Release provenance/status only; it is not a data-quality certification or operational decision."))
    manifest = {
        "schema_version": "tsird-drought-production-release/v1",
        "release_id": release_id,
        "release_state": "validated",
        "prepared_by": args.prepared_by,
        "prepared_at": utc_now(),
        "previous_release_id": None,
        "public_scope": common_boundary,
        "assets": assets,
    }
    write_json(release_dir / "manifest.json", manifest)
    print(json.dumps({"release_directory": str(release_dir), "release_id": release_id, "assets": len(assets)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
