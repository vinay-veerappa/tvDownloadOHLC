"""C2: Expected Move completeness signal.

Computes where price sits relative to the EM range.
EM is a 1-SD range — a magnet/target, not a ceiling.

Source: Pipeline-generated intraday_levels.json (via run_options_levels.py)

Lookup priority for futures tickers (NQ1, ES1, etc.):
  1. Futures-native entry (NQ, ES) with translation_mode=rtd_direct —
     uses TOS futures IV, NOT ETF-translated. Preferred per user directive.
  2. ETF proxy (QQQ, SPY) — fallback when futures-native not available.
     Scaled by basis_ratio to futures price space.

Futures-to-ETF fallback mapping (used only when futures-native is absent):
  - NQ1 → NQ (futures, rtd_direct) → QQQ (index/ETF fallback)
  - ES1 → ES (futures, rtd_direct) → SPY (index/ETF fallback)
  - YM1 → YM → DIA
  - RTY1 → RTY → IWM
  - MES, MNQ, etc. → use /ES, /NQ directly
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)
_REPO = Path(__file__).parent.parent.parent.parent

# Futures-to-futures-native mapping (try these FIRST in market_structure)
FUTURES_NATIVE = {
    "NQ1": "NQ",
    "NQ": "NQ",
    "/NQ": "NQ",
    "/NQH25": "NQ",  # Micro NQ
    "MNQ": "NQ",
    "ES1": "ES",
    "ES": "ES",
    "/ES": "ES",
    "/ESH25": "ES",  # Micro ES
    "MES": "ES",
    "YM1": "YM",
    "YM": "YM",
    "/YM": "YM",
    "MYM": "YM",
    "RTY1": "RTY",
    "RTY": "RTY",
    "/RTY": "RTY",
    "M2K": "RTY",  # Micro Russell
}

# Futures-to-ETF fallback mapping (used only when futures-native not in file)
FUTURES_TO_ETF = {
    "NQ1": "QQQ",
    "NQ": "QQQ",
    "/NQ": "QQQ",
    "/NQH25": "QQQ",
    "MNQ": "QQQ",
    "ES1": "SPY",
    "ES": "SPY",
    "/ES": "SPY",
    "/ESH25": "SPY",
    "MES": "SPY",
    "YM1": "DIA",
    "YM": "DIA",
    "/YM": "DIA",
    "MYM": "DIA",
    "RTY1": "IWM",
    "RTY": "IWM",
    "/RTY": "IWM",
    "M2K": "IWM",
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
    raw_ticker = ticker.upper().strip()

    # Build lookup priority: futures-native first, then ETF proxy
    # Per user directive: NQ/ES must use futures TOS EM, not SPY/QQQ translated.
    # The pipeline writes NQ/ES with translation_mode=rtd_direct when TOS RTD is active.
    is_futures_request = raw_ticker in FUTURES_NATIVE or raw_ticker in FUTURES_TO_ETF
    lookup_candidates: list[str] = []
    if raw_ticker in FUTURES_NATIVE:
        lookup_candidates.append(FUTURES_NATIVE[raw_ticker])
    if raw_ticker in FUTURES_TO_ETF:
        etf = FUTURES_TO_ETF[raw_ticker]
        if etf not in lookup_candidates:
            lookup_candidates.append(etf)
    if raw_ticker not in lookup_candidates:
        lookup_candidates.append(raw_ticker)

    # Try pipeline-generated intraday_levels.json (canonical path) first,
    # then fall back to daily_levels.json (legacy alias) for backwards compat.
    p = _REPO / "data" / "options" / "intraday_levels.json"
    if not p.exists():
        p = _REPO / "data" / "options" / "daily_levels.json"
    if not p.exists():
        log.warning(f"[em] Pipeline file not found: intraday_levels.json or daily_levels.json")
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
            ticker_entry = None
            matched_ticker = None
            
            # Try each lookup candidate in priority order
            for lookup_ticker in lookup_candidates:
                for entry in market_struct:
                    if entry.get("asset", "").upper() == lookup_ticker:
                        ticker_entry = entry
                        matched_ticker = lookup_ticker
                        break
                if ticker_entry:
                    break
            
            if not ticker_entry:
                log.warning(f"[em] Ticker {ticker} (tried {lookup_candidates}) not found in market_structure")
                return result
            
            log.debug("[em] Matched %s → %s", ticker, matched_ticker)
            
            # Determine whether to scale by basis_ratio.
            # RTD-native entries (NQ, ES with translation_mode=rtd_direct) are already
            # in futures price space — do NOT scale. Only ETF-proxy entries need scaling,
            # and only when the caller requested a futures ticker (not the ETF directly).
            translation_mode = ticker_entry.get("translation_mode", "")
            is_rtd_native = translation_mode == "rtd_direct"
            
            basis_ratio = ticker_entry.get("basis_ratio")
            should_scale = (
                not is_rtd_native
                and is_futures_request
                and basis_ratio
                and basis_ratio != 1.0
            )
            if should_scale:
                log.debug("[em] Scaling EM by basis_ratio=%.4f for %s (ETF proxy for futures request)", basis_ratio, matched_ticker)
            else:
                basis_ratio = None  # No scaling needed
            
            # Get first EM (shortest DTE)
            expected_moves = ticker_entry.get("expected_moves", [])
            if not expected_moves:
                log.warning(f"[em] No expected_moves for {matched_ticker}")
                return result
            
            em_first = expected_moves[0]  # Shortest DTE
            em_upper = float(em_first.get("em_upper") or 0)
            em_lower = float(em_first.get("em_lower") or 0)
            
            # Scale to futures if ETF proxy with translation ratio
            if basis_ratio:
                em_upper = round(em_upper * basis_ratio, 2)
                em_lower = round(em_lower * basis_ratio, 2)
        
        # Handle legacy format: data array
        elif "data" in em_data:
            entries = em_data.get("data", [])
            if not entries:
                log.warning("[em] Empty data array")
                return result

            # Find the ticker's EM — try each lookup candidate
            em_entry = None
            for lookup_ticker in lookup_candidates:
                for e in entries:
                    if isinstance(e, dict) and e.get("ticker", "").upper() in (lookup_ticker, lookup_ticker.replace("1", "")):
                        em_entry = e
                        break
                if em_entry:
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