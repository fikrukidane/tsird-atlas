"""Inspect the official ICPAC seasonal-outlook catalogue without ingesting data.

This deliberately does not parse forecast map colours, infer probabilities, or
download a seasonal raster.  It creates a small redacted receipt so a reviewed
operator can decide whether an individual provider asset is sufficiently
machine-readable to enter the seasonal-outlook loader.
"""
from __future__ import annotations

import json
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


CATALOGUE_URL = "https://www.icpac.net/seasonal-forecast/"
RECEIPT = Path("/data/drought/outputs/igad-icpac-seasonal-probe.json")


def main() -> None:
    request = urllib.request.Request(CATALOGUE_URL, headers={"User-Agent": "TSIRD-Atlas-development-probe/1.0"})
    status_code = None
    body = ""
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            status_code = response.status
            body = response.read(512_000).decode("utf-8", errors="replace")
        seasonal_labels = sorted(set(re.findall(r"\b(?:JFM|FMA|MAM|AMJ|MJJ|JJA|JAS|ASO|SON|OND|NDJ|DJF)\s*-\s*20\d{2}\b", body)))
        result = {
            "status": "manual_asset_review_required",
            "reason": "Catalogue reachable; no forecast grid/vector was ingested or inferred from page imagery.",
            "catalogue_url": CATALOGUE_URL,
            "http_status": status_code,
            "season_labels_seen": seasonal_labels[:24],
            "next_gate": "Register one official machine-readable provider asset with issue date, valid period, probabilities, licence, and native geography before loading.",
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as exc:
        result = {
            "status": "unavailable",
            "reason": f"ICPAC catalogue probe failed: {type(exc).__name__}",
            "catalogue_url": CATALOGUE_URL,
            "http_status": status_code,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        }
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
