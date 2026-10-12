#!/usr/bin/env python3
"""Mirror the public assets needed for a local Drought UI stage.

This helper is deliberately *not* a publisher, validator, release builder, or
deployment tool. It downloads already-public dashboard values, display
geometry, the three released exposure summaries, and exactly two historical
snapshots (one observed-rainfall and one NDVI), then creates an ignored,
local-only fixture for exercising the isolated stage. It never sends a request
other than HTTPS GET. The two snapshots deliberately cover the distinct
historical code paths without mirroring the full retained history.
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
    if not isinstance(relative_url, str) or not (
        relative_url.startswith("/map/api/drought/public/indicators/assets/")
        or re.fullmatch(r"/map/api/drought/public/indicators/releases/[0-9TZ:-]+-indicators/assets/[a-z0-9-]+", relative_url)
    ):
        raise ValueError("public metadata returned an unsafe asset URL")
    return urllib.parse.urljoin(base_url.rstrip("/") + "/", relative_url.lstrip("/"))


def write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}-", delete=False) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    os.replace(temporary, path)


def asset_id(prefix: str, run_id: str) -> str:
    """Match the public API's deterministic retained-run asset names."""
    suffix = re.sub(r"[^a-z0-9]+", "-", run_id.lower()).strip("-")
    if not suffix:
        raise ValueError("public retained-run ID cannot form a safe asset ID")
    return f"{prefix}-{suffix}"


def historical_run(index: object, description: str) -> dict:
    """Return one real retained run after the current (first) entry."""
    if not isinstance(index, dict) or not isinstance(index.get("runs"), list):
        raise ValueError(f"public {description} run index is malformed")
    for item in index["runs"][1:]:
        if isinstance(item, dict) and isinstance(item.get("run_id"), str) and item["run_id"]:
            return item
    raise ValueError(f"public {description} run index has no historical fixture")


def write_json_asset(release_dir: Path, manifest_assets: list[dict], name: str, payload: object) -> None:
    """Write an immutable-compatible JSON sidecar and its manifest record."""
    content = (json.dumps(payload, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")
    target = release_dir / f"{name}.json"
    write_bytes(target, content)
    write_bytes(target.with_name(f"{target.name}.gz"), gzip.compress(content, mtime=0))
    manifest_assets.append({"asset_id": name, "relative_path": target.name})


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

    geometry_pointer = get_json(args.base_url.rstrip("/") + "/map/api/drought/public/dashboard/geometry")
    if not isinstance(geometry_pointer, dict):
        raise ValueError("public geometry pointer is not an object")
    display_asset_id = geometry_pointer.get("asset_id")
    if (
        geometry_pointer.get("release_id") != release_id
        or not isinstance(display_asset_id, str)
        or not re.fullmatch(r"[a-z0-9-]+", display_asset_id)
    ):
        raise ValueError("public geometry pointer does not match the active indicator release")
    geometry_url = safe_asset_url(args.base_url, geometry_pointer.get("url"))

    release_dir = args.output_root.resolve() / release_id
    release_dir.mkdir(parents=True, exist_ok=True)
    manifest_assets = []
    for required_asset_id in (asset for asset in ASSETS if asset != "tabia-geometry"):
        source = asset_records[required_asset_id]
        asset_url = safe_asset_url(args.base_url, source.get("url"))
        request = urllib.request.Request(asset_url, headers={"Accept-Encoding": "identity"})
        with urllib.request.urlopen(request, timeout=180) as response:
            content = response.read()
        relative_path = f"{required_asset_id}.json"
        target = release_dir / relative_path
        write_bytes(target, content)
        # Match the release-builder contract so the stage exercises the same
        # immutable pre-compressed asset response as a future publication.
        write_bytes(target.with_name(f"{target.name}.gz"), gzip.compress(content, mtime=0))
        manifest_assets.append({"asset_id": required_asset_id, "relative_path": relative_path})

    # Follow the same release-ID display pointer as the public workspace. The
    # generic metadata endpoint retains a legacy GeoJSON convenience URL;
    # using it here would make the stage substantially larger than production
    # and hide a format regression.
    request = urllib.request.Request(geometry_url, headers={"Accept-Encoding": "identity"})
    with urllib.request.urlopen(request, timeout=180) as response:
        content = response.read()
    relative_path = f"{display_asset_id}.json"
    target = release_dir / relative_path
    write_bytes(target, content)
    write_bytes(target.with_name(f"{target.name}.gz"), gzip.compress(content, mtime=0))
    manifest_assets.append({"asset_id": display_asset_id, "relative_path": relative_path})

    base = args.base_url.rstrip("/")
    observed_index = get_json(f"{base}/map/api/drought/public/dashboard/observed-rainfall/runs")
    ndvi_index = get_json(f"{base}/map/api/drought/public/dashboard/evidence/ndvi/runs")
    observed_run = historical_run(observed_index, "observed-rainfall")
    ndvi_run = historical_run(ndvi_index, "NDVI")
    observed_run_id = observed_run["run_id"]
    ndvi_run_id = ndvi_run["run_id"]

    observed_snapshot = get_json(
        f"{base}/map/api/drought/public/dashboard/observed-rainfall/runs/"
        f"{urllib.parse.quote(observed_run_id, safe='')}"
    )
    ndvi_features = get_json(
        f"{base}/map/api/drought/public/dashboard/evidence/ndvi/runs/"
        f"{urllib.parse.quote(ndvi_run_id, safe='')}/features"
    )
    if not isinstance(ndvi_features, dict) or not isinstance(ndvi_features.get("features"), list):
        raise ValueError("public NDVI historical feature response is malformed")
    ndvi_rows = [
        feature.get("properties")
        for feature in ndvi_features["features"]
        if isinstance(feature, dict) and isinstance(feature.get("properties"), dict)
    ]
    if not ndvi_rows:
        raise ValueError("public NDVI historical feature response has no rows")

    write_json_asset(release_dir, manifest_assets, "observed-rainfall-runs", observed_index)
    write_json_asset(
        release_dir,
        manifest_assets,
        asset_id("observed-rainfall-run", observed_run_id),
        observed_snapshot,
    )
    write_json_asset(release_dir, manifest_assets, "evidence-ndvi-runs", ndvi_index)
    write_json_asset(
        release_dir,
        manifest_assets,
        asset_id("evidence-ndvi-run", ndvi_run_id),
        {"schema_version": "tsird-drought-evidence-snapshot.v1", "run": ndvi_run, "rows": ndvi_rows},
    )

    manifest = {
        "schema_version": "tsird-drought-production-release/v1",
        "release_id": release_id,
        "release_state": "auto-validated",
        "release_channel": "indicator-evidence",
        "public_scope": "Local performance-stage fixture mirrored from already-public retained evidence; not a publisher release.",
        "freshness": metadata.get("freshness", []),
        "display_geometry": {
            key: geometry_pointer[key]
            for key in ("asset_id", "format", "feature_count", "vertex_statistics")
            if key in geometry_pointer
        },
        "assets": manifest_assets,
    }
    write_bytes(release_dir / "manifest.json", (json.dumps(manifest, sort_keys=True) + "\n").encode("utf-8"))
    pointer = {
        "schema_version": "tsird-drought-performance-stage-pointer/v1",
        "release_id": release_id,
        "activated_at": metadata.get("activated_at"),
    }
    write_bytes(args.output_root.resolve() / "current.json", (json.dumps(pointer, sort_keys=True) + "\n").encode("utf-8"))
    print(
        f"Mirrored {release_id}: {', '.join(ASSETS)}; "
        f"historical observed={observed_run_id}; historical ndvi={ndvi_run_id}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
