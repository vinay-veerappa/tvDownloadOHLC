"""GEX × EM Confluence Verdict.

Combines the GEX dealer regime (pinned/trending/coiled/battle zone) with
the current price position relative to the Expected Move envelope into a
single actionable verdict — Python-decided, LLM narrates.

The GEX regime determines the *nature* of the day (range vs. trend).
The EM position determines *where* price is relative to the expected range.
Together they answer: "what should I actually do right now?"

Usage:
    from scripts.trader.signals.gex_em_confluence import compute_gex_em_verdict

    verdict = compute_gex_em_verdict(
        gex_regime="NEGATIVE",
        regime_label="TRENDING",
        em_upper=29266.45,
        em_lower=27802.55,
        spot=28560,
        call_wall=28700,
        put_wall=28275,
        gamma_magnet=28500,
    )
    # → {verdict: "TREND-FOLLOW", setup: "Long continuation, trail stops", ...}
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass
class ConfluenceVerdict:
    """Structured GEX × EM confluence verdict."""

    verdict: str           # FADE / TREND-FOLLOW / WAIT / BREAKOUT-WAIT / WALL-TRADE / NEUTRAL
    setup: str             # Plain-English setup description
    invalidation: str      # What invalidates this setup
    confidence: str        # HIGH / MEDIUM / LOW
    em_position_pct: float # 0-100, where price sits in the EM range
    regime: str            # POSITIVE / NEGATIVE / NEUTRAL
    regime_label: str      # PINNED / TRENDING / COILED / BATTLE ZONE / NEUTRAL
    read: str              # Full plain-English read for the cheat sheet


def compute_gex_em_verdict(
    gex_regime: str,
    regime_label: str,
    em_upper: float,
    em_lower: float,
    spot: float,
    call_wall: float | None = None,
    put_wall: float | None = None,
    gamma_magnet: float | None = None,
) -> dict:
    """Return a single actionable verdict combining GEX regime + EM position.

    Args:
        gex_regime: POSITIVE / NEGATIVE / NEUTRAL (from GexSnapshot or META_)
        regime_label: PINNED / TRENDING / COILED / BATTLE ZONE / NEUTRAL
        em_upper: Expected Move upper bound
        em_lower: Expected Move lower bound
        spot: Current price
        call_wall: Call wall level (optional, improves accuracy)
        put_wall: Put wall level (optional, improves accuracy)
        gamma_magnet: Gamma magnet level (optional, for fade target)

    Returns:
        Dict with: verdict, setup, invalidation, confidence, em_position_pct,
        regime, regime_label, read
    """
    # Calculate EM position
    if em_upper and em_lower and em_upper > em_lower:
        em_range = em_upper - em_lower
        em_pos_pct = ((spot - em_lower) / em_range) * 100
    else:
        em_pos_pct = 50.0
        em_range = 0

    # Clamp for sanity
    em_pos_pct = max(-50, min(150, em_pos_pct))

    regime_upper = (gex_regime or "").upper()
    label_upper = (regime_label or "").upper()

    # Determine regime bucket
    is_pinned = regime_upper == "POSITIVE" and "PINNED" in label_upper
    is_trending = regime_upper == "NEGATIVE" and "TRENDING" in label_upper
    is_coiled = regime_upper == "NEGATIVE" and "COILED" in label_upper
    is_battle = regime_upper == "POSITIVE" and "BATTLE" in label_upper
    is_neutral_gex = regime_upper == "NEUTRAL" or "NEUTRAL" in label_upper

    # If we can't determine a specific bucket, infer from regime sign
    if not any([is_pinned, is_trending, is_coiled, is_battle]):
        if regime_upper == "POSITIVE":
            is_pinned = True  # default positive = pinned behavior
        elif regime_upper == "NEGATIVE":
            is_trending = True  # default negative = trending behavior
        else:
            is_neutral_gex = True

    # ── Logic matrix ──

    # EM position thresholds
    near_em_hi = em_pos_pct >= 85
    near_em_lo = em_pos_pct <= 15
    above_em = em_pos_pct > 100
    below_em = em_pos_pct < 0
    mid_range = 35 <= em_pos_pct <= 65

    # Wall proximity (if provided)
    near_call_wall = call_wall and spot > 0 and abs(spot - call_wall) / spot < 0.005
    near_put_wall = put_wall and spot > 0 and abs(spot - put_wall) / spot < 0.005

    magnet_target = gamma_magnet or "the gamma magnet"

    if is_pinned:
        if near_em_hi or near_call_wall:
            verdict = "FADE"
            setup = f"Short near EM High ({em_upper:.2f}) / Call Wall ({call_wall or 'N/A'}). "
            setup += f"Target retracement to {magnet_target}."
            invalidation = f"Close above Call Wall ({call_wall or em_upper:.2f}) — pin broken, model invalidated"
            confidence = "HIGH" if near_call_wall else "MEDIUM"
        elif near_em_lo or near_put_wall:
            verdict = "FADE"
            setup = f"Long near EM Low ({em_lower:.2f}) / Put Wall ({put_wall or 'N/A'}). "
            setup += f"Target retracement to {magnet_target}."
            invalidation = f"Close below Put Wall ({put_wall or em_lower:.2f}) — pin broken, model invalidated"
            confidence = "HIGH" if near_put_wall else "MEDIUM"
        elif mid_range:
            verdict = "NEUTRAL"
            setup = f"Price at mid-range ({em_pos_pct:.0f}% of EM), near {magnet_target}. "
            setup += "Stay flat; wait for price to reach EM edge or wall for a fade setup."
            invalidation = "N/A — observation only"
            confidence = "LOW"
        else:
            verdict = "FADE"
            setup = f"Price at {em_pos_pct:.0f}% of EM range. "
            if em_pos_pct > 65:
                setup += f"Approaching EM High — prepare fade toward {magnet_target}."
            else:
                setup += f"Approaching EM Low — prepare fade toward {magnet_target}."
            invalidation = "EM boundary break with candle close"
            confidence = "MEDIUM"

    elif is_trending:
        if above_em:
            verdict = "TREND-FOLLOW"
            setup = f"Price ABOVE EM High ({em_upper:.2f}) — trend day. "
            setup += "Long continuation, trail stops. Do not fade."
            invalidation = "Rejection back inside EM envelope on 30-min close"
            confidence = "HIGH"
        elif below_em:
            verdict = "TREND-FOLLOW"
            setup = f"Price BELOW EM Low ({em_lower:.2f}) — trend day (bearish). "
            setup += "Short continuation, trail stops. Do not fade."
            invalidation = "Rejection back inside EM envelope on 30-min close"
            confidence = "HIGH"
        elif near_em_hi:
            verdict = "WAIT"
            setup = f"Near EM High ({em_upper:.2f}) in trending regime. "
            setup += "Wait for EM break (bullish continuation) or rejection (reversal)."
            invalidation = "N/A — wait for confirmation"
            confidence = "LOW"
        elif near_em_lo:
            verdict = "WAIT"
            setup = f"Near EM Low ({em_lower:.2f}) in trending regime. "
            setup += "Wait for EM break (bearish continuation) or rejection (reversal)."
            invalidation = "N/A — wait for confirmation"
            confidence = "LOW"
        else:
            verdict = "WAIT"
            setup = f"Price inside EM ({em_pos_pct:.0f}% of range) in trending regime. "
            setup += "Wait for EM boundary break, then join direction."
            invalidation = "N/A — wait for EM break"
            confidence = "LOW"

    elif is_coiled:
        verdict = "BREAKOUT-WAIT"
        setup = "Coiled regime (negative GEX + tight walls). "
        if call_wall and put_wall:
            setup += f"Wait for break of Call Wall ({call_wall:.2f}) or Put Wall ({put_wall:.2f}). "
            setup += "Require candle close outside the wall before entry."
            invalidation = f"False breakout — candle close back inside [{put_wall:.2f}, {call_wall:.2f}]"
        else:
            setup += "Wait for wall break with momentum confirmation."
            invalidation = "False breakout — price rejected back inside range"
        confidence = "MEDIUM"

    elif is_battle:
        if near_call_wall or near_em_hi:
            verdict = "WALL-TRADE"
            setup = f"Short near Call Wall ({call_wall or em_upper:.2f}). "
            setup += f"Target opposite wall / Put Wall ({put_wall or em_lower:.2f}). "
            setup += "Use wider stops — battle zone means big swings that reverse."
            invalidation = f"Close above Call Wall ({call_wall or em_upper:.2f})"
            confidence = "MEDIUM"
        elif near_put_wall or near_em_lo:
            verdict = "WALL-TRADE"
            setup = f"Long near Put Wall ({put_wall or em_lower:.2f}). "
            setup += f"Target opposite wall / Call Wall ({call_wall or em_upper:.2f}). "
            setup += "Use wider stops — battle zone means big swings that reverse."
            invalidation = f"Close below Put Wall ({put_wall or em_lower:.2f})"
            confidence = "MEDIUM"
        else:
            verdict = "WALL-TRADE"
            setup = f"Battle zone — price at {em_pos_pct:.0f}% of EM. "
            setup += "Trade wall-to-wall. Fade near walls, target opposite wall."
            invalidation = "Wall break with candle close"
            confidence = "LOW"

    else:  # Neutral GEX
        verdict = "NEUTRAL"
        setup = f"Neutral GEX regime. Price at {em_pos_pct:.0f}% of EM range. "
        setup += "No strong dealer positioning signal. Observe and wait for regime to clarify."
        invalidation = "N/A — observation only"
        confidence = "LOW"

    # Build the full read string
    read_parts = [
        f"REGIME: {regime_upper} ({label_upper})",
        f"EM POSITION: {em_pos_pct:.0f}% of range [{em_lower:.2f} - {em_upper:.2f}]",
        f"VERDICT: {verdict} (confidence: {confidence})",
        f"SETUP: {setup}",
        f"INVALIDATION: {invalidation}",
    ]
    read_str = " | ".join(read_parts)

    return {
        "verdict": verdict,
        "setup": setup,
        "invalidation": invalidation,
        "confidence": confidence,
        "em_position_pct": round(em_pos_pct, 1),
        "regime": regime_upper,
        "regime_label": label_upper,
        "read": read_str,
    }


def format_confluence_block(verdict_data: dict) -> str:
    """Format the confluence verdict into a cheat-sheet block."""
    if not verdict_data or "read" not in verdict_data:
        return "== GEX × EM CONFLUENCE ==\nNo confluence data available."

    lines = ["== GEX × EM CONFLUENCE =="]
    v = verdict_data
    lines.append(f"• Regime: {v.get('regime', 'N/A')} ({v.get('regime_label', 'N/A')})")
    lines.append(f"• EM Position: {v.get('em_position_pct', 'N/A')}% of range")
    lines.append(f"• Verdict: {v.get('verdict', 'N/A')} (confidence: {v.get('confidence', 'N/A')})")
    lines.append(f"• Setup: {v.get('setup', 'N/A')}")
    lines.append(f"• Invalidation: {v.get('invalidation', 'N/A')}")
    return "\n".join(lines)