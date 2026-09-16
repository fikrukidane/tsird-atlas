"""Perform one bounded CDS seasonal-forecast access test.

The probe is deliberately not an outlook loader.  It requests a tiny,
temporary precipitation subset only to confirm account access and accepted
dataset terms, records no credentials or forecast values, then removes the
test file.  A future loader must retrieve matched hindcasts and validate skill
before it may publish any probability map.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import cdsapi


DATASET = "seasonal-monthly-single-levels"
TEMPORARY_TARGET = Path("/data/drought/cache/c3s-seasonal-access-probe.grib")
RECEIPT = Path("/data/drought/outputs/c3s-seasonal-access-probe.json")

# One small ECMWF monthly-mean precipitation subset. It is only an account and
# data-access check; its footprint and one-month lead make it unusable as a
# displayed outlook or a persisted evidence item.
REQUEST = {
    "originating_centre": "ecmwf",
    "system": "51",
    "variable": ["total_precipitation"],
    "product_type": ["monthly_mean"],
    "year": ["2026"],
    "month": ["08"],
    "leadtime_month": ["1"],
    "area": [14.5, 38.5, 14.0, 39.0],
    "data_format": "grib",
}


def main() -> None:
    api_url = os.environ.get("C3S_CDS_API_URL", "").strip()
    api_key = os.environ.get("C3S_CDS_API_KEY", "").strip()
    result: dict[str, object]
    try:
        if not api_url or not api_key:
            raise RuntimeError("runner-only CDS API configuration is missing")
        TEMPORARY_TARGET.parent.mkdir(parents=True, exist_ok=True)
        client = cdsapi.Client(url=api_url, key=api_key, quiet=True)
        client.retrieve(DATASET, REQUEST, str(TEMPORARY_TARGET))
        byte_count = TEMPORARY_TARGET.stat().st_size
        if byte_count <= 0:
            raise RuntimeError("CDS returned an empty access-test file")
        result = {
            "status": "passed",
            "reason": "CDS account authenticated and the seasonal monthly precipitation dataset accepted one bounded request.",
            "dataset": DATASET,
            "request_scope": "temporary 0.5 degree test window; August 2026 initialization; one-month lead",
            "temporary_byte_count": byte_count,
            "retained_output": False,
            "next_gate": "Retrieve matched hindcasts, assess Tigray-relevant skill, and define a probability method before any outlook artifact is loaded.",
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as exc:
        response = getattr(exc, "response", None)
        http_status = getattr(response, "status_code", None)
        if http_status is None:
            http_status = getattr(exc, "code", None)
        result = {
            "status": "unavailable",
            "reason": f"C3S seasonal access probe failed: {type(exc).__name__}",
            "dataset": DATASET,
            "http_status": http_status if isinstance(http_status, int) else None,
            "retained_output": False,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        }
    finally:
        try:
            TEMPORARY_TARGET.unlink(missing_ok=True)
        except OSError:
            pass
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
