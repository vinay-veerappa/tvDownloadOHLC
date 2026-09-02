"""
========================================================================================
Institutional NT8 Parity Backtesting Engine (Trading Framework Layer 5)
========================================================================================
Plugs into scripts.trading_framework as the canonical execution engine:
- Guarantees 100% parity with NinjaTrader 8's RiskManagerBase.cs
- Enforces position concurrency lockout (no duplicate entries while in a trade)
- Implements the 2-consecutive-loss 30-min pause & 3-loss hard stop
- Enforces strict 0.25 tick snapping for futures limit orders, stops, and targets
- Resolves intra-bar arrival ambiguity with Cover The Queen breakeven lock
- Returns standardized output compatible with tearsheets and PropFirmSimulator
========================================================================================
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import numpy as np
import pandas as pd

_current_dir = Path(__file__).resolve().parent
while _current_dir.name and _current_dir.name != "scripts":
    _current_dir = _current_dir.parent
if _current_dir.name == "scripts":
    _root_dir = str(_current_dir.parent)
    if _root_dir not in sys.path:
        sys.path.insert(0, _root_dir)

from scripts.trading_framework.core.base import BaseBacktester
from src.execution.nt8_parity_engine import NT8ParityEngine, NT8Trade


class NT8ParityBacktester(BaseBacktester):
    """
    NinjaTrader 8 Parity Backtester for the Statistical Trading Framework.
    """

    def __init__(
        self,
        account_size: float = 50000.0,
        commission_per_contract_rt: float = 1.40,
        slippage_ticks: float = 0.0,
        max_trades_per_day: int = 3,
        max_consecutive_losers: int = 2,
        pause_minutes: int = 30,
        hard_stop_losers: int = 3,
        daily_max_loss: float = 1500.0,
        contracts: int = 2,
    ):
        self.account_size = account_size
        self.commission = commission_per_contract_rt
        self.slippage_ticks = slippage_ticks
        self.max_trades_per_day = max_trades_per_day
        self.max_consecutive_losers = max_consecutive_losers
        self.pause_minutes = pause_minutes
        self.hard_stop_losers = hard_stop_losers
        self.daily_max_loss = daily_max_loss
        self.contracts = contracts

        self.multipliers = {
            "NQ1": 20.0, "NQ": 20.0, "MNQ": 2.0,
            "ES1": 50.0, "ES": 50.0, "MES": 5.0,
            "RTY": 50.0, "M2K": 5.0,
            "CL": 1000.0, "MCL": 100.0,
            "GC": 100.0, "MGC": 10.0,
        }

    def run(
        self,
        signals: Union[pd.Series, pd.DataFrame],
        data: pd.DataFrame,
        risk_params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Execute trades matching NinjaTrader 8 RiskManagerBase state machine.
        """
        ticker = risk_params.get("ticker", "NQ1").upper()
        pt_val = self.multipliers.get(ticker, 20.0)
        tick_sz = 0.25 if ("NQ" in ticker or "ES" in ticker or "RTY" in ticker) else 0.01

        # Extract limits and stops if provided in DataFrame, else calculate default 5 bps
        if isinstance(signals, pd.DataFrame):
            sig_series = signals.get("direction_int", signals.get("signal", pd.Series(0, index=data.index)))
            lmt_series = signals.get("entry_price", data["close"])
            sl_series = signals.get("stop_price", data["close"] * 0.9995)
        else:
            sig_series = signals
            # Default to limit at Close and stop at 5 bps
            lmt_series = data["close"]
            sl_series = np.where(sig_series == 1, data["close"] * (1 - 0.0005), data["close"] * (1 + 0.0005))
            sl_series = pd.Series(sl_series, index=data.index)

        engine = NT8ParityEngine(
            point_value=pt_val,
            tick_size=tick_sz,
            max_trades_per_day=risk_params.get("max_trades_per_day", self.max_trades_per_day),
            max_consecutive_losers=risk_params.get("max_consecutive_losers", self.max_consecutive_losers),
            pause_minutes=risk_params.get("pause_minutes", self.pause_minutes),
            hard_stop_losers=risk_params.get("hard_stop_losers", self.hard_stop_losers),
            daily_max_loss=risk_params.get("daily_max_loss", self.daily_max_loss),
            contracts=risk_params.get("contracts", self.contracts),
            commission_per_contract_rt=risk_params.get("commission", self.commission),
            slippage_ticks=risk_params.get("slippage_ticks", self.slippage_ticks),
        )

        queen_bps = risk_params.get("queen_bps", 10.0)
        runner_bps = risk_params.get("runner_bps", 30.0)

        df_trades = engine.simulate(
            df=data,
            signals=sig_series,
            limit_prices=lmt_series,
            stop_losses=sl_series,
            queen_bps=queen_bps,
            runner_bps=runner_bps,
            order_timeout_bars=risk_params.get("order_timeout_bars", 6),
            earliest_entry_hhmm=risk_params.get("earliest_entry_hhmm", 945),
            latest_entry_hhmm=risk_params.get("latest_entry_hhmm", 1530),
            flatten_hhmm=risk_params.get("flatten_hhmm", 1555),
            filter_lunch=risk_params.get("filter_lunch", True),
        )

        if df_trades.empty:
            return {
                "total_trades": 0,
                "win_rate_%": 0.0,
                "profit_factor": 0.0,
                "net_profit": 0.0,
                "max_drawdown": 0.0,
                "trades_detailed": pd.DataFrame(),
                "equity_curve": pd.Series([self.account_size], index=[data.index[0]]),
            }

        # Calculate performance metrics
        df_trades["pnl_pct"] = (df_trades["total_pnl_usd"] / self.account_size) * 100.0
        df_trades["is_win"] = df_trades["total_pnl_usd"] > 0
        df_trades["cum_pnl"] = df_trades["total_pnl_usd"].cumsum()
        df_trades["equity"] = self.account_size + df_trades["cum_pnl"]

        gross_profit = df_trades[df_trades["total_pnl_usd"] > 0]["total_pnl_usd"].sum()
        gross_loss = abs(df_trades[df_trades["total_pnl_usd"] < 0]["total_pnl_usd"].sum())
        pf = (gross_profit / gross_loss) if gross_loss > 0 else np.nan
        win_rate = df_trades["is_win"].mean() * 100.0
        net_profit = df_trades["total_pnl_usd"].sum()

        cum_peak = df_trades["equity"].cummax()
        dd_series = df_trades["equity"] - cum_peak
        max_dd = abs(dd_series.min()) if not dd_series.empty else 0.0

        # Resample daily returns for Sharpe
        df_trades["date"] = pd.to_datetime(df_trades["exit_time"]).dt.date
        daily_pnl = df_trades.groupby("date")["total_pnl_usd"].sum()
        daily_ret = daily_pnl / self.account_size
        sharpe = (daily_ret.mean() / daily_ret.std()) * np.sqrt(252) if daily_ret.std() > 0 else 0.0

        return {
            "total_trades": len(df_trades),
            "win_rate_%": win_rate,
            "profit_factor": pf,
            "gross_profit": gross_profit,
            "gross_loss": gross_loss,
            "net_profit": net_profit,
            "max_drawdown": max_dd,
            "sharpe_ratio": sharpe,
            "trades_detailed": df_trades,
            "equity_curve": df_trades.set_index("exit_time")["equity"],
        }
