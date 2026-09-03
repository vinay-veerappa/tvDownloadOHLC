"""
Multi-Day Verification Runner: August 24 to August 28, 2026
Runs the complete ICT Liquidity Grab + CISD + TTrades + Chop Filter engine across all 5 sessions.
Generates charts for each session and outputs an exact audit table.
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

def audit_full_week():
    data_file = "data/NQ_recent_week.parquet"
    df_all = pd.read_parquet(data_file)
    df_all["date"] = df_all.index.date
    df_all["hhmm"] = df_all.index.strftime("%H%M")

    week_dates = [
        "2026-08-24",
        "2026-08-25",
        "2026-08-26",
        "2026-08-27",
        "2026-08-28"
    ]

    all_trades = []

    for target_date in week_dates:
        target_d = pd.to_datetime(target_date).date()
        prev_dates = [d for d in df_all["date"].unique() if d < target_d]
        if not prev_dates:
            continue
        prev_d = max(prev_dates)

        # 1. HTF Anchors
        df_prev = df_all[df_all["date"] == prev_d]
        pdl = df_prev["low"].min()
        pdh = df_prev["high"].max()

        df_day = df_all[df_all["date"] == target_d].copy()
        if df_day.empty:
            continue

        # Asia (20:00 prev_d to 00:00 target_d)
        asia_bars = df_all[((df_all["date"] == prev_d) & (df_all["hhmm"] >= "2000")) |
                           ((df_all["date"] == target_d) & (df_all["hhmm"] < "0000"))]
        asia_high = asia_bars["high"].max() if not asia_bars.empty else np.nan
        asia_low = asia_bars["low"].min() if not asia_bars.empty else np.nan

        # London (02:00 to 05:00 target_d)
        lon_bars = df_day[(df_day["hhmm"] >= "0200") & (df_day["hhmm"] < "0500")]
        lon_high = lon_bars["high"].max() if not lon_bars.empty else np.nan
        lon_low = lon_bars["low"].min() if not lon_bars.empty else np.nan

        # NY AM IB (09:30 to 10:00 target_d)
        ny_am_bars = df_day[(df_day["hhmm"] >= "0930") & (df_day["hhmm"] <= "1000")]
        ny_am_high = ny_am_bars["high"].max() if not ny_am_bars.empty else np.nan
        ny_am_low = ny_am_bars["low"].min() if not ny_am_bars.empty else np.nan

        df_day_rth = df_day[(df_day["hhmm"] >= "0930") & (df_day["hhmm"] <= "1600")].copy()
        df_5m = df_day_rth.resample("5min").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()

        df_5m["h1_high"] = df_5m["high"].rolling(12, min_periods=1).max().shift(1)
        df_5m["h1_low"] = df_5m["low"].rolling(12, min_periods=1).min().shift(1)

        # Chop Filter: Candle Color Alternation Rate
        is_green = df_day_rth["close"] > df_day_rth["open"]
        alt_rate_10 = (is_green != is_green.shift(1)).astype(float).rolling(10, min_periods=5).mean()
        df_day_rth["alt_rate_10"] = alt_rate_10
        df_day_rth["is_chop"] = (alt_rate_10 >= 0.70) | ((df_day_rth["hhmm"] >= "1200") & (df_day_rth["hhmm"] <= "1330"))

        day_trades = []
        active_sweep = None
        last_down_open = np.nan
        last_up_open = np.nan

        for i in range(len(df_5m)):
            t5 = df_5m.index[i]
            hhmm5 = t5.strftime("%H%M")
            c5, o5, h5, l5 = df_5m["close"].iloc[i], df_5m["open"].iloc[i], df_5m["high"].iloc[i], df_5m["low"].iloc[i]
            h5_2 = df_5m["high"].iloc[i-2] if i >= 2 else np.nan
            l5_2 = df_5m["low"].iloc[i-2] if i >= 2 else np.nan

            if i > 0:
                for step in range(1, min(i, 15)+1):
                    if df_5m["close"].iloc[i-step] < df_5m["open"].iloc[i-step] and np.isnan(last_down_open):
                        last_down_open = df_5m["open"].iloc[i-step]
                    if df_5m["close"].iloc[i-step] > df_5m["open"].iloc[i-step] and np.isnan(last_up_open):
                        last_up_open = df_5m["open"].iloc[i-step]

            if c5 < o5: last_down_open = o5
            elif c5 > o5: last_up_open = o5

            lookback_bars = df_5m.iloc[max(0, i-4):i+1]
            rec_min_l = lookback_bars["low"].min()
            rec_max_h = lookback_bars["high"].max()

            # Manage active_sweep expiration & ICT Invalidation
            if active_sweep:
                # Invalidation: if price breaks beyond the sweep extreme, the sweep is dead!
                if active_sweep["type"] == "BEAR" and h5 > active_sweep["extreme"]:
                    active_sweep = None
                elif active_sweep["type"] == "BULL" and l5 < active_sweep["extreme"]:
                    active_sweep = None
                # Expiration: 8 bars = 40 minutes max to form CISD
                elif (i - active_sweep["bar_idx"]) > 8:
                    active_sweep = None

            # Only search for a new sweep if no active sweep is awaiting CISD confirmation
            # Initial Balance sweeps can ONLY occur strictly after 10:00 AM (10:05 onwards)
            if active_sweep is None and hhmm5 > "1000":
                bull_anchors = [
                    ("NY AM Low", ny_am_low), ("London Low", lon_low),
                    ("Asia Low", asia_low), ("PDL", pdl),
                    ("1H Low", df_5m["h1_low"].iloc[i])
                ]
                for name, lvl in bull_anchors:
                    if not np.isnan(lvl):
                        is_wick_reject = (l5 <= lvl and c5 > lvl)
                        is_reclaim = (i > 0 and df_5m["low"].iloc[i-1] <= lvl and df_5m["close"].iloc[i-1] <= lvl and c5 > lvl)
                        approached_from_above = any(df_5m["high"].iloc[max(0, i-4):i] > lvl) if i > 0 else True

                        # Acceptance filter: if 2 or more consecutive prior closes were below lvl, it was a real breakdown, NOT a sweep!
                        prior_closes_below = sum(df_5m["close"].iloc[max(0, i-4):i] < lvl)
                        no_acceptance = prior_closes_below <= 1

                        if (is_wick_reject or is_reclaim) and approached_from_above and no_acceptance:
                            active_sweep = {"type": "BULL", "anchor": name, "level": lvl, "time": t5, "bar_idx": i, "extreme": l5}
                            break

                if active_sweep is None:
                    bear_anchors = [
                        ("NY AM High", ny_am_high), ("London High", lon_high),
                        ("Asia High", asia_high), ("PDH", pdh),
                        ("1H High", df_5m["h1_high"].iloc[i])
                    ]
                    for name, lvl in bear_anchors:
                        if not np.isnan(lvl):
                            is_wick_reject = (h5 >= lvl and c5 < lvl)
                            is_reclaim = (i > 0 and df_5m["high"].iloc[i-1] >= lvl and df_5m["close"].iloc[i-1] >= lvl and c5 < lvl)
                            approached_from_below = any(df_5m["low"].iloc[max(0, i-4):i] < lvl) if i > 0 else True

                            # Acceptance filter: if 2 or more consecutive prior closes were above lvl, it was a real breakout, NOT a sweep!
                            prior_closes_above = sum(df_5m["close"].iloc[max(0, i-4):i] > lvl)
                            no_acceptance = prior_closes_above <= 1

                            if (is_wick_reject or is_reclaim) and approached_from_below and no_acceptance:
                                active_sweep = {"type": "BEAR", "anchor": name, "level": lvl, "time": t5, "bar_idx": i, "extreme": h5}
                                break

            # CISD Check
            if active_sweep and (i - active_sweep["bar_idx"]) <= 8:
                if active_sweep["type"] == "BULL" and not np.isnan(last_down_open) and c5 > last_down_open:
                    cisd_level = last_down_open
                    cisd_time = t5
                    has_fvg = (l5 > h5_2) if not np.isnan(h5_2) else False
                    fvg_top = l5 if has_fvg else max(cisd_level, c5)
                    fvg_bot = h5_2 if has_fvg else min(cisd_level, o5)

                    m1_window = df_day_rth.loc[t5:t5 + pd.Timedelta(minutes=30)]
                    tapped, tap_idx = False, -1
                    for m in range(1, len(m1_window)):
                        if m1_window.iloc[m]["low"] <= fvg_top:
                            tapped = True; tap_idx = m; break

                    if tapped:
                        for k in range(tap_idx, min(len(m1_window), tap_idx + 10)):
                            k_row = m1_window.iloc[k]
                            k_time = m1_window.index[k]
                            if k_row["is_chop"]: continue

                            if k_row["close"] > k_row["open"]:
                                entry_p = k_row["close"]
                                protected_swing = m1_window.iloc[tap_idx:k+1]["low"].min()
                                sl_p = protected_swing - 1.0
                                risk_pts = entry_p - sl_p
                                risk_bps = (risk_pts / entry_p) * 10000.0

                                if 2.0 <= risk_bps <= 15.0:
                                    tp1_p = entry_p + (entry_p * 0.0010)
                                    tp2_p = entry_p + (entry_p * 0.0030)

                                    sim_bars = df_day_rth.loc[k_time:]
                                    q_hit, r_hit, sl_hit = False, False, False
                                    active_sl = sl_p
                                    exit_time = None

                                    for s in range(1, len(sim_bars)):
                                        sb = sim_bars.iloc[s]
                                        if not q_hit and sb["high"] >= tp1_p:
                                            q_hit = True; active_sl = entry_p
                                        if sb["low"] <= active_sl:
                                            sl_hit = True; exit_time = sim_bars.index[s]; break
                                        if sb["high"] >= tp2_p:
                                            r_hit = True; exit_time = sim_bars.index[s]; break

                                    tr_dict = {
                                        "date": target_date, "direction": "BUY LONG",
                                        "anchor_name": active_sweep["anchor"], "anchor_level": active_sweep["level"],
                                        "sweep_time": active_sweep["time"], "cisd_level": cisd_level, "cisd_time": cisd_time,
                                        "fvg_top": fvg_top, "fvg_bot": fvg_bot, "entry_time": k_time, "entry_price": entry_p,
                                        "sl_price": sl_p, "tp1_price": tp1_p, "tp2_price": tp2_p, "risk_bps": risk_bps,
                                        "q_hit": q_hit, "r_hit": r_hit, "exit_time": exit_time
                                    }
                                    day_trades.append(tr_dict)
                                    all_trades.append(tr_dict)
                                    active_sweep = None
                                    break
                        if day_trades:
                            break

                elif active_sweep["type"] == "BEAR" and not np.isnan(last_up_open) and c5 < last_up_open:
                    cisd_level = last_up_open
                    cisd_time = t5
                    has_fvg = (h5 < l5_2) if not np.isnan(l5_2) else False
                    fvg_top = l5_2 if has_fvg else max(cisd_level, o5)
                    fvg_bot = h5 if has_fvg else min(cisd_level, c5)

                    m1_window = df_day_rth.loc[t5:t5 + pd.Timedelta(minutes=30)]
                    tapped, tap_idx = False, -1
                    for m in range(1, len(m1_window)):
                        if m1_window.iloc[m]["high"] >= fvg_bot:
                            tapped = True; tap_idx = m; break

                    if tapped:
                        for k in range(tap_idx, min(len(m1_window), tap_idx + 10)):
                            k_row = m1_window.iloc[k]
                            k_time = m1_window.index[k]
                            if k_row["is_chop"]: continue

                            if k_row["close"] < k_row["open"]:
                                entry_p = k_row["close"]
                                protected_swing = m1_window.iloc[tap_idx:k+1]["high"].max()
                                sl_p = protected_swing + 1.0
                                risk_pts = sl_p - entry_p
                                risk_bps = (risk_pts / entry_p) * 10000.0

                                if 2.0 <= risk_bps <= 15.0:
                                    tp1_p = entry_p - (entry_p * 0.0010)
                                    tp2_p = entry_p - (entry_p * 0.0030)

                                    sim_bars = df_day_rth.loc[k_time:]
                                    q_hit, r_hit, sl_hit = False, False, False
                                    active_sl = sl_p
                                    exit_time = None

                                    for s in range(1, len(sim_bars)):
                                        sb = sim_bars.iloc[s]
                                        if not q_hit and sb["low"] <= tp1_p:
                                            q_hit = True; active_sl = entry_p
                                        if sb["high"] >= active_sl:
                                            sl_hit = True; exit_time = sim_bars.index[s]; break
                                        if sb["low"] <= tp2_p:
                                            r_hit = True; exit_time = sim_bars.index[s]; break

                                    tr_dict = {
                                        "date": target_date, "direction": "SELL SHORT",
                                        "anchor_name": active_sweep["anchor"], "anchor_level": active_sweep["level"],
                                        "sweep_time": active_sweep["time"], "cisd_level": cisd_level, "cisd_time": cisd_time,
                                        "fvg_top": fvg_top, "fvg_bot": fvg_bot, "entry_time": k_time, "entry_price": entry_p,
                                        "sl_price": sl_p, "tp1_price": tp1_p, "tp2_price": tp2_p, "risk_bps": risk_bps,
                                        "q_hit": q_hit, "r_hit": r_hit, "exit_time": exit_time
                                    }
                                    day_trades.append(tr_dict)
                                    all_trades.append(tr_dict)
                                    active_sweep = None
                                    break
                        if day_trades:
                            break

        # Generate Chart for each day
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 9), gridspec_kw={"height_ratios": [3, 1]}, sharex=True)
        plt.subplots_adjust(hspace=0.08)

        width = 0.0004
        width2 = 0.00008
        up = df_day_rth[df_day_rth["close"] >= df_day_rth["open"]]
        down = df_day_rth[df_day_rth["close"] < df_day_rth["open"]]

        ax1.bar(up.index, up["close"] - up["open"], width, bottom=up["open"], color="#089981", edgecolor="#089981")
        ax1.bar(up.index, up["high"] - up["close"], width2, bottom=up["close"], color="#089981")
        ax1.bar(up.index, up["low"] - up["open"], width2, bottom=up["open"], color="#089981")

        ax1.bar(down.index, down["open"] - down["close"], width, bottom=down["close"], color="#f23645", edgecolor="#f23645")
        ax1.bar(down.index, down["high"] - down["open"], width2, bottom=down["open"], color="#f23645")
        ax1.bar(down.index, down["low"] - down["close"], width2, bottom=down["close"], color="#f23645")

        ax1.axhline(pdl, color="#3b82f6", linestyle="--", alpha=0.6, label=f"PDL ({pdl:.1f})")
        ax1.axhline(pdh, color="#ef4444", linestyle="--", alpha=0.6, label=f"PDH ({pdh:.1f})")
        if not np.isnan(ny_am_low): ax1.axhline(ny_am_low, color="#06b6d4", linestyle=":", alpha=0.7, label=f"NY AM Low ({ny_am_low:.1f})")
        if not np.isnan(ny_am_high): ax1.axhline(ny_am_high, color="#f97316", linestyle=":", alpha=0.7, label=f"NY AM High ({ny_am_high:.1f})")

        for tr in day_trades:
            is_long = tr["direction"] == "BUY LONG"
            box_col = "#22c55e" if is_long else "#ef4444"
            edge_col = "#16a34a" if is_long else "#dc2626"

            ax1.axhline(tr["anchor_level"], color="#2563eb", linestyle="-.", linewidth=1.5)
            ax1.text(df_day_rth.index[5], tr["anchor_level"] - (5 if is_long else -5), f"[SWEPT] {tr['anchor_name']} ({tr['anchor_level']:.2f})", color="#2563eb", fontsize=10, fontweight="bold")

            ax1.axhline(tr["cisd_level"], color="#eab308", linestyle="-", linewidth=1.5)
            ax1.text(tr["cisd_time"], tr["cisd_level"] + (3 if is_long else -3), f"[CISD SHIFT] {tr['cisd_level']:.2f}", color="#ca8a04", fontsize=10, fontweight="bold")

            fvg_rect = Rectangle((mdates.date2num(tr["cisd_time"]), tr["fvg_bot"]),
                                 mdates.date2num(tr["entry_time"]) - mdates.date2num(tr["cisd_time"]) + 0.005,
                                 tr["fvg_top"] - tr["fvg_bot"],
                                 facecolor=box_col, alpha=0.25, edgecolor=edge_col, linestyle="--")
            ax1.add_patch(fvg_rect)

            offset = -60 if is_long else 60
            ax1.annotate(f"{tr['direction']}\nEntry: {tr['entry_price']:.2f}\nSL: {tr['sl_price']:.2f}\nQueen (+10): {tr['tp1_price']:.2f}\nRunner (+30): {tr['tp2_price']:.2f}",
                         xy=(tr["entry_time"], tr["entry_price"]),
                         xytext=(tr["entry_time"], tr["entry_price"] + offset),
                         arrowprops=dict(facecolor=box_col, edgecolor=edge_col, width=2, headwidth=8),
                         bbox=dict(boxstyle="round,pad=0.5", facecolor="#f8fafc", edgecolor=box_col, alpha=0.9),
                         fontsize=9, fontweight="bold")

            ax1.hlines(tr["sl_price"], xmin=tr["entry_time"], xmax=tr["exit_time"] if tr["exit_time"] else df_day_rth.index[-1], color="#ef4444", linestyle="--", linewidth=1.5)
            ax1.hlines(tr["tp1_price"], xmin=tr["entry_time"], xmax=tr["exit_time"] if tr["exit_time"] else df_day_rth.index[-1], color="#22c55e", linestyle="--", linewidth=1.5)
            ax1.hlines(tr["tp2_price"], xmin=tr["entry_time"], xmax=tr["exit_time"] if tr["exit_time"] else df_day_rth.index[-1], color="#16a34a", linestyle="-", linewidth=2.0)

        ax1.set_title(f"NQ Futures — {target_date} | Canonical ICT Liquidity Grab + CISD + TTrades + Chop Filter", fontsize=13, fontweight="bold", pad=12)
        ax1.set_ylabel("Price (Points)", fontsize=11)
        ax1.grid(True, alpha=0.25)
        ax1.legend(loc="upper left", fontsize=9, framealpha=0.8)

        ax2.plot(df_day_rth.index, df_day_rth["alt_rate_10"], color="#6366f1", linewidth=1.5, label="10-Bar Candle Alternation Rate")
        ax2.axhline(0.70, color="#ef4444", linestyle="--", linewidth=1.2, label="Chop Threshold (70%)")
        ax2.fill_between(df_day_rth.index, 0.70, df_day_rth["alt_rate_10"], where=(df_day_rth["alt_rate_10"] >= 0.70), color="#fee2e2", alpha=0.6, label="Chop Zone (Stand Down)")
        ax2.set_ylabel("Chop Index", fontsize=11)
        ax2.set_ylim(0, 1.0)
        ax2.grid(True, alpha=0.25)
        ax2.legend(loc="upper left", fontsize=9, framealpha=0.8)

        ax2.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
        ax2.xaxis.set_major_locator(mdates.HourLocator(interval=1))
        fig.autofmt_xdate()

        chart_path = OUTPUT_DIR / f"audit_chart_{target_date}.png"
        plt.savefig(chart_path, dpi=150, bbox_inches="tight")
        plt.close()
        print(f"Generated chart for {target_date}: {chart_path.name} ({len(day_trades)} trades)")

    print("\n" + "=" * 115)
    print("WEEKLY AUDIT SUMMARY (AUGUST 24 - AUGUST 28, 2026)")
    print("=" * 115)
    tdf = pd.DataFrame(all_trades)
    if not tdf.empty:
        summary_cols = ["date", "direction", "entry_time", "entry_price", "anchor_name", "risk_bps", "q_hit", "r_hit"]
        tdf["time_str"] = tdf["entry_time"].dt.strftime("%H:%M")
        print(tdf[["date", "direction", "time_str", "entry_price", "anchor_name", "risk_bps", "q_hit", "r_hit"]].to_string(index=False))
        total = len(tdf)
        q_wins = tdf["q_hit"].sum()
        r_wins = tdf["r_hit"].sum()
        print(f"\nTotal Trades: {total} | Queen (+10 bps) Win Rate: {(q_wins/total)*100:.1f}% ({q_wins}/{total}) | Runner (+30 bps) Win Rate: {(r_wins/total)*100:.1f}% ({r_wins}/{total})")
    else:
        print("No trades triggered.")

if __name__ == "__main__":
    audit_full_week()
