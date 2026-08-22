"""
Multi-Strategy Range Trading Comparison Engine

Tests 5 distinct range trading hypotheses under identical conditions:
1. IB Sweep Fade (champion reimplementation) — sweep + FVG displacement rejection
2. ORB 5m — opening range breakout continuation
3. VWAP Mean Reversion — fade extreme VWAP deviation inside IB
4. Failed Breakout Reversal — breakout fails, enter reversal
5. IB Breakout Continuation — breakout holds, enter pullback

All strategies share:
- Same 1m OHLC data source (zero look-ahead)
- Same session definitions (Asia, London, NY_AM, NY_MIDDAY, NY_PM)
- Same execution model (1-tick slippage, commission, 2-leg scaling, BE on T1)
- Same prop firm sim ($50K account, $3K target, $2K trailing DD)
- Same position sizing (4 Micro ES / 2 Micro NQ)

Usage:
    python -m scripts.analysis.range_strategy_comparison --start-year 2021 --end-year 2026 --symbols ES,NQ
"""
from __future__ import annotations

import argparse
import warnings
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class DayContext:
    """Pre-computed context for a single trading day (zero look-ahead)."""
    trade_date: pd.Timestamp
    prev_day: pd.Timestamp
    atr_val: float
    prior_rth_high: float
    prior_rth_low: float
    asia_high: float
    asia_low: float
    overnight_high: float
    overnight_low: float
    ib_high: float
    ib_low: float
    ib_range: float
    ib_mid: float
    ib_bars_1m: pd.DataFrame
    day_bars_1m: pd.DataFrame  # full day 1m bars
    day_bars_5m: pd.DataFrame
    session_bars: Dict[str, pd.DataFrame]  # session_name -> 1m bars
    session_5m: Dict[str, pd.DataFrame]    # session_name -> 5m bars
    progressive_vwap: Dict[str, pd.Series]   # session_name -> VWAP series


@dataclass
class TradeSignal:
    """Signal emitted by a strategy."""
    direction: str          # "LONG" or "SHORT"
    entry_price: float
    stop_loss: float
    tp1_price: float
    tp2_price: float
    risk_points: float
    entry_time: pd.Timestamp
    session_name: str
    metadata: Dict = field(default_factory=dict)


@dataclass
class TradeResult:
    """Result of a simulated trade."""
    strategy_name: str
    symbol: str
    session_name: str
    date: str
    direction: str
    entry_time: pd.Timestamp
    entry_price: float
    stop_loss: float
    tp1_price: float
    tp2_price: float
    risk_points: float
    t1_hit: bool
    t2_hit: bool
    stopped_out: bool
    exit_time: pd.Timestamp
    leg1_pnl: float
    leg2_pnl: float
    total_pnl_points: float
    total_pnl_dollars: float
    r_multiple: float


# ============================================================================
# STRATEGY BASE CLASS
# ============================================================================

class RangeStrategy(ABC):
    """Base class for all range trading strategies."""

    def __init__(self, name: str, symbol: str, tick_size: float = 0.25):
        self.name = name
        self.symbol = symbol
        self.tick_size = tick_size

    @abstractmethod
    def detect_signal(self, ctx: DayContext, session_name: str) -> Optional[TradeSignal]:
        """Scan session bars and return a trade signal, or None."""
        pass

    def get_active_sessions(self) -> List[str]:
        """Which sessions this strategy trades in."""
        return ["NY_MIDDAY", "NY_PM"]


# ============================================================================
# STRATEGY 1: IB SWEEP FADE (Champion Reimplementation)
# ============================================================================

class IBSweepFadeStrategy(RangeStrategy):
    """
    Sweep of IB High/Low with 5m FVG displacement rejection.
    Entry: FVG edge after sweep + close back inside IB.
    Stop: 2 ticks beyond sweep extreme.
    TP1: 50% of IB range. TP2: Opposite IB boundary.
    Filter: IB range < 0.40 * ATR (compressed = mean-reverting regime).
    """

    def __init__(self, symbol: str, tick_size: float = 0.25):
        super().__init__("IB_Sweep_Fade", symbol, tick_size)

    def detect_signal(self, ctx: DayContext, session_name: str) -> Optional[TradeSignal]:
        if session_name not in ("NY_MIDDAY", "NY_PM"):
            return None

        ref_h, ref_l, ref_r = ctx.ib_high, ctx.ib_low, ctx.ib_range
        if np.isnan(ref_h) or np.isnan(ref_l) or ref_r <= 0:
            return None

        # Filter B: IB must be compressed
        if ref_r >= (0.40 * ctx.atr_val):
            return None

        min_fvg = 0.75 if "ES" in self.symbol else 3.5
        bars_5m = ctx.session_5m.get(session_name)
        if bars_5m is None or len(bars_5m) < 4:
            return None

        scan_start = pd.Timestamp(f"{ctx.trade_date} 11:30:00")
        scan = bars_5m.loc[scan_start:]

        for i in range(2, len(scan)):
            b0 = scan.iloc[i - 2]
            b1 = scan.iloc[i - 1]
            b2 = scan.iloc[i]
            curr_time = scan.index[i]

            # SHORT: Sweep IB High + reject
            swept_h = (b1["high"] > ref_h or b2["high"] > ref_h)
            closed_inside = (b2["close"] < ref_h) and (b2["close"] < b2["open"])
            bear_fvg = (b0["low"] - b2["high"]) >= min_fvg

            if swept_h and closed_inside and bear_fvg:
                entry = b2["high"]
                sweep_ext = max(b1["high"], b2["high"])
                sl = sweep_ext + (2 * self.tick_size)
                risk = sl - entry
                tp1 = ref_l + (0.50 * ref_r)
                tp2 = ref_l

                if risk > 0 and risk < (0.30 * ctx.atr_val) and tp1 < entry:
                    return TradeSignal(
                        direction="SHORT", entry_price=entry, stop_loss=sl,
                        tp1_price=tp1, tp2_price=tp2, risk_points=risk,
                        entry_time=curr_time, session_name=session_name,
                        metadata={"sweep_ext": sweep_ext, "fvg_size": b0["low"] - b2["high"]},
                    )

            # LONG: Sweep IB Low + reject
            swept_l = (b1["low"] < ref_l or b2["low"] < ref_l)
            closed_inside_l = (b2["close"] > ref_l) and (b2["close"] > b2["open"])
            bull_fvg = (b2["low"] - b0["high"]) >= min_fvg

            if swept_l and closed_inside_l and bull_fvg:
                entry = b2["low"]
                sweep_ext = min(b1["low"], b2["low"])
                sl = sweep_ext - (2 * self.tick_size)
                risk = entry - sl
                tp1 = ref_l + (0.50 * ref_r)
                tp2 = ref_h

                if risk > 0 and risk < (0.30 * ctx.atr_val) and tp1 > entry:
                    return TradeSignal(
                        direction="LONG", entry_price=entry, stop_loss=sl,
                        tp1_price=tp1, tp2_price=tp2, risk_points=risk,
                        entry_time=curr_time, session_name=session_name,
                        metadata={"sweep_ext": sweep_ext, "fvg_size": b2["low"] - b0["high"]},
                    )

        return None


# ============================================================================
# STRATEGY 2: OPENING RANGE BREAKOUT (ORB)
# ============================================================================

class ORBStrategy(RangeStrategy):
    """
    5-minute Opening Range Breakout.
    After 09:35, if price closes beyond OR_5 high/low, enter in breakout direction.
    Stop: opposite end of OR. Target: 1x OR range extension.
    Only trades NY_AM session. Tests momentum continuation hypothesis.
    """

    def __init__(self, symbol: str, tick_size: float = 0.25, or_minutes: int = 5):
        super().__init__("ORB_5m", symbol, tick_size)
        self.or_minutes = or_minutes

    def get_active_sessions(self) -> List[str]:
        return ["NY_AM"]

    def detect_signal(self, ctx: DayContext, session_name: str) -> Optional[TradeSignal]:
        if session_name != "NY_AM":
            return None

        or_end = pd.Timestamp(f"{ctx.trade_date} 09:{30 + self.or_minutes:02d}:00")
        or_bars = ctx.day_bars_1m.loc[f"{ctx.trade_date} 09:30:00":or_end]
        if len(or_bars) < self.or_minutes:
            return None

        or_h = or_bars["high"].max()
        or_l = or_bars["low"].min()
        or_r = or_h - or_l
        if or_r <= 0:
            return None

        # Scan 5m bars after OR for breakout
        scan_start = pd.Timestamp(f"{ctx.trade_date} 09:{30 + self.or_minutes:02d}:00")
        scan_5m = ctx.day_bars_5m.loc[scan_start:]

        for i in range(1, len(scan_5m)):
            bar = scan_5m.iloc[i]
            curr_time = scan_5m.index[i]

            # Only look at first 90 minutes after OR
            if curr_time > pd.Timestamp(f"{ctx.trade_date} 11:00:00"):
                break

            # LONG breakout
            if bar["close"] > or_h:
                entry = bar["close"]
                sl = or_l
                risk = entry - sl
                tp1 = entry + (0.5 * or_r)
                tp2 = entry + (1.0 * or_r)

                if risk > 0 and risk < (0.50 * ctx.atr_val):
                    return TradeSignal("LONG", entry, sl, tp1, tp2, risk, curr_time, session_name)

            # SHORT breakout
            if bar["close"] < or_l:
                entry = bar["close"]
                sl = or_h
                risk = sl - entry
                tp1 = entry - (0.5 * or_r)
                tp2 = entry - (1.0 * or_r)

                if risk > 0 and risk < (0.50 * ctx.atr_val):
                    return TradeSignal("SHORT", entry, sl, tp1, tp2, risk, curr_time, session_name)

        return None


# ============================================================================
# STRATEGY 3: VWAP MEAN REVERSION
# ============================================================================

class VWAPMeanReversionStrategy(RangeStrategy):
    """
    Fade extreme deviation from session VWAP during Midday/PM.
    Entry: when price is >1.0 ATR from session VWAP AND still inside IB.
    Direction: toward VWAP (and opposite IB boundary).
    Stop: IB boundary + 2 ticks. Target: IB midpoint, then opposite IB boundary.
    Tests whether VWAP reversion has edge independent of sweep mechanics.
    """

    def __init__(self, symbol: str, tick_size: float = 0.25):
        super().__init__("VWAP_MR", symbol, tick_size)

    def detect_signal(self, ctx: DayContext, session_name: str) -> Optional[TradeSignal]:
        if session_name not in ("NY_MIDDAY", "NY_PM"):
            return None

        ref_h, ref_l, ref_r = ctx.ib_high, ctx.ib_low, ctx.ib_range
        if np.isnan(ref_h) or np.isnan(ref_l) or ref_r <= 0:
            return None

        vwap = ctx.progressive_vwap.get(session_name)
        bars_1m = ctx.session_bars.get(session_name)
        if vwap is None or bars_1m is None or len(bars_1m) < 20:
            return None

        scan = bars_1m.loc[f"{ctx.trade_date} 11:30:00":]

        for i in range(10, len(scan)):
            curr_time = scan.index[i]
            price = scan["close"].iloc[i]
            vwap_val = vwap.loc[curr_time] if curr_time in vwap.index else np.nan
            if np.isnan(vwap_val):
                continue

            dev = abs(price - vwap_val)

            # Fade when price deviates from VWAP by 0.3 ATR
            # No IB compression filter — test VWAP reversion independent of range regime
            if dev > (0.30 * ctx.atr_val):
                # Short if price above VWAP, Long if below
                if price > vwap_val:
                    entry = price
                    sl = ref_h + (2 * self.tick_size)
                    risk = sl - entry
                    if risk <= 0:
                        continue
                    tp1 = ctx.ib_mid
                    tp2 = ref_l
                    if tp1 < entry and tp2 < entry and risk < (0.50 * ctx.atr_val):
                        return TradeSignal("SHORT", entry, sl, tp1, tp2, risk, curr_time, session_name)
                else:
                    entry = price
                    sl = ref_l - (2 * self.tick_size)
                    risk = entry - sl
                    if risk <= 0:
                        continue
                    tp1 = ctx.ib_mid
                    tp2 = ref_h
                    if tp1 > entry and tp2 > entry and risk < (0.50 * ctx.atr_val):
                        return TradeSignal("LONG", entry, sl, tp1, tp2, risk, curr_time, session_name)

        return None


# ============================================================================
# STRATEGY 4: FAILED BREAKOUT REVERSAL
# ============================================================================

class FailedBreakoutStrategy(RangeStrategy):
    """
    If price breaks IB high/low but closes back inside within 2 bars, enter reversal.
    No FVG requirement (unlike IB Sweep Fade) — tests whether the sweep itself is the edge.
    Entry: close of the rejection bar.
    Stop: beyond the sweep wick extreme. Target: opposite IB boundary.
    """

    def __init__(self, symbol: str, tick_size: float = 0.25):
        super().__init__("Failed_BO", symbol, tick_size)

    def detect_signal(self, ctx: DayContext, session_name: str) -> Optional[TradeSignal]:
        if session_name not in ("NY_MIDDAY", "NY_PM"):
            return None

        ref_h, ref_l, ref_r = ctx.ib_high, ctx.ib_low, ctx.ib_range
        if np.isnan(ref_h) or np.isnan(ref_l) or ref_r <= 0:
            return None

        bars_5m = ctx.session_5m.get(session_name)
        if bars_5m is None or len(bars_5m) < 4:
            return None

        scan = bars_5m.loc[f"{ctx.trade_date} 11:30:00":]

        for i in range(1, len(scan)):
            b1 = scan.iloc[i - 1]
            b2 = scan.iloc[i]
            curr_time = scan.index[i]

            # SHORT: swept high but closed back inside
            if b1["high"] > ref_h and b2["close"] < ref_h and b2["close"] < b2["open"]:
                entry = b2["close"]
                sweep_ext = max(b1["high"], b2["high"])
                sl = sweep_ext + (2 * self.tick_size)
                risk = sl - entry
                tp1 = ctx.ib_mid
                tp2 = ref_l
                if risk > 0 and risk < (0.40 * ctx.atr_val) and tp1 < entry:
                    return TradeSignal("SHORT", entry, sl, tp1, tp2, risk, curr_time, session_name)

            # LONG: swept low but closed back inside
            if b1["low"] < ref_l and b2["close"] > ref_l and b2["close"] > b2["open"]:
                entry = b2["close"]
                sweep_ext = min(b1["low"], b2["low"])
                sl = sweep_ext - (2 * self.tick_size)
                risk = entry - sl
                tp1 = ctx.ib_mid
                tp2 = ref_h
                if risk > 0 and risk < (0.40 * ctx.atr_val) and tp1 > entry:
                    return TradeSignal("LONG", entry, sl, tp1, tp2, risk, curr_time, session_name)

        return None


# ============================================================================
# STRATEGY 5: IB BREAKOUT CONTINUATION
# ============================================================================

class IBBreakoutContinuationStrategy(RangeStrategy):
    """
    If price breaks IB and closes OUTSIDE for 3 consecutive 5m bars, enter pullback.
    Entry: first pullback back to the broken IB boundary.
    Stop: IB midpoint (behind the breakout). Target: 1x IB range extension beyond breakout.
    Tests trend-following inside range structure (opposite of sweep fade).
    """

    def __init__(self, symbol: str, tick_size: float = 0.25):
        super().__init__("IB_BO_Cont", symbol, tick_size)

    def detect_signal(self, ctx: DayContext, session_name: str) -> Optional[TradeSignal]:
        if session_name not in ("NY_MIDDAY", "NY_PM"):
            return None

        ref_h, ref_l, ref_r = ctx.ib_high, ctx.ib_low, ctx.ib_range
        if np.isnan(ref_h) or np.isnan(ref_l) or ref_r <= 0:
            return None

        bars_5m = ctx.session_5m.get(session_name)
        if bars_5m is None or len(bars_5m) < 6:
            return None

        scan = bars_5m.loc[f"{ctx.trade_date} 11:30:00":]

        for i in range(3, len(scan)):
            curr_time = scan.index[i]
            b1 = scan.iloc[i - 1]
            b2 = scan.iloc[i]

            # Check if last 3 bars all closed above IB High
            prev3 = scan.iloc[i - 3:i]
            all_above = all(prev3["close"] > ref_h)
            all_below = all(prev3["close"] < ref_l)

            # LONG continuation: 3 closes above IB High, now pullback to IB High
            if all_above and b2["low"] <= ref_h + (1 * self.tick_size) and b2["close"] > ref_h:
                entry = ref_h
                sl = ctx.ib_mid
                risk = entry - sl
                tp1 = entry + (0.5 * ref_r)
                tp2 = entry + (1.0 * ref_r)
                if risk > 0 and risk < (0.50 * ctx.atr_val):
                    return TradeSignal("LONG", entry, sl, tp1, tp2, risk, curr_time, session_name)

            # SHORT continuation: 3 closes below IB Low, now pullback to IB Low
            if all_below and b2["high"] >= ref_l - (1 * self.tick_size) and b2["close"] < ref_l:
                entry = ref_l
                sl = ctx.ib_mid
                risk = sl - entry
                tp1 = entry - (0.5 * ref_r)
                tp2 = entry - (1.0 * ref_r)
                if risk > 0 and risk < (0.50 * ctx.atr_val):
                    return TradeSignal("SHORT", entry, sl, tp1, tp2, risk, curr_time, session_name)

        return None


# ============================================================================
# BACKTEST ENGINE
# ============================================================================

class BacktestEngine:
    """Shared execution engine. Simulates 1m fills with slippage and commission."""

    def __init__(self, symbol: str, tick_size: float = 0.25):
        self.symbol = symbol
        self.tick_size = tick_size

        # Position sizing
        is_es = "ES" in symbol
        self.contracts_total = 4 if is_es else 2
        self.contracts_per_leg = 2 if is_es else 1
        self.pt_val_per_leg = (5.0 * self.contracts_per_leg) if is_es else (2.0 * self.contracts_per_leg)
        self.comm_total = self.contracts_total * 1.20
        self.slippage_ticks = 1

    def simulate_trade(self, signal: TradeSignal, ctx: DayContext) -> Optional[TradeResult]:
        """Simulate a trade signal on 1m bars with 2-leg management."""
        session_bars = ctx.session_bars.get(signal.session_name)
        if session_bars is None:
            return None

        sim = session_bars.loc[signal.entry_time:]
        if len(sim) == 0:
            return None

        is_long = signal.direction == "LONG"
        entry = signal.entry_price
        sl = signal.stop_loss
        tp1 = signal.tp1_price
        tp2 = signal.tp2_price
        risk = signal.risk_points

        filled = False
        fill_idx = None
        t1_hit = False
        t2_hit = False
        stopped = False
        leg1_pnl = 0.0
        leg2_pnl = 0.0
        exit_time = None

        for t_bar, row in sim.iterrows():
            if not filled:
                if is_long and row["low"] <= entry:
                    filled = True
                    fill_idx = t_bar
                elif not is_long and row["high"] >= entry:
                    filled = True
                    fill_idx = t_bar
                else:
                    continue

            # Check stop
            if is_long and row["low"] <= sl:
                stopped = True
                eff_sl_pnl = -risk - (self.slippage_ticks * self.tick_size)
                leg1_pnl = eff_sl_pnl if not t1_hit else leg1_pnl
                leg2_pnl = eff_sl_pnl if not t1_hit else -(self.slippage_ticks * self.tick_size)
                exit_time = t_bar
                break
            elif not is_long and row["high"] >= sl:
                stopped = True
                eff_sl_pnl = -risk - (self.slippage_ticks * self.tick_size)
                leg1_pnl = eff_sl_pnl if not t1_hit else leg1_pnl
                leg2_pnl = eff_sl_pnl if not t1_hit else -(self.slippage_ticks * self.tick_size)
                exit_time = t_bar
                break

            # Check TP1 (50% scale)
            if not t1_hit:
                if is_long and row["high"] >= tp1:
                    t1_hit = True
                    leg1_pnl = tp1 - entry
                    sl = entry  # Move to BE
                elif not is_long and row["low"] <= tp1:
                    t1_hit = True
                    leg1_pnl = entry - tp1
                    sl = entry

            # Check TP2 (runner)
            if is_long and row["high"] >= tp2:
                t2_hit = True
                leg2_pnl = tp2 - entry
                exit_time = t_bar
                break
            elif not is_long and row["low"] <= tp2:
                t2_hit = True
                leg2_pnl = entry - tp2
                exit_time = t_bar
                break

        if not filled:
            return None

        if not stopped and not t2_hit:
            exit_price = sim["close"].iloc[-1]
            exit_time = sim.index[-1]
            if not t1_hit:
                leg1_pnl = (exit_price - entry) if is_long else (entry - exit_price)
            leg2_pnl = (exit_price - entry) if is_long else (entry - exit_price)

        gross = (leg1_pnl * self.pt_val_per_leg) + (leg2_pnl * self.pt_val_per_leg)
        net = gross - self.comm_total
        total_pts = (leg1_pnl + leg2_pnl) / 2.0
        r_mult = total_pts / risk if risk > 0 else 0.0

        return TradeResult(
            strategy_name=signal.metadata.get("strategy_name", ""),
            symbol=self.symbol, session_name=signal.session_name, date=str(ctx.trade_date.date()),
            direction=signal.direction, entry_time=fill_idx, entry_price=entry,
            stop_loss=signal.stop_loss, tp1_price=tp1, tp2_price=tp2,
            risk_points=risk, t1_hit=t1_hit, t2_hit=t2_hit, stopped_out=stopped,
            exit_time=exit_time, leg1_pnl=leg1_pnl, leg2_pnl=leg2_pnl,
            total_pnl_points=total_pts, total_pnl_dollars=net, r_multiple=r_mult,
        )


# ============================================================================
# DAY CONTEXT BUILDER
# ============================================================================

def build_day_context(
    trade_date: pd.Timestamp,
    df_1m: pd.DataFrame,
    df_5m: pd.DataFrame,
    daily_atr: pd.Series,
) -> Optional[DayContext]:
    """Build zero-lookahead context for a single trading day."""
    prev_day = trade_date - pd.Timedelta(days=1)

    atr_val = daily_atr.get(pd.Timestamp(prev_day), daily_atr.mean())
    if pd.isna(atr_val) or atr_val <= 0:
        atr_val = 20.0
    # Find actual previous trading day (skip weekends)
    for offset in range(1, 5):
        candidate = trade_date - pd.Timedelta(days=offset)
        if candidate.weekday() < 5:
            prev_day = candidate
            break

    prior_rth = df_1m.loc[f"{prev_day} 09:30:00":f"{prev_day} 16:00:00"]
    prior_rth_h = prior_rth["high"].max() if len(prior_rth) > 0 else np.nan
    prior_rth_l = prior_rth["low"].min() if len(prior_rth) > 0 else np.nan

    asia = df_1m.loc[f"{prev_day} 18:00:00":f"{trade_date} 02:00:00"]
    asia_h = asia["high"].max() if len(asia) > 0 else np.nan
    asia_l = asia["low"].min() if len(asia) > 0 else np.nan

    on = df_1m.loc[f"{prev_day} 18:00:00":f"{trade_date} 09:29:00"]
    on_h = on["high"].max() if len(on) > 0 else np.nan
    on_l = on["low"].min() if len(on) > 0 else np.nan

    ib = df_1m.loc[f"{trade_date} 09:30:00":f"{trade_date} 10:30:00"]
    ib_h = ib["high"].max() if len(ib) > 0 else np.nan
    ib_l = ib["low"].min() if len(ib) > 0 else np.nan
    ib_r = (ib_h - ib_l) if not np.isnan(ib_h) else np.nan
    ib_mid = (ib_h + ib_l) / 2.0 if not np.isnan(ib_h) else np.nan

    # Session bars
    sessions = {
        "ASIA": (f"{prev_day} 18:00:00", f"{trade_date} 02:00:00"),
        "LONDON": (f"{trade_date} 02:00:00", f"{trade_date} 08:30:00"),
        "NY_AM": (f"{trade_date} 09:30:00", f"{trade_date} 11:30:00"),
        "NY_MIDDAY": (f"{trade_date} 11:30:00", f"{trade_date} 13:30:00"),
        "NY_PM": (f"{trade_date} 13:30:00", f"{trade_date} 16:00:00"),
    }

    session_bars = {}
    session_5m = {}
    progressive_vwap = {}

    for name, (start, end) in sessions.items():
        bars = df_1m.loc[start:end]
        if len(bars) > 0:
            session_bars[name] = bars
            cum_vol = bars["volume"].cumsum()
            cum_vp = (bars["close"] * bars["volume"]).cumsum()
            progressive_vwap[name] = (cum_vp / cum_vol.replace(0, np.nan)).ffill().bfill()

        bars5 = df_5m.loc[start:end]
        if len(bars5) > 0:
            session_5m[name] = bars5

    day_bars = df_1m.loc[f"{trade_date} 09:30:00":f"{trade_date} 16:00:00"]
    day_bars_5m = df_5m.loc[f"{trade_date} 09:30:00":f"{trade_date} 16:00:00"]

    return DayContext(
        trade_date=trade_date, prev_day=prev_day, atr_val=atr_val,
        prior_rth_high=prior_rth_h, prior_rth_low=prior_rth_l,
        asia_high=asia_h, asia_low=asia_l,
        overnight_high=on_h, overnight_low=on_l,
        ib_high=ib_h, ib_low=ib_l, ib_range=ib_r, ib_mid=ib_mid,
        ib_bars_1m=ib, day_bars_1m=day_bars, day_bars_5m=day_bars_5m,
        session_bars=session_bars, session_5m=session_5m,
        progressive_vwap=progressive_vwap,
    )


# ============================================================================
# MAIN BACKTEST RUNNER
# ============================================================================

def run_comparison(
    symbol: str,
    df_1m: pd.DataFrame,
    df_5m: pd.DataFrame,
    strategies: List[RangeStrategy],
    start_year: int = 2021,
    end_year: int = 2026,
) -> pd.DataFrame:
    """Run all strategies on the same data and return combined results."""
    df_1m = df_1m[(df_1m.index.year >= start_year) & (df_1m.index.year <= end_year)].copy()
    if df_1m.empty:
        return pd.DataFrame()

    # Daily ATR (zero look-ahead: computed from prior day)
    df_daily = df_1m.resample("D").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    tr = pd.concat([
        df_daily["high"] - df_daily["low"],
        (df_daily["high"] - df_daily["close"].shift(1)).abs(),
        (df_daily["low"] - df_daily["close"].shift(1)).abs(),
    ], axis=1).max(axis=1)
    daily_atr = tr.rolling(10, min_periods=1).mean()

    # Trade dates
    df_1m["trade_date"] = df_1m.index.date
    evening = df_1m.index.hour >= 18
    df_1m.loc[evening, "trade_date"] = (df_1m.loc[evening].index + pd.Timedelta(days=1)).date
    unique_dates = sorted(df_1m["trade_date"].unique())

    engine = BacktestEngine(symbol)
    all_trades: List[TradeResult] = []

    print(f"\n[{symbol}] Running {len(strategies)} strategies over {len(unique_dates)} days...")

    for i_date, t_date in enumerate(unique_dates):
        if i_date % 200 == 0:
            print(f"  Day {i_date}/{len(unique_dates)}...")

        ts = pd.Timestamp(t_date)
        if ts.weekday() >= 5:
            continue

        ctx = build_day_context(ts, df_1m, df_5m, daily_atr)
        if ctx is None:
            continue

        for strat in strategies:
            for sess_name in strat.get_active_sessions():
                signal = strat.detect_signal(ctx, sess_name)
                if signal is None:
                    continue
                signal.metadata["strategy_name"] = strat.name
                trade = engine.simulate_trade(signal, ctx)
                if trade is not None:
                    trade.strategy_name = strat.name
                    all_trades.append(trade)

    return pd.DataFrame([t.__dict__ for t in all_trades])


# ============================================================================
# ANALYSIS & REPORTING
# ============================================================================

def generate_comparison_table(df: pd.DataFrame, symbol: str) -> str:
    """Generate side-by-side comparison table."""
    lines = []
    lines.append("=" * 120)
    lines.append(f"RANGE STRATEGY COMPARISON: {symbol}")
    lines.append("=" * 120)

    strategies = df["strategy_name"].unique()
    for strat in sorted(strategies):
        sub = df[df["strategy_name"] == strat].sort_values("entry_time").reset_index(drop=True)
        if len(sub) == 0:
            lines.append(f"\n{strat}: No trades")
            continue

        pnl = sub["total_pnl_dollars"]
        cum = pnl.cumsum()
        dd = cum - cum.cummax()

        # Win rate (net > $1 to exclude near-BE)
        wr = round((pnl > 1).mean() * 100, 1)
        gp = pnl[pnl > 0].sum()
        gl = abs(pnl[pnl < 0].sum())
        pf = round(gp / gl, 2) if gl > 0 else 999.0
        max_dd = round(abs(dd.min()), 0)
        total_net = round(cum.iloc[-1], 0)
        avg_r = round(sub["r_multiple"].mean(), 2)
        t1_rate = round(sub["t1_hit"].mean() * 100, 1)
        t2_rate = round(sub["t2_hit"].mean() * 100, 1)
        stop_rate = round(sub["stopped_out"].mean() * 100, 1)
        trades_per_month = round(len(sub) / ((sub["date"].nunique() / 252) * 12), 1) if sub["date"].nunique() > 0 else 0

        # Year-by-year consistency
        sub["year"] = pd.to_datetime(sub["date"]).dt.year
        yearly_wr = []
        for yr in sorted(sub["year"].unique()):
            ys = sub[sub["year"] == yr]
            yearly_wr.append(f"{yr}:{round((ys['total_pnl_dollars'] > 1).mean() * 100, 0)}%")

        lines.append(f"\n--- {strat} ---")
        lines.append(f"  Trades: {len(sub)} (~{trades_per_month}/mo)")
        lines.append(f"  Win Rate: {wr}%  |  PF: {pf}  |  MaxDD: ${max_dd}  |  Net: ${total_net}")
        lines.append(f"  Avg R: {avg_r}  |  T1: {t1_rate}%  |  T2: {t2_rate}%  |  Stopped: {stop_rate}%")
        lines.append(f"  Avg Win: ${round(pnl[pnl > 0].mean(), 1)}  |  Avg Loss: ${round(pnl[pnl < 0].mean(), 1)}")
        lines.append(f"  Yearly WR: {' | '.join(yearly_wr)}")

        # Prop firm sim
        target = 3000.0
        max_dd_limit = 2000.0
        curr_pnl = 0.0
        curr_peak = 0.0
        passes = 0
        fails = 0
        for _, row in sub.iterrows():
            curr_pnl += row["total_pnl_dollars"]
            if curr_pnl > curr_peak:
                curr_peak = curr_pnl
            if abs(curr_pnl - curr_peak) >= max_dd_limit:
                fails += 1
                curr_pnl = 0.0
                curr_peak = 0.0
            elif curr_pnl >= target:
                passes += 1
                curr_pnl = 0.0
                curr_peak = 0.0

        pr = round(passes / (passes + fails) * 100, 1) if (passes + fails) > 0 else 0
        lines.append(f"  Prop Firm: {passes} passes / {fails} fails ({pr}% pass rate)")

    lines.append("\n" + "=" * 120)
    lines.append("SUMMARY COMPARISON")
    lines.append("=" * 120)
    lines.append(f"{'Strategy':<18} {'Trades':>7} {'WR%':>6} {'PF':>6} {'MaxDD$':>8} {'Net$':>10} {'AvgR':>6} {'PropPass':>9}")
    lines.append("-" * 120)

    for strat in sorted(strategies):
        sub = df[df["strategy_name"] == strat]
        if len(sub) == 0:
            lines.append(f"{strat:<18} {'0':>7} {'--':>6} {'--':>6} {'--':>8} {'--':>10} {'--':>6} {'--':>9}")
            continue

        pnl = sub["total_pnl_dollars"]
        cum = pnl.cumsum()
        dd = cum - cum.cummax()
        wr = round((pnl > 1).mean() * 100, 1)
        gp = pnl[pnl > 0].sum()
        gl = abs(pnl[pnl < 0].sum())
        pf = round(gp / gl, 2) if gl > 0 else 999.0

        # Prop pass rate
        target = 3000.0
        max_dd_limit = 2000.0
        curr_pnl = 0.0
        curr_peak = 0.0
        passes = 0
        fails = 0
        for _, row in sub.sort_values("entry_time").iterrows():
            curr_pnl += row["total_pnl_dollars"]
            if curr_pnl > curr_peak:
                curr_peak = curr_pnl
            if abs(curr_pnl - curr_peak) >= max_dd_limit:
                fails += 1
                curr_pnl = 0.0
                curr_peak = 0.0
            elif curr_pnl >= target:
                passes += 1
                curr_pnl = 0.0
                curr_peak = 0.0

        lines.append(
            f"{strat:<18} {len(sub):>7} {wr:>6} {pf:>6} {round(abs(dd.min()),0):>8} {round(cum.iloc[-1],0):>10} {round(sub['r_multiple'].mean(),2):>6} {passes:>9}"
        )

    return "\n".join(lines)


# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Multi-Strategy Range Trading Comparison")
    parser.add_argument("--start-year", type=int, default=2021)
    parser.add_argument("--end-year", type=int, default=2026)
    parser.add_argument("--symbols", type=str, default="ES,NQ")
    args = parser.parse_args()

    symbols = [s.strip().upper() for s in args.symbols.split(",")]
    all_results = {}

    for sym in symbols:
        sym_key = f"{sym}1" if not sym.endswith("1") else sym
        live_path = Path(f"data/live/live_storage_-{sym}.parquet")
        hist_path = Path(f"data/{sym_key}_1m.parquet")

        dfs = []

        if live_path.exists():
            df_live = pd.read_parquet(live_path)
            if not df_live.empty:
                if "time" in df_live.columns:
                    df_live["datetime"] = pd.to_datetime(df_live["time"], unit="ms")
                    df_live = df_live.set_index("datetime")
                dfs.append(df_live)
                print(f"[{sym}] Live: {len(df_live)} rows ({df_live.index.min()} -> {df_live.index.max()})")

        if hist_path.exists():
            df_hist = pd.read_parquet(hist_path)
            if not df_hist.empty and isinstance(df_hist.index, pd.DatetimeIndex):
                # Filter corrupt tail rows (time column with tiny values)
                if "time" in df_hist.columns:
                    valid = df_hist["time"] > 1e9
                    df_hist = df_hist[valid].drop(columns=["time"])
                dfs.append(df_hist)
                print(f"[{sym}] Hist: {len(df_hist)} rows ({df_hist.index.min()} -> {df_hist.index.max()})")

        if not dfs:
            print(f"[{sym}] No data file found")
            continue

        df_1m = pd.concat(dfs)
        df_1m = df_1m[~df_1m.index.duplicated(keep="last")]
        df_1m = df_1m.sort_index()

        # Ensure timezone-naive ET for simpler slicing
        if df_1m.index.tz is not None:
            df_1m.index = df_1m.index.tz_convert("America/New_York").tz_localize(None)

        print(f"[{sym}] Fused: {len(df_1m)} rows ({df_1m.index.min()} -> {df_1m.index.max()})")

        # 5m resample
        df_5m = df_1m.resample("5min").agg({
            "open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"
        }).dropna()

        # Build strategies
        strategies = [
            IBSweepFadeStrategy(sym),
            ORBStrategy(sym),
            VWAPMeanReversionStrategy(sym),
            FailedBreakoutStrategy(sym),
            IBBreakoutContinuationStrategy(sym),
        ]

        df_results = run_comparison(sym, df_1m, df_5m, strategies, args.start_year, args.end_year)
        all_results[sym] = df_results

        if not df_results.empty:
            report = generate_comparison_table(df_results, sym)
            print(report)

            # Save
            out_path = Path(f"data/derived/range_strategy_comparison_{sym}_{args.start_year}_{args.end_year}.csv")
            out_path.parent.mkdir(parents=True, exist_ok=True)
            df_results.to_csv(out_path, index=False)
            print(f"\nSaved to {out_path}")

    # Combined report
    if all_results:
        combined = pd.concat(all_results.values(), ignore_index=True)
        combined_path = Path(f"data/derived/range_strategy_comparison_all_{args.start_year}_{args.end_year}.csv")
        combined.to_csv(combined_path, index=False)
        print(f"\nCombined results saved to {combined_path}")


if __name__ == "__main__":
    main()