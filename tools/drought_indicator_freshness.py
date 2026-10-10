"""Shared release-freshness helpers for automatic indicator evidence.

The checked-in JSON contract is deliberately data-only so the Python builder,
the n8n Node publisher, public API, and an external monitor can use the same
source cadence and staleness policy without embedding separate thresholds.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any


CONTRACT_PATH = Path(__file__).resolve().parents[1] / "n8n" / "publisher" / "drought-indicator-freshness-contract.json"


def load_contract() -> dict[str, Any]:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    sources = contract.get("sources")
    if contract.get("schema_version") != "tsird-drought-indicator-freshness-contract/v1" or not isinstance(sources, list):
        raise RuntimeError("indicator freshness contract is invalid")
    return contract


def observation_end(run: dict[str, Any]) -> str:
    value = run.get("observation_end") or run.get("source_period_end") or run.get("period_end") or run.get("source_latest_month")
    if not isinstance(value, str):
        raise RuntimeError("indicator run lacks a source-observation end date")
    value = value[:10]
    try:
        date.fromisoformat(value)
    except ValueError as error:
        raise RuntimeError("indicator run has an invalid source-observation end date") from error
    return value


def build_freshness(payloads: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Create deterministic per-source freshness facts for an immutable release."""
    result: list[dict[str, Any]] = []
    for source in load_contract()["sources"]:
        key = source["key"]
        payload = payloads.get(key)
        run = payload.get("run") if isinstance(payload, dict) else None
        if not isinstance(run, dict):
            raise RuntimeError(f"{key} has no run metadata for freshness")
        ended = date.fromisoformat(observation_end(run))
        expected = ended + timedelta(days=int(source["expected_after_days"]))
        stale = ended + timedelta(days=int(source["stale_after_days"]))
        result.append({
            "source_key": key,
            "label": source["label"],
            "source_observation_end": ended.isoformat(),
            "expected_next": expected.isoformat(),
            "stale_after": stale.isoformat(),
            "automation_state": source["automation_state"],
        })
    return result
