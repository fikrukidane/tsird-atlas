#!/usr/bin/env python3
"""Apply a named local approval to one validated TSIRD drought release.

This command changes only the release manifest on the local staging mount. It
does not publish, transfer, activate or otherwise expose a release. A later
publisher still needs remote checksum verification before it can write a
production current-release pointer.
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from validate_drought_production_release import validate_release


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("release_directory", type=Path)
    parser.add_argument("--approved-by", required=True, help="named human release approver")
    args = parser.parse_args()

    approver = args.approved_by.strip()
    if len(approver) < 2:
        parser.error("--approved-by must identify the human approver")
    release_dir = args.release_directory.resolve()
    manifest_path = release_dir / "manifest.json"
    original_manifest = manifest_path.read_bytes()

    # Verify the exact local payload before changing its state.  This allows a
    # validated manifest but rejects a malformed, rejected or already-invalid
    # release.
    manifest = validate_release(release_dir, allow_validated=True)
    if manifest.get("release_state") != "validated":
        parser.error("only a validated release may be approved; create a new release for any revision")

    manifest["release_state"] = "approved"
    manifest["approved_by"] = approver
    manifest["approved_at"] = utc_now()
    encoded = (json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    with tempfile.NamedTemporaryFile(dir=release_dir, prefix=".manifest-", suffix=".tmp", delete=False) as handle:
        handle.write(encoded)
        temporary_path = Path(handle.name)
    try:
        os.replace(temporary_path, manifest_path)
        validate_release(release_dir, allow_validated=False)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        manifest_path.write_bytes(original_manifest)
        raise
    print(f"OK: approved local release {manifest['release_id']} as {approver}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
