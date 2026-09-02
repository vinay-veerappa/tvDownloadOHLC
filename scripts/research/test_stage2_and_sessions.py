"""
========================================================================================
Advanced ICT Research: Stage 2 Distribution, 5m+1m Micro-Entry & Session Profiles
========================================================================================
1. Aspect A: Stage 1 (SMR / Turtle Soup) vs. Stage 2 (Low-Risk Buy/Sell)
2. Aspect B: Session Analysis:
   - NY RTH Session (09:45 - 15:30 ET)
   - London Killzone (02:00 - 05:00 ET) - Asian Range Sweep & Expansion
   - Asia Session (18:00 - 02:00 ET) - Range Accumulation
3. Aspect C: 1m Intrabar Micro-Entry Stop Compression (2.5-3.5 bps vs. 5.0 bps)
========================================================================================
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Tuple

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


def run_stage2_session_study(start_year: int = 2022) -> pd.DataFrame:
    print("Loading NQ1 5m parquet data for Stage 2 & Session study...", flush=True)
    df_5m = pd.read_parquet(_root / "data/NQ1_5m.parquet")
    df_5m = df_5m[df_5m.index >= f"{start_year}-01-01"].copy()

    if df_5m.index.tz is None:
        df_5m.index = df_5m.index.tz_localize("UTC").tz_convert("America/New_York")
    else:
        df_5m.index = df_5m.index.tz_convert("America/New_York")

    times = df_5m.index
    n = len(df_5m)

    o = df_5m["open"].to_numpy(dtype=np.float64)
    h = df_5m["high"].to_numpy(dtype=np.float64)
    l = df_5m["low"].to_numpy(dtype=np.float64)
    c = df_5m["close"].to_numpy(dtype=np.float64)

    # 4H EMA for HTF Orderflow
    df_4h = df_5m.resample("4h").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    df_4h["ema20"] = df_4h["close"].ewm(span=20).mean()
    df_4h_reindexed = df_4h.reindex(df_5m.index, method="ffill")
    htf_bias_arr = np.where(df_4h_reindexed["close"] > df_4h_reindexed["ema20"], 1, -1)

    time_strs = times.strftime("%H%M")
    hours = times.hour
    mins = times.minute

    # Tracking Sessions: Asia (18:00 - 02:00), London (02:00 - 05:00), NY (09:30 - 16:00)
    asia_high = np.nan
    asia_low = np.nan
    cur_asia_h = np.nan
    cur_asia_l = np.nan

    vibes = 0
    bagholder_entry = np.nan
    pain_threshold = np.nan

    def consult_crystal_ball(bias: int, idx: int):
        max_lb = min(15, idx)
        ext_o = o[idx - 1]
        for k in range(1, max_lb + 1):
            is_opp = (c[idx - k] < o[idx - k]) if bias == 1 else (c[idx - k] > o[idx - k])
            if is_opp:
                ext_o = o[idx - k]
                break
        return ext_o

    trades = []

    # Track Stage 1 SMR state to detect Stage 2 Distribution
    stage1_bull_active = False
    stage1_bull_bar = 0
    stage1_bull_disp_high = 0.0

    stage1_bear_active = False
    stage1_bear_bar = 0
    stage1_bear_disp_low = 0.0

    for i in range(50, n):
        t = times[i]
        hhmm = time_strs[i]
        h0, l0, c0, o0 = h[i], l[i], c[i], o[i]
        h2, l2 = h[i - 2], l[i - 2]
        hh = hours[i]
        mm = mins[i]

        # Session Categorization
        session = "OTHER"
        if "0945" <= hhmm <= "1530" and not ("1200" <= hhmm <= "1330"):
            session = "NY_RTH"
        elif "0200" <= hhmm <= "0500":
            session = "LONDON"
        elif hhmm >= "1800" or hhmm <= "0200":
            session = "ASIA"

        # Track Asian Range (18:00 - 02:00)
        if hhmm == "1800":
            cur_asia_h = h0
            cur_asia_l = l0
        elif (hhmm > "1800" or hhmm <= "0200") and not np.isnan(cur_asia_h):
            cur_asia_h = max(cur_asia_h, h0)
            cur_asia_l = min(cur_asia_l, l0)
        elif hhmm == "0205":
            asia_high = cur_asia_h
            asia_low = cur_asia_l

        # CISD Core Engine
        candle_pers = 1 if c0 > o0 else (-1 if c0 < o0 else 0)
        if vibes == 0:
            vibes = candle_pers if candle_pers != 0 else 1
            bagholder_entry = consult_crystal_ball(vibes, i)
            pain_threshold = h0 if vibes == 1 else l0

        if vibes == 1 and h0 > pain_threshold:
            pain_threshold = h0
            bagholder_entry = consult_crystal_ball(1, i)
        elif vibes == -1 and l0 < pain_threshold:
            pain_threshold = l0
            bagholder_entry = consult_crystal_ball(-1, i)

        active_lvl = bagholder_entry

        # ── 1. STAGE 1 (SMR / TURTLE SOUP) TRIGGER ──
        if vibes == -1 and c0 > active_lvl:
            vibes = 1
            pain_threshold = h0
            bagholder_entry = consult_crystal_ball(1, i)

            # Record Stage 1 SMR for Stage 2 tracking
            stage1_bull_active = True
            stage1_bull_bar = i
            stage1_bull_disp_high = h0

            # Record baseline Stage 1 trade
            if htf_bias_arr[i] == 1:
                fvg_top = h2 if l0 > h2 else active_lvl
                trades.append({
                    "bar_idx": i, "time": t, "session": session, "model": "Stage1_SMR",
                    "direction": "Long", "entry_price": fvg_top,
                    "stop_price": fvg_top - (fvg_top * 0.0005), # 5.0 bps
                    "tp1": fvg_top + (fvg_top * 0.0010),        # 10.0 bps (Queen)
                    "tp2": fvg_top + (fvg_top * 0.0030),        # 30.0 bps (Runner)
                })

        elif vibes == 1 and c0 < active_lvl:
            vibes = -1
            pain_threshold = l0
            bagholder_entry = consult_crystal_ball(-1, i)

            # Record Stage 1 SMR for Stage 2 tracking
            stage1_bear_active = True
            stage1_bear_bar = i
            stage1_bear_disp_low = l0

            # Record baseline Stage 1 trade
            if htf_bias_arr[i] == -1:
                fvg_bot = l2 if h0 < l2 else active_lvl
                trades.append({
                    "bar_idx": i, "time": t, "session": session, "model": "Stage1_SMR",
                    "direction": "Short", "entry_price": fvg_bot,
                    "stop_price": fvg_bot + (fvg_bot * 0.0005),
                    "tp1": fvg_bot - (fvg_bot * 0.0010),
                    "tp2": fvg_bot - (fvg_bot * 0.0030),
                })

        # ── 2. STAGE 2 DISTRIBUTION (LOW-RISK BUY / SELL) ──
        # Conditions for Stage 2:
        # After Stage 1 SMR: price displaces, creates a new swing high/low, then pulls back
        # into the secondary FVG / Discount zone between 3 and 12 bars later.
        if stage1_bull_active:
            bars_since = i - stage1_bull_bar
            if h0 > stage1_bull_disp_high:
                stage1_bull_disp_high = h0

            if 2 <= bars_since <= 12:
                # Stage 2 Pullback: price forms a bullish FVG after the initial displacement
                # and retraces into it with 4H trend support
                is_pullback_fvg = (l0 > h2) and (c0 < stage1_bull_disp_high)
                if is_pullback_fvg and htf_bias_arr[i] == 1:
                    # London Asia Sweep Bonus check
                    swept_asia = (session == "LONDON") and (not np.isnan(asia_low)) and (l0 < asia_low)
                    s2_entry = h2
                    s2_stop = s2_entry - (s2_entry * 0.00035)  # Compressed 3.5 bps micro-stop!
                    trades.append({
                        "bar_idx": i, "time": t, "session": session, "model": "Stage2_Distribution",
                        "direction": "Long", "entry_price": s2_entry,
                        "stop_price": s2_stop,
                        "tp1": s2_entry + (s2_entry * 0.0010),
                        "tp2": s2_entry + (s2_entry * 0.0030),
                        "swept_asia": swept_asia,
                    })
                    stage1_bull_active = False
            elif bars_since > 12:
                stage1_bull_active = False

        if stage1_bear_active:
            bars_since = i - stage1_bear_bar
            if l0 < stage1_bear_disp_low:
                stage1_bear_disp_low = l0

            if 2 <= bars_since <= 12:
                is_pullback_fvg = (h0 < l2) and (c0 > stage1_bear_disp_low)
                if is_pullback_fvg and htf_bias_arr[i] == -1:
                    swept_asia = (session == "LONDON") and (not np.isnan(asia_high)) and (h0 > asia_high)
                    s2_entry = l2
                    s2_stop = s2_entry + (s2_entry * 0.00035)  # Compressed 3.5 bps micro-stop!
                    trades.append({
                        "bar_idx": i, "time": t, "session": session, "model": "Stage2_Distribution",
                        "direction": "Short", "entry_price": s2_entry,
                        "stop_price": s2_stop,
                        "tp1": s2_entry - (s2_entry * 0.0010),
                        "tp2": s2_entry - (s2_entry * 0.0030),
                        "swept_asia": swept_asia,
                    })
                    stage1_bear_active = False
            elif bars_since > 12:
                stage1_bear_active = False

    # Simulate Outcomes for both models across future bars
    print(f"Evaluating outcomes for {len(trades):,d} candidate setups...", flush=True)
    evaluated = []
    for tr in trades:
        b_idx = tr["bar_idx"]
        direction = tr["direction"]
        entry = tr["entry_price"]
        sl = tr["stop_price"]
        tp1 = tr["tp1"]
        tp2 = tr["tp2"]

        # Search next 48 bars (4 hours)
        max_fwd = min(n, b_idx + 48)
        filled = False
        queen_hit = False
        runner_hit = False
        stopped_out = False
        active_sl = sl
        exit_price = entry

        for j in range(b_idx + 1, max_fwd):
            bh, bl, bc = h[j], l[j], c[j]

            if not filled:
                if direction == "Long" and bl <= entry:
                    filled = True
                elif direction == "Short" and bh >= entry:
                    filled = True
                if not filled and (j - b_idx) > 6:
                    break  # Order expired
                continue

            # In Position
            if direction == "Long":
                if not queen_hit and bh >= tp1:
                    queen_hit = True
                    active_sl = entry  # Move to Breakeven
                if bl <= active_sl:
                    stopped_out = True
                    exit_price = active_sl
                    break
                if bh >= tp2:
                    runner_hit = True
                    exit_price = tp2
                    break
            elif direction == "Short":
                if not queen_hit and bl <= tp1:
                    queen_hit = True
                    active_sl = entry
                if bh >= active_sl:
                    stopped_out = True
                    exit_price = active_sl
                    break
                if bl <= tp2:
                    runner_hit = True
                    exit_price = tp2
                    break

        if filled:
            # P&L Calculation with Cover The Queen
            if direction == "Long":
                q_pts = (tp1 - entry) if queen_hit else (exit_price - entry)
                r_pts = (exit_price - entry)
            else:
                q_pts = (entry - tp1) if queen_hit else (entry - exit_price)
                r_pts = (entry - exit_price)

            avg_pts = (q_pts + r_pts) / 2.0
            pnl_bps = (avg_pts / entry) * 10000.0

            tr_out = dict(tr)
            tr_out["filled"] = True
            tr_out["queen_hit"] = queen_hit
            tr_out["runner_hit"] = runner_hit
            tr_out["pnl_bps"] = pnl_bps
            tr_out["is_win"] = pnl_bps > 0
            evaluated.append(tr_out)

    df_out = pd.DataFrame(evaluated)
    return df_out


def main():
    print(f"\n{'='*125}", flush=True)
    print("EMPIRICAL ICT STUDY: STAGE 1 (SMR) vs. STAGE 2 DISTRIBUTION ACROSS SESSIONS", flush=True)
    print("=" * 125, flush=True)

    df = run_stage2_session_study(start_year=2022)

    # 1. Compare Stage 1 vs Stage 2 Overall
    print(f"\n1. STAGE 1 (SMR / TURTLE SOUP) vs. STAGE 2 (SECOND STAGE DISTRIBUTION)")
    print(f"─────────────────────────────────────────────────────────────────────────────")
    for model in ["Stage1_SMR", "Stage2_Distribution"]:
        sub = df[df["model"] == model]
        n = len(sub)
        wr = sub["is_win"].mean() * 100.0
        q_rate = sub["queen_hit"].mean() * 100.0
        r_rate = sub["runner_hit"].mean() * 100.0
        wins = sub[sub["pnl_bps"] > 0]["pnl_bps"].sum()
        losses = abs(sub[sub["pnl_bps"] < 0]["pnl_bps"].sum())
        pf = wins / losses if losses > 0 else np.nan
        exp = sub["pnl_bps"].mean()

        print(f"Model: {model:<23} | Trades: {n:4d} | Win Rate: {wr:4.1f}% | Queen Reach: {q_rate:4.1f}% | Runner: {r_rate:4.1f}% | PF: {pf:.2f} | Exp: {exp:+.2f} bps/tr")

    # 2. Session Performance Breakdown (NY vs London vs Asia)
    print(f"\n2. SESSION PERFORMANCE BREAKDOWN (STAGE 2 DISTRIBUTION)")
    print(f"─────────────────────────────────────────────────────────────────────────────")
    sub_s2 = df[df["model"] == "Stage2_Distribution"]
    for sess in ["NY_RTH", "LONDON", "ASIA"]:
        sub = sub_s2[sub_s2["session"] == sess]
        n = len(sub)
        if n == 0:
            continue
        wr = sub["is_win"].mean() * 100.0
        q_rate = sub["queen_hit"].mean() * 100.0
        r_rate = sub["runner_hit"].mean() * 100.0
        wins = sub[sub["pnl_bps"] > 0]["pnl_bps"].sum()
        losses = abs(sub[sub["pnl_bps"] < 0]["pnl_bps"].sum())
        pf = wins / losses if losses > 0 else np.nan
        exp = sub["pnl_bps"].mean()

        print(f"Session: {sess:<10} | Trades: {n:4d} | Win Rate: {wr:4.1f}% | Queen Reach: {q_rate:4.1f}% | Runner: {r_rate:4.1f}% | PF: {pf:.2f} | Exp: {exp:+.2f} bps/tr")

    # 3. London Asian Range Sweep Special Case
    print(f"\n3. LONDON SESSION: ASIAN RANGE SWEEP + STAGE 2 DISTRIBUTION")
    print(f"─────────────────────────────────────────────────────────────────────────────")
    london_trades = sub_s2[sub_s2["session"] == "LONDON"]
    for swept in [True, False]:
        sub = london_trades[london_trades.get("swept_asia", False) == swept]
        n = len(sub)
        if n == 0:
            continue
        wr = sub["is_win"].mean() * 100.0
        q_rate = sub["queen_hit"].mean() * 100.0
        wins = sub[sub["pnl_bps"] > 0]["pnl_bps"].sum()
        losses = abs(sub[sub["pnl_bps"] < 0]["pnl_bps"].sum())
        pf = wins / losses if losses > 0 else np.nan
        exp = sub["pnl_bps"].mean()
        label = "Swept Asia High/Low (Judas Trap)" if swept else "Normal London Stage 2"
        print(f"{label:<35} | Trades: {n:4d} | Win Rate: {wr:4.1f}% | Queen Reach: {q_rate:4.1f}% | PF: {pf:.2f} | Exp: {exp:+.2f} bps/tr")


if __name__ == "__main__":
    main()
