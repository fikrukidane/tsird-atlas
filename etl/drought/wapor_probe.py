"""Metadata-only availability probe for the FAO WaPOR v3 T/AETI source pair."""
import json
from datetime import datetime, timezone
from pathlib import Path

from wapor_tabia_summary import AETI_MAPSET, T_MAPSET, latest_pair


def main():
    period_start, period_end, transpiration, aeti = latest_pair()
    age = (datetime.now(timezone.utc).date() - period_end).days
    run_id = f"fao-wapor-v3-l2-{period_start:%Y%m}-d{((period_start.day - 1) // 10) + 1}"
    manifest_path = Path("/data/drought/outputs") / f"{run_id}.manifest.json"
    already_published = False
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            already_published = (
                manifest.get("run_id") == run_id
                and manifest.get("source_period_start") == period_start.isoformat()
                and manifest.get("source_period_end") == period_end.isoformat()
            )
        except (OSError, json.JSONDecodeError):
            # A malformed receipt must be reviewed by reprocessing rather than
            # being mistaken for a valid current artifact.
            already_published = False
    if age > 25:
        status, reason = "degraded", "latest provider dekad exceeds the 25-day freshness threshold"
    elif already_published:
        status, reason = "current", "latest provider dekad already has a matching local provenance receipt"
    else:
        status, reason = "ready", "a fresh provider dekad has no matching local provenance receipt"
    result = {
        "source_id": "fao-wapor-v3", "status": status, "reason": reason,
        "run_id": run_id, "already_published": already_published,
        "mapsets": [T_MAPSET, AETI_MAPSET], "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(), "age_days": age,
        "transpiration_code": transpiration.get("code"), "aeti_code": aeti.get("code"),
        "credential_required": False,
    }
    output = Path("/data/drought/outputs")
    output.mkdir(parents=True, exist_ok=True)
    (output / "fao-wapor-v3-probe.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
