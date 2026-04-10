"""Strategy simulation engine for range-based setups.

This module implements Phase 4 strategy simulation contracts from
MARKET_ANALYTICS_PLATFORM_SPEC.md.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Optional

import pandas as pd


@dataclass
class StrategyDefinition:
    name: str
    display_name: str
    entry_type: str  # "MR" or "BO"

    # MR entry rules
    mr_trigger: str = "retest_boundary"  # "retest_boundary", "retest_mid", "retest_fib"
    mr_fib_level: float = 0.5
    mr_confirmation_bars: int = 2

    # BO entry rules
    bo_trigger: str = "close_beyond"  # "close_beyond", "hold_N_bars"
    bo_hold_bars: int = 2
    bo_pullback_entry: bool = False

    # Target rules
    target_type: str = "extension"  # "extension", "fib", "opposite", "time", "next_range"
    target_extension: float = 1.0
    target_fib: float = 0.0
    target_minutes: int = 60

    # Stop rules
    stop_type: str = "range_based"  # "range_based", "atr_based", "opposite", "swing"
    stop_range_fraction: float = 0.25
    stop_atr_multiple: float = 1.5

    # Risk management
    cover_the_queen: bool = True
    ctq_fraction: float = 0.5
    trail_after_ctq: bool = True
    max_hold_minutes: int = 240


@dataclass
class StrategyTrade:
    symbol: str
    range_name: str
    strategy_name: str
    trading_date: str

    entry_triggered: bool
    entry_price: float | None
    entry_time: pd.Timestamp | None
    entry_side: str | None  # "LONG" or "SHORT"
    entry_minutes_after_range: float | None

    exit_price: float | None
    exit_time: pd.Timestamp | None
    exit_reason: str | None  # "TARGET", "STOP", "TIME_STOP", "EOD"
    exit_bar_check_order: str | None  # "STOP_ONLY", "TARGET_ONLY", "AMBIGUOUS_BOTH", ...
    ambiguous_bar: bool

    pnl_points: float | None
    pnl_r_multiple: float | None
    initial_risk_points: float | None

    mfe_points: float | None
    mae_points: float | None
    mfe_pct_of_range: float | None
    mae_pct_of_range: float | None
    mfe_time_minutes: float | None
    mae_time_minutes: float | None


@dataclass
class SimulationPolicy:
    """Policy for resolving ambiguous OHLC bars that hit both stop and target."""

    # Allowed values: STOP_FIRST, TARGET_FIRST, SPLIT, EXCLUDE
    ambiguous_bar_resolution: str = "SPLIT"


STRATEGY_PRESETS: dict[str, StrategyDefinition] = {
    "MR_TO_MID": StrategyDefinition(
        "MR_TO_MID",
        "MR to Midpoint",
        "MR",
        target_type="fib",
        target_fib=0.5,
        stop_type="range_based",
        stop_range_fraction=0.25,
    ),
    "MR_TO_OPPOSITE": StrategyDefinition(
        "MR_TO_OPPOSITE",
        "MR to Opposite",
        "MR",
        target_type="opposite",
        stop_type="range_based",
        stop_range_fraction=0.5,
    ),
    "BO_1X": StrategyDefinition(
        "BO_1X",
        "Breakout 1x Extension",
        "BO",
        target_type="extension",
        target_extension=1.0,
        stop_type="opposite",
    ),
    "BO_PULLBACK_1X": StrategyDefinition(
        "BO_PULLBACK_1X",
        "BO Pullback 1x",
        "BO",
        bo_pullback_entry=True,
        target_type="extension",
        target_extension=1.0,
        stop_type="range_based",
        stop_range_fraction=0.5,
    ),
    "BO_TIME_HOLD": StrategyDefinition(
        "BO_TIME_HOLD",
        "BO Time Exit",
        "BO",
        target_type="time",
        target_minutes=60,
        stop_type="range_based",
        stop_range_fraction=0.5,
    ),
    "FAILED_BO_REVERSE": StrategyDefinition(
        "FAILED_BO_REVERSE",
        "Failed BO Reversal",
        "MR",
        mr_confirmation_bars=3,
        target_type="opposite",
        stop_type="swing",
    ),
}


def _minutes_since(ts: pd.Timestamp, start: pd.Timestamp) -> float:
    return float((ts - start).total_seconds() / 60.0)


def _build_no_entry_trade(range_record: dict, strategy: StrategyDefinition) -> StrategyTrade:
    return StrategyTrade(
        symbol=str(range_record["symbol"]),
        range_name=str(range_record["range_name"]),
        strategy_name=str(strategy.name),
        trading_date=str(range_record["trading_date"]),
        entry_triggered=False,
        entry_price=None,
        entry_time=None,
        entry_side=None,
        entry_minutes_after_range=None,
        exit_price=None,
        exit_time=None,
        exit_reason=None,
        exit_bar_check_order=None,
        ambiguous_bar=False,
        pnl_points=None,
        pnl_r_multiple=None,
        initial_risk_points=None,
        mfe_points=None,
        mae_points=None,
        mfe_pct_of_range=None,
        mae_pct_of_range=None,
        mfe_time_minutes=None,
        mae_time_minutes=None,
    )


def _find_breakout_entry(
    post_bars: pd.DataFrame,
    range_high: float,
    range_low: float,
    strategy: StrategyDefinition,
) -> tuple[Optional[pd.Timestamp], Optional[float], Optional[str], Optional[pd.Timestamp], Optional[str]]:
    """Return (entry_time, entry_price, side, breakout_time, breakout_side)."""
    breakout_time = None
    breakout_side = None

    if strategy.bo_trigger == "hold_N_bars":
        above_run = 0
        below_run = 0
        for ts, row in post_bars.iterrows():
            c = float(row["close"])
            if c > range_high:
                above_run += 1
                below_run = 0
            elif c < range_low:
                below_run += 1
                above_run = 0
            else:
                above_run = 0
                below_run = 0

            if above_run >= strategy.bo_hold_bars:
                breakout_time = ts
                breakout_side = "LONG"
                break
            if below_run >= strategy.bo_hold_bars:
                breakout_time = ts
                breakout_side = "SHORT"
                break
    else:
        for ts, row in post_bars.iterrows():
            c = float(row["close"])
            if c > range_high:
                breakout_time = ts
                breakout_side = "LONG"
                break
            if c < range_low:
                breakout_time = ts
                breakout_side = "SHORT"
                break

    if breakout_time is None or breakout_side is None:
        return None, None, None, None, None

    if not strategy.bo_pullback_entry:
        return breakout_time, float(post_bars.loc[breakout_time, "close"]), breakout_side, breakout_time, breakout_side

    # Pullback entry: wait for retest of broken boundary then continuation close in BO direction.
    boundary = range_high if breakout_side == "LONG" else range_low
    after_break = post_bars.loc[post_bars.index > breakout_time]
    touched = False
    for ts, row in after_break.iterrows():
        h = float(row["high"])
        l = float(row["low"])
        c = float(row["close"])
        if not touched:
            if breakout_side == "LONG" and l <= boundary:
                touched = True
            if breakout_side == "SHORT" and h >= boundary:
                touched = True
            continue

        if breakout_side == "LONG" and c > boundary:
            return ts, c, "LONG", breakout_time, breakout_side
        if breakout_side == "SHORT" and c < boundary:
            return ts, c, "SHORT", breakout_time, breakout_side

    return None, None, None, breakout_time, breakout_side


def _find_mr_entry(
    post_bars: pd.DataFrame,
    range_high: float,
    range_low: float,
    range_mid: float,
    strategy: StrategyDefinition,
) -> tuple[Optional[pd.Timestamp], Optional[float], Optional[str]]:
    """
    Mean reversion entry model:
    1) Wait for first boundary break (HIGH or LOW) to determine trade direction.
    2) Determine the entry level from ``mr_trigger``:
       - ``retest_boundary``: wait for price to retest the broken boundary (default)
       - ``retest_mid``:      wait for price to retest the range midpoint
       - ``retest_fib``:      wait for price to retest
                              ``range_low + mr_fib_level * range_width``
    3) Require ``mr_confirmation_bars`` consecutive bars that:
       (a) touch ``entry_level`` (bar's H/L straddles it), AND
       (b) close on the interior side of ``entry_level``.
       Non-touching bars reset the confirmation counter — confirmation requires
       N *consecutive* touching bars with the correct close direction.
    """
    broke_side = None
    break_ts = None

    for ts, row in post_bars.iterrows():
        h = float(row["high"])
        l = float(row["low"])
        if h > range_high:
            broke_side = "HIGH"
            break_ts = ts
            break
        if l < range_low:
            broke_side = "LOW"
            break_ts = ts
            break

    if break_ts is None or broke_side is None:
        return None, None, None

    boundary = range_high if broke_side == "HIGH" else range_low
    side = "SHORT" if broke_side == "HIGH" else "LONG"

    # Determine the level at which entry is triggered.
    if strategy.mr_trigger == "retest_mid":
        entry_level = range_mid
    elif strategy.mr_trigger == "retest_fib":
        entry_level = range_low + strategy.mr_fib_level * (range_high - range_low)
    else:  # "retest_boundary" (default)
        entry_level = boundary

    after = post_bars.loc[post_bars.index > break_ts]
    confirm = 0
    for ts, row in after.iterrows():
        h = float(row["high"])
        l = float(row["low"])
        c = float(row["close"])

        touched = (l <= entry_level <= h)
        if not touched:
            confirm = 0
            continue

        if side == "SHORT" and c < entry_level:
            confirm += 1
        elif side == "LONG" and c > entry_level:
            confirm += 1
        else:
            confirm = 0

        if confirm >= max(1, strategy.mr_confirmation_bars):
            return ts, c, side

    return None, None, None


def _target_price(strategy: StrategyDefinition, side: str, rr: dict) -> Optional[float]:
    rh = float(rr["range_high"])
    rl = float(rr["range_low"])
    rw = float(rr["range_width"])

    if strategy.target_type == "extension":
        if side == "LONG":
            return rh + strategy.target_extension * rw
        return rl - strategy.target_extension * rw

    if strategy.target_type == "fib":
        return rl + strategy.target_fib * rw

    if strategy.target_type == "opposite":
        if side == "LONG":
            return rh
        return rl

    return None


def _stop_price(strategy: StrategyDefinition, side: str, rr: dict, entry_price: float) -> float:
    rh = float(rr["range_high"])
    rl = float(rr["range_low"])
    rw = float(rr["range_width"])

    if strategy.stop_type in {"opposite", "swing"}:
        # NOTE: "swing" is currently aliased to "opposite" (boundary as stop).
        # A proper swing stop would use the local H/L around the entry sequence.
        # Implement true swing stop in Phase 4 when equity curve accuracy matters.
        if side == "LONG":
            return rl
        return rh

    # default range-based
    frac = max(strategy.stop_range_fraction, 0.01)
    if side == "LONG":
        return entry_price - frac * rw
    return entry_price + frac * rw


def simulate_strategy(
    post_bars: pd.DataFrame,
    range_record: dict,
    strategy: StrategyDefinition,
    range_end_ts: pd.Timestamp,
    policy: Optional[SimulationPolicy] = None,
) -> StrategyTrade | None:
    """Walk bars after range close and return a StrategyTrade or None."""
    policy = policy or SimulationPolicy()

    if post_bars.empty:
        return None

    rh = float(range_record["range_high"])
    rl = float(range_record["range_low"])
    rm = float(range_record["range_mid"])
    rw = float(range_record["range_width"])

    if rw <= 0:
        return None

    entry_time = None
    entry_price = None
    entry_side = None

    if strategy.entry_type == "BO":
        entry_time, entry_price, entry_side, _, _ = _find_breakout_entry(post_bars, rh, rl, strategy)
    else:
        entry_time, entry_price, entry_side = _find_mr_entry(post_bars, rh, rl, rm, strategy)

    if entry_time is None or entry_price is None or entry_side is None:
        return None

    stop = _stop_price(strategy, entry_side, range_record, entry_price)
    target = _target_price(strategy, entry_side, range_record)
    risk = abs(entry_price - stop)
    if risk <= 0:
        return None

    # Entry bar is included in observation (trade_bars starts at entry_time).
    # This models a fill at some point during the bar — conservative for research.
    # If strict close-based fill is needed, change >= to > (excludes entry bar).
    # NOTE: cover_the_queen (CTQ) partial-profit and trail logic are defined in
    # StrategyDefinition but not yet applied here — all trades use single full-
    # position exits. CTQ can be retroactively computed from the MFE path.
    # Implement in Phase 4 when building equity curves.
    trade_bars = post_bars.loc[post_bars.index >= entry_time].copy()
    max_hold_deadline = entry_time + pd.Timedelta(minutes=strategy.max_hold_minutes)

    best_fav = 0.0
    worst_adv = 0.0
    best_ts = entry_time
    worst_ts = entry_time

    exit_time = None
    exit_price = None
    exit_reason = None
    exit_bar_check_order = None
    ambiguous_bar = False

    for ts, row in trade_bars.iterrows():
        h = float(row["high"])
        l = float(row["low"])
        c = float(row["close"])

        if entry_side == "LONG":
            fav = h - entry_price
            adv = entry_price - l
        else:
            fav = entry_price - l
            adv = h - entry_price

        if fav > best_fav:
            best_fav = fav
            best_ts = ts
        if adv > worst_adv:
            worst_adv = adv
            worst_ts = ts

        # Conservative precedence if target and stop are both touched in one bar.
        if entry_side == "LONG":
            stop_hit = l <= stop
            target_hit = target is not None and h >= target
        else:
            stop_hit = h >= stop
            target_hit = target is not None and l <= target

        if stop_hit and target_hit:
            ambiguous_bar = True
            exit_time = ts
            exit_bar_check_order = "AMBIGUOUS_BOTH"

            mode = str(policy.ambiguous_bar_resolution).upper()
            if mode == "STOP_FIRST":
                exit_price = stop
                exit_reason = "AMBIGUOUS_STOP_FIRST"
            elif mode == "TARGET_FIRST":
                exit_price = float(target) if target is not None else stop
                exit_reason = "AMBIGUOUS_TARGET_FIRST"
            elif mode == "EXCLUDE":
                exit_price = None
                exit_reason = "AMBIGUOUS_EXCLUDED"
            else:
                # SPLIT default: midpoint between stop/target on ambiguous bars.
                if target is not None:
                    exit_price = float((stop + float(target)) / 2.0)
                else:
                    exit_price = stop
                exit_reason = "AMBIGUOUS_SPLIT"
            break

        if stop_hit:
            exit_time = ts
            exit_price = stop
            exit_reason = "STOP"
            exit_bar_check_order = "STOP_ONLY"
            break
        if target_hit:
            exit_time = ts
            exit_price = float(target)
            exit_reason = "TARGET"
            exit_bar_check_order = "TARGET_ONLY"
            break

        if strategy.target_type == "time":
            if _minutes_since(ts, entry_time) >= strategy.target_minutes:
                exit_time = ts
                exit_price = c
                exit_reason = "TIME_TARGET"
                exit_bar_check_order = "TIME_ONLY"
                break

        if ts >= max_hold_deadline:
            exit_time = ts
            exit_price = c
            exit_reason = "TIME_STOP"
            exit_bar_check_order = "TIME_ONLY"
            break

    if exit_time is None:
        # End-of-observation fallback.
        last_ts = trade_bars.index[-1]
        exit_time = last_ts
        exit_price = float(trade_bars.iloc[-1]["close"])
        exit_reason = "EOD"
        exit_bar_check_order = "EOD_ONLY"

    if exit_price is None:
        pnl = None
        r_multiple = None
    else:
        if entry_side == "LONG":
            pnl = float(exit_price - entry_price)
        else:
            pnl = float(entry_price - exit_price)
        r_multiple = float(pnl / risk)

    return StrategyTrade(
        symbol=str(range_record["symbol"]),
        range_name=str(range_record["range_name"]),
        strategy_name=strategy.name,
        trading_date=str(range_record["trading_date"]),
        entry_triggered=True,
        entry_price=float(entry_price),
        entry_time=entry_time,
        entry_side=entry_side,
        entry_minutes_after_range=_minutes_since(entry_time, range_end_ts),
        exit_price=float(exit_price) if exit_price is not None else None,
        exit_time=exit_time,
        exit_reason=exit_reason,
        exit_bar_check_order=exit_bar_check_order,
        ambiguous_bar=ambiguous_bar,
        pnl_points=pnl,
        pnl_r_multiple=r_multiple,
        initial_risk_points=float(risk),
        mfe_points=float(best_fav),
        mae_points=float(worst_adv),
        mfe_pct_of_range=float(best_fav / rw * 100),
        mae_pct_of_range=float(worst_adv / rw * 100),
        mfe_time_minutes=_minutes_since(best_ts, entry_time),
        mae_time_minutes=_minutes_since(worst_ts, entry_time),
    )


def to_record(trade: StrategyTrade) -> dict:
    rec = asdict(trade)
    for k in ("entry_time", "exit_time"):
        if rec[k] is not None:
            rec[k] = pd.Timestamp(rec[k])
    return rec


def no_entry_record(range_record: dict, strategy: StrategyDefinition) -> dict:
    return to_record(_build_no_entry_trade(range_record, strategy))
