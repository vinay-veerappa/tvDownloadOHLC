"""
Render August 24, 2026 Exact User Master Long Setup
===================================================
Matches user's TradingView chart (media_1788416448294.png):
1. 09:30 Drop was untradable / No Trade.
2. +OB H1 @ 28,990.00 supported the accumulation base.
3. 5m Displacement & CISD 5m @ 29,025.00.
4. 5m FVG created [29,038.00 - 29,071.00].
5. Retest @ 11:22 ET: "5m FVG CE respected." (dips to 29,038.75, rejects).
6. 11:27 ET: "5m FVG exit and entry at 1m" @ 29,080.00.
7. Expansion to 29,205.50+ (+125.5 pts WIN!).
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

def render_aug24_user_setup():
    df_nq = pd.read_parquet("data/NQ_recent_week.parquet").sort_index()
    target_date = "2026-08-24"
    target_d = pd.to_datetime(target_date).date()
    nq_day = df_nq[df_nq.index.date == target_d].copy()

    mc = mpf.make_marketcolors(up='#089981', down='#f23645', edge='inherit', wick='inherit')
    s = mpf.make_mpf_style(marketcolors=mc, gridcolor='#f1f5f9', gridstyle='--', y_on_right=True, figcolor='#ffffff')

    # Zoom window: 10:15 ET to 12:15 ET
    df_trade = nq_day.loc[f"{target_date} 10:15:00":f"{target_date} 12:15:00"].copy()

    fig, ax = mpf.plot(
        df_trade,
        type='candle',
        style=s,
        figsize=(16, 9),
        returnfig=True,
        title="NQ 1-Min — August 24, 2026 | User's Master Long: 5m FVG CE Respected to 1m Entry (+125 pts)",
        ylabel="Price (Points)"
    )

    time_list = [t.strftime("%H:%M") for t in df_trade.index]
    idx_cisd_5m = time_list.index("10:30") if "10:30" in time_list else 15
    idx_ce_test = time_list.index("11:22") if "11:22" in time_list else 67
    idx_1m_entry = time_list.index("11:27") if "11:27" in time_list else 72
    idx_tp = time_list.index("11:47") if "11:47" in time_list else 92

    # 1. +OB H1 Line: 28990.00
    ax[0].axhline(28990.00, color='#8b5cf6', linestyle='--', linewidth=1.5)
    ax[0].text(1, 28992.00, "+OB H1 (28990.00) — Macro Accumulation Base", color='#6d28d9', fontsize=9.5, fontweight='bold')

    # 2. CISD 5m Line: 29025.00
    ax[0].axhline(29025.00, color='#2563eb', linestyle='-', linewidth=1.8)
    ax[0].text(1, 29027.00, "CISD 5m (29025.00)", color='#1d4ed8', fontsize=9.5, fontweight='bold')

    # 3. Green Box: 5m FVG [29038.00 - 29071.00]
    rect_fvg = Rectangle((idx_cisd_5m, 29038.0), 55.0, 33.0,
                         facecolor='#22c55e', alpha=0.20, edgecolor='#16a34a', linestyle='--')
    ax[0].add_patch(rect_fvg)
    ax[0].text(idx_cisd_5m + 5, 29045.00, "5m FVG [29038.00 - 29071.00]", color='#15803d', fontsize=8.5, fontweight='bold')

    # 4. Purple Box: 1m Entry Zone @ 29075 - 29085
    rect_entry = Rectangle((idx_1m_entry - 2, 29075.0), 6.0, 10.0,
                           facecolor='#a855f7', alpha=0.35, edgecolor='#9333ea', linestyle='-')
    ax[0].add_patch(rect_entry)

    # 5. Target Line: 29205.50
    ax[0].axhline(29205.50, color='#16a34a', linestyle='-', linewidth=2.0)
    ax[0].text(1, 29207.50, "TARGET: Session Liquidity Highs (29205.50)", color='#15803d', fontsize=9.5, fontweight='bold')

    # Annotations
    ax[0].annotate(
        "5m FVG CE respected.\nPrice dips to 29038.75 (50% Consequent Encroachment)\nInstitutional buyers absorb sell pressure",
        xy=(idx_ce_test, 29038.75),
        xytext=(idx_ce_test - 18, 29000.00),
        arrowprops=dict(facecolor='#16a34a', edgecolor='#15803d', width=1.5, headwidth=6),
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#f0fdf4", edgecolor="#16a34a", alpha=0.95),
        fontsize=9, fontweight='bold', color='#14532d'
    )

    ax[0].annotate(
        "5m FVG exit and entry at 1m\nLimit Fill @ 29080.00 (11:27 ET)\nStop Loss: 29035.00 (below 5m FVG low)",
        xy=(idx_1m_entry, 29080.00),
        xytext=(idx_1m_entry - 20, 29115.00),
        arrowprops=dict(facecolor='#a855f7', edgecolor='#7e22ce', width=1.5, headwidth=6),
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#faf5ff", edgecolor="#a855f7", alpha=0.95),
        fontsize=9, fontweight='bold', color='#6b21a8'
    )

    ax[0].annotate(
        "TARGET HIT @ 29205.50 (11:47 ET)\n+125.5 Points Profit (+43.2 bps)!\nInstitutional delivery complete",
        xy=(idx_tp, 29205.50),
        xytext=(idx_tp - 15, 29165.00),
        arrowprops=dict(facecolor='#16a34a', edgecolor='#15803d', width=1.5, headwidth=6),
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#f0fdf4", edgecolor="#16a34a", alpha=0.95),
        fontsize=9, fontweight='bold', color='#14532d'
    )

    out_file = OUTPUT_DIR / "aug24_user_master_long.png"
    fig.savefig(out_file, dpi=160, bbox_inches='tight')
    plt.close(fig)
    print(f"Saved: {out_file}")

if __name__ == "__main__":
    render_aug24_user_setup()
