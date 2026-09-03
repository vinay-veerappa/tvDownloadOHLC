"""
Deep Dive Forensic Analysis: August 28, 2026
=============================================
Focuses exclusively on August 28, 2026 to systematically dissect:
1. What setups appeared throughout the session?
2. Which ones worked, which ones failed, and WHY?
3. Generates two pristine, publication-quality charts using mplfinance:
   - 5-Minute Overview (08:30 to 12:30 ET)
   - 1-Minute Execution Zoom (10:05 to 10:45 ET)
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle
import mplfinance as mpf

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

OUTPUT_DIR = Path("C:/Users/vinay/.gemini/antigravity/brain/4c21dcc0-89c9-42df-8e6a-fc48ef5552a9/scratch/charts")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def generate_deep_dive():
    df_nq = pd.read_parquet("data/NQ_recent_week.parquet").sort_index()
    df_es = pd.read_parquet("data/ES_recent_week.parquet").sort_index()

    target_date = "2026-08-28"
    target_d = pd.to_datetime(target_date).date()
    prev_d = pd.to_datetime("2026-08-27").date()

    # Prev Day NY PM (13:30 - 16:00 ET)
    nq_prev = df_nq[df_nq.index.date == prev_d]
    es_prev = df_es[df_es.index.date == prev_d]

    nq_pm = nq_prev[(nq_prev.index.strftime("%H%M") >= "1330") & (nq_prev.index.strftime("%H%M") <= "1600")]
    es_pm = es_prev[(es_prev.index.strftime("%H%M") >= "1330") & (es_prev.index.strftime("%H%M") <= "1600")]

    nq_pm_low = nq_pm["low"].min()
    es_pm_low = es_pm["low"].min()

    # Target Day 5m
    nq_day = df_nq[df_nq.index.date == target_d]
    nq_5m = nq_day.resample("5min").agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna()

    # 1. Generate 5-Minute Overview Chart (08:30 to 12:30 ET)
    t_start_5m = f"{target_date} 08:30:00"
    t_end_5m = f"{target_date} 12:30:00"
    df_plot_5m = nq_5m.loc[t_start_5m:t_end_5m].copy()

    # Custom TradingView Style
    mc = mpf.make_marketcolors(up='#089981', down='#f23645', edge='inherit', wick='inherit', volume='#089981')
    s = mpf.make_mpf_style(marketcolors=mc, gridcolor='#e2e8f0', gridstyle='--', y_on_right=True, figcolor='#ffffff')

    fig, ax = mpf.plot(
        df_plot_5m,
        type='candle',
        style=s,
        figsize=(16, 9),
        returnfig=True,
        title=f"NQ Futures (5-Min) — August 28, 2026 | Morning Session Forensic Overview",
        ylabel="Price (Points)",
        warn_too_much_data=1000
    )

    # Add Horizontal Key Levels
    # 1. Swept NY PM Low
    ax[0].axhline(nq_pm_low, color='#ec4899', linestyle='--', linewidth=1.5)
    ax[0].text(1, nq_pm_low - 4, f"Swept NY PM Low ({nq_pm_low:.2f})", color='#db2777', fontsize=10, fontweight='bold')

    # 2. CISD Level
    cisd_price = 29606.00
    ax[0].axhline(cisd_price, color='#ca8a04', linestyle='-', linewidth=1.5)
    ax[0].text(1, cisd_price + 3, f"CISD Shift Level ({cisd_price:.2f})", color='#ca8a04', fontsize=10, fontweight='bold')

    # 3. Target BSL
    bsl_price = 29811.75
    ax[0].axhline(bsl_price, color='#8b5cf6', linestyle=':', linewidth=2.0)
    ax[0].text(1, bsl_price + 3, f"Opposing BSL Target: NYAM High ({bsl_price:.2f}) -> Reversal Zone", color='#8b5cf6', fontsize=10, fontweight='bold')

    # Find integer index for x-axis annotations in mplfinance
    time_list_5m = [t.strftime("%H:%M") for t in df_plot_5m.index]
    
    # 10:15 bar is around index of 10:15
    idx_1015 = time_list_5m.index("10:15") if "10:15" in time_list_5m else 21
    idx_1020 = time_list_5m.index("10:20") if "10:20" in time_list_5m else 22
    idx_1030 = time_list_5m.index("10:30") if "10:30" in time_list_5m else 24
    idx_1100 = time_list_5m.index("11:00") if "11:00" in time_list_5m else 30

    # Annotate Sweep Pivot (10:15 ET)
    ax[0].annotate(
        "① LIQUIDITY SWEEP + SMT\nLow: 29505.00 sweeps NY PM Low\nES held +3.75 pts above level",
        xy=(idx_1015, 29505.00),
        xytext=(idx_1015 - 5, 29470.00),
        arrowprops=dict(facecolor='#f59e0b', edgecolor='#b45309', width=1.5, headwidth=6),
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#fef3c7", edgecolor="#f59e0b", alpha=0.95),
        fontsize=8.5, fontweight='bold', color='#92400e'
    )

    # Annotate CISD Shift (10:20 ET)
    ax[0].annotate(
        "② CISD SHIFT\nClose: 29644.75 > 29606.00\nBody displacement: +139 pts",
        xy=(idx_1020, 29644.75),
        xytext=(idx_1020 - 4, 29685.00),
        arrowprops=dict(facecolor='#ca8a04', edgecolor='#854d0e', width=1.5, headwidth=6),
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#fef9c3", edgecolor="#ca8a04", alpha=0.95),
        fontsize=8.5, fontweight='bold', color='#713f12'
    )

    # Retest Box (OB & iFVG)
    rect_5m = Rectangle((idx_1020, 29604.0), 3.0, 29635.0 - 29604.0,
                        facecolor='#a855f7', alpha=0.3, edgecolor='#9333ea', linestyle='--')
    ax[0].add_patch(rect_5m)
    ax[0].text(idx_1020 + 0.5, 29620.0, "③ 2nd Stage Retest:\nOB & iFVG", color='#6b21a8', fontsize=8, fontweight='bold')

    # Entry Marker
    ax[0].annotate(
        "ENTRY LONG @ 29617.50\nSL: 29602.50 (5 bps risk)\nTarget: 29811.75 (+194 pts)",
        xy=(idx_1020 + 0.5, 29617.50),
        xytext=(idx_1020 + 3, 29550.00),
        arrowprops=dict(facecolor='#22c55e', edgecolor='#15803d', width=2, headwidth=7),
        bbox=dict(boxstyle="round,pad=0.5", facecolor="#f0fdf4", edgecolor="#22c55e", alpha=0.95),
        fontsize=9, fontweight='bold', color='#14532d'
    )

    # Annotate Target Hit & Reversal
    ax[0].annotate(
        "④ BSL HIT @ 29811.75\nTarget Achieved -> Reversal Triggered!\nPrice dumped 200+ pts",
        xy=(idx_1100, 29811.75),
        xytext=(idx_1100 + 2, 29770.00),
        arrowprops=dict(facecolor='#8b5cf6', edgecolor='#6d28d9', width=1.5, headwidth=6),
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#faf5ff", edgecolor="#8b5cf6", alpha=0.95),
        fontsize=8.5, fontweight='bold', color='#581c87'
    )

    chart_file_5m = OUTPUT_DIR / "aug28_5m_overview.png"
    fig.savefig(chart_file_5m, dpi=160, bbox_inches='tight')
    plt.close(fig)
    print(f"Saved 5m chart: {chart_file_5m}")

    # 2. Generate 1-Minute Execution Zoom (10:05 to 10:45 ET)
    t_start_1m = f"{target_date} 10:05:00"
    t_end_1m = f"{target_date} 10:45:00"
    df_plot_1m = nq_day.loc[t_start_1m:t_end_1m].copy()

    fig1, ax1 = mpf.plot(
        df_plot_1m,
        type='candle',
        style=s,
        figsize=(16, 9),
        returnfig=True,
        title="NQ Futures (1-Min) — August 28, 2026 | Precision Execution Window (10:05 - 10:45 ET)",
        ylabel="Price (Points)",
        warn_too_much_data=1000
    )

    # Key Levels on 1m
    ax1[0].axhline(nq_pm_low, color='#ec4899', linestyle='--', linewidth=1.5)
    ax1[0].text(1, nq_pm_low - 3, f"Swept NY PM Low ({nq_pm_low:.2f})", color='#db2777', fontsize=9.5, fontweight='bold')

    ax1[0].axhline(cisd_price, color='#ca8a04', linestyle='-', linewidth=1.5)
    ax1[0].text(1, cisd_price + 2, f"CISD Level ({cisd_price:.2f})", color='#ca8a04', fontsize=9.5, fontweight='bold')

    time_list_1m = [t.strftime("%H:%M") for t in df_plot_1m.index]
    idx_dump = time_list_1m.index("10:14") if "10:14" in time_list_1m else 9
    idx_retest = time_list_1m.index("10:21") if "10:21" in time_list_1m else 16

    # Highlight Sweep
    ax1[0].annotate(
        "10:14 ET Dump to 29505.00\nWicked below NY PM Low\nImmediate Reclaim!",
        xy=(idx_dump, 29505.00),
        xytext=(idx_dump - 5, 29475.00),
        arrowprops=dict(facecolor='#f59e0b', edgecolor='#b45309', width=1.5, headwidth=6),
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#fef3c7", edgecolor="#f59e0b", alpha=0.95),
        fontsize=9, fontweight='bold', color='#92400e'
    )

    # Highlight Retest Zone
    rect_1m = Rectangle((idx_dump + 4, 29604.0), 9.0, 29635.0 - 29604.0,
                         facecolor='#a855f7', alpha=0.25, edgecolor='#9333ea', linestyle='--')
    ax1[0].add_patch(rect_1m)
    ax1[0].text(idx_dump + 5, 29640.0, "2nd Stage Retest into OB & iFVG (29604 - 29635)", color='#7e22ce', fontsize=9, fontweight='bold')

    # Entry Point
    ax1[0].annotate(
        "LONG ENTRY CONFIRMED @ 29617.50\n1m Green Candle Rejection\nStop Loss: 29602.50 (5.1 bps)",
        xy=(idx_retest, 29617.50),
        xytext=(idx_retest + 3, 29565.00),
        arrowprops=dict(facecolor='#22c55e', edgecolor='#15803d', width=2, headwidth=7),
        bbox=dict(boxstyle="round,pad=0.5", facecolor="#f0fdf4", edgecolor="#22c55e", alpha=0.95),
        fontsize=9.5, fontweight='bold', color='#14532d'
    )

    chart_file_1m = OUTPUT_DIR / "aug28_1m_entry_zoom.png"
    fig1.savefig(chart_file_1m, dpi=160, bbox_inches='tight')
    plt.close(fig1)
    print(f"Saved 1m chart: {chart_file_1m}")

    # Copy to root artifact directory
    import shutil
    shutil.copy(chart_file_5m, Path("C:/Users/vinay/.gemini/antigravity/brain/4c21dcc0-89c9-42df-8e6a-fc48ef5552a9/aug28_5m_overview.png"))
    shutil.copy(chart_file_1m, Path("C:/Users/vinay/.gemini/antigravity/brain/4c21dcc0-89c9-42df-8e6a-fc48ef5552a9/aug28_1m_entry_zoom.png"))

if __name__ == "__main__":
    generate_deep_dive()
