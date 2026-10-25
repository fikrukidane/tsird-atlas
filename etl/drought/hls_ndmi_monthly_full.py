"""Build one fixed all-Tabia monthly HLS NDMI DEV evidence artifact.

This is deliberately separate from the 20-Tabia feasibility pilot.  It uses
the pilot's reviewed 30 m pixel-level compositing and mask profiles, retains
only compact Tabia statistics, and checkpoints locally after each Tabia so an
interruption can resume without repeating completed provider reads.  It has no
schedule, public-release path, or production behaviour.
"""
import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import psycopg2

from hls_ndmi_monthly_pilot import (
    HLS_COLLECTIONS, MIN_LIMITED_SPATIAL_COVERAGE_PCT,
    MIN_SPATIAL_COVERAGE_PCT, MIN_USABLE_ACQUISITIONS,
    MIN_VALID_OBSERVATION_PIXELS, PRODUCT, dsn, earthdata_token,
    completed_month, summarize_tabia,
)

SOURCE_ID = "nasa-hls-v2-ndmi-monthly-full-development"
PROCESSING_VERSION = "tsird-hls-ndmi-monthly-full-dev.v1-spatial-coverage"
TABIA_COUNT = 748


def full_tabias():
    """Return exactly the canonical regional set in a reproducible order."""
    with psycopg2.connect(dsn()) as conn, conn.cursor() as cur:
        cur.execute('''SELECT i.tsird_tabia_id, t."TABIA", t."WEREDA", ST_AsGeoJSON(t.geometry)
                       FROM tigray_tabias_ws t
                       JOIN tsird.tabia_identity i USING (tsird_tabia_id)
                       ORDER BY i.tsird_tabia_id''')
        rows = [(row[0], row[1], row[2], json.loads(row[3])) for row in cur.fetchall()]
    if len(rows) != TABIA_COUNT:
        raise RuntimeError(f"Expected exactly {TABIA_COUNT} canonical Tabias, found {len(rows)}")
    return rows


def read_checkpoint(path):
    if not path.is_file():
        return []
    with path.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    ids = [row.get("tsird_tabia_id", "") for row in rows]
    if (len(rows) > TABIA_COUNT or len(set(ids)) != len(ids) or
            any(not value.startswith("tsird-tabia-v1-") for value in ids)):
        raise RuntimeError("HLS full-development checkpoint is invalid")
    return rows


def write_rows(path, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


def row_from_profiles(tabia_id, tabia, woreda, profiles):
    primary = profiles["adjacency_allowed"]
    if primary["evidence_tier"] == "adequate":
        quality = "ok"
    elif primary["evidence_tier"] == "limited":
        quality = "limited_observation_coverage"
    else:
        quality = "insufficient_observation_coverage"
    row = {
        "tsird_tabia_id": tabia_id,
        "tabia_name_en": tabia,
        "woreda_name_en": woreda,
        "ndmi_mean": primary["ndmi_mean"],
        "ndmi_median": primary["ndmi_median"],
        "valid_observation_pixel_count": primary["valid_spatial_pixel_count"],
        "candidate_observation_pixel_count": primary["total_eligible_pixel_count"],
        "coverage_pct": primary["spatial_coverage_pct"],
        "candidate_acquisition_count": primary["candidate_acquisition_count"],
        "usable_acquisition_count": primary["usable_acquisition_count"],
        "first_acquisition_at": primary["first_acquisition_at"],
        "last_acquisition_at": primary["last_acquisition_at"],
        "median_acquisition_at": primary["median_acquisition_at"],
        "quality_status": quality,
    }
    for profile, values in profiles.items():
        for key, value in values.items():
            row[f"{profile}_{key}"] = value
    return row


def main():
    parser = argparse.ArgumentParser(description="Run the fixed all-Tabia HLS monthly NDMI DEV acquisition")
    parser.add_argument("--dry-run", action="store_true", help="print the fixed contract without database or Earthdata access")
    args = parser.parse_args()
    start, end = completed_month(datetime.now(timezone.utc))
    if args.dry_run:
        print(json.dumps({
            "source_id": SOURCE_ID,
            "run_scope": "full_development",
            "observation_start": start.isoformat(),
            "observation_end": end.isoformat(),
            "tabia_count": TABIA_COUNT,
            "native_resolution": "30 m HLS surface-reflectance analysis grid",
            "mask_profiles": ["strict", "adjacency_allowed"],
            "checkpoint": "compact DEV statistics after each completed Tabia",
            "schedule": "none",
            "publication": "none",
        }, indent=2))
        return
    run_id = f"nasa-hls-v2-ndmi-full-dev-{start:%Y%m}-spatial-v1"
    root = Path("/data/drought/outputs")
    root.mkdir(parents=True, exist_ok=True)
    base = root / run_id
    checkpoint = base.with_suffix(".partial.csv")
    rows = read_checkpoint(checkpoint)
    completed_ids = {row["tsird_tabia_id"] for row in rows}
    tabias = full_tabias()
    expected_ids = {tabia_id for tabia_id, *_ in tabias}
    if not completed_ids.issubset(expected_ids):
        raise RuntimeError("HLS full-development checkpoint is not a canonical Tabia subset")
    token = earthdata_token()
    for position, (tabia_id, tabia, woreda, geometry) in enumerate(tabias, start=1):
        if tabia_id in completed_ids:
            continue
        rows.append(row_from_profiles(tabia_id, tabia, woreda, summarize_tabia(geometry, start, end, token)))
        write_rows(checkpoint, rows)
        if len(rows) % 10 == 0 or len(rows) == TABIA_COUNT:
            print(json.dumps({"progress": len(rows), "of": TABIA_COUNT}), flush=True)
    if len(rows) != TABIA_COUNT:
        raise RuntimeError("HLS full-development run did not produce all canonical Tabias")
    write_rows(base.with_suffix(".csv"), rows)
    primary_adequate = sum(row["adjacency_allowed_evidence_tier"] == "adequate" for row in rows)
    primary_limited = sum(row["adjacency_allowed_evidence_tier"] == "limited" for row in rows)
    manifest = {
        "run_id": run_id,
        "source_id": SOURCE_ID,
        "run_scope": "full_development",
        "source_product": PRODUCT,
        "status": "development" if primary_adequate + primary_limited else "degraded",
        "observation_start": start.isoformat(),
        "observation_end": end.isoformat(),
        "native_resolution": "30 m HLS surface-reflectance analysis grid",
        "source_collections": list(HLS_COLLECTIONS),
        "validity_mask": "Strict profile excludes Fmask cloud, adjacent cloud/shadow, cloud shadow, snow/ice, water, high aerosol, fill, saturation and zero denominator. Operational profile retains adjacent-to-cloud/shadow pixels but reports them separately; all other exclusions remain.",
        "coverage_definition": "Spatial coverage is the percentage of 30 m equal-area Tabia pixels with at least one valid observation in the completed calendar month. Two-observation coverage is reported separately. It is not observation-weighted and no gap filling or temporal interpolation is used.",
        "min_valid_observation_coverage_pct": MIN_SPATIAL_COVERAGE_PCT,
        "min_limited_observation_coverage_pct": MIN_LIMITED_SPATIAL_COVERAGE_PCT,
        "min_valid_observation_pixels": MIN_VALID_OBSERVATION_PIXELS,
        "min_usable_acquisition_count": MIN_USABLE_ACQUISITIONS,
        "tabia_count": TABIA_COUNT,
        "source_retrieved_at": datetime.now(timezone.utc).isoformat(),
        "processing_version": PROCESSING_VERSION,
        "method": "CMR-STAC discovery; authenticated HLS v2 COG range reads; paired NIR/SWIR1 NDMI per valid observation; per-pixel monthly NDMI medians on a 30 m equal-area grid before Tabia statistics. Strict and adjacency-allowed Fmask profiles are retained. No temporal interpolation or gap filling.",
        "publication_note": "Development-only HLS all-Tabia observed evidence. Not a drought, food-security, priority, forecast, allocation, response, or public release product.",
        "geoinfotech_acknowledgement": "The educational index-selection framing refers to Geoinfotech's Spatial Indices Analysis explainer shared with TSIRD on 2026-10-24. Geoinfotech does not supply HLS data, validate the method, or endorse TSIRD results.",
    }
    base.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    checkpoint.unlink(missing_ok=True)
    print(json.dumps({"run_id": run_id, "status": manifest["status"], "rows": len(rows),
                      "adequate_primary_rows": primary_adequate, "limited_primary_rows": primary_limited}, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # Do not expose Earthdata credentials, source URLs, raw provider output, or geometry.
        raise SystemExit(f"HLS full-development NDMI failed: {type(exc).__name__}: {str(exc)[:240]}")
