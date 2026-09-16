"""Record a retained local evidence raster without exposing source credentials.

The source-specific run tables remain authoritative for measurements.  This
small catalogue gives the timeline UI one bounded, provenance-preserving index
for retained native grids and their matching Tabia summaries.
"""
import argparse
import csv
import json
import os
from pathlib import Path

import psycopg2
from psycopg2.extras import Json


SPECS = {
    "chirps": ("chc-chirps-v3", "rainfall", "observation_start", "observation_end", "raster_path", "raster_sha256"),
    "rapid": ("chc-chirps-v3-preliminary", "rapid_rainfall", "period_start", "period_end", "raster_path", "raster_sha256"),
    "ndvi": ("cdse-clms-ndvi-v3", "ndvi", "observation_timestamp", "observation_timestamp", "raster_path", "raster_sha256"),
    "swi": ("cdse-clms-swi-v4", "swi", "observation_at", "observation_at", "raster_path", "raster_sha256"),
    "lst": ("cdse-clms-lst-v2", "lst", "observation_at", "observation_at", "raster_path", "raster_sha256"),
    "wapor": ("fao-wapor-v3", "wapor_transpiration", "source_period_start", "source_period_end", "raster_paths", "raster_sha256"),
}


def dsn():
    return " ".join(("host=tsird-postgis", "port=5432", f"dbname={os.environ['POSTGRES_DB']}",
                     f"user={os.environ['POSTGRES_USER']}", f"password={os.environ['POSTGRES_PASSWORD']}"))


def quality_summary(base):
    with base.with_suffix(".csv").open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    counts = {}
    for row in rows:
        key = row.get("quality_status") or "unknown"
        counts[key] = counts.get(key, 0) + 1
    return {"record_count": len(rows), "quality_counts": counts}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("kind", choices=tuple(SPECS))
    parser.add_argument("artifact_base")
    args = parser.parse_args()
    base = Path(args.artifact_base)
    manifest = json.loads(base.with_suffix(".manifest.json").read_text(encoding="utf-8"))
    source_id, evidence_kind, start_key, end_key, paths_key, hashes_key = SPECS[args.kind]
    run_id = manifest["run_id"]
    start = manifest[start_key]
    end = manifest[end_key]
    paths = manifest[paths_key]
    hashes = manifest[hashes_key]
    if not isinstance(paths, dict): paths = {"primary": paths}
    if not isinstance(hashes, dict): hashes = {"primary": hashes}
    if args.kind == "wapor":
        # The dashboard's primary native view is transpiration.  Preserve AETI
        # as a named supporting raster without exposing either filesystem path.
        paths = {"primary": paths["transpiration"], "aeti": paths["aeti"]}
        hashes = {"primary": hashes["transpiration"], "aeti": hashes["aeti"]}
    if not all(isinstance(value, str) and value.startswith("/data/drought/") for value in paths.values()):
        raise ValueError("evidence raster path must stay within the local drought data mount")
    quality = quality_summary(base)
    provenance = {
        "source_product": manifest.get("source_product"),
        "collection_id": manifest.get("collection_id"),
        "method": manifest.get("method"),
        "publication_note": manifest.get("publication_note"),
        "source_retrieved_at": manifest.get("source_retrieved_at"),
    }
    with psycopg2.connect(dsn()) as conn, conn.cursor() as cur:
        cur.execute("""INSERT INTO tsird.drought_evidence_raster
          (evidence_id, source_id, run_id, evidence_kind, observation_start, observation_end,
           native_resolution, raster_paths, raster_sha256, boundary_set_version, status,
           quality_summary, provenance)
          VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
          ON CONFLICT (source_id, run_id) DO UPDATE SET
            observation_start=EXCLUDED.observation_start, observation_end=EXCLUDED.observation_end,
            native_resolution=EXCLUDED.native_resolution, raster_paths=EXCLUDED.raster_paths,
            raster_sha256=EXCLUDED.raster_sha256, boundary_set_version=EXCLUDED.boundary_set_version,
            status=EXCLUDED.status, quality_summary=EXCLUDED.quality_summary,
            provenance=EXCLUDED.provenance, updated_at=now()""",
          (f"evidence-raster--{run_id}", source_id, run_id, evidence_kind, start, end,
           manifest["native_resolution"], Json(paths), Json(hashes), manifest.get("boundary_set_version"),
           manifest["status"], Json(quality), Json(provenance)))
    print(json.dumps({"catalogued": True, "source_id": source_id, "run_id": run_id,
                      "record_count": quality["record_count"]}))


if __name__ == "__main__":
    main()
