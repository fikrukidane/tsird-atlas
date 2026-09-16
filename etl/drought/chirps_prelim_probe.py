"""Probe the official CHIRPS preliminary African pentad feed.

This is an acquisition/freshness gate for the future near-real-time workflow.
It deliberately does not publish a Tabia classification or replace the final
monthly artifact: the preliminary product needs its own reviewed aggregation
and disclosure method first.
"""
import hashlib
import json
import re
import shutil
import tempfile
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

import rasterio

INDEX_URL = "https://data.chc.ucsb.edu/products/CHIRPS/v3.0/prelim/pentads/africa/tifs/"
FILE_URL = INDEX_URL + "chirps-v3.0.{year}.{month:02d}.{pentad}.tif"
MAX_AGE_DAYS = 10
PATTERN = re.compile(r"chirps-v3\.0\.(\d{4})\.(\d{2})\.([1-6])\.tif")


def pentad_end(year, month, pentad):
    if pentad < 6:
        return date(year, month, pentad * 5)
    # The sixth period runs from day 26 through the end of its month.
    if month == 12:
        return date(year + 1, 1, 1) - date.resolution
    return date(year, month + 1, 1) - date.resolution


def main():
    root = Path("/data/drought")
    output = root / "outputs"
    output.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(INDEX_URL, headers={"User-Agent": "TSIRD-Atlas-development/1.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        listing = response.read().decode("utf-8", errors="replace")
    candidates = sorted((tuple(map(int, match.groups())) for match in PATTERN.finditer(listing)))
    if not candidates:
        raise RuntimeError("official CHIRPS preliminary index contained no recognised pentad files")
    year, month, pentad = candidates[-1]
    latest_pentad = {"year": year, "month": month, "pentad": pentad}
    already_summarized = False
    for manifest_path in output.glob("chirps-v3-prelim-*.manifest.json"):
        if manifest_path.name.endswith(".prelim-baseline.manifest.json"):
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            selected = manifest.get("selected_pentads", [])
            already_summarized = bool(
                manifest.get("status") == "development" and selected and selected[-1] == latest_pentad
            )
        except (OSError, json.JSONDecodeError):
            already_summarized = False
        if already_summarized:
            break
    source_url = FILE_URL.format(year=year, month=month, pentad=pentad)
    with tempfile.TemporaryDirectory() as temporary:
        path = Path(temporary) / "pentad.tif"
        source_request = urllib.request.Request(source_url, headers={"User-Agent": "TSIRD-Atlas-development/1.0"})
        with urllib.request.urlopen(source_request, timeout=180) as response, path.open("wb") as handle:
            shutil.copyfileobj(response, handle)
            headers = response.headers
            http_status = getattr(response, "status", 200)
        if path.stat().st_size < 100_000:
            raise RuntimeError("official preliminary file was implausibly small")
        with rasterio.open(path) as raster:
            if raster.count != 1 or raster.crs is None or raster.crs.to_epsg() != 4326:
                raise RuntimeError("official preliminary file has an unexpected raster structure")
        observed_end = pentad_end(year, month, pentad)
        age_days = (datetime.now(timezone.utc).date() - observed_end).days
        if age_days > MAX_AGE_DAYS:
            status, reason = "degraded", "preliminary source exceeds 10-day freshness threshold"
        elif already_summarized:
            status, reason = "current", "latest preliminary pentad is already represented by a valid local six-pentad summary"
        else:
            status, reason = "ready", "fresh preliminary pentad has no matching local six-pentad summary"
        result = {
            "workflow": "chirps-preliminary-pentad-probe",
            "status": status,
            "publication_action": "none",
            "reason": reason,
            "source_product": "CHIRPS v3 preliminary pentad, Africa subset",
            "native_resolution": "0.05 degree grid",
            "source_url": source_url,
            "period": {"year": year, "month": month, "pentad": pentad, "end_date": observed_end.isoformat()},
            "already_summarized": already_summarized,
            "age_days": age_days,
            "freshness_threshold_days": MAX_AGE_DAYS,
            "receipt": {"http_status": http_status, "byte_count": path.stat().st_size,
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                        "etag": headers.get("ETag"), "last_modified": headers.get("Last-Modified"),
                        "retrieved_at": datetime.now(timezone.utc).isoformat()},
        }
    receipt_path = output / "chirps-v3-preliminary-pentad-probe.json"
    receipt_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
