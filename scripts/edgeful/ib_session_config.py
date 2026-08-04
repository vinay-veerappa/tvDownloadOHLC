"""IB Custom Range Configuration (FR-11, BL-4).

Reads custom time range definitions from YAML and registers them into
SESSION_CONFIGS_V5 so they flow through the full IB pipeline.

Usage
-----
    from scripts.edgeful.ib_session_config import load_custom_ranges

    load_custom_ranges("scripts/config/ib_custom_ranges.yaml")
    # Now SESSION_CONFIGS_V5 has the custom ranges registered
    # and calculate_ib_statistics_v5 / ib_derived_fields will process them
"""
from __future__ import annotations

from datetime import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

# Import the session config dict that all IB scripts use
import sys
_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from scripts.libs_py.nqstats.ib import SESSION_CONFIGS_V5


def _parse_hhmm(hhmm: str) -> time:
    """Parse 'HHMM' string to datetime.time.

    >>> _parse_hhmm("0930")
    datetime.time(9, 30)
    >>> _parse_hhmm("1400")
    datetime.time(14, 0)
    >>> _parse_hhmm("0300")
    datetime.time(3, 0)
    """
    if isinstance(hhmm, time):
        return hhmm
    s = str(hhmm).strip()
    if len(s) == 3:
        s = "0" + s
    if len(s) != 4:
        raise ValueError(f"Invalid time format: {hhmm!r}. Expected HHMM (e.g. '0930')")
    h = int(s[:2])
    m = int(s[2:])
    return time(h, m)


def parse_custom_ranges(yaml_path: str | Path) -> List[Dict[str, Any]]:
    """Parse custom range definitions from YAML.

    Parameters
    ----------
    yaml_path : str | Path
        Path to the YAML config file.

    Returns
    -------
    list[dict]
        List of range specs with parsed time objects.
    """
    path = Path(yaml_path)
    if not path.exists():
        raise FileNotFoundError(f"Custom ranges config not found: {path}")

    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not data or "custom_ranges" not in data:
        raise ValueError(f"No 'custom_ranges' key in {path}")

    ranges = []
    for entry in data["custom_ranges"]:
        name = entry["name"]
        start = _parse_hhmm(entry["start"])
        end = _parse_hhmm(entry["end"])
        cutoff = _parse_hhmm(entry.get("cutoff", "1600"))
        timezone = entry.get("timezone", "America/New_York")
        days = entry.get("days", "12345")
        time_basis = entry.get("time_basis", "ET_fixed")

        ranges.append({
            "name": name,
            "start": start,
            "end": end,
            "cutoff": cutoff,
            "timezone": timezone,
            "days": days,
            "time_basis": time_basis,
        })

    return ranges


def load_custom_ranges(yaml_path: str | Path | None = None) -> List[str]:
    """Load custom ranges from YAML and register into SESSION_CONFIGS_V5.

    Parameters
    ----------
    yaml_path : str | Path, optional
        Path to YAML config. If None, uses default
        ``scripts/config/ib_custom_ranges.yaml``.

    Returns
    -------
    list[str]
        List of registered session_slot names.
    """
    if yaml_path is None:
        default = _root / "scripts" / "config" / "ib_custom_ranges.yaml"
        if not default.exists():
            return []
        yaml_path = default

    ranges = parse_custom_ranges(yaml_path)
    registered = []

    for r in ranges:
        name = r["name"]
        SESSION_CONFIGS_V5[name] = {
            "ib_start": r["start"],
            "ib_end": r["end"],
            "out_end": r["cutoff"],
            "time_basis": r["time_basis"],
            "custom": True,  # flag for downstream filtering
            "days": r["days"],
        }
        registered.append(name)

    return registered


def get_all_session_slots(include_custom: bool = True) -> List[str]:
    """Return all available session slot names.

    Parameters
    ----------
    include_custom : bool
        If True, include custom ranges registered via load_custom_ranges().
    """
    if include_custom:
        return list(SESSION_CONFIGS_V5.keys())
    return [k for k, v in SESSION_CONFIGS_V5.items() if not v.get("custom")]


def is_custom_range(session_slot: str) -> bool:
    """Check if a session_slot is a custom range."""
    cfg = SESSION_CONFIGS_V5.get(session_slot)
    return cfg is not None and cfg.get("custom", False)