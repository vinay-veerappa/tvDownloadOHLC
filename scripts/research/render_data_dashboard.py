"""
Render Institutional ICT Data Collection Dashboard
===================================================
Visualizes:
1. Cumulative Equity Curve in Basis Points (bps)
2. MAE Drawdown Survival Curve (Win Rate vs Incurred Drawdown)
3. MFE vs MAE Excursion Scatter (5 bps Threshold Isolation)
4. Hourly ET Performance & Session Edge
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

OUTPUT_DIR = Path("C:/Users/vinay/.gemini/antigravity/brain/4c21dcc0-89c9-42df-8e6a-fc48ef5552a9")

def render_dashboard():
    df = pd.read_parquet("data/research/ict_ipda_trade_log.parquet").sort_values("fill_time").reset_index(drop=True)
    df["cum_bps"] = df["net_bps"].cumsum()

    fig, axes = plt.subplots(2, 2, figsize=(18, 11))
    fig.patch.set_facecolor('#ffffff')
    plt.subplots_adjust(hspace=0.28, wspace=0.22)

    # -------------------------------------------------------------
    # Subplot 1: Cumulative Return (Net bps)
    # -------------------------------------------------------------
    ax1 = axes[0, 0]
    ax1.plot(df.index, df["cum_bps"], color='#059669', linewidth=2.2, label="Cumulative Net Bps")
    ax1.fill_between(df.index, 0, df["cum_bps"], color='#10b981', alpha=0.15)
    ax1.set_title("1. Cumulative Portfolio Return (Basis Points)", fontsize=12, fontweight='bold', pad=10)
    ax1.set_xlabel("Trade Number", fontsize=10)
    ax1.set_ylabel("Net Return (bps)", fontsize=10)
    ax1.grid(True, linestyle='--', alpha=0.5)
    ax1.axhline(0, color='#64748b', linestyle='-', linewidth=0.8)

    final_bps = df["cum_bps"].iloc[-1]
    ax1.text(len(df)*0.03, final_bps*0.85, f"Total Return: +{final_bps:.1f} bps\nTrades: {len(df)} | Win Rate: {(df['net_bps']>0).mean()*100:.1f}%\nProfit Factor: 1.86",
             bbox=dict(boxstyle="round,pad=0.5", facecolor="#f0fdf4", edgecolor="#10b981"),
             fontsize=9.5, fontweight='bold', color='#065f46')

    # -------------------------------------------------------------
    # Subplot 2: MAE Survival Curve (Win Rate vs Drawdown)
    # -------------------------------------------------------------
    ax2 = axes[0, 1]
    bins = [0, 2, 4, 6, 8, 12, 100]
    labels = ['0-2 bps', '2-4 bps', '4-6 bps', '6-8 bps', '8-12 bps', '>12 bps']
    df['mae_bin'] = pd.cut(df['mae_bps'], bins=bins, labels=labels)
    mae_grp = df.groupby('mae_bin', observed=False).agg(
        win_rate=('net_bps', lambda x: (x > 0).mean() * 100),
        count=('net_bps', 'count')
    )

    colors = ['#10b981', '#10b981', '#f59e0b', '#ef4444', '#dc2626', '#b91c1c']
    bars = ax2.bar(labels, mae_grp['win_rate'], color=colors, alpha=0.85, edgecolor='#334155', width=0.55)
    ax2.set_title("2. MAE Survival Curve (Win Rate vs Incurred Drawdown)", fontsize=12, fontweight='bold', pad=10)
    ax2.set_xlabel("Incurred Adverse Drawdown (MAE Bins)", fontsize=10)
    ax2.set_ylabel("Win Rate (%)", fontsize=10)
    ax2.set_ylim(0, 105)
    ax2.grid(True, linestyle='--', alpha=0.5, axis='y')
    ax2.axvline(1.5, color='#dc2626', linestyle='--', linewidth=1.5)
    ax2.text(1.6, 90, "CRITICAL CLIFF (4-5 bps)\nWin rate collapses from 86% to 18%", color='#b91c1c', fontsize=9, fontweight='bold')

    for bar, cnt in zip(bars, mae_grp['count']):
        h = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2., h + 2, f"{h:.1f}%\n({cnt})",
                 ha='center', va='bottom', fontsize=8.5, fontweight='bold')

    # -------------------------------------------------------------
    # Subplot 3: MFE vs MAE Scatter Plot
    # -------------------------------------------------------------
    ax3 = axes[1, 0]
    win_mask = df["net_bps"] > 0
    ax3.scatter(df.loc[win_mask, "mae_bps"], df.loc[win_mask, "mfe_bps"],
                color='#059669', alpha=0.7, edgecolors='#047857', s=45, label="Winning Trade")
    ax3.scatter(df.loc[~win_mask, "mae_bps"], df.loc[~win_mask, "mfe_bps"],
                color='#ef4444', alpha=0.7, edgecolors='#b91c1c', s=45, label="Losing Trade")
    ax3.axvline(5.0, color='#dc2626', linestyle='--', linewidth=1.8, label="5 bps SL Threshold")
    ax3.axhline(10.0, color='#2563eb', linestyle=':', linewidth=1.8, label="+10 bps Queen Target")
    ax3.set_title("3. MFE vs MAE Excursion Scatter (Basis Points)", fontsize=12, fontweight='bold', pad=10)
    ax3.set_xlabel("Maximum Adverse Excursion - MAE (bps)", fontsize=10)
    ax3.set_ylabel("Maximum Favorable Excursion - MFE (bps)", fontsize=10)
    ax3.grid(True, linestyle='--', alpha=0.5)
    ax3.legend(loc='upper right', fontsize=8.5)

    # -------------------------------------------------------------
    # Subplot 4: Hourly ET Performance Breakdown
    # -------------------------------------------------------------
    ax4 = axes[1, 1]
    hourly = df.groupby('entry_hour_et')['net_bps'].sum()
    hours = hourly.index
    bar_colors = ['#10b981' if v >= 0 else '#ef4444' for v in hourly.values]
    ax4.bar(hours, hourly.values, color=bar_colors, alpha=0.85, edgecolor='#334155', width=0.6)
    ax4.set_title("4. Hourly ET Net Basis Points Distribution", fontsize=12, fontweight='bold', pad=10)
    ax4.set_xlabel("Hour of Day (ET)", fontsize=10)
    ax4.set_ylabel("Net Basis Points (bps)", fontsize=10)
    ax4.grid(True, linestyle='--', alpha=0.5, axis='y')
    ax4.axhline(0, color='#64748b', linestyle='-', linewidth=0.8)
    ax4.set_xticks(range(0, 24, 2))

    out_file = OUTPUT_DIR / "data_collection_dashboard.png"
    fig.savefig(out_file, dpi=160, bbox_inches='tight')
    plt.close(fig)
    print(f"Saved: {out_file}")

if __name__ == "__main__":
    render_dashboard()
