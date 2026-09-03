"""
Canonical ICT HTF-to-LTF Execution Engine
==========================================
Architecture:
1. Continuous HTF Liquidity Tracking across 24 Hours:
   - Previous Day High / Low (PDH / PDL)
   - Previous Week High / Low (PWH / PWL)
   - Previous Day NY PM High / Low (13:30 - 16:00 ET)
   - Previous Day NY AM High / Low (09:30 - 12:00 ET)
   - Asia High / Low (20:00 - 00:00 ET)
   - London High / Low (02:00 - 05:00 ET)
   - Rolling 4-Hour High / Low (4H High / Low)
   - Rolling 1-Hour High / Low (1H High / Low)
   - Session Opens (NY Open 09:30 ET / 08:30 CT, Midnight Open)

2. HTF Liquidity Grab (Can occur at ANY time):
   - Price pierces an HTF pool with wick rejection or immediate reclaim without multi-candle acceptance outside.
   - Tags the exact HTF pool name and price.

3. CISD Shift (Change in State of Delivery) on Structural 5m/15m:
   - Close across the opposing sequence open (last down-candle open for Bull, last up-candle open for Bear).
   - Invalidation: Price trading beyond sweep extreme resets the sweep.

4. 2nd Stage of Distribution (Retracement into OB & iFVG):
   - Defines the Order Block (OB) and Inverse Fair Value Gap (iFVG) created during displacement.
   - 1-minute price pulls back into the OB/iFVG zone ("Let the wick form").
   - 1-minute candle rejects and closes in trend direction -> ENTRY!
   - Stop placed at protected swing extreme.
   - Target 1: Queen (+10 bps, move stop to BE), Target 2: Runner (+30 bps or opposing HTF liquidity).
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

def run_canonical_audit(target_date="2026-08-28"):
    print("=" * 110)
    print(f"CANONICAL ICT HTF-TO-LTF AUDIT: {target_date}")
    print("=" * 110)

    data_file = "data/NQ_recent_week.parquet"
    df_all = pd.read_parquet(data_file)
    df_all["date"] = df_all.index.date
    df_all["hhmm"] = df_all.index.strftime("%H%M")

    target_d = pd.to_datetime(target_date).date()
    prev_dates = sorted([d for d in df_all["date"].unique() if d < target_d])
    if not prev_dates:
        print(f"No prior history before {target_date}")
        return None

    prev_d = prev_dates[-1]

    # 1. Extract ALL HTF Anchors
    # Previous Day H/L
    df_prev = df_all[df_all["date"] == prev_d]
    pdl = df_prev["low"].min()
    pdh = df_prev["high"].max()

    # Previous Day NY PM (13:30 to 16:00 ET)
    prev_ny_pm = df_prev[(df_prev["hhmm"] >= "1330") & (df_prev["hhmm"] <= "1600")]
    prev_ny_pm_low = prev_ny_pm["low"].min() if not prev_ny_pm.empty else np.nan
    prev_ny_pm_high = prev_ny_pm["high"].max() if not prev_ny_pm.empty else np.nan

    # Previous Day NY AM (09:30 to 12:00 ET)
    prev_ny_am = df_prev[(df_prev["hhmm"] >= "0930") & (df_prev["hhmm"] <= "1200")]
    prev_ny_am_low = prev_ny_am["low"].min() if not prev_ny_am.empty else np.nan
    prev_ny_am_high = prev_ny_am["high"].max() if not prev_ny_am.empty else np.nan

    # Asia (20:00 prev_d to 00:00 target_d)
    asia_bars = df_all[((df_all["date"] == prev_d) & (df_all["hhmm"] >= "2000")) |
                       ((df_all["date"] == target_d) & (df_all["hhmm"] < "0000"))]
    asia_high = asia_bars["high"].max() if not asia_bars.empty else np.nan
    asia_low = asia_bars["low"].min() if not asia_bars.empty else np.nan

    # Target Day Data
    df_day = df_all[df_all["date"] == target_d].copy()
    if df_day.empty:
        print(f"No data for {target_date}")
        return None

    # London (02:00 to 05:00 ET)
    lon_bars = df_day[(df_day["hhmm"] >= "0200") & (df_day["hhmm"] < "0500")]
    lon_high = lon_bars["high"].max() if not lon_bars.empty else np.nan
    lon_low = lon_bars["low"].min() if not lon_bars.empty else np.nan

    # NY Open Price (09:30 ET)
    ny_open_bar = df_day[df_day["hhmm"] == "0930"]
    ny_open_price = ny_open_bar["open"].iloc[0] if not ny_open_bar.empty else np.nan

    # Previous Week Low / High (PWL / PWH)
    # Estimate from earlier data
    earlier_bars = df_all[df_all["date"] < target_d]
    pwl = earlier_bars["low"].min() if not earlier_bars.empty else np.nan
    pwh = earlier_bars["high"].max() if not earlier_bars.empty else np.nan

    print("HTF Anchor Levels:")
    print(f"  • PDH: {pdh:.2f} | PDL: {pdl:.2f}")
    print(f"  • Prev NY PM High: {prev_ny_pm_high:.2f} | Prev NY PM Low: {prev_ny_pm_low:.2f}")
    print(f"  • Prev NY AM High: {prev_ny_am_high:.2f} | Prev NY AM Low: {prev_ny_am_low:.2f}")
    print(f"  • Asia High: {asia_high:.2f} | Asia Low: {asia_low:.2f}")
    print(f"  • London High: {lon_high:.2f} | London Low: {lon_low:.2f}")
    print(f"  • NY Open: {ny_open_price:.2f}")

    # 2. Resample to 5m for Continuous Intraday Tracking
    df_5m = df_day.resample("5min").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()

    # Rolling 1H & 4H High/Low
    df_5m["h1_high"] = df_5m["high"].rolling(12, min_periods=1).max().shift(1)
    df_5m["h1_low"] = df_5m["low"].rolling(12, min_periods=1).min().shift(1)
    df_5m["h4_high"] = df_5m["high"].rolling(48, min_periods=1).max().shift(1)
    df_5m["h4_low"] = df_5m["low"].rolling(48, min_periods=1).min().shift(1)

    trades = []
    active_sweep = None
    last_down_open = np.nan
    last_up_open = np.nan
    last_down_bar = None
    last_up_bar = None

    for i in range(len(df_5m)):
        t5 = df_5m.index[i]
        hhmm5 = t5.strftime("%H%M")
        c5, o5, h5, l5 = df_5m["close"].iloc[i], df_5m["open"].iloc[i], df_5m["high"].iloc[i], df_5m["low"].iloc[i]
        h5_2 = df_5m["high"].iloc[i-2] if i >= 2 else np.nan
        l5_2 = df_5m["low"].iloc[i-2] if i >= 2 else np.nan

        # Track last opposing candle open and body (for Order Block identification)
        if c5 < o5:
            last_down_open = o5
            last_down_bar = {"open": o5, "high": h5, "low": l5, "close": c5, "time": t5}
        elif c5 > o5:
            last_up_open = o5
            last_up_bar = {"open": o5, "high": h5, "low": l5, "close": c5, "time": t5}

        # Killzone Gate: Only trade during high-probability institutional windows
        # NY AM: 09:30 - 11:30 ET | NY PM: 13:30 - 16:00 ET
        in_killzone = ("0930" <= hhmm5 <= "1130") or ("1330" <= hhmm5 <= "1600")

        # Manage active_sweep expiration & ICT Invalidation
        if active_sweep:
            if active_sweep["type"] == "BEAR" and h5 > active_sweep["extreme"]:
                active_sweep = None # Invalidated by higher high
            elif active_sweep["type"] == "BULL" and l5 < active_sweep["extreme"]:
                active_sweep = None # Invalidated by lower low
            elif (i - active_sweep["bar_idx"]) > 10:
                active_sweep = None # Timed out

        # Continuous HTF Sweep Detection (Runs across all bars, but entries executed in killzone)
        if active_sweep is None:
            # True HTF Major Anchors
            bull_anchors = [
                ("NY PM Low", prev_ny_pm_low),
                ("4H Low", df_5m["h4_low"].iloc[i]),
                ("London Low", lon_low),
                ("Asia Low", asia_low),
                ("PDL", pdl),
                ("PWL", pwl)
            ]
            for name, lvl in bull_anchors:
                if not np.isnan(lvl):
                    is_wick_reject = (l5 <= lvl and c5 > lvl)
                    is_reclaim = (i > 0 and df_5m["low"].iloc[i-1] <= lvl and df_5m["close"].iloc[i-1] <= lvl and c5 > lvl)
                    prior_closes_below = sum(df_5m["close"].iloc[max(0, i-4):i] < lvl)

                    if (is_wick_reject or is_reclaim) and prior_closes_below <= 1:
                        other_swept = [n for n, l in bull_anchors if n != name and not np.isnan(l) and l5 <= l and c5 > l]
                        full_name = name + (f" & {other_swept[0]}" if other_swept else "")
                        active_sweep = {"type": "BULL", "anchor": full_name, "level": lvl, "time": t5, "bar_idx": i, "extreme": l5}
                        break

            if active_sweep is None:
                bear_anchors = [
                    ("NY PM High", prev_ny_pm_high),
                    ("4H High", df_5m["h4_high"].iloc[i]),
                    ("London High", lon_high),
                    ("Asia High", asia_high),
                    ("PDH", pdh),
                    ("PWH", pwh)
                ]
                for name, lvl in bear_anchors:
                    if not np.isnan(lvl):
                        is_wick_reject = (h5 >= lvl and c5 < lvl)
                        is_reclaim = (i > 0 and df_5m["high"].iloc[i-1] >= lvl and df_5m["close"].iloc[i-1] >= lvl and c5 < lvl)
                        prior_closes_above = sum(df_5m["close"].iloc[max(0, i-4):i] > lvl)

                        if (is_wick_reject or is_reclaim) and prior_closes_above <= 1:
                            other_swept = [n for n, l in bear_anchors if n != name and not np.isnan(l) and h5 >= l and c5 < l]
                            full_name = name + (f" & {other_swept[0]}" if other_swept else "")
                            active_sweep = {"type": "BEAR", "anchor": full_name, "level": lvl, "time": t5, "bar_idx": i, "extreme": h5}
                            break

        # Step 2: CISD Shift Detection (Only entry within Killzone)
        if in_killzone and active_sweep and (i - active_sweep["bar_idx"]) <= 10:
            if active_sweep["type"] == "BULL" and not np.isnan(last_down_open) and c5 > last_down_open:
                cisd_level = last_down_open
                cisd_time = t5

                # Step 3: 2nd Stage of Distribution into OB & iFVG
                # Order Block bounds
                ob_high = last_down_bar["high"] if last_down_bar else cisd_level
                ob_low = last_down_bar["low"] if last_down_bar else min(o5, c5)
                # Displacement FVG bounds
                has_fvg = (l5 > h5_2) if not np.isnan(h5_2) else False
                fvg_top = l5 if has_fvg else max(c5, cisd_level)
                fvg_bot = h5_2 if has_fvg else min(o5, cisd_level)

                # Combined Retest Zone (OB and iFVG)
                retest_top = max(ob_high, fvg_top)
                retest_bot = min(ob_low, fvg_bot)

                # Look forward on 1m bars for 2nd stage retest into OB/iFVG
                m1_window = df_day.loc[t5:t5 + pd.Timedelta(minutes=30)]
                tapped, tap_idx = False, -1
                for m in range(1, len(m1_window)):
                    if m1_window.iloc[m]["low"] <= retest_top:
                        tapped = True
                        tap_idx = m
                        break

                if tapped:
                    # Look for 1m candle rejection / respect (Close > Open)
                    for k in range(tap_idx, min(len(m1_window), tap_idx + 12)):
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
                                tp2_p = entry_p + (entry_p * 0.0030) # +30 bps Runner

                                sim_bars = df_day.loc[k_time:]
                                q_hit, r_hit = False, False
                                active_sl = sl_p
                                exit_time = None

                                for s in range(1, len(sim_bars)):
                                    sb = sim_bars.iloc[s]
                                    if not q_hit and sb["high"] >= tp1_p:
                                        q_hit = True
                                        active_sl = entry_p
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

                m1_window = df_day.loc[t5:t5 + pd.Timedelta(minutes=30)]
                tapped, tap_idx = False, -1
                for m in range(1, len(m1_window)):
                    if m1_window.iloc[m]["high"] >= retest_bot:
                        tapped = True
                        tap_idx = m
                        break

                if tapped:
                    for k in range(tap_idx, min(len(m1_window), tap_idx + 12)):
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
                                tp2_p = entry_p - (entry_p * 0.0030)

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
                                    "risk_bps": risk_bps,
                                    "q_hit": q_hit,
                                    "r_hit": r_hit,
                                    "exit_time": exit_time
                                })
                                active_sweep = None
                                break

    print(f"\nRESULTS FOR {target_date}: {len(trades)} trades")
    for tr in trades:
        print(f"  [{tr['direction']}] @ {tr['entry_time'].strftime('%H:%M ET')} | Entry: {tr['entry_price']:.2f}")
        print(f"    • HTF Sweep Trigger: {tr['anchor_name']} ({tr['anchor_level']:.2f}) at {tr['sweep_time'].strftime('%H:%M ET')}")
        print(f"    • CISD Shift Level: {tr['cisd_level']:.2f} at {tr['cisd_time'].strftime('%H:%M ET')}")
        print(f"    • 2nd Stage OB/iFVG Retest Zone: [{tr['retest_bot']:.2f}, {tr['retest_top']:.2f}]")
        print(f"    • Stop Loss: {tr['sl_price']:.2f} ({tr['risk_bps']:.1f} bps risk)")
        print(f"    • Queen (+10 bps): {tr['q_hit']} | Runner (+30 bps): {tr['r_hit']}")

    # Render Chart
    df_plot = df_day[(df_day["hhmm"] >= "0830") & (df_day["hhmm"] <= "1400")].copy()
    if df_plot.empty:
        df_plot = df_day.copy()

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

    # Plot HTF Lines
    if not np.isnan(prev_ny_pm_low):
        ax.axhline(prev_ny_pm_low, color="#ec4899", linestyle="--", alpha=0.8, label=f"NY PM Low ({prev_ny_pm_low:.1f})")
    if not np.isnan(pdl):
        ax.axhline(pdl, color="#3b82f6", linestyle=":", alpha=0.6, label=f"PDL ({pdl:.1f})")
    if not np.isnan(ny_open_price):
        ax.axhline(ny_open_price, color="#64748b", linestyle="-.", alpha=0.6, label=f"NY Open ({ny_open_price:.1f})")

    for tr in trades:
        is_long = tr["direction"] == "BUY LONG"
        col = "#22c55e" if is_long else "#ef4444"

        # Swept Level
        ax.axhline(tr["anchor_level"], color="#2563eb", linestyle="-.", linewidth=1.5)
        ax.text(df_plot.index[5], tr["anchor_level"] - (6 if is_long else -6), f"[HTF SWEPT] {tr['anchor_name']} ({tr['anchor_level']:.2f})", color="#2563eb", fontsize=10, fontweight="bold")

        # CISD Level
        ax.axhline(tr["cisd_level"], color="#eab308", linestyle="-", linewidth=1.5)
        ax.text(tr["cisd_time"], tr["cisd_level"] + (3 if is_long else -3), f"[CISD SHIFT] {tr['cisd_level']:.2f}", color="#ca8a04", fontsize=10, fontweight="bold")

        # OB / iFVG Retest Box
        rect = Rectangle((mdates.date2num(tr["cisd_time"]), tr["retest_bot"]),
                         mdates.date2num(tr["entry_time"]) - mdates.date2num(tr["cisd_time"]) + 0.005,
                         tr["retest_top"] - tr["retest_bot"],
                         facecolor="#a855f7", alpha=0.25, edgecolor="#9333ea", linestyle="--")
        ax.add_patch(rect)
        ax.text(tr["cisd_time"], tr["retest_top"] + 2, "2nd Stage Retest: OB & iFVG", color="#9333ea", fontsize=9, fontweight="bold")

        # Entry Marker
        offset = -50 if is_long else 50
        ax.annotate(f"{tr['direction']}\nEntry: {tr['entry_price']:.2f}\nSL: {tr['sl_price']:.2f}\nQueen: {tr['tp1_price']:.2f}\nRunner: {tr['tp2_price']:.2f}",
                    xy=(tr["entry_time"], tr["entry_price"]),
                    xytext=(tr["entry_time"], tr["entry_price"] + offset),
                    arrowprops=dict(facecolor=col, edgecolor="#15803d" if is_long else "#991b1b", width=2, headwidth=8),
                    bbox=dict(boxstyle="round,pad=0.5", facecolor="#f8fafc", edgecolor=col, alpha=0.9),
                    fontsize=9, fontweight="bold")

        ax.hlines(tr["sl_price"], xmin=tr["entry_time"], xmax=tr["exit_time"] if tr["exit_time"] else df_plot.index[-1], color="#ef4444", linestyle="--", linewidth=1.5)
        ax.hlines(tr["tp1_price"], xmin=tr["entry_time"], xmax=tr["exit_time"] if tr["exit_time"] else df_plot.index[-1], color="#22c55e", linestyle="--", linewidth=1.5)
        ax.hlines(tr["tp2_price"], xmin=tr["entry_time"], xmax=tr["exit_time"] if tr["exit_time"] else df_plot.index[-1], color="#16a34a", linestyle="-", linewidth=2.0)

    ax.set_title(f"NQ Futures — {target_date} | Canonical ICT HTF Liquidity Grab -> CISD -> 2nd Stage OB/iFVG Retest", fontsize=13, fontweight="bold", pad=12)
    ax.set_ylabel("Price (Points)", fontsize=11)
    ax.grid(True, alpha=0.25)
    ax.legend(loc="upper left", fontsize=9, framealpha=0.8)

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M ET"))
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=1))
    fig.autofmt_xdate()

    chart_file = OUTPUT_DIR / f"canonical_ict_{target_date}.png"
    plt.savefig(chart_file, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Saved canonical chart to: {chart_file}")

    # Copy to root artifact directory
    root_art = Path(f"C:/Users/vinay/.gemini/antigravity/brain/4c21dcc0-89c9-42df-8e6a-fc48ef5552a9/canonical_ict_{target_date}.png")
    import shutil
    shutil.copy(chart_file, root_art)

if __name__ == "__main__":
    run_canonical_audit("2026-08-28")
    run_canonical_audit("2026-08-26")
