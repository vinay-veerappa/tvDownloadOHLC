"""
Audit & Visual Verification Engine for ICT Liquidity Grab + CISD + TTrades + Chop Filter
Generates crystal-clear session charts with:
1. Exact Liquidity Grab Anchor line & label (PDH/PDL, London H/L, Asia H/L, NY AM H/L, 1H/4H H/L)
2. CISD Shift line & label
3. Retest FVG / Order block shaded box
4. Entry decision callout, SL, Queen (+10 bps), Runner (+30 bps)
5. Chop Filter Subpanel (10-bar Candle Color Alternation Rate & FVG Quality Gate)
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

# Ensure output directory exists
OUTPUT_DIR = Path("C:/Users/vinay/.gemini/antigravity/brain/4c21dcc0-89c9-42df-8e6a-fc48ef5552a9/scratch/charts")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def run_session_audit(data_file="data/NQ_recent_week.parquet", target_date="2026-08-28"):
    print("=" * 110)
    print(f"SESSION AUDIT & VISUAL GENERATION: {target_date}")
    print("=" * 110)

    df_all = pd.read_parquet(data_file)
    df_all["date"] = df_all.index.date
    df_all["hhmm"] = df_all.index.strftime("%H%M")

    target_d = pd.to_datetime(target_date).date()
    prev_dates = [d for d in df_all["date"].unique() if d < target_d]
    if not prev_dates:
        print(f"No prior history found before {target_date}")
        return None

    prev_d = max(prev_dates)

    # 1. Extract HTF Anchors
    # Previous Day H/L
    df_prev = df_all[df_all["date"] == prev_d]
    pdl = df_prev["low"].min()
    pdh = df_prev["high"].max()

    # Target Day Data
    df_day = df_all[df_all["date"] == target_d].copy()
    if df_day.empty:
        print(f"No data for {target_date}")
        return None

    # Asia (20:00 prev_d to 00:00 target_d)
    asia_bars = df_all[((df_all["date"] == prev_d) & (df_all["hhmm"] >= "2000")) |
                       ((df_all["date"] == target_d) & (df_all["hhmm"] < "0000"))]
    asia_high = asia_bars["high"].max() if not asia_bars.empty else np.nan
    asia_low = asia_bars["low"].min() if not asia_bars.empty else np.nan

    # London (02:00 to 05:00 target_d)
    lon_bars = df_day[(df_day["hhmm"] >= "0200") & (df_day["hhmm"] < "0500")]
    lon_high = lon_bars["high"].max() if not lon_bars.empty else np.nan
    lon_low = lon_bars["low"].min() if not lon_bars.empty else np.nan

    # NY AM Initial Balance (09:30 to 10:00 target_d)
    ny_am_bars = df_day[(df_day["hhmm"] >= "0930") & (df_day["hhmm"] <= "1000")]
    ny_am_high = ny_am_bars["high"].max() if not ny_am_bars.empty else np.nan
    ny_am_low = ny_am_bars["low"].min() if not ny_am_bars.empty else np.nan

    print(f"HTF Anchors for {target_date}:")
    print(f"  • PDH: {pdh:.2f} | PDL: {pdl:.2f}")
    print(f"  • Asia High: {asia_high:.2f} | Asia Low: {asia_low:.2f}")
    print(f"  • London High: {lon_high:.2f} | London Low: {lon_low:.2f}")
    print(f"  • NY AM IB High: {ny_am_high:.2f} | NY AM IB Low: {ny_am_low:.2f}")

    # 2. Resample to 5m & 15m for Structure
    df_day_rth = df_day[(df_day["hhmm"] >= "0930") & (df_day["hhmm"] <= "1600")].copy()
    df_5m = df_day_rth.resample("5min").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()

    # Rolling 1-Hour High/Low on 5m (12 bars)
    df_5m["h1_high"] = df_5m["high"].rolling(12, min_periods=1).max().shift(1)
    df_5m["h1_low"] = df_5m["low"].rolling(12, min_periods=1).min().shift(1)

    # 3. Chop Filter Calculation (Candle Color Alternation Rate)
    # is_green != shift(1)
    is_green = df_day_rth["close"] > df_day_rth["open"]
    alt_rate_10 = (is_green != is_green.shift(1)).astype(float).rolling(10, min_periods=5).mean()
    df_day_rth["alt_rate_10"] = alt_rate_10
    df_day_rth["is_chop"] = (alt_rate_10 >= 0.70) | ((df_day_rth["hhmm"] >= "1200") & (df_day_rth["hhmm"] <= "1330"))

    # 4. Sequential Execution Logic
    # Step 1: Detect Liquidity Sweeps with Wick Rejections
    # Check each 5m candle
    trades = []
    active_sweep = None
    vibes = -1 # Start session tracking
    last_down_open = np.nan
    last_up_open = np.nan

    for i in range(len(df_5m)):
        t5 = df_5m.index[i]
        hhmm5 = t5.strftime("%H%M")
        c5, o5, h5, l5 = df_5m["close"].iloc[i], df_5m["open"].iloc[i], df_5m["high"].iloc[i], df_5m["low"].iloc[i]
        h5_2 = df_5m["high"].iloc[i-2] if i >= 2 else np.nan
        l5_2 = df_5m["low"].iloc[i-2] if i >= 2 else np.nan

        # Update last opposing candle open
        if i > 0:
            for step in range(1, min(i, 15)+1):
                if df_5m["close"].iloc[i-step] < df_5m["open"].iloc[i-step] and np.isnan(last_down_open):
                    last_down_open = df_5m["open"].iloc[i-step]
                if df_5m["close"].iloc[i-step] > df_5m["open"].iloc[i-step] and np.isnan(last_up_open):
                    last_up_open = df_5m["open"].iloc[i-step]

        if c5 < o5:
            last_down_open = o5
        elif c5 > o5:
            last_up_open = o5

        # Check for Rejection Sweeps (Wick breach & close back inside)
        # Check against PDL, Asia Low, London Low, NY AM Low, H1 Low
        lookback_bars = df_5m.iloc[max(0, i-4):i+1]
        rec_min_l = lookback_bars["low"].min()
        rec_max_h = lookback_bars["high"].max()

        # Bullish Grab (SSL Purged)
        bull_anchors = [
            ("PDL", pdl), ("London Low", lon_low), ("Asia Low", asia_low),
            ("NY AM Low", ny_am_low if hhmm5 > "1000" else np.nan),
            ("1H Low", df_5m["h1_low"].iloc[i])
        ]
        for name, lvl in bull_anchors:
            if not np.isnan(lvl) and rec_min_l <= lvl and c5 > lvl:
                active_sweep = {"type": "BULL", "anchor": name, "level": lvl, "time": t5, "bar_idx": i}
                break

        # Bearish Grab (BSL Purged)
        bear_anchors = [
            ("PDH", pdh), ("London High", lon_high), ("Asia High", asia_high),
            ("NY AM High", ny_am_high if hhmm5 > "1000" else np.nan),
            ("1H High", df_5m["h1_high"].iloc[i])
        ]
        for name, lvl in bear_anchors:
            if not np.isnan(lvl) and rec_max_h >= lvl and c5 < lvl:
                active_sweep = {"type": "BEAR", "anchor": name, "level": lvl, "time": t5, "bar_idx": i}
                break

        # Step 2: Check CISD Confirmation
        if active_sweep and (i - active_sweep["bar_idx"]) <= 8:
            if active_sweep["type"] == "BULL" and not np.isnan(last_down_open) and c5 > last_down_open:
                # Bullish CISD Triggered!
                cisd_level = last_down_open
                cisd_time = t5
                # Establish Retest Zone (FVG or candle body)
                has_fvg = (l5 > h5_2) if not np.isnan(h5_2) else False
                fvg_top = l5 if has_fvg else max(cisd_level, c5)
                fvg_bot = h5_2 if has_fvg else min(cisd_level, o5)

                # Step 3: TTrades 1m Execution on the lower wick retest
                # Look forward on 1m bars from t5 to t5 + 30 min
                m1_window = df_day_rth.loc[t5:t5 + pd.Timedelta(minutes=30)]
                tapped = False
                tap_idx = -1
                for m in range(1, len(m1_window)):
                    m1_row = m1_window.iloc[m]
                    if m1_row["low"] <= fvg_top:
                        tapped = True
                        tap_idx = m
                        break

                if tapped:
                    # Look for 1m confirmation candle (Close > Open)
                    for k in range(tap_idx, min(len(m1_window), tap_idx + 10)):
                        k_row = m1_window.iloc[k]
                        k_time = m1_window.index[k]
                        # Check Chop Filter
                        is_choppy = k_row["is_chop"]
                        if is_choppy:
                            continue # Skip entry during chop

                        if k_row["close"] > k_row["open"]:
                            # Confirm Long Entry!
                            entry_p = k_row["close"]
                            protected_swing = m1_window.iloc[tap_idx:k+1]["low"].min()
                            sl_p = protected_swing - 1.0 # 1 tick buffer
                            risk_pts = entry_p - sl_p
                            risk_bps = (risk_pts / entry_p) * 10000.0

                            if 2.0 <= risk_bps <= 15.0:
                                tp1_p = entry_p + (entry_p * 0.0010) # +10 bps Queen
                                tp2_p = entry_p + (entry_p * 0.0030) # +30 bps Runner

                                # Evaluate trade outcome
                                sim_bars = df_day_rth.loc[k_time:]
                                q_hit, r_hit, sl_hit = False, False, False
                                active_sl = sl_p
                                exit_time = None

                                for s in range(1, len(sim_bars)):
                                    sb = sim_bars.iloc[s]
                                    if not q_hit and sb["high"] >= tp1_p:
                                        q_hit = True
                                        active_sl = entry_p # Move to Breakeven
                                    if sb["low"] <= active_sl:
                                        sl_hit = True
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
                                    "fvg_top": fvg_top,
                                    "fvg_bot": fvg_bot,
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

    print(f"\nTRADES DETECTED FOR {target_date}: {len(trades)}")
    for tr in trades:
        print(f"  [{tr['direction']}] @ {tr['entry_time'].strftime('%H:%M')} | Price: {tr['entry_price']:.2f}")
        print(f"    • Trigger: Swept {tr['anchor_name']} ({tr['anchor_level']:.2f})")
        print(f"    • CISD Shift: {tr['cisd_level']:.2f} at {tr['cisd_time'].strftime('%H:%M')}")
        print(f"    • Retest Zone: [{tr['fvg_bot']:.2f}, {tr['fvg_top']:.2f}]")
        print(f"    • Risk: {tr['risk_bps']:.1f} bps | SL: {tr['sl_price']:.2f}")
        print(f"    • Outcome: Queen (+10 bps) Hit: {tr['q_hit']} | Runner (+30 bps) Hit: {tr['r_hit']}")

    # 5. Generate Professional Matplotlib Chart
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 10), gridspec_kw={"height_ratios": [3, 1]}, sharex=True)
    plt.subplots_adjust(hspace=0.08)

    # Candlestick plotting on ax1
    dates = df_day_rth.index
    width = 0.0004
    width2 = 0.00008

    up = df_day_rth[df_day_rth["close"] >= df_day_rth["open"]]
    down = df_day_rth[df_day_rth["close"] < df_day_rth["open"]]

    # Plot up candles
    ax1.bar(up.index, up["close"] - up["open"], width, bottom=up["open"], color="#089981", edgecolor="#089981")
    ax1.bar(up.index, up["high"] - up["close"], width2, bottom=up["close"], color="#089981")
    ax1.bar(up.index, up["low"] - up["open"], width2, bottom=up["open"], color="#089981")

    # Plot down candles
    ax1.bar(down.index, down["open"] - down["close"], width, bottom=down["close"], color="#f23645", edgecolor="#f23645")
    ax1.bar(down.index, down["high"] - down["open"], width2, bottom=down["open"], color="#f23645")
    ax1.bar(down.index, down["low"] - down["close"], width2, bottom=down["close"], color="#f23645")

    # Draw HTF Anchors
    ax1.axhline(pdl, color="#3b82f6", linestyle="--", alpha=0.6, label=f"PDL ({pdl:.1f})")
    ax1.axhline(pdh, color="#ef4444", linestyle="--", alpha=0.6, label=f"PDH ({pdh:.1f})")
    if not np.isnan(ny_am_low):
        ax1.axhline(ny_am_low, color="#06b6d4", linestyle=":", alpha=0.7, label=f"NY AM Low ({ny_am_low:.1f})")

    # Plot Trade Overlays
    for tr in trades:
        # Swept Level
        ax1.axhline(tr["anchor_level"], color="#2563eb", linestyle="-.", linewidth=1.5)
        ax1.text(df_day_rth.index[10], tr["anchor_level"] - 5, f"[SWEPT] {tr['anchor_name']} ({tr['anchor_level']:.2f})", color="#2563eb", fontsize=10, fontweight="bold")

        # CISD Level
        ax1.axhline(tr["cisd_level"], color="#eab308", linestyle="-", linewidth=1.5)
        ax1.text(tr["cisd_time"], tr["cisd_level"] + 3, f"[CISD SHIFT] {tr['cisd_level']:.2f}", color="#ca8a04", fontsize=10, fontweight="bold")

        # Retest FVG Box
        fvg_rect = Rectangle((mdates.date2num(tr["cisd_time"]), tr["fvg_bot"]),
                             mdates.date2num(tr["entry_time"]) - mdates.date2num(tr["cisd_time"]) + 0.005,
                             tr["fvg_top"] - tr["fvg_bot"],
                             facecolor="#22c55e", alpha=0.25, edgecolor="#16a34a", linestyle="--")
        ax1.add_patch(fvg_rect)

        # Entry Marker & Brackets
        ax1.annotate(f"{tr['direction']}\nEntry: {tr['entry_price']:.2f}\nSL: {tr['sl_price']:.2f}\nQueen (+10): {tr['tp1_price']:.2f}\nRunner (+30): {tr['tp2_price']:.2f}",
                     xy=(tr["entry_time"], tr["entry_price"]),
                     xytext=(tr["entry_time"], tr["entry_price"] - 60),
                     arrowprops=dict(facecolor="#22c55e", edgecolor="#15803d", width=2, headwidth=8),
                     bbox=dict(boxstyle="round,pad=0.5", facecolor="#f0fdf4", edgecolor="#22c55e", alpha=0.9),
                     fontsize=9, fontweight="bold")

        # Horizontal SL and Targets
        ax1.hlines(tr["sl_price"], xmin=tr["entry_time"], xmax=tr["exit_time"] if tr["exit_time"] else df_day_rth.index[-1], color="#ef4444", linestyle="--", linewidth=1.5, label="Stop Loss")
        ax1.hlines(tr["tp1_price"], xmin=tr["entry_time"], xmax=tr["exit_time"] if tr["exit_time"] else df_day_rth.index[-1], color="#22c55e", linestyle="--", linewidth=1.5, label="Queen (+10 bps)")
        ax1.hlines(tr["tp2_price"], xmin=tr["entry_time"], xmax=tr["exit_time"] if tr["exit_time"] else df_day_rth.index[-1], color="#16a34a", linestyle="-", linewidth=2.0, label="Runner (+30 bps)")

    ax1.set_title(f"NQ Futures — {target_date} | Canonical ICT Liquidity Grab + CISD + TTrades Retest Engine", fontsize=14, fontweight="bold", pad=12)
    ax1.set_ylabel("Price (Points)", fontsize=11)
    ax1.grid(True, alpha=0.25)
    ax1.legend(loc="upper left", fontsize=9, framealpha=0.8)

    # Subpanel: Chop Filter (Candle Color Alternation Rate)
    ax2.plot(df_day_rth.index, df_day_rth["alt_rate_10"], color="#6366f1", linewidth=1.5, label="10-Bar Candle Alternation Rate")
    ax2.axhline(0.70, color="#ef4444", linestyle="--", linewidth=1.2, label="Chop Threshold (70%)")
    ax2.fill_between(df_day_rth.index, 0.70, df_day_rth["alt_rate_10"], where=(df_day_rth["alt_rate_10"] >= 0.70), color="#fee2e2", alpha=0.6, label="Chop Zone (Stand Down)")
    ax2.set_ylabel("Chop Index", fontsize=11)
    ax2.set_ylim(0, 1.0)
    ax2.grid(True, alpha=0.25)
    ax2.legend(loc="upper left", fontsize=9, framealpha=0.8)

    # Format x-axis
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    ax2.xaxis.set_major_locator(mdates.HourLocator(interval=1))
    fig.autofmt_xdate()

    chart_file = OUTPUT_DIR / f"audit_chart_{target_date}.png"
    plt.savefig(chart_file, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Saved visual chart to: {chart_file}")

    return {
        "date": target_date, "trades": trades, "chart_file": str(chart_file)
    }

if __name__ == "__main__":
    run_session_audit(target_date="2026-08-28")
