"""Probe FEWS NET's documented FDW endpoint without ingesting or publishing data.

FEWS NET food-security classifications are a separate decision-context source;
they are not a seasonal-rainfall probability forecast and must never be
downscaled to TSIRD Tabias.  This probe reads only a one-record Ethiopia
near-term query, retains no provider payload, and writes a small redacted
receipt for a later human data-contract review.
"""
from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


FDW_URL = (
    "https://fdw.fews.net/api/ipcphase.json?"
    "country_code=ET&scenario=ML1&page_size=1"
)
RECEIPT = Path("/data/drought/outputs/fews-net-fdw-food-security-probe.json")


def main() -> None:
    request = urllib.request.Request(
        FDW_URL,
        headers={"User-Agent": "TSIRD-Atlas-development-probe/1.0"},
    )
    status_code = None
    content_type = None
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            status_code = response.status
            content_type = response.headers.get_content_type()
            payload = json.loads(response.read(64_000).decode("utf-8"))
        result_count = payload.get("count") if isinstance(payload, dict) else None
        result = {
            "status": "manual_data_contract_review_required",
            "reason": (
                "FEWS NET FDW endpoint responded; no classification, geometry, "
                "or provider payload was retained, joined, or published."
            ),
            "source": "FEWS NET Food Data Warehouse",
            "endpoint_kind": "Ethiopia near-term IPC phase (ML1) metadata probe",
            "http_status": status_code,
            "content_type": content_type,
            "result_count": result_count if isinstance(result_count, int) else None,
            "next_gate": (
                "Review permitted access and data-use terms; confirm the exact "
                "issue date, valid period, scenario, geography, and TSIRD "
                "crosswalk before any contextual layer is loaded. Do not create "
                "a Tabia food-security classification."
            ),
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as exc:
        result = {
            "status": "unavailable",
            "reason": f"FEWS NET FDW metadata probe failed: {type(exc).__name__}",
            "source": "FEWS NET Food Data Warehouse",
            "endpoint_kind": "Ethiopia near-term IPC phase (ML1) metadata probe",
            "http_status": status_code,
            "content_type": content_type,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        }
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
