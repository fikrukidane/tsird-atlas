"""Verify availability of one matched C3S seasonal hindcast, without retaining data.

This is a technical availability gate, not a forecast-skill assessment or an
Outlook loader.  It uses the same ECMWF System 51 and small Tigray test window
as the access probe, but requests a retrospective 2016 initialization.  The
temporary GRIB is removed whether the request passes or fails.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import cdsapi
import rasterio


DATASET = "seasonal-monthly-single-levels"
TEMPORARY_TARGET = Path("/data/drought/cache/c3s-seasonal-hindcast-probe.grib")
RECEIPT = Path("/data/drought/outputs/c3s-seasonal-hindcast-probe.json")
REQUEST = {
    "originating_centre": "ecmwf",
    "system": "51",
    "variable": ["total_precipitation"],
    "product_type": ["monthly_mean"],
    "year": ["2016"],
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
        cdsapi.Client(url=api_url, key=api_key, quiet=True).retrieve(
            DATASET, REQUEST, str(TEMPORARY_TARGET)
        )
        byte_count = TEMPORARY_TARGET.stat().st_size
        if byte_count <= 0:
            raise RuntimeError("CDS returned an empty hindcast-test file")
        with rasterio.open(TEMPORARY_TARGET) as source:
            if source.count < 1 or source.crs is None:
                raise RuntimeError("CDS hindcast file is not a readable geospatial raster")
            tags = source.tags()
            band_tags = source.tags(1)
            raster_contract = {
                "band_count": source.count,
                "crs": source.crs.to_string(),
                "grid_width": source.width,
                "grid_height": source.height,
                "units": band_tags.get("GRIB_UNIT") or band_tags.get("units") or tags.get("GRIB_UNIT") or tags.get("units") or "not supplied by raster driver",
                "parameter": band_tags.get("GRIB_ELEMENT") or tags.get("GRIB_ELEMENT") or "not supplied by raster driver",
            }
        result = {
            "status": "passed",
            "reason": "One matched ECMWF System 51 seasonal precipitation hindcast request completed.",
            "dataset": DATASET,
            "request_scope": "temporary 0.5 degree test window; August 2016 initialization; one-month lead",
            "temporary_byte_count": byte_count,
            "raster_contract": raster_contract,
            "retained_output": False,
            "next_gate": "Retrieve a reviewed matched hindcast sample and compare it with an observed reference before any forecast skill or probability method is claimed.",
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as exc:
        response = getattr(exc, "response", None)
        http_status = getattr(response, "status_code", None)
        if http_status is None:
            http_status = getattr(exc, "code", None)
        result = {
            "status": "unavailable",
            "reason": f"C3S seasonal hindcast probe failed: {type(exc).__name__}",
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
