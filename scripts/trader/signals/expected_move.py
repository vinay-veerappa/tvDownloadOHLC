"""C2: Expected Move completeness signal.

Computes where price sits relative to the EM range.
EM is a 1-SD range — a magnet/target, not a ceiling.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)
_REPO = Path(__file__).parent.parent.parent.parent


def get_em_context(spot: float, ticker: str = "NQ1") -> dict:
    """Returns EM position and interpretation."""
    result = {
        "em_upper": None, "em_lower": None, "em_range": None,
        "price_position_pct": None, "read": "EM unavailable", "is_exceeded": False,
    }

    p = _REPO / "data" / "expected_moves.json"
    if not p.exists():
        log.warning("[em] File not found")
        return result

    try:
        em_data = json.load(open(p, "r", encoding="utf-8"))
        entries = em_data.get("data", [])
        if not entries:
            log.warning("[em] Empty data array")
            return result

        # Find the ticker's EM (entries may be keyed by ticker)
        em_entry = None
        for e in entries:
            if isinstance(e, dict) and e.get("ticker", "").upper() in (ticker, ticker.replace("1", "")):
                em_entry = e
                break
        if not em_entry and entries:
            em_entry = entries[0] if isinstance(entries[0], dict) else {}

        em_upper = float(em_entry.get("em_upper") or em_entry.get("high") or 0)
        em_lower = float(em_entry.get("em_lower") or em_entry.get("low") or 0)

        if em_upper <= 0 or em_lower <= 0 or em_upper == em_lower:
            return result

        em_range = em_upper - em_lower
        pos_pct = ((spot - em_lower) / em_range * 100) if em_range > 0 else 50.0

        result.update({
            "em_upper": round(em_upper, 2),
            "em_lower": round(em_lower, 2),
            "em_range": round(em_range, 2),
            "price_position_pct": round(pos_pct, 1),
        })

        if pos_pct > 100:
            result["is_exceeded"] = True
            result["read"] = "Price ABOVE EM upper — trend day signal, don't fade"
        elif pos_pct > 90:
            result["read"] = "Near EM upper — magnet/target, not ceiling"
        elif pos_pct < 0:
            result["is_exceeded"] = True
            result["read"] = "Price BELOW EM lower — trend day signal (bearish), don't fade"
        elif pos_pct < 10:
            result["read"] = "Near EM lower — magnet/target, not floor"
        else:
            result["read"] = f"Price at {pos_pct:.0f}% of EM range — mid-range"

    except Exception as e:
        log.warning("[em] Error: %s", e)

    return result


def format_em_block(data: dict) -> str:
    lines = ["== EXPECTED MOVE =="]
    if data["em_upper"] is None:
        return "== EXPECTED MOVE ==\nEM unavailable"
    lines.append(f"EM: {data['em_lower']:.2f} to {data['em_upper']:.2f} | Price at {data['price_position_pct']:.0f}% of range")
    lines.append(f"Read: {data['read']}")
    return "\n".join(lines)