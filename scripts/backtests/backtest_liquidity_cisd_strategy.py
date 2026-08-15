"""
========================================================================================
Institutional Backtest Engine: Liquidity -> CISD -> Retest Entry (Cover The Queen)
========================================================================================
Performs rigorous, event-driven backtesting of the 5-step institutional trading framework
across multi-year NQ 5-minute historical data.

Key Features:
1. Strict No-Cheating Bar-by-Bar Execution:
   - Orders armed on bar t are ONLY evaluated for fill on bar t+1 onwards.
   - Zero same-bar lookahead / 0-bar noise elimination.
2. Authentic Cover The Queen & Runner Trade Management:
   - Position Sizing: 2 contracts (1 Queen + 1 Runner).
   - Queen Exit: Scaled out at exact Basis Points (e.g. 10 bps).
   - Breakeven Lock: Stop on Runner automatically locks to BE upon Queen fill.
   - Runner Target: Exits at Median MFE / Fat-Tail MFE (e.g. 30 bps, 70 bps).
3. Parameter Grid / Experimentation:
   - Entry Models: FVG Boundary vs 50% CE vs CISD Line Retest.
   - Stop Loss Models: SL-1 (Sweep Wick) vs SL-4 (CISD Origin) vs FVG Forming Wick.
   - HTF Alignment Filter: 1H/4H Trend Lock vs Raw.

Author: Institutional Research Suite / Antigravity
========================================================================================
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# Setup root path
_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))


@dataclass
class TradeRecord:
    trade_id: int
    direction: int  # +1 = Long, -1 = Short
    entry_time: pd.Timestamp
    entry_bar: int
    entry_price: float
    entry_model: str
    stop_loss: float
    sl_model: str
    queen_tp: float
    runner_tp: float
    queen_exit_time: Optional[pd.Timestamp] = None
    queen_exit_price: Optional[float] = None
    queen_exit_reason: str = ""
    queen_pnl_pts: float = 0.0
    runner_exit_time: Optional[pd.Timestamp] = None
    runner_exit_price: Optional[float] = None
    runner_exit_reason: str = ""
    runner_pnl_pts: float = 0.0
    total_pnl_usd: float = 0.0
    bars_held: int = 0
    mfe_pts: float = 0.0
    mae_pts: float = 0.0


def run_liquidity_cisd_backtest(
    df: pd.DataFrame,
    entry_model: str = "FVG_Touch",  # "FVG_Touch", "FVG_CE_50", "CISD_Level"
    sl_model: str = "SL1_SweepWick",  # "SL1_SweepWick", "SL4_CISD_Origin", "FVG_FormingWick"
    use_htf_filter: bool = True,
    queen_bps: float = 10.0,
    runner_mfe_bps: float = 30.0,
    point_value: float = 2.0,  # $2/pt for MNQ, $20/pt for NQ
    comm_per_contract: float = 0.52,  # $0.52/side = $1.04 RT per contract for MNQ
    max_wait_bars: int = 20,
    max_daily_trades: int = 5,
) -> Tuple[pd.DataFrame, Dict]:
    """
    Runs the event-driven backtest on 5m OHLCV DataFrame.
    """
    df = df.copy()
    if not isinstance(df.index, pd.DatetimeIndex):
        if "datetime" in df.columns:
            df["datetime"] = pd.to_datetime(df["datetime"])
            df.set_index("datetime", inplace=True)

    # Ensure Eastern Time
    times = df.index
    opens = df["open"].values
    highs = df["high"].values
    lows = df["low"].values
    closes = df["close"].values
    n = len(df)

    # Precalculate Daily PDH/PDL and Session Info
    df["date"] = times.date
    df["hour"] = times.hour
    df["minute"] = times.minute
    df["day_time"] = df["hour"] * 60 + df["minute"]

    # RTH Window: 09:45 - 15:30 ET
    rth_mask = (df["day_time"] >= 585) & (df["day_time"] <= 930)
    eod_mask = df["day_time"] >= 955  # 15:55 ET

    # Daily aggregation
    daily_df = df.groupby("date").agg({"high": "max", "low": "min", "close": "last"}).shift(1)
    pdh_map = daily_df["high"].to_dict()
    pdl_map = daily_df["low"].to_dict()

    # 1H and 4H Resampling for sweeps & HTF bias
    df_1h = df.resample("1h").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    df_1h["h1_h0"] = df_1h["high"].shift(1)
    df_1h["h1_l0"] = df_1h["low"].shift(1)
    h1_h0_series = df_1h["h1_h0"].reindex(df.index, method="ffill").values
    h1_l0_series = df_1h["h1_l0"].reindex(df.index, method="ffill").values

    # 4H Resampling
    df_4h = df.resample("4h").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    df_4h["h4_h0"] = df_4h["high"].shift(1)
    df_4h["h4_l0"] = df_4h["low"].shift(1)
    h4_h0_series = df_4h["h4_h0"].reindex(df.index, method="ffill").values
    h4_l0_series = df_4h["h4_l0"].reindex(df.index, method="ffill").values

    # Precalculate 3-bar Swing Pivots
    sw_h = np.full(n, np.nan)
    sw_l = np.full(n, np.nan)
    for i in range(3, n - 3):
        if highs[i] > highs[i - 1] and highs[i] > highs[i - 2] and highs[i] > highs[i - 3] and \
           highs[i] > highs[i + 1] and highs[i] > highs[i + 2] and highs[i] > highs[i + 3]:
            sw_h[i + 3] = highs[i]
        if lows[i] < lows[i - 1] and lows[i] < lows[i - 2] and lows[i] < lows[i - 3] and \
           lows[i] < lows[i + 1] and lows[i] < lows[i + 2] and lows[i] < lows[i + 3]:
            sw_l[i + 3] = lows[i]

    # Simulation State
    trades: List[TradeRecord] = []
    trade_count = 0

    current_date = None
    daily_trade_count = 0

    # Liquidity Sweep State
    has_bull_sweep = False
    has_bear_sweep = False
    bull_sweep_low = np.nan
    bear_sweep_high = np.nan
    bull_sweep_bar = -9999
    bear_sweep_bar = -9999

    # CISD Arming State
    armed_bull_cisd = False
    armed_bear_cisd = False
    armed_bull_high = np.nan
    armed_bear_low = np.nan
    armed_cisd_origin_sl = np.nan
    current_delivery_regime = 0  # +1 = Bull, -1 = Bear

    # Pending Entry Zone (Armed on bar t, evaluated for fill on bar t+1)
    pending_zone: Optional[Dict] = None

    # Active Position State (1 Queen + 1 Runner)
    in_position = False
    pos_dir = 0
    active_entry_price = 0.0
    active_stop_loss = 0.0
    active_queen_tp = 0.0
    active_runner_tp = 0.0
    queen_filled = False
    runner_filled = False
    pos_entry_bar = 0
    pos_entry_time = None
    pos_mfe = 0.0
    pos_mae = 0.0
    active_sl_model = ""
    active_entry_model = ""

    # Rolling Swing Lists
    bsl_list: List[float] = []
    ssl_list: List[float] = []

    for i in range(25, n):
        t = times[i]
        bar_date = t.date()

        # Day boundary reset
        if bar_date != current_date:
            current_date = bar_date
            daily_trade_count = 0

        # Extract Daily Levels
        pdh = pdh_map.get(bar_date, np.nan)
        pdl = pdl_map.get(bar_date, np.nan)

        h0, l0, c0, o0 = highs[i], lows[i], closes[i], opens[i]
        h1, l1, c1, o1 = highs[i - 1], lows[i - 1], closes[i - 1], opens[i - 1]
        h2, l2, c2, o2 = highs[i - 2], lows[i - 2], closes[i - 2], opens[i - 2]

        # Update rolling swing lists
        if not np.isnan(sw_h[i]):
            bsl_list.append(sw_h[i])
            if len(bsl_list) > 10:
                bsl_list.pop(0)
        if not np.isnan(sw_l[i]):
            ssl_list.append(sw_l[i])
            if len(ssl_list) > 10:
                ssl_list.pop(0)

        # -------------------------------------------------------------
        # 1. POSITION MANAGEMENT (If in trade)
        # -------------------------------------------------------------
        if in_position:
            # Update MFE / MAE
            if pos_dir == 1:
                cur_favorable = h0 - active_entry_price
                cur_adverse = active_entry_price - l0
            else:
                cur_favorable = active_entry_price - l0
                cur_adverse = h0 - active_entry_price

            pos_mfe = max(pos_mfe, cur_favorable)
            pos_mae = max(pos_mae, cur_adverse)

            # Check EOD Flatten (15:55 ET)
            if eod_mask.iloc[i]:
                # Flatten remaining
                exit_price = c0
                if not queen_filled:
                    q_pnl = (exit_price - active_entry_price) * pos_dir
                    r_pnl = (exit_price - active_entry_price) * pos_dir
                    q_reason = "EOD 15:55 Flat"
                    r_reason = "EOD 15:55 Flat"
                else:
                    q_pnl = (active_queen_tp - active_entry_price) * pos_dir
                    r_pnl = (exit_price - active_entry_price) * pos_dir
                    q_reason = "Queen Covered"
                    r_reason = "EOD 15:55 Flat"

                total_usd = (q_pnl + r_pnl) * point_value - (4 * comm_per_contract)
                trade_count += 1
                trades.append(TradeRecord(
                    trade_id=trade_count,
                    direction=pos_dir,
                    entry_time=pos_entry_time,
                    entry_bar=pos_entry_bar,
                    entry_price=active_entry_price,
                    entry_model=active_entry_model,
                    stop_loss=active_stop_loss,
                    sl_model=active_sl_model,
                    queen_tp=active_queen_tp,
                    runner_tp=active_runner_tp,
                    queen_exit_time=t,
                    queen_exit_price=active_queen_tp if queen_filled else exit_price,
                    queen_exit_reason=q_reason,
                    queen_pnl_pts=q_pnl,
                    runner_exit_time=t,
                    runner_exit_price=exit_price,
                    runner_exit_reason=r_reason,
                    runner_pnl_pts=r_pnl,
                    total_pnl_usd=total_usd,
                    bars_held=i - pos_entry_bar,
                    mfe_pts=pos_mfe,
                    mae_pts=pos_mae,
                ))
                in_position = False
                continue

            # Long Position Management
            if pos_dir == 1:
                # Check Stop Loss first (conservative)
                if l0 <= active_stop_loss:
                    q_pnl = (active_stop_loss - active_entry_price) if not queen_filled else (active_queen_tp - active_entry_price)
                    r_pnl = (active_stop_loss - active_entry_price)
                    q_reason = "Stop Loss" if not queen_filled else "Queen Covered"
                    r_reason = "Runner Stop Loss" if not queen_filled else "Runner Breakeven Stop"
                    total_usd = (q_pnl + r_pnl) * point_value - (4 * comm_per_contract)
                    trade_count += 1
                    trades.append(TradeRecord(
                        trade_id=trade_count,
                        direction=1,
                        entry_time=pos_entry_time,
                        entry_bar=pos_entry_bar,
                        entry_price=active_entry_price,
                        entry_model=active_entry_model,
                        stop_loss=active_stop_loss,
                        sl_model=active_sl_model,
                        queen_tp=active_queen_tp,
                        runner_tp=active_runner_tp,
                        queen_exit_time=t,
                        queen_exit_price=active_queen_tp if queen_filled else active_stop_loss,
                        queen_exit_reason=q_reason,
                        queen_pnl_pts=q_pnl,
                        runner_exit_time=t,
                        runner_exit_price=active_stop_loss,
                        runner_exit_reason=r_reason,
                        runner_pnl_pts=r_pnl,
                        total_pnl_usd=total_usd,
                        bars_held=i - pos_entry_bar,
                        mfe_pts=pos_mfe,
                        mae_pts=pos_mae,
                    ))
                    in_position = False
                    continue

                # Check Queen TP1
                if not queen_filled and h0 >= active_queen_tp:
                    queen_filled = True
                    # Lock Runner to Breakeven
                    active_stop_loss = active_entry_price

                # Check Runner TP2
                if h0 >= active_runner_tp:
                    q_pnl = (active_queen_tp - active_entry_price)
                    r_pnl = (active_runner_tp - active_entry_price)
                    total_usd = (q_pnl + r_pnl) * point_value - (4 * comm_per_contract)
                    trade_count += 1
                    trades.append(TradeRecord(
                        trade_id=trade_count,
                        direction=1,
                        entry_time=pos_entry_time,
                        entry_bar=pos_entry_bar,
                        entry_price=active_entry_price,
                        entry_model=active_entry_model,
                        stop_loss=active_stop_loss,
                        sl_model=active_sl_model,
                        queen_tp=active_queen_tp,
                        runner_tp=active_runner_tp,
                        queen_exit_time=t,
                        queen_exit_price=active_queen_tp,
                        queen_exit_reason="Queen Covered (10bps)",
                        queen_pnl_pts=q_pnl,
                        runner_exit_time=t,
                        runner_exit_price=active_runner_tp,
                        runner_exit_reason="Runner TP2 MFE Hit",
                        runner_pnl_pts=r_pnl,
                        total_pnl_usd=total_usd,
                        bars_held=i - pos_entry_bar,
                        mfe_pts=pos_mfe,
                        mae_pts=pos_mae,
                    ))
                    in_position = False
                    continue

            # Short Position Management
            elif pos_dir == -1:
                if h0 >= active_stop_loss:
                    q_pnl = (active_entry_price - active_stop_loss) if not queen_filled else (active_entry_price - active_queen_tp)
                    r_pnl = (active_entry_price - active_stop_loss)
                    q_reason = "Stop Loss" if not queen_filled else "Queen Covered"
                    r_reason = "Runner Stop Loss" if not queen_filled else "Runner Breakeven Stop"
                    total_usd = (q_pnl + r_pnl) * point_value - (4 * comm_per_contract)
                    trade_count += 1
                    trades.append(TradeRecord(
                        trade_id=trade_count,
                        direction=-1,
                        entry_time=pos_entry_time,
                        entry_bar=pos_entry_bar,
                        entry_price=active_entry_price,
                        entry_model=active_entry_model,
                        stop_loss=active_stop_loss,
                        sl_model=active_sl_model,
                        queen_tp=active_queen_tp,
                        runner_tp=active_runner_tp,
                        queen_exit_time=t,
                        queen_exit_price=active_queen_tp if queen_filled else active_stop_loss,
                        queen_exit_reason=q_reason,
                        queen_pnl_pts=q_pnl,
                        runner_exit_time=t,
                        runner_exit_price=active_stop_loss,
                        runner_exit_reason=r_reason,
                        runner_pnl_pts=r_pnl,
                        total_pnl_usd=total_usd,
                        bars_held=i - pos_entry_bar,
                        mfe_pts=pos_mfe,
                        mae_pts=pos_mae,
                    ))
                    in_position = False
                    continue

                if not queen_filled and l0 <= active_queen_tp:
                    queen_filled = True
                    active_stop_loss = active_entry_price

                if l0 <= active_runner_tp:
                    q_pnl = (active_entry_price - active_queen_tp)
                    r_pnl = (active_entry_price - active_runner_tp)
                    total_usd = (q_pnl + r_pnl) * point_value - (4 * comm_per_contract)
                    trade_count += 1
                    trades.append(TradeRecord(
                        trade_id=trade_count,
                        direction=-1,
                        entry_time=pos_entry_time,
                        entry_bar=pos_entry_bar,
                        entry_price=active_entry_price,
                        entry_model=active_entry_model,
                        stop_loss=active_stop_loss,
                        sl_model=active_sl_model,
                        queen_tp=active_queen_tp,
                        runner_tp=active_runner_tp,
                        queen_exit_time=t,
                        queen_exit_price=active_queen_tp,
                        queen_exit_reason="Queen Covered (10bps)",
                        queen_pnl_pts=q_pnl,
                        runner_exit_time=t,
                        runner_exit_price=active_runner_tp,
                        runner_exit_reason="Runner TP2 MFE Hit",
                        runner_pnl_pts=r_pnl,
                        total_pnl_usd=total_usd,
                        bars_held=i - pos_entry_bar,
                        mfe_pts=pos_mfe,
                        mae_pts=pos_mae,
                    ))
                    in_position = False
                    continue

        # -------------------------------------------------------------
        # 2. EVALUATE PENDING ENTRY FILL (On subsequent bar i)
        # -------------------------------------------------------------
        if pending_zone is not None and not in_position:
            p_dir = pending_zone["dir"]
            p_level = pending_zone["entry_level"]
            p_sl = pending_zone["sl"]
            p_armed_bar = pending_zone["armed_bar"]
            p_entry_model = pending_zone["entry_model"]
            p_sl_model = pending_zone["sl_model"]

            if (i - p_armed_bar) <= max_wait_bars:
                can_enter = rth_mask.iloc[i] and (daily_trade_count < max_daily_trades)

                # Check HTF Delivery Filter
                if use_htf_filter and current_delivery_regime != 0:
                    if p_dir != current_delivery_regime:
                        can_enter = False

                if can_enter:
                    # Fill Long
                    if p_dir == 1 and l0 <= p_level:
                        in_position = True
                        pos_dir = 1
                        active_entry_price = p_level
                        active_stop_loss = p_sl
                        active_sl_model = p_sl_model
                        active_entry_model = p_entry_model
                        pos_entry_bar = i
                        pos_entry_time = t
                        pos_mfe = max(0.0, h0 - active_entry_price)
                        pos_mae = max(0.0, active_entry_price - l0)

                        dist_queen = round((active_entry_price * (queen_bps / 10000.0)) * 4) / 4.0
                        dist_runner = round((active_entry_price * (runner_mfe_bps / 10000.0)) * 4) / 4.0

                        active_queen_tp = active_entry_price + dist_queen
                        active_runner_tp = active_entry_price + dist_runner
                        queen_filled = False
                        daily_trade_count += 1
                        pending_zone = None

                    # Fill Short
                    elif p_dir == -1 and h0 >= p_level:
                        in_position = True
                        pos_dir = -1
                        active_entry_price = p_level
                        active_stop_loss = p_sl
                        active_sl_model = p_sl_model
                        active_entry_model = p_entry_model
                        pos_entry_bar = i
                        pos_entry_time = t
                        pos_mfe = max(0.0, active_entry_price - l0)
                        pos_mae = max(0.0, h0 - active_entry_price)

                        dist_queen = round((active_entry_price * (queen_bps / 10000.0)) * 4) / 4.0
                        dist_runner = round((active_entry_price * (runner_mfe_bps / 10000.0)) * 4) / 4.0

                        active_queen_tp = active_entry_price - dist_queen
                        active_runner_tp = active_entry_price - dist_runner
                        queen_filled = False
                        daily_trade_count += 1
                        pending_zone = None
            else:
                # Expired wait
                pending_zone = None

        # -------------------------------------------------------------
        # 3. STEP 1: LIQUIDITY SWEEP DETECTION
        # -------------------------------------------------------------
        bsl_swept = False
        ssl_swept = False
        sweep_extreme = np.nan

        # Daily Sweeps
        if not np.isnan(pdh) and h0 > pdh and (c0 < pdh or o0 < pdh):
            bsl_swept = True
            sweep_extreme = h0
        if not np.isnan(pdl) and l0 < pdl and (c0 > pdl or o0 > pdl):
            ssl_swept = True
            sweep_extreme = l0

        # 4H Sweeps
        h4_h = h4_h0_series[i]
        h4_l = h4_l0_series[i]
        if not np.isnan(h4_h) and h0 > h4_h and (c0 < h4_h or o0 < h4_h):
            bsl_swept = True
            sweep_extreme = h0
        if not np.isnan(h4_l) and l0 < h4_l and (c0 > h4_l or o0 > h4_l):
            ssl_swept = True
            sweep_extreme = l0

        # 1H Sweeps
        h1_h = h1_h0_series[i]
        h1_l = h1_l0_series[i]
        if not np.isnan(h1_h) and h0 > h1_h and (c0 < h1_h or o0 < h1_h):
            bsl_swept = True
            sweep_extreme = h0
        if not np.isnan(h1_l) and l0 < h1_l and (c0 > h1_l or o0 > h1_l):
            ssl_swept = True
            sweep_extreme = l0

        # Intraday Swing Sweeps
        if not bsl_swept:
            for bsl_val in bsl_list:
                if h0 > bsl_val and c0 < bsl_val:
                    bsl_swept = True
                    sweep_extreme = h0
                    break

        if not ssl_swept:
            for ssl_val in ssl_list:
                if l0 < ssl_val and c0 > ssl_val:
                    ssl_swept = True
                    sweep_extreme = l0
                    break

        if ssl_swept:
            has_bull_sweep = True
            bull_sweep_low = sweep_extreme if not np.isnan(sweep_extreme) else l0
            bull_sweep_bar = i

        if bsl_swept:
            has_bear_sweep = True
            bear_sweep_high = sweep_extreme if not np.isnan(sweep_extreme) else h0
            bear_sweep_bar = i

        if (i - bull_sweep_bar) > 25:
            has_bull_sweep = False
        if (i - bear_sweep_bar) > 25:
            has_bear_sweep = False

        # -------------------------------------------------------------
        # 4. STEP 2: CANONICAL BACKWARD-WALKING CISD
        # -------------------------------------------------------------
        if has_bull_sweep and ssl_swept:
            s_high = max(o0, c0)
            s_low = min(o0, c0)
            for k in range(1, min(25, i)):
                if closes[i - k] <= opens[i - k]:
                    s_high = max(s_high, max(opens[i - k], closes[i - k]))
                    s_low = min(s_low, min(opens[i - k], closes[i - k]))
                else:
                    break
            armed_bull_cisd = True
            armed_bull_high = s_high
            armed_cisd_origin_sl = s_low

        if has_bear_sweep and bsl_swept:
            s_high = max(o0, c0)
            s_low = min(o0, c0)
            for k in range(1, min(25, i)):
                if closes[i - k] >= opens[i - k]:
                    s_high = max(s_high, max(opens[i - k], closes[i - k]))
                    s_low = min(s_low, min(opens[i - k], closes[i - k]))
                else:
                    break
            armed_bear_cisd = True
            armed_bear_low = s_low
            armed_cisd_origin_sl = s_high

        bull_cisd_trigger = False
        bear_cisd_trigger = False

        if armed_bull_cisd and not np.isnan(armed_bull_high) and c0 > armed_bull_high:
            armed_bull_cisd = False
            bull_cisd_trigger = True
            current_delivery_regime = 1
            has_bull_sweep = False

        if armed_bear_cisd and not np.isnan(armed_bear_low) and c0 < armed_bear_low:
            armed_bear_cisd = False
            bear_cisd_trigger = True
            current_delivery_regime = -1
            has_bear_sweep = False

        # -------------------------------------------------------------
        # 5. STEP 3: ARM ENTRY ZONE (Arm on bar i, fill from bar i+1)
        # -------------------------------------------------------------
        new_bull_fvg = l0 > h2
        new_bear_fvg = h0 < l2

        if bull_cisd_trigger or (current_delivery_regime == 1 and new_bull_fvg and pending_zone is None and not in_position):
            z_top = l0 if new_bull_fvg else armed_bull_high
            z_bot = h2 if new_bull_fvg else (armed_bull_high - 1.0)
            z_ce = (z_top + z_bot) / 2.0

            if entry_model == "FVG_CE_50":
                e_price = z_ce
            elif entry_model == "CISD_Level":
                e_price = armed_bull_high if not np.isnan(armed_bull_high) else z_top
            else:  # FVG_Touch
                e_price = z_top

            if sl_model == "SL1_SweepWick":
                sl_price = (bull_sweep_low if not np.isnan(bull_sweep_low) else l1) - 0.50
            elif sl_model == "SL4_CISD_Origin":
                sl_price = (armed_cisd_origin_sl if not np.isnan(armed_cisd_origin_sl) else l1) - 0.50
            else:  # FVG_FormingWick
                sl_price = (h2 if new_bull_fvg else bull_sweep_low) - 0.50

            pending_zone = {
                "dir": 1,
                "entry_level": e_price,
                "sl": sl_price,
                "armed_bar": i,
                "entry_model": entry_model,
                "sl_model": sl_model,
            }

        if bear_cisd_trigger or (current_delivery_regime == -1 and new_bear_fvg and pending_zone is None and not in_position):
            z_top = l2 if new_bear_fvg else (armed_bear_low + 1.0)
            z_bot = h0 if new_bear_fvg else armed_bear_low
            z_ce = (z_top + z_bot) / 2.0

            if entry_model == "FVG_CE_50":
                e_price = z_ce
            elif entry_model == "CISD_Level":
                e_price = armed_bear_low if not np.isnan(armed_bear_low) else z_bot
            else:  # FVG_Touch
                e_price = z_bot

            if sl_model == "SL1_SweepWick":
                sl_price = (bear_sweep_high if not np.isnan(bear_sweep_high) else h1) + 0.50
            elif sl_model == "SL4_CISD_Origin":
                sl_price = (armed_cisd_origin_sl if not np.isnan(armed_cisd_origin_sl) else h1) + 0.50
            else:  # FVG_FormingWick
                sl_price = (l2 if new_bear_fvg else bear_sweep_high) + 0.50

            pending_zone = {
                "dir": -1,
                "entry_level": e_price,
                "sl": sl_price,
                "armed_bar": i,
                "entry_model": entry_model,
                "sl_model": sl_model,
            }

    # Convert results to DataFrame
    trades_df = pd.DataFrame([t.__dict__ for t in trades])
    if len(trades_df) == 0:
        return trades_df, {"total_trades": 0, "net_pnl": 0.0, "profit_factor": 0.0, "win_rate": 0.0}

    win_trades = trades_df[trades_df["total_pnl_usd"] > 0]
    loss_trades = trades_df[trades_df["total_pnl_usd"] < 0]
    gross_profit = win_trades["total_pnl_usd"].sum()
    gross_loss = abs(loss_trades["total_pnl_usd"].sum())
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else np.nan
    win_rate = len(win_trades) / len(trades_df) * 100
    avg_win = win_trades["total_pnl_usd"].mean() if len(win_trades) > 0 else 0
    avg_loss = loss_trades["total_pnl_usd"].mean() if len(loss_trades) > 0 else 0

    stats = {
        "total_trades": len(trades_df),
        "net_pnl": trades_df["total_pnl_usd"].sum(),
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        "profit_factor": profit_factor,
        "win_rate": win_rate,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "payoff_ratio": abs(avg_win / avg_loss) if avg_loss != 0 else np.nan,
        "avg_bars": trades_df["bars_held"].mean(),
    }
    return trades_df, stats


if __name__ == "__main__":
    print("Loading NQ 5m historical data...")
    data_path = _root / "data" / "NQ1_5m.parquet"
    df = pd.read_parquet(data_path)

    # Filter to last 4 years (2022-2026) for fast comprehensive benchmarking
    if isinstance(df.index, pd.DatetimeIndex):
        df_bench = df[df.index >= "2022-01-01"]
    else:
        df["datetime"] = pd.to_datetime(df["datetime"])
        df.set_index("datetime", inplace=True)
        df_bench = df[df.index >= "2022-01-01"]

    print(f"Dataset: {len(df_bench):,} bars from {df_bench.index.min()} to {df_bench.index.max()}")

    # -------------------------------------------------------------
    # EXPERIMENT MATRIX
    # -------------------------------------------------------------
    experiments = [
        # Base Variations
        {"name": "Base (FVG Touch, SL1 Sweep, No HTF Filter)", "entry": "FVG_Touch", "sl": "SL1_SweepWick", "htf": False, "qbps": 10.0, "rbps": 30.0},
        {"name": "HTF Aligned (FVG Touch, SL1 Sweep, HTF Trend Lock)", "entry": "FVG_Touch", "sl": "SL1_SweepWick", "htf": True, "qbps": 10.0, "rbps": 30.0},
        
        # Entry Models (with HTF Filter)
        {"name": "50% CE Limit Entry (SL1 Sweep, HTF Filter)", "entry": "FVG_CE_50", "sl": "SL1_SweepWick", "htf": True, "qbps": 10.0, "rbps": 30.0},
        {"name": "CISD Line Retest Entry (SL1 Sweep, HTF Filter)", "entry": "CISD_Level", "sl": "SL1_SweepWick", "htf": True, "qbps": 10.0, "rbps": 30.0},

        # Stop Loss Models
        {"name": "SL4 Delivery Origin Stop (FVG Touch, HTF Filter)", "entry": "FVG_Touch", "sl": "SL4_CISD_Origin", "htf": True, "qbps": 10.0, "rbps": 30.0},
        {"name": "FVG Forming Wick Stop (FVG Touch, HTF Filter)", "entry": "FVG_Touch", "sl": "FVG_FormingWick", "htf": True, "qbps": 10.0, "rbps": 30.0},

        # Target Scaling
        {"name": "Runner 50 bps MFE (FVG Touch, SL1 Sweep, HTF Filter)", "entry": "FVG_Touch", "sl": "SL1_SweepWick", "htf": True, "qbps": 10.0, "rbps": 50.0},
        {"name": "Runner 70 bps Fat-Tail MFE (FVG Touch, SL1 Sweep, HTF Filter)", "entry": "FVG_Touch", "sl": "SL1_SweepWick", "htf": True, "qbps": 10.0, "rbps": 70.0},
        {"name": "Queen 15 bps + Runner 50 bps (FVG Touch, SL1 Sweep, HTF Filter)", "entry": "FVG_Touch", "sl": "SL1_SweepWick", "htf": True, "qbps": 15.0, "rbps": 50.0},
    ]

    results = []
    print("\n" + "=" * 90)
    print("RUNNING INSTITUTIONAL LIQUIDITY -> CISD -> ENTRY EXPERIMENT SUITE")
    print("=" * 90)

    for exp in experiments:
        t0 = time.time()
        trades_df, stats = run_liquidity_cisd_backtest(
            df_bench,
            entry_model=exp["entry"],
            sl_model=exp["sl"],
            use_htf_filter=exp["htf"],
            queen_bps=exp["qbps"],
            runner_mfe_bps=exp["rbps"],
        )
        elapsed = time.time() - t0
        stats["Experiment"] = exp["name"]
        stats["Elapsed (s)"] = round(elapsed, 2)
        results.append(stats)
        print(f"[{exp['name']}] Trades: {stats['total_trades']} | Net PnL: ${stats['net_pnl']:,.2f} | PF: {stats['profit_factor']:.2f} | WinRate: {stats['win_rate']:.1f}% | Time: {elapsed:.2f}s")

    res_df = pd.DataFrame(results)[["Experiment", "total_trades", "net_pnl", "profit_factor", "win_rate", "payoff_ratio", "avg_win", "avg_loss", "Elapsed (s)"]]
    print("\n" + "=" * 110)
    print("FINAL EXPERIMENT MATRIX COMPARISON (2022 - 2026)")
    print("=" * 110)
    print(res_df.to_string(index=False))
