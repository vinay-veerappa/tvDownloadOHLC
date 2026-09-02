"""Algorithmic Wargaming Trajectory and 4-Outcome Elimination Engine

Mickey & Austin 4-Outcome Framework:
1. Long True (LT)   - Breakout > NY1 High sustains trend expansion
2. Long False (LF)  - Breakout > NY1 High fails, reverses through Mid, sweeps NY1 Low
3. Short True (ST)  - Breakout < NY1 Low sustains trend expansion
4. Short False (SF) - Breakout < NY1 Low fails, reverses through Mid, sweeps NY1 High

Each outcome has distinct Target Box coordinates, Mode Times, and Trajectory paths.
"""
from __future__ import annotations

from typing import Dict, Any, List, Tuple
from datetime import datetime, date, time, timedelta
import pandas as pd
import pytz

ET = pytz.timezone("America/New_York")


def compute_wargame_probabilities_and_trajectories(
    ticker: str,
    target_date: date,
    spot_price: float,
    p12: Dict[str, Any],
    anchors: Dict[str, Any],
    sessions: Dict[str, Any],
    cs: Dict[str, Any],
    profiler_prediction: Dict[str, Any],
) -> Dict[str, Any]:
    """Compute level hit probabilities, magnet tiers, 4-outcome elimination tree, and outcome-specific target boxes."""
    t_dt = target_date
    ny1_pred = profiler_prediction.get("predictions", {}).get("NY1", {})
    rates_by_outcome = ny1_pred.get("level_hit_rates_per_outcome", {})

    rates_sf = rates_by_outcome.get("SF", {})
    rates_lf = rates_by_outcome.get("LF", {})
    rates_lt = rates_by_outcome.get("LT", {})
    rates_st = rates_by_outcome.get("ST", {})

    def get_hr(outcome_dict: dict, key: str, default_val: float) -> float:
        val = outcome_dict.get(key, {}).get("hit_rate")
        return float(val) if val is not None else default_val

    # NY1 Initial Range (07:30 - 08:30 ET)
    ny1_formed = anchors.get("ny1_formed", False)
    ny1_h = anchors.get("ny1_high", p12["high"])
    ny1_l = anchors.get("ny1_low", p12["low"])
    ny1_m = (ny1_h + ny1_l) / 2.0

    # 1. Base Probabilities for NY1
    base_probs = {
        "SF": 32.8,
        "LF": 33.3,
        "LT": 17.2,
        "ST": 16.5,
    }

    # 2. Elimination State based on Spot Price relative to NY1 Range Box
    if not ny1_formed:
        state = "INSIDE_RANGE"
        active_outcomes = ["SF", "LF", "LT", "ST"]
        eliminated_outcomes = []
        sf_conditional = base_probs["SF"]
        lf_conditional = base_probs["LF"]
        lt_conditional = base_probs["LT"]
        st_conditional = base_probs["ST"]
        state_desc = f"Pre-NY1 / Pre-Open: Spot ({spot_price:,.2f}) inside P12 Range ({p12['low']:,.2f} - {p12['high']:,.2f}). NY1 direction undetermined. All 4 outcome branches active."
    elif spot_price > ny1_h:
        state = "LONG_BREAKOUT"
        active_outcomes = ["LF", "LT"]
        eliminated_outcomes = ["SF", "ST"]
        lf_conditional = round(base_probs["LF"] / (base_probs["LF"] + base_probs["LT"]) * 100, 1)
        lt_conditional = round(base_probs["LT"] / (base_probs["LF"] + base_probs["LT"]) * 100, 1)
        sf_conditional = 0.0
        st_conditional = 0.0
        state_desc = f"Spot ({spot_price:,.2f}) > NY1 High ({ny1_h:,.2f}). ST & SF ELIMINATED. Active branch: LF ({lf_conditional}%) vs LT ({lt_conditional}%)."
    elif spot_price < ny1_l:
        state = "SHORT_BREAKOUT"
        active_outcomes = ["SF", "ST"]
        eliminated_outcomes = ["LF", "LT"]
        sf_conditional = round(base_probs["SF"] / (base_probs["SF"] + base_probs["ST"]) * 100, 1)
        st_conditional = round(base_probs["ST"] / (base_probs["SF"] + base_probs["ST"]) * 100, 1)
        lf_conditional = 0.0
        lt_conditional = 0.0
        state_desc = f"Spot ({spot_price:,.2f}) < NY1 Low ({ny1_l:,.2f}). LT & LF ELIMINATED. Active branch: SF ({sf_conditional}%) vs ST ({st_conditional}%)."
    else:
        state = "INSIDE_RANGE"
        active_outcomes = ["SF", "LF", "LT", "ST"]
        eliminated_outcomes = []
        sf_conditional = base_probs["SF"]
        lf_conditional = base_probs["LF"]
        lt_conditional = base_probs["LT"]
        st_conditional = base_probs["ST"]
        state_desc = f"Spot ({spot_price:,.2f}) inside NY1 Range ({ny1_l:,.2f} - {ny1_h:,.2f}). All 4 outcomes active. False Branch edge: 66.1% vs True 33.7%."

    # 3. Candle Science Distribution Targets
    bull_p30 = spot_price * (1.0 + cs["bull"]["p30"] / 100.0)
    bull_p50 = spot_price * (1.0 + cs["bull"]["p50"] / 100.0)
    bull_p70 = spot_price * (1.0 + cs["bull"]["p70"] / 100.0)

    bear_p30 = spot_price * (1.0 + cs["bear"]["p30"] / 100.0)
    bear_p50 = spot_price * (1.0 + cs["bear"]["p50"] / 100.0)
    bear_p70 = spot_price * (1.0 + cs["bear"]["p70"] / 100.0)

    def ts_at(hour: int, minute: int) -> int:
        return int(pd.Timestamp(datetime.combine(t_dt, time(hour, minute)), tz="America/New_York").timestamp())

    # 4. OUTCOME-SPECIFIC TARGET BOXES (Times & Prices)
    boxes_by_outcome = {
        "SF": {
            "lod": {
                "start_ts": ts_at(9, 30),
                "end_ts": ts_at(10, 15),
                "top": float(max(p12["low"], bear_p30)),
                "bottom": float(min(bear_p50, p12["low"] - 35.0)),
                "label": "🟢 SF LOD TARGET BOX (09:30-10:15 ET)",
                "time_desc": "09:30 – 10:15 ET",
            },
            "hod": {
                "start_ts": ts_at(13, 30),
                "end_ts": ts_at(16, 0),
                "bottom": float(min(p12["high"], bull_p30)),
                "top": float(max(bull_p50, p12["high"] + 45.0)),
                "label": "🔴 SF HOD TARGET BOX (13:30-16:00 ET)",
                "time_desc": "13:30 – 16:00 ET",
            }
        },
        "LF": {
            "hod": {
                "start_ts": ts_at(9, 30),
                "end_ts": ts_at(10, 15),
                "bottom": float(ny1_h),
                "top": float(max(ny1_h + 35.0, bull_p30)),
                "label": "🔴 LF HOD TARGET BOX (09:30-10:15 ET)",
                "time_desc": "09:30 – 10:15 ET",
            },
            "lod": {
                "start_ts": ts_at(13, 30),
                "end_ts": ts_at(16, 0),
                "top": float(min(ny1_l, bear_p30)),
                "bottom": float(min(bear_p50, ny1_l - 45.0)),
                "label": "🟢 LF LOD TARGET BOX (13:30-16:00 ET)",
                "time_desc": "13:30 – 16:00 ET",
            }
        },
        "LT": {
            "lod": {
                "start_ts": ts_at(9, 30),
                "end_ts": ts_at(9, 45),
                "top": float(ny1_h),
                "bottom": float(ny1_m),
                "label": "🟢 LT LOD BASELINE (09:30-09:45 ET)",
                "time_desc": "09:30 – 09:45 ET",
            },
            "hod": {
                "start_ts": ts_at(14, 30),
                "end_ts": ts_at(16, 15),
                "bottom": float(bull_p50),
                "top": float(bull_p70),
                "label": "🔴 LT HOD EXTENSION (14:30-16:15 ET)",
                "time_desc": "14:30 – 16:15 ET",
            }
        },
        "ST": {
            "hod": {
                "start_ts": ts_at(9, 30),
                "end_ts": ts_at(9, 45),
                "top": float(ny1_m),
                "bottom": float(ny1_l),
                "label": "🔴 ST HOD BASELINE (09:30-09:45 ET)",
                "time_desc": "09:30 – 09:45 ET",
            },
            "lod": {
                "start_ts": ts_at(14, 30),
                "end_ts": ts_at(16, 15),
                "top": float(bear_p50),
                "bottom": float(bear_p70),
                "label": "🟢 ST LOD EXTENSION (14:30-16:15 ET)",
                "time_desc": "14:30 – 16:15 ET",
            }
        },
    }

    # 5. TRAJECTORIES FOR ALL 4 OUTCOMES
    # 1. SF (Short False - Primary Bullish Mean Reversion)
    traj_sf = [
        {"ts": ts_at(9, 30), "price": spot_price, "desc": "09:30 RTH Open"},
        {"ts": ts_at(9, 50), "price": (boxes_by_outcome["SF"]["lod"]["top"] + boxes_by_outcome["SF"]["lod"]["bottom"]) / 2.0, "desc": "09:50 False Sweep < NY1 Low"},
        {"ts": ts_at(10, 20), "price": p12["mid"], "desc": "10:20 Reversion > P12 Mid (88.5%)"},
        {"ts": ts_at(14, 30), "price": (boxes_by_outcome["SF"]["hod"]["top"] + boxes_by_outcome["SF"]["hod"]["bottom"]) / 2.0, "desc": "14:30 Target HOD Box (81.7%)"},
    ]

    # 2. LF (Long False - Bearish Mean Reversion)
    traj_lf = [
        {"ts": ts_at(9, 30), "price": spot_price, "desc": "09:30 RTH Open"},
        {"ts": ts_at(9, 50), "price": (boxes_by_outcome["LF"]["hod"]["top"] + boxes_by_outcome["LF"]["hod"]["bottom"]) / 2.0, "desc": "09:50 Long Trap > NY1 High"},
        {"ts": ts_at(10, 20), "price": p12["mid"], "desc": "10:20 Rejection < P12 Mid (88.5%)"},
        {"ts": ts_at(14, 30), "price": (boxes_by_outcome["LF"]["lod"]["top"] + boxes_by_outcome["LF"]["lod"]["bottom"]) / 2.0, "desc": "14:30 Target LOD Box"},
    ]

    # 3. LT (Long True - Bullish Trend Expansion)
    traj_lt = [
        {"ts": ts_at(9, 30), "price": spot_price, "desc": "09:30 RTH Open"},
        {"ts": ts_at(9, 45), "price": ny1_h + 10.0, "desc": "09:45 Acceptance > NY1 High"},
        {"ts": ts_at(10, 30), "price": ny1_h + 25.0, "desc": "10:30 Trend Continuation"},
        {"ts": ts_at(15, 0), "price": (boxes_by_outcome["LT"]["hod"]["top"] + boxes_by_outcome["LT"]["hod"]["bottom"]) / 2.0, "desc": "15:00 Bullish Expansion to P70"},
    ]

    # 4. ST (Short True - Bearish Trend Expansion)
    traj_st = [
        {"ts": ts_at(9, 30), "price": spot_price, "desc": "09:30 RTH Open"},
        {"ts": ts_at(9, 45), "price": ny1_l - 10.0, "desc": "09:45 Acceptance < NY1 Low"},
        {"ts": ts_at(10, 30), "price": ny1_l - 25.0, "desc": "10:30 Trend Continuation"},
        {"ts": ts_at(15, 0), "price": (boxes_by_outcome["ST"]["lod"]["top"] + boxes_by_outcome["ST"]["lod"]["bottom"]) / 2.0, "desc": "15:00 Bearish Expansion to P70"},
    ]

    # 6. Build Magnet Hierarchy for active outcome
    active_rates = rates_sf if p12.get("bias") == "BULLISH" else rates_lf
    magnets_list = [
        {"name": "P12 MIDLINE", "price": p12["mid"], "prob": get_hr(active_rates, "p12m", 88.5), "tier": "Tier 1 (Core Magnet)", "color": "#f59e0b", "style": "solid", "role": "Equilibrium Switch & Primary Mean-Reversion Target"},
        {"name": "MIDNIGHT OPEN", "price": anchors.get("midnight_open"), "prob": get_hr(active_rates, "midnight_open", 84.1), "tier": "Tier 1 (Core Magnet)", "color": "#3b82f6", "style": "dotted", "role": "Daily Session Anchor & Opening Retest Level"},
        {"name": "P12 HIGH", "price": p12["high"], "prob": get_hr(active_rates, "p12h", 81.7), "tier": "Tier 1 (Core Magnet)", "color": "#ef4444", "style": "dashed", "role": "Overnight Liquidity Ceiling & Bullish Goalpost"},
        {"name": "NY1 MIDPOINT", "price": ny1_m, "prob": get_hr(active_rates, "ny1_mid", 99.4), "tier": "Tier 1 (Core Magnet)", "color": "#f97316", "style": "dashed", "role": "Pre-Market Reference Range Balance (07:30-08:30)"},
        {"name": "07:30 OPEN", "price": anchors.get("open_0730"), "prob": get_hr(active_rates, "open_0730", 74.7), "tier": "Tier 2 (Structural Pivot)", "color": "#9ca3af", "style": "dotted", "role": "Pre-Market Institutional Auction Baseline"},
        {"name": "P12 LOW", "price": p12["low"], "prob": get_hr(active_rates, "p12l", 68.9), "tier": "Tier 2 (Structural Pivot)", "color": "#10b981", "style": "dashed", "role": "Overnight Liquidity Floor & Primary Sweep Zone"},
        {"name": "PREV DAY MID (PDM)", "price": anchors.get("pdm"), "prob": get_hr(active_rates, "pdm", 65.0), "tier": "Tier 2 (Structural Pivot)", "color": "#06b6d4", "style": "dashed", "role": "Higher Timeframe 50% Balance Point"},
        {"name": "PREV DAY HIGH (PDH)", "price": anchors.get("pdh"), "prob": get_hr(active_rates, "pdh", 58.6), "tier": "Tier 3 (Expansion Outlier)", "color": "#eab308", "style": "solid", "role": "Daily Range Expansion Target"},
        {"name": "SETTLEMENT", "price": anchors.get("settle_price"), "prob": get_hr(active_rates, "settle", 49.1), "tier": "Tier 3 (Expansion Outlier)", "color": "#f97316", "style": "solid", "role": "Institutional Closing Basis"},
        {"name": "PREV DAY LOW (PDL)", "price": anchors.get("pdl"), "prob": get_hr(active_rates, "pdl", 41.9), "tier": "Tier 3 (Expansion Outlier)", "color": "#ec4899", "style": "solid", "role": "Downside Liquidity Pool"},
    ]
    valid_magnets = [m for m in magnets_list if m["price"] is not None]
    valid_magnets.sort(key=lambda x: x["prob"], reverse=True)

    return {
        "state": state,
        "state_desc": state_desc,
        "active_outcomes": active_outcomes,
        "eliminated_outcomes": eliminated_outcomes,
        "base_probs": base_probs,
        "conditional_probs": {
            "SF": sf_conditional,
            "LF": lf_conditional,
            "LT": lt_conditional,
            "ST": st_conditional,
        },
        "magnets": valid_magnets,
        "boxes_by_outcome": boxes_by_outcome,
        # Default boxes for active
        "lod_box": boxes_by_outcome["SF"]["lod"],
        "hod_box": boxes_by_outcome["SF"]["hod"],
        "trajectories": {
            "SF": traj_sf,
            "LF": traj_lf,
            "LT": traj_lt,
            "ST": traj_st,
        },
        "directional_narrative": (
            f"Decision Tree Status: {state_desc} "
            f"P12 Midline ({p12['mid']:,.2f}) has an 88.5% touch probability and Midnight Open ({anchors.get('midnight_open', p12['mid']):,.2f}) has an 84.1% touch probability. "
            f"In NY1, False Reversions (66.1%) hold a 2:1 statistical advantage over True Trend Expansions (33.7%). "
            f"Wait for the initial 09:30 directional sweep to eliminate 2 branches, then execute the False Reversion if rejected before 09:45 AM."
        )
    }
