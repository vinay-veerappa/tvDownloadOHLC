"""
macro_charting.py
=================
Implementation of Task 3: Charting with mplfinance.
Generates a dual-panel macro chart with clamped OHLC and labeled OI profiles.
"""
from __future__ import annotations

import io
import logging
from typing import Any

import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import mplfinance as mpf
import pandas as pd
import yfinance as yf
from .level_scorer import (
    ScoredLevels, 
    MechanicalWall, 
    StructuralAnchor, 
    InflectionPoint
)

log = logging.getLogger(__name__)

def generate_macro_chart_bytes(
    ticker: str, 
    spot: float,                    
    levels: dict[str, Any],          # <--- Update to Any (since it holds dominant_nodes now)
    anomalies: list[dict[str, Any]],
    scored: ScoredLevels | None = None
) -> io.BytesIO:
    """
    Generates a clamped macro HTF chart.
    Layout: 6-month daily candles (left) + OI profile (right).
    """
    log.info("Generating macro chart for %s...", ticker)
    
    # 1. Fetch 6 months of OHLCV data
    yf_ticker = ticker
    if ticker in ["SPX", "NDX", "DJX", "RUT", "VIX"]:
        yf_ticker = f"^{ticker}"
        
    df = yf.download(yf_ticker, period="6mo", interval="1d", progress=False)
    if df.empty:
        log.error("Could not fetch OHLC data for %s", ticker)
        return io.BytesIO()

    # Flatten columns if multi-indexed
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # --- THE Y-AXIS CLAMP ---
    # Lock the view to +/- 8% of the current spot price
    zoom_range = 0.08 
    lower_bound = spot * (1 - zoom_range)
    upper_bound = spot * (1 + zoom_range)

    # 2. Setup GridSpec
    fig = plt.figure(figsize=(16, 9))
    gs = gridspec.GridSpec(1, 2, width_ratios=[3, 1.8], wspace=0.15, left=0.05, right=0.98, top=0.9, bottom=0.2)
    ax1 = fig.add_subplot(gs[0])
    ax2 = fig.add_subplot(gs[1]) # Removed sharey to manually sync clamped bounds

    # 3. Plot OHLC (Left) with the Clamp applied
    mpf.plot(
        df, 
        type='candle', 
        ax=ax1, 
        style='nightclouds', 
        datetime_format='%b %d',
        xrotation=0,
        tight_layout=False,
        ylim=(lower_bound, upper_bound) # <--- The Clamp
    )
    ax1.set_title(f"{ticker} Macro HTF - 6 Month Analysis", fontsize=16, color='white', pad=20)

    # 4. Overlays (Horizontal Lines)
    x_left = int(len(df) * 0.02)
    x_right = len(df) - int(len(df) * 0.15)

    if levels.get("macro_call_wall"):
        ax1.axhline(levels["macro_call_wall"], color='red', linestyle='--', alpha=0.8, linewidth=1.5)
        ax1.text(x_left, levels["macro_call_wall"], " CALL WALL", color='red', va='bottom', fontsize=8, alpha=0.8)

    if levels.get("macro_put_wall"):
        ax1.axhline(levels["macro_put_wall"], color='green', linestyle='--', alpha=0.8, linewidth=1.5)
        ax1.text(x_left, levels["macro_put_wall"], " PUT WALL", color='green', va='top', fontsize=8, alpha=0.8)

    if levels.get("zero_gamma"):
        ax1.axhline(levels["zero_gamma"], color='yellow', linestyle=':', alpha=0.8, linewidth=1.2)
        ax1.text(x_left, levels["zero_gamma"], " ZERO GAMMA", color='yellow', va='bottom', fontsize=8, alpha=0.8)

    # Top 3 Whale Anomalies
    top_whales = anomalies[:3]
    for i, whale in enumerate(top_whales):
        strike = whale["strike"]
        # Only plot whales inside the clamped view
        if lower_bound <= strike <= upper_bound:
            label = f"WHALE {whale['type']} ({whale['dte_str']})"
            ax1.axhline(strike, color='fuchsia', linestyle='-', alpha=0.6, linewidth=1.0)
            ax1.text(x_right, strike, f" {label}", color='fuchsia', va='center', fontsize=7, bbox=dict(facecolor='black', alpha=0.5, edgecolor='none', pad=1))
    
    # ── Scored Analysis Overlays (Filters) ──────────────────────
    if scored:
        # --- Layer 1: Resistance Walls (Filter 1) ---
        for w in scored.resistance_walls[:2]:
            ax1.axhline(w.strike, color='#FF5555', linestyle='--', alpha=0.9, linewidth=1.5)
            # Use pct_of_book for visual weight
            ax1.text(x_left, w.strike, f" {w.label} ({w.pct_of_book*100:.1f}% BOOK)", 
                    color='#FF5555', fontsize=8, fontweight='bold', va='bottom', ha='left')

        for w in scored.support_walls[:2]:
            ax1.axhline(w.strike, color='#55FF55', linestyle='--', alpha=0.9, linewidth=1.5)
            ax1.text(x_left, w.strike, f" {w.label} ({w.pct_of_book*100:.1f}% BOOK)", 
                    color='#55FF55', fontsize=8, fontweight='bold', va='top', ha='left')

        # --- Layer 2: Structural Anchors (Filter 2) ---
        anchors = [l for l in scored.tagged_levels if isinstance(l, StructuralAnchor)]
        for a in anchors[:2]:
            ax1.axhline(a.strike, color='#FFD700', linestyle='-', alpha=0.8, linewidth=2.0)
            ax1.text(x_left, a.strike, f" [{a.matched_program}] ({a.relevance})", 
                    color='#FFD700', fontsize=8, fontweight='bold', va='center', ha='left')

        # --- Layer 3: Inflection Points (Filter 3) ---
        pts = [l for l in scored.tagged_levels if isinstance(l, InflectionPoint)]
        for p in pts:
            if p.label == "Zero Gamma Level":
                ax1.axhline(p.strike, color='#ffffff', linestyle=':', alpha=0.9, linewidth=1.5)
                ax1.text(x_right, p.strike, " ZERO GEX ", color='#ffffff', 
                        fontsize=7, bbox=dict(facecolor='black', alpha=0.5), va='center', ha='right')

    # 5. OI Profile (Right)
    strikes_data = levels.get("strikes_oi", [])
    if strikes_data:
        sdf = pd.DataFrame(strikes_data)
        # Filter OI bars to only those inside the clamped view
        sdf_vis = sdf[(sdf["strike"] >= lower_bound) & (sdf["strike"] <= upper_bound)]
        
        if not sdf_vis.empty:
            strike_diffs = sdf_vis["strike"].diff().abs()
            bar_height = strike_diffs.median() * 0.8 if not strike_diffs.isna().all() else 1.0
            
            ax2.barh(sdf_vis["strike"], sdf_vis["call_oi"], color='green', alpha=0.5, label="Call OI", height=bar_height)
            ax2.barh(sdf_vis["strike"], -sdf_vis["put_oi"], color='red', alpha=0.5, label="Put OI", height=bar_height)
            
            # Label the Top 3 Calls and Puts in the visible range
            top_calls = sdf_vis.nlargest(3, "call_oi")
            for _, row in top_calls.iterrows():
                if row["call_oi"] > 0:
                    ax2.text(row["call_oi"], row["strike"], f" {row['strike']:g}", va='center', ha='left', color='lime', fontsize=9, fontweight='bold')
                    
            top_puts = sdf_vis.nlargest(3, "put_oi")
            for _, row in top_puts.iterrows():
                if row["put_oi"] > 0:
                    ax2.text(-row["put_oi"], row["strike"], f"{row['strike']:g} ", va='center', ha='right', color='red', fontsize=9, fontweight='bold')

        ax2.axvline(0, color='white', linewidth=0.5)
        ax2.set_title("Open Interest Profile", fontsize=12, color='white')
        ax2.set_xlabel("Put OI <--- | ---> Call OI", color='gray')
        ax2.grid(True, axis='x', alpha=0.2)
        ax2.set_ylim(lower_bound, upper_bound) # Sync the clamp
    
    # Aesthetics
    fig.patch.set_facecolor('#0b0d0f')
    ax1.set_facecolor('#0b0d0f')
    ax2.set_facecolor('#0b0d0f')
    ax1.tick_params(colors='white')
    ax2.tick_params(colors='white')
    for spine in ax2.spines.values():
        spine.set_edgecolor('#333333')
    for spine in ax1.spines.values():
        spine.set_edgecolor('#333333')

    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=120, facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return buf