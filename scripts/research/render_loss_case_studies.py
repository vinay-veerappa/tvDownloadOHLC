"""
Render Loss Case Studies for Forensic Analysis:
1. Case Study 1: August 27, 2026 (09:35 to 10:15 ET / 08:35 to 09:15 CT)
   - Fake breakout to 29,605.00 -> 180-point collapse to 29,423.75!
   - Why it failed: Trapped buyers into 1H Bearish OB, unanchored 09:45 anomaly.

2. Case Study 2: August 24, 2026 (09:50 to 10:25 ET / 08:50 to 09:25 CT)
   - Premature bottom trap: Bounce to 29,036.00 -> Secondary flush to 28,953.50!
   - Why it failed: Buying before intermediate 5m CISD confirmation.
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

def render_losses():
    df_nq = pd.read_parquet("data/NQ_recent_week.parquet").sort_index()

    mc = mpf.make_marketcolors(up='#089981', down='#f23645', edge='inherit', wick='inherit')
    s = mpf.make_mpf_style(marketcolors=mc, gridcolor='#f1f5f9', gridstyle='--', y_on_right=True, figcolor='#ffffff')

    # =========================================================================
    # LOSS 1: AUGUST 27 (09:35 to 10:15 ET) — The 09:45 Whipsaw Trap
    # =========================================================================
    aug27 = df_nq[df_nq.index.date == pd.to_datetime("2026-08-27").date()]
    df_l1 = aug27.loc["2026-08-27 09:35:00":"2026-08-27 10:15:00"].copy()

    fig_1, ax_1 = mpf.plot(
        df_l1,
        type='candle',
        style=s,
        figsize=(16, 9),
        returnfig=True,
        title="NQ 1-Min — August 27, 2026 | LOSS CASE STUDY 1: The 09:45 Breakout Trap (-80 pts)",
        ylabel="Price (Points)"
    )

    t1 = [t.strftime("%H:%M") for t in df_l1.index]
    idx_trap_top = t1.index("09:45") if "09:45" in t1 else 10
    idx_long_entry = t1.index("09:48") if "09:48" in t1 else 13
    idx_dump_bot = t1.index("09:58") if "09:58" in t1 else 23

    # High Line: 29605.00
    ax_1[0].axhline(29605.00, color='#ef4444', linestyle='--', linewidth=1.5)
    ax_1[0].text(1, 29607.00, "Trap High (29605.00) — Headfaked Breakout", color='#b91c1c', fontsize=9.5, fontweight='bold')

    # Low Line: 29423.75
    ax_1[0].axhline(29423.75, color='#dc2626', linestyle='-', linewidth=2.0)
    ax_1[0].text(1, 29426.00, "Flush Low (29423.75) — 181-Point Violent Dump", color='#991b1b', fontsize=9.5, fontweight='bold')

    # Annotations
    ax_1[0].annotate(
        "PREMATURE LONG ENTRY (09:48 ET)\n• Bought 1m pullback @ 29540.00\n• Trapped inside 09:45 macro anomaly window\n• Targeted PDH (29654.75)",
        xy=(idx_long_entry, 29540.00),
        xytext=(idx_long_entry - 6, 29575.00),
        arrowprops=dict(facecolor='#f97316', edgecolor='#c2410c', width=1.5, headwidth=6),
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#fff7ed", edgecolor="#f97316", alpha=0.95),
        fontsize=9, fontweight='bold', color='#9a3412'
    )

    ax_1[0].annotate(
        "STOPPED OUT & FLUSHED (-80 pts)\n• Price collapsed 181 pts in 10 minutes\n• Sliced right through 29500 & 29450\n• Stopped out at 29460.00!",
        xy=(idx_dump_bot, 29423.75),
        xytext=(idx_dump_bot - 10, 29460.00),
        arrowprops=dict(facecolor='#dc2626', edgecolor='#991b1b', width=1.5, headwidth=6),
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#fef2f2", edgecolor="#dc2626", alpha=0.95),
        fontsize=9, fontweight='bold', color='#7f1d1d'
    )

    f1 = OUTPUT_DIR / "loss_case1_aug27.png"
    fig_1.savefig(f1, dpi=160, bbox_inches='tight')
    plt.close(fig_1)
    print(f"Saved: {f1}")

    # =========================================================================
    # LOSS 2: AUGUST 24 (09:50 to 10:30 ET) — Premature Bottom Sweep Trap
    # =========================================================================
    aug24 = df_nq[df_nq.index.date == pd.to_datetime("2026-08-24").date()]
    df_l2 = aug24.loc["2026-08-24 09:50:00":"2026-08-24 10:30:00"].copy()

    fig_2, ax_2 = mpf.plot(
        df_l2,
        type='candle',
        style=s,
        figsize=(16, 9),
        returnfig=True,
        title="NQ 1-Min — August 24, 2026 | LOSS CASE STUDY 2: Premature Bottom Trap (-45 pts)",
        ylabel="Price (Points)"
    )

    t2 = [t.strftime("%H:%M") for t in df_l2.index]
    idx_fake_bottom = t2.index("09:55") if "09:55" in t2 else 5
    idx_fake_entry = t2.index("09:58") if "09:58" in t2 else 8
    idx_secondary_flush = t2.index("10:09") if "10:09" in t2 else 19

    # First Low Line: 28946.75
    ax_2[0].axhline(28946.75, color='#3b82f6', linestyle='--', linewidth=1.5)
    ax_2[0].text(1, 28948.50, "First Low of Day (28946.75)", color='#1d4ed8', fontsize=9.5, fontweight='bold')

    # Fake Bounce High: 29036.00
    ax_2[0].axhline(29036.00, color='#6366f1', linestyle=':', linewidth=1.5)
    ax_2[0].text(1, 29038.00, "1m Bounce High (29036.00) — False 1m CISD", color='#4338ca', fontsize=9, fontweight='bold')

    ax_2[0].annotate(
        "PREMATURE LONG ENTRY @ 29005.00 (09:58 ET)\n• Bought 1m retest after 80-pt bounce\n• Blind to continuing 5m Bearish trend\n• Stop Loss placed @ 28960.00",
        xy=(idx_fake_entry, 29005.00),
        xytext=(idx_fake_entry + 2, 29025.00),
        arrowprops=dict(facecolor='#f97316', edgecolor='#c2410c', width=1.5, headwidth=6),
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#fff7ed", edgecolor="#f97316", alpha=0.95),
        fontsize=9, fontweight='bold', color='#9a3412'
    )

    ax_2[0].annotate(
        "STOPPED OUT @ 28960.00 (-45 pts)\n• Secondary flush plunged to 28953.50\n• 5m candle was still expanding down\n• Real reversal only formed at 10:30 ET!",
        xy=(idx_secondary_flush, 28953.50),
        xytext=(idx_secondary_flush - 8, 28975.00),
        arrowprops=dict(facecolor='#dc2626', edgecolor='#991b1b', width=1.5, headwidth=6),
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#fef2f2", edgecolor="#dc2626", alpha=0.95),
        fontsize=9, fontweight='bold', color='#7f1d1d'
    )

    f2 = OUTPUT_DIR / "loss_case2_aug24.png"
    fig_2.savefig(f2, dpi=160, bbox_inches='tight')
    plt.close(fig_2)
    print(f"Saved: {f2}")

if __name__ == "__main__":
    render_losses()
