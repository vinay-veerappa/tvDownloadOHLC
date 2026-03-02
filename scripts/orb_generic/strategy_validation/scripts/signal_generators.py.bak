"""
signal_generators.py — Entry strategy signal generators
=========================================================
Each generator takes standardized inputs and returns a list of StrategySignal.
All use percentage-based normalization for regime independence.
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import List, Optional, Dict
from scripts.market_structure import (
    detect_swings, get_swing_levels, detect_structure_shifts,
    detect_order_blocks, detect_fvgs, fib_zone,
    compute_vwap, compute_vwap_bands, compute_atr,
    pct_of_price, points_from_pct,
)


@dataclass
class StrategySignal:
    trade_date: str
    entry_bar_idx: int
    entry_time: str
    direction: str       # "long" or "short"
    entry_price: float
    stop_price: float
    target_price: float
    risk_pct: float      # risk as % of price
    reward_pct: float    # reward as % of price
    rr_ratio: float      # reward / risk
    signal_name: str
    confidence: float = 1.0  # 0-1, for multi-confirmation scoring


# ---------------------------------------------------------------------------
# Shared: OR context and bias
# ---------------------------------------------------------------------------

def get_day_context(day_bars: pd.DataFrame, or_high: float, or_low: float,
                    or_end_idx: int) -> dict:
    """Compute context for a single day's trading.

    Returns dict with all the structural info signal generators need.
    """
    o = day_bars["open"].values
    h = day_bars["high"].values
    l = day_bars["low"].values
    c = day_bars["close"].values
    v = day_bars["volume"].values

    or_mid = (or_high + or_low) / 2
    or_width = or_high - or_low
    ref_price = or_mid  # reference price for % calculations
    or_width_pct = pct_of_price(or_width, ref_price)

    # Post-OR bars
    post_h = h[or_end_idx:]
    post_l = l[or_end_idx:]
    post_c = c[or_end_idx:]
    post_o = o[or_end_idx:]
    post_v = v[or_end_idx:]

    # ATR for normalization (use all bars available)
    atr = compute_atr(h, l, c, period=14)
    current_atr = atr[or_end_idx] if or_end_idx < len(atr) else atr[-1]

    # VWAP from session start
    reset = np.zeros(len(h), dtype=bool)
    reset[0] = True
    vwap = compute_vwap(h, l, c, v, reset_mask=reset)

    # Detect structures in post-OR bars
    if len(post_h) > 10:
        swing_h, swing_l = detect_swings(post_h, post_l, lookback=2, lookforward=2)
        last_sh, last_sl = get_swing_levels(post_h, post_l, swing_h, swing_l)
    else:
        swing_h = swing_l = np.zeros(len(post_h), dtype=bool)
        last_sh = last_sl = np.full(len(post_h), np.nan)

    return {
        "open": o, "high": h, "low": l, "close": c, "volume": v,
        "post_open": post_o, "post_high": post_h, "post_low": post_l,
        "post_close": post_c, "post_volume": post_v,
        "or_high": or_high, "or_low": or_low, "or_mid": or_mid,
        "or_width": or_width, "or_width_pct": or_width_pct,
        "ref_price": ref_price, "atr": current_atr,
        "vwap": vwap, "or_end_idx": or_end_idx,
        "swing_highs": swing_h, "swing_lows": swing_l,
        "last_swing_high": last_sh, "last_swing_low": last_sl,
        "bar_times": day_bars.index,
    }


def make_signal(td_str: str, bar_idx: int, bar_times, direction: str,
                entry: float, stop: float, target: float,
                ref_price: float, name: str, confidence: float = 1.0) -> StrategySignal:
    """Helper to construct a signal with auto-computed percentages."""
    risk = abs(entry - stop)
    reward = abs(target - entry)
    risk_pct = pct_of_price(risk, ref_price)
    reward_pct = pct_of_price(reward, ref_price)
    rr = reward / risk if risk > 0 else 0

    return StrategySignal(
        trade_date=td_str,
        entry_bar_idx=bar_idx,
        entry_time=str(bar_times[bar_idx]) if bar_idx < len(bar_times) else "",
        direction=direction,
        entry_price=entry,
        stop_price=stop,
        target_price=target,
        risk_pct=risk_pct,
        reward_pct=reward_pct,
        rr_ratio=rr,
        signal_name=name,
        confidence=confidence,
    )


# ---------------------------------------------------------------------------
# Strategy 1B: Breakout + Retest
# ---------------------------------------------------------------------------

def generate_breakout_retest(ctx: dict, td_str: str, bias: Optional[str] = None,
                              params: dict = None) -> List[StrategySignal]:
    """Wait for OR break, then enter on retest of OR level as S/R.

    Params:
        retest_tolerance_pct: how close price must come to OR level (% of price)
        max_risk_pct: maximum risk as % of price
        target_rr: reward:risk ratio for target
        max_bars_to_retest: max bars to wait for retest after breakout
    """
    if params is None:
        params = {"retest_tolerance_pct": 0.05, "max_risk_pct": 0.15,
                  "target_rr": 1.5, "max_bars_to_retest": 30, "stop_buffer_pct": 0.03}

    signals = []
    ph, pl, pc = ctx["post_high"], ctx["post_low"], ctx["post_close"]
    or_h, or_l = ctx["or_high"], ctx["or_low"]
    ref = ctx["ref_price"]
    tol = points_from_pct(params["retest_tolerance_pct"], ref)
    stop_buf = points_from_pct(params["stop_buffer_pct"], ref)
    offset = ctx["or_end_idx"]

    for i in range(len(ph)):
        # Bullish breakout: close above OR high
        if bias != "short" and pc[i] > or_h:
            # Look for retest: price comes back to within tolerance of OR high
            for j in range(i + 1, min(i + params["max_bars_to_retest"], len(pl))):
                if pl[j] <= or_h + tol and pc[j] > or_h:
                    # Retest confirmed — enter long
                    entry = pc[j]
                    stop = or_h - stop_buf
                    risk = entry - stop
                    if pct_of_price(risk, ref) > params["max_risk_pct"]:
                        break
                    target = entry + risk * params["target_rr"]
                    signals.append(make_signal(
                        td_str, offset + j, ctx["bar_times"], "long",
                        entry, stop, target, ref, "breakout_retest"))
                    break
            break  # one signal per day per direction

        # Bearish breakout: close below OR low
        if bias != "long" and pc[i] < or_l:
            for j in range(i + 1, min(i + params["max_bars_to_retest"], len(ph))):
                if ph[j] >= or_l - tol and pc[j] < or_l:
                    entry = pc[j]
                    stop = or_l + stop_buf
                    risk = stop - entry
                    if pct_of_price(risk, ref) > params["max_risk_pct"]:
                        break
                    target = entry - risk * params["target_rr"]
                    signals.append(make_signal(
                        td_str, offset + j, ctx["bar_times"], "short",
                        entry, stop, target, ref, "breakout_retest"))
                    break
            break

    return signals


# ---------------------------------------------------------------------------
# Strategy 2A: Fibonacci Discount Entry
# ---------------------------------------------------------------------------

def generate_fib_discount(ctx: dict, td_str: str, bias: Optional[str] = None,
                           params: dict = None) -> List[StrategySignal]:
    """Enter at Fibonacci discount/premium zone within OR.

    For long bias: wait for price to dip to discount zone (below 38.2% of OR)
    For short bias: wait for price to rise to premium zone (above 61.8% of OR)
    """
    if params is None:
        params = {"max_risk_pct": 0.15, "target_rr": 1.5,
                  "stop_buffer_pct": 0.03, "max_bars_to_entry": 60}

    signals = []
    ph, pl, pc = ctx["post_high"], ctx["post_low"], ctx["post_close"]
    or_h, or_l = ctx["or_high"], ctx["or_low"]
    ref = ctx["ref_price"]
    stop_buf = points_from_pct(params["stop_buffer_pct"], ref)
    offset = ctx["or_end_idx"]

    discount_low, discount_high = fib_zone(or_h, or_l, "discount")
    premium_low, premium_high = fib_zone(or_h, or_l, "premium")

    for i in range(min(params["max_bars_to_entry"], len(pl))):
        # Long at discount
        if bias in (None, "long") and pl[i] <= discount_high and pc[i] > discount_low:
            entry = pc[i]
            stop = or_l - stop_buf
            risk = entry - stop
            if risk <= 0 or pct_of_price(risk, ref) > params["max_risk_pct"]:
                continue
            target = entry + risk * params["target_rr"]
            signals.append(make_signal(
                td_str, offset + i, ctx["bar_times"], "long",
                entry, stop, target, ref, "fib_discount"))
            return signals

        # Short at premium
        if bias in (None, "short") and ph[i] >= premium_low and pc[i] < premium_high:
            entry = pc[i]
            stop = or_h + stop_buf
            risk = stop - entry
            if risk <= 0 or pct_of_price(risk, ref) > params["max_risk_pct"]:
                continue
            target = entry - risk * params["target_rr"]
            signals.append(make_signal(
                td_str, offset + i, ctx["bar_times"], "short",
                entry, stop, target, ref, "fib_discount"))
            return signals

    return signals


# ---------------------------------------------------------------------------
# Strategy 3A: Order Block at OR Boundary
# ---------------------------------------------------------------------------

def generate_ob_entry(ctx: dict, td_str: str, bias: Optional[str] = None,
                       params: dict = None) -> List[StrategySignal]:
    """Enter at an order block near the OR boundary after breakout."""
    if params is None:
        params = {"max_risk_pct": 0.15, "target_rr": 2.0,
                  "stop_buffer_pct": 0.02, "ob_proximity_pct": 0.1}

    signals = []
    o, h, l, c = ctx["post_open"], ctx["post_high"], ctx["post_low"], ctx["post_close"]
    or_h, or_l = ctx["or_high"], ctx["or_low"]
    ref = ctx["ref_price"]
    stop_buf = points_from_pct(params["stop_buffer_pct"], ref)
    prox = points_from_pct(params["ob_proximity_pct"], ref)
    offset = ctx["or_end_idx"]

    if len(o) < 15:
        return signals

    # Detect OBs in post-OR bars
    obs = detect_order_blocks(o, h, l, c, displacement_mult=1.5)
    if obs.empty:
        return signals

    for _, ob in obs.iterrows():
        ob_idx = int(ob["bar_idx"])
        disp_idx = int(ob["displacement_bar"])

        # Bullish OB near OR boundary → long entry
        if ob["ob_type"] == "bullish" and bias != "short":
            if abs(ob["ob_mid"] - or_h) < prox or ob["ob_mid"] > or_l:
                # Wait for retest of OB
                for j in range(disp_idx + 1, min(disp_idx + 30, len(l))):
                    if l[j] <= ob["ob_high"] and c[j] > ob["ob_low"]:
                        entry = c[j]
                        stop = ob["ob_low"] - stop_buf
                        risk = entry - stop
                        if risk <= 0 or pct_of_price(risk, ref) > params["max_risk_pct"]:
                            break
                        target = entry + risk * params["target_rr"]
                        signals.append(make_signal(
                            td_str, offset + j, ctx["bar_times"], "long",
                            entry, stop, target, ref, "ob_entry"))
                        return signals

        # Bearish OB → short entry
        elif ob["ob_type"] == "bearish" and bias != "long":
            if abs(ob["ob_mid"] - or_l) < prox or ob["ob_mid"] < or_h:
                for j in range(disp_idx + 1, min(disp_idx + 30, len(h))):
                    if h[j] >= ob["ob_low"] and c[j] < ob["ob_high"]:
                        entry = c[j]
                        stop = ob["ob_high"] + stop_buf
                        risk = stop - entry
                        if risk <= 0 or pct_of_price(risk, ref) > params["max_risk_pct"]:
                            break
                        target = entry - risk * params["target_rr"]
                        signals.append(make_signal(
                            td_str, offset + j, ctx["bar_times"], "short",
                            entry, stop, target, ref, "ob_entry"))
                        return signals

    return signals


# ---------------------------------------------------------------------------
# Strategy 4B: FVG on Displacement Break
# ---------------------------------------------------------------------------

def generate_fvg_displacement(ctx: dict, td_str: str, bias: Optional[str] = None,
                               params: dict = None) -> List[StrategySignal]:
    """Enter on FVG fill after a displacement breakout of OR."""
    if params is None:
        params = {"max_risk_pct": 0.15, "target_rr": 1.5,
                  "stop_buffer_pct": 0.02, "min_fvg_pct": 0.02,
                  "max_bars_to_fill": 30}

    signals = []
    h, l, c = ctx["post_high"], ctx["post_low"], ctx["post_close"]
    or_h, or_l = ctx["or_high"], ctx["or_low"]
    ref = ctx["ref_price"]
    stop_buf = points_from_pct(params["stop_buffer_pct"], ref)
    offset = ctx["or_end_idx"]

    if len(h) < 5:
        return signals

    fvgs = detect_fvgs(h, l, min_gap_pct=params["min_fvg_pct"])
    if fvgs.empty:
        return signals

    for _, fvg in fvgs.iterrows():
        fvg_idx = int(fvg["bar_idx"])

        # Bullish FVG after upside break
        if fvg["fvg_type"] == "bullish" and bias != "short":
            if fvg["fvg_bottom"] >= or_l:  # FVG is above OR low (meaningful)
                # Wait for price to fill to FVG mid
                for j in range(fvg_idx + 1, min(fvg_idx + params["max_bars_to_fill"], len(l))):
                    if l[j] <= fvg["fvg_mid"]:
                        entry = max(c[j], fvg["fvg_bottom"])
                        stop = fvg["fvg_bottom"] - stop_buf
                        risk = entry - stop
                        if risk <= 0 or pct_of_price(risk, ref) > params["max_risk_pct"]:
                            break
                        target = entry + risk * params["target_rr"]
                        signals.append(make_signal(
                            td_str, offset + j, ctx["bar_times"], "long",
                            entry, stop, target, ref, "fvg_displacement"))
                        return signals

        # Bearish FVG after downside break
        elif fvg["fvg_type"] == "bearish" and bias != "long":
            if fvg["fvg_top"] <= or_h:
                for j in range(fvg_idx + 1, min(fvg_idx + params["max_bars_to_fill"], len(h))):
                    if h[j] >= fvg["fvg_mid"]:
                        entry = min(c[j], fvg["fvg_top"])
                        stop = fvg["fvg_top"] + stop_buf
                        risk = stop - entry
                        if risk <= 0 or pct_of_price(risk, ref) > params["max_risk_pct"]:
                            break
                        target = entry - risk * params["target_rr"]
                        signals.append(make_signal(
                            td_str, offset + j, ctx["bar_times"], "short",
                            entry, stop, target, ref, "fvg_displacement"))
                        return signals

    return signals


# ---------------------------------------------------------------------------
# Strategy 5B: CHOCH Fade
# ---------------------------------------------------------------------------

def generate_choch_fade(ctx: dict, td_str: str, bias: Optional[str] = None,
                         params: dict = None) -> List[StrategySignal]:
    """Enter on Change of Character after false OR breakout."""
    if params is None:
        params = {"max_risk_pct": 0.2, "target_rr": 1.5,
                  "stop_buffer_pct": 0.03, "swing_lookback": 2}

    signals = []
    o, h, l, c = ctx["post_open"], ctx["post_high"], ctx["post_low"], ctx["post_close"]
    or_h, or_l = ctx["or_high"], ctx["or_low"]
    ref = ctx["ref_price"]
    stop_buf = points_from_pct(params["stop_buffer_pct"], ref)
    offset = ctx["or_end_idx"]

    if len(h) < 15:
        return signals

    sh, sl = detect_swings(h, l, lookback=params["swing_lookback"],
                           lookforward=params["swing_lookback"])
    events = detect_structure_shifts(h, l, c, sh, sl)

    if events.empty:
        return signals

    for _, ev in events.iterrows():
        ev_bar = int(ev["bar_idx"])

        # Bullish CHOCH after bearish structure (price broke OR low, then shifted bullish)
        if ev["type"] == "choch" and ev["direction"] == "bullish" and bias != "short":
            # Verify: was there a prior sweep of OR low?
            if np.any(l[:ev_bar] < or_l):
                entry = c[ev_bar]
                # Stop below the swing low that preceded the CHOCH
                recent_lows = l[:ev_bar][sl[:ev_bar]] if np.any(sl[:ev_bar]) else l[:ev_bar]
                stop = np.min(recent_lows[-3:]) - stop_buf if len(recent_lows) > 0 else or_l - stop_buf
                risk = entry - stop
                if risk <= 0 or pct_of_price(risk, ref) > params["max_risk_pct"]:
                    continue
                target = entry + risk * params["target_rr"]
                signals.append(make_signal(
                    td_str, offset + ev_bar, ctx["bar_times"], "long",
                    entry, stop, target, ref, "choch_fade"))
                return signals

        # Bearish CHOCH after bullish structure
        elif ev["type"] == "choch" and ev["direction"] == "bearish" and bias != "long":
            if np.any(h[:ev_bar] > or_h):
                entry = c[ev_bar]
                recent_highs = h[:ev_bar][sh[:ev_bar]] if np.any(sh[:ev_bar]) else h[:ev_bar]
                stop = np.max(recent_highs[-3:]) + stop_buf if len(recent_highs) > 0 else or_h + stop_buf
                risk = stop - entry
                if risk <= 0 or pct_of_price(risk, ref) > params["max_risk_pct"]:
                    continue
                target = entry - risk * params["target_rr"]
                signals.append(make_signal(
                    td_str, offset + ev_bar, ctx["bar_times"], "short",
                    entry, stop, target, ref, "choch_fade"))
                return signals

    return signals


# ---------------------------------------------------------------------------
# Strategy 6C: Full Multi-Confirmation
# ---------------------------------------------------------------------------

def generate_full_confluence(ctx: dict, td_str: str, bias: Optional[str] = None,
                              params: dict = None) -> List[StrategySignal]:
    """Require multiple confirmations: CHOCH/BOS + FVG or OB + Fib zone."""
    if params is None:
        params = {"max_risk_pct": 0.15, "target_rr": 2.0,
                  "stop_buffer_pct": 0.02, "min_confirmations": 2}

    signals = []
    o, h, l, c = ctx["post_open"], ctx["post_high"], ctx["post_low"], ctx["post_close"]
    or_h, or_l = ctx["or_high"], ctx["or_low"]
    ref = ctx["ref_price"]
    stop_buf = points_from_pct(params["stop_buffer_pct"], ref)
    offset = ctx["or_end_idx"]

    if len(h) < 15:
        return signals

    # Detect all structures
    sh, sl = detect_swings(h, l, lookback=2, lookforward=2)
    events = detect_structure_shifts(h, l, c, sh, sl)
    obs = detect_order_blocks(o, h, l, c, displacement_mult=1.5)
    fvgs = detect_fvgs(h, l, min_gap_pct=0.02)

    discount_low, discount_high = fib_zone(or_h, or_l, "discount")
    premium_low, premium_high = fib_zone(or_h, or_l, "premium")

    # Score each potential entry bar
    for i in range(5, len(c)):
        confirmations_long = 0
        confirmations_short = 0
        stop_long = or_l - stop_buf
        stop_short = or_h + stop_buf

        # Check CHOCH/BOS
        if not events.empty:
            recent = events[events["bar_idx"] <= i]
            if len(recent) > 0:
                last_ev = recent.iloc[-1]
                if last_ev["direction"] == "bullish" and last_ev["bar_idx"] >= i - 5:
                    confirmations_long += 1
                elif last_ev["direction"] == "bearish" and last_ev["bar_idx"] >= i - 5:
                    confirmations_short += 1

        # Check FVG
        if not fvgs.empty:
            for _, fvg in fvgs.iterrows():
                if fvg["fvg_type"] == "bullish" and l[i] <= fvg["fvg_top"] and c[i] > fvg["fvg_bottom"]:
                    confirmations_long += 1
                    stop_long = max(stop_long, fvg["fvg_bottom"] - stop_buf)
                elif fvg["fvg_type"] == "bearish" and h[i] >= fvg["fvg_bottom"] and c[i] < fvg["fvg_top"]:
                    confirmations_short += 1
                    stop_short = min(stop_short, fvg["fvg_top"] + stop_buf)

        # Check OB
        if not obs.empty:
            for _, ob in obs.iterrows():
                if ob["ob_type"] == "bullish" and l[i] <= ob["ob_high"] and c[i] > ob["ob_low"]:
                    confirmations_long += 1
                    stop_long = max(stop_long, ob["ob_low"] - stop_buf)
                elif ob["ob_type"] == "bearish" and h[i] >= ob["ob_low"] and c[i] < ob["ob_high"]:
                    confirmations_short += 1
                    stop_short = min(stop_short, ob["ob_high"] + stop_buf)

        # Check Fib zone
        if c[i] <= discount_high:
            confirmations_long += 1
        if c[i] >= premium_low:
            confirmations_short += 1

        # Generate signal if enough confirmations
        min_conf = params["min_confirmations"]

        if confirmations_long >= min_conf and bias != "short":
            entry = c[i]
            risk = entry - stop_long
            if risk > 0 and pct_of_price(risk, ref) <= params["max_risk_pct"]:
                target = entry + risk * params["target_rr"]
                conf_score = min(1.0, confirmations_long / 4.0)
                signals.append(make_signal(
                    td_str, offset + i, ctx["bar_times"], "long",
                    entry, stop_long, target, ref, "full_confluence", conf_score))
                return signals

        if confirmations_short >= min_conf and bias != "long":
            entry = c[i]
            risk = stop_short - entry
            if risk > 0 and pct_of_price(risk, ref) <= params["max_risk_pct"]:
                target = entry - risk * params["target_rr"]
                conf_score = min(1.0, confirmations_short / 4.0)
                signals.append(make_signal(
                    td_str, offset + i, ctx["bar_times"], "short",
                    entry, stop_short, target, ref, "full_confluence", conf_score))
                return signals

    return signals


# ---------------------------------------------------------------------------
# Strategy 2B: VWAP Mean Reversion (Tier 3)
# ---------------------------------------------------------------------------

def generate_vwap_reversion(ctx: dict, td_str: str, bias: Optional[str] = None,
                             params: dict = None) -> List[StrategySignal]:
    """Enter when price reverts to VWAP inside OR zone with directional bias."""
    if params is None:
        params = {"max_risk_pct": 0.15, "target_rr": 1.5,
                  "stop_buffer_pct": 0.03, "vwap_tolerance_pct": 0.03,
                  "max_bars_to_entry": 60}

    signals = []
    h, l, c = ctx["post_high"], ctx["post_low"], ctx["post_close"]
    vwap = ctx["vwap"]
    or_h, or_l = ctx["or_high"], ctx["or_low"]
    ref = ctx["ref_price"]
    stop_buf = points_from_pct(params["stop_buffer_pct"], ref)
    vwap_tol = points_from_pct(params["vwap_tolerance_pct"], ref)
    offset = ctx["or_end_idx"]

    post_vwap = vwap[offset:]

    for i in range(min(params["max_bars_to_entry"], len(c))):
        vw = post_vwap[i] if i < len(post_vwap) else ref

        # Price near VWAP and inside OR range
        near_vwap = abs(c[i] - vw) <= vwap_tol
        inside_or = or_l <= c[i] <= or_h

        if not (near_vwap and inside_or):
            continue

        # Long: price touching VWAP from above, VWAP is in lower half of OR
        if bias in (None, "long") and vw < ctx["or_mid"] and c[i] >= vw:
            entry = c[i]
            stop = or_l - stop_buf
            risk = entry - stop
            if risk <= 0 or pct_of_price(risk, ref) > params["max_risk_pct"]:
                continue
            target = entry + risk * params["target_rr"]
            signals.append(make_signal(
                td_str, offset + i, ctx["bar_times"], "long",
                entry, stop, target, ref, "vwap_reversion"))
            return signals

        # Short: price touching VWAP from below, VWAP in upper half
        if bias in (None, "short") and vw > ctx["or_mid"] and c[i] <= vw:
            entry = c[i]
            stop = or_h + stop_buf
            risk = stop - entry
            if risk <= 0 or pct_of_price(risk, ref) > params["max_risk_pct"]:
                continue
            target = entry - risk * params["target_rr"]
            signals.append(make_signal(
                td_str, offset + i, ctx["bar_times"], "short",
                entry, stop, target, ref, "vwap_reversion"))
            return signals

    return signals


# ---------------------------------------------------------------------------
# Strategy Registry
# ---------------------------------------------------------------------------

STRATEGIES = {
    "breakout_retest":   generate_breakout_retest,
    "fib_discount":      generate_fib_discount,
    "ob_entry":          generate_ob_entry,
    "fvg_displacement":  generate_fvg_displacement,
    "choch_fade":        generate_choch_fade,
    "full_confluence":   generate_full_confluence,
    "vwap_reversion":    generate_vwap_reversion,
}

ALL_STRATEGY_NAMES = list(STRATEGIES.keys())
