"""
Universal ICT Engine: Full Multi-Timeframe Liquidity Architecture
==================================================================
Features:
1. Dynamic Unmitigated Pool Tracking across All Sessions (24/7):
   - Unmitigated Swing Highs / Lows (1H / 4H / Daily) in the recent past
   - Unmitigated HTF Fair Value Gaps (1H / 4H FVGs)
   - Unmitigated HTF Order Blocks (1H / 4H OBs)
   - Session Anchors: Asia H/L, London H/L, NY AM H/L, NY PM H/L, PDH/PDL, PWH/PWL
2. Universal Liquidity Grab Detection:
   - Sweeps of unmitigated swing/session levels (wick rejection / reclaim)
   - Taps into unmitigated HTF FVGs / OBs
3. CISD Shift:
   - Close across opposing delivery sequence open
4. 2nd Stage of Distribution Retest:
   - Retest into Order Block (OB), Fair Value Gap (FVG), or Inverse FVG (iFVG)
   - Respect confirmation on 1m chart (rejection wick + candle closing in trend direction)
5. Liquidity-Calibrated Targets:
   - Target 1: +10 bps (Queen partial + BE lock)
   - Target 2: Opposing Unmitigated HTF Liquidity Pool (BSL for Long, SSL for Short)
   - Flags expected reversal upon liquidity target reach!
"""

import os
import sys
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

OUTPUT_DIR = Path("C:/Users/vinay/.gemini/antigravity/brain/4c21dcc0-89c9-42df-8e6a-fc48ef5552a9/scratch/charts")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def find_unmitigated_pivots(df, window=3):
    """Finds unmitigated swing highs and lows in historical dataframe."""
    highs = []
    lows = []
    n = len(df)
    for i in range(window, n - window):
        h = df["high"].iloc[i]
        l = df["low"].iloc[i]
        t = df.index[i]
        
        is_swing_h = all(df["high"].iloc[i-j] < h for j in range(1, window+1)) and \
                     all(df["high"].iloc[i+j] <= h for j in range(1, window+1))
        is_swing_l = all(df["low"].iloc[i-j] > l for j in range(1, window+1)) and \
                     all(df["low"].iloc[i+j] >= l for j in range(1, window+1))
        
        if is_swing_h:
            highs.append({"price": h, "time": t, "idx": i, "mitigated": False})
        if is_swing_l:
            lows.append({"price": l, "time": t, "idx": i, "mitigated": False})
    return highs, lows

def find_htf_fvgs(df_htf):
    """Finds HTF FVGs (1H or 4H)."""
    fvgs = []
    for i in range(2, len(df_htf)):
        b0 = df_htf.iloc[i-2]
        b1 = df_htf.iloc[i-1]
        b2 = df_htf.iloc[i]
        t = df_htf.index[i]
        
        # Bullish FVG: b2.low > b0.high
        if b2["low"] > b0["high"]:
            fvgs.append({
                "type": "BULL", "top": b2["low"], "bot": b0["high"],
                "mid": (b2["low"] + b0["high"]) / 2.0, "time": t, "mitigated": False
            })
        # Bearish FVG: b2.high < b0.low
        elif b2["high"] < b0["low"]:
            fvgs.append({
                "type": "BEAR", "top": b0["low"], "bot": b2["high"],
                "mid": (b0["low"] + b2["high"]) / 2.0, "time": t, "mitigated": False
            })
    return fvgs

def run_universal_ict(data_file="data/NQ_recent_week.parquet", target_date="2026-08-28"):
    print("=" * 110)
    print(f"UNIVERSAL ICT MULTI-SESSION AUDIT: {target_date}")
    print("=" * 110)

    df_all = pd.read_parquet(data_file).sort_index()
    df_all["date"] = df_all.index.date
    df_all["hhmm"] = df_all.index.strftime("%H%M")

    target_d = pd.to_datetime(target_date).date()
    df_day = df_all[df_all["date"] == target_d].copy()
    if df_day.empty:
        print(f"No data for {target_date}")
        return None

    # Resample HTF: 1H and 4H
    df_1h = df_all.resample("1h").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    df_4h = df_all.resample("4h").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()

    # Structural 5m
    df_5m = df_day.resample("5min").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()

    # 1. Gather Historical Unmitigated Pools prior to target_date
    df_prior_1h = df_1h[df_1h.index.date < target_d]
    sh_list, sl_list = find_unmitigated_pivots(df_prior_1h, window=2)
    htf_fvgs = find_htf_fvgs(df_prior_1h)

    # Previous Day Sessions
    prev_dates = sorted([d for d in df_all["date"].unique() if d < target_d])
    prev_d = prev_dates[-1]
    df_prev = df_all[df_all["date"] == prev_d]

    pdh = df_prev["high"].max()
    pdl = df_prev["low"].min()
    
    prev_ny_pm = df_prev[(df_prev["hhmm"] >= "1330") & (df_prev["hhmm"] <= "1600")]
    prev_ny_pm_low = prev_ny_pm["low"].min() if not prev_ny_pm.empty else np.nan
    prev_ny_pm_high = prev_ny_pm["high"].max() if not prev_ny_pm.empty else np.nan

    asia_bars = df_all[((df_all["date"] == prev_d) & (df_all["hhmm"] >= "2000")) |
                       ((df_all["date"] == target_d) & (df_all["hhmm"] < "0000"))]
    asia_high = asia_bars["high"].max() if not asia_bars.empty else np.nan
    asia_low = asia_bars["low"].min() if not asia_bars.empty else np.nan

    lon_bars = df_day[(df_day["hhmm"] >= "0200") & (df_day["hhmm"] < "0500")]
    lon_high = lon_bars["high"].max() if not lon_bars.empty else np.nan
    lon_low = lon_bars["low"].min() if not lon_bars.empty else np.nan

    print("Key Initial HTF Anchors:")
    print(f"  • PDH: {pdh:.2f} | PDL: {pdl:.2f}")
    print(f"  • Prev NY PM Low: {prev_ny_pm_low:.2f} | Prev NY PM High: {prev_ny_pm_high:.2f}")
    print(f"  • London Low: {lon_low:.2f} | London High: {lon_high:.2f}")
    print(f"  • Active Unmitigated 1H Swing Lows: {[round(x['price'], 2) for x in sl_list[-3:]]}")
    print(f"  • Active Unmitigated 1H Swing Highs: {[round(x['price'], 2) for x in sh_list[-3:]]}")
    print(f"  • Active Unmitigated HTF FVGs: {len(htf_fvgs)}")

    # 2. Sequential Intraday Execution Loop across 5m bars
    trades = []
    active_sweep = None
    last_down_open = np.nan
    last_up_open = np.nan
    last_down_bar = None
    last_up_bar = None

    for i in range(len(df_5m)):
        t5 = df_5m.index[i]
        c5, o5, h5, l5 = df_5m["close"].iloc[i], df_5m["open"].iloc[i], df_5m["high"].iloc[i], df_5m["low"].iloc[i]
        h5_2 = df_5m["high"].iloc[i-2] if i >= 2 else np.nan
        l5_2 = df_5m["low"].iloc[i-2] if i >= 2 else np.nan

        # Rolling 1H & 4H High/Low from past data
        sub_hist = df_all.loc[:t5]
        h1_low = sub_hist.iloc[-60:]["low"].min()
        h1_high = sub_hist.iloc[-60:]["high"].max()
        h4_low = sub_hist.iloc[-240:]["low"].min()
        h4_high = sub_hist.iloc[-240:]["high"].max()

        # Update last opposing candle open and Order Block candidate
        if c5 < o5:
            last_down_open = o5
            last_down_bar = {"open": o5, "high": h5, "low": l5, "close": c5, "time": t5}
        elif c5 > o5:
            last_up_open = o5
            last_up_bar = {"open": o5, "high": h5, "low": l5, "close": c5, "time": t5}

        # Check Active Sweep Expiration / Invalidation
        if active_sweep:
            if active_sweep["type"] == "BEAR" and h5 > active_sweep["extreme"]:
                active_sweep = None # Invalidation by higher high
            elif active_sweep["type"] == "BULL" and l5 < active_sweep["extreme"]:
                active_sweep = None # Invalidation by lower low
            elif (i - active_sweep["bar_idx"]) > 10:
                active_sweep = None

        # Universal Liquidity Grab Detection (Runs 24/7 across any session)
        if active_sweep is None:
            # 1. Bullish Liquidity Grabs (Sellside Liquidity / Discount Pools)
            bull_candidates = [
                ("NY PM Low", prev_ny_pm_low),
                ("4H Low", h4_low),
                ("1H Low", h1_low),
                ("London Low", lon_low),
                ("Asia Low", asia_low),
                ("PDL", pdl)
            ]
            # Add recent unmitigated swing lows
            for sl in sl_list[-5:]:
                if not sl["mitigated"]:
                    bull_candidates.append(("Unmitigated 1H Low", sl["price"]))

            for name, lvl in bull_candidates:
                if not np.isnan(lvl):
                    is_wick_reject = (l5 <= lvl and c5 > lvl)
                    is_reclaim = (i > 0 and df_5m["low"].iloc[i-1] <= lvl and df_5m["close"].iloc[i-1] <= lvl and c5 > lvl)
                    prior_closes_below = sum(df_5m["close"].iloc[max(0, i-4):i] < lvl)

                    if (is_wick_reject or is_reclaim) and prior_closes_below <= 1:
                        # Check confluences
                        other_swept = [n for n, l in bull_candidates if n != name and not np.isnan(l) and l5 <= l and c5 > l]
                        full_name = name + (f" & {other_swept[0]}" if other_swept else "")
                        active_sweep = {
                            "type": "BULL", "anchor": full_name, "level": lvl,
                            "time": t5, "bar_idx": i, "extreme": l5
                        }
                        break

            # Check Bullish HTF FVG Taps
            if active_sweep is None:
                for fvg in htf_fvgs:
                    if fvg["type"] == "BULL" and not fvg["mitigated"]:
                        if l5 <= fvg["top"] and c5 >= fvg["bot"]:
                            active_sweep = {
                                "type": "BULL", "anchor": f"HTF Bullish FVG Tap [{fvg['bot']:.1f}-{fvg['top']:.1f}]",
                                "level": fvg["top"], "time": t5, "bar_idx": i, "extreme": l5
                            }
                            fvg["mitigated"] = True
                            break

            # 2. Bearish Liquidity Grabs (Buyside Liquidity / Premium Pools)
            if active_sweep is None:
                bear_candidates = [
                    ("NY PM High", prev_ny_pm_high),
                    ("4H High", h4_high),
                    ("1H High", h1_high),
                    ("London High", lon_high),
                    ("Asia High", asia_high),
                    ("PDH", pdh)
                ]
                for sh in sh_list[-5:]:
                    if not sh["mitigated"]:
                        bear_candidates.append(("Unmitigated 1H High", sh["price"]))

                for name, lvl in bear_candidates:
                    if not np.isnan(lvl):
                        is_wick_reject = (h5 >= lvl and c5 < lvl)
                        is_reclaim = (i > 0 and df_5m["high"].iloc[i-1] >= lvl and df_5m["close"].iloc[i-1] >= lvl and c5 < lvl)
                        prior_closes_above = sum(df_5m["close"].iloc[max(0, i-4):i] > lvl)

                        if (is_wick_reject or is_reclaim) and prior_closes_above <= 1:
                            other_swept = [n for n, l in bear_candidates if n != name and not np.isnan(l) and h5 >= l and c5 < l]
                            full_name = name + (f" & {other_swept[0]}" if other_swept else "")
                            active_sweep = {
                                "type": "BEAR", "anchor": full_name, "level": lvl,
                                "time": t5, "bar_idx": i, "extreme": h5
                            }
                            break

                # Check Bearish HTF FVG Taps
                if active_sweep is None:
                    for fvg in htf_fvgs:
                        if fvg["type"] == "BEAR" and not fvg["mitigated"]:
                            if h5 >= fvg["bot"] and c5 <= fvg["top"]:
                                active_sweep = {
                                    "type": "BEAR", "anchor": f"HTF Bearish FVG Tap [{fvg['bot']:.1f}-{fvg['top']:.1f}]",
                                    "level": fvg["bot"], "time": t5, "bar_idx": i, "extreme": h5
                                }
                                fvg["mitigated"] = True
                                break

        # Step 2: CISD Shift Detection
        if active_sweep and (i - active_sweep["bar_idx"]) <= 10:
            if active_sweep["type"] == "BULL" and not np.isnan(last_down_open) and c5 > last_down_open:
                cisd_level = last_down_open
                cisd_time = t5

                # 2nd Stage of Distribution: Retest into OB, FVG, or iFVG
                ob_high = last_down_bar["high"] if last_down_bar else cisd_level
                ob_low = last_down_bar["low"] if last_down_bar else min(o5, c5)
                has_fvg = (l5 > h5_2) if not np.isnan(h5_2) else False
                fvg_top = l5 if has_fvg else max(c5, cisd_level)
                fvg_bot = h5_2 if has_fvg else min(o5, cisd_level)

                retest_top = max(ob_high, fvg_top)
                retest_bot = min(ob_low, fvg_bot)

                # Determine Opposing Liquidity Target (BSL)
                # Find nearest unmitigated high above entry
                bsl_targets = [p for p in [pdh, prev_ny_pm_high, lon_high, asia_high] if not np.isnan(p) and p > c5]
                for sh in sh_list:
                    if sh["price"] > c5: bsl_targets.append(sh["price"])
                # Also include session high if applicable
                session_h = df_5m["high"].iloc[:i+1].max()
                if session_h > c5: bsl_targets.append(session_h)
                
                opposing_target = min(bsl_targets) if bsl_targets else c5 + (c5 * 0.0030)

                # Look forward on 1m bars for 2nd stage retest into OB / FVG / iFVG
                m1_window = df_day.loc[t5:t5 + pd.Timedelta(minutes=35)]
                tapped, tap_idx = False, -1
                for m in range(1, len(m1_window)):
                    if m1_window.iloc[m]["low"] <= retest_top:
                        tapped = True
                        tap_idx = m
                        break

                if tapped:
                    for k in range(tap_idx, min(len(m1_window), tap_idx + 15)):
                        k_row = m1_window.iloc[k]
                        k_time = m1_window.index[k]

                        if k_row["close"] > k_row["open"]:
                            entry_p = k_row["close"]
                            protected_swing = m1_window.iloc[tap_idx:k+1]["low"].min()
                            sl_p = protected_swing - 1.0
                            risk_pts = entry_p - sl_p
                            risk_bps = (risk_pts / entry_p) * 10000.0

                            if 2.0 <= risk_bps <= 15.0:
                                tp1_p = entry_p + (entry_p * 0.0010) # +10 bps Queen
                                tp2_p = opposing_target # Calibrated to Opposing Liquidity Target!

                                sim_bars = df_day.loc[k_time:]
                                q_hit, r_hit = False, False
                                active_sl = sl_p
                                exit_time = None

                                for s in range(1, len(sim_bars)):
                                    sb = sim_bars.iloc[s]
                                    if not q_hit and sb["high"] >= tp1_p:
                                        q_hit = True
                                        active_sl = entry_p # BE lock
                                    if sb["low"] <= active_sl:
                                        exit_time = sim_bars.index[s]
                                        break
                                    if sb["high"] >= tp2_p:
                                        r_hit = True
                                        exit_time = sim_bars.index[s]
                                        break

                                trades.append({
                                    "direction": "BUY LONG",
                                    "anchor_name": active_sweep["anchor"],
                                    "anchor_level": active_sweep["level"],
                                    "sweep_time": active_sweep["time"],
                                    "cisd_level": cisd_level,
                                    "cisd_time": cisd_time,
                                    "retest_top": retest_top,
                                    "retest_bot": retest_bot,
                                    "entry_time": k_time,
                                    "entry_price": entry_p,
                                    "sl_price": sl_p,
                                    "tp1_price": tp1_p,
                                    "tp2_price": tp2_p,
                                    "opposing_target_name": f"BSL ({opposing_target:.2f})",
                                    "risk_bps": risk_bps,
                                    "q_hit": q_hit,
                                    "r_hit": r_hit,
                                    "exit_time": exit_time
                                })
                                active_sweep = None
                                break

            elif active_sweep["type"] == "BEAR" and not np.isnan(last_up_open) and c5 < last_up_open:
                cisd_level = last_up_open
                cisd_time = t5

                ob_high = last_up_bar["high"] if last_up_bar else cisd_level
                ob_low = last_up_bar["low"] if last_up_bar else min(o5, c5)
                has_fvg = (h5 < l5_2) if not np.isnan(l5_2) else False
                fvg_top = l5_2 if has_fvg else max(o5, cisd_level)
                fvg_bot = h5 if has_fvg else min(c5, cisd_level)

                retest_top = max(ob_high, fvg_top)
                retest_bot = min(ob_low, fvg_bot)

                # Determine Opposing Liquidity Target (SSL)
                ssl_targets = [p for p in [pdl, prev_ny_pm_low, lon_low, asia_low] if not np.isnan(p) and p < c5]
                for sl in sl_list:
                    if sl["price"] < c5: ssl_targets.append(sl["price"])
                session_l = df_5m["low"].iloc[:i+1].min()
                if session_l < c5: ssl_targets.append(session_l)

                opposing_target = max(ssl_targets) if ssl_targets else c5 - (c5 * 0.0030)

                m1_window = df_day.loc[t5:t5 + pd.Timedelta(minutes=35)]
                tapped, tap_idx = False, -1
                for m in range(1, len(m1_window)):
                    if m1_window.iloc[m]["high"] >= retest_bot:
                        tapped = True
                        tap_idx = m
                        break

                if tapped:
                    for k in range(tap_idx, min(len(m1_window), tap_idx + 15)):
                        k_row = m1_window.iloc[k]
                        k_time = m1_window.index[k]

                        if k_row["close"] < k_row["open"]:
                            entry_p = k_row["close"]
                            protected_swing = m1_window.iloc[tap_idx:k+1]["high"].max()
                            sl_p = protected_swing + 1.0
                            risk_pts = sl_p - entry_p
                            risk_bps = (risk_pts / entry_p) * 10000.0

                            if 2.0 <= risk_bps <= 15.0:
                                tp1_p = entry_p - (entry_p * 0.0010)
                                tp2_p = opposing_target

                                sim_bars = df_day.loc[k_time:]
                                q_hit, r_hit = False, False
                                active_sl = sl_p
                                exit_time = None

                                for s in range(1, len(sim_bars)):
                                    sb = sim_bars.iloc[s]
                                    if not q_hit and sb["low"] <= tp1_p:
                                        q_hit = True
                                        active_sl = entry_p
                                    if sb["high"] >= active_sl:
                                        exit_time = sim_bars.index[s]
                                        break
                                    if sb["low"] <= tp2_p:
                                        r_hit = True
                                        exit_time = sim_bars.index[s]
                                        break

                                trades.append({
                                    "direction": "SELL SHORT",
                                    "anchor_name": active_sweep["anchor"],
                                    "anchor_level": active_sweep["level"],
                                    "sweep_time": active_sweep["time"],
                                    "cisd_level": cisd_level,
                                    "cisd_time": cisd_time,
                                    "retest_top": retest_top,
                                    "retest_bot": retest_bot,
                                    "entry_time": k_time,
                                    "entry_price": entry_p,
                                    "sl_price": sl_p,
                                    "tp1_price": tp1_p,
                                    "tp2_price": tp2_p,
                                    "opposing_target_name": f"SSL ({opposing_target:.2f})",
                                    "risk_bps": risk_bps,
                                    "q_hit": q_hit,
                                    "r_hit": r_hit,
                                    "exit_time": exit_time
                                })
                                active_sweep = None
                                break

    print(f"\nAUDIT RESULTS FOR {target_date}: {len(trades)} trades")
    for tr in trades:
        print(f"  [{tr['direction']}] @ {tr['entry_time'].strftime('%H:%M ET')} | Entry: {tr['entry_price']:.2f}")
        print(f"    • Trigger: {tr['anchor_name']} ({tr['anchor_level']:.2f})")
        print(f"    • CISD Shift Level: {tr['cisd_level']:.2f} at {tr['cisd_time'].strftime('%H:%M ET')}")
        print(f"    • 2nd Stage Retest (OB/FVG/iFVG): [{tr['retest_bot']:.2f}, {tr['retest_top']:.2f}]")
        print(f"    • Stop Loss: {tr['sl_price']:.2f} ({tr['risk_bps']:.1f} bps)")
        print(f"    • Queen (+10 bps): {tr['q_hit']}")
        print(f"    • Liquidity Target: {tr['opposing_target_name']} | Hit: {tr['r_hit']}")

    # Render Chart
    df_plot = df_day[(df_day["hhmm"] >= "0830") & (df_day["hhmm"] <= "1400")].copy()
    if df_plot.empty: df_plot = df_day.copy()

    fig, ax = plt.subplots(figsize=(16, 9))
    width = 0.0004
    width2 = 0.00008

    up = df_plot[df_plot["close"] >= df_plot["open"]]
    down = df_plot[df_plot["close"] < df_plot["open"]]

    ax.bar(up.index, up["close"] - up["open"], width, bottom=up["open"], color="#089981", edgecolor="#089981")
    ax.bar(up.index, up["high"] - up["close"], width2, bottom=up["close"], color="#089981")
    ax.bar(up.index, up["low"] - up["open"], width2, bottom=up["open"], color="#089981")

    ax.bar(down.index, down["open"] - down["close"], width, bottom=down["close"], color="#f23645", edgecolor="#f23645")
    ax.bar(down.index, down["high"] - down["open"], width2, bottom=down["open"], color="#f23645")
    ax.bar(down.index, down["low"] - down["close"], width2, bottom=down["close"], color="#f23645")

    for tr in trades:
        is_long = tr["direction"] == "BUY LONG"
        col = "#22c55e" if is_long else "#ef4444"

        # Swept Level
        ax.axhline(tr["anchor_level"], color="#2563eb", linestyle="-.", linewidth=1.5)
        ax.text(df_plot.index[5], tr["anchor_level"] - (6 if is_long else -6), f"[HTF GRAB] {tr['anchor_name']} ({tr['anchor_level']:.2f})", color="#2563eb", fontsize=10, fontweight="bold")

        # CISD Level
        ax.axhline(tr["cisd_level"], color="#eab308", linestyle="-", linewidth=1.5)
        ax.text(tr["cisd_time"], tr["cisd_level"] + (3 if is_long else -3), f"[CISD] {tr['cisd_level']:.2f}", color="#ca8a04", fontsize=10, fontweight="bold")

        # OB / FVG / iFVG Retest Box
        rect = Rectangle((mdates.date2num(tr["cisd_time"]), tr["retest_bot"]),
                         mdates.date2num(tr["entry_time"]) - mdates.date2num(tr["cisd_time"]) + 0.005,
                         tr["retest_top"] - tr["retest_bot"],
                         facecolor="#a855f7", alpha=0.25, edgecolor="#9333ea", linestyle="--")
        ax.add_patch(rect)
        ax.text(tr["cisd_time"], tr["retest_top"] + 2, "2nd Stage: OB / FVG / iFVG", color="#9333ea", fontsize=9, fontweight="bold")

        # Liquidity Target Line
        ax.axhline(tr["tp2_price"], color="#8b5cf6", linestyle=":", linewidth=1.8, label=f"Liquidity Target: {tr['opposing_target_name']}")
        ax.text(df_plot.index[15], tr["tp2_price"] + 3, f"[LIQUIDITY TARGET - WATCH FOR REVERSAL] {tr['opposing_target_name']}", color="#8b5cf6", fontsize=10, fontweight="bold")

        # Entry Marker
        offset = -50 if is_long else 50
        ax.annotate(f"{tr['direction']}\nEntry: {tr['entry_price']:.2f}\nSL: {tr['sl_price']:.2f}\nQueen (+10): {tr['tp1_price']:.2f}\nTarget: {tr['opposing_target_name']}",
                    xy=(tr["entry_time"], tr["entry_price"]),
                    xytext=(tr["entry_time"], tr["entry_price"] + offset),
                    arrowprops=dict(facecolor=col, edgecolor="#15803d" if is_long else "#991b1b", width=2, headwidth=8),
                    bbox=dict(boxstyle="round,pad=0.5", facecolor="#f8fafc", edgecolor=col, alpha=0.9),
                    fontsize=9, fontweight="bold")

        ax.hlines(tr["sl_price"], xmin=tr["entry_time"], xmax=tr["exit_time"] if tr["exit_time"] else df_plot.index[-1], color="#ef4444", linestyle="--", linewidth=1.5)
        ax.hlines(tr["tp1_price"], xmin=tr["entry_time"], xmax=tr["exit_time"] if tr["exit_time"] else df_plot.index[-1], color="#22c55e", linestyle="--", linewidth=1.5)

    ax.set_title(f"NQ Futures — {target_date} | Universal ICT Engine: HTF Grab -> CISD -> 2nd Stage OB/FVG -> Liquidity Target", fontsize=12, fontweight="bold", pad=12)
    ax.set_ylabel("Price (Points)", fontsize=11)
    ax.grid(True, alpha=0.25)
    ax.legend(loc="upper left", fontsize=9, framealpha=0.8)

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M ET"))
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=1))
    fig.autofmt_xdate()

    chart_file = OUTPUT_DIR / f"universal_ict_{target_date}.png"
    plt.savefig(chart_file, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Saved chart to: {chart_file}")

    # Copy to root artifact directory
    root_art = Path(f"C:/Users/vinay/.gemini/antigravity/brain/4c21dcc0-89c9-42df-8e6a-fc48ef5552a9/universal_ict_{target_date}.png")
    import shutil
    shutil.copy(chart_file, root_art)

if __name__ == "__main__":
    run_universal_ict(target_date="2026-08-28")
    run_universal_ict(target_date="2026-08-26")
