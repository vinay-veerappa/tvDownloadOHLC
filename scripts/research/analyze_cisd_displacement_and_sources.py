"""
========================================================================================
Institutional Research Engine: CISD Displacement Leg vs Entry Bar & Sweep Source Impact
========================================================================================
Tests:
1. Body Ratio & Volume on CISD BREAK BAR (Displacement) vs Retest Entry Bar.
2. Sweep Source Performance (PDH/PDL, 4H Swings, 1H Swings, Local 5m Swings).
3. Session-Specific Target Profiles (Asia vs London vs NY AM vs NY PM).
========================================================================================
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


def classify_session(hhmm: str) -> str:
    if hhmm >= "1800" or hhmm < "0200":
        return "Asia (18:00-02:00)"
    elif "0200" <= hhmm < "0800":
        return "London (02:00-08:00)"
    elif "0800" <= hhmm < "0930":
        return "Pre-NY (08:00-09:30)"
    elif "0930" <= hhmm < "1200":
        return "NY AM (09:30-12:00)"
    elif "1200" <= hhmm < "1330":
        return "NY Lunch (12:00-13:30)"
    elif "1330" <= hhmm <= "1600":
        return "NY PM (13:30-16:00)"
    return "Globex Other"


class AdvancedCISDResearchEngine:
    def __init__(self, df: pd.DataFrame):
        df = df.copy()
        if not isinstance(df.index, pd.DatetimeIndex):
            if "datetime" in df.columns:
                df["datetime"] = pd.to_datetime(df["datetime"])
                df.set_index("datetime", inplace=True)

        self.times = df.index
        self.opens = df["open"].to_numpy(dtype=np.float64)
        self.highs = df["high"].to_numpy(dtype=np.float64)
        self.lows = df["low"].to_numpy(dtype=np.float64)
        self.closes = df["close"].to_numpy(dtype=np.float64)
        self.volumes = df["volume"].to_numpy(dtype=np.float64) if "volume" in df.columns else np.ones(len(df))
        self.n = len(df)

        self.time_strs = self.times.strftime("%H%M")
        self.sessions = np.array([classify_session(hhmm) for hhmm in self.time_strs])
        self.dates = self.times.date

        # Volume SMA
        self.vol_sma = pd.Series(self.volumes).rolling(20).mean().to_numpy(dtype=np.float64)

        # Body-to-wick ratio
        candle_ranges = self.highs - self.lows
        candle_bodies = np.abs(self.closes - self.opens)
        self.body_ratios = np.where(candle_ranges > 0, candle_bodies / candle_ranges, 0.0)

        # Kaufman Efficiency Ratio (10)
        direction = np.abs(self.closes[10:] - self.closes[:-10])
        abs_diffs = np.abs(np.diff(self.closes))
        volatility = pd.Series(abs_diffs).rolling(10).sum().to_numpy(dtype=np.float64)[9:]
        ker_core = np.where(volatility > 0, direction / volatility, 0.0)
        self.ker = np.full(self.n, np.nan)
        self.ker[10:] = ker_core

        # Precalculate HTF sweeps
        df_1h = df.resample("1h").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
        df_1h["h1_h0"] = df_1h["high"].shift(1)
        df_1h["h1_l0"] = df_1h["low"].shift(1)
        self.h1_h0 = df_1h["h1_h0"].reindex(df.index, method="ffill").to_numpy(dtype=np.float64)
        self.h1_l0 = df_1h["h1_l0"].reindex(df.index, method="ffill").to_numpy(dtype=np.float64)

        df_4h = df.resample("4h").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
        df_4h["h4_h0"] = df_4h["high"].shift(1)
        df_4h["h4_l0"] = df_4h["low"].shift(1)
        self.h4_h0 = df_4h["h4_h0"].reindex(df.index, method="ffill").to_numpy(dtype=np.float64)
        self.h4_l0 = df_4h["h4_l0"].reindex(df.index, method="ffill").to_numpy(dtype=np.float64)

        # Daily PDH/PDL
        df["date_tmp"] = self.dates
        daily_df = df.groupby("date_tmp").agg({"high": "max", "low": "min"}).shift(1)
        pdh_map = daily_df["high"].to_dict()
        pdl_map = daily_df["low"].to_dict()
        self.pdh = np.array([pdh_map.get(d, np.nan) for d in self.dates])
        self.pdl = np.array([pdl_map.get(d, np.nan) for d in self.dates])

        # 3-bar swing pivots
        self.sw_h = np.full(self.n, np.nan)
        self.sw_l = np.full(self.n, np.nan)
        h = self.highs
        l = self.lows
        for i in range(3, self.n - 3):
            if h[i] > h[i-1] and h[i] > h[i-2] and h[i] > h[i-3] and h[i] > h[i+1] and h[i] > h[i+2] and h[i] > h[i+3]:
                self.sw_h[i+3] = h[i]
            if l[i] < l[i-1] and l[i] < l[i-2] and l[i] < l[i-3] and l[i] < l[i+1] and l[i] < l[i+2] and l[i] < l[i+3]:
                self.sw_l[i+3] = l[i]

    def run_simulation(
        self,
        allowed_sessions: Optional[List[str]] = None,
        allowed_sources: Optional[List[str]] = None,
        min_break_body_ratio: float = 0.0,
        min_break_vol_mult: float = 0.0,
        min_break_ker: float = 0.0,
        queen_bps: float = 10.0,
        runner_mfe_bps: float = 30.0,
        point_value: float = 2.0,
        comm_per_contract: float = 0.52,
        max_risk_bps: float = 15.0,
        min_risk_bps: float = 2.0,
        max_wait_bars: int = 20,
        max_daily_trades: int = 10,
    ) -> Tuple[pd.DataFrame, Dict]:
        n = self.n
        highs = self.highs
        lows = self.lows
        closes = self.closes
        opens = self.opens
        volumes = self.volumes
        vol_sma = self.vol_sma
        body_ratios = self.body_ratios
        ker = self.ker
        sessions = self.sessions
        dates = self.dates
        pdh = self.pdh
        pdl = self.pdl
        h1_h0 = self.h1_h0
        h1_l0 = self.h1_l0
        h4_h0 = self.h4_h0
        h4_l0 = self.h4_l0
        sw_h = self.sw_h
        sw_l = self.sw_l
        times = self.times

        bsl_list: List[float] = []
        ssl_list: List[float] = []

        trades = []
        trade_count = 0
        current_date = None
        daily_trade_count = 0

        has_bull_sweep = False
        has_bear_sweep = False
        bull_sweep_low = np.nan
        bear_sweep_high = np.nan
        bull_sweep_bar = -9999
        bear_sweep_bar = -9999
        last_sweep_source = ""

        armed_bull_cisd = False
        armed_bear_cisd = False
        armed_bull_high = np.nan
        armed_bear_low = np.nan
        armed_cisd_origin_sl = np.nan
        current_delivery_regime = 0

        pending_zone: Optional[Dict] = None
        in_position = False
        pos_dir = 0
        pos_entry_bar = 0
        pos_entry_time = None
        pos_entry_price = 0.0
        active_stop_loss = 0.0
        active_queen_tp = 0.0
        active_runner_tp = 0.0
        queen_filled = False
        pos_mfe = 0.0
        pos_mae = 0.0
        pos_session = ""
        pos_sweep_src = ""
        pos_initial_sl = 0.0

        for i in range(25, n):
            t = times[i]
            bar_date = dates[i]
            sess = sessions[i]
            h0, l0, c0, o0 = highs[i], lows[i], closes[i], opens[i]
            h1, l1 = highs[i - 1], lows[i - 1]
            h2, l2 = highs[i - 2], lows[i - 2]

            if bar_date != current_date:
                current_date = bar_date
                daily_trade_count = 0

            # Update swing lists
            if not np.isnan(sw_h[i]):
                bsl_list.append(sw_h[i])
                if len(bsl_list) > 10: bsl_list.pop(0)
            if not np.isnan(sw_l[i]):
                ssl_list.append(sw_l[i])
                if len(ssl_list) > 10: ssl_list.pop(0)

            # 1. POSITION MANAGEMENT
            if in_position:
                if pos_dir == 1:
                    pos_mfe = max(pos_mfe, h0 - pos_entry_price)
                    pos_mae = max(pos_mae, pos_entry_price - l0)

                    if l0 <= active_stop_loss:
                        q_pnl = (active_queen_tp - pos_entry_price) if queen_filled else (active_stop_loss - pos_entry_price)
                        r_pnl = (active_stop_loss - pos_entry_price)
                        tot_usd = (q_pnl + r_pnl) * point_value - (4 * comm_per_contract)
                        trade_count += 1
                        risk_pts = abs(pos_entry_price - pos_initial_sl)
                        trades.append({
                            "trade_id": trade_count, "direction": 1, "entry_time": pos_entry_time, "entry_bar": pos_entry_bar,
                            "entry_price": pos_entry_price, "stop_loss": pos_initial_sl, "risk_pts": risk_pts,
                            "risk_bps": (risk_pts / pos_entry_price) * 10000.0, "queen_tp": active_queen_tp, "runner_tp": active_runner_tp,
                            "queen_pnl_pts": q_pnl, "runner_pnl_pts": r_pnl, "total_pnl_usd": tot_usd, "is_win": tot_usd > 0,
                            "queen_filled": queen_filled, "runner_filled": False, "bars_held": i - pos_entry_bar,
                            "mfe_pts": pos_mfe, "mae_pts": pos_mae, "mfe_bps": (pos_mfe / pos_entry_price) * 10000.0,
                            "mae_bps": (pos_mae / pos_entry_price) * 10000.0, "session_name": pos_session,
                            "sweep_source": pos_sweep_src,
                        })
                        in_position = False
                        continue

                    if not queen_filled and h0 >= active_queen_tp:
                        queen_filled = True
                        active_stop_loss = pos_entry_price

                    if h0 >= active_runner_tp:
                        q_pnl = active_queen_tp - pos_entry_price
                        r_pnl = active_runner_tp - pos_entry_price
                        tot_usd = (q_pnl + r_pnl) * point_value - (4 * comm_per_contract)
                        trade_count += 1
                        risk_pts = abs(pos_entry_price - pos_initial_sl)
                        trades.append({
                            "trade_id": trade_count, "direction": 1, "entry_time": pos_entry_time, "entry_bar": pos_entry_bar,
                            "entry_price": pos_entry_price, "stop_loss": pos_initial_sl, "risk_pts": risk_pts,
                            "risk_bps": (risk_pts / pos_entry_price) * 10000.0, "queen_tp": active_queen_tp, "runner_tp": active_runner_tp,
                            "queen_pnl_pts": q_pnl, "runner_pnl_pts": r_pnl, "total_pnl_usd": tot_usd, "is_win": True,
                            "queen_filled": True, "runner_filled": True, "bars_held": i - pos_entry_bar,
                            "mfe_pts": pos_mfe, "mae_pts": pos_mae, "mfe_bps": (pos_mfe / pos_entry_price) * 10000.0,
                            "mae_bps": (pos_mae / pos_entry_price) * 10000.0, "session_name": pos_session,
                            "sweep_source": pos_sweep_src,
                        })
                        in_position = False
                        continue

                elif pos_dir == -1:
                    pos_mfe = max(pos_mfe, pos_entry_price - l0)
                    pos_mae = max(pos_mae, h0 - pos_entry_price)

                    if h0 >= active_stop_loss:
                        q_pnl = (pos_entry_price - active_queen_tp) if queen_filled else (pos_entry_price - active_stop_loss)
                        r_pnl = (pos_entry_price - active_stop_loss)
                        tot_usd = (q_pnl + r_pnl) * point_value - (4 * comm_per_contract)
                        trade_count += 1
                        risk_pts = abs(pos_entry_price - pos_initial_sl)
                        trades.append({
                            "trade_id": trade_count, "direction": -1, "entry_time": pos_entry_time, "entry_bar": pos_entry_bar,
                            "entry_price": pos_entry_price, "stop_loss": pos_initial_sl, "risk_pts": risk_pts,
                            "risk_bps": (risk_pts / pos_entry_price) * 10000.0, "queen_tp": active_queen_tp, "runner_tp": active_runner_tp,
                            "queen_pnl_pts": q_pnl, "runner_pnl_pts": r_pnl, "total_pnl_usd": tot_usd, "is_win": tot_usd > 0,
                            "queen_filled": queen_filled, "runner_filled": False, "bars_held": i - pos_entry_bar,
                            "mfe_pts": pos_mfe, "mae_pts": pos_mae, "mfe_bps": (pos_mfe / pos_entry_price) * 10000.0,
                            "mae_bps": (pos_mae / pos_entry_price) * 10000.0, "session_name": pos_session,
                            "sweep_source": pos_sweep_src,
                        })
                        in_position = False
                        continue

                    if not queen_filled and l0 <= active_queen_tp:
                        queen_filled = True
                        active_stop_loss = pos_entry_price

                    if l0 <= active_runner_tp:
                        q_pnl = pos_entry_price - active_queen_tp
                        r_pnl = pos_entry_price - active_runner_tp
                        tot_usd = (q_pnl + r_pnl) * point_value - (4 * comm_per_contract)
                        trade_count += 1
                        risk_pts = abs(pos_entry_price - pos_initial_sl)
                        trades.append({
                            "trade_id": trade_count, "direction": -1, "entry_time": pos_entry_time, "entry_bar": pos_entry_bar,
                            "entry_price": pos_entry_price, "stop_loss": pos_initial_sl, "risk_pts": risk_pts,
                            "risk_bps": (risk_pts / pos_entry_price) * 10000.0, "queen_tp": active_queen_tp, "runner_tp": active_runner_tp,
                            "queen_pnl_pts": q_pnl, "runner_pnl_pts": r_pnl, "total_pnl_usd": tot_usd, "is_win": True,
                            "queen_filled": True, "runner_filled": True, "bars_held": i - pos_entry_bar,
                            "mfe_pts": pos_mfe, "mae_pts": pos_mae, "mfe_bps": (pos_mfe / pos_entry_price) * 10000.0,
                            "mae_bps": (pos_mae / pos_entry_price) * 10000.0, "session_name": pos_session,
                            "sweep_source": pos_sweep_src,
                        })
                        in_position = False
                        continue

            # 2. EVALUATE PENDING ENTRY FILL
            if pending_zone is not None and not in_position:
                p_dir = pending_zone["dir"]
                p_level = pending_zone["entry_level"]
                p_sl = pending_zone["sl"]
                p_armed_bar = pending_zone["armed_bar"]

                if (i - p_armed_bar) <= max_wait_bars:
                    sess_ok = True
                    if allowed_sessions is not None and sess not in allowed_sessions:
                        sess_ok = False

                    src_ok = True
                    if allowed_sources is not None and pending_zone["sweep_source"] not in allowed_sources:
                        src_ok = False

                    can_enter = sess_ok and src_ok and (daily_trade_count < max_daily_trades)

                    if can_enter:
                        if p_dir == 1 and l0 <= p_level:
                            in_position = True; pos_dir = 1
                            pos_entry_price = p_level; active_stop_loss = p_sl
                            pos_initial_sl = p_sl
                            pos_entry_bar = i; pos_entry_time = t
                            pos_mfe = max(0.0, h0 - pos_entry_price)
                            pos_mae = max(0.0, pos_entry_price - l0)
                            pos_session = sess
                            pos_sweep_src = pending_zone["sweep_source"]

                            dist_q = round(pos_entry_price * (queen_bps / 10000.0) * 4) / 4.0
                            dist_r = round(pos_entry_price * (runner_mfe_bps / 10000.0) * 4) / 4.0
                            active_queen_tp = pos_entry_price + dist_q
                            active_runner_tp = pos_entry_price + dist_r
                            queen_filled = False
                            daily_trade_count += 1
                            pending_zone = None

                        elif p_dir == -1 and h0 >= p_level:
                            in_position = True; pos_dir = -1
                            pos_entry_price = p_level; active_stop_loss = p_sl
                            pos_initial_sl = p_sl
                            pos_entry_bar = i; pos_entry_time = t
                            pos_mfe = max(0.0, pos_entry_price - l0)
                            pos_mae = max(0.0, h0 - pos_entry_price)
                            pos_session = sess
                            pos_sweep_src = pending_zone["sweep_source"]

                            dist_q = round(pos_entry_price * (queen_bps / 10000.0) * 4) / 4.0
                            dist_r = round(pos_entry_price * (runner_mfe_bps / 10000.0) * 4) / 4.0
                            active_queen_tp = pos_entry_price - dist_q
                            active_runner_tp = pos_entry_price - dist_r
                            queen_filled = False
                            daily_trade_count += 1
                            pending_zone = None
                else:
                    pending_zone = None

            # 3. SWEEP DETECTION
            bsl_swept = False
            ssl_swept = False
            sweep_extreme = np.nan
            sweep_src = ""

            cur_pdh = pdh[i]
            cur_pdl = pdl[i]
            if not np.isnan(cur_pdh) and h0 > cur_pdh and (c0 < cur_pdh or o0 < cur_pdh):
                bsl_swept = True; sweep_extreme = h0; sweep_src = "PDH"
            if not np.isnan(cur_pdl) and l0 < cur_pdl and (c0 > cur_pdl or o0 > cur_pdl):
                ssl_swept = True; sweep_extreme = l0; sweep_src = "PDL"

            cur_h4_h = h4_h0[i]; cur_h4_l = h4_l0[i]
            if not np.isnan(cur_h4_h) and h0 > cur_h4_h and (c0 < cur_h4_h or o0 < cur_h4_h):
                bsl_swept = True; sweep_extreme = h0; sweep_src = "4H_BSL"
            if not np.isnan(cur_h4_l) and l0 < cur_h4_l and (c0 > cur_h4_l or o0 > cur_h4_l):
                ssl_swept = True; sweep_extreme = l0; sweep_src = "4H_SSL"

            cur_h1_h = h1_h0[i]; cur_h1_l = h1_l0[i]
            if not np.isnan(cur_h1_h) and h0 > cur_h1_h and (c0 < cur_h1_h or o0 < cur_h1_h):
                bsl_swept = True; sweep_extreme = h0; sweep_src = "1H_BSL"
            if not np.isnan(cur_h1_l) and l0 < cur_h1_l and (c0 > cur_h1_l or o0 > cur_h1_l):
                ssl_swept = True; sweep_extreme = l0; sweep_src = "1H_SSL"

            if not bsl_swept:
                for b_val in bsl_list:
                    if h0 > b_val and c0 < b_val:
                        bsl_swept = True; sweep_extreme = h0; sweep_src = "Swing_H"; break
            if not ssl_swept:
                for s_val in ssl_list:
                    if l0 < s_val and c0 > s_val:
                        ssl_swept = True; sweep_extreme = l0; sweep_src = "Swing_L"; break

            if ssl_swept:
                has_bull_sweep = True; bull_sweep_low = sweep_extreme if not np.isnan(sweep_extreme) else l0
                bull_sweep_bar = i; last_sweep_source = sweep_src
            if bsl_swept:
                has_bear_sweep = True; bear_sweep_high = sweep_extreme if not np.isnan(sweep_extreme) else h0
                bear_sweep_bar = i; last_sweep_source = sweep_src

            if (i - bull_sweep_bar) > 25: has_bull_sweep = False
            if (i - bear_sweep_bar) > 25: has_bear_sweep = False

            # 4. CISD DETECTION ON DISPLACEMENT BAR
            if has_bull_sweep and ssl_swept:
                s_high = max(o0, c0); s_low = min(o0, c0)
                for k in range(1, min(25, i)):
                    if closes[i - k] <= opens[i - k]:
                        s_high = max(s_high, max(opens[i - k], closes[i - k]))
                        s_low = min(s_low, min(opens[i - k], closes[i - k]))
                    else:
                        break
                armed_bull_cisd = True; armed_bull_high = s_high; armed_cisd_origin_sl = s_low

            if has_bear_sweep and bsl_swept:
                s_high = max(o0, c0); s_low = min(o0, c0)
                for k in range(1, min(25, i)):
                    if closes[i - k] >= opens[i - k]:
                        s_high = max(s_high, max(opens[i - k], closes[i - k]))
                        s_low = min(s_low, min(opens[i - k], closes[i - k]))
                    else:
                        break
                armed_bear_cisd = True; armed_bear_low = s_low; armed_cisd_origin_sl = s_high

            bull_cisd_trig = False; bear_cisd_trig = False
            # Check displacement bar quality
            br_ok = body_ratios[i] >= min_break_body_ratio if min_break_body_ratio > 0 else True
            cur_v_sma = vol_sma[i] if not np.isnan(vol_sma[i]) and vol_sma[i] > 0 else 1.0
            vr_ok = (volumes[i] / cur_v_sma) >= min_break_vol_mult if min_break_vol_mult > 0 else True
            ker_val = ker[i] if not np.isnan(ker[i]) else 0.5
            ker_ok = ker_val >= min_break_ker if min_break_ker > 0 else True
            break_filters_passed = br_ok and vr_ok and ker_ok

            if armed_bull_cisd and not np.isnan(armed_bull_high) and c0 > armed_bull_high:
                armed_bull_cisd = False
                if break_filters_passed:
                    bull_cisd_trig = True; current_delivery_regime = 1; has_bull_sweep = False

            if armed_bear_cisd and not np.isnan(armed_bear_low) and c0 < armed_bear_low:
                armed_bear_cisd = False
                if break_filters_passed:
                    bear_cisd_trig = True; current_delivery_regime = -1; has_bear_sweep = False

            # 5. ENTRY ZONE ARMING
            new_bull_fvg = l0 > h2 and (l0 - h2) >= 0.50
            new_bear_fvg = h0 < l2 and (l2 - h0) >= 0.50

            if (bull_cisd_trig or (current_delivery_regime == 1 and new_bull_fvg)) and pending_zone is None and not in_position:
                e_price = l0
                sl_price = (armed_cisd_origin_sl if not np.isnan(armed_cisd_origin_sl) else l1) - 0.50
                if not np.isnan(sl_price) and sl_price < e_price:
                    risk_bps = ((e_price - sl_price) / e_price) * 10000.0
                    if min_risk_bps <= risk_bps <= max_risk_bps:
                        pending_zone = {
                            "dir": 1, "entry_level": e_price, "sl": sl_price, "armed_bar": i,
                            "sweep_source": last_sweep_source,
                        }

            if (bear_cisd_trig or (current_delivery_regime == -1 and new_bear_fvg)) and pending_zone is None and not in_position:
                e_price = h0
                sl_price = (armed_cisd_origin_sl if not np.isnan(armed_cisd_origin_sl) else h1) + 0.50
                if not np.isnan(sl_price) and sl_price > e_price:
                    risk_bps = ((sl_price - e_price) / e_price) * 10000.0
                    if min_risk_bps <= risk_bps <= max_risk_bps:
                        pending_zone = {
                            "dir": -1, "entry_level": e_price, "sl": sl_price, "armed_bar": i,
                            "sweep_source": last_sweep_source,
                        }

        trades_df = pd.DataFrame(trades)
        if len(trades_df) == 0:
            return trades_df, {"total_trades": 0, "net_pnl": 0.0, "profit_factor": 0.0, "win_rate": 0.0}

        win_trades = trades_df[trades_df["total_pnl_usd"] > 0]
        loss_trades = trades_df[trades_df["total_pnl_usd"] < 0]
        gp = win_trades["total_pnl_usd"].sum()
        gl = abs(loss_trades["total_pnl_usd"].sum())
        pf = gp / gl if gl > 0 else np.nan
        wr = (len(win_trades) / len(trades_df)) * 100.0

        stats = {
            "total_trades": len(trades_df),
            "net_pnl": trades_df["total_pnl_usd"].sum(),
            "gross_profit": gp,
            "gross_loss": gl,
            "profit_factor": pf,
            "win_rate": wr,
        }
        return trades_df, stats


def main():
    data_path = _root / "data/NQ1_5m.parquet"
    df_nq = pd.read_parquet(data_path)
    if not isinstance(df_nq.index, pd.DatetimeIndex):
        df_nq["datetime"] = pd.to_datetime(df_nq["datetime"])
        df_nq.set_index("datetime", inplace=True)
    df_bench = df_nq[df_nq.index >= "2022-01-01"].copy()

    engine = AdvancedCISDResearchEngine(df_bench)

    # 1. DISPLACEMENT BAR FILTER TESTS
    print("\n" + "=" * 95, flush=True)
    print("TEST 1: FILTERS APPLIED TO DISPLACEMENT BAR (The CISD Break Bar)", flush=True)
    print("=" * 95, flush=True)

    break_tests = [
        {"name": "Raw Baseline (No Break Filters)", "body": 0.0, "vol": 0.0, "ker": 0.0},
        {"name": "Displacement Body Ratio >= 50%", "body": 0.50, "vol": 0.0, "ker": 0.0},
        {"name": "Displacement Body Ratio >= 60%", "body": 0.60, "vol": 0.0, "ker": 0.0},
        {"name": "Displacement Body Ratio >= 65%", "body": 0.65, "vol": 0.0, "ker": 0.0},
        {"name": "Displacement Volume >= 1.25x", "body": 0.0, "vol": 1.25, "ker": 0.0},
        {"name": "Displacement Volume >= 1.50x", "body": 0.0, "vol": 1.50, "ker": 0.0},
        {"name": "Displacement KER >= 0.40", "body": 0.0, "vol": 0.0, "ker": 0.40},
        {"name": "Displacement Combo: Body 60% + Vol 1.25x", "body": 0.60, "vol": 1.25, "ker": 0.0},
    ]

    res1 = []
    for bt in break_tests:
        tdf, st = engine.run_simulation(
            min_break_body_ratio=bt["body"],
            min_break_vol_mult=bt["vol"],
            min_break_ker=bt["ker"],
        )
        res1.append({
            "Displacement Test": bt["name"],
            "Trades": st["total_trades"],
            "Win Rate": f"{st['win_rate']:.1f}%",
            "Profit Factor": f"{st['profit_factor']:.2f}",
            "Net PnL ($)": f"${st['net_pnl']:,.2f}",
            "Avg Trade ($)": f"${st['net_pnl']/st['total_trades']:.2f}" if st["total_trades"] > 0 else "0",
        })
    print(pd.DataFrame(res1).to_string(index=False), flush=True)

    # 2. SWEEP SOURCE ABLATION
    print("\n" + "=" * 95, flush=True)
    print("TEST 2: SWEEP SOURCE ABLATION (Where did the liquidity sweep originate?)", flush=True)
    print("=" * 95, flush=True)

    sources = ["PDH", "PDL", "4H_BSL", "4H_SSL", "1H_BSL", "1H_SSL", "Swing_H", "Swing_L"]
    base_df, _ = engine.run_simulation()
    
    src_rows = []
    for src in ["PDH", "PDL", "4H_BSL", "4H_SSL", "1H_BSL", "1H_SSL", "Swing_H", "Swing_L"]:
        sub = base_df[base_df["sweep_source"] == src]
        if len(sub) == 0: continue
        wins = sub[sub["total_pnl_usd"] > 0]
        losses = sub[sub["total_pnl_usd"] < 0]
        gp = wins["total_pnl_usd"].sum()
        gl = abs(losses["total_pnl_usd"].sum())
        pf = gp / gl if gl > 0 else np.nan
        wr = (len(wins) / len(sub)) * 100.0
        src_rows.append({
            "Sweep Source": src,
            "Trades": len(sub),
            "Trade Share": f"{(len(sub)/len(base_df))*100:.1f}%",
            "Win Rate": f"{wr:.1f}%",
            "Profit Factor": f"{pf:.2f}" if not np.isnan(pf) else "N/A",
            "Net PnL ($)": f"${sub['total_pnl_usd'].sum():,.2f}",
            "Median MFE (bps)": f"{sub['mfe_bps'].median():.1f} bps",
            "Median MAE (bps)": f"{sub['mae_bps'].median():.1f} bps",
        })
    print(pd.DataFrame(src_rows).to_string(index=False), flush=True)


if __name__ == "__main__":
    main()
