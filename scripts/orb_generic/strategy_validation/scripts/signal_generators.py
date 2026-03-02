"""
signal_generators.py v6 — Zone-Based Architecture
====================================================
All strategies build structural zones from 9:30 onward (including OR period),
then look for price to enter these zones post-OR with confirmation.

Zone types:
  - fib: Fibonacci retracement levels of OR (38.2, 50, 61.8, 78.6%)
  - fvg: Fair Value Gaps from 9:30 onward
  - ob: Order Blocks from 9:30 onward
  - choch: CHOCH level where structure shifted
  - or_boundary: OR high/low (for retest entries)
  - vwap: Dynamic VWAP level

Each zone has: price_high, price_low, zone_type, direction (long/short/both),
and a confluence score.
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple
from scripts.market_structure import (
    detect_swings, get_swing_levels, detect_structure_shifts,
    detect_order_blocks, detect_fvgs, fib_zone,
    compute_vwap, compute_atr,
    pct_of_price, points_from_pct,
)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class Zone:
    """A price zone where an entry may be taken."""
    zone_type: str       # "fib", "fvg", "ob", "choch", "or_boundary", "vwap"
    direction: str       # "long", "short", or "both"
    price_high: float    # upper boundary of zone
    price_low: float     # lower boundary of zone
    price_mid: float     # midpoint (typical entry target)
    stop_price: float    # suggested stop for this zone
    source_bar: int      # session-relative bar index where zone was created
    score: int = 1       # confluence score (higher = more confirmations)
    label: str = ""      # descriptive label for debugging


@dataclass
class StrategySignal:
    trade_date: str
    entry_bar_idx: int
    entry_time: str
    direction: str
    entry_price: float
    stop_price: float
    target_price: float
    risk_pct: float
    reward_pct: float
    rr_ratio: float
    signal_name: str
    confidence: float = 1.0
    ib_bias: str = ""
    first_formed: str = ""
    zones_hit: str = ""   # which zone types contributed to entry


# ---------------------------------------------------------------------------
# IB Bias
# ---------------------------------------------------------------------------

def compute_ib_bias(high: np.ndarray, low: np.ndarray,
                    or_start_idx: int, or_end_idx: int,
                    bias_minutes: int = 15) -> Tuple[str, str]:
    bias_end_idx = min(or_start_idx + bias_minutes, or_end_idx)
    if bias_end_idx <= or_start_idx:
        return "", "same"

    running_high = high[or_start_idx]
    running_low = low[or_start_idx]
    high_last_set = or_start_idx
    low_last_set = or_start_idx

    for i in range(or_start_idx + 1, bias_end_idx):
        if i >= len(high):
            break
        if high[i] > running_high:
            running_high = high[i]
            high_last_set = i
        if low[i] < running_low:
            running_low = low[i]
            low_last_set = i

    if high_last_set < low_last_set:
        return "short", "high"
    elif low_last_set < high_last_set:
        return "long", "low"
    else:
        return "", "same"


# ---------------------------------------------------------------------------
# Zone Builder — builds ALL zones from 9:30 onward
# ---------------------------------------------------------------------------

def build_zones(day_bars: pd.DataFrame, or_high: float, or_low: float,
                or_start_idx: int, or_end_idx: int,
                swing_lookback: int = 2,
                min_fvg_pct: float = 0.02,
                disp_mult: float = 1.5,
                stop_buffer_pct: float = 0.03,
                vwap_tol_pct: float = 0.03) -> Tuple[List[Zone], dict]:
    """Build all structural zones from session start (9:30).

    Returns:
        zones: list of Zone objects
        context: dict with arrays and metadata needed for entry scanning
    """
    h = day_bars["high"].values
    l = day_bars["low"].values
    o = day_bars["open"].values
    c = day_bars["close"].values
    v = day_bars["volume"].values

    or_mid = (or_high + or_low) / 2
    or_width = or_high - or_low
    ref = or_mid
    stop_buf = points_from_pct(stop_buffer_pct, ref)

    zones = []

    # === FIB ZONES ===
    # Multiple fib levels as zones, not just 38.2%
    fib_levels = {
        "fib_236": (or_low + 0.236 * or_width, "long"),
        "fib_382": (or_low + 0.382 * or_width, "long"),    # discount
        "fib_500": (or_low + 0.500 * or_width, "both"),    # equilibrium
        "fib_618": (or_low + 0.618 * or_width, "short"),   # premium
        "fib_786": (or_low + 0.786 * or_width, "short"),
    }

    # Zone thickness = small % of OR width
    fib_thickness = or_width * 0.05  # 5% of OR width as zone thickness

    for fib_name, (fib_price, fib_dir) in fib_levels.items():
        # For "both" direction (50%), create two zones
        if fib_dir == "both":
            zones.append(Zone(
                zone_type="fib", direction="long",
                price_high=fib_price + fib_thickness, price_low=fib_price - fib_thickness,
                price_mid=fib_price, stop_price=or_low - stop_buf,
                source_bar=or_end_idx, label=fib_name + "_long"))
            zones.append(Zone(
                zone_type="fib", direction="short",
                price_high=fib_price + fib_thickness, price_low=fib_price - fib_thickness,
                price_mid=fib_price, stop_price=or_high + stop_buf,
                source_bar=or_end_idx, label=fib_name + "_short"))
        elif fib_dir == "long":
            zones.append(Zone(
                zone_type="fib", direction="long",
                price_high=fib_price + fib_thickness, price_low=fib_price - fib_thickness,
                price_mid=fib_price, stop_price=or_low - stop_buf,
                source_bar=or_end_idx, label=fib_name))
        else:
            zones.append(Zone(
                zone_type="fib", direction="short",
                price_high=fib_price + fib_thickness, price_low=fib_price - fib_thickness,
                price_mid=fib_price, stop_price=or_high + stop_buf,
                source_bar=or_end_idx, label=fib_name))

    # === OR BOUNDARY ZONES (for retest entries) ===
    retest_thickness = points_from_pct(0.05, ref)
    zones.append(Zone(
        zone_type="or_boundary", direction="long",
        price_high=or_high + retest_thickness, price_low=or_high - retest_thickness,
        price_mid=or_high, stop_price=or_high - stop_buf * 2,
        source_bar=or_end_idx, label="or_high_retest"))
    zones.append(Zone(
        zone_type="or_boundary", direction="short",
        price_high=or_low + retest_thickness, price_low=or_low - retest_thickness,
        price_mid=or_low, stop_price=or_low + stop_buf * 2,
        source_bar=or_end_idx, label="or_low_retest"))

    # === SESSION STRUCTURE (from 9:30 onward) ===
    sess_h = h[or_start_idx:]
    sess_l = l[or_start_idx:]
    sess_c = c[or_start_idx:]
    sess_o = o[or_start_idx:]
    n_sess = len(sess_h)

    if n_sess > 10:
        # Swings
        swing_highs, swing_lows = detect_swings(sess_h, sess_l,
                                                 lookback=swing_lookback,
                                                 lookforward=swing_lookback)
        last_sh, last_sl = get_swing_levels(sess_h, sess_l, swing_highs, swing_lows)

        # Structure shifts (CHOCH/BOS)
        events = detect_structure_shifts(sess_h, sess_l, sess_c, swing_highs, swing_lows)

        # FVGs from 9:30 onward
        fvgs = detect_fvgs(sess_h, sess_l, min_gap_pct=min_fvg_pct)

        # OBs from 9:30 onward
        obs = detect_order_blocks(sess_o, sess_h, sess_l, sess_c, displacement_mult=disp_mult)
    else:
        swing_highs = swing_lows = np.zeros(n_sess, dtype=bool)
        last_sh = last_sl = np.full(n_sess, np.nan)
        events = pd.DataFrame(columns=["bar_idx", "type", "direction", "level_broken", "price"])
        fvgs = pd.DataFrame(columns=["bar_idx", "fvg_type", "fvg_top", "fvg_bottom", "fvg_mid"])
        obs = pd.DataFrame(columns=["bar_idx", "ob_type", "ob_high", "ob_low", "ob_mid"])

    # === CHOCH ZONES ===
    for _, ev in events.iterrows():
        if ev["type"] == "choch":
            ev_bar = int(ev["bar_idx"])
            level = ev["level_broken"]

            if ev["direction"] == "bullish":
                # Bullish CHOCH: broken above swing high → zone around that level for pullback long
                zones.append(Zone(
                    zone_type="choch", direction="long",
                    price_high=level + fib_thickness, price_low=level - fib_thickness,
                    price_mid=level,
                    stop_price=last_sl[ev_bar] - stop_buf if not np.isnan(last_sl[ev_bar]) else or_low - stop_buf,
                    source_bar=or_start_idx + ev_bar, label=f"choch_bull@{level:.0f}"))
            else:
                zones.append(Zone(
                    zone_type="choch", direction="short",
                    price_high=level + fib_thickness, price_low=level - fib_thickness,
                    price_mid=level,
                    stop_price=last_sh[ev_bar] + stop_buf if not np.isnan(last_sh[ev_bar]) else or_high + stop_buf,
                    source_bar=or_start_idx + ev_bar, label=f"choch_bear@{level:.0f}"))

    # === FVG ZONES ===
    for _, fvg in fvgs.iterrows():
        fvg_bar = int(fvg["bar_idx"])
        if fvg["fvg_type"] == "bullish":
            zones.append(Zone(
                zone_type="fvg", direction="long",
                price_high=fvg["fvg_top"], price_low=fvg["fvg_bottom"],
                price_mid=fvg["fvg_mid"],
                stop_price=fvg["fvg_bottom"] - stop_buf,
                source_bar=or_start_idx + fvg_bar, label=f"fvg_bull@{fvg['fvg_mid']:.0f}"))
        else:
            zones.append(Zone(
                zone_type="fvg", direction="short",
                price_high=fvg["fvg_top"], price_low=fvg["fvg_bottom"],
                price_mid=fvg["fvg_mid"],
                stop_price=fvg["fvg_top"] + stop_buf,
                source_bar=or_start_idx + fvg_bar, label=f"fvg_bear@{fvg['fvg_mid']:.0f}"))

    # === OB ZONES ===
    for _, ob in obs.iterrows():
        ob_bar = int(ob["bar_idx"])
        if ob["ob_type"] == "bullish":
            zones.append(Zone(
                zone_type="ob", direction="long",
                price_high=ob["ob_high"], price_low=ob["ob_low"],
                price_mid=ob["ob_mid"],
                stop_price=ob["ob_low"] - stop_buf,
                source_bar=or_start_idx + ob_bar, label=f"ob_bull@{ob['ob_mid']:.0f}"))
        else:
            zones.append(Zone(
                zone_type="ob", direction="short",
                price_high=ob["ob_high"], price_low=ob["ob_low"],
                price_mid=ob["ob_mid"],
                stop_price=ob["ob_high"] + stop_buf,
                source_bar=or_start_idx + ob_bar, label=f"ob_bear@{ob['ob_mid']:.0f}"))

    # === VWAP (computed but added as dynamic zone during scanning) ===
    reset = np.zeros(len(h), dtype=bool)
    reset[or_start_idx] = True
    vwap = compute_vwap(h, l, c, v, reset_mask=reset)

    # ATR
    atr = compute_atr(h, l, c, period=14)
    current_atr = atr[or_end_idx] if or_end_idx < len(atr) else atr[-1]

    # OR sweep tracking
    or_bars_count = or_end_idx - or_start_idx
    post_h = h[or_end_idx:]
    post_l = l[or_end_idx:]
    post_c = c[or_end_idx:]

    context = {
        "high": h, "low": l, "close": c, "open": o, "volume": v,
        "post_high": post_h, "post_low": post_l, "post_close": post_c,
        "or_high": or_high, "or_low": or_low, "or_mid": or_mid,
        "or_width": or_width, "or_width_pct": pct_of_price(or_width, ref),
        "or_start_idx": or_start_idx, "or_end_idx": or_end_idx,
        "ref_price": ref, "atr": current_atr, "vwap": vwap,
        "vwap_tol": points_from_pct(vwap_tol_pct, ref),
        "stop_buffer": stop_buf,
        "swing_highs": swing_highs, "swing_lows": swing_lows,
        "last_sh": last_sh, "last_sl": last_sl,
        "structure_events": events,
        "or_bars_count": or_bars_count,
        "bar_times": day_bars.index,
    }

    return zones, context


# ---------------------------------------------------------------------------
# Zone scoring — adds confluence points
# ---------------------------------------------------------------------------

def score_zones(zones: List[Zone], context: dict) -> List[Zone]:
    """Score zones by confluence: overlapping zones of different types boost the score."""
    for i, z1 in enumerate(zones):
        for j, z2 in enumerate(zones):
            if i == j:
                continue
            if z1.direction != z2.direction:
                continue
            if z1.zone_type == z2.zone_type:
                continue  # same type doesn't add confluence
            # Check overlap
            if z1.price_low <= z2.price_high and z1.price_high >= z2.price_low:
                z1.score += 1
    return zones


# ---------------------------------------------------------------------------
# Entry scanner — scans post-OR bars for price entering scored zones
# ---------------------------------------------------------------------------

def scan_for_entries(zones: List[Zone], context: dict, td_str: str,
                     bias: Optional[str] = None,
                     strategy_filter: Optional[str] = None,
                     max_risk_pct: float = 0.20,
                     target_rr: float = 1.5,
                     min_score: int = 1,
                     require_or_sweep: bool = True,
                     require_close_confirmation: bool = True,
                     ib_bias: str = "", first_formed: str = ""
                     ) -> List[StrategySignal]:
    """Scan post-OR bars for price entering any qualifying zone.

    Args:
        zones: scored zones to monitor
        strategy_filter: if set, only consider zones of this type (e.g., "choch", "fib")
        min_score: minimum confluence score to enter
        require_or_sweep: for CHOCH zones, require OR boundary to be swept first
        require_close_confirmation: require candle close inside zone, not just wick
    """
    signals = []
    post_h = context["post_high"]
    post_l = context["post_low"]
    post_c = context["post_close"]
    or_h = context["or_high"]
    or_l = context["or_low"]
    ref = context["ref_price"]
    offset = context["or_end_idx"]
    bar_times = context["bar_times"]

    # Track OR sweeps
    or_high_swept = False
    or_low_swept = False

    # Filter zones by direction bias and strategy
    eligible = []
    for z in zones:
        if bias and z.direction != bias:
            continue
        if strategy_filter and z.zone_type != strategy_filter:
            # For composite strategies, allow multiple types
            if strategy_filter == "all":
                pass
            elif strategy_filter == "choch_fade" and z.zone_type not in ("choch",):
                continue
            elif strategy_filter == "fib_discount" and z.zone_type not in ("fib",):
                continue
            elif strategy_filter == "ob_entry" and z.zone_type not in ("ob",):
                continue
            elif strategy_filter == "fvg_displacement" and z.zone_type not in ("fvg",):
                continue
            elif strategy_filter == "breakout_retest" and z.zone_type not in ("or_boundary",):
                continue
            elif strategy_filter == "full_confluence":
                pass  # allow all zone types
            elif strategy_filter == "vwap_reversion" and z.zone_type not in ("fib", "vwap"):
                continue
        if z.score < min_score:
            continue
        eligible.append(z)

    if not eligible:
        return signals

    for i in range(len(post_h)):
        # Update sweep tracking
        if post_h[i] > or_h:
            or_high_swept = True
        if post_l[i] < or_l:
            or_low_swept = True

        # Add VWAP as dynamic zone at current bar
        vwap_val = context["vwap"][offset + i] if (offset + i) < len(context["vwap"]) else None
        vwap_tol = context["vwap_tol"]

        for z in eligible:
            # Check if price is in this zone
            price_in_zone = False

            if require_close_confirmation:
                # Close must be inside the zone
                if z.direction == "long":
                    price_in_zone = post_l[i] <= z.price_high and post_c[i] >= z.price_low and post_c[i] > z.price_low
                else:
                    price_in_zone = post_h[i] >= z.price_low and post_c[i] <= z.price_high and post_c[i] < z.price_high
            else:
                # Any wick touch counts
                price_in_zone = post_l[i] <= z.price_high and post_h[i] >= z.price_low

            if not price_in_zone:
                continue

            # For CHOCH zones, verify OR was swept
            if require_or_sweep and z.zone_type == "choch":
                if z.direction == "long" and not or_low_swept:
                    continue
                if z.direction == "short" and not or_high_swept:
                    continue

            # For OR boundary retests, verify the boundary was broken first
            if z.zone_type == "or_boundary":
                if z.direction == "long" and not or_high_swept:
                    continue  # OR high must be broken before we look for retest
                if z.direction == "short" and not or_low_swept:
                    continue

            # VWAP confluence bonus: check if zone is near VWAP
            vwap_bonus = 0
            if vwap_val is not None and abs(z.price_mid - vwap_val) <= vwap_tol:
                vwap_bonus = 1

            effective_score = z.score + vwap_bonus

            if effective_score < min_score:
                continue

            # Calculate risk/reward
            entry = post_c[i]
            stop = z.stop_price
            risk = abs(entry - stop)
            risk_pct = pct_of_price(risk, ref)

            if risk <= 0 or risk_pct > max_risk_pct:
                continue

            if z.direction == "long":
                target = entry + risk * target_rr
            else:
                target = entry - risk * target_rr

            reward = abs(target - entry)
            reward_pct = pct_of_price(reward, ref)
            rr = reward / risk if risk > 0 else 0

            # Determine signal name
            signal_name = z.zone_type
            if strategy_filter and strategy_filter != "all":
                signal_name = strategy_filter

            bar_idx = offset + i
            entry_time = str(bar_times[bar_idx]) if bar_idx < len(bar_times) else ""

            zones_hit = z.label + (f"+vwap" if vwap_bonus else "")

            signals.append(StrategySignal(
                trade_date=td_str,
                entry_bar_idx=bar_idx,
                entry_time=entry_time,
                direction=z.direction,
                entry_price=entry,
                stop_price=stop,
                target_price=target,
                risk_pct=risk_pct,
                reward_pct=reward_pct,
                rr_ratio=rr,
                signal_name=signal_name,
                confidence=min(1.0, effective_score / 4.0),
                ib_bias=ib_bias,
                first_formed=first_formed,
                zones_hit=zones_hit,
            ))
            return signals  # one signal per day

    return signals


# ---------------------------------------------------------------------------
# Strategy entry points — each just configures the scanner differently
# ---------------------------------------------------------------------------

def _run_strategy(ctx_args: dict, td_str: str, bias: Optional[str],
                  strategy_name: str, min_score: int = 1,
                  max_risk_pct: float = 0.20, target_rr: float = 1.5,
                  require_or_sweep: bool = True,
                  require_close: bool = True,
                  **zone_kwargs) -> List[StrategySignal]:
    """Common runner for all strategies."""
    day_bars = ctx_args["day_bars"]
    or_h = ctx_args["or_high"]
    or_l = ctx_args["or_low"]
    or_start = ctx_args["or_start_idx"]
    or_end = ctx_args["or_end_idx"]
    swing_lb = ctx_args.get("swing_lookback", 2)
    bias_min = ctx_args.get("bias_minutes", 15)

    # Build zones
    zones, context = build_zones(
        day_bars, or_h, or_l, or_start, or_end,
        swing_lookback=swing_lb,
        **zone_kwargs
    )

    # Score zones
    zones = score_zones(zones, context)

    # IB Bias
    ib_dir, ff = compute_ib_bias(context["high"], context["low"], or_start, or_end, bias_min)

    # Scan for entries
    return scan_for_entries(
        zones, context, td_str,
        bias=bias,
        strategy_filter=strategy_name,
        max_risk_pct=max_risk_pct,
        target_rr=target_rr,
        min_score=min_score,
        require_or_sweep=require_or_sweep,
        require_close_confirmation=require_close,
        ib_bias=ib_dir,
        first_formed=ff,
    )


def generate_breakout_retest(ctx_args: dict, td_str: str, bias: Optional[str] = None,
                              params: dict = None) -> List[StrategySignal]:
    if params is None:
        params = {}
    return _run_strategy(ctx_args, td_str, bias, "breakout_retest",
                         min_score=1, max_risk_pct=params.get("max_risk_pct", 0.15),
                         target_rr=params.get("target_rr", 1.5),
                         require_or_sweep=True, require_close=True)


def generate_fib_discount(ctx_args: dict, td_str: str, bias: Optional[str] = None,
                           params: dict = None) -> List[StrategySignal]:
    if params is None:
        params = {}
    return _run_strategy(ctx_args, td_str, bias, "fib_discount",
                         min_score=1, max_risk_pct=params.get("max_risk_pct", 0.15),
                         target_rr=params.get("target_rr", 1.5),
                         require_or_sweep=False, require_close=True)


def generate_ob_entry(ctx_args: dict, td_str: str, bias: Optional[str] = None,
                       params: dict = None) -> List[StrategySignal]:
    if params is None:
        params = {}
    return _run_strategy(ctx_args, td_str, bias, "ob_entry",
                         min_score=1, max_risk_pct=params.get("max_risk_pct", 0.15),
                         target_rr=params.get("target_rr", 2.0),
                         require_or_sweep=False, require_close=True)


def generate_fvg_displacement(ctx_args: dict, td_str: str, bias: Optional[str] = None,
                               params: dict = None) -> List[StrategySignal]:
    if params is None:
        params = {}
    return _run_strategy(ctx_args, td_str, bias, "fvg_displacement",
                         min_score=1, max_risk_pct=params.get("max_risk_pct", 0.15),
                         target_rr=params.get("target_rr", 1.5),
                         require_or_sweep=False, require_close=True)


def generate_choch_fade(ctx_args: dict, td_str: str, bias: Optional[str] = None,
                         params: dict = None) -> List[StrategySignal]:
    if params is None:
        params = {}
    return _run_strategy(ctx_args, td_str, bias, "choch_fade",
                         min_score=1, max_risk_pct=params.get("max_risk_pct", 0.20),
                         target_rr=params.get("target_rr", 1.5),
                         require_or_sweep=True, require_close=True)


def generate_full_confluence(ctx_args: dict, td_str: str, bias: Optional[str] = None,
                              params: dict = None) -> List[StrategySignal]:
    if params is None:
        params = {}
    return _run_strategy(ctx_args, td_str, bias, "full_confluence",
                         min_score=params.get("min_confirmations", 2),
                         max_risk_pct=params.get("max_risk_pct", 0.15),
                         target_rr=params.get("target_rr", 2.0),
                         require_or_sweep=False, require_close=True)


def generate_vwap_reversion(ctx_args: dict, td_str: str, bias: Optional[str] = None,
                             params: dict = None) -> List[StrategySignal]:
    if params is None:
        params = {}
    return _run_strategy(ctx_args, td_str, bias, "vwap_reversion",
                         min_score=1, max_risk_pct=params.get("max_risk_pct", 0.15),
                         target_rr=params.get("target_rr", 1.5),
                         require_or_sweep=False, require_close=True)


# ---------------------------------------------------------------------------
# Registry
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
