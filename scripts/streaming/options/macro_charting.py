"""
macro_charting.py
=================
Implementation of Task 3: Charting with mplfinance.
Generates a dual-panel macro chart with OHLC and Open Interest profiles.
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

from .options_fetcher import OptionChainData

log = logging.getLogger(__name__)

def generate_macro_chart_bytes(
    ticker: str, 
    levels: dict[str, float | None], 
    anomalies: list[dict[str, Any]]
) -> io.BytesIO:
    """
    Generates a macro HTF chart.
    Layout: 6-month daily candles (left) + OI profile (right).
    Overlays: Call/Put Walls, Zero Gamma, and top 3 Whales.
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

    # 2. Setup GridSpec
    fig = plt.figure(figsize=(16, 9))
    gs = gridspec.GridSpec(1, 2, width_ratios=[3, 1.8], wspace=0.15, left=0.05, right=0.98, top=0.9, bottom=0.2)
    ax1 = fig.add_subplot(gs[0])
    ax2 = fig.add_subplot(gs[1], sharey=ax1)

    # 3. Plot OHLC (Left)
    mpf.plot(
        df, 
        type='candle', 
        ax=ax1, 
        style='nightclouds', 
        datetime_format='%b %d',
        xrotation=0,
        tight_layout=False
    )
    ax1.set_title(f"{ticker} Macro HTF - 6 Month Analysis", fontsize=16, color='white', pad=20)

    # 4. Overlays (Horizontal Lines)
    # Call Wall (Red), Put Wall (Green), Zero Gamma (Yellow)

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
        label = f"WHALE {whale['type']} ({whale['dte_str']})"
        ax1.axhline(strike, color='fuchsia', linestyle='-', alpha=0.6, linewidth=1.0)
        ax1.text(x_right, strike, f" {label}", color='fuchsia', va='center', fontsize=7, bbox=dict(facecolor='black', alpha=0.5, edgecolor='none', pad=1))
    
    # 5. OI Profile (Right)
    # We aggregate OI from the anomalies or the full chain if available
    # For a macro HTF, more useful is the full OI profile if provided.
    # If levels contains 'strike_oi', we use that.
    strikes_data = levels.get("strikes_oi", [])
    if strikes_data:
        sdf = pd.DataFrame(strikes_data)
        y_min, y_max = ax1.get_ylim()
        sdf = sdf[(sdf["strike"] >= y_min) & (sdf["strike"] <= y_max)]
        
        # Calculate dynamic bar height
        strike_diffs = sdf["strike"].diff().abs()
        bar_height = strike_diffs.median() * 0.8 if not strike_diffs.isna().all() else 1.0
        
        ax2.barh(sdf["strike"], sdf["call_oi"], color='green', alpha=0.5, label="Call OI", height=bar_height)
        ax2.barh(sdf["strike"], -sdf["put_oi"], color='red', alpha=0.5, label="Put OI", height=bar_height)
        ax2.axvline(0, color='white', linewidth=0.5)
        ax2.set_title("Open Interest Profile", fontsize=12, color='white')
        ax2.set_xlabel("Put OI <--- | ---> Call OI", color='gray')
        ax2.grid(True, axis='x', alpha=0.2)
    
    # Aesthetics
    fig.patch.set_facecolor('#0b0d0f') # Match nightclouds background
    ax1.set_facecolor('#0b0d0f')
    ax2.set_facecolor('#0b0d0f')
    ax1.tick_params(colors='white')
    ax2.tick_params(colors='white')
    for spine in ax2.spines.values():
        spine.set_edgecolor('#333333')
    for spine in ax1.spines.values():
        spine.set_edgecolor('#333333')

    # Export to buffer
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=120, facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return buf
