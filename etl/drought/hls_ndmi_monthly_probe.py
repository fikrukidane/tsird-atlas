"""Discover one eligible HLS monthly NDMI period without reading HLS COGs.

The probe is intentionally cheap: it checks the completed calendar month,
confirms that CMR-STAC indexes HLS L30/S30 items over Tigray, and compares the
period with the latest loaded full-development artifact.  It never emits a
token, provider URL, scene ID, geometry, or raw provider response.
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import psycopg2

from hls_ndmi_monthly_pilot import completed_month, dsn, fetch_tabias_and_bounds, stac_items

OUTPUT = Path("/data/drought/outputs/hls-ndmi-monthly-probe.json")


def regional_polygon(bounds):
    west, south, east, north = bounds
    return {"type": "Polygon", "coordinates": [[[west, south], [east, south], [east, north], [west, north], [west, south]]]}


def retained_full_run(start, end):
    with psycopg2.connect(dsn()) as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT r.run_id, r.status, count(t.tsird_tabia_id)
                 FROM tsird.drought_hls_ndmi_run r
                 LEFT JOIN tsird.drought_tabia_hls_ndmi t USING (run_id)
                WHERE r.run_scope = 'full_development'
                  AND r.observation_start = %s AND r.observation_end = %s
                GROUP BY r.run_id, r.status
                ORDER BY r.created_at DESC LIMIT 1""",
            (start, end),
        )
        return cur.fetchone()


def main():
    checked_at = datetime.now(timezone.utc)
    start, end = completed_month(checked_at)
    receipt = {
        "workflow": "hls-ndmi-monthly-probe",
        "checked_at": checked_at.isoformat(),
        "observation_start": start.isoformat(),
        "observation_end": end.isoformat(),
        "status": "unavailable",
    }
    if not os.environ.get("EARTHDATA_TOKEN", "").strip():
        receipt["reason"] = "EARTHDATA_TOKEN is not configured in the local development runner"
    else:
        _, bounds = fetch_tabias_and_bounds()
        items = stac_items(regional_polygon(bounds), start, end)
        if not items:
            receipt.update(status="degraded", reason="CMR-STAC has no HLS L30/S30 item for the eligible completed month")
        else:
            retained = retained_full_run(start, end)
            if retained and retained[1] in {"development", "degraded"} and retained[2] == 748:
                receipt.update(status="current", run_id=retained[0], reason="eligible completed HLS month is already retained as a 748-Tabia artifact")
            else:
                receipt.update(status="ready", reason="CMR-STAC indexes the eligible completed HLS month and no 748-Tabia artifact is retained")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        receipt = {
            "workflow": "hls-ndmi-monthly-probe",
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "status": "unavailable",
            "reason": f"HLS monthly source discovery failed: {type(exc).__name__}",
        }
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
        print(json.dumps(receipt, indent=2))
