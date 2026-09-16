"""Metadata-only new/current probe for the configured CDSE NDVI or SWI source.

The probe obtains an OAuth token and queries the catalogue but never calls the
Process API. A source is ``ready`` only when its latest timestamp has no valid
local manifest; a current source is a normal no-download result.
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError

from cdse_ndvi_tabia_summary import access_token, cdse_settings, fetch_tabias_and_bounds, latest_item
from cdse_swi_tabia_summary import get_settings as swi_settings


CONFIG = {
    "ndvi": {"prefix": "cdse-clms-ndvi-v3-", "timestamp": "observation_timestamp", "max_age": 15},
    "swi": {"prefix": "cdse-clms-swi-v4-", "timestamp": "observation_at", "max_age": 15},
}


def has_valid_manifest(kind: str, stamp: str) -> bool:
    config = CONFIG[kind]
    for path in Path("/data/drought/outputs").glob(f"{config['prefix']}*.manifest.json"):
        try:
            manifest = json.loads(path.read_text(encoding="utf-8"))
            if manifest.get("status") in {"development", "degraded"} and manifest.get(config["timestamp"]) == stamp:
                return True
        except (OSError, json.JSONDecodeError):
            continue
    return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("kind", choices=sorted(CONFIG))
    kind = parser.parse_args().kind
    try:
        settings, collection = swi_settings() if kind == "swi" else cdse_settings()
        token = access_token(settings)
        _, bounds = fetch_tabias_and_bounds()
        _, stamp = latest_item(token, collection, bounds)
        observed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        age_days = round((datetime.now(timezone.utc) - observed).total_seconds() / 86400, 1)
        current = has_valid_manifest(kind, stamp)
        if age_days > CONFIG[kind]["max_age"]:
            status, reason = "degraded", "latest catalogue item exceeds the freshness threshold"
        elif current:
            status, reason = "current", "latest catalogue item already has a valid local manifest"
        else:
            status, reason = "ready", "fresh catalogue item has no valid local manifest"
        result = {"kind": kind, "status": status, "reason": reason, "observation_timestamp": stamp,
                  "age_days": age_days, "freshness_threshold_days": CONFIG[kind]["max_age"],
                  "already_summarized": current, "authentication": "passed", "collection_access": "passed"}
    except (HTTPError, URLError, TimeoutError):
        result = {"kind": kind, "status": "unavailable", "reason": "CDSE metadata request failed", "authentication": "unknown", "collection_access": "unknown"}
    except (RuntimeError, ValueError, OSError):
        result = {"kind": kind, "status": "unavailable", "reason": "CDSE probe configuration or response was invalid", "authentication": "unknown", "collection_access": "unknown"}
    output = Path("/data/drought/outputs")
    output.mkdir(parents=True, exist_ok=True)
    (output / f"cdse-{kind}-probe.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result))
    return 0 if result["status"] != "unavailable" else 1


if __name__ == "__main__":
    raise SystemExit(main())
