"""Bounded technical C3S-versus-CHIRPS seasonal-skill pilot.

The pilot evaluates one explicitly labelled rainfall case: ECMWF System 51,
August initialisation, lead month 1 (August rainfall), 1993--2016.  It uses
unweighted Tigray-bounds means only, retains annual summaries and Brier-score
diagnostics, and deletes every raw C3S GRIB and global CHIRPS GeoTIFF.

It is a development diagnostic, not a Woreda/Tabia forecast, a calibrated
provider product, or a public Outlook publication.
"""
from __future__ import annotations

import csv
import argparse
import json
import math
import os
from calendar import monthrange
from datetime import datetime, timezone
from pathlib import Path

import cdsapi
import numpy as np
import rasterio

from chirps_tabia_summary import chirps_url, download_source, fetch_bounds


DATASET = "seasonal-monthly-single-levels"
YEARS = tuple(range(1993, 2017))
CASES = {
    "august-lead-1": {"initialization_month": 8, "lead_month": 1, "target_month": 8},
    "august-lead-2": {"initialization_month": 7, "lead_month": 2, "target_month": 8},
    "august-lead-3": {"initialization_month": 6, "lead_month": 3, "target_month": 8},
}
CACHE = Path("/data/drought/cache/c3s-skill-pilot")
OUTPUT = Path("/data/drought/outputs")


def c3s_request(year: int, bounds: tuple[float, float, float, float], case: dict[str, int]) -> dict[str, object]:
    left, bottom, right, top = bounds
    return {
        "originating_centre": "ecmwf", "system": "51",
        "variable": ["total_precipitation"], "product_type": ["monthly_mean"],
        "year": [str(year)], "month": [f"{case['initialization_month']:02d}"],
        "leadtime_month": [str(case["lead_month"])], "area": [top, right, bottom, left],
        "data_format": "grib",
    }


def valid_mean(values: np.ndarray) -> float:
    array = np.ma.asarray(values, dtype="float64").compressed()
    array = array[np.isfinite(array)]
    if not array.size:
        raise RuntimeError("source subset had no finite rainfall cells")
    return float(array.mean())


def c3s_ensemble_mm(client: cdsapi.Client, year: int, bounds: tuple[float, float, float, float], case: dict[str, int]) -> list[float]:
    target = CACHE / f"ecmwf51-{year}-{case['initialization_month']:02d}-lead{case['lead_month']}.grib"
    try:
        client.retrieve(DATASET, c3s_request(year, bounds, case), str(target))
        with rasterio.open(target) as source:
            if source.count < 2 or source.crs is None:
                raise RuntimeError("C3S response did not contain a readable ensemble raster")
            # C3S seasonal monthly total precipitation is supplied as a rate.
            # Convert each member's spatial mean to its August monthly depth.
            factor = monthrange(year, case["target_month"])[1] * 86400 * 1000
            return [valid_mean(source.read(index, masked=True)) * factor for index in range(1, source.count + 1)]
    finally:
        target.unlink(missing_ok=True)


def chirps_mm(year: int, bounds: tuple[float, float, float, float], target_month: int) -> float:
    for source, _receipt in download_source(chirps_url(year, target_month), bounds):
        with rasterio.open(source) as raster:
            window = raster.window(*bounds).round_offsets().round_lengths()
            return valid_mean(raster.read(1, window=window, masked=True))
    raise RuntimeError("CHIRPS source download yielded no raster")


def category(value: float, lower: float, upper: float) -> str:
    return "below" if value < lower else "above" if value > upper else "near"


def score(records: list[dict[str, object]]) -> dict[str, object]:
    per_category: dict[str, list[tuple[float, int, float]]] = {name: [] for name in ("below", "near", "above")}
    for record in records:
        others = [item for item in records if item["year"] != record["year"]]
        observed_thresholds = np.quantile([float(item["observed_chirps_mm"]) for item in others], [1 / 3, 2 / 3])
        model_thresholds = np.quantile([float(item["forecast_ensemble_mean_mm"]) for item in others], [1 / 3, 2 / 3])
        members = [float(item) for item in record["forecast_members_mm"]]
        observed_category = category(float(record["observed_chirps_mm"]), *observed_thresholds)
        for name in per_category:
            if name == "below": probability = sum(item < model_thresholds[0] for item in members) / len(members)
            elif name == "above": probability = sum(item > model_thresholds[1] for item in members) / len(members)
            else: probability = sum(model_thresholds[0] <= item <= model_thresholds[1] for item in members) / len(members)
            climatology = sum(category(float(item["observed_chirps_mm"]), *observed_thresholds) == name for item in others) / len(others)
            per_category[name].append((probability, int(observed_category == name), climatology))
    result: dict[str, object] = {}
    for name, values in per_category.items():
        brier = sum((probability - event) ** 2 for probability, event, _ in values) / len(values)
        reference = sum((climatology - event) ** 2 for _, event, climatology in values) / len(values)
        result[name] = {"brier_score": round(brier, 4), "climatology_brier_score": round(reference, 4),
                        "brier_skill_score": round(1 - brier / reference, 4) if reference > 0 else None}
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=tuple(CASES), default="august-lead-1")
    selected_case = parser.parse_args().case
    case = CASES[selected_case]
    url = os.environ.get("C3S_CDS_API_URL", "").strip()
    key = os.environ.get("C3S_CDS_API_KEY", "").strip()
    if not url or not key:
        raise RuntimeError("runner-only CDS API configuration is missing")
    CACHE.mkdir(parents=True, exist_ok=True); OUTPUT.mkdir(parents=True, exist_ok=True)
    bounds = fetch_bounds()
    client = cdsapi.Client(url=url, key=key, quiet=True)
    records: list[dict[str, object]] = []
    for year in YEARS:
        members = c3s_ensemble_mm(client, year, bounds, case)
        observed = chirps_mm(year, bounds, case["target_month"])
        records.append({"year": year, "observed_chirps_mm": round(observed, 3),
                        "forecast_ensemble_mean_mm": round(float(np.mean(members)), 3),
                        "forecast_ensemble_spread_mm": round(float(np.std(members)), 3),
                        "forecast_members_mm": [round(item, 5) for item in members]})
    metrics = score(records)
    summary = {
        "status": "development_skill_pilot", "provider": "Copernicus C3S", "dataset": DATASET,
        "system": "ECMWF 51", "observed_reference": "CHIRPS v3 monthly", "years": [YEARS[0], YEARS[-1]],
        "case": f"August rainfall target; {case['lead_month']}-month lead; {case['initialization_month']:02d} initialization", "geography": "unweighted Tigray-bounds mean",
        "target_month": case["target_month"], "initialization_month": case["initialization_month"],
        "lead_month": case["lead_month"],
        "forecast_member_count": len(records[0]["forecast_members_mm"]), "metric": "leave-one-year-out tercile Brier skill score",
        "metrics": metrics, "limitations": ["technical regional pilot only", "not Woreda or Tabia skill", "not a calibrated or provider-issued probability product", "not for public Outlook publication"],
        "raw_rasters_retained": False, "created_at": datetime.now(timezone.utc).isoformat(),
    }
    stem = f"c3s-skill-pilot-ecmwf51-{selected_case.replace('-lead-', '-lead')}"
    csv_path = OUTPUT / f"{stem}.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=("year", "observed_chirps_mm", "forecast_ensemble_mean_mm", "forecast_ensemble_spread_mm"))
        writer.writeheader(); writer.writerows([{key: value for key, value in row.items() if key != "forecast_members_mm"} for row in records])
    (OUTPUT / f"{stem}.json").write_text(json.dumps({**summary, "records": records}, indent=2), encoding="utf-8")
    print(json.dumps({**summary, "record_count": len(records), "summary_path": str(OUTPUT / f"{stem}.json")}))


if __name__ == "__main__":
    main()
