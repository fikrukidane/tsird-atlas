#!/usr/bin/env python3
"""Validate a compact, approved TSIRD drought production release directory.

This is intentionally local-only. It neither reads credentials nor connects to
production. A future fixed-purpose publisher may use its result as one of its
pre-transfer gates.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import Any


SCHEMA_VERSION = "tsird-drought-production-release/v1"
ALLOWED_KINDS = {
    "drought_evidence_summary",
    "priority_replay_summary",
    "fews_net_native_context",
    "public_status",
    "static_documentation",
    "vector_display_summary",
    "native_evidence_raster",
}
SHA256 = re.compile(r"^[a-f0-9]{64}$")
RELEASE_ID = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{6}Z(?:-[a-z0-9][a-z0-9-]*)?$")
PUBLIC_REPLAY_FORBIDDEN_PROPERTIES = {"planning_action", "priority_class", "priority_rank", "triggered_rules"}
AUTO_INDICATOR_CHANNEL = "indicator-evidence"
AUTO_INDICATOR_KINDS = {"drought_evidence_summary", "vector_display_summary", "public_status", "native_evidence_raster"}
AUTO_INDICATOR_RASTERS = {
    "native-raster-chirps": "chirps-current-rainfall.tif",
    "native-raster-rapid": "chirps-rapid-rainfall.tif",
    "native-raster-ndvi": "ndvi-current.tif",
    "native-raster-swi": "swi040-current.tif",
    "native-raster-lst": "lst-current.tif",
    "native-raster-wapor": "wapor-transpiration-current.tif",
}
FRESHNESS_CONTRACT_PATH = Path(__file__).resolve().parents[1] / "n8n" / "publisher" / "drought-indicator-freshness-contract.json"
GZIP_REQUIRED_MIN_BYTES = 64 * 1024
DISPLAY_GEOMETRY_ENGINE = "mapshaper@0.7.83"
DISPLAY_GEOMETRY_INTERVAL_MIN_METERS = 30.0
DISPLAY_GEOMETRY_INTERVAL_MAX_METERS = 75.0
DISPLAY_VERTEX_FLOOR = 4
KNOWN_SOURCE_FLOOR_TABIA_IDS = {
    "tsird-tabia-v1-eaac4242a1fc0b5b3399463efb3e4ccd",
    "tsird-tabia-v1-490fc743c6304faac0849b61ae167eb5",
}
JSON_ASSET_SUFFIXES = {".json", ".geojson", ".topojson"}


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise ValueError(message)


def require_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        fail(f"{field} must be a non-empty string")
    return value


def require_timestamp(value: Any, field: str) -> str:
    text = require_string(value, field)
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        fail(f"{field} must be an ISO-8601 timestamp")
    return text


def require_date(value: Any, field: str) -> str:
    text = require_string(value, field)
    try:
        datetime.strptime(text, "%Y-%m-%d")
    except ValueError:
        fail(f"{field} must be a YYYY-MM-DD date")
    return text


def load_indicator_freshness_contract() -> dict[str, dict[str, Any]]:
    try:
        contract = json.loads(FRESHNESS_CONTRACT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        fail(f"indicator freshness contract is unreadable: {error}")
    sources = contract.get("sources") if isinstance(contract, dict) else None
    if contract.get("schema_version") != "tsird-drought-indicator-freshness-contract/v1" or not isinstance(sources, list):
        fail("indicator freshness contract is invalid")
    result: dict[str, dict[str, Any]] = {}
    for source in sources:
        if not isinstance(source, dict) or not isinstance(source.get("key"), str):
            fail("indicator freshness contract has an invalid source")
        result[source["key"]] = source
    return result


def validate_indicator_freshness(manifest: dict[str, Any]) -> None:
    """Require a complete, contract-derived freshness declaration.

    Freshness is release metadata rather than UI-only text. This keeps a stale
    public indicator visible as last-known-good evidence while making its age
    testable by the validator and by external monitoring.
    """
    expected = load_indicator_freshness_contract()
    freshness = manifest.get("freshness")
    if not isinstance(freshness, list) or len(freshness) != len(expected):
        fail("auto-validated indicator release must contain complete freshness metadata")
    actual: dict[str, dict[str, Any]] = {}
    for index, record in enumerate(freshness):
        if not isinstance(record, dict):
            fail(f"freshness[{index}] must be an object")
        key = require_string(record.get("source_key"), f"freshness[{index}].source_key")
        if key in actual or key not in expected:
            fail(f"freshness[{index}] has an unexpected or duplicate source_key")
        actual[key] = record
    if set(actual) != set(expected):
        fail("auto-validated indicator release freshness sources do not match the contract")
    for key, source in expected.items():
        record = actual[key]
        if record.get("label") != source.get("label"):
            fail(f"freshness[{key}] label does not match the contract")
        if record.get("automation_state") != source.get("automation_state"):
            fail(f"freshness[{key}] automation state does not match the contract")
        ended = datetime.strptime(require_date(record.get("source_observation_end"), f"freshness[{key}].source_observation_end"), "%Y-%m-%d").date()
        expected_next = datetime.strptime(require_date(record.get("expected_next"), f"freshness[{key}].expected_next"), "%Y-%m-%d").date()
        stale_after = datetime.strptime(require_date(record.get("stale_after"), f"freshness[{key}].stale_after"), "%Y-%m-%d").date()
        if expected_next != ended + timedelta(days=int(source["expected_after_days"])):
            fail(f"freshness[{key}] expected_next does not match the contract")
        if stale_after != ended + timedelta(days=int(source["stale_after_days"])):
            fail(f"freshness[{key}] stale_after does not match the contract")


def _ring_vertex_count(ring: Any) -> int:
    if not isinstance(ring, list) or not ring:
        fail("tabia-geometry contains an invalid polygon ring")
    count = len(ring)
    if count > 1 and ring[0] == ring[-1]:
        count -= 1
    if count < 3:
        fail("tabia-geometry contains a degenerate polygon ring")
    return count


def _feature_vertex_count(feature: Any) -> int:
    geometry = feature.get("geometry") if isinstance(feature, dict) else None
    if not isinstance(geometry, dict):
        fail("tabia-geometry contains an invalid feature")
    coordinates = geometry.get("coordinates")
    if geometry.get("type") == "Polygon" and isinstance(coordinates, list):
        rings = coordinates
    elif geometry.get("type") == "MultiPolygon" and isinstance(coordinates, list):
        rings = [ring for polygon in coordinates if isinstance(polygon, list) for ring in polygon]
    else:
        fail("tabia-geometry contains a non-polygon feature")
    return sum(_ring_vertex_count(ring) for ring in rings)


def _display_vertex_statistics(geometry: dict[str, Any]) -> dict[str, int | float]:
    features = geometry.get("features")
    if not isinstance(features, list) or not features:
        fail("tabia-geometry has no features for vertex statistics")
    values = sorted(_feature_vertex_count(feature) for feature in features)
    midpoint = len(values) // 2
    median: int | float = values[midpoint] if len(values) % 2 else (values[midpoint - 1] + values[midpoint]) / 2
    return {
        "feature_count": len(values),
        "minimum_vertices": values[0],
        "median_vertices": median,
        "maximum_vertices": values[-1],
        "floor_vertices": DISPLAY_VERTEX_FLOOR,
        "floor_feature_count": sum(value <= DISPLAY_VERTEX_FLOOR for value in values),
    }


def _floor_tabia_ids(geometry: dict[str, Any]) -> set[str]:
    features = geometry.get("features")
    if not isinstance(features, list):
        fail("tabia-geometry has no features")
    result: set[str] = set()
    for feature in features:
        properties = feature.get("properties") if isinstance(feature, dict) else None
        tabia_id = properties.get("tsird_tabia_id") if isinstance(properties, dict) else None
        if not isinstance(tabia_id, str):
            fail("tabia-geometry feature lacks tsird_tabia_id")
        if _feature_vertex_count(feature) <= DISPLAY_VERTEX_FLOOR:
            result.add(tabia_id)
    return result


def validate_display_geometry(release_dir: Path, manifest: dict[str, Any], assets: list[Any]) -> None:
    """Keep release-only display geometry compact without changing analysis data."""
    geometry_asset = next((asset for asset in assets if isinstance(asset, dict) and asset.get("asset_id") == "tabia-geometry"), None)
    if geometry_asset is None:
        fail("auto-validated indicator release lacks tabia-geometry")
    relative_path = safe_relative_path(geometry_asset.get("relative_path"), "tabia-geometry.relative_path")
    try:
        geometry = json.loads((release_dir / relative_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        fail(f"tabia-geometry is not readable JSON: {error}")
    if not isinstance(geometry, dict) or geometry.get("type") != "FeatureCollection" or not isinstance(geometry.get("features"), list):
        fail("tabia-geometry must be a GeoJSON FeatureCollection")
    if geometry.get("display_coordinate_precision") != 5:
        fail("tabia-geometry must use five-decimal display coordinates")
    simplification = geometry.get("display_simplification")
    if not isinstance(simplification, dict) or simplification.get("engine") != DISPLAY_GEOMETRY_ENGINE:
        fail("tabia-geometry must declare the required topology-preserving display simplifier")
    if simplification.get("method") != "interval":
        fail("tabia-geometry must declare metre-interval display simplification")
    interval_meters = simplification.get("interval_meters")
    if not isinstance(interval_meters, (int, float)) or isinstance(interval_meters, bool) or not (
        DISPLAY_GEOMETRY_INTERVAL_MIN_METERS <= interval_meters <= DISPLAY_GEOMETRY_INTERVAL_MAX_METERS
    ):
        fail("tabia-geometry must declare a 30-75 metre display simplification interval")
    if "keep-shapes" not in str(simplification.get("topology", "")):
        fail("tabia-geometry must declare shared-boundary topology preservation")
    statistics = _display_vertex_statistics(geometry)
    floor_ids = _floor_tabia_ids(geometry)
    if not floor_ids.issubset(KNOWN_SOURCE_FLOOR_TABIA_IDS):
        fail("tabia-geometry has an unrecognised low-vertex display feature")
    declared_statistics = geometry.get("display_vertex_statistics")
    expected_statistics = {
        **statistics,
        "preexisting_floor_feature_count": len(floor_ids),
        "preexisting_floor_tabia_ids": sorted(floor_ids),
        "introduced_floor_feature_count": 0,
    }
    if declared_statistics != expected_statistics:
        fail("tabia-geometry display_vertex_statistics does not match the geometry")
    manifest_geometry = manifest.get("display_geometry")
    if not isinstance(manifest_geometry, dict):
        fail("auto-validated indicator release lacks display_geometry provenance")
    if manifest_geometry.get("asset_id") != "tabia-geometry-display" or manifest_geometry.get("format") != "topojson":
        fail("manifest display_geometry must name the TopoJSON display asset")
    display_asset = next((asset for asset in assets if isinstance(asset, dict) and asset.get("asset_id") == "tabia-geometry-display"), None)
    if display_asset is None:
        fail("auto-validated indicator release lacks tabia-geometry-display")
    display_path = safe_relative_path(display_asset.get("relative_path"), "tabia-geometry-display.relative_path")
    try:
        topology = json.loads((release_dir / display_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        fail(f"tabia-geometry-display is not readable JSON: {error}")
    if not isinstance(topology, dict) or topology.get("type") != "Topology" or not isinstance(topology.get("objects"), dict):
        fail("tabia-geometry-display must be a TopoJSON topology")
    if topology.get("display_simplification") != simplification or topology.get("display_vertex_statistics") != expected_statistics:
        fail("tabia-geometry-display provenance does not match tabia-geometry")
    if manifest_geometry.get("simplification") != simplification:
        fail("manifest display_geometry simplification does not match tabia-geometry")
    if manifest_geometry.get("vertex_statistics") != expected_statistics:
        fail("manifest display_geometry vertex statistics do not match tabia-geometry")


def safe_relative_path(value: Any, field: str) -> PurePosixPath:
    text = require_string(value, field)
    path = PurePosixPath(text)
    if path.is_absolute() or ".." in path.parts or "\\" in text or path.name != text:
        fail(f"{field} must name one safe file in the release directory")
    return path


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_public_replay_payload(path: Path) -> None:
    """Reject internal priority/action fields from a public replay asset."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        fail(f"public replay asset is not readable JSON: {error}")
    if not isinstance(payload, dict):
        fail("public replay asset root must be an object")
    features = payload.get("features")
    if isinstance(features, list):
        for index, feature in enumerate(features):
            properties = feature.get("properties") if isinstance(feature, dict) else None
            if not isinstance(properties, dict):
                fail(f"public replay feature {index} has no properties object")
            forbidden = PUBLIC_REPLAY_FORBIDDEN_PROPERTIES.intersection(properties)
            if forbidden:
                fail(f"public replay feature {index} exposes internal field(s): {', '.join(sorted(forbidden))}")
            if "retrospective_draft_code" not in properties:
                fail(f"public replay feature {index} lacks a neutral retrospective_draft_code")
    text = json.dumps(payload, ensure_ascii=False).lower()
    if "immediate verification" in text or "coordinated response planning" in text:
        fail("public replay asset contains operational planning wording")


def validate_asset(release_dir: Path, asset: Any, index: int, names: set[str]) -> None:
    if not isinstance(asset, dict):
        fail(f"assets[{index}] must be an object")

    asset_id = require_string(asset.get("asset_id"), f"assets[{index}].asset_id")
    if asset_id in names:
        fail(f"duplicate asset_id: {asset_id}")
    names.add(asset_id)

    kind = require_string(asset.get("kind"), f"assets[{index}].kind")
    if kind not in ALLOWED_KINDS:
        fail(f"assets[{index}].kind is not allowed: {kind}")

    relative_path = safe_relative_path(asset.get("relative_path"), f"assets[{index}].relative_path")
    file_path = release_dir / relative_path
    if not file_path.is_file():
        fail(f"assets[{index}] referenced file is missing: {relative_path}")
    gzip_path = file_path.with_name(f"{file_path.name}.gz")
    if file_path.suffix.lower() in JSON_ASSET_SUFFIXES and file_path.stat().st_size >= GZIP_REQUIRED_MIN_BYTES and not gzip_path.exists():
        fail(f"assets[{index}] large JSON asset is missing its required compressed sidecar")
    if gzip_path.exists():
        if file_path.suffix.lower() not in JSON_ASSET_SUFFIXES or gzip_path.is_symlink() or not gzip_path.is_file():
            fail(f"assets[{index}] has an invalid compressed JSON sidecar")
        try:
            if gzip.decompress(gzip_path.read_bytes()) != file_path.read_bytes():
                fail(f"assets[{index}] compressed JSON sidecar does not match the asset")
        except OSError as error:
            fail(f"assets[{index}] compressed JSON sidecar is unreadable: {error}")
    if kind == "native_evidence_raster":
        if AUTO_INDICATOR_RASTERS.get(asset_id) != str(relative_path):
            fail("native evidence raster is not one of the fixed display-ready indicator files")
        if file_path.is_symlink() or file_path.suffix.lower() not in {".tif", ".tiff"}:
            fail("native evidence raster must be a regular TIFF file")

    size = asset.get("byte_size")
    if not isinstance(size, int) or size < 0:
        fail(f"assets[{index}].byte_size must be a non-negative integer")
    actual_size = file_path.stat().st_size
    if actual_size != size:
        fail(f"assets[{index}] byte size mismatch for {relative_path}: manifest={size}, actual={actual_size}")

    checksum = require_string(asset.get("sha256"), f"assets[{index}].sha256")
    if not SHA256.fullmatch(checksum):
        fail(f"assets[{index}].sha256 must be a lowercase SHA-256 hash")
    actual_checksum = file_digest(file_path)
    if actual_checksum != checksum:
        fail(f"assets[{index}] checksum mismatch for {relative_path}")

    require_string(asset.get("source"), f"assets[{index}].source")
    start = require_date(asset.get("source_observation_start"), f"assets[{index}].source_observation_start")
    end = require_date(asset.get("source_observation_end"), f"assets[{index}].source_observation_end")
    if end < start:
        fail(f"assets[{index}] source observation end precedes start")
    require_timestamp(asset.get("retrieved_at"), f"assets[{index}].retrieved_at")
    require_string(asset.get("processing_version"), f"assets[{index}].processing_version")
    if asset.get("quality_state") != "validated":
        fail(f"assets[{index}].quality_state must be validated for publication")
    boundary = require_string(asset.get("interpretation_boundary"), f"assets[{index}].interpretation_boundary")
    if kind == "fews_net_native_context" and "Tabia" not in boundary:
        fail("FEWS NET interpretation boundary must explicitly retain the Tabia non-transfer rule")
    if kind == "priority_replay_summary" and "forecast" not in boundary.lower():
        fail("Priority replay interpretation boundary must explicitly state its forecast limitation")
    if kind == "priority_replay_summary":
        validate_public_replay_payload(file_path)


def validate_release(
    release_dir: Path,
    allow_validated: bool,
    allow_auto_validated_indicators: bool = False,
) -> dict[str, Any]:
    manifest_path = release_dir / "manifest.json"
    if not manifest_path.is_file():
        fail(f"missing manifest: {manifest_path}")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        fail(f"manifest is not valid JSON: {error}")
    if not isinstance(manifest, dict):
        fail("manifest root must be an object")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        fail(f"unsupported schema_version: {manifest.get('schema_version')!r}")

    release_id = require_string(manifest.get("release_id"), "release_id")
    if not RELEASE_ID.fullmatch(release_id):
        fail("release_id must be UTC compact timestamp, optionally followed by a lowercase suffix")
    if release_dir.name != release_id:
        fail("release directory name must equal manifest release_id")

    state = manifest.get("release_state")
    if state not in {"validated", "approved", "auto-validated", "rejected"}:
        fail("release_state must be validated, approved, auto-validated or rejected")
    if state == "rejected":
        fail("rejected release cannot be staged or published")
    if state == "validated" and not allow_validated:
        fail("validated release is not approved for staging or publishing")
    channel = manifest.get("release_channel", "reviewed-release")
    if channel not in {"reviewed-release", AUTO_INDICATOR_CHANNEL}:
        fail("release_channel must be reviewed-release or indicator-evidence")
    if state == "auto-validated":
        if channel != AUTO_INDICATOR_CHANNEL:
            fail("auto-validated releases are permitted only for indicator-evidence")
        if not allow_auto_validated_indicators:
            fail("auto-validated indicator release requires the dedicated indicator publisher")
    elif channel == AUTO_INDICATOR_CHANNEL:
        fail("indicator-evidence releases must use auto-validated state")
    require_string(manifest.get("prepared_by"), "prepared_by")
    require_timestamp(manifest.get("prepared_at"), "prepared_at")
    if state == "approved":
        require_string(manifest.get("approved_by"), "approved_by")
        require_timestamp(manifest.get("approved_at"), "approved_at")
    previous = manifest.get("previous_release_id")
    if previous is not None and (not isinstance(previous, str) or not RELEASE_ID.fullmatch(previous)):
        fail("previous_release_id must be null or a valid release ID")
    require_string(manifest.get("public_scope"), "public_scope")

    assets = manifest.get("assets")
    if not isinstance(assets, list) or not assets:
        fail("assets must be a non-empty list")
    names: set[str] = set()
    for index, asset in enumerate(assets):
        validate_asset(release_dir, asset, index, names)
        if state == "auto-validated" and asset.get("kind") not in AUTO_INDICATOR_KINDS:
            fail("auto-validated indicator release contains a non-indicator asset")
    if state == "auto-validated":
        required = {"drought-evidence-summary", "drought-workspace-latest", "release-status", "exposure-population", "exposure-cropland", "exposure-road", *AUTO_INDICATOR_RASTERS}
        if not required.issubset(names):
            fail("auto-validated indicator release lacks a required current indicator summary or fixed native raster")
        allowed_history = re.compile(r"^(tabia-geometry|tabia-geometry-display|observed-rainfall-runs|observed-rainfall-run-[a-z0-9-]+|evidence-(rapid|ndvi|swi|lst|wapor)-runs|evidence-(rapid|ndvi|swi|lst|wapor)-run-[a-z0-9-]+)$")
        unexpected = names - required
        if any(not allowed_history.fullmatch(name) for name in unexpected):
            fail("auto-validated indicator release contains an unapproved asset")
        validate_indicator_freshness(manifest)
        validate_display_geometry(release_dir, manifest, assets)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("release_directory", type=Path)
    parser.add_argument(
        "--allow-validated",
        action="store_true",
        help="permit a validated (but not approved) manifest for a local staging check only",
    )
    parser.add_argument(
        "--allow-auto-validated-indicators",
        action="store_true",
        help="permit an auto-validated indicator-evidence package for the dedicated publisher only",
    )
    args = parser.parse_args()
    try:
        manifest = validate_release(
            args.release_directory.resolve(),
            args.allow_validated,
            args.allow_auto_validated_indicators,
        )
    except ValueError:
        return 1
    print(
        f"OK: {manifest['release_id']} ({manifest['release_state']}), "
        f"{len(manifest['assets'])} validated assets"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
