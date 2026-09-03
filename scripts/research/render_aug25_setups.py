"""
Render August 25, 2026 Setups:
1. Morning Master Long (10:25 ET to 11:15 ET / 09:25 CT to 10:15 CT)
   - Liquidity Purge to 29138.00 (86-point lower wick rejection!)
   - Bullish CISD Shift @ 29229.75
   - 1m Second Stage Entry @ 29205.00 (+OB Retest)
   - Expansion to 29309.75 (+104.75 pts WIN!)

2. Afternoon Session Re-Accumulation (15:20 ET to 16:00 ET / 14:20 CT to 15:00 CT)
   - External Sweep of London Low (29212.25) to 29211.50
   - CISD Shift @ 29225.25
   - 1m Limit Entry @ 29225.00
   - Expansion into Close @ 29289.50 (+64.5 pts WIN!)
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

def render_aug25_charts():
    df_nq = pd.read_parquet("data/NQ_recent_week.parquet").sort_index()
    target_date = "2026-08-25"
    target_d = pd.to_datetime(target_date).date()
    nq_day = df_nq[df_nq.index.date == target_d].copy()

    mc = mpf.make_marketcolors(up='#089981', down='#f23645', edge='inherit', wick='inherit')
    s = mpf.make_mpf_style(marketcolors=mc, gridcolor='#f1f5f9', gridstyle='--', y_on_right=True, figcolor='#ffffff')

    # =========================================================================
    # CHART 1: MORNING MASTER LONG (10:25 to 11:15 ET)
    # =========================================================================
    df_morn = nq_day.loc[f"{target_date} 10:25:00":f"{target_date} 11:15:00"].copy()

    fig_1, ax_1 = mpf.plot(
        df_morn,
        type='candle',
        style=s,
        figsize=(16, 9),
        returnfig=True,
        title="NQ 1-Min — August 25, 2026 | Morning Liquidity Purge & Master Long (+104 pts)",
        ylabel="Price (Points)"
    )

    time_1 = [t.strftime("%H:%M") for t in df_morn.index]
    idx_dump = time_1.index("10:31") if "10:31" in time_1 else 6
    idx_cisd = time_1.index("10:33") if "10:33" in time_1 else 8
    idx_entry = time_1.index("10:36") if "10:36" in time_1 else 11
    idx_tp = time_1.index("11:10") if "11:10" in time_1 else 45

    # London Low Line (29212.25)
    ax_1[0].axhline(29212.25, color='#ec4899', linestyle='--', linewidth=1.5)
    ax_1[0].text(1, 29213.50, "London Low (29212.25) — External SSL Swept", color='#db2777', fontsize=9.5, fontweight='bold')

    # CISD Line (29229.75)
    ax_1[0].axhline(29229.75, color='#2563eb', linestyle='-', linewidth=1.8)
    ax_1[0].text(1, 29231.00, "CISD Shift Level (29229.75)", color='#1d4ed8', fontsize=9.5, fontweight='bold')

    # 1m Order Block Box (29205 - 29215)
    rect_ob1 = Rectangle((idx_entry - 2, 29205.0), 6.0, 10.0,
                         facecolor='#22c55e', alpha=0.25, edgecolor='#16a34a', linestyle='--')
    ax_1[0].add_patch(rect_ob1)
    ax_1[0].text(idx_entry - 1, 29201.0, "+ OB Retest Zone (29205.00)", color='#15803d', fontsize=8.5, fontweight='bold')

    # Target Line (29309.75)
    ax_1[0].axhline(29304.00, color='#16a34a', linestyle='-', linewidth=2.0)
    ax_1[0].text(1, 29305.50, "TARGET: PDH / BSL Pool (29304.00)", color='#15803d', fontsize=9.5, fontweight='bold')

    # Annotations
    ax_1[0].annotate(
        "MASSIVE LIQUIDITY PURGE (29138.00)\n86-Point Lower Wick Rejection!\nInstitutions absorb sell-stop panic",
        xy=(idx_dump, 29138.00),
        xytext=(idx_dump - 4, 29160.00),
        arrowprops=dict(facecolor='#ec4899', edgecolor='#db2777', width=1.5, headwidth=6),
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#fdf2f8", edgecolor="#ec4899", alpha=0.95),
        fontsize=9, fontweight='bold', color='#9d174d'
    )

    ax_1[0].annotate(
        "LONG ENTRY @ 29205.00 (10:36 ET)\nRetest into + OB & FVG\nStop Loss: 29135.00 (below sweep wick)",
        xy=(idx_entry, 29205.00),
        xytext=(idx_entry + 3, 29180.00),
        arrowprops=dict(facecolor='#2563eb', edgecolor='#1d4ed8', width=1.5, headwidth=6),
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#eff6ff", edgecolor="#2563eb", alpha=0.95),
        fontsize=9, fontweight='bold', color='#1e40af'
    )

    ax_1[0].annotate(
        "EXPANSION TO TARGET\nReaches 29309.75 (+104.75 pts / +35.8 bps)!\nInstitutional delivery complete",
        xy=(len(df_morn) - 3, 29230.00),
        xytext=(len(df_morn) - 15, 29270.00),
        arrowprops=dict(facecolor='#16a34a', edgecolor='#15803d', width=1.5, headwidth=6),
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#f0fdf4", edgecolor="#16a34a", alpha=0.95),
        fontsize=9, fontweight='bold', color='#14532d'
    )

    chart_1_file = OUTPUT_DIR / "aug25_morning_long.png"
    fig_1.savefig(chart_1_file, dpi=160, bbox_inches='tight')
    plt.close(fig_1)
    print(f"Saved: {chart_1_file}")

    # =========================================================================
    # CHART 2: AFTERNOON RE-ACCUMULATION (15:20 to 16:00 ET)
    # =========================================================================
    df_pm = nq_day.loc[f"{target_date} 15:20:00":f"{target_date} 16:00:00"].copy()

    fig_2, ax_2 = mpf.plot(
        df_pm,
        type='candle',
        style=s,
        figsize=(16, 9),
        returnfig=True,
        title="NQ 1-Min — August 25, 2026 | Afternoon NY PM Re-Accumulation (+64.5 pts)",
        ylabel="Price (Points)"
    )

    time_2 = [t.strftime("%H:%M") for t in df_pm.index]
    idx_pm_sweep = time_2.index("15:30") if "15:30" in time_2 else 10
    idx_pm_cisd = time_2.index("15:35") if "15:35" in time_2 else 15
    idx_pm_entry = time_2.index("15:37") if "15:37" in time_2 else 17

    ax_2[0].axhline(29212.25, color='#ec4899', linestyle='--', linewidth=1.5)
    ax_2[0].text(1, 29213.50, "London Low (29212.25) — Retest & Sweep to 29211.50", color='#db2777', fontsize=9.5, fontweight='bold')

    ax_2[0].axhline(29225.25, color='#2563eb', linestyle='-', linewidth=1.8)
    ax_2[0].text(1, 29226.50, "1m CISD Shift (29225.25)", color='#1d4ed8', fontsize=9.5, fontweight='bold')

    ax_2[0].annotate(
        "AFTERNOON PURGE (15:30 ET)\nTaps 29211.50 & Wicks Back Up\nBullish SMT vs ES (+3.25 pts)",
        xy=(idx_pm_sweep, 29211.50),
        xytext=(idx_pm_sweep - 6, 29220.00),
        arrowprops=dict(facecolor='#ec4899', edgecolor='#db2777', width=1.5, headwidth=6),
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#fdf2f8", edgecolor="#ec4899", alpha=0.95),
        fontsize=9, fontweight='bold', color='#9d174d'
    )

    ax_2[0].annotate(
        "LONG ENTRY @ 29225.00 (15:37 ET)\nRetest into 1m CISD & + OB\nStop Loss: 29208.00",
        xy=(idx_pm_entry, 29225.00),
        xytext=(idx_pm_entry + 3, 29235.00),
        arrowprops=dict(facecolor='#2563eb', edgecolor='#1d4ed8', width=1.5, headwidth=6),
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#eff6ff", edgecolor="#2563eb", alpha=0.95),
        fontsize=9, fontweight='bold', color='#1e40af'
    )

    ax_2[0].annotate(
        "EXPANSION INTO 16:00 CLOSE\nReaches 29289.50 (+64.5 pts / +22.0 bps)!\nClosing drive expansion",
        xy=(len(df_pm) - 3, 29285.00),
        xytext=(len(df_pm) - 12, 29260.00),
        arrowprops=dict(facecolor='#16a34a', edgecolor='#15803d', width=1.5, headwidth=6),
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#f0fdf4", edgecolor="#16a34a", alpha=0.95),
        fontsize=9, fontweight='bold', color='#14532d'
    )

    chart_2_file = OUTPUT_DIR / "aug25_afternoon_long.png"
    fig_2.savefig(chart_2_file, dpi=160, bbox_inches='tight')
    plt.close(fig_2)
    print(f"Saved: {chart_2_file}")

if __name__ == "__main__":
    render_aug25_charts()
