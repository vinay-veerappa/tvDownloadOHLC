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


def compute_gex_verdict(
    live_gex: dict | None,
    open_gex: dict | None,
    spot: float | None,
) -> dict:
    """Compute a pre-computed GEX verdict for the intraday cheat sheet.

    Compares current live GEX levels to the morning open snapshot and
    produces a regime, bias, wall shift info, and read string — so the
    LLM doesn't have to interpret raw GEX levels.

    Args:
        live_gex: Current live GEX dict (call_wall, put_wall, flip, gamma_magnet).
        open_gex: Morning open snapshot GEX dict (same keys).
        spot: Current price.

    Returns:
        dict with: regime, bias, call_wall, put_wall, flip, magnet,
        wall_shift_note, read
    """
    if not live_gex or not spot:
        return {"regime": "N/A", "bias": "NEUTRAL", "read": "No GEX data available."}

    cw = live_gex.get("call_wall")
    pw = live_gex.get("put_wall")
    flip = live_gex.get("flip") or live_gex.get("zero_gamma")
    magnet = live_gex.get("gamma_magnet")

    # Regime
    if flip and spot > flip:
        regime = "NEGATIVE GAMMA (destabilizing — dealers sell rips)"
    elif flip and spot < flip:
        regime = "POSITIVE GAMMA (stabilizing — dealers buy dips)"
    else:
        regime = "NEUTRAL GAMMA"

    # Bias from wall structure
    bias_parts = []
    if cw and spot > cw:
        bias_parts.append("call wall broken (bullish)")
    elif cw:
        bias_parts.append(f"call wall overhead ({cw - spot:.0f}pts above)")
    if pw and spot < pw:
        bias_parts.append("put wall broken (bearish)")
    elif pw:
        bias_parts.append(f"put wall below ({spot - pw:.0f}pts below)")

    if bias_parts:
        has_bull = any("bullish" in b for b in bias_parts)
        has_bear = any("bearish" in b for b in bias_parts)
        if has_bull and not has_bear:
            bias = "BULLISH"
        elif has_bear and not has_bull:
            bias = "BEARISH"
        else:
            bias = "NEUTRAL"
    else:
        bias = "NEUTRAL"

    # Wall shift vs morning open
    wall_shift_note = ""
    if open_gex:
        o_cw = open_gex.get("call_wall")
        o_pw = open_gex.get("put_wall")
        shifts = []
        if o_cw and cw and abs(cw - o_cw) > _WALL_THRESHOLD:
            direction = "up" if cw > o_cw else "down"
            shifts.append(f"call wall {direction} {abs(cw - o_cw):.0f}pts")
        if o_pw and pw and abs(pw - o_pw) > _WALL_THRESHOLD:
            direction = "up" if pw > o_pw else "down"
            shifts.append(f"put wall {direction} {abs(pw - o_pw):.0f}pts")
        if shifts:
            wall_shift_note = "Walls shifted: " + ", ".join(shifts)
        else:
            wall_shift_note = "Walls stable"

    # Read
    read_parts = []
    if pw and spot < pw:
        read_parts.append(f"Put wall ({pw:,.2f}) broken — support failed, bearish")
    if cw and spot > cw:
        read_parts.append(f"Call wall ({cw:,.2f}) broken — resistance taken out, bullish")
    if cw and pw and pw < spot < cw:
        read_parts.append(f"Price between put wall ({pw:,.2f}) and call wall ({cw:,.2f}) — range-bound expected")
    if "POSITIVE" in regime:
        read_parts.append("positive gamma dampens moves (mean reversion favored)")
    elif "NEGATIVE" in regime:
        read_parts.append("negative gamma amplifies moves (trend favored)")
    if magnet:
        read_parts.append(f"price magnet at {magnet:,.2f}")
    read = ". ".join(read_parts) + "." if read_parts else "No GEX interpretation available."

    return {
        "regime": regime,
        "bias": bias,
        "call_wall": cw,
        "put_wall": pw,
        "flip": flip,
        "magnet": magnet,
        "wall_shift_note": wall_shift_note,
        "read": read,
    }


def get_gex_regime_change(today_gex: dict) -> dict:
    """Compare today's GEX to yesterday's snapshot.

    Args:
        today_gex: dict with call_wall, put_wall, flip, gamma_magnet keys

    Returns:
        dict with regime_change description
    """
    result = {"regime_change": "stable", "flip_crossed": False, "wall_moved": None}

    today = date.today()
    yest_path = None
    if _SNAPSHOT_DIR.exists():
        try:
            snapshots = sorted([
                f for f in _SNAPSHOT_DIR.glob("*.json")
                if f.stem < today.isoformat()
            ])
            if snapshots:
                yest_path = snapshots[-1]
        except Exception as e:
            log.warning("[gex_regime] Error listing snapshots: %s", e)

    if not yest_path or not yest_path.exists():
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