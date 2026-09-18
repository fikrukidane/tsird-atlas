"""Synchronize current native evidence rasters with the current Tabia run.

The dashboard/API chooses each current evidence run by the provider observation
date, not by the time an older retained artifact happened to be loaded.  This
tool applies that exact selection rule to the stable MapServer raster paths.
It is deliberately local-development only: it reads retained rasters, writes
only display derivatives below ``/data/drought/published``, and never acquires
provider data or changes Tabia summaries.
"""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path

import psycopg2
import rasterio

from publish_evidence_raster import publish_provider_band, publish_rainfall_total


ROOT = Path("/data/drought")
PUBLISHED = ROOT / "published"
STATE_PATH = PUBLISHED / "current-evidence-manifest.json"

SPECS = {
    "rainfall": {
        "query": """SELECT run_id, source_latest_month::text AS observed_at
                    FROM tsird.drought_rainfall_run WHERE status='development'
                    ORDER BY source_latest_month DESC, cardinality(season_months) DESC, created_at DESC LIMIT 1""",
        "target": "chirps-current-rainfall.tif", "source": lambda row: PUBLISHED / f"{row['run_id']}.tif",
        "publish": "rainfall",
        "table": "drought_tabia_rainfall_condition", "value": "rainfall_mm",
    },
    "rapid": {
        "query": """SELECT run_id, period_end::text AS observed_at
                    FROM tsird.drought_preliminary_rainfall_run WHERE status='development'
                    ORDER BY period_end DESC, created_at DESC LIMIT 1""",
        "target": "chirps-rapid-rainfall.tif", "source": lambda row: PUBLISHED / f"{row['run_id']}.tif",
        "publish": "rainfall",
        "table": "drought_tabia_preliminary_rainfall", "value": "rainfall_mm",
    },
    "ndvi": {
        "query": """SELECT run_id, raster_path, observation_end::text AS observed_at
                    FROM tsird.drought_ndvi_run ORDER BY observation_end DESC, created_at DESC LIMIT 1""",
        "target": "ndvi-current.tif", "source": lambda row: Path(row['raster_path']),
        "publish": "provider", "band": 1, "scale": 1 / 250, "offset": -0.08, "mask_band": 3,
        "table": "drought_tabia_ndvi", "value": "ndvi_mean",
    },
    "swi": {
        "query": """SELECT run_id, raster_path, observation_at::text AS observed_at
                    FROM tsird.drought_swi_run ORDER BY observation_at DESC, created_at DESC LIMIT 1""",
        "target": "swi040-current.tif", "source": lambda row: Path(row['raster_path']),
        "publish": "provider", "band": 2, "scale": 0.5, "offset": 0, "mask_band": 5,
        "table": "drought_tabia_swi", "value": "swi040_mean",
    },
    "lst": {
        "query": """SELECT run_id, raster_path, observation_at::text AS observed_at
                    FROM tsird.drought_lst_run ORDER BY observation_at DESC, created_at DESC LIMIT 1""",
        "target": "lst-current.tif", "source": lambda row: Path(row['raster_path']),
        "publish": "provider", "band": 1, "scale": 0.01, "offset": 0, "mask_band": 5,
        "table": "drought_tabia_lst", "value": "lst_c_mean",
    },
    "wapor": {
        "query": """SELECT run_id, transpiration_raster_path AS raster_path, source_period_end::text AS observed_at
                    FROM tsird.drought_wapor_run ORDER BY source_period_end DESC, created_at DESC LIMIT 1""",
        "target": "wapor-transpiration-current.tif", "source": lambda row: Path(row['raster_path']),
        "publish": "wapor",
        "table": "drought_tabia_wapor", "value": "transpiration_mm",
    },
}


def dsn():
    return " ".join(("host=tsird-postgis", "port=5432", f"dbname={os.environ['POSTGRES_DB']}",
                     f"user={os.environ['POSTGRES_USER']}", f"password={os.environ['POSTGRES_PASSWORD']}"))


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def selected_run(cursor, spec):
    cursor.execute(spec["query"])
    row = cursor.fetchone()
    if not row:
        raise RuntimeError("no retained development evidence run is available")
    return {column.name: value for column, value in zip(cursor.description, row)}


def retained_sources(kind, spec, row):
    primary = spec["source"](row)
    if primary.is_file():
        return [primary]
    # Older preliminary records pre-date the per-run derived raster. Their
    # manifests still identify the exact six cached pentads, so rebuild from
    # those retained source clips rather than letting the stale stable raster
    # stand in for a newer Tabia run.
    if kind == "rapid":
        manifest_path = ROOT / "outputs" / f"{row['run_id']}.manifest.json"
        if manifest_path.is_file():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            paths = [ROOT / "cache" / "prelim-tabia-extent-v1" /
                     f"chirps-v3-prelim.{item['year']}.{item['month']:02d}.{item['pentad']}.tif"
                     for item in manifest.get("selected_pentads", [])]
            if paths and all(path.is_file() for path in paths):
                return paths
    return [primary]


def apply(spec, sources, target):
    if spec["publish"] == "rainfall":
        publish_rainfall_total(sources, target)
    elif spec["publish"] == "wapor":
        with rasterio.open(sources[0]) as dataset:
            scale = dataset.scales[0] if dataset.scales and dataset.scales[0] not in (None, 0) else 1.0
        publish_provider_band(sources[0], target, band=1, scale=scale, offset=0, mask_band=None)
    else:
        publish_provider_band(sources[0], target, band=spec["band"], scale=spec["scale"],
                              offset=spec["offset"], mask_band=spec["mask_band"])


def verify_tabia_values(cursor, kind, spec, run_id):
    """Check that every stored Tabia value is exactly the retained summary value."""
    csv_path = ROOT / "outputs" / f"{run_id}.csv"
    if not csv_path.is_file():
        raise RuntimeError(f"{kind}: retained Tabia summary is missing: {csv_path}")
    with csv_path.open(encoding="utf-8", newline="") as source:
        expected = {row["tsird_tabia_id"]: row.get(spec["value"]) or None for row in csv.DictReader(source)}
    cursor.execute(f"SELECT tsird_tabia_id, {spec['value']}::text FROM tsird.{spec['table']} WHERE run_id=%s", (run_id,))
    actual = dict(cursor.fetchall())
    mismatched = []
    for tabia_id, value in expected.items():
        stored = actual.get(tabia_id)
        if value is None and stored is None:
            continue
        if value is None or stored is None or abs(float(value) - float(stored)) > 1e-6:
            mismatched.append(tabia_id)
    return {"source_rows": len(expected), "stored_rows": len(actual), "mismatched_rows": len(mismatched),
            "sample_mismatched_ids": mismatched[:5], "passed": len(expected) == len(actual) and not mismatched}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--kind", choices=(*SPECS, "all"), default="all")
    parser.add_argument("--apply", action="store_true", help="regenerate the selected stable native-raster paths")
    parser.add_argument("--verify-tabia-values", action="store_true",
                        help="compare all current stored Tabia values with their retained source summaries")
    args = parser.parse_args()
    requested = tuple(SPECS) if args.kind == "all" else (args.kind,)
    previous = json.loads(STATE_PATH.read_text(encoding="utf-8")) if STATE_PATH.is_file() else {"indicators": {}}
    indicators, report = {}, []
    with psycopg2.connect(dsn()) as connection, connection.cursor() as cursor:
        for kind in requested:
            spec = SPECS[kind]
            row = selected_run(cursor, spec)
            sources = retained_sources(kind, spec, row)
            target = PUBLISHED / spec["target"]
            missing = [path for path in sources if not path.is_file()]
            if missing:
                raise RuntimeError(f"{kind}: retained source raster is missing: {missing[0]}")
            prior = (previous.get("indicators") or {}).get(kind, {})
            synchronized = prior.get("run_id") == row["run_id"] and target.is_file() and prior.get("target_sha256") == sha256(target)
            if args.apply:
                apply(spec, sources, target)
                synchronized = True
            target_hash = sha256(target) if target.is_file() else None
            indicators[kind] = {"run_id": row["run_id"], "observed_at": str(row["observed_at"]),
                                "source_paths": [str(path) for path in sources], "target_path": str(target),
                                "target_sha256": target_hash}
            report.append({"kind": kind, "run_id": row["run_id"], "observed_at": str(row["observed_at"]),
                           "source_exists": True, "target_exists": target.is_file(), "synchronized": synchronized})
            if args.verify_tabia_values:
                report[-1]["tabia_values"] = verify_tabia_values(cursor, kind, spec, row["run_id"])
    if args.apply:
        state = {"format": "tsird-current-evidence-v1", "indicators": {**(previous.get("indicators") or {}), **indicators}}
        temporary = STATE_PATH.with_suffix(".json.part")
        temporary.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        temporary.replace(STATE_PATH)
    print(json.dumps({"development_only": True, "applied": args.apply, "indicators": report}, indent=2))
    if not args.apply and not all(item["synchronized"] for item in report):
        raise SystemExit(2)
    if args.verify_tabia_values and not all(item["tabia_values"]["passed"] for item in report):
        raise SystemExit(3)


if __name__ == "__main__":
    main()
