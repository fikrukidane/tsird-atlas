from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from config.paths import PROJECT_ROOT

OVERRIDE_YAML = PROJECT_ROOT / "config" / "crs_overrides.yml"


def _normalize_epsg(epsg_value: Any) -> int:
    """
    Accepts: 32637, "32637", "EPSG:32637"
    Returns: 32637
    Raises ValueError for invalid inputs.
    """
    if epsg_value is None:
        raise ValueError("epsg is missing")

    if isinstance(epsg_value, int):
        return epsg_value

    if isinstance(epsg_value, str):
        s = epsg_value.strip().upper()
        if s.startswith("EPSG:"):
            s = s.split("EPSG:", 1)[1].strip()
        if s.isdigit():
            return int(s)

    raise ValueError(f"Invalid epsg value: {epsg_value!r}")


def load_crs_overrides(path: Path = OVERRIDE_YAML) -> dict[str, int]:
    """
    Returns mapping: layer_name -> epsg_int
    """
    if not path.exists():
        return {}

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    overrides = data.get("overrides") or {}

    out: dict[str, int] = {}
    for layer_name, cfg in overrides.items():
        if cfg is None:
            continue
        if isinstance(cfg, dict):
            epsg = _normalize_epsg(cfg.get("epsg"))
        else:
            # allow short form: layer_name: 32637
            epsg = _normalize_epsg(cfg)
        out[str(layer_name)] = epsg

    return out
