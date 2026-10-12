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
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from build_drought_production_release import (
    API_PATHS,
    EVIDENCE_RUNS_PATH,
    EVIDENCE_SUMMARY_PATH,
    EXPOSURE_FEATURE_PATH,
    EXPOSURE_MEASURES,
    HISTORY_SOURCES,
    OBSERVED_FEATURE_PATH,
    OBSERVED_RUN_PATH,
    OBSERVED_RUNS_PATH,
    WORKSPACE_PATHS,
    asset_record,
    public_history_run_index,
    public_history_snapshot,
    public_exposure_features,
    public_observed_run_index,
    public_observed_snapshot,
    public_rainfall_index,
    public_tabia_geometry,
    public_workspace_summary,
    request_json,
    safe_asset_suffix,
    write_json,
)
from drought_indicator_freshness import build_freshness


RELEASE_ID = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{6}Z-indicators$")
REQUIRED_INDICATORS = tuple(WORKSPACE_PATHS)
NATIVE_RASTERS = (
    ("native-raster-chirps", "chirps-current-rainfall.tif", "TSIRD display-ready CHIRPS final rainfall native grid", "observed"),
    ("native-raster-rapid", "chirps-rapid-rainfall.tif", "TSIRD display-ready CHIRPS preliminary rainfall native grid", "rapid"),
    ("native-raster-ndvi", "ndvi-current.tif", "TSIRD display-ready Copernicus NDVI native grid", "vegetation"),
    ("native-raster-swi", "swi040-current.tif", "TSIRD display-ready Copernicus SWI-040 native grid", "soil_water"),
    ("native-raster-lst", "lst-current.tif", "TSIRD display-ready Copernicus LST native grid", "thermal"),
    ("native-raster-wapor", "wapor-transpiration-current.tif", "TSIRD display-ready FAO WaPOR transpiration native grid", "water_use"),
)
DISPLAY_COORDINATE_PRECISION = 0.00001
DISPLAY_SIMPLIFICATION_INTERVAL_METERS = 75.0
DISPLAY_SIMPLIFICATION_INTERVAL_MIN_METERS = 30.0
DISPLAY_SIMPLIFICATION_INTERVAL_MAX_METERS = 75.0
DISPLAY_VERTEX_FLOOR = 4
KNOWN_SOURCE_FLOOR_TABIA_IDS = frozenset({
    "tsird-tabia-v1-eaac4242a1fc0b5b3399463efb3e4ccd",  # Debre Genet, Kola Temben
    "tsird-tabia-v1-490fc743c6304faac0849b61ae167eb5",  # Menachek, Degua Temben
})


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


def _round_display_coordinates(value: Any, precision: int = 5) -> Any:
    """Round only the public display copy; analytical PostGIS geometry stays intact."""
    if isinstance(value, float):
        return round(value, precision)
    if isinstance(value, list):
        return [_round_display_coordinates(item, precision) for item in value]
    return value


def compact_display_geometry(payload: dict[str, Any]) -> dict[str, Any]:
    """Prepare the release-only geometry before topology-preserving simplify."""
    if payload.get("type") != "FeatureCollection" or not isinstance(payload.get("features"), list):
        raise RuntimeError("public Tabia geometry is not a FeatureCollection")
    compact = dict(payload)
    compact["features"] = []
    for feature in payload["features"]:
        geometry = feature.get("geometry") if isinstance(feature, dict) else None
        if not isinstance(geometry, dict) or "coordinates" not in geometry:
            raise RuntimeError("public Tabia geometry contains an invalid feature")
        compact["features"].append({
            **feature,
            "geometry": {**geometry, "coordinates": _round_display_coordinates(geometry["coordinates"])},
        })
    compact["display_coordinate_precision"] = 5
    compact["display_geometry_note"] = (
        "Display-only coordinates are prepared for topology-preserving simplification; analytical PostGIS boundaries are unchanged."
    )
    return compact


def tabia_ids(payload: dict[str, Any]) -> set[str]:
    """Return the exact Tabia identity set expected in a display geometry."""
    features = payload.get("features")
    if not isinstance(features, list):
        raise RuntimeError("public Tabia geometry is not a FeatureCollection")
    identifiers = {
        feature.get("properties", {}).get("tsird_tabia_id")
        for feature in features
        if isinstance(feature, dict)
        and isinstance(feature.get("properties"), dict)
        and isinstance(feature["properties"].get("tsird_tabia_id"), str)
        and isinstance(feature.get("geometry"), dict)
        and feature["geometry"].get("coordinates")
    }
    if len(identifiers) != len(features):
        raise RuntimeError("public Tabia geometry has a missing identity or empty feature")
    return identifiers


def _ring_vertex_count(ring: Any) -> int:
    """Count a GeoJSON ring without its repeated closing coordinate."""
    if not isinstance(ring, list) or not ring:
        raise RuntimeError("public Tabia geometry contains an invalid polygon ring")
    count = len(ring)
    if count > 1 and ring[0] == ring[-1]:
        count -= 1
    if count < 3:
        raise RuntimeError("public Tabia geometry contains a degenerate polygon ring")
    return count


def feature_vertex_count(feature: Any) -> int:
    """Return the display vertices for Polygon or MultiPolygon geometry."""
    geometry = feature.get("geometry") if isinstance(feature, dict) else None
    if not isinstance(geometry, dict):
        raise RuntimeError("public Tabia geometry contains an invalid feature")
    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates")
    if geometry_type == "Polygon" and isinstance(coordinates, list):
        rings = coordinates
    elif geometry_type == "MultiPolygon" and isinstance(coordinates, list):
        rings = [ring for polygon in coordinates if isinstance(polygon, list) for ring in polygon]
    else:
        raise RuntimeError("public Tabia geometry contains a non-polygon feature")
    return sum(_ring_vertex_count(ring) for ring in rings)


def floor_tabia_ids(payload: dict[str, Any]) -> set[str]:
    """Return the low-vertex source geometries that need a boundary-data repair."""
    features = payload.get("features") if isinstance(payload, dict) else None
    if not isinstance(features, list):
        raise RuntimeError("public Tabia geometry has no features")
    result: set[str] = set()
    for feature in features:
        properties = feature.get("properties") if isinstance(feature, dict) else None
        tabia_id = properties.get("tsird_tabia_id") if isinstance(properties, dict) else None
        if not isinstance(tabia_id, str):
            raise RuntimeError("public Tabia geometry has a missing identity")
        if feature_vertex_count(feature) <= DISPLAY_VERTEX_FLOOR:
            result.add(tabia_id)
    return result


def display_vertex_statistics(payload: dict[str, Any]) -> dict[str, int | float]:
    """Describe release-only geometry fidelity without changing analysis data."""
    features = payload.get("features") if isinstance(payload, dict) else None
    if not isinstance(features, list) or not features:
        raise RuntimeError("public Tabia geometry has no features for vertex statistics")
    values = sorted(feature_vertex_count(feature) for feature in features)
    midpoint = len(values) // 2
    if len(values) % 2:
        median: int | float = values[midpoint]
    else:
        median = (values[midpoint - 1] + values[midpoint]) / 2
    return {
        "feature_count": len(values),
        "minimum_vertices": values[0],
        "median_vertices": median,
        "maximum_vertices": values[-1],
        "floor_vertices": DISPLAY_VERTEX_FLOOR,
        "floor_feature_count": sum(value <= DISPLAY_VERTEX_FLOOR for value in values),
    }


def simplify_display_geometry(
    payload: dict[str, Any], mapshaper_bin: str, interval_meters: float
) -> dict[str, Any]:
    """Simplify only the public copy with shared topology preserved.

    ``mapshaper`` builds topology across the whole FeatureCollection before it
    simplifies. That makes shared Tabia borders use the same retained arcs,
    unlike per-feature simplification which can introduce visible slivers.
    The source PostGIS geometry is never read or changed by this operation.
    """
    source = compact_display_geometry(payload)
    expected_ids = tabia_ids(source)
    source_floor_ids = floor_tabia_ids(source)
    if not source_floor_ids.issubset(KNOWN_SOURCE_FLOOR_TABIA_IDS):
        raise RuntimeError("source Tabia geometry contains an unrecognised low-vertex boundary")
    with tempfile.TemporaryDirectory(prefix="tsird-display-geometry-") as temp:
        input_path = Path(temp) / "tabia-geometry-source.json"
        output_path = Path(temp) / "tabia-geometry.json"
        input_path.write_text(json.dumps(source, separators=(",", ":")), encoding="utf-8")
        try:
            subprocess.run(
                [
                    mapshaper_bin,
                    str(input_path),
                    "-simplify",
                    f"interval={interval_meters:g}m",
                    "keep-shapes",
                    "-o",
                    "format=geojson",
                    f"precision={DISPLAY_COORDINATE_PRECISION}",
                    str(output_path),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError as error:
            raise RuntimeError(
                "topology-preserving display simplifier is unavailable; install the pinned mapshaper tool before building an indicator release"
            ) from error
        except subprocess.CalledProcessError as error:
            detail = (error.stderr or error.stdout or "mapshaper failed").strip()
            raise RuntimeError(f"topology-preserving display simplification failed: {detail}") from error
        if not output_path.is_file():
            raise RuntimeError("topology-preserving display simplifier produced no geometry output")
        try:
            simplified = json.loads(output_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise RuntimeError("topology-preserving display simplifier produced invalid JSON") from error
    if not isinstance(simplified, dict) or simplified.get("type") != "FeatureCollection":
        raise RuntimeError("topology-preserving display simplifier produced invalid geometry")
    if tabia_ids(simplified) != expected_ids:
        raise RuntimeError("topology-preserving display simplifier changed the released Tabia identity set")
    simplified_floor_ids = floor_tabia_ids(simplified)
    if not simplified_floor_ids.issubset(source_floor_ids):
        raise RuntimeError(
            "topology-preserving display simplification introduced one or more low-vertex Tabias; "
            "choose a more faithful interval"
        )
    vertex_statistics = display_vertex_statistics(simplified)
    vertex_statistics.update({
        "preexisting_floor_feature_count": len(simplified_floor_ids),
        "preexisting_floor_tabia_ids": sorted(simplified_floor_ids),
        "introduced_floor_feature_count": 0,
    })
    simplified["schema_version"] = source.get("schema_version", "tsird-public-tabia-geometry/v1")
    simplified["display_coordinate_precision"] = 5
    simplified["display_simplification"] = {
        "engine": "mapshaper@0.7.83",
        "method": "interval",
        "interval_meters": interval_meters,
        "topology": "shared Tabia arcs retained together with keep-shapes",
    }
    simplified["display_vertex_statistics"] = vertex_statistics
    simplified["display_geometry_note"] = (
        "Display-only geometry simplified with shared Tabia topology and five-decimal output precision; analytical PostGIS boundaries are unchanged."
    )
    return simplified


def encode_display_topology(
    geometry: dict[str, Any], mapshaper_bin: str
) -> dict[str, Any]:
    """Encode the already-validated display copy with shared arcs for the browser.

    The GeoJSON companion remains inside the release for server-side metadata
    lookups. The dashboard receives this TopoJSON asset because its shared arcs
    keep a faithful mixed-size Tabia layer inside the slow-4G byte budget.
    """
    with tempfile.TemporaryDirectory(prefix="tsird-display-topology-") as temp:
        input_path = Path(temp) / "tabia-geometry.json"
        output_path = Path(temp) / "tabia-geometry-display.topojson"
        input_path.write_text(json.dumps(geometry, separators=(",", ":")), encoding="utf-8")
        try:
            subprocess.run(
                [mapshaper_bin, str(input_path), "-o", "format=topojson", str(output_path)],
                check=True,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError as error:
            raise RuntimeError("topology-preserving display simplifier is unavailable") from error
        except subprocess.CalledProcessError as error:
            detail = (error.stderr or error.stdout or "mapshaper failed").strip()
            raise RuntimeError(f"TopoJSON display encoding failed: {detail}") from error
        try:
            topology = json.loads(output_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise RuntimeError("TopoJSON display encoding produced invalid JSON") from error
    if not isinstance(topology, dict) or topology.get("type") != "Topology" or not isinstance(topology.get("objects"), dict):
        raise RuntimeError("TopoJSON display encoding produced invalid topology")
    for key in ("schema_version", "display_coordinate_precision", "display_simplification", "display_vertex_statistics", "display_geometry_note"):
        topology[key] = geometry[key]
    return topology


def copy_native_rasters(source_root: Path, release_dir: Path, payloads: dict[str, dict[str, Any]], boundary: str) -> list[dict[str, Any]]:
    """Copy only display-ready physical-value rasters into the immutable package.

    Provider archives and credentials never cross this boundary.  The six fixed
    filenames are the same derivatives already rendered in development; each
    copy is checksummed in the manifest before the automatic pointer can move.
    """
    records: list[dict[str, Any]] = []
    for asset_id, filename, source, indicator in NATIVE_RASTERS:
        source_path = source_root / filename
        if not source_path.is_file() or source_path.is_symlink():
            raise RuntimeError(f"native display raster is missing or unsafe: {source_path}")
        target = release_dir / filename
        shutil.copyfile(source_path, target)
        digest = hashlib.sha256()
        with target.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        run = payloads[indicator].get("run")
        if not isinstance(run, dict):
            raise RuntimeError(f"{indicator} has no run metadata for native raster")
        start, end = observation_window(run)
        records.append(asset_record(
            asset_id, "native_evidence_raster", filename,
            (target.stat().st_size, digest.hexdigest()), source, start, end,
            str(run.get("schema_version") or run.get("run_id") or "unknown"), boundary,
        ))
    return records


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
    parser.add_argument("--native-raster-root", type=Path, default=Path("/data/drought/published"), help="fixed display-ready native-raster directory")
    parser.add_argument("--prepared-by", default="TSIRD automated indicator validation", help="release preparer identity")
    parser.add_argument("--release-id", default=None, help="optional UTC indicator release ID")
    parser.add_argument("--mapshaper-bin", default="mapshaper", help="pinned mapshaper executable for release-only display geometry")
    parser.add_argument(
        "--display-simplification-interval-meters",
        type=float,
        default=DISPLAY_SIMPLIFICATION_INTERVAL_METERS,
        help=(
            "mapshaper display-only simplification interval in metres; must stay within "
            f"{DISPLAY_SIMPLIFICATION_INTERVAL_MIN_METERS:g}-{DISPLAY_SIMPLIFICATION_INTERVAL_MAX_METERS:g} m"
        ),
    )
    args = parser.parse_args()

    if not (
        DISPLAY_SIMPLIFICATION_INTERVAL_MIN_METERS
        <= args.display_simplification_interval_meters
        <= DISPLAY_SIMPLIFICATION_INTERVAL_MAX_METERS
    ):
        print(
            "ERROR: display simplification interval must be between "
            f"{DISPLAY_SIMPLIFICATION_INTERVAL_MIN_METERS:g} and {DISPLAY_SIMPLIFICATION_INTERVAL_MAX_METERS:g} metres",
            file=sys.stderr,
        )
        return 2

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
        freshness = build_freshness(workspace_payloads)
        rainfall_payload = request_json(args.api_base, API_PATHS["drought-evidence-summary.json"])
        observed_runs_payload = request_json(args.api_base, OBSERVED_RUNS_PATH)
        exposure_payloads = {
            measure: request_json(args.api_base, EXPOSURE_FEATURE_PATH.format(measure=measure))
            for measure in EXPOSURE_MEASURES
        }
    except RuntimeError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    rainfall_runs = rainfall_payload.get("runs")
    if not isinstance(rainfall_runs, list) or not rainfall_runs or not isinstance(rainfall_runs[0], dict):
        print("ERROR: final rainfall evidence index is incomplete", file=sys.stderr)
        return 2
    observed_runs = observed_runs_payload.get("runs")
    if not isinstance(observed_runs, list) or not observed_runs:
        print("ERROR: observed rainfall snapshot index is incomplete", file=sys.stderr)
        return 2
    observed_asset_ids: dict[str, str] = {}
    history_payloads: dict[str, dict[str, Any]] = {}
    history_asset_ids: dict[str, dict[str, str]] = {}
    try:
        for index, run in enumerate(observed_runs):
            run_id = run.get("run_id") if isinstance(run, dict) else None
            if not isinstance(run_id, str):
                raise RuntimeError("observed rainfall snapshot is missing its run ID")
            asset_id = f"observed-rainfall-run-{safe_asset_suffix(run_id)}"
            observed_asset_ids[run_id] = asset_id
            history_payloads[f"{asset_id}.json"] = public_observed_snapshot(request_json(args.api_base, OBSERVED_RUN_PATH.format(run_id=run_id)))
            if index == 0:
                history_payloads["tabia-geometry.json"] = simplify_display_geometry(
                    public_tabia_geometry(request_json(args.api_base, OBSERVED_FEATURE_PATH.format(run_id=run_id))),
                    args.mapshaper_bin,
                    args.display_simplification_interval_meters,
                )
                history_payloads["tabia-geometry-display.topojson"] = encode_display_topology(
                    history_payloads["tabia-geometry.json"], args.mapshaper_bin
                )
        history_payloads["observed-rainfall-runs.json"] = public_observed_run_index(observed_runs_payload)
        for source in HISTORY_SOURCES:
            index_payload = request_json(args.api_base, EVIDENCE_RUNS_PATH.format(source=source))
            index = public_history_run_index(source, index_payload)
            runs = index.get("runs")
            if not isinstance(runs, list) or not runs:
                raise RuntimeError(f"{source} evidence index is incomplete")
            history_payloads[f"evidence-{source}-runs.json"] = index
            history_asset_ids[source] = {}
            for run in runs:
                run_id = run.get("run_id") if isinstance(run, dict) else None
                if not isinstance(run_id, str):
                    raise RuntimeError(f"{source} evidence run is missing its run ID")
                asset_id = f"evidence-{source}-run-{safe_asset_suffix(run_id)}"
                history_asset_ids[source][run_id] = asset_id
                history_payloads[f"{asset_id}.json"] = public_history_snapshot(source, run, request_json(args.api_base, EVIDENCE_SUMMARY_PATH.format(source=source, run_id=run_id)))
    except RuntimeError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2

    geometry = history_payloads.get("tabia-geometry.json")
    geometry_features = geometry.get("features") if isinstance(geometry, dict) else None
    expected_tabia_ids = {
        feature.get("properties", {}).get("tsird_tabia_id")
        for feature in geometry_features or []
        if isinstance(feature, dict) and isinstance(feature.get("properties"), dict)
        and isinstance(feature["properties"].get("tsird_tabia_id"), str)
    }
    if not expected_tabia_ids:
        print("ERROR: released Tabia geometry is incomplete", file=sys.stderr)
        return 2
    try:
        exposure_assets = {
            measure: public_exposure_features(measure, payload, expected_tabia_ids)
            for measure, payload in exposure_payloads.items()
        }
    except RuntimeError as error:
        print(f"ERROR: {error}", file=sys.stderr)
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
    written.update({filename: write_json(release_dir / filename, payload) for filename, payload in history_payloads.items()})
    written.update({
        f"exposure-{measure}.json": write_json(release_dir / f"exposure-{measure}.json", payload)
        for measure, payload in exposure_assets.items()
    })
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
        asset_record("tabia-geometry", "vector_display_summary", "tabia-geometry.json", written["tabia-geometry.json"], "TSIRD Tabia boundary geometry for retained evidence display", start, end, history_payloads["tabia-geometry.json"].get("schema_version", "unknown"), f"{boundary} Boundary geometry joins only to released Tabia evidence summaries."),
        asset_record("tabia-geometry-display", "vector_display_summary", "tabia-geometry-display.topojson", written["tabia-geometry-display.topojson"], "TSIRD shared-arc Tabia display geometry for retained evidence", start, end, history_payloads["tabia-geometry.json"].get("schema_version", "unknown"), f"{boundary} Shared-arc display geometry only; analytical PostGIS boundaries are unchanged."),
        asset_record("observed-rainfall-runs", "drought_evidence_summary", "observed-rainfall-runs.json", written["observed-rainfall-runs.json"], "TSIRD retained observed rainfall snapshot index", start, end, history_payloads["observed-rainfall-runs.json"].get("schema_version", "unknown"), f"{boundary} Historical selections remain archived observations."),
        asset_record("release-status", "public_status", "status.json", written["status.json"], "TSIRD automated indicator validator", start, end, status["schema_version"], "Publication provenance only; it is not a scientific certification or operational decision."),
    ]
    assets.extend([
        asset_record(
            f"exposure-{measure}", "vector_display_summary", f"exposure-{measure}.json", written[f"exposure-{measure}.json"],
            {"population": "WorldPop 2025 Tabia population baseline", "cropland": "ESA WorldCover 2021 Tabia cropland baseline", "road": "TSIRD Tigray Roads 2006 Tabia road-proximity baseline"}[measure],
            start, end, exposure_assets[measure].get("schema_version", "unknown"),
            "Static Tabia context shown separately; it is not a composite risk, food-security classification, allocation recommendation, or operational decision.",
        )
        for measure in EXPOSURE_MEASURES
    ])
    for run in observed_runs:
        run_id = run["run_id"]
        asset_id = observed_asset_ids[run_id]
        filename = f"{asset_id}.json"
        run_start, run_end = observation_window(run)
        assets.append(asset_record(asset_id, "vector_display_summary", filename, written[filename], "TSIRD retained observed rainfall Tabia snapshot", run_start, run_end, history_payloads[filename].get("schema_version", "unknown"), f"{boundary} Historical snapshot is an archived observation, not a forecast or a past decision product."))
    for source in HISTORY_SOURCES:
        index_filename = f"evidence-{source}-runs.json"
        index = history_payloads[index_filename]
        runs = index["runs"]
        index_start, index_end = observation_window(runs[0])
        assets.append(asset_record(f"evidence-{source}-runs", "drought_evidence_summary", index_filename, written[index_filename], f"TSIRD retained {source} evidence index", index_start, index_end, index.get("schema_version", "unknown"), f"{boundary} Retained source observations remain separate."))
        for run in runs:
            run_id = run["run_id"]
            asset_id = history_asset_ids[source][run_id]
            filename = f"{asset_id}.json"
            run_start, run_end = observation_window(run)
            assets.append(asset_record(asset_id, "vector_display_summary", filename, written[filename], f"TSIRD retained {source} Tabia snapshot", run_start, run_end, history_payloads[filename].get("schema_version", "unknown"), f"{boundary} Retained source observation only; it does not create a class, forecast, or priority result."))
    try:
        assets.extend(copy_native_rasters(args.native_raster_root, release_dir, workspace_payloads, boundary))
    except RuntimeError as error:
        shutil.rmtree(release_dir, ignore_errors=True)
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    manifest = {
        "schema_version": "tsird-drought-production-release/v1",
        "release_id": release_id,
        "release_state": "auto-validated",
        "release_channel": "indicator-evidence",
        "prepared_by": args.prepared_by,
        "prepared_at": utc_now(),
        "previous_release_id": None,
        "public_scope": boundary,
        "freshness": freshness,
        "display_geometry": {
            "asset_id": "tabia-geometry-display",
            "format": "topojson",
            "simplification": history_payloads["tabia-geometry.json"]["display_simplification"],
            "vertex_statistics": history_payloads["tabia-geometry.json"]["display_vertex_statistics"],
        },
        "assets": assets,
    }
    write_json(release_dir / "manifest.json", manifest)
    print(json.dumps({"release_directory": str(release_dir), "release_id": release_id, "assets": len(assets)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
