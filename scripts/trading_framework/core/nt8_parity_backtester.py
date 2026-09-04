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
from scripts.trading_framework.core.backtest_engine import (
    VectorizedBacktester,
    validate_signal_geometry,
)
from scripts.execution.nt8_parity_engine import NT8ParityEngine, NT8Trade


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

    # ------------------------------------------------------------------
    # Signal input shapes
    #
    # This engine consumes PER-BAR arrays: one signal/limit/stop value for every
    # bar in `data`. Two different callers supply two different things, and until
    # 2026-09-04 the code assumed the first:
    #
    #   * `scripts/research/validate_apples_to_apples.py` passes per-bar Series,
    #     which is what the engine wants;
    #   * every strategy in `strategies/registry.py` emits the CANONICAL frame --
    #     one ROW per signal, carrying `signal_time`, `direction`, `entry_price`,
    #     `stop_price`, `target1_price`, with a RangeIndex.
    #
    # Fed the canonical frame, the old code did:
    #
    #     sig_series = signals.get("direction_int",
    #                              signals.get("signal", pd.Series(0, index=data.index)))
    #     lmt_series = signals.get("entry_price", data["close"])
    #
    # The canonical frame has neither `direction_int` nor `signal`, so
    # `sig_series` fell all the way through to a zero series of length
    # len(data), while `lmt_series` and `sl_series` came back at length
    # n_signals. The Rust core then raised "input arrays must have equal
    # length". `--engine nt8_parity` is the ADR-024 DEFAULT, so a default
    # invocation of the research pipeline had never completed.
    #
    # Note which half of that is the dangerous one. The crash was the LOUD
    # failure. The quiet one is `sig_series` being all zeros: on any input where
    # the lengths happened to agree, this engine would have run with no signals
    # at all and reported a clean null result -- zero trades, no error. The
    # adapter therefore refuses an unrecognised shape by name rather than
    # defaulting to a zero series.
    # ------------------------------------------------------------------
    _CANONICAL_COLS = ("signal_time", "direction", "entry_price", "stop_price")

    def _prepare_series(self, signals, data):
        """Normalise either accepted input shape to per-bar arrays.

        Returns (signal, limit, stop, alignment_report). The alignment report is
        the same structure `VectorizedBacktester` produces, so a run record can
        store it and a caller can see how many signals actually landed.
        """
        default_stop_long = data["close"] * (1 - 0.0005)
        default_stop_short = data["close"] * (1 + 0.0005)

        # (a) per-bar Series -- the shape this engine was written for
        if isinstance(signals, pd.Series):
            if not signals.index.equals(data.index):
                raise ValueError(
                    "a per-bar signal Series must share the price frame's index; "
                    "got {} signal rows vs {} bars. Index-aligned arithmetic "
                    "would silently produce NaN rather than failing.".format(
                        len(signals.index), len(data.index)))
            sl = np.where(signals.to_numpy() == 1, default_stop_long, default_stop_short)
            return (signals, data["close"], pd.Series(sl, index=data.index),
                    {"inputShape": "per_bar_series", "signals_in": int((signals != 0).sum()),
                     "signals_kept": int((signals != 0).sum())})

        if not isinstance(signals, pd.DataFrame):
            raise ValueError(
                "unsupported signal type {}; pass a per-bar Series or the "
                "canonical signal DataFrame".format(type(signals).__name__))

        # (b) per-bar DataFrame carrying an explicit direction column
        if len(signals) == len(data) and (
                "direction_int" in signals.columns or "signal" in signals.columns):
            col = "direction_int" if "direction_int" in signals.columns else "signal"
            sig = pd.Series(signals[col].to_numpy(), index=data.index)
            lmt = (pd.Series(signals["entry_price"].to_numpy(), index=data.index)
                   if "entry_price" in signals.columns else data["close"])
            sl = (pd.Series(signals["stop_price"].to_numpy(), index=data.index)
                  if "stop_price" in signals.columns
                  else pd.Series(np.where(sig.to_numpy() == 1, default_stop_long,
                                          default_stop_short), index=data.index))
            return sig, lmt, sl, {"inputShape": "per_bar_frame",
                                  "signals_in": int((sig != 0).sum()),
                                  "signals_kept": int((sig != 0).sum())}

        # (c) the canonical one-row-per-signal frame -- expand it onto the bars
        if all(c in signals.columns for c in self._CANONICAL_COLS):
            # Same geometry check as the vectorized engine, and this is the
            # engine on which it was found: 36 of 38 trades here exited with
            # reason "Stop Loss" for an average of +48.6 points.
            signals, geometry = validate_signal_geometry(signals, {})
            # Reuse the bounded aligner rather than reimplementing bfill here:
            # the unbounded version of exactly this mapping is what collapsed a
            # whole signal set onto bar 0 elsewhere in this codebase.
            placed, idx, alignment = VectorizedBacktester._align_signals_to_frame(
                signals, data, {})
            alignment["inputShape"] = "canonical_signal_frame"
            alignment["geometry"] = geometry

            sig = pd.Series(0, index=data.index, dtype="int32")
            lmt = data["close"].astype("float64").copy()
            sl = pd.Series(np.where(np.zeros(len(data)) == 1, default_stop_long,
                                    default_stop_short), index=data.index)
            if len(placed):
                dirs = np.where(
                    placed["direction"].astype(str).str.lower().to_numpy() == "long",
                    1, -1).astype("int32")
                sig.iloc[idx] = dirs
                lmt.iloc[idx] = placed["entry_price"].to_numpy(dtype="float64")
                sl.iloc[idx] = placed["stop_price"].to_numpy(dtype="float64")
            return sig, lmt, sl, alignment

        raise ValueError(
            "unrecognised signal frame: {} rows against {} bars, columns {}. "
            "Expected either a per-bar frame with `direction_int`/`signal`, or "
            "the canonical frame with {}. Refusing rather than defaulting to a "
            "zero signal series, which would report a clean null result."
            .format(len(signals), len(data), list(signals.columns)[:12],
                    list(self._CANONICAL_COLS)))

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

        # See _prepare_series: this block used to assume a PER-BAR frame and
        # silently produced mismatched arrays for the canonical one-row-per-signal
        # frame that every registry strategy emits.
        sig_series, lmt_series, sl_series, alignment = self._prepare_series(
            signals, data)

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

        df_1m = risk_params.get("data_1m", None)
        if df_1m is not None:
            df_trades = engine.simulate_mtf(
                df_5m=data,
                df_1m=df_1m,
                signals_5m=sig_series,
                queen_bps=queen_bps,
                runner_bps=runner_bps,
                stop_loss_bps=risk_params.get("stop_loss_bps", 2.5),
                earliest_entry_hhmm=risk_params.get("earliest_entry_hhmm", 945),
                latest_entry_hhmm=risk_params.get("latest_entry_hhmm", 1530),
                flatten_hhmm=risk_params.get("flatten_hhmm", 1555),
                filter_lunch=risk_params.get("filter_lunch", True),
            )
        else:
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
                "signal_alignment": alignment,
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
            "signal_alignment": alignment,
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
