"""
Render Exact 1-Minute Charts for August 28, 2026 Matching User's TradingView Annotations
========================================================================================
1. Chart A: The Long Setup (09:05 CT to 09:45 CT / 10:05 ET to 10:45 ET)
   - Swept NY PM Low (29526.50) & 4H Low (29527.00)
   - "Entry at CISD" @ 29605.75
   - "Second stage entry" @ 29639.25 (OB) & Inv FVG (29635 - 29640)
   - Target: D-FVG @ 29811.75 (NO lookahead bias!)

2. Chart B: The Reversal Short (09:45 CT to 10:50 CT / 10:45 ET to 11:50 ET)
   - Tagged D-FVG @ 29811.75
   - "1m CISD" @ 29788.00
   - Purple Retest Box (29780 - 29788) & PWM OB (29770 - 29775)
   - Reversal Short Entry @ 29782 - 29785
   - Target Draw: PDH @ 29708.00 and discount targets
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

def render_exact_charts():
    df_nq = pd.read_parquet("data/NQ_recent_week.parquet").sort_index()

    target_date = "2026-08-28"
    target_d = pd.to_datetime(target_date).date()
    nq_day = df_nq[df_nq.index.date == target_d].copy()

    # Style
    mc = mpf.make_marketcolors(up='#089981', down='#f23645', edge='inherit', wick='inherit')
    s = mpf.make_mpf_style(marketcolors=mc, gridcolor='#f1f5f9', gridstyle='--', y_on_right=True, figcolor='#ffffff')

    # =========================================================================
    # CHART A: LONG SETUP (10:05 ET to 10:45 ET / 09:05 CT to 09:45 CT)
    # =========================================================================
    df_long = nq_day.loc[f"{target_date} 10:05:00":f"{target_date} 10:45:00"].copy()

    fig_a, ax_a = mpf.plot(
        df_long,
        type='candle',
        style=s,
        figsize=(16, 9),
        returnfig=True,
        title="NQ 1-Min — August 28, 2026 | The Bullish Setup (Matching media_1788408434865.png)",
        ylabel="Price (Points)"
    )

    # 1. Swept NY PM Low Line
    ax_a[0].axhline(29526.50, color='#ec4899', linestyle='--', linewidth=1.5)
    ax_a[0].text(1, 29523.50, "Swept NY PM Low (29526.50) & 4H Low", color='#db2777', fontsize=9.5, fontweight='bold')

    # 2. CISD Line: 29605.75
    ax_a[0].axhline(29605.75, color='#2563eb', linestyle='-', linewidth=1.8)
    ax_a[0].text(1, 29607.50, "CISD (29605.75)", color='#1d4ed8', fontsize=9.5, fontweight='bold')

    # 3. Order Block (OB) Line: 29639.25
    ax_a[0].axhline(29639.25, color='#2563eb', linestyle='--', linewidth=1.5)
    ax_a[0].text(1, 29641.00, "OB (29639.25)", color='#1d4ed8', fontsize=9.5, fontweight='bold')

    # 4. Target D-FVG Line at top: 29811.75
    # (Off the top of this zoom, but labeled as destination)
    time_list_a = [t.strftime("%H:%M") for t in df_long.index]
    idx_dump = time_list_a.index("10:14") if "10:14" in time_list_a else 9
    idx_cisd_touch = time_list_a.index("10:21") if "10:21" in time_list_a else 16
    idx_ob_touch = time_list_a.index("10:28") if "10:28" in time_list_a else 23

    # Callout: Entry at CISD
    ax_a[0].annotate(
        "Entry at CISD\n(29605.75)",
        xy=(idx_cisd_touch, 29605.75),
        xytext=(idx_cisd_touch + 3, 29580.00),
        arrowprops=dict(facecolor='#2563eb', edgecolor='#1d4ed8', width=1.5, headwidth=6),
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#eff6ff", edgecolor="#2563eb", alpha=0.95),
        fontsize=9.5, fontweight='bold', color='#1e40af'
    )

    # Purple Box: Inv FVG (29635 - 29640)
    rect_fvg = Rectangle((idx_cisd_touch + 3, 29635.0), 9.0, 5.0,
                         facecolor='#a855f7', alpha=0.3, edgecolor='#9333ea', linestyle='--')
    ax_a[0].add_patch(rect_fvg)
    ax_a[0].text(idx_cisd_touch + 4, 29642.50, "Inv FVG (29635.00 - 29640.00)", color='#7e22ce', fontsize=8.5, fontweight='bold')

    # Callout: Second Stage Entry
    ax_a[0].annotate(
        "Second stage entry\nRetest into OB (29639.25) & Inv FVG",
        xy=(idx_ob_touch, 29637.00),
        xytext=(idx_ob_touch + 2, 29615.00),
        arrowprops=dict(facecolor='#9333ea', edgecolor='#6b21a8', width=1.5, headwidth=6),
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#faf5ff", edgecolor="#9333ea", alpha=0.95),
        fontsize=9.5, fontweight='bold', color='#581c87'
    )

    # Target callout
    ax_a[0].text(len(df_long) - 15, 29740.00, "Target: D-FVG (Daily FVG) @ 29811.75\n(Pre-existing HTF magnet)",
                 bbox=dict(boxstyle="round,pad=0.5", facecolor="#fdf4ff", edgecolor="#d946ef"),
                 fontsize=9.5, fontweight='bold', color='#86198f')

    chart_a_file = OUTPUT_DIR / "aug28_exact_long_entry.png"
    fig_a.savefig(chart_a_file, dpi=160, bbox_inches='tight')
    plt.close(fig_a)
    print(f"Saved Chart A: {chart_a_file}")

    # =========================================================================
    # CHART B: REVERSAL SHORT (10:50 ET to 11:45 ET / 09:50 CT to 10:45 CT)
    # =========================================================================
    df_rev = nq_day.loc[f"{target_date} 10:50:00":f"{target_date} 11:45:00"].copy()

    fig_b, ax_b = mpf.plot(
        df_rev,
        type='candle',
        style=s,
        figsize=(16, 9),
        returnfig=True,
        title="NQ 1-Min — August 28, 2026 | The Reversal Short Setup (Matching media_1788408228776.png)",
        ylabel="Price (Points)"
    )

    time_list_b = [t.strftime("%H:%M") for t in df_rev.index]
    idx_top = time_list_b.index("11:02") if "11:02" in time_list_b else 12
    idx_cisd_rev = time_list_b.index("11:08") if "11:08" in time_list_b else 18
    idx_retest_rev = time_list_b.index("11:27") if "11:27" in time_list_b else 37

    # 1. Target D-FVG Tagged at Top: 29811.75
    ax_b[0].axhline(29811.75, color='#a855f7', linestyle='-', linewidth=2.0)
    ax_b[0].text(1, 29813.50, "D-FVG Target Tagged (29811.75) -> Institutional Exhaustion / Reversal Zone", color='#7e22ce', fontsize=9.5, fontweight='bold')

    # 2. 1m CISD Shift: 29788.00
    ax_b[0].axhline(29788.00, color='#2563eb', linestyle='-', linewidth=1.8)
    ax_b[0].text(1, 29789.50, "1m CISD (29788.00)", color='#1d4ed8', fontsize=9.5, fontweight='bold')

    # 3. Purple Box: Retest Zone (29780.00 - 29788.00)
    rect_rev1 = Rectangle((idx_cisd_rev + 3, 29780.0), 18.0, 8.0,
                          facecolor='#a855f7', alpha=0.3, edgecolor='#9333ea', linestyle='--')
    ax_b[0].add_patch(rect_rev1)
    ax_b[0].text(idx_cisd_rev + 4, 29784.0, "OB / FVG Retest Zone (29780 - 29788)", color='#581c87', fontsize=8.5, fontweight='bold')

    # 4. PWM Line (Previous Week Midpoint) / Lower OB: 29770 - 29775
    rect_rev2 = Rectangle((idx_cisd_rev + 8, 29770.0), 13.0, 5.0,
                          facecolor='#e879f9', alpha=0.25, edgecolor='#c026d3', linestyle=':')
    ax_b[0].add_patch(rect_rev2)
    ax_b[0].text(idx_cisd_rev + 9, 29771.5, "PWM / OB (29770 - 29775)", color='#86198f', fontsize=8.5, fontweight='bold')

    # 5. PDH Line: 29708.00
    ax_b[0].axhline(29708.00, color='#3b82f6', linestyle=':', linewidth=1.5)
    ax_b[0].text(1, 29709.50, "PDH (29708.00) - Primary Downside Target", color='#2563eb', fontsize=9.5, fontweight='bold')

    # Callout: Short Entry
    ax_b[0].annotate(
        "REVERSAL SHORT ENTRY @ 29782 - 29785\nUpper Wicks Rejecting OB/FVG Box\nStop Loss above 29811.75 D-FVG",
        xy=(idx_retest_rev, 29785.00),
        xytext=(idx_retest_rev - 8, 29798.00),
        arrowprops=dict(facecolor='#ef4444', edgecolor='#b91c1c', width=1.5, headwidth=6),
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#fef2f2", edgecolor="#ef4444", alpha=0.95),
        fontsize=9, fontweight='bold', color='#991b1b'
    )

    # Waterfall Downside Callout
    ax_b[0].annotate(
        "Waterfall Dump to PDH (29708.00)\n& Beyond (29665.00)\n+115 points profit!",
        xy=(len(df_rev) - 4, 29670.00),
        xytext=(len(df_rev) - 14, 29720.00),
        arrowprops=dict(facecolor='#ef4444', edgecolor='#b91c1c', width=1.5, headwidth=6),
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#fff1f2", edgecolor="#f43f5e", alpha=0.95),
        fontsize=9, fontweight='bold', color='#881337'
    )

    chart_b_file = OUTPUT_DIR / "aug28_exact_reversal_short.png"
    fig_b.savefig(chart_b_file, dpi=160, bbox_inches='tight')
    plt.close(fig_b)
    print(f"Saved Chart B: {chart_b_file}")

if __name__ == "__main__":
    render_exact_charts()
