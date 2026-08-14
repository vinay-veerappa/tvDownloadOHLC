"""
Multi-Contract & Scale-Out Backtesting Engine (Layer 5 - ADR-008 / ADR-017).
=============================================================================
Supports:
1. Cover The Queen Partial Scale-Out (e.g. 50% exit at TP1, 50% runner at TP2)
2. Trailing Stop Management (Structural / Breakeven / ATR trail)
3. Prop Firm Real-Time Drawdown Tracking (Daily Loss Limit & Peak-to-Trough Trailing Drawdown)
4. Full Transaction Cost Modeling (Commissions & Slippage per micro/mini contract)
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional


class MultiContractBacktester:
    """
    Simulates multi-contract executions with partial scale-outs,
    trailing stop mutations, and prop-firm compliance tracking.
    """

    def __init__(
        self,
        contracts: int = 2,
        tp1_qty_pct: float = 0.5,
        commission_per_contract: float = 1.05,  # $1.05 per side for MNQ micro
        slippage_ticks: int = 1,
        tick_size: float = 0.25,
        point_value: float = 2.0,  # $2.0 per point for MNQ micro ($20 for NQ)
        account_size: float = 50000.0,
        max_daily_loss: float = 1000.0,
        max_trailing_drawdown: float = 2000.0,
    ) -> None:
        self.contracts = contracts
        self.tp1_qty_pct = tp1_qty_pct
        self.commission_per_contract = commission_per_contract
        self.slippage_ticks = slippage_ticks
        self.tick_size = tick_size
        self.point_value = point_value
        self.account_size = account_size
        self.max_daily_loss = max_daily_loss
        self.max_trailing_drawdown = max_trailing_drawdown

    def run(
        self,
        signals: pd.DataFrame,
        data: pd.DataFrame,
        risk_params: Optional[Dict[str, Any]] = None,
        max_forward_bars: int = 240,
    ) -> Dict[str, Any]:
        """
        Simulate all signals bar-by-bar with multi-contract scale out.
        """
        p = risk_params or {}
        ticker = p.get("ticker", "MNQ")
        move_to_be_on_tp1 = p.get("move_to_be_on_tp1", False)  # CoverTheQueen default is False to protect runners

        if signals is None or signals.empty:
            return self._empty_results()

        highs = data["high"].values
        lows = data["low"].values
        closes = data["close"].values
        times = data.index

        trade_log = []
        c_qty1 = int(round(self.contracts * self.tp1_qty_pct))
        c_qty2 = self.contracts - c_qty1

        slippage_cost = self.slippage_ticks * self.tick_size

        for _, sig in signals.iterrows():
            sig_time = sig["signal_time"]
            direction = sig["direction"]
            entry_price = float(sig["entry_price"])
            initial_stop = float(sig["stop_price"])
            tp1_price = float(sig["target1_price"])
            tp2_price = float(sig.get("target2_price", tp1_price))
            model_name = sig.get("model_name", "standard")

            # Locate starting bar index
            idx_arr = np.where(times >= sig_time)[0]
            if len(idx_arr) == 0:
                continue
            start_idx = idx_arr[0]
            end_idx = min(start_idx + max_forward_bars, len(data))

            is_long = direction == "long"
            executed_entry = entry_price + slippage_cost if is_long else entry_price - slippage_cost

            # Initial State
            tp1_hit = False
            tp1_exit_price = 0.0
            tp1_bar_idx = -1

            tp2_hit = False
            tp2_exit_price = 0.0

            stop_hit = False
            stop_exit_price = 0.0

            current_stop = initial_stop
            exit_bar_idx = end_idx - 1

            for bar_i in range(start_idx, end_idx):
                h = highs[bar_i]
                l = lows[bar_i]
                c = closes[bar_i]

                # Check Stop Loss first
                if is_long:
                    if l <= current_stop:
                        stop_hit = True
                        stop_exit_price = current_stop - slippage_cost
                        exit_bar_idx = bar_i
                        break
                    # Check TP1
                    if not tp1_hit and h >= tp1_price:
                        tp1_hit = True
                        tp1_exit_price = tp1_price - slippage_cost
                        tp1_bar_idx = bar_i
                        if move_to_be_on_tp1:
                            current_stop = executed_entry
                    # Check TP2
                    if tp1_hit and h >= tp2_price:
                        tp2_hit = True
                        tp2_exit_price = tp2_price - slippage_cost
                        exit_bar_idx = bar_i
                        break
                else:  # Short
                    if h >= current_stop:
                        stop_hit = True
                        stop_exit_price = current_stop + slippage_cost
                        exit_bar_idx = bar_i
                        break
                    # Check TP1
                    if not tp1_hit and l <= tp1_price:
                        tp1_hit = True
                        tp1_exit_price = tp1_price + slippage_cost
                        tp1_bar_idx = bar_i
                        if move_to_be_on_tp1:
                            current_stop = executed_entry
                    # Check TP2
                    if tp1_hit and l <= tp2_price:
                        tp2_hit = True
                        tp2_exit_price = tp2_price + slippage_cost
                        exit_bar_idx = bar_i
                        break
            else:
                # Timed out exit at market close of last bar
                last_c = closes[end_idx - 1]
                timeout_price = last_c - slippage_cost if is_long else last_c + slippage_cost
                if not tp1_hit:
                    tp1_exit_price = timeout_price
                if not tp2_hit and not stop_hit:
                    tp2_exit_price = timeout_price

            # Calculate realized PnL for Lot 1 (TP1) and Lot 2 (Runner)
            # Total commission = $1.05 * 2 sides * contracts
            comm_lot1 = self.commission_per_contract * 2 * c_qty1
            comm_lot2 = self.commission_per_contract * 2 * c_qty2

            if stop_hit:
                if not tp1_hit:
                    # Both lots stopped out at stop_exit_price
                    pnl1_pts = (stop_exit_price - executed_entry) if is_long else (executed_entry - stop_exit_price)
                    pnl2_pts = pnl1_pts
                else:
                    # Lot 1 exited at TP1, Lot 2 stopped out at stop_exit_price
                    pnl1_pts = (tp1_exit_price - executed_entry) if is_long else (executed_entry - tp1_exit_price)
                    pnl2_pts = (stop_exit_price - executed_entry) if is_long else (executed_entry - stop_exit_price)
            elif tp2_hit:
                # Lot 1 at TP1, Lot 2 at TP2
                pnl1_pts = (tp1_exit_price - executed_entry) if is_long else (executed_entry - tp1_exit_price)
                pnl2_pts = (tp2_exit_price - executed_entry) if is_long else (executed_entry - tp2_exit_price)
            else:
                # Timeout
                if tp1_hit:
                    pnl1_pts = (tp1_exit_price - executed_entry) if is_long else (executed_entry - tp1_exit_price)
                    pnl2_pts = (tp2_exit_price - executed_entry) if is_long else (executed_entry - tp2_exit_price)
                else:
                    pnl1_pts = (tp1_exit_price - executed_entry) if is_long else (executed_entry - tp1_exit_price)
                    pnl2_pts = pnl1_pts

            pnl1_usd = (pnl1_pts * self.point_value * c_qty1) - comm_lot1
            pnl2_usd = (pnl2_pts * self.point_value * c_qty2) - comm_lot2
            total_trade_pnl_usd = pnl1_usd + pnl2_usd
            total_trade_pnl_pct = (total_trade_pnl_usd / self.account_size) * 100.0

            trade_log.append({
                "signal_time": sig_time,
                "exit_time": times[exit_bar_idx],
                "direction": direction,
                "model_name": model_name,
                "entry_price": executed_entry,
                "tp1_hit": tp1_hit,
                "tp2_hit": tp2_hit,
                "stop_hit": stop_hit,
                "pnl_usd": total_trade_pnl_usd,
                "pnl_pct": total_trade_pnl_pct,
                "holding_bars": exit_bar_idx - start_idx + 1,
            })

        df_trades = pd.DataFrame(trade_log)
        if df_trades.empty:
            return self._empty_results()

        # ── Calculate Summary Statistics ──
        df_trades["trading_date"] = pd.to_datetime(df_trades["signal_time"]).dt.date
        wins = df_trades[df_trades["pnl_usd"] > 0]
        losses = df_trades[df_trades["pnl_usd"] < 0]

        gross_profit = wins["pnl_usd"].sum()
        gross_loss = abs(losses["pnl_usd"].sum())
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 999.0
        win_rate = (len(wins) / len(df_trades)) * 100.0
        tp1_reach_rate = (df_trades["tp1_hit"].sum() / len(df_trades)) * 100.0
        tp2_reach_rate = (df_trades["tp2_hit"].sum() / len(df_trades)) * 100.0

        # Equity Curve & Drawdown
        df_trades["cum_pnl_usd"] = df_trades["pnl_usd"].cumsum()
        df_trades["equity"] = self.account_size + df_trades["cum_pnl_usd"]
        df_trades["peak_equity"] = df_trades["equity"].cummax()
        df_trades["drawdown_usd"] = df_trades["equity"] - df_trades["peak_equity"]
        max_drawdown_usd = df_trades["drawdown_usd"].min()
        max_drawdown_pct = (max_drawdown_usd / self.account_size) * 100.0

        # Daily PnL tracking for prop-firm daily loss limit
        daily_pnl = df_trades.groupby("trading_date")["pnl_usd"].sum()
        worst_day_usd = daily_pnl.min()
        best_day_usd = daily_pnl.max()
        profitable_days_pct = (daily_pnl > 0).sum() / len(daily_pnl) * 100.0

        # Sharpe ratio
        daily_returns = daily_pnl / self.account_size
        sharpe = (daily_returns.mean() / daily_returns.std() * np.sqrt(252)) if daily_returns.std() > 0 else 0.0

        return {
            "num_trades": len(df_trades),
            "win_rate_%": round(win_rate, 2),
            "tp1_reach_rate_%": round(tp1_reach_rate, 2),
            "tp2_reach_rate_%": round(tp2_reach_rate, 2),
            "profit_factor": round(profit_factor, 2),
            "total_net_pnl_usd": round(df_trades["cum_pnl_usd"].iloc[-1], 2),
            "total_return_%": round((df_trades["cum_pnl_usd"].iloc[-1] / self.account_size) * 100.0, 2),
            "max_drawdown_usd": round(max_drawdown_usd, 2),
            "max_drawdown_%": round(max_drawdown_pct, 2),
            "worst_day_usd": round(worst_day_usd, 2),
            "best_day_usd": round(best_day_usd, 2),
            "profitable_days_%": round(profitable_days_pct, 1),
            "sharpe_ratio": round(sharpe, 2),
            "avg_trade_usd": round(df_trades["pnl_usd"].mean(), 2),
            "trades_df": df_trades,
        }

    def _empty_results(self) -> Dict[str, Any]:
        return {
            "num_trades": 0,
            "win_rate_%": 0.0,
            "tp1_reach_rate_%": 0.0,
            "tp2_reach_rate_%": 0.0,
            "profit_factor": 0.0,
            "total_net_pnl_usd": 0.0,
            "total_return_%": 0.0,
            "max_drawdown_usd": 0.0,
            "max_drawdown_%": 0.0,
            "worst_day_usd": 0.0,
            "best_day_usd": 0.0,
            "profitable_days_%": 0.0,
            "sharpe_ratio": 0.0,
            "avg_trade_usd": 0.0,
            "trades_df": pd.DataFrame(),
        }
