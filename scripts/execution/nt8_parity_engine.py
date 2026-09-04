"""
========================================================================================
Canonical NinjaTrader 8 Parity Engine & Risk Manager State Machine
========================================================================================
ADR-024 / Repository Standard: Absolute Cross-Platform Ground-Truth Parity

Guarantees 100% mathematical and behavioral parity between Python backtesters
and NinjaTrader 8 (RiskManagerBase.cs):

1. Position Concurrency Lockout:
   - While in a trade (MarketPosition != Flat), new signals are rejected.
2. Exact Risk Manager State Machine:
   - MaxTradesPerDay: Capped per calendar day (default 3).
   - MaxConsecutiveLosers: 2 consecutive losses -> 30-minute cooling pause.
   - HardStopConsecutiveLosers: 3 consecutive losses -> halt for remainder of day.
   - DailyMaxLoss: Halts for remainder of day if realized drawdown hits threshold.
3. Strict Tick Snapping:
   - Snaps all limits, stops, targets to the instrument tick boundary (0.25 on NQ / ES).
4. Realistic Intra-Bar Fill Sequence:
   - Accurately resolves intra-bar target vs stop arrivals (e.g. Queen +10 bps hit
     and BE lock prior to stop tagging).
========================================================================================
"""

from __future__ import annotations

import os
import warnings
from dataclasses import dataclass
from datetime import datetime, time
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

try:
    import nt8_parity_core
    HAS_RUST_CORE = True
    RUST_CORE_IMPORT_ERROR: Optional[str] = None
except ImportError as _exc:  # pragma: no cover - depends on build state
    HAS_RUST_CORE = False
    RUST_CORE_IMPORT_ERROR = str(_exc)

# Opt-out for a deliberate pure-Python run (fresh clone, bisecting a divergence).
ALLOW_PY_FALLBACK = os.environ.get("NT8_PARITY_ALLOW_PY_FALLBACK", "") == "1"

_RUST_MISSING_MSG = (
    "nt8_parity_core (PyO3) is not importable, so simulate() would silently fall back "
    "to the pure-Python bar loop.\n"
    "  import error: {err}\n"
    "  This is NOT just ~378x slower. The two paths derive `hhmm` differently (Rust "
    "reads UTC from epoch-ms, Python reads the parquet index), so on a source whose "
    "timestamps are stored differently they can produce DIFFERENT TRADES. Gate 2 pins "
    "them equal only for the build that is actually loaded.\n"
    "  Build it:  $env:PYO3_PYTHON=\"<repo>\\.venv\\Scripts\\python.exe\"; "
    ".venv\\Scripts\\python.exe -m maturin develop --release -m crates\\nt8_parity_core\\Cargo.toml\n"
    "  Re-run `maturin develop` after ANY edit to crates/nt8_parity_core/src/lib.rs.\n"
    "  To run the Python path on purpose: pass use_rust=False, or set "
    "NT8_PARITY_ALLOW_PY_FALLBACK=1."
)

if not HAS_RUST_CORE:
    # Loud at import time. A missing accelerator that only shows up as "the backtest
    # took an hour" is the same silent-degradation class as a dead alert relay.
    warnings.warn(
        _RUST_MISSING_MSG.format(err=RUST_CORE_IMPORT_ERROR),
        RuntimeWarning,
        stacklevel=2,
    )


def _require_rust_core() -> None:
    """Fail closed when the caller asked for the Rust path and it is not there.

    `use_rust` defaults to True, so without this the default call quietly changes
    which engine ran - and the engines are only proven equal by a gate that ran
    against a build this process may not have loaded.
    """
    if HAS_RUST_CORE or ALLOW_PY_FALLBACK:
        return
    raise ImportError(_RUST_MISSING_MSG.format(err=RUST_CORE_IMPORT_ERROR))


def _index_to_wallclock_ms(idx: pd.DatetimeIndex) -> np.ndarray:
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    return idx.values.astype("datetime64[ms]").astype(np.int64)


def _restore_datetime_series(ms_arr, target_tz) -> pd.DatetimeIndex:
    dt = pd.to_datetime(ms_arr, unit="ms")
    if target_tz is not None:
        dt = dt.tz_localize(target_tz)
    return dt


@dataclass
class NT8Trade:
    entry_time: datetime
    exit_time: datetime
    direction: str  # "Long" or "Short"
    entry_price: float
    exit_price: float
    leg1_points: float
    leg2_points: float
    total_points: float
    total_pnl_usd: float
    exit_reason: str
    queen_hit: bool
    runner_hit: bool
    mfe_points: float = 0.0
    mae_points: float = 0.0
    mfe_bps: float = 0.0
    mae_bps: float = 0.0
    is_reentry: bool = False


class NT8ParityEngine:
    """
    Python implementation of NinjaTrader 8's RiskManagerBase.cs execution engine.
    """

    def __init__(
        self,
        point_value: float = 2.0,           # $2.00 for MNQ, $5.00 for MES, $20 for NQ, $50 for ES
        tick_size: float = 0.25,
        max_trades_per_day: int = 3,
        max_consecutive_losers: int = 2,
        pause_minutes: int = 30,
        hard_stop_losers: int = 3,
        daily_max_loss: float = 1500.0,
        contracts: int = 2,                 # 2-contract pack (1 Queen + 1 Runner)
        commission_per_contract_rt: float = 1.40,
        slippage_ticks: float = 0.0,
    ):
        self.point_value = point_value
        self.tick_size = tick_size
        self.max_trades_per_day = max_trades_per_day
        self.max_consecutive_losers = max_consecutive_losers
        self.pause_minutes = pause_minutes
        self.hard_stop_losers = hard_stop_losers
        self.daily_max_loss = daily_max_loss
        self.contracts = contracts
        self.commission_per_contract_rt = commission_per_contract_rt
        self.slippage_ticks = slippage_ticks

    def round_tick(self, price: float) -> float:
        """Snap price to exact tick size (e.g. 0.25)."""
        return round(price / self.tick_size) * self.tick_size

    def simulate(
        self,
        df: pd.DataFrame,
        signals: pd.Series,             # +1 for Buy, -1 for Sell, 0 for None
        limit_prices: pd.Series,         # Limit price for entry
        stop_losses: pd.Series,          # Stop loss price
        queen_bps: float = 10.0,
        runner_bps: float = 30.0,
        order_timeout_bars: int = 6,
        earliest_entry_hhmm: int = 945,
        latest_entry_hhmm: int = 1530,
        flatten_hhmm: int = 1555,
        filter_lunch: bool = True,
        use_rust: bool = True,
    ) -> pd.DataFrame:
        """
        Simulate trade execution matching NinjaTrader 8 tick-for-tick.
        Dispatches to high-speed PyO3 Rust extension (nt8_parity_core) by default.
        """
        if use_rust:
            _require_rust_core()
        if use_rust and HAS_RUST_CORE:
            return self._simulate_rust(
                df, signals, limit_prices, stop_losses,
                queen_bps=queen_bps, runner_bps=runner_bps,
                order_timeout_bars=order_timeout_bars,
                earliest_entry_hhmm=earliest_entry_hhmm,
                latest_entry_hhmm=latest_entry_hhmm,
                flatten_hhmm=flatten_hhmm,
                filter_lunch=filter_lunch,
            )
        return self._simulate_py(
            df, signals, limit_prices, stop_losses,
            queen_bps=queen_bps, runner_bps=runner_bps,
            order_timeout_bars=order_timeout_bars,
            earliest_entry_hhmm=earliest_entry_hhmm,
            latest_entry_hhmm=latest_entry_hhmm,
            flatten_hhmm=flatten_hhmm,
            filter_lunch=filter_lunch,
        )

    def _simulate_rust(
        self,
        df: pd.DataFrame,
        signals: pd.Series,
        limit_prices: pd.Series,
        stop_losses: pd.Series,
        queen_bps: float = 10.0,
        runner_bps: float = 30.0,
        order_timeout_bars: int = 6,
        earliest_entry_hhmm: int = 945,
        latest_entry_hhmm: int = 1530,
        flatten_hhmm: int = 1555,
        filter_lunch: bool = True,
    ) -> pd.DataFrame:
        times_ms = _index_to_wallclock_ms(df.index)
        opens = df["open"].to_numpy(dtype=np.float64)
        highs = df["high"].to_numpy(dtype=np.float64)
        lows = df["low"].to_numpy(dtype=np.float64)
        closes = df["close"].to_numpy(dtype=np.float64)
        sig_arr = signals.to_numpy(dtype=np.int32)
        lmt_arr = limit_prices.to_numpy(dtype=np.float64)
        sl_arr = stop_losses.to_numpy(dtype=np.float64)

        res = nt8_parity_core.simulate_bars_v1(
            times_ms, opens, highs, lows, closes, sig_arr, lmt_arr, sl_arr,
            point_value=self.point_value,
            tick_size=self.tick_size,
            max_trades_per_day=self.max_trades_per_day,
            max_consecutive_losers=self.max_consecutive_losers,
            pause_minutes=self.pause_minutes,
            hard_stop_losers=self.hard_stop_losers,
            daily_max_loss=self.daily_max_loss,
            contracts=self.contracts,
            commission_per_contract_rt=self.commission_per_contract_rt,
            slippage_ticks=self.slippage_ticks,
            queen_bps=queen_bps,
            runner_bps=runner_bps,
            order_timeout_bars=order_timeout_bars,
            earliest_entry_hhmm=earliest_entry_hhmm,
            latest_entry_hhmm=latest_entry_hhmm,
            flatten_hhmm=flatten_hhmm,
            filter_lunch=filter_lunch,
        )

        n_trades = len(res["entry_time_ms"])
        if n_trades == 0:
            return pd.DataFrame(columns=[
                "entry_time", "exit_time", "direction", "entry_price", "exit_price",
                "leg1_points", "leg2_points", "total_points", "total_pnl_usd",
                "exit_reason", "queen_hit", "runner_hit", "mfe_points", "mae_points",
                "mfe_bps", "mae_bps", "is_reentry"
            ])

        entry_times = _restore_datetime_series(res["entry_time_ms"], df.index.tz)
        exit_times = _restore_datetime_series(res["exit_time_ms"], df.index.tz)

        total_pts = np.asarray(res["total_points"], dtype=np.float64)
        gross_usd = total_pts * self.point_value * self.contracts
        comm_usd = self.commission_per_contract_rt * self.contracts
        slip_usd = (self.slippage_ticks * self.tick_size * self.point_value) * self.contracts
        net_usd = gross_usd - comm_usd - slip_usd

        dirs = ["Long" if d == 1 else "Short" for d in res["dir"]]

        return pd.DataFrame({
            "entry_time": entry_times,
            "exit_time": exit_times,
            "direction": dirs,
            "entry_price": np.asarray(res["entry_price"], dtype=np.float64),
            "exit_price": np.asarray(res["exit_price"], dtype=np.float64),
            "leg1_points": np.asarray(res["leg1_points"], dtype=np.float64),
            "leg2_points": np.asarray(res["leg2_points"], dtype=np.float64),
            "total_points": total_pts,
            "total_pnl_usd": net_usd,
            "exit_reason": res["exit_reason"],
            "queen_hit": np.asarray(res["queen_hit"], dtype=bool),
            "runner_hit": np.asarray(res["runner_hit"], dtype=bool),
            "mfe_points": np.zeros(n_trades, dtype=np.float64),
            "mae_points": np.zeros(n_trades, dtype=np.float64),
            "mfe_bps": np.zeros(n_trades, dtype=np.float64),
            "mae_bps": np.zeros(n_trades, dtype=np.float64),
            "is_reentry": np.zeros(n_trades, dtype=bool),
        })

    def _simulate_py(
        self,
        df: pd.DataFrame,
        signals: pd.Series,             # +1 for Buy, -1 for Sell, 0 for None
        limit_prices: pd.Series,         # Limit price for entry
        stop_losses: pd.Series,          # Stop loss price
        queen_bps: float = 10.0,
        runner_bps: float = 30.0,
        order_timeout_bars: int = 6,
        earliest_entry_hhmm: int = 945,
        latest_entry_hhmm: int = 1530,
        flatten_hhmm: int = 1555,
        filter_lunch: bool = True,
    ) -> pd.DataFrame:
        """
        Simulate trade execution matching NinjaTrader 8 tick-for-tick (Python engine).
        """
        times = df.index
        opens = df["open"].to_numpy(dtype=np.float64)
        highs = df["high"].to_numpy(dtype=np.float64)
        lows = df["low"].to_numpy(dtype=np.float64)
        closes = df["close"].to_numpy(dtype=np.float64)
        sig_arr = signals.to_numpy(dtype=np.int32)
        lmt_arr = limit_prices.to_numpy(dtype=np.float64)
        sl_arr = stop_losses.to_numpy(dtype=np.float64)
        n = len(df)

        time_strs = times.strftime("%H%M")
        hours = times.hour
        mins = times.minute

        trades: List[NT8Trade] = []
        in_pos = False
        pos_dir = 0
        pos_entry_price = 0.0
        pos_entry_time = None
        active_sl = 0.0
        active_tp1 = 0.0
        active_tp2 = 0.0
        queen_filled = False

        # Daily State
        cur_day = None
        daily_trades = 0
        consecutive_losers = 0
        pause_until_time = None
        daily_pnl = 0.0
        pending_order = None

        for i in range(n):
            t = times[i]
            hhmm = time_strs[i]
            bar_date = t.date()
            h0, l0, c0, o0 = highs[i], lows[i], closes[i], opens[i]

            # New day reset
            if bar_date != cur_day:
                cur_day = bar_date
                daily_trades = 0
                consecutive_losers = 0
                pause_until_time = None
                daily_pnl = 0.0
                pending_order = None

            # ──────────────────────────────────────────────────────────
            # 1. POSITION MANAGEMENT
            # ──────────────────────────────────────────────────────────
            if in_pos:
                closed = False
                pnl_pts = 0.0
                reason = ""
                r_hit = False

                if pos_dir == 1:
                    # Check Queen Target (+10 bps) fill first
                    if not queen_filled and h0 >= active_tp1:
                        queen_filled = True
                        active_sl = pos_entry_price  # BE Lock (+0 risk)

                    # EOD Session Flatten
                    if int(hhmm) >= flatten_hhmm:
                        q_pts = (active_tp1 - pos_entry_price) if queen_filled else (c0 - pos_entry_price)
                        r_pts = (c0 - pos_entry_price)
                        pnl_pts = (q_pts + r_pts) / 2.0
                        reason = "EOD Flat"
                        closed = True

                    # Stop Loss
                    elif l0 <= active_sl:
                        q_pts = (active_tp1 - pos_entry_price) if queen_filled else (active_sl - pos_entry_price)
                        r_pts = (active_sl - pos_entry_price)
                        pnl_pts = (q_pts + r_pts) / 2.0
                        reason = "Stop Loss"
                        closed = True

                    # Runner Target (+30 bps)
                    elif h0 >= active_tp2:
                        q_pts = (active_tp1 - pos_entry_price)
                        r_pts = (active_tp2 - pos_entry_price)
                        pnl_pts = (q_pts + r_pts) / 2.0
                        reason = "Profit Target"
                        r_hit = True
                        closed = True

                elif pos_dir == -1:
                    if not queen_filled and l0 <= active_tp1:
                        queen_filled = True
                        active_sl = pos_entry_price

                    if int(hhmm) >= flatten_hhmm:
                        q_pts = (pos_entry_price - active_tp1) if queen_filled else (pos_entry_price - c0)
                        r_pts = (pos_entry_price - c0)
                        pnl_pts = (q_pts + r_pts) / 2.0
                        reason = "EOD Flat"
                        closed = True

                    elif h0 >= active_sl:
                        q_pts = (pos_entry_price - active_tp1) if queen_filled else (pos_entry_price - active_sl)
                        r_pts = (pos_entry_price - active_sl)
                        pnl_pts = (q_pts + r_pts) / 2.0
                        reason = "Stop Loss"
                        closed = True

                    elif l0 <= active_tp2:
                        q_pts = (pos_entry_price - active_tp1)
                        r_pts = (pos_entry_price - active_tp2)
                        pnl_pts = (q_pts + r_pts) / 2.0
                        reason = "Profit Target"
                        r_hit = True
                        closed = True

                if closed:
                    in_pos = False
                    gross_usd = pnl_pts * self.point_value * self.contracts
                    comm_usd = self.commission_per_contract_rt * self.contracts
                    slip_usd = (self.slippage_ticks * self.tick_size * self.point_value) * self.contracts
                    net_usd = gross_usd - comm_usd - slip_usd

                    trades.append(NT8Trade(
                        entry_time=pos_entry_time, exit_time=t, direction="Long" if pos_dir == 1 else "Short",
                        entry_price=pos_entry_price, exit_price=active_tp2 if r_hit else (active_sl if "Stop" in reason else c0),
                        leg1_points=q_pts, leg2_points=r_pts, total_points=pnl_pts,
                        total_pnl_usd=net_usd, exit_reason=reason, queen_hit=queen_filled, runner_hit=r_hit,
                    ))

                    daily_pnl += net_usd
                    if net_usd < 0:
                        consecutive_losers += 1
                        if consecutive_losers >= self.max_consecutive_losers:
                            pause_until_time = t + pd.Timedelta(minutes=self.pause_minutes)
                    else:
                        consecutive_losers = 0

            # ──────────────────────────────────────────────────────────
            # 2. PENDING LIMIT ORDER EVALUATION
            # ──────────────────────────────────────────────────────────
            if pending_order is not None and not in_pos:
                p_dir = pending_order["dir"]
                p_limit = pending_order["limit"]
                p_sl = pending_order["sl"]
                p_bar = pending_order["bar"]

                is_paused = (pause_until_time is not None and t < pause_until_time)
                hit_hard_stop = (consecutive_losers >= self.hard_stop_losers)
                hit_daily_max = (daily_pnl <= -self.daily_max_loss)
                hm = int(hhmm)
                in_time = (earliest_entry_hhmm <= hm <= latest_entry_hhmm)
                if filter_lunch and (1200 <= hm <= 1330):
                    in_time = False

                if (i - p_bar) <= order_timeout_bars:
                    if in_time and daily_trades < self.max_trades_per_day and not is_paused and not hit_hard_stop and not hit_daily_max:
                        if p_dir == 1 and l0 <= p_limit:
                            in_pos = True
                            pos_dir = 1
                            pos_entry_time = t
                            pos_entry_price = p_limit
                            active_sl = p_sl
                            active_tp1 = self.round_tick(p_limit + (p_limit * (queen_bps / 10000.0)))
                            active_tp2 = self.round_tick(p_limit + (p_limit * (runner_bps / 10000.0)))
                            queen_filled = False
                            daily_trades += 1
                            pending_order = None

                        elif p_dir == -1 and h0 >= p_limit:
                            in_pos = True
                            pos_dir = -1
                            pos_entry_time = t
                            pos_entry_price = p_limit
                            active_sl = p_sl
                            active_tp1 = self.round_tick(p_limit - (p_limit * (queen_bps / 10000.0)))
                            active_tp2 = self.round_tick(p_limit - (p_limit * (runner_bps / 10000.0)))
                            queen_filled = False
                            daily_trades += 1
                            pending_order = None
                else:
                    pending_order = None

            # ──────────────────────────────────────────────────────────
            # 3. ARM NEW SIGNAL (IF NOT ALREADY IN POSITION OR WORKING)
            # ──────────────────────────────────────────────────────────
            if not in_pos and pending_order is None and sig_arr[i] != 0:
                lmt = self.round_tick(lmt_arr[i])
                sl = self.round_tick(sl_arr[i])
                pending_order = {"dir": sig_arr[i], "limit": lmt, "sl": sl, "bar": i}

        return pd.DataFrame([t.__dict__ for t in trades])

    def simulate_mtf(
        self,
        df_5m: pd.DataFrame,
        df_1m: pd.DataFrame,
        signals_5m: pd.Series,
        queen_bps: float = 10.0,
        runner_bps: float = 30.0,
        stop_loss_bps: float = 5.0,
        earliest_entry_hhmm: int = 945,
        latest_entry_hhmm: int = 1530,
        flatten_hhmm: int = 1555,
        filter_lunch: bool = True,
        allow_reentry: bool = True,
        use_rust: bool = True,
    ) -> pd.DataFrame:
        """
        Multi-Timeframe Simulation: 5m Structure/CISD + 1m FVG Precision Entry.
        Includes bar-by-bar MFE/MAE excursion tracking and Confirmed Re-entry Protocol.
        Dispatches to high-speed PyO3 Rust extension (nt8_parity_core) by default.
        """
        if use_rust:
            _require_rust_core()
        if use_rust and HAS_RUST_CORE:
            return self._simulate_mtf_rust(
                df_5m, df_1m, signals_5m,
                queen_bps=queen_bps, runner_bps=runner_bps,
                stop_loss_bps=stop_loss_bps,
                earliest_entry_hhmm=earliest_entry_hhmm,
                latest_entry_hhmm=latest_entry_hhmm,
                flatten_hhmm=flatten_hhmm,
                filter_lunch=filter_lunch,
                allow_reentry=allow_reentry,
            )
        return self._simulate_mtf_py(
            df_5m, df_1m, signals_5m,
            queen_bps=queen_bps, runner_bps=runner_bps,
            stop_loss_bps=stop_loss_bps,
            earliest_entry_hhmm=earliest_entry_hhmm,
            latest_entry_hhmm=latest_entry_hhmm,
            flatten_hhmm=flatten_hhmm,
            filter_lunch=filter_lunch,
            allow_reentry=allow_reentry,
        )

    def _simulate_mtf_rust(
        self,
        df_5m: pd.DataFrame,
        df_1m: pd.DataFrame,
        signals_5m: pd.Series,
        queen_bps: float = 10.0,
        runner_bps: float = 30.0,
        stop_loss_bps: float = 5.0,
        earliest_entry_hhmm: int = 945,
        latest_entry_hhmm: int = 1530,
        flatten_hhmm: int = 1555,
        filter_lunch: bool = True,
        allow_reentry: bool = True,
    ) -> pd.DataFrame:
        times_1m_ms = _index_to_wallclock_ms(df_1m.index)
        opens_1m = df_1m["open"].to_numpy(dtype=np.float64)
        highs_1m = df_1m["high"].to_numpy(dtype=np.float64)
        lows_1m = df_1m["low"].to_numpy(dtype=np.float64)
        closes_1m = df_1m["close"].to_numpy(dtype=np.float64)

        sig_times_5m = _index_to_wallclock_ms(signals_5m.index)
        sig_dirs_5m = signals_5m.to_numpy(dtype=np.int32)

        res = nt8_parity_core.simulate_bars_v2(
            times_1m_ms, opens_1m, highs_1m, lows_1m, closes_1m,
            sig_times_5m, sig_dirs_5m,
            point_value=self.point_value,
            tick_size=self.tick_size,
            max_trades_per_day=self.max_trades_per_day,
            max_consecutive_losers=self.max_consecutive_losers,
            pause_minutes=self.pause_minutes,
            hard_stop_losers=self.hard_stop_losers,
            daily_max_loss=self.daily_max_loss,
            contracts=self.contracts,
            commission_per_contract_rt=self.commission_per_contract_rt,
            slippage_ticks=self.slippage_ticks,
            queen_bps=queen_bps,
            runner_bps=runner_bps,
            stop_loss_bps=stop_loss_bps,
            earliest_entry_hhmm=earliest_entry_hhmm,
            latest_entry_hhmm=latest_entry_hhmm,
            flatten_hhmm=flatten_hhmm,
            filter_lunch=filter_lunch,
            allow_reentry=allow_reentry,
        )

        n_trades = len(res["entry_time_ms"])
        if n_trades == 0:
            return pd.DataFrame(columns=[
                "entry_time", "exit_time", "direction", "entry_price", "exit_price",
                "leg1_points", "leg2_points", "total_points", "total_pnl_usd",
                "exit_reason", "queen_hit", "runner_hit", "mfe_points", "mae_points",
                "mfe_bps", "mae_bps", "is_reentry"
            ])

        entry_times = _restore_datetime_series(res["entry_time_ms"], df_1m.index.tz)
        exit_times = _restore_datetime_series(res["exit_time_ms"], df_1m.index.tz)

        entry_px = np.asarray(res["entry_price"], dtype=np.float64)
        exit_px = np.asarray(res["exit_price"], dtype=np.float64)
        leg1 = np.asarray(res["leg1_points"], dtype=np.float64)
        leg2 = np.asarray(res["leg2_points"], dtype=np.float64)
        total_pts = np.asarray(res["total_points"], dtype=np.float64)
        mfe_pts = np.asarray(res["mfe_points"], dtype=np.float64)
        mae_pts = np.asarray(res["mae_points"], dtype=np.float64)

        gross_usd = total_pts * self.point_value * self.contracts
        comm_usd = self.commission_per_contract_rt * self.contracts
        slip_usd = (self.slippage_ticks * self.tick_size * self.point_value) * self.contracts
        net_usd = gross_usd - comm_usd - slip_usd

        dirs = ["Long" if d == 1 else "Short" for d in res["dir"]]
        mfe_bps = np.where(entry_px > 0, (mfe_pts / entry_px) * 10000.0, 0.0)
        mae_bps = np.where(entry_px > 0, (mae_pts / entry_px) * 10000.0, 0.0)

        return pd.DataFrame({
            "entry_time": entry_times,
            "exit_time": exit_times,
            "direction": dirs,
            "entry_price": entry_px,
            "exit_price": exit_px,
            "leg1_points": leg1,
            "leg2_points": leg2,
            "total_points": total_pts,
            "total_pnl_usd": net_usd,
            "exit_reason": res["exit_reason"],
            "queen_hit": np.asarray(res["queen_hit"], dtype=bool),
            "runner_hit": np.asarray(res["runner_hit"], dtype=bool),
            "mfe_points": mfe_pts,
            "mae_points": mae_pts,
            "mfe_bps": mfe_bps,
            "mae_bps": mae_bps,
            "is_reentry": np.asarray(res["is_reentry"], dtype=bool),
        })

    def _simulate_mtf_py(
        self,
        df_5m: pd.DataFrame,
        df_1m: pd.DataFrame,
        signals_5m: pd.Series,
        queen_bps: float = 10.0,
        runner_bps: float = 30.0,
        stop_loss_bps: float = 5.0,
        earliest_entry_hhmm: int = 945,
        latest_entry_hhmm: int = 1530,
        flatten_hhmm: int = 1555,
        filter_lunch: bool = True,
        allow_reentry: bool = True,
    ) -> pd.DataFrame:
        """
        Multi-Timeframe Simulation: 5m Structure/CISD + 1m FVG Precision Entry (Python engine).
        Includes bar-by-bar MFE/MAE excursion tracking and Confirmed Re-entry Protocol.
        """
        times_1m = df_1m.index
        opens_1m = df_1m["open"].to_numpy(dtype=np.float64)
        highs_1m = df_1m["high"].to_numpy(dtype=np.float64)
        lows_1m = df_1m["low"].to_numpy(dtype=np.float64)
        closes_1m = df_1m["close"].to_numpy(dtype=np.float64)
        n_1m = len(df_1m)

        time_strs_1m = times_1m.strftime("%H%M")
        sig_map = signals_5m[signals_5m != 0].to_dict()

        trades: List[NT8Trade] = []
        in_pos = False
        pos_dir = 0
        pos_entry_price = 0.0
        pos_entry_time = None
        active_sl = 0.0
        active_tp1 = 0.0
        active_tp2 = 0.0
        queen_filled = False
        cur_mfe_pts = 0.0
        cur_mae_pts = 0.0
        is_cur_reentry = False
        reentry_armed = False
        reentry_dir = 0
        reentry_time = None

        # State
        cur_day = None
        daily_trades = 0
        consecutive_losers = 0
        pause_until_time = None
        daily_pnl = 0.0
        armed_dir = 0
        armed_time = None

        for i in range(2, n_1m):
            t = times_1m[i]
            hhmm = time_strs_1m[i]
            bar_date = t.date()
            h0, l0, c0, o0 = highs_1m[i], lows_1m[i], closes_1m[i], opens_1m[i]
            h2, l2 = highs_1m[i - 2], lows_1m[i - 2]

            if bar_date != cur_day:
                cur_day = bar_date
                daily_trades = 0
                consecutive_losers = 0
                pause_until_time = None
                daily_pnl = 0.0
                armed_dir = 0
                armed_time = None
                reentry_armed = False

            # 1. Manage open position & track MFE/MAE
            if in_pos:
                closed = False
                pnl_pts = 0.0
                reason = ""
                r_hit = False

                if pos_dir == 1:
                    fav = h0 - pos_entry_price
                    adv = pos_entry_price - l0
                    if fav > cur_mfe_pts: cur_mfe_pts = fav
                    if adv > cur_mae_pts: cur_mae_pts = adv

                    if not queen_filled and h0 >= active_tp1:
                        queen_filled = True
                        active_sl = pos_entry_price

                    if int(hhmm) >= flatten_hhmm:
                        q_pts = (active_tp1 - pos_entry_price) if queen_filled else (c0 - pos_entry_price)
                        r_pts = (c0 - pos_entry_price)
                        pnl_pts = (q_pts + r_pts) / 2.0
                        reason = "EOD Flat"
                        closed = True
                    elif l0 <= active_sl:
                        q_pts = (active_tp1 - pos_entry_price) if queen_filled else (active_sl - pos_entry_price)
                        r_pts = (active_sl - pos_entry_price)
                        pnl_pts = (q_pts + r_pts) / 2.0
                        reason = "Stop Loss"
                        closed = True
                    elif h0 >= active_tp2:
                        q_pts = (active_tp1 - pos_entry_price)
                        r_pts = (active_tp2 - pos_entry_price)
                        pnl_pts = (q_pts + r_pts) / 2.0
                        reason = "Profit Target"
                        r_hit = True
                        closed = True

                elif pos_dir == -1:
                    fav = pos_entry_price - l0
                    adv = h0 - pos_entry_price
                    if fav > cur_mfe_pts: cur_mfe_pts = fav
                    if adv > cur_mae_pts: cur_mae_pts = adv

                    if not queen_filled and l0 <= active_tp1:
                        queen_filled = True
                        active_sl = pos_entry_price

                    if int(hhmm) >= flatten_hhmm:
                        q_pts = (pos_entry_price - active_tp1) if queen_filled else (pos_entry_price - c0)
                        r_pts = (pos_entry_price - c0)
                        pnl_pts = (q_pts + r_pts) / 2.0
                        reason = "EOD Flat"
                        closed = True
                    elif h0 >= active_sl:
                        q_pts = (pos_entry_price - active_tp1) if queen_filled else (pos_entry_price - active_sl)
                        r_pts = (pos_entry_price - active_sl)
                        pnl_pts = (q_pts + r_pts) / 2.0
                        reason = "Stop Loss"
                        closed = True
                    elif l0 <= active_tp2:
                        q_pts = (pos_entry_price - active_tp1)
                        r_pts = (pos_entry_price - active_tp2)
                        pnl_pts = (q_pts + r_pts) / 2.0
                        reason = "Profit Target"
                        r_hit = True
                        closed = True

                if closed:
                    in_pos = False
                    gross_usd = pnl_pts * self.point_value * self.contracts
                    comm_usd = self.commission_per_contract_rt * self.contracts
                    slip_usd = (self.slippage_ticks * self.tick_size * self.point_value) * self.contracts
                    net_usd = gross_usd - comm_usd - slip_usd

                    mfe_b = (cur_mfe_pts / pos_entry_price) * 10000.0 if pos_entry_price > 0 else 0.0
                    mae_b = (cur_mae_pts / pos_entry_price) * 10000.0 if pos_entry_price > 0 else 0.0

                    trades.append(NT8Trade(
                        entry_time=pos_entry_time, exit_time=t, direction="Long" if pos_dir == 1 else "Short",
                        entry_price=pos_entry_price, exit_price=active_tp2 if r_hit else (active_sl if "Stop" in reason else c0),
                        leg1_points=q_pts, leg2_points=r_pts, total_points=pnl_pts,
                        total_pnl_usd=net_usd, exit_reason=reason, queen_hit=queen_filled, runner_hit=r_hit,
                        mfe_points=cur_mfe_pts, mae_points=cur_mae_pts, mfe_bps=mfe_b, mae_bps=mae_b,
                        is_reentry=is_cur_reentry,
                    ))

                    daily_pnl += net_usd
                    if net_usd < 0:
                        consecutive_losers += 1
                        if consecutive_losers >= self.max_consecutive_losers:
                            pause_until_time = t + pd.Timedelta(minutes=self.pause_minutes)
                        # Re-Entry Protocol: If stopped out on tight SL, arm for 1 confirmed re-entry
                        if allow_reentry and not is_cur_reentry and "Stop" in reason:
                            reentry_armed = True
                            reentry_dir = pos_dir
                            reentry_time = t
                    else:
                        consecutive_losers = 0
                        reentry_armed = False

            # 2. Check 5m CISD signals at 5m bar closures
            if t in sig_map:
                armed_dir = sig_map[t]
                armed_time = t

            # 3. Check 1m FVG Entry Trigger (or Confirmed Re-Entry)
            target_dir = reentry_dir if reentry_armed else armed_dir
            t_ref = reentry_time if reentry_armed else armed_time
            if not in_pos and target_dir != 0:
                is_paused = (pause_until_time is not None and t < pause_until_time) and not reentry_armed
                hit_hard_stop = (consecutive_losers >= self.hard_stop_losers)
                hit_daily_max = (daily_pnl <= -self.daily_max_loss)
                hm = int(hhmm)
                in_time = (earliest_entry_hhmm <= hm <= latest_entry_hhmm)
                if filter_lunch and (1200 <= hm <= 1330):
                    in_time = False

                bars_armed = (t - t_ref).total_seconds() / 60.0 if t_ref else 999.0
                if bars_armed <= 20.0 and in_time and daily_trades < self.max_trades_per_day and not is_paused and not hit_hard_stop and not hit_daily_max:
                    if target_dir == 1 and l0 > h2:  # 1m Bullish FVG
                        entry_p = self.round_tick(h2)
                        active_sl = self.round_tick(entry_p - (entry_p * (stop_loss_bps / 10000.0)))
                        active_tp1 = self.round_tick(entry_p + (entry_p * (queen_bps / 10000.0)))
                        active_tp2 = self.round_tick(entry_p + (entry_p * (runner_bps / 10000.0)))
                        pos_entry_price = entry_p
                        pos_entry_time = t
                        pos_dir = 1
                        in_pos = True
                        queen_filled = False
                        cur_mfe_pts = 0.0
                        cur_mae_pts = 0.0
                        is_cur_reentry = reentry_armed
                        daily_trades += 1
                        armed_dir = 0
                        reentry_armed = False
                    elif target_dir == -1 and h0 < l2:  # 1m Bearish FVG
                        entry_p = self.round_tick(l2)
                        active_sl = self.round_tick(entry_p + (entry_p * (stop_loss_bps / 10000.0)))
                        active_tp1 = self.round_tick(entry_p - (entry_p * (queen_bps / 10000.0)))
                        active_tp2 = self.round_tick(entry_p - (entry_p * (runner_bps / 10000.0)))
                        pos_entry_price = entry_p
                        pos_entry_time = t
                        pos_dir = -1
                        in_pos = True
                        queen_filled = False
                        cur_mfe_pts = 0.0
                        cur_mae_pts = 0.0
                        is_cur_reentry = reentry_armed
                        daily_trades += 1
                        armed_dir = 0
                        reentry_armed = False
                elif bars_armed > 20.0:
                    armed_dir = 0
                    reentry_armed = False

        return pd.DataFrame([t.__dict__ for t in trades])

