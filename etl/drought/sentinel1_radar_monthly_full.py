"""Build one resumable all-Tabia Sentinel-1 radar artifact for development.

It retains compact zonal statistics only.  Backscatter is influenced by terrain,
vegetation structure and acquisition geometry, so it is never labelled as soil
moisture, flood, drought or a decision classification.
"""
import csv
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from cdse_ndvi_tabia_summary import access_token, fetch_tabias_and_bounds
from sentinel2_ndmi_statistical_full import full_tabias
from sentinel2_ndmi_statistical_pilot import STATISTICS_CRS, STATISTICS_URL, settings
from sentinel1_radar_monthly_probe import SOURCE_ID, completed_month, fingerprint, scenes

PROCESSING_VERSION = "tsird-sentinel1-radar-monthly-dev.v1"
TABIA_COUNT = 748
ANALYTICAL_RESOLUTION_METERS = 30
MIN_VALID_COVERAGE_PCT = 70
MIN_USABLE_SCENE_COUNT = 2
REQUEST_INTERVAL_SECONDS = 4
MAX_RATE_LIMIT_RETRIES = 6


def evalscript():
    return '''//VERSION=3
function setup() {
  return {input:["VV", "VH", "dataMask"], mosaicking:"ORBIT",
    output:[{id:"vv", bands:1, sampleType:"FLOAT32"}, {id:"vh", bands:1, sampleType:"FLOAT32"}, {id:"dataMask", bands:1, sampleType:"UINT8"}]};
}
function median(values) { values.sort(function(a,b){return a-b;}); var n=values.length; return n % 2 ? values[(n-1)/2] : (values[n/2-1]+values[n/2])/2; }
function evaluatePixel(samples) {
  var vv=[], vh=[];
  for (var i=0; i<samples.length; i++) { var s=samples[i]; if (s.dataMask===1 && s.VV>0 && s.VH>0) { vv.push(10*Math.log(s.VV)/Math.LN10); vh.push(10*Math.log(s.VH)/Math.LN10); } }
  if (!vv.length) return {vv:[0], vh:[0], dataMask:[0]};
  return {vv:[median(vv)], vh:[median(vh)], dataMask:[1]};
}'''


def request_body(geometry, start, end):
    return {"input": {"bounds": {"geometry": geometry, "properties": {"crs": STATISTICS_CRS}},
             "data": [{"type": "sentinel-1-grd", "dataFilter": {"timeRange": {"from": start.isoformat().replace("+00:00", "Z"), "to": end.isoformat().replace("+00:00", "Z")}, "acquisitionMode": "IW", "polarization": "DV", "orbitDirection": "DESCENDING"}, "processing": {"orthorectify": True, "backCoeff": "GAMMA0_TERRAIN", "speckleFilter": {"type": "LEE", "windowSizeX": 3, "windowSizeY": 3}}}]},
            "aggregation": {"timeRange": {"from": start.isoformat().replace("+00:00", "Z"), "to": end.isoformat().replace("+00:00", "Z")}, "aggregationInterval": {"of": "P1M"}, "evalscript": evalscript(), "resx": ANALYTICAL_RESOLUTION_METERS, "resy": ANALYTICAL_RESOLUTION_METERS},
            "calculations": {"vv": {"statistics": {"default": {"percentiles": {"k": [50]}}}}, "vh": {"statistics": {"default": {"percentiles": {"k": [50]}}}}}}


def _stats(token_state, geometry, start, end):
    retries = refreshes = 0
    while True:
        request = Request(STATISTICS_URL, data=json.dumps(request_body(geometry, start, end)).encode("utf-8"), method="POST", headers={"Authorization": f"Bearer {token_state['token']}", "Content-Type": "application/json", "Accept": "application/json"})
        try:
            with urlopen(request, timeout=150) as response: payload = json.loads(response.read().decode("utf-8"))
            break
        except HTTPError as exc:
            if exc.code == 401 and refreshes < 3:
                token_state["token"] = access_token(settings()); refreshes += 1; continue
            if exc.code != 429 or retries >= MAX_RATE_LIMIT_RETRIES: raise
            retries += 1; time.sleep(min(120, max(REQUEST_INTERVAL_SECONDS, float(exc.headers.get("Retry-After", "0")) / 1000)))
    data = payload.get("data") or []
    if len(data) != 1: raise RuntimeError("Sentinel-1 statistics response did not contain one monthly interval")
    try:
        outputs = data[0]["outputs"]
        vv = outputs["vv"]["bands"]["B0"]["stats"]
        vh = outputs["vh"]["bands"]["B0"]["stats"]
        return vv, vh
    except (KeyError, TypeError) as exc:
        raise RuntimeError("Sentinel-1 statistics response omitted VV/VH statistics") from exc


def _row(token_state, geometry, start, end, scene_count):
    vv, vh = _stats(token_state, geometry, start, end)
    total = int(vv.get("sampleCount") or 0); missing = int(vv.get("noDataCount") or 0); valid = max(0, total - missing)
    coverage = round(100 * valid / total, 1) if total else 0.0
    status = "ok" if coverage >= MIN_VALID_COVERAGE_PCT and scene_count >= MIN_USABLE_SCENE_COUNT else ("limited_coverage" if valid else "insufficient_evidence")
    def median(stats):
        percentiles = stats.get("percentiles") or {}
        value = percentiles.get("50.0", percentiles.get("50"))
        if value is None:
            raise RuntimeError("Sentinel-1 statistics response omitted the requested 50th percentile")
        return round(float(value), 3)

    return {"vv_db_median": median(vv) if valid else None,
            "vh_db_median": median(vh) if valid else None,
            "valid_pixel_count": valid, "grid_cell_count": total, "coverage_pct": coverage,
            "contributing_scene_count": scene_count, "quality_status": status}


def main():
    start, end = completed_month(datetime.now(timezone.utc)); tabias = full_tabias(); _, bounds = fetch_tabias_and_bounds()
    items = scenes(bounds, start, end)
    if len(items) < MIN_USABLE_SCENE_COUNT: raise RuntimeError("Sentinel-1 eligible month does not have enough IW dual-polarisation scenes")
    run_id = f"cdse-sentinel1-grd-monthly-dev-{start:%Y%m}"
    root = Path("/data/drought/outputs"); root.mkdir(parents=True, exist_ok=True); base = root / run_id; checkpoint = base.with_suffix(".partial.csv")
    rows = []
    if checkpoint.exists():
        with checkpoint.open(encoding="utf-8") as handle: rows = list(csv.DictReader(handle))
    seen = {row["tsird_tabia_id"] for row in rows}
    if len(rows) > TABIA_COUNT or any(not key.startswith("tsird-tabia-v1-") for key in seen): raise RuntimeError("Sentinel-1 checkpoint is invalid")
    token_state = {"token": access_token(settings())}
    for position, (tabia_id, tabia, woreda, geometry) in enumerate(tabias, start=1):
        if tabia_id in seen: continue
        row = {"tsird_tabia_id": tabia_id, "tabia_name_en": tabia, "woreda_name_en": woreda}
        row.update(_row(token_state, geometry, start, end, len(items))); rows.append(row)
        with checkpoint.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=rows[0]); writer.writeheader(); writer.writerows(rows)
        if position % 25 == 0: print(json.dumps({"progress": len(rows), "of": TABIA_COUNT}), flush=True)
        if position < TABIA_COUNT: time.sleep(REQUEST_INTERVAL_SECONDS)
    if len(rows) != TABIA_COUNT: raise RuntimeError("Sentinel-1 run did not produce all canonical Tabias")
    with base.with_suffix(".csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0]); writer.writeheader(); writer.writerows(rows)
    manifest = {"run_id": run_id, "source_id": SOURCE_ID, "status": "development" if any(row["quality_status"] == "ok" for row in rows) else "degraded",
      "observation_start": start.isoformat(), "observation_end": end.isoformat(), "native_resolution": "30 m analytical grid; Sentinel-1 GRD IW source at 10 m pixel spacing", "orbit_direction": "descending only", "polarizations": ["VV", "VH"], "terrain_correction": "gamma0 terrain correction with orthorectification and 3×3 Lee speckle filter", "source_scene_count": len(items), "source_fingerprint": fingerprint(items), "min_valid_coverage_pct": MIN_VALID_COVERAGE_PCT, "min_usable_scene_count": MIN_USABLE_SCENE_COUNT, "tabia_count": TABIA_COUNT, "source_retrieved_at": datetime.now(timezone.utc).isoformat(), "processing_version": PROCESSING_VERSION,
      "method": "CDSE Sentinel Hub Statistical API; completed-calendar-month Sentinel-1 GRD IW descending dual-VV/VH observations, terrain-corrected gamma0 backscatter transformed to dB, temporal median over valid observations, then 30 m Tabia zonal summaries. No interpolation or flood/drought threshold is applied.",
      "publication_note": "Development-only all-weather radar evidence. Radar backscatter is influenced by terrain, vegetation structure, roughness and geometry. It is not a soil-moisture measurement, drought class, flood declaration, food-security classification, forecast, allocation or response trigger."}
    base.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8"); checkpoint.unlink(missing_ok=True)
    print(json.dumps({"run_id": run_id, "status": manifest["status"], "rows": len(rows), "scene_count": len(items)}))


if __name__ == "__main__": main()
