#!/usr/bin/env python3
"""External, state-change-only monitor for TSIRD public indicator freshness.

Run this from a scheduler that is independent of n8n. It reads only the
public indicator metadata endpoint and persists a small local alert state. A
Telegram message is sent only when the alert state changes; credentials come
only from environment variables and are never read from project files.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from drought_indicator_freshness import load_contract


def get_json(url: str) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("public indicator endpoint did not return an object")
    return payload


def alert_state(payload: dict[str, Any]) -> dict[str, Any]:
    contract = load_contract()
    expected = {source["key"] for source in contract["sources"]}
    freshness = payload.get("freshness")
    if not isinstance(freshness, list):
        return {"state": "invalid", "reason": "public indicator release has no freshness metadata"}
    records = {
        item.get("source_key"): item
        for item in freshness
        if isinstance(item, dict) and isinstance(item.get("source_key"), str)
    }
    if set(records) != expected:
        return {"state": "invalid", "reason": "public indicator release freshness sources are incomplete"}
    today = date.today()
    stale: list[str] = []
    for key, record in sorted(records.items()):
        deadline = record.get("stale_after")
        try:
            if not isinstance(deadline, str) or date.fromisoformat(deadline) < today:
                stale.append(f"{key} (as of {record.get('source_observation_end', 'unknown')}; stale after {deadline or 'unknown'})")
        except ValueError:
            stale.append(f"{key} (invalid stale_after)")
    if stale:
        return {"state": "stale", "release_id": payload.get("release_id"), "sources": stale}
    return {"state": "current", "release_id": payload.get("release_id")}


def load_previous(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=path.parent, encoding="utf-8", delete=False) as handle:
        json.dump(payload, handle, sort_keys=True)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(path)


def telegram(text: str) -> None:
    token = os.environ.get("TSIRD_MONITOR_TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TSIRD_MONITOR_TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        raise RuntimeError("Telegram notification requested but monitor environment variables are absent")
    body = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode("utf-8")
    request = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=body, method="POST")
    with urllib.request.urlopen(request, timeout=20) as response:
        if response.status != 200:
            raise RuntimeError("Telegram notification was rejected")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public-base", required=True, help="for example https://lab.tigrayinsights.net")
    parser.add_argument("--state-file", type=Path, required=True, help="ignored local monitor state file")
    parser.add_argument("--telegram", action="store_true", help="send a state-change notification using monitor environment variables")
    args = parser.parse_args()
    endpoint = args.public_base.rstrip("/") + "/map/api/drought/public/indicators"
    try:
        current = alert_state(get_json(endpoint))
    except Exception as error:
        current = {"state": "unreachable", "reason": f"{type(error).__name__}: {error}"}
    current["checked_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    previous = load_previous(args.state_file)
    comparable = {key: value for key, value in current.items() if key != "checked_at"}
    previous_comparable = {key: value for key, value in previous.items() if key != "checked_at"}
    changed = comparable != previous_comparable
    if changed and args.telegram:
        state = current["state"]
        if state == "current":
            message = f"TSIRD monitor: public indicator release {current.get('release_id', 'unknown')} is within all declared freshness windows."
        elif state == "stale":
            message = "TSIRD monitor: public indicator evidence is stale: " + "; ".join(current["sources"])
        else:
            message = "TSIRD monitor: public indicator freshness check failed: " + current.get("reason", "unknown error")
        telegram(message)
    save_state(args.state_file, current)
    print(json.dumps({"changed": changed, **current}, sort_keys=True))
    return 0 if current["state"] == "current" else 2


if __name__ == "__main__":
    raise SystemExit(main())
