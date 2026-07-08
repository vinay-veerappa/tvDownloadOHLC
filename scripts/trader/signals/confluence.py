"""C9: Confluence Assessment.

Evaluates 3 independent directional signals and determines conviction level + sizing.
Signals: (1) Overnight (Pre-NY + ALN), (2) RTH Open (Gap Up/Down/Inside), (3) Daily Chart (Candle Science)
Context (GEX, ICT, VIX, classification, calendar) adjusts execution, NOT direction.
"""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)


def classify_signal_overnight(pre_ny_status: str, aln_pattern: str) -> str:
    """Signal 1: Overnight direction from Herman Pre-NY + ALN.

    Args:
        pre_ny_status: "BROKE_LONDON_HIGH", "BROKE_LONDON_LOW", "INSIDE"
        aln_pattern: "LPEU", "LPED", "LEA", "AEL"
    """
    from scripts.trader.config_loader import get_config
    cfg = get_config()
    aln_bias = cfg["aln_patterns"].get(aln_pattern, {}).get("bias", "neutral")

    if pre_ny_status == "BROKE_LONDON_HIGH":
        return "BULLISH"  # 86.4%
    elif pre_ny_status == "BROKE_LONDON_LOW":
        return "BEARISH"  # 77.9%
    elif aln_bias == "bullish":
        return "BULLISH"
    elif aln_bias == "bearish":
        return "BEARISH"
    else:
        return "NEUTRAL"


def classify_signal_rth_open(rth_scenario: str) -> str:
    """Signal 2: RTH open scenario (independent of overnight)."""
    if rth_scenario == "GAP_UP":
        return "BULLISH"  # 70% hold
    elif rth_scenario == "GAP_DOWN":
        return "BEARISH"  # 60% hold
    else:  # INSIDE
        return "NEUTRAL"  # 74% one-side break, direction from ALN


def classify_signal_daily_chart(cs_data: dict) -> str:
    """Signal 3: Candle Science daily chart read."""
    if not cs_data or cs_data.get("n_matches", 0) == 0:
        return "NEUTRAL"
    p_bull = cs_data.get("p_bull", 50.0)
    p_bear = cs_data.get("p_bear", 50.0)
    edge = abs(p_bull - p_bear)

    from scripts.trader.config_loader import get_config
    threshold = get_config()["candle_science"]["edge_threshold"]

    if edge < threshold:
        return "NEUTRAL"
    return "BULLISH" if p_bull > p_bear else "BEARISH"


def assess_confluence(signal_1: str, signal_2: str, signal_3: str) -> dict:
    """Evaluate confluence of 3 independent signals.

    Returns:
        dict with confluence level (HIGH/MEDIUM/LOW), sizing, conviction note
    """
    from scripts.trader.config_loader import get_config
    cfg = get_config()["confluence"]

    signals = [signal_1, signal_2, signal_3]
    bull_count = signals.count("BULLISH")
    bear_count = signals.count("BEARISH")
    neutral_count = signals.count("NEUTRAL")

    # Count directional agreement (ignore neutrals)
    directional = [s for s in signals if s != "NEUTRAL"]
    if not directional:
        return {
            "overnight_signal": signal_1, "rth_open_signal": signal_2, "daily_chart_signal": signal_3,
            "confluence": "LOW", "sizing": cfg["low"]["sizing"],
            "conviction_note": "All neutral — no directional signal. Wait for open to resolve.",
        }

    if all(s == directional[0] for s in directional) and len(directional) >= 2:
        level = "HIGH"
        sizing = cfg["high"]["sizing"]
        note = f"All {len(directional)} directional signals agree ({directional[0]}) — {cfg['high']['read']}"
    elif len(directional) >= 2 and (bull_count > bear_count or bear_count > bull_count):
        level = "MEDIUM"
        sizing = cfg["medium"]["sizing"]
        dominant = "BULLISH" if bull_count > bear_count else "BEARISH"
        note = f"2 of 3 lean {dominant} — {cfg['medium']['read']}"
    else:
        level = "LOW"
        sizing = cfg["low"]["sizing"]
        note = f"Bull/bear conflict — {cfg['low']['read']}"

    return {
        "overnight_signal": signal_1,
        "rth_open_signal": signal_2,
        "daily_chart_signal": signal_3,
        "confluence": level,
        "sizing": sizing,
        "conviction_note": note,
    }


def format_confluence_block(data: dict) -> str:
    lines = ["== CONFLUENCE ASSESSMENT =="]
    lines.append(f"Signal 1 (Overnight): {data['overnight_signal']}")
    lines.append(f"Signal 2 (RTH Open): {data['rth_open_signal']}")
    lines.append(f"Signal 3 (Daily Chart): {data['daily_chart_signal']}")
    lines.append(f"Confluence: {data['confluence']} → sizing {data['sizing']:.0%}")
    lines.append(f"Note: {data['conviction_note']}")
    return "\n".join(lines)