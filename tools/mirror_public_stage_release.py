#!/usr/bin/env python3
"""Mirror the public assets needed for a local Drought UI stage.

This helper is deliberately *not* a publisher, validator, release builder, or
deployment tool. It downloads already-public dashboard values, display
geometry, and the three released exposure summaries, then creates an ignored,
local-only fixture for exercising the isolated stage. It never sends a request
other than HTTPS GET.
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
import re
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path


RELEASE_ID = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{6}Z-indicators$")
ASSETS = (
    "drought-workspace-latest",
    "tabia-geometry",
    "exposure-population",
    "exposure-cropland",
    "exposure-road",
)


def get_json(url: str) -> object:
    request = urllib.request.Request(url, headers={"Accept-Encoding": "identity"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def safe_asset_url(base_url: str, relative_url: object) -> str:
    if not isinstance(relative_url, str) or not relative_url.startswith("/map/api/drought/public/indicators/assets/"):
        raise ValueError("public metadata returned an unsafe asset URL")
    return urllib.parse.urljoin(base_url.rstrip("/") + "/", relative_url.lstrip("/"))


def write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}-", delete=False) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="https://lab.tigrayinsights.net")
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()

    metadata_url = args.base_url.rstrip("/") + "/map/api/drought/public/indicators"
    metadata = get_json(metadata_url)
    if not isinstance(metadata, dict):
        raise ValueError("public indicator metadata is not an object")
    release_id = metadata.get("release_id")
    if not isinstance(release_id, str) or not RELEASE_ID.fullmatch(release_id):
        raise ValueError("public indicator metadata has an unsupported release ID")
    asset_records = {
        item.get("asset_id"): item
        for item in metadata.get("assets", [])
        if isinstance(item, dict) and isinstance(item.get("asset_id"), str)
    }
    if set(ASSETS) - set(asset_records):
        raise ValueError("public indicator metadata lacks a required stage asset")

    release_dir = args.output_root.resolve() / release_id
    release_dir.mkdir(parents=True, exist_ok=True)
    manifest_assets = []
    for asset_id in ASSETS:
        source = asset_records[asset_id]
        asset_url = safe_asset_url(args.base_url, source.get("url"))
        request = urllib.request.Request(asset_url, headers={"Accept-Encoding": "identity"})
        with urllib.request.urlopen(request, timeout=180) as response:
            content = response.read()
        relative_path = f"{asset_id}.json"
        target = release_dir / relative_path
        write_bytes(target, content)
        # Match the release-builder contract so the stage exercises the same
        # immutable pre-compressed asset response as a future publication.
        write_bytes(target.with_name(f"{target.name}.gz"), gzip.compress(content, mtime=0))
        manifest_assets.append({"asset_id": asset_id, "relative_path": relative_path})

    manifest = {
        "schema_version": "tsird-drought-production-release/v1",
        "release_id": release_id,
        "release_state": "auto-validated",
        "release_channel": "indicator-evidence",
        "public_scope": "Local performance-stage fixture mirrored from already-public retained evidence; not a publisher release.",
        "freshness": metadata.get("freshness", []),
        "assets": manifest_assets,
    }
    write_bytes(release_dir / "manifest.json", (json.dumps(manifest, sort_keys=True) + "\n").encode("utf-8"))
    pointer = {
        "schema_version": "tsird-drought-performance-stage-pointer/v1",
        "release_id": release_id,
        "activated_at": metadata.get("activated_at"),
    }
    write_bytes(args.output_root.resolve() / "current.json", (json.dumps(pointer, sort_keys=True) + "\n").encode("utf-8"))
    print(f"Mirrored {release_id}: {', '.join(ASSETS)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
