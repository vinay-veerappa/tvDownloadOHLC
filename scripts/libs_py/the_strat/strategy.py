"""The Strat Automated Backtesting Engine.

Simulates automated execution of Strat setups (2-1-2 continuations/reversals, 2-2 traps)
filtered by Full Time Frame Continuity (FTFC), ATR bounds, and session time windows.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time
from typing import Any
import numpy as np
import pandas as pd

from scripts.libs_py.the_strat.combos import ComboType, StratComboDetector, StratSetup, TradeDirection
from scripts.libs_py.the_strat.taxonomy import classify_bars_df


@dataclass
class StratTradeResult:
    entry_index: int
    entry_time: Any
    exit_index: int
    exit_time: Any
    direction: TradeDirection
    combo_type: ComboType
    entry_price: float
    exit_price: float
    stop_loss: float
    target_price: float
    pnl_points: float
    pnl_dollars: float
    return_r: float
    hit_target: bool
    hit_stop: bool
    bars_held: int
    exit_reason: str


@dataclass
class StratBacktestSummary:
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    net_pnl_points: float = 0.0
    net_pnl_dollars: float = 0.0
    max_drawdown_dollars: float = 0.0
    avg_trade_points: float = 0.0
    avg_win_points: float = 0.0
    avg_loss_points: float = 0.0
    trades: list[StratTradeResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_trades": self.total_trades,
            "win_rate_pct": round(self.win_rate * 100, 2),
            "profit_factor": round(self.profit_factor, 2),
            "net_pnl_pts": round(self.net_pnl_points, 2),
            "net_pnl_dollars": round(self.net_pnl_dollars, 2),
            "max_drawdown_dollars": round(self.max_drawdown_dollars, 2),
            "avg_trade_pts": round(self.avg_trade_points, 2),
            "avg_win_pts": round(self.avg_win_points, 2),
            "avg_loss_pts": round(self.avg_loss_points, 2),
        }


class StratBacktester:
    """High-speed vector/event backtester for Strat setups."""

    def __init__(
        self,
        point_value: float = 20.0,  # $20/pt for NQ, $50/pt for ES, $2 for MNQ
        commission_per_contract: float = 2.05,
        slippage_ticks: int = 1,
        tick_size: float = 0.25,
    ):
        self.point_value = point_value
        self.commission_per_contract = commission_per_contract
        self.slippage_points = slippage_ticks * tick_size
        self.tick_size = tick_size
        self.detector = StratComboDetector(tick_size=tick_size)

    def run_backtest(
        self,
        df: pd.DataFrame,
        allowed_combos: set[ComboType] | None = None,
        min_rr_ratio: float = 1.0,
        max_holding_bars: int = 20,
        start_time_et: time = time(9, 30),
        end_time_et: time = time(15, 45),
    ) -> StratBacktestSummary:
        """Run backtest on an OHLC DataFrame."""
        if df.empty:
            return StratBacktestSummary()

        cols = {c.lower(): c for c in df.columns}
        h = df[cols["high"]].values
        l = df[cols["low"]].values
        c = df[cols["close"]].values
        o = df[cols["open"]].values
        timestamps = df.index if isinstance(df.index, pd.DatetimeIndex) else pd.to_datetime(df.index)

        # Detect all setups
        setups = self.detector.scan_dataframe(df, min_rr_ratio=min_rr_ratio)
        if allowed_combos is not None:
            setups = [s for s in setups if s.combo_type in allowed_combos]

        trades: list[StratTradeResult] = []

        last_exit_idx = -1

        for setup in setups:
            idx = setup.index
            # Skip if we were in a trade
            if idx <= last_exit_idx:
                continue

            ts = timestamps[idx]
            if hasattr(ts, "time"):
                t = ts.time()
                if t < start_time_et or t > end_time_et:
                    continue

            # Simulate entry on the bar that triggered the setup
            direction = setup.direction
            entry_price = setup.entry_trigger_price
            stop_loss = setup.stop_loss_price
            target = setup.magnitude_1_target

            # Apply entry slippage
            if direction == TradeDirection.LONG:
                actual_entry = entry_price + self.slippage_points
            else:
                actual_entry = entry_price - self.slippage_points

            # Track trade forward bar-by-bar
            exit_idx = idx
            exit_price = actual_entry
            exit_reason = "max_bars"
            hit_target = False
            hit_stop = False

            for f_idx in range(idx, min(idx + max_holding_bars, len(df))):
                bar_h = h[f_idx]
                bar_l = l[f_idx]
                bar_c = c[f_idx]

                if direction == TradeDirection.LONG:
                    # Check stop loss first for conservative modeling
                    if bar_l <= stop_loss:
                        exit_idx = f_idx
                        exit_price = stop_loss - self.slippage_points
                        exit_reason = "stop_loss"
                        hit_stop = True
                        break
                    # Check target
                    if bar_h >= target:
                        exit_idx = f_idx
                        exit_price = target
                        exit_reason = "target_mag1"
                        hit_target = True
                        break
                else:  # SHORT
                    if bar_h >= stop_loss:
                        exit_idx = f_idx
                        exit_price = stop_loss + self.slippage_points
                        exit_reason = "stop_loss"
                        hit_stop = True
                        break
                    if bar_l <= target:
                        exit_idx = f_idx
                        exit_price = target
                        exit_reason = "target_mag1"
                        hit_target = True
                        break

            # If no stop/target triggered within window, exit at close of last bar
            if not hit_target and not hit_stop:
                exit_idx = min(idx + max_holding_bars - 1, len(df) - 1)
                exit_price = c[exit_idx]
                exit_reason = "time_exit"

            last_exit_idx = exit_idx

            # Calculate PnL
            if direction == TradeDirection.LONG:
                pnl_pts = exit_price - actual_entry
            else:
                pnl_pts = actual_entry - exit_price

            gross_dollars = pnl_pts * self.point_value
            net_dollars = gross_dollars - (2 * self.commission_per_contract)
            risk_pts = max(setup.risk_points, self.tick_size)
            return_r = pnl_pts / risk_pts

            trades.append(StratTradeResult(
                entry_index=idx,
                entry_time=timestamps[idx],
                exit_index=exit_idx,
                exit_time=timestamps[exit_idx],
                direction=direction,
                combo_type=setup.combo_type,
                entry_price=actual_entry,
                exit_price=exit_price,
                stop_loss=stop_loss,
                target_price=target,
                pnl_points=pnl_pts,
                pnl_dollars=net_dollars,
                return_r=return_r,
                hit_target=hit_target,
                hit_stop=hit_stop,
                bars_held=exit_idx - idx + 1,
                exit_reason=exit_reason,
            ))

        # Summarize results
        summary = StratBacktestSummary(trades=trades)
        if not trades:
            return summary

        summary.total_trades = len(trades)
        wins = [t for t in trades if t.pnl_dollars > 0]
        losses = [t for t in trades if t.pnl_dollars <= 0]
        summary.winning_trades = len(wins)
        summary.losing_trades = len(losses)
        summary.win_rate = len(wins) / len(trades) if trades else 0.0

        total_win_dollars = sum(t.pnl_dollars for t in wins)
        total_loss_dollars = abs(sum(t.pnl_dollars for t in losses))
        summary.profit_factor = (total_win_dollars / total_loss_dollars) if total_loss_dollars > 0 else (999.0 if total_win_dollars > 0 else 0.0)

        summary.net_pnl_points = sum(t.pnl_points for t in trades)
        summary.net_pnl_dollars = sum(t.pnl_dollars for t in trades)

        # Max drawdown
        cum_equity = np.cumsum([t.pnl_dollars for t in trades])
        peak = np.maximum.accumulate(cum_equity)
        drawdowns = peak - cum_equity
        summary.max_drawdown_dollars = float(np.max(drawdowns)) if len(drawdowns) > 0 else 0.0

        summary.avg_trade_points = summary.net_pnl_points / len(trades)
        summary.avg_win_points = sum(t.pnl_points for t in wins) / len(wins) if wins else 0.0
        summary.avg_loss_points = sum(t.pnl_points for t in losses) / len(losses) if losses else 0.0

        return summary
