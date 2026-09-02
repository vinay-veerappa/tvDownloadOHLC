"""
========================================================================================
5m Structure + 1m Precision Entry Backtest
========================================================================================
Tests:
1. 5m chart confirms the 4H Trend + 5m CISD
2. Instead of entering at 5m FVG with 5.0 bps stop:
   - Drop to 1m chart
   - Enter on the FIRST 1-minute FVG retest inside the 5m displacement
   - Micro-stop: placed behind the 1m swing invalidation (typically 2.0 to 3.0 bps!)
3. Compare Win Rate, Profit Factor, and Risk-Reward vs 5m baseline.
========================================================================================
"""

from __future__ import annotations

import sys
from pathlib import Path

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


def run_5m_1m_mtf_study(start_year: int = 2023) -> pd.DataFrame:
    print("Loading 1m and 5m parquet data for MTF 5m+1m study...", flush=True)
    df_1m = pd.read_parquet(_root / "data/NQ1_1m.parquet")
    df_1m = df_1m[df_1m.index >= f"{start_year}-01-01"].copy()

    if df_1m.index.tz is None:
        df_1m.index = df_1m.index.tz_localize("UTC").tz_convert("America/New_York")
    else:
        df_1m.index = df_1m.index.tz_convert("America/New_York")

    # Resample to 5m
    df_5m = df_1m.resample("5min").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()

    # 4H EMA
    df_4h = df_5m.resample("4h").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    df_4h["ema20"] = df_4h["close"].ewm(span=20).mean()
    df_4h_reindexed = df_4h.reindex(df_5m.index, method="ffill")
    htf_bias_arr = np.where(df_4h_reindexed["close"] > df_4h_reindexed["ema20"], 1, -1)

    # 5m CISD signals
    times_5m = df_5m.index
    n_5m = len(df_5m)
    c5 = df_5m["close"].to_numpy()
    o5 = df_5m["open"].to_numpy()
    h5 = df_5m["high"].to_numpy()
    l5 = df_5m["low"].to_numpy()
    time_strs_5m = times_5m.strftime("%H%M")

    vibes = 0
    bagholder_entry = np.nan
    pain_threshold = np.nan

    def consult_crystal_ball_5m(bias: int, idx: int):
        max_lb = min(15, idx)
        ext_o = o5[idx - 1]
        for k in range(1, max_lb + 1):
            is_opp = (c5[idx - k] < o5[idx - k]) if bias == 1 else (c5[idx - k] > o5[idx - k])
            if is_opp:
                ext_o = o5[idx - k]
                break
        return ext_o

    sig_5m_events = []

    for i in range(50, n_5m):
        t = times_5m[i]
        hhmm = time_strs_5m[i]
        c0, o0, h0, l0 = c5[i], o5[i], h5[i], l5[i]

        candle_pers = 1 if c0 > o0 else (-1 if c0 < o0 else 0)
        if vibes == 0:
            vibes = candle_pers if candle_pers != 0 else 1
            bagholder_entry = consult_crystal_ball_5m(vibes, i)
            pain_threshold = h0 if vibes == 1 else l0

        if vibes == 1 and h0 > pain_threshold:
            pain_threshold = h0
            bagholder_entry = consult_crystal_ball_5m(1, i)
        elif vibes == -1 and l0 < pain_threshold:
            pain_threshold = l0
            bagholder_entry = consult_crystal_ball_5m(-1, i)

        active_lvl = bagholder_entry
        in_time = ("0945" <= hhmm <= "1530") and not ("1200" <= hhmm <= "1330")

        if vibes == -1 and c0 > active_lvl and in_time:
            vibes = 1
            pain_threshold = h0
            bagholder_entry = consult_crystal_ball_5m(1, i)
            if htf_bias_arr[i] == 1:
                sig_5m_events.append({"time": t, "dir": 1, "c5": c0})

        elif vibes == 1 and c0 < active_lvl and in_time:
            vibes = -1
            pain_threshold = l0
            bagholder_entry = consult_crystal_ball_5m(-1, i)
            if htf_bias_arr[i] == -1:
                sig_5m_events.append({"time": t, "dir": -1, "c5": c0})

    print(f"Total 5m CISD events detected: {len(sig_5m_events):,d}", flush=True)

    # Now drop to 1m data for execution!
    # For each 5m CISD event: look for the 1st 1m FVG that forms in the next 15 minutes (15 1m bars)
    times_1m = df_1m.index
    c1 = df_1m["close"].to_numpy()
    o1 = df_1m["open"].to_numpy()
    h1 = df_1m["high"].to_numpy()
    l1 = df_1m["low"].to_numpy()
    n_1m = len(df_1m)

    trades_5m_baseline = []
    trades_1m_mtf = []

    for ev in sig_5m_events:
        t_event = ev["time"]
        direction = ev["dir"]

        # Find 1m bar corresponding to this 5m bar close
        idx_1m = times_1m.searchsorted(t_event)
        if idx_1m >= n_1m - 60:
            continue

        # ── 1. Baseline 5m Entry: Enter at 5m Close, 5.0 bps stop ──
        base_entry = c1[idx_1m]
        base_sl = base_entry - (base_entry * 0.0005) if direction == 1 else base_entry + (base_entry * 0.0005)
        base_tp1 = base_entry + (base_entry * 0.0010) if direction == 1 else base_entry - (base_entry * 0.0010)
        base_tp2 = base_entry + (base_entry * 0.0030) if direction == 1 else base_entry - (base_entry * 0.0030)

        # Simulate baseline 5m
        q_hit = False
        r_hit = False
        active_sl = base_sl
        exit_p = base_entry
        for k in range(idx_1m + 1, min(n_1m, idx_1m + 180)):
            bh, bl = h1[k], l1[k]
            if direction == 1:
                if not q_hit and bh >= base_tp1:
                    q_hit = True
                    active_sl = base_entry
                if bl <= active_sl:
                    exit_p = active_sl
                    break
                if bh >= base_tp2:
                    r_hit = True
                    exit_p = base_tp2
                    break
            else:
                if not q_hit and bl <= base_tp1:
                    q_hit = True
                    active_sl = base_entry
                if bh >= active_sl:
                    exit_p = active_sl
                    break
                if bl <= base_tp2:
                    r_hit = True
                    exit_p = base_tp2
                    break

        q_pts = (base_tp1 - base_entry) if q_hit else (exit_p - base_entry if direction == 1 else base_entry - exit_p)
        r_pts = (exit_p - base_entry) if direction == 1 else (base_entry - exit_p)
        pnl_bps = ((q_pts + r_pts) / 2.0 / base_entry) * 10000.0
        trades_5m_baseline.append({"pnl_bps": pnl_bps, "is_win": pnl_bps > 0, "q_hit": q_hit, "r_hit": r_hit})

        # ── 2. MTF 1m Entry: Find 1st 1m FVG in next 12 bars ──
        # Micro-stop: 2.5 bps (slashed risk!)
        found_1m_fvg = False
        for k in range(idx_1m + 2, min(n_1m, idx_1m + 15)):
            if direction == 1 and (l1[k] > h1[k - 2]):  # 1m Bullish FVG
                entry_1m = h1[k - 2]
                sl_1m = entry_1m - (entry_1m * 0.00025)  # 2.5 bps micro-stop!
                tp1_1m = entry_1m + (entry_1m * 0.0010)   # 10.0 bps (4:1 R:R!)
                tp2_1m = entry_1m + (entry_1m * 0.0030)   # 30.0 bps (12:1 R:R!)
                found_1m_fvg = True
                break
            elif direction == -1 and (h1[k] < l1[k - 2]):  # 1m Bearish FVG
                entry_1m = l1[k - 2]
                sl_1m = entry_1m + (entry_1m * 0.00025)  # 2.5 bps micro-stop!
                tp1_1m = entry_1m - (entry_1m * 0.0010)
                tp2_1m = entry_1m - (entry_1m * 0.0030)
                found_1m_fvg = True
                break

        if found_1m_fvg:
            q_hit_1m = False
            r_hit_1m = False
            active_sl_1m = sl_1m
            exit_p_1m = entry_1m
            for m in range(k + 1, min(n_1m, k + 180)):
                bh, bl = h1[m], l1[m]
                if direction == 1:
                    if not q_hit_1m and bh >= tp1_1m:
                        q_hit_1m = True
                        active_sl_1m = entry_1m
                    if bl <= active_sl_1m:
                        exit_p_1m = active_sl_1m
                        break
                    if bh >= tp2_1m:
                        r_hit_1m = True
                        exit_p_1m = tp2_1m
                        break
                else:
                    if not q_hit_1m and bl <= tp1_1m:
                        q_hit_1m = True
                        active_sl_1m = entry_1m
                    if bh >= active_sl_1m:
                        exit_p_1m = active_sl_1m
                        break
                    if bl <= tp2_1m:
                        r_hit_1m = True
                        exit_p_1m = tp2_1m
                        break

            q_pts_1m = (tp1_1m - entry_1m) if q_hit_1m else (exit_p_1m - entry_1m if direction == 1 else entry_1m - exit_p_1m)
            r_pts_1m = (exit_p_1m - entry_1m) if direction == 1 else (entry_1m - exit_p_1m)
            pnl_bps_1m = ((q_pts_1m + r_pts_1m) / 2.0 / entry_1m) * 10000.0
            trades_1m_mtf.append({"pnl_bps": pnl_bps_1m, "is_win": pnl_bps_1m > 0, "q_hit": q_hit_1m, "r_hit": r_hit_1m})

    df_base = pd.DataFrame(trades_5m_baseline)
    df_mtf = pd.DataFrame(trades_1m_mtf)

    return df_base, df_mtf


def main():
    print(f"\n{'='*125}", flush=True)
    print("EMPIRICAL COMPARISON: 5m BASELINE vs. 5m STRUCTURE + 1m PRECISION ENTRY", flush=True)
    print("=" * 125, flush=True)

    df_base, df_mtf = run_5m_1m_mtf_study(start_year=2023)

    def calc_stats(df, label, stop_bps):
        n = len(df)
        wr = df["is_win"].mean() * 100.0
        q_rate = df["q_hit"].mean() * 100.0
        r_rate = df["r_hit"].mean() * 100.0
        wins = df[df["pnl_bps"] > 0]["pnl_bps"].sum()
        losses = abs(df[df["pnl_bps"] < 0]["pnl_bps"].sum())
        pf = wins / losses if losses > 0 else np.nan
        exp = df["pnl_bps"].mean()
        # Risk Reward on Target 1
        rr_t1 = 10.0 / stop_bps
        print(f"Model: {label:<32} | Stop: {stop_bps:.1f}bps | Trades: {n:4d} | Win Rate: {wr:4.1f}% | Queen: {q_rate:4.1f}% | Runner: {r_rate:4.1f}% | Target 1 R:R: {rr_t1:3.1f}:1 | PF: {pf:.2f} | Exp: {exp:+.2f} bps/tr")

    print("\n--- RESULTS ---")
    calc_stats(df_base, "5m Baseline (5.0 bps stop)", 5.0)
    calc_stats(df_mtf, "5m Structure + 1m FVG Entry", 2.5)


if __name__ == "__main__":
    main()
