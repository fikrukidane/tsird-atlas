#!/usr/bin/env python3
"""Validate a compact, approved TSIRD drought production release directory.

This is intentionally local-only. It neither reads credentials nor connects to
production. A future fixed-purpose publisher may use its result as one of its
pre-transfer gates.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
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
        required = {"drought-evidence-summary", "drought-workspace-latest", "release-status", *AUTO_INDICATOR_RASTERS}
        if not required.issubset(names):
            fail("auto-validated indicator release lacks a required current indicator summary or fixed native raster")
        allowed_history = re.compile(r"^(tabia-geometry|observed-rainfall-runs|observed-rainfall-run-[a-z0-9-]+|evidence-(rapid|ndvi|swi|lst|wapor)-runs|evidence-(rapid|ndvi|swi|lst|wapor)-run-[a-z0-9-]+)$")
        unexpected = names - required
        if any(not allowed_history.fullmatch(name) for name in unexpected):
            fail("auto-validated indicator release contains an unapproved asset")
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
