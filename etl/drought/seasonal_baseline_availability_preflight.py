"""Read-only provider-availability preflight for a possible seasonal baseline.

The result is deliberately a capability check, not an acquisition plan.  It
requests catalogue metadata only: no raster pixels are requested, retained, or
processed, and it neither calculates an anomaly nor changes a priority replay.
"""
import json
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

from cdse_ndvi_tabia_summary import CATALOG_SEARCH_URL, access_token, cdse_settings, fetch_tabias_and_bounds
from wapor_tabia_summary import AETI_MAPSET, T_MAPSET, catalogue_items, parse_period


START_YEAR = 2016
END_YEAR = 2025


def timestamp(feature):
    properties = feature.get("properties") or {}
    return properties.get("datetime") or properties.get("end_datetime") or properties.get("start_datetime")


def cdse_months(token, collection, bounds):
    by_month = defaultdict(set)
    for year in range(START_YEAR, END_YEAR + 1):
        for month in range(1, 13):
            next_month = 1 if month == 12 else month + 1
            next_year = year + 1 if month == 12 else year
            query = {
                "bbox": bounds,
                "datetime": f"{year}-{month:02d}-01T00:00:00Z/{next_year}-{next_month:02d}-01T00:00:00Z",
                "collections": [f"byoc-{collection}"], "limit": 100,
                "fields": {"include": ["properties.datetime", "properties.start_datetime", "properties.end_datetime"]},
            }
            request = Request(CATALOG_SEARCH_URL, data=json.dumps(query).encode(), method="POST", headers={
                "Authorization": f"Bearer {token}", "Content-Type": "application/json", "Accept": "application/geo+json"})
            with urlopen(request, timeout=60) as response:
                features = json.loads(response.read().decode()).get("features") or []
            if any(timestamp(item) for item in features):
                by_month[month].add(year)
    return by_month


def wapor_months():
    transpiration = {item.get("code"): item for item in catalogue_items(T_MAPSET) if parse_period(item.get("code"))}
    aeti = {item.get("code"): item for item in catalogue_items(AETI_MAPSET) if parse_period(item.get("code"))}
    by_month = defaultdict(set)
    for code, item in transpiration.items():
        period = parse_period(code)
        if not period or not item.get("downloadUrl"):
            continue
        suffix = code.split(f"WAPOR-3.{T_MAPSET}.", 1)[-1]
        matching = aeti.get(f"WAPOR-3.{AETI_MAPSET}.{suffix}")
        if matching and matching.get("downloadUrl") and START_YEAR <= period[0].year <= END_YEAR:
            by_month[period[0].month].add(period[0].year)
    return by_month


def report(source, years_by_month):
    expected = set(range(START_YEAR, END_YEAR + 1))
    months = []
    for month in range(1, 13):
        years = sorted(years_by_month.get(month, set()))
        months.append({"calendar_month": month, "years_available": years,
                       "years_missing": sorted(expected - set(years)), "complete": set(years) == expected})
    complete = all(item["complete"] for item in months)
    return {"source_id": source, "candidate_period": f"{START_YEAR}-{END_YEAR}",
            "status": "candidate_coverage_complete" if complete else "candidate_coverage_incomplete",
            "calendar_months": months}


def main():
    result = {"schema_version": "tsird-seasonal-baseline-availability.v1", "development_only": True,
              "read_only": True, "candidate_period": f"{START_YEAR}-{END_YEAR}",
              "retrieved_at": datetime.now(timezone.utc).isoformat(),
              "purpose": "Metadata-only availability check for a possible future same-calendar-month baseline.",
              "not_an_acquisition": "No raster pixels were downloaded or retained; no baseline, anomaly, or priority class was calculated."}
    try:
        settings, collection = cdse_settings()
        _, bounds = fetch_tabias_and_bounds()
        result["ndvi"] = report("cdse-clms-ndvi-v3", cdse_months(access_token(settings), collection, bounds))
        result["wapor"] = report("fao-wapor-v3", wapor_months())
        statuses = [result["ndvi"]["status"], result["wapor"]["status"]]
        result["status"] = "review_required" if all(value == "candidate_coverage_complete" for value in statuses) else "incomplete"
        result["next_step"] = "Review the candidate period, source revisions, seasonal method, quality rule, and access terms before any historical acquisition."
    except Exception as exc:
        result.update({"status": "unavailable", "reason": f"Metadata-only availability check failed: {type(exc).__name__}"})
    output = Path("/data/drought/outputs")
    output.mkdir(parents=True, exist_ok=True)
    (output / "seasonal-baseline-availability-preflight.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result))
    return 0 if result["status"] != "unavailable" else 1


if __name__ == "__main__":
    raise SystemExit(main())
