"""C2: Expected Move completeness signal.

Computes where price sits relative to the EM range.
EM is a 1-SD range — a magnet/target, not a ceiling.

Source: Pipeline-generated daily_levels.json (via run_options_levels.py)
Futures are mapped to their index proxies:
  - NQ1 → /NQ (futures) → QQQ (index/ETF)
  - ES1 → /ES (futures) → SPY (index/ETF)
  - YM1 → /YM (futures) → DIA (index/ETF)
  - RTY1 → /RTY (futures) → IWM (index/ETF)
  - MES, MNQ, etc. → use /ES, /NQ directly
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)
_REPO = Path(__file__).parent.parent.parent.parent

# Futures-to-ETF mapping for EM lookup
FUTURES_TO_ETF = {
    "NQ1": "QQQ",
    "NQ": "QQQ",
    "/NQ": "QQQ",
    "/NQH25": "QQQ",  # Micro NQ
    "ES1": "SPY",
    "ES": "SPY",
    "/ES": "SPY",
    "/ESH25": "SPY",  # Micro ES
    "YM1": "DIA",
    "YM": "DIA",
    "/YM": "DIA",
    "RTY1": "IWM",
    "RTY": "IWM",
    "/RTY": "IWM",
    # Micro contracts
    "MNQ": "QQQ",
    "MES": "SPY",
    "MYM": "DIA",
    "M2K": "IWM",  # Micro Russell
}


def get_em_context(spot: float, ticker: str = "NQ1") -> dict:
    """Returns EM position and interpretation.
    
    Args:
        spot: Current price. If 0 or None, returns EM range only without position calc.
        ticker: Symbol (NQ1, ES1, /ES, /NQ, QQQ, SPY, etc.)
    
    Returns:
        Dict with em_upper, em_lower, em_range, price_position_pct, read, is_exceeded
    """
    result = {
        "em_upper": None, "em_lower": None, "em_range": None,
        "price_position_pct": None, "read": "EM unavailable", "is_exceeded": False,
    }
    
    has_spot = spot is not None and spot > 0

    # Normalize ticker to lookup key
    lookup_ticker = ticker.upper().strip()
    if lookup_ticker in FUTURES_TO_ETF:
        lookup_ticker = FUTURES_TO_ETF[lookup_ticker]
    
    # Try pipeline-generated daily_levels.json first
    p = _REPO / "data" / "options" / "daily_levels.json"
    if not p.exists():
        log.warning(f"[em] Pipeline file not found: {p}")
        # Fall back to legacy expected_moves.json
        p = _REPO / "data" / "expected_moves.json"
        if not p.exists():
            log.warning("[em] No EM data files found")
            return result

    try:
        with open(p, "r", encoding="utf-8") as f:
            em_data = json.load(f)
        
        # Handle pipeline format: market_structure array
        if "market_structure" in em_data:
            market_struct = em_data.get("market_structure", [])
            em_entry = None
            
            # Find by asset field
            for entry in market_struct:
                if entry.get("asset", "").upper() == lookup_ticker:
                    em_entry = entry
                    break
            
            if not em_entry:
                log.warning(f"[em] Ticker {ticker} → {lookup_ticker} not found in market_structure")
                return result
            
            # Get translation ratio for ETF→futures scaling
            basis_ratio = em_entry.get("basis_ratio")
            if basis_ratio and basis_ratio != 1.0:
                log.debug("[em] Scaling EM by basis_ratio=%.4f for %s", basis_ratio, lookup_ticker)
            else:
                basis_ratio = None
            
            # Get first EM (shortest DTE)
            expected_moves = em_entry.get("expected_moves", [])
            if not expected_moves:
                log.warning(f"[em] No expected_moves for {lookup_ticker}")
                return result
            
            em_entry = expected_moves[0]  # Shortest DTE
            em_upper = float(em_entry.get("em_upper") or 0)
            em_lower = float(em_entry.get("em_lower") or 0)
            
            # Scale to futures if translation ratio available
            if basis_ratio:
                em_upper = round(em_upper * basis_ratio, 2)
                em_lower = round(em_lower * basis_ratio, 2)
        
        # Handle legacy format: data array
        elif "data" in em_data:
            entries = em_data.get("data", [])
            if not entries:
                log.warning("[em] Empty data array")
                return result

            # Find the ticker's EM
            em_entry = None
            for e in entries:
                if isinstance(e, dict) and e.get("ticker", "").upper() in (lookup_ticker, lookup_ticker.replace("1", "")):
                    em_entry = e
                    break
            if not em_entry and entries:
                em_entry = entries[0] if isinstance(entries[0], dict) else {}

            em_upper = float(em_entry.get("em_upper") or em_entry.get("high") or 0)
            em_lower = float(em_entry.get("em_lower") or em_entry.get("low") or 0)
        
        else:
            log.warning("[em] Unrecognized EM data format")
            return result

        if em_upper <= 0 or em_lower <= 0 or em_upper == em_lower:
            log.warning(f"[em] Invalid EM values: upper={em_upper}, lower={em_lower}")
            return result

        em_range = em_upper - em_lower
        
        # If no spot price provided, just return EM range
        if not has_spot:
            result.update({
                "em_upper": round(em_upper, 2),
                "em_lower": round(em_lower, 2),
                "em_range": round(em_range, 2),
                "price_position_pct": None,
                "read": f"EM Range (0DTE): {round(em_lower, 2)} to {round(em_upper, 2)}",
                "is_exceeded": False,
            })
            return result
        
        # With spot price, calculate position within EM
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
        log.warning("[em] Error: %s", e, exc_info=True)

    return result


def format_em_block(data: dict) -> str:
    lines = ["== EXPECTED MOVE =="]
    if data["em_upper"] is None:
        return "== EXPECTED MOVE ==\nEM unavailable"
    
    # If we have price position, show it
    if data["price_position_pct"] is not None:
        lines.append(f"EM: {data['em_lower']:.2f} to {data['em_upper']:.2f} | Price at {data['price_position_pct']:.0f}% of range")
    else:
        # Just show EM range without price
        lines.append(f"EM Range: {data['em_lower']:.2f} to {data['em_upper']:.2f}")
    
    lines.append(f"Read: {data['read']}")
    return "\n".join(lines)