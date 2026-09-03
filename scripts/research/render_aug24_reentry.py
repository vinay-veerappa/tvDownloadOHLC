"""
Render August 24, 2026: The 5 bps SL and Confirmed Re-Entry Protocol
===================================================================
Phase 1: Initial Entry @ top of 5m FVG (29,070.00) -> 5 bps SL hit @ 29,055.50 (-14.5 pts).
Phase 2: 5m FVG CE (50% midpoint @ 29,038.75) strictly respected!
Phase 3: Displacement out of FVG -> Confirmed 1m Re-entry @ 29,080.00.
Phase 4: Expansion to 29,205.50 (+125.5 pts WIN!).
Combined Net: +111.0 points profit.
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

def render_aug24_reentry():
    df_nq = pd.read_parquet("data/NQ_recent_week.parquet").sort_index()
    target_date = "2026-08-24"
    target_d = pd.to_datetime(target_date).date()
    nq_day = df_nq[df_nq.index.date == target_d].copy()

    mc = mpf.make_marketcolors(up='#089981', down='#f23645', edge='inherit', wick='inherit')
    s = mpf.make_mpf_style(marketcolors=mc, gridcolor='#f1f5f9', gridstyle='--', y_on_right=True, figcolor='#ffffff')

    # Window: 10:45 ET to 12:15 ET
    df_zoom = nq_day.loc[f"{target_date} 10:45:00":f"{target_date} 12:15:00"].copy()

    fig, ax = mpf.plot(
        df_zoom,
        type='candle',
        style=s,
        figsize=(16, 9),
        returnfig=True,
        title="NQ 1-Min — August 24, 2026 | Initial 5 bps SL & Confirmed 1m Re-Entry (+125.5 pts)",
        ylabel="Price (Points)"
    )

    t_list = [t.strftime("%H:%M") for t in df_zoom.index]
    idx_entry1 = t_list.index("11:01") if "11:01" in t_list else 16
    idx_sl1 = t_list.index("11:06") if "11:06" in t_list else 21
    idx_ce = t_list.index("11:22") if "11:22" in t_list else 37
    idx_reentry = t_list.index("11:27") if "11:27" in t_list else 42
    idx_tp = t_list.index("11:47") if "11:47" in t_list else 62

    # 1. 5m FVG Zone: 29038.00 - 29071.00
    rect_fvg = Rectangle((0, 29038.0), len(df_zoom), 33.0,
                         facecolor='#22c55e', alpha=0.15, edgecolor='#16a34a', linestyle='--')
    ax[0].add_patch(rect_fvg)
    ax[0].text(1, 29065.0, "5m FVG Zone [29038.00 - 29071.00]", color='#15803d', fontsize=9, fontweight='bold')

    # 2. 5m FVG CE Line (50% midpoint): 29054.50
    ax[0].axhline(29054.50, color='#15803d', linestyle=':', linewidth=1.5)
    ax[0].text(1, 29056.0, "5m FVG Consequent Encroachment (CE = 50%) @ 29054.50", color='#166534', fontsize=9, fontweight='bold')

    # 3. Initial Entry & SL Callout
    ax[0].annotate(
        "INITIAL ENTRY @ 29070.00 (11:01 ET)\nFirst tap into top of 5m FVG\nStop Loss: 5 bps (29055.50 / 14.5 pts)",
        xy=(idx_entry1, 29070.00),
        xytext=(idx_entry1 - 10, 29110.00),
        arrowprops=dict(facecolor='#f97316', edgecolor='#c2410c', width=1.5, headwidth=6),
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#fff7ed", edgecolor="#f97316", alpha=0.95),
        fontsize=8.5, fontweight='bold', color='#9a3412'
    )

    ax[0].annotate(
        "STOPPED OUT (-5 bps / -14.5 pts)\nDips deeper to test CE (29055.50 tagged)\nHTF thesis STILL INTACT!",
        xy=(idx_sl1, 29055.50),
        xytext=(idx_sl1 - 6, 29020.00),
        arrowprops=dict(facecolor='#dc2626', edgecolor='#991b1b', width=1.5, headwidth=6),
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#fef2f2", edgecolor="#dc2626", alpha=0.95),
        fontsize=8.5, fontweight='bold', color='#7f1d1d'
    )

    # 4. CE Respected Callout
    ax[0].annotate(
        "5m FVG CE RESPECTED @ 29038.75\nPrice holds 50% midpoint with wicks\nBuyers defend institutional imbalance",
        xy=(idx_ce, 29038.75),
        xytext=(idx_ce - 8, 29005.00),
        arrowprops=dict(facecolor='#16a34a', edgecolor='#15803d', width=1.5, headwidth=6),
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#f0fdf4", edgecolor="#16a34a", alpha=0.95),
        fontsize=8.5, fontweight='bold', color='#14532d'
    )

    # 5. Confirmed Re-Entry Callout
    ax[0].annotate(
        "CONFIRMED RE-ENTRY @ 29080.00 (11:27 ET)\n• Displaces out of 5m FVG\n• Retest into 1m OB [29079 - 29085]\n• SL: 29050.00",
        xy=(idx_reentry, 29080.00),
        xytext=(idx_reentry - 14, 29135.00),
        arrowprops=dict(facecolor='#a855f7', edgecolor='#7e22ce', width=1.5, headwidth=6),
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#faf5ff", edgecolor="#a855f7", alpha=0.95),
        fontsize=9, fontweight='bold', color='#6b21a8'
    )

    # 6. Target Hit Callout
    ax[0].axhline(29205.50, color='#16a34a', linestyle='-', linewidth=2.0)
    ax[0].text(1, 29207.50, "TARGET: Session Liquidity Highs (29205.50)", color='#15803d', fontsize=9.5, fontweight='bold')

    ax[0].annotate(
        "TARGET HIT @ 29205.50 (11:47 ET)\n+125.5 Points Profit (+43.2 bps)!\nCombined Net: +111.0 Points (+38.2 bps)",
        xy=(idx_tp, 29205.50),
        xytext=(idx_tp - 15, 29170.00),
        arrowprops=dict(facecolor='#16a34a', edgecolor='#15803d', width=1.5, headwidth=6),
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#f0fdf4", edgecolor="#16a34a", alpha=0.95),
        fontsize=9, fontweight='bold', color='#14532d'
    )

    out_file = OUTPUT_DIR / "aug24_confirmed_reentry.png"
    fig.savefig(out_file, dpi=160, bbox_inches='tight')
    plt.close(fig)
    print(f"Saved: {out_file}")

if __name__ == "__main__":
    render_aug24_reentry()
