"""
========================================================================================
Institutional Research Engine: Midline (50% Equilibrium) CISD & Magnet Analytics
========================================================================================
Analyzes:
1. Midline Sweep & Reclaim CISD Trades:
   - Prev Day Mid (PDM)
   - P12 Mid (18:00 - 06:00 ET)
   - Asia Mid (18:00 - 02:00 ET)
   - London Mid (02:00 - 08:00 ET)
2. Midlines as Magnet / Draw on Liquidity (DOL):
   - From External Sweep to Mid Target Reach Probabilities
   - MFE & MAE distributions in Basis Points (bps) and Price %
========================================================================================
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass
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


class MidlineCISDResearchEngine:
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
        self.dates = self.times.date

        time_strs = self.times.strftime("%H%M")
        self.time_strs = time_strs

        # -------------------------------------------------------------
        # 1. COMPUTE ALL SESSION MIDLINES (PDM, P12 Mid, Asia Mid, London Mid)
        # -------------------------------------------------------------
        print("Calculating Session Boxes and 50% Midlines...", flush=True)

        # A. Previous Day High / Low / Mid (PDM)
        df["date_tmp"] = self.dates
        daily_df = df.groupby("date_tmp").agg({"high": "max", "low": "min"}).shift(1)
        daily_df["pdm"] = (daily_df["high"] + daily_df["low"]) / 2.0
        pdh_map = daily_df["high"].to_dict()
        pdl_map = daily_df["low"].to_dict()
        pdm_map = daily_df["pdm"].to_dict()

        self.pdh = np.array([pdh_map.get(d, np.nan) for d in self.dates])
        self.pdl = np.array([pdl_map.get(d, np.nan) for d in self.dates])
        self.pdm = np.array([pdm_map.get(d, np.nan) for d in self.dates])

        # B. Asia Session Box (18:00 - 02:00 ET) & Asia Mid
        self.asia_high = np.full(self.n, np.nan)
        self.asia_low = np.full(self.n, np.nan)
        self.asia_mid = np.full(self.n, np.nan)

        # C. London Session Box (02:00 - 08:00 ET) & London Mid
        self.london_high = np.full(self.n, np.nan)
        self.london_low = np.full(self.n, np.nan)
        self.london_mid = np.full(self.n, np.nan)

        # D. P12 Box (18:00 - 06:00 ET) & P12 Mid
        self.p12_high = np.full(self.n, np.nan)
        self.p12_low = np.full(self.n, np.nan)
        self.p12_mid = np.full(self.n, np.nan)

        # Populate rolling session boundaries
        cur_asia_h, cur_asia_l = np.nan, np.nan
        last_asia_h, last_asia_l = np.nan, np.nan

        cur_london_h, cur_london_l = np.nan, np.nan
        last_london_h, last_london_l = np.nan, np.nan

        cur_p12_h, cur_p12_l = np.nan, np.nan
        last_p12_h, last_p12_l = np.nan, np.nan

        for i in range(self.n):
            hhmm = time_strs[i]
            h, l = self.highs[i], self.lows[i]

            # Asia window: 18:00 - 02:00
            if hhmm == "1800":
                cur_asia_h, cur_asia_l = h, l
                cur_p12_h, cur_p12_l = h, l
            elif hhmm > "1800" or hhmm < "0200":
                cur_asia_h = max(cur_asia_h, h) if not np.isnan(cur_asia_h) else h
                cur_asia_l = min(cur_asia_l, l) if not np.isnan(cur_asia_l) else l
                cur_p12_h = max(cur_p12_h, h) if not np.isnan(cur_p12_h) else h
                cur_p12_l = min(cur_p12_l, l) if not np.isnan(cur_p12_l) else l
            elif hhmm == "0200":
                last_asia_h, last_asia_l = cur_asia_h, cur_asia_l
                cur_london_h, cur_london_l = h, l
                cur_p12_h = max(cur_p12_h, h) if not np.isnan(cur_p12_h) else h
                cur_p12_l = min(cur_p12_l, l) if not np.isnan(cur_p12_l) else l
            elif "0200" < hhmm < "0600":
                cur_london_h = max(cur_london_h, h) if not np.isnan(cur_london_h) else h
                cur_london_l = min(cur_london_l, l) if not np.isnan(cur_london_l) else l
                cur_p12_h = max(cur_p12_h, h) if not np.isnan(cur_p12_h) else h
                cur_p12_l = min(cur_p12_l, l) if not np.isnan(cur_p12_l) else l
            elif hhmm == "0600":
                last_p12_h, last_p12_l = cur_p12_h, cur_p12_l
                cur_london_h = max(cur_london_h, h) if not np.isnan(cur_london_h) else h
                cur_london_l = min(cur_london_l, l) if not np.isnan(cur_london_l) else l
            elif "0600" < hhmm < "0800":
                cur_london_h = max(cur_london_h, h) if not np.isnan(cur_london_h) else h
                cur_london_l = min(cur_london_l, l) if not np.isnan(cur_london_l) else l
            elif hhmm == "0800":
                last_london_h, last_london_l = cur_london_h, cur_london_l

            # Set available completed levels
            if not np.isnan(last_asia_h) and not np.isnan(last_asia_l):
                self.asia_high[i] = last_asia_h
                self.asia_low[i] = last_asia_l
                self.asia_mid[i] = (last_asia_h + last_asia_l) / 2.0

            if not np.isnan(last_london_h) and not np.isnan(last_london_l):
                self.london_high[i] = last_london_h
                self.london_low[i] = last_london_l
                self.london_mid[i] = (last_london_h + last_london_l) / 2.0

            if not np.isnan(last_p12_h) and not np.isnan(last_p12_l):
                self.p12_high[i] = last_p12_h
                self.p12_low[i] = last_p12_l
                self.p12_mid[i] = (last_p12_h + last_p12_l) / 2.0

    def run_midline_sweep_simulation(
        self,
        queen_bps: float = 10.0,
        runner_mfe_bps: float = 30.0,
        point_value: float = 2.0,
        comm_per_contract: float = 0.52,
        max_risk_bps: float = 15.0,
        min_risk_bps: float = 2.0,
    ) -> pd.DataFrame:
        """
        Simulates CISD setups triggered specifically from false-break sweeps & reclaims of Midlines:
        - Prev Day Mid (PDM)
        - P12 Mid
        - Asia Mid
        - London Mid
        """
        n = self.n
        highs = self.highs
        lows = self.lows
        closes = self.closes
        opens = self.opens
        times = self.times
        dates = self.dates

        pdm = self.pdm
        p12_mid = self.p12_mid
        asia_mid = self.asia_mid
        london_mid = self.london_mid

        trades = []
        trade_count = 0

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
        pos_mid_src = ""
        pos_initial_sl = 0.0

        pending_zone = None

        # Track armed mid sweep state
        armed_bull = False; armed_bear = False
        armed_bull_high = np.nan; armed_bear_low = np.nan
        armed_sl = np.nan
        armed_src = ""
        armed_bar = -9999

        for i in range(25, n):
            t = times[i]
            h0, l0, c0, o0 = highs[i], lows[i], closes[i], opens[i]
            h1, l1 = highs[i - 1], lows[i - 1]
            h2, l2 = highs[i - 2], lows[i - 2]

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
                            "trade_id": trade_count, "direction": 1, "entry_time": pos_entry_time, "entry_price": pos_entry_price,
                            "stop_loss": pos_initial_sl, "risk_pts": risk_pts, "risk_bps": (risk_pts / pos_entry_price) * 10000.0,
                            "queen_pnl_pts": q_pnl, "runner_pnl_pts": r_pnl, "total_pnl_usd": tot_usd, "is_win": tot_usd > 0,
                            "bars_held": i - pos_entry_bar, "mfe_pts": pos_mfe, "mae_pts": pos_mae,
                            "mfe_bps": (pos_mfe / pos_entry_price) * 10000.0, "mae_bps": (pos_mae / pos_entry_price) * 10000.0,
                            "mid_source": pos_mid_src,
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
                            "trade_id": trade_count, "direction": 1, "entry_time": pos_entry_time, "entry_price": pos_entry_price,
                            "stop_loss": pos_initial_sl, "risk_pts": risk_pts, "risk_bps": (risk_pts / pos_entry_price) * 10000.0,
                            "queen_pnl_pts": q_pnl, "runner_pnl_pts": r_pnl, "total_pnl_usd": tot_usd, "is_win": True,
                            "bars_held": i - pos_entry_bar, "mfe_pts": pos_mfe, "mae_pts": pos_mae,
                            "mfe_bps": (pos_mfe / pos_entry_price) * 10000.0, "mae_bps": (pos_mae / pos_entry_price) * 10000.0,
                            "mid_source": pos_mid_src,
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
                            "trade_id": trade_count, "direction": -1, "entry_time": pos_entry_time, "entry_price": pos_entry_price,
                            "stop_loss": pos_initial_sl, "risk_pts": risk_pts, "risk_bps": (risk_pts / pos_entry_price) * 10000.0,
                            "queen_pnl_pts": q_pnl, "runner_pnl_pts": r_pnl, "total_pnl_usd": tot_usd, "is_win": tot_usd > 0,
                            "bars_held": i - pos_entry_bar, "mfe_pts": pos_mfe, "mae_pts": pos_mae,
                            "mfe_bps": (pos_mfe / pos_entry_price) * 10000.0, "mae_bps": (pos_mae / pos_entry_price) * 10000.0,
                            "mid_source": pos_mid_src,
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
                            "trade_id": trade_count, "direction": -1, "entry_time": pos_entry_time, "entry_price": pos_entry_price,
                            "stop_loss": pos_initial_sl, "risk_pts": risk_pts, "risk_bps": (risk_pts / pos_entry_price) * 10000.0,
                            "queen_pnl_pts": q_pnl, "runner_pnl_pts": r_pnl, "total_pnl_usd": tot_usd, "is_win": True,
                            "bars_held": i - pos_entry_bar, "mfe_pts": pos_mfe, "mae_pts": pos_mae,
                            "mfe_bps": (pos_mfe / pos_entry_price) * 10000.0, "mae_bps": (pos_mae / pos_entry_price) * 10000.0,
                            "mid_source": pos_mid_src,
                        })
                        in_position = False
                        continue

            # 2. PENDING ENTRY FILL
            if pending_zone is not None and not in_position:
                if (i - pending_zone["armed_bar"]) <= 20:
                    p_dir = pending_zone["dir"]
                    p_level = pending_zone["entry_level"]
                    p_sl = pending_zone["sl"]

                    if p_dir == 1 and l0 <= p_level:
                        in_position = True; pos_dir = 1
                        pos_entry_price = p_level; active_stop_loss = p_sl
                        pos_initial_sl = p_sl
                        pos_entry_bar = i; pos_entry_time = t
                        pos_mfe = max(0.0, h0 - pos_entry_price)
                        pos_mae = max(0.0, pos_entry_price - l0)
                        pos_mid_src = pending_zone["mid_src"]

                        dist_q = round(pos_entry_price * (queen_bps / 10000.0) * 4) / 4.0
                        dist_r = round(pos_entry_price * (runner_mfe_bps / 10000.0) * 4) / 4.0
                        active_queen_tp = pos_entry_price + dist_q
                        active_runner_tp = pos_entry_price + dist_r
                        queen_filled = False
                        pending_zone = None

                    elif p_dir == -1 and h0 >= p_level:
                        in_position = True; pos_dir = -1
                        pos_entry_price = p_level; active_stop_loss = p_sl
                        pos_initial_sl = p_sl
                        pos_entry_bar = i; pos_entry_time = t
                        pos_mfe = max(0.0, pos_entry_price - l0)
                        pos_mae = max(0.0, h0 - pos_entry_price)
                        pos_mid_src = pending_zone["mid_src"]

                        dist_q = round(pos_entry_price * (queen_bps / 10000.0) * 4) / 4.0
                        dist_r = round(pos_entry_price * (runner_mfe_bps / 10000.0) * 4) / 4.0
                        active_queen_tp = pos_entry_price - dist_q
                        active_runner_tp = pos_entry_price - dist_r
                        queen_filled = False
                        pending_zone = None
                else:
                    pending_zone = None

            # 3. DETECT MIDLINE SWEEPS & ARMED CISD
            mid_candidates = [
                ("Prev_Day_Mid (PDM)", pdm[i]),
                ("P12_Mid (Overnight 50%)", p12_mid[i]),
                ("Asia_Mid (50%)", asia_mid[i]),
                ("London_Mid (50%)", london_mid[i]),
            ]

            for m_name, m_val in mid_candidates:
                if np.isnan(m_val):
                    continue

                # Bullish Mid Sweep: Price probed below Mid, but closed above or delivery reversed
                if l0 < m_val and c0 > m_val and o0 > m_val:
                    # Find delivery origin
                    s_high = max(o0, c0); s_low = min(o0, c0)
                    for k in range(1, min(25, i)):
                        if closes[i - k] <= opens[i - k]:
                            s_high = max(s_high, max(opens[i - k], closes[i - k]))
                            s_low = min(s_low, min(opens[i - k], closes[i - k]))
                        else:
                            break
                    armed_bull = True; armed_bull_high = s_high; armed_sl = s_low; armed_src = m_name
                    armed_bar = i
                    break

                # Bearish Mid Sweep: Price probed above Mid, but closed below
                if h0 > m_val and c0 < m_val and o0 < m_val:
                    s_high = max(o0, c0); s_low = min(o0, c0)
                    for k in range(1, min(25, i)):
                        if closes[i - k] >= opens[i - k]:
                            s_high = max(s_high, max(opens[i - k], closes[i - k]))
                            s_low = min(s_low, min(opens[i - k], closes[i - k]))
                        else:
                            break
                    armed_bear = True; armed_bear_low = s_low; armed_sl = s_high; armed_src = m_name
                    armed_bar = i
                    break

            if (i - armed_bar) > 25:
                armed_bull = False; armed_bear = False

            # 4. CISD TRIGGER
            if armed_bull and not np.isnan(armed_bull_high) and c0 > armed_bull_high and pending_zone is None and not in_position:
                armed_bull = False
                e_price = l0
                sl_price = (armed_sl if not np.isnan(armed_sl) else l1) - 0.50
                if sl_price < e_price:
                    risk_bps = ((e_price - sl_price) / e_price) * 10000.0
                    if min_risk_bps <= risk_bps <= max_risk_bps:
                        pending_zone = {"dir": 1, "entry_level": e_price, "sl": sl_price, "armed_bar": i, "mid_src": armed_src}

            if armed_bear and not np.isnan(armed_bear_low) and c0 < armed_bear_low and pending_zone is None and not in_position:
                armed_bear = False
                e_price = h0
                sl_price = (armed_sl if not np.isnan(armed_sl) else h1) + 0.50
                if sl_price > e_price:
                    risk_bps = ((sl_price - e_price) / e_price) * 10000.0
                    if min_risk_bps <= risk_bps <= max_risk_bps:
                        pending_zone = {"dir": -1, "entry_level": e_price, "sl": sl_price, "armed_bar": i, "mid_src": armed_src}

        return pd.DataFrame(trades)

    def analyze_mid_as_magnet_target(self) -> pd.DataFrame:
        """
        Analyzes when price sweeps an External Extreme (e.g. Asia Low, London Low, P12 Low, PDL),
        what is the empirical hit rate of price reaching the 50% Midline before hitting the opposite extreme.
        """
        n = self.n
        highs = self.highs
        lows = self.lows
        closes = self.closes
        times = self.times

        asia_h, asia_l, asia_m = self.asia_high, self.asia_low, self.asia_mid
        london_h, london_l, london_m = self.london_high, self.london_low, self.london_mid
        p12_h, p12_l, p12_m = self.p12_high, self.p12_low, self.p12_mid
        pdh, pdl, pdm = self.pdh, self.pdl, self.pdm

        tests = [
            ("Asia Range (18-02)", asia_h, asia_l, asia_m),
            ("London Range (02-08)", london_h, london_l, london_m),
            ("P12 Range (18-06)", p12_h, p12_l, p12_m),
            ("Previous Day Range", pdh, pdl, pdm),
        ]

        results = []
        for name, arr_h, arr_l, arr_m in tests:
            total_sweeps = 0
            mid_hits = 0
            opposing_extreme_hits = 0

            # Forward scan for magnet reach
            i = 25
            while i < n - 100:
                h0, l0 = highs[i], lows[i]
                cur_h, cur_l, cur_m = arr_h[i], arr_l[i], arr_m[i]

                if not np.isnan(cur_h) and not np.isnan(cur_l) and not np.isnan(cur_m):
                    # Case 1: Sweep Low -> Target Mid
                    if l0 < cur_l and closes[i] > cur_l:
                        total_sweeps += 1
                        # Forward look up to 72 bars (6 hours)
                        hit_mid = False
                        hit_opp = False
                        for f in range(1, min(72, n - i)):
                            if highs[i + f] >= cur_m:
                                hit_mid = True
                                break
                            if lows[i + f] < (cur_l - (cur_m - cur_l)):
                                break
                        for f in range(1, min(72, n - i)):
                            if highs[i + f] >= cur_h:
                                hit_opp = True
                                break
                        if hit_mid: mid_hits += 1
                        if hit_opp: opposing_extreme_hits += 1
                        i += 15
                        continue

                    # Case 2: Sweep High -> Target Mid
                    elif h0 > cur_h and closes[i] < cur_h:
                        total_sweeps += 1
                        hit_mid = False
                        hit_opp = False
                        for f in range(1, min(72, n - i)):
                            if lows[i + f] <= cur_m:
                                hit_mid = True
                                break
                            if highs[i + f] > (cur_h + (cur_h - cur_m)):
                                break
                        for f in range(1, min(72, n - i)):
                            if lows[i + f] <= cur_l:
                                hit_opp = True
                                break
                        if hit_mid: mid_hits += 1
                        if hit_opp: opposing_extreme_hits += 1
                        i += 15
                        continue
                i += 1

            results.append({
                "Structural Session Range": name,
                "Total External Sweeps": total_sweeps,
                "Mid (50%) Hit Count": mid_hits,
                "Mid Magnet Probability (%)": f"{(mid_hits / total_sweeps) * 100:.1f}%" if total_sweeps > 0 else "0.0%",
                "Full Range Expansion Reach (%)": f"{(opposing_extreme_hits / total_sweeps) * 100:.1f}%" if total_sweeps > 0 else "0.0%",
                "Median Move to Mid (bps)": f"{(np.nanmedian(np.abs(arr_h - arr_m) / arr_m)) * 10000:.1f} bps" if not np.isnan(arr_m).all() else "N/A",
            })

        return pd.DataFrame(results)


def main():
    print(f"\n{'='*95}", flush=True)
    print("STARTING MIDLINE (50% EQUILIBRIUM) CISD & MAGNET RESEARCH (NQ1 2022-2026)", flush=True)
    print("=" * 95, flush=True)

    data_path = _root / "data/NQ1_5m.parquet"
    df_nq = pd.read_parquet(data_path)
    if not isinstance(df_nq.index, pd.DatetimeIndex):
        df_nq["datetime"] = pd.to_datetime(df_nq["datetime"])
        df_nq.set_index("datetime", inplace=True)
    df_bench = df_nq[df_nq.index >= "2022-01-01"].copy()

    engine = MidlineCISDResearchEngine(df_bench)

    # 1. MIDLINE AS MAGNET / DRAW ON LIQUIDITY
    print("\n" + "─" * 95, flush=True)
    print("🎯 PART 1: 50% MIDLINES AS MAGNET / DRAW ON LIQUIDITY (From External Sweep to Mid)", flush=True)
    print("─" * 95, flush=True)
    magnet_df = engine.analyze_mid_as_magnet_target()
    print(magnet_df.to_string(index=False), flush=True)

    # 2. MIDLINE SWEEPS & CISD RECLAIM SETUPS
    print("\n" + "─" * 95, flush=True)
    print("⚡ PART 2: MIDLINE FALSE-BREAK SWEEP & CISD RECLAIM PERFORMANCE", flush=True)
    print("─" * 95, flush=True)
    mid_trades_df = engine.run_midline_sweep_simulation()
    print(f"Total Midline Reclaim Trades: {len(mid_trades_df):,}", flush=True)

    sources = [
        "Prev_Day_Mid (PDM)",
        "P12_Mid (Overnight 50%)",
        "Asia_Mid (50%)",
        "London_Mid (50%)",
    ]

    mid_summary = []
    for src in sources:
        sub = mid_trades_df[mid_trades_df["mid_source"] == src]
        if len(sub) == 0: continue
        wins = sub[sub["total_pnl_usd"] > 0]
        losses = sub[sub["total_pnl_usd"] < 0]
        gp = wins["total_pnl_usd"].sum()
        gl = abs(losses["total_pnl_usd"].sum())
        pf = gp / gl if gl > 0 else np.nan
        wr = (len(wins) / len(sub)) * 100.0

        mid_summary.append({
            "Midline Level": src,
            "Trades": len(sub),
            "Trade Share": f"{(len(sub)/len(mid_trades_df))*100:.1f}%",
            "Win Rate": f"{wr:.1f}%",
            "Profit Factor": f"{pf:.2f}" if not np.isnan(pf) else "N/A",
            "Net PnL ($)": f"${sub['total_pnl_usd'].sum():,.2f}",
            "Median MFE": f"{sub['mfe_bps'].median():.1f} bps",
            "Median MAE": f"{sub['mae_bps'].median():.1f} bps",
            "Queen (+10bps) Reach": f"{(sub['mfe_bps'] >= 10.0).sum() / len(sub) * 100:.1f}%",
            "Runner (+30bps) Reach": f"{(sub['mfe_bps'] >= 30.0).sum() / len(sub) * 100:.1f}%",
        })

    print(pd.DataFrame(mid_summary).to_string(index=False), flush=True)


if __name__ == "__main__":
    main()
