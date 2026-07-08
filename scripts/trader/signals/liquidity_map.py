"""C5: ICT Liquidity Map.

Based on ICT's May 2025 X Space teachings. Identifies the raid target before the real move.
Bias determines which liquidity gets raided: bullish → lows raided, bearish → highs raided.
News tier determines which session's liquidity is targeted.
"""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)


def build_liquidity_map(bias: str, nq_status: dict, overnight: dict,
                        ict: dict, news_tier: str = "NONE") -> dict:
    """Build the ICT liquidity raid map.

    Args:
        bias: "BULLISH" / "BEARISH" / "NEUTRAL"
        nq_status: NQStatsEngine get_latest_status() output
        overnight: build_overnight_context() output
        ict: compute_ict_from_htf() output
        news_tier: "HIGH" / "MEDIUM" / "NONE"
    """
    from scripts.trader.config_loader import get_config
    cfg = get_config()
    ict_rules = cfg["ict_liquidity"]

    result = {
        "bias": bias,
        "raid_target": "unknown",
        "raid_target_level": None,
        "level_equality": "unknown",
        "weekly_position": "unknown",
        "entry_timing": ict_rules["raid_then_run"],
    }

    # Determine weekly position
    pd = ict.get("premium_discount", "unknown")
    result["weekly_position"] = "discount" if pd == "DISCOUNT" else ("premium" if pd == "PREMIUM" else "unknown")

    # Session levels for raid targets
    london_h = nq_status.get("london_high") if nq_status else None
    london_l = nq_status.get("london_low") if nq_status else None
    overnight_low = overnight.get("low") if overnight else None
    overnight_high = overnight.get("high") if overnight else None
    asia_l = None
    asia_h = None
    # Try to get Asia levels from nq_status if available
    if nq_status and "asia_high" in nq_status:
        asia_h = nq_status["asia_high"]
    if nq_status and "asia_low" in nq_status:
        asia_l = nq_status["asia_low"]

    # Select raid target based on bias and news tier
    if bias == "BULLISH":
        # Bullish → expect lows to be raided before the real move up
        if news_tier == "HIGH":
            target_name = "Asian low"
            target_level = asia_l or overnight_low
        elif news_tier == "MEDIUM":
            target_name = "London low"
            target_level = london_l or overnight_low
        else:
            # No news → based on Premium/Discount
            if result["weekly_position"] == "discount":
                target_name = "London low"
                target_level = london_l or overnight_low
            else:
                target_name = "Pre-Market low"
                target_level = overnight_low
        result["raid_target"] = target_name
        result["raid_target_level"] = round(target_level, 2) if target_level else None

    elif bias == "BEARISH":
        # Bearish → expect highs to be raided before the real move down
        if news_tier == "HIGH":
            target_name = "Asian high"
            target_level = asia_h or overnight_high
        elif news_tier == "MEDIUM":
            target_name = "London high"
            target_level = london_h or overnight_high
        else:
            if result["weekly_position"] == "premium":
                target_name = "London high"
                target_level = london_h or overnight_high
            else:
                target_name = "Pre-Market high"
                target_level = overnight_high
        result["raid_target"] = target_name
        result["raid_target_level"] = round(target_level, 2) if target_level else None
    else:
        result["raid_target"] = "no clear bias — wait for direction"

    # Level equality check (ICT: relatively equal levels = higher raid probability)
    if london_h and london_l and abs(london_h - london_l) > 0:
        # Simple heuristic: if London range is small relative to typical, levels are "equal"
        range_pts = london_h - london_l
        if range_pts < 100:  # NQ heuristic
            result["level_equality"] = "relatively equal — higher raid probability"
        else:
            result["level_equality"] = "disparate — lower raid probability"

    return result


def format_liquidity_block(data: dict) -> str:
    lines = ["== ICT LIQUIDITY MAP =="]
    lines.append(f"Bias: {data['bias']}")
    lines.append(f"Raid target: {data['raid_target']} ({data['raid_target_level']}) before real move")
    lines.append(f"Level equality: {data['level_equality']}")
    lines.append(f"Weekly position: {data['weekly_position']} — {'expect deep retracements' if data['weekly_position'] == 'discount' else 'shallow, dont wait for deep pullbacks' if data['weekly_position'] == 'premium' else ''}")
    lines.append(f"Entry: {data['entry_timing']}")
    return "\n".join(lines)