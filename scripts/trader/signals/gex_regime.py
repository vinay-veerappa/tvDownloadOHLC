"""C3: GEX Regime Change Detection.

Compares today's GEX levels to yesterday's to detect regime changes.
Today's GEX comes from unified_levels.json. Yesterday's from daily snapshot archive.
"""
from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path

log = logging.getLogger(__name__)
_REPO = Path(__file__).parent.parent.parent.parent
_SNAPSHOT_DIR = _REPO / "data" / "options" / "daily" / "gex_snapshots"
_FLIP_THRESHOLD = 5.0  # points to consider flip "crossed"
_WALL_THRESHOLD = 25.0  # points to consider wall "moved"


def get_gex_regime_change(today_gex: dict) -> dict:
    """Compare today's GEX to yesterday's snapshot.

    Args:
        today_gex: dict with call_wall, put_wall, flip, gamma_magnet keys

    Returns:
        dict with regime_change description
    """
    result = {"regime_change": "stable", "flip_crossed": False, "wall_moved": None}

    today = date.today()
    yesterday = date(today.year, today.month, today.day - 1)
    yest_path = _SNAPSHOT_DIR / f"{yesterday.isoformat()}.json"

    if not yest_path.exists():
        result["regime_change"] = "no prior snapshot for comparison"
        return result

    try:
        yest = json.load(open(yest_path, "r", encoding="utf-8"))
    except Exception:
        result["regime_change"] = "could not read prior snapshot"
        return result

    changes = []

    # Flip check
    today_flip = today_gex.get("flip")
    yest_flip = yest.get("flip")
    if today_flip and yest_flip:
        if today_flip > yest_flip + _FLIP_THRESHOLD:
            changes.append(f"flip moved up {today_flip - yest_flip:.0f}pts")
            result["flip_crossed"] = True
        elif today_flip < yest_flip - _FLIP_THRESHOLD:
            changes.append(f"flip moved down {yest_flip - today_flip:.0f}pts")
            result["flip_crossed"] = True

    # Wall check
    today_cw = today_gex.get("call_wall")
    yest_cw = yest.get("call_wall")
    if today_cw and yest_cw and abs(today_cw - yest_cw) > _WALL_THRESHOLD:
        direction = "up" if today_cw > yest_cw else "down"
        changes.append(f"call wall {direction} {abs(today_cw - yest_cw):.0f}pts")

    today_pw = today_gex.get("put_wall")
    yest_pw = yest.get("put_wall")
    if today_pw and yest_pw and abs(today_pw - yest_pw) > _WALL_THRESHOLD:
        direction = "up" if today_pw > yest_pw else "down"
        changes.append(f"put wall {direction} {abs(today_pw - yest_pw):.0f}pts")

    if changes:
        result["regime_change"] = "; ".join(changes)
    else:
        result["regime_change"] = "stable — levels unchanged from yesterday"

    return result


def save_today_snapshot(gex: dict) -> None:
    """Save today's GEX snapshot for tomorrow's comparison."""
    _SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today()
    path = _SNAPSHOT_DIR / f"{today.isoformat()}.json"
    try:
        json.dump(gex, open(path, "w", encoding="utf-8"), indent=2)
    except Exception as e:
        log.warning("[gex_regime] Could not save snapshot: %s", e)


def format_gex_regime_block(regime_data: dict) -> str:
    lines = ["== GEX REGIME CHANGE =="]
    lines.append(f"Change: {regime_data['regime_change']}")
    if regime_data["flip_crossed"]:
        lines.append("⚠️ Flip crossed — gamma regime may have shifted")
    return "\n".join(lines)