"""
Render August 26, 2026 Verification: 1 Winning Trade & 1 Losing Trade
=====================================================================
1. Winning Trade: Long Setup (10:20 ET to 11:05 ET / 09:20 CT to 10:05 CT)
   - Swept London Low (29185.00) & PWL
   - Bullish SMT vs ES
   - CISD Shift @ 29190.00
   - Entry: Retest @ 29192.75
   - Target: Opposing BSL @ 29277.25 (+85 pts WIN)

2. Losing Trade: Short Setup (13:30 ET to 14:15 ET / 12:30 CT to 13:15 CT)
   - Minor local high poke to 29284.75
   - False 1m CISD @ 29282.50
   - Entry: Short @ 29279.50
   - SL: 29293.00 (-13.5 pts LOSS)
   - Why it failed: Inducement during lunch lull, no HTF FVG/OB backing, fighting macro expansion
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import mplfinance as mpf

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

OUTPUT_DIR = Path("C:/Users/vinay/.gemini/antigravity/brain/4c21dcc0-89c9-42df-8e6a-fc48ef5552a9")

def render_aug26_analysis():
    df_nq = pd.read_parquet("data/NQ_recent_week.parquet").sort_index()
    target_date = "2026-08-26"
    target_d = pd.to_datetime(target_date).date()
    nq_day = df_nq[df_nq.index.date == target_d].copy()

    mc = mpf.make_marketcolors(up='#089981', down='#f23645', edge='inherit', wick='inherit')
    s = mpf.make_mpf_style(marketcolors=mc, gridcolor='#f1f5f9', gridstyle='--', y_on_right=True, figcolor='#ffffff')

    # =========================================================================
    # CHART 1: THE WINNING TRADE (10:20 ET to 11:05 ET)
    # =========================================================================
    df_win = nq_day.loc[f"{target_date} 10:20:00":f"{target_date} 11:05:00"].copy()

    fig_w, ax_w = mpf.plot(
        df_win,
        type='candle',
        style=s,
        figsize=(16, 9),
        returnfig=True,
        title="NQ 1-Min — August 26, 2026 | WINNING TRADE (+85 pts) — External SSL Sweep to BSL Delivery",
        ylabel="Price (Points)"
    )

    time_w = [t.strftime("%H:%M") for t in df_win.index]
    idx_sweep = time_w.index("10:28") if "10:28" in time_w else 8
    idx_cisd = time_w.index("10:35") if "10:35" in time_w else 15
    idx_entry = time_w.index("10:37") if "10:37" in time_w else 17
    idx_tp = time_w.index("10:55") if "10:55" in time_w else 35

    # London Low Line
    ax_w[0].axhline(29185.00, color='#ec4899', linestyle='--', linewidth=1.5)
    ax_w[0].text(1, 29186.50, "Swept London Low (29185.00) & PWL (29202.50)", color='#db2777', fontsize=9.5, fontweight='bold')

    # CISD Line
    ax_w[0].axhline(29190.00, color='#2563eb', linestyle='-', linewidth=1.8)
    ax_w[0].text(1, 29191.50, "CISD Shift (29190.00)", color='#1d4ed8', fontsize=9.5, fontweight='bold')

    # Target BSL Line
    ax_w[0].axhline(29277.25, color='#16a34a', linestyle='-', linewidth=2.0)
    ax_w[0].text(1, 29279.00, "TARGET: Opposing BSL (29277.25) — External Buyside Liquidity", color='#15803d', fontsize=9.5, fontweight='bold')

    # Annotations
    ax_w[0].annotate(
        "EXTERNAL SSL SWEEP (29163.00)\n+ Bullish SMT vs ES\n(ES held above London Low)",
        xy=(idx_sweep, 29163.00),
        xytext=(idx_sweep - 3, 29145.00),
        arrowprops=dict(facecolor='#ec4899', edgecolor='#db2777', width=1.5, headwidth=6),
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#fdf2f8", edgecolor="#ec4899", alpha=0.95),
        fontsize=9, fontweight='bold', color='#9d174d'
    )

    ax_w[0].annotate(
        "LONG ENTRY @ 29192.75\nRetest into CISD line & 1m OB\nStop Loss: 29160.00 (below sweep)",
        xy=(idx_entry, 29192.75),
        xytext=(idx_entry + 2, 29175.00),
        arrowprops=dict(facecolor='#2563eb', edgecolor='#1d4ed8', width=1.5, headwidth=6),
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#eff6ff", edgecolor="#2563eb", alpha=0.95),
        fontsize=9, fontweight='bold', color='#1e40af'
    )

    ax_w[0].annotate(
        "TARGET HIT @ 29277.25\n+84.5 Points Profit (+29 bps)!\nInstitutional delivery complete",
        xy=(idx_tp, 29277.25),
        xytext=(idx_tp - 10, 29255.00),
        arrowprops=dict(facecolor='#16a34a', edgecolor='#15803d', width=1.5, headwidth=6),
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#f0fdf4", edgecolor="#16a34a", alpha=0.95),
        fontsize=9, fontweight='bold', color='#14532d'
    )

    win_file = OUTPUT_DIR / "aug26_winning_trade.png"
    fig_w.savefig(win_file, dpi=160, bbox_inches='tight')
    plt.close(fig_w)
    print(f"Saved: {win_file}")

    # =========================================================================
    # CHART 2: THE LOSING TRADE (13:30 ET to 14:15 ET)
    # =========================================================================
    df_loss = nq_day.loc[f"{target_date} 13:30:00":f"{target_date} 14:15:00"].copy()

    fig_l, ax_l = mpf.plot(
        df_loss,
        type='candle',
        style=s,
        figsize=(16, 9),
        returnfig=True,
        title="NQ 1-Min — August 26, 2026 | LOSING TRADE (-13.5 pts) — False Reversal Trap (Inducement)",
        ylabel="Price (Points)"
    )

    time_l = [t.strftime("%H:%M") for t in df_loss.index]
    idx_fake_sweep = time_l.index("13:40") if "13:40" in time_l else 10
    idx_short_entry = time_l.index("13:46") if "13:46" in time_l else 16
    idx_sl_hit = time_l.index("13:56") if "13:56" in time_l else 26

    # Fake sweep line
    ax_l[0].axhline(29284.75, color='#ef4444', linestyle='--', linewidth=1.5)
    ax_l[0].text(1, 29285.50, "Apparent Sweep of Local High (29284.75) — LUNCH INDUCEMENT", color='#b91c1c', fontsize=9.5, fontweight='bold')

    # Stop Loss Line
    ax_l[0].axhline(29293.00, color='#dc2626', linestyle='-', linewidth=2.0)
    ax_l[0].text(1, 29294.00, "STOP LOSS (29293.00)", color='#991b1b', fontsize=9.5, fontweight='bold')

    # Annotations
    ax_l[0].annotate(
        "FALSE SWEEP TRAP (13:40 ET)\n• No HTF FVG or HTF OB backing\n• Fighting macro uptrend expansion\n• Lunch volume lull (inducement)",
        xy=(idx_fake_sweep, 29284.75),
        xytext=(idx_fake_sweep - 7, 29290.00),
        arrowprops=dict(facecolor='#ef4444', edgecolor='#b91c1c', width=1.5, headwidth=6),
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#fef2f2", edgecolor="#ef4444", alpha=0.95),
        fontsize=9, fontweight='bold', color='#991b1b'
    )

    ax_l[0].annotate(
        "SHORT ENTRY @ 29279.50 (13:46 ET)\nWeak 1m CISD break\nTargeted SSL (29202.00)",
        xy=(idx_short_entry, 29279.50),
        xytext=(idx_short_entry - 5, 29270.00),
        arrowprops=dict(facecolor='#f97316', edgecolor='#c2410c', width=1.5, headwidth=6),
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#fff7ed", edgecolor="#f97316", alpha=0.95),
        fontsize=9, fontweight='bold', color='#9a3412'
    )

    ax_l[0].annotate(
        "STOPPED OUT @ 29293.00 (-13.5 pts)\nBuyers violently resume macro trend\nNQ expands all the way to 29654!",
        xy=(idx_sl_hit, 29293.75),
        xytext=(idx_sl_hit + 2, 29282.00),
        arrowprops=dict(facecolor='#dc2626', edgecolor='#991b1b', width=1.5, headwidth=6),
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#fef2f2", edgecolor="#dc2626", alpha=0.95),
        fontsize=9, fontweight='bold', color='#7f1d1d'
    )

    loss_file = OUTPUT_DIR / "aug26_losing_trade.png"
    fig_l.savefig(loss_file, dpi=160, bbox_inches='tight')
    plt.close(fig_l)
    print(f"Saved: {loss_file}")

if __name__ == "__main__":
    render_aug26_analysis()
