#!/usr/bin/env python3
"""Atomically activate an already-approved local release on the VPS.

This is a VPS-side utility intended to be called only by a forced-command SSH
activation account. It accepts one validated release ID, copies it from the
SFTP ingress directory into the API's read-only release root, validates it
again, and atomically replaces current.json. It never retrieves data, runs a
model, builds containers, or accepts arbitrary filesystem paths.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from validate_drought_production_release import RELEASE_ID as PUBLIC_RELEASE_ID_PATTERN, validate_release


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_previous_release(pointer_path: Path) -> str | None:
    if not pointer_path.is_file():
        return None
    try:
        pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
        candidate = pointer.get("release_id")
        return candidate if isinstance(candidate, str) and PUBLIC_RELEASE_ID_PATTERN.fullmatch(candidate) else None
    except (OSError, json.JSONDecodeError):
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("release_id")
    parser.add_argument("--incoming-root", type=Path, required=True)
    parser.add_argument("--public-root", type=Path, required=True)
    parser.add_argument(
        "--allow-auto-validated-indicators",
        action="store_true",
        help="allow only an auto-validated indicator-evidence package at this separate pointer root",
    )
    args = parser.parse_args()
    if not PUBLIC_RELEASE_ID_PATTERN.fullmatch(args.release_id):
        parser.error("release_id is invalid")

    incoming_root = args.incoming_root.resolve(strict=True)
    public_root = args.public_root.resolve()
    incoming_release = (incoming_root / args.release_id).resolve(strict=True)
    if incoming_release.parent != incoming_root or not incoming_release.is_dir():
        parser.error("incoming release is missing or outside the configured ingress root")

    # Verify the uploaded package before and after copying.  Only an approved
    # release can become current; a failed copy never changes current.json.
    manifest = validate_release(
        incoming_release,
        allow_validated=False,
        allow_auto_validated_indicators=args.allow_auto_validated_indicators,
    )
    if args.allow_auto_validated_indicators and manifest.get("release_channel") != "indicator-evidence":
        parser.error("automatic activation accepts only indicator-evidence releases")
    public_root.mkdir(parents=True, exist_ok=True)
    target = public_root / args.release_id
    if target.exists():
        parser.error("target release ID already exists; releases are immutable")
    shutil.copytree(incoming_release, target, copy_function=shutil.copy2)
    try:
        validate_release(
            target,
            allow_validated=False,
            allow_auto_validated_indicators=args.allow_auto_validated_indicators,
        )
        pointer_path = public_root / "current.json"
        pointer = {
            "schema_version": "tsird-drought-production-current-pointer/v1",
            "release_id": args.release_id,
            "activated_at": utc_now(),
            "previous_release_id": read_previous_release(pointer_path),
        }
        encoded = (json.dumps(pointer, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
        with tempfile.NamedTemporaryFile(dir=public_root, prefix=".current-", suffix=".tmp", delete=False) as handle:
            handle.write(encoded)
            temporary_pointer = Path(handle.name)
        os.replace(temporary_pointer, pointer_path)
    except Exception:
        # Keep the copied immutable release for investigation/audit, but never
        # switch the pointer when validation or pointer creation fails.
        raise
    print(json.dumps(pointer, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
