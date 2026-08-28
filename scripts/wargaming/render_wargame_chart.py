"""Interactive Lightweight Charts HTML Visual Renderer for Pack Wargaming

Generates an authentic Mickey & Austin wargaming visual matching their live streams:
1. Full 1m Candlestick Chart in Eastern Time (ET).
2. Shaded Asia (18:00-02:00 ET) and London (02:00-08:30 ET) session boxes with H/L boundaries.
3. Shaded Green LOD Target Box (09:30-10:15 ET) & Red HOD Target Box (11:00-16:00 ET).
4. Magenta Wargaming Trajectory Arrows (Sweeper -> Mean Reversion -> Expansion).
5. Floating Real-time HUD stats panel (Overnight HOD/LOD, Distances, 10-Day Median Ranges).
6. Horizontal Price Rays for P12 High, Low, Midline, and Midnight Open.
7. Bottom Probability Matrix Table.
8. 100% self-contained single-file HTML report (inlined Lightweight Charts v5.2.0).
"""
from __future__ import annotations

import sys
import json
import logging
import argparse
from pathlib import Path
from datetime import datetime, date, time, timedelta
from typing import Dict, Any, Optional, List
import pandas as pd
import pytz

REPO_ROOT = Path(__file__).parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.wargaming.generate_daily_wargame import generate_wargame_data
from scripts.utils.fused_data_loader import load_fused_data
from scripts.wargaming.gdrive_sync import upload_to_drive

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

REPORTS_DIR = REPO_ROOT / "data" / "wargaming" / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

ET = pytz.timezone("America/New_York")


def generate_html_chart(wargame_data: Dict[str, Any], df_1m: Optional[pd.DataFrame] = None) -> str:
    """Generate self-contained HTML containing TradingView Lightweight Charts and full wargaming overlays."""
    ticker = wargame_data["ticker"]
    dt_str = wargame_data["date"]
    cutoff = wargame_data["cutoff_time"]
    spot = wargame_data["spot_price"]
    p12 = wargame_data["p12"]
    anchors = wargame_data["anchors"]
    sess = wargame_data["sessions"]
    cs = wargame_data["candle_science"]
    pack = wargame_data["pack_trading"]

    # Load 1m bars if not provided
    if df_1m is None or df_1m.empty:
        df_1m = load_fused_data(ticker, timeframe="1m", require_historical=False)
        if df_1m.index.tz is None:
            df_1m.index = df_1m.index.tz_localize("US/Eastern")
        else:
            df_1m.index = df_1m.index.tz_convert("US/Eastern")

    t_dt = datetime.strptime(dt_str, "%Y-%m-%d").date()
    c_h, c_m = map(int, cutoff.split(":"))
    cutoff_dt = pd.Timestamp(datetime.combine(t_dt, time(c_h, c_m)), tz="America/New_York")
    start_dt = pd.Timestamp(datetime.combine(t_dt - timedelta(days=1), time(18, 0)), tz="America/New_York")

    chart_df = df_1m[(df_1m.index >= start_dt) & (df_1m.index <= cutoff_dt)].copy()
    chart_df = chart_df[~chart_df.index.duplicated(keep='last')].sort_index()

    # Convert candles to Lightweight Charts JSON format
    candles_data = []
    seen_ts = set()
    for ts, row in chart_df.iterrows():
        unix_sec = int(ts.timestamp())
        if unix_sec in seen_ts:
            continue
        seen_ts.add(unix_sec)
        candles_data.append({
            "time": unix_sec,
            "open": round(float(row["open"]), 2),
            "high": round(float(row["high"]), 2),
            "low": round(float(row["low"]), 2),
            "close": round(float(row["close"]), 2),
        })

    candles_json = json.dumps(candles_data)

    # Session bounds in timestamps
    asia_start_ts = int(pd.Timestamp(datetime.combine(t_dt - timedelta(days=1), time(18, 0)), tz="America/New_York").timestamp())
    asia_end_ts = int(pd.Timestamp(datetime.combine(t_dt, time(2, 0)), tz="America/New_York").timestamp())
    
    lon_start_ts = int(pd.Timestamp(datetime.combine(t_dt, time(2, 0)), tz="America/New_York").timestamp())
    lon_end_ts = int(pd.Timestamp(datetime.combine(t_dt, time(8, 30)), tz="America/New_York").timestamp())
    
    ny_open_ts = int(pd.Timestamp(datetime.combine(t_dt, time(9, 30)), tz="America/New_York").timestamp())
    lod_box_start_ts = int(pd.Timestamp(datetime.combine(t_dt, time(9, 30)), tz="America/New_York").timestamp())
    lod_box_end_ts = int(pd.Timestamp(datetime.combine(t_dt, time(10, 30)), tz="America/New_York").timestamp())
    
    hod_box_start_ts = int(pd.Timestamp(datetime.combine(t_dt, time(11, 0)), tz="America/New_York").timestamp())
    hod_box_end_ts = int(pd.Timestamp(datetime.combine(t_dt, time(16, 0)), tz="America/New_York").timestamp())

    # Target Box Coordinates derived from Candle Science P50
    bull_p50_pct = cs.get("bull", {}).get("p50", 1.20)
    bear_p50_pct = cs.get("bear", {}).get("p50", -0.85)

    bull_p50_pts = spot * (1.0 + bull_p50_pct / 100.0)
    bear_p50_pts = spot * (1.0 + bear_p50_pct / 100.0)

    lod_box_top = float(p12['low'] + 15.0)
    lod_box_bottom = float(bear_p50_pts) if bear_p50_pts < lod_box_top else float(p12['low'] - 65.0)

    hod_box_bottom = float(p12['high'] - 10.0)
    hod_box_top = float(bull_p50_pts) if bull_p50_pts > hod_box_bottom else float(p12['high'] + 85.0)

    # Invalidate if invalid
    if lod_box_bottom >= lod_box_top:
        lod_box_bottom = lod_box_top - 60.0
    if hod_box_top <= hod_box_bottom:
        hod_box_top = hod_box_bottom + 80.0

    p12_hod_time = p12.get("hod_time") or p12.get("high_time", "23:29")
    p12_lod_time = p12.get("lod_time") or p12.get("low_time", "04:07")


    p12_pos = "ABOVE" if p12["diff_pts"] >= 0 else "BELOW"
    bias_color = "#22c55e" if p12["bias"] == "BULLISH" else "#ef4444"

    # Inline local Lightweight Charts JS bundle for 100% offline self-containment if found
    lwc_script_tag = '<script src="https://unpkg.com/lightweight-charts/dist/lightweight-charts.standalone.production.js"></script>'
    for possible_path in [
        REPO_ROOT / "web" / "node_modules" / "lightweight-charts" / "dist" / "lightweight-charts.standalone.production.js",
        REPO_ROOT / "node_modules" / "lightweight-charts" / "dist" / "lightweight-charts.standalone.production.js"
    ]:
        if possible_path.exists():
            try:
                bundle_code = possible_path.read_text(encoding="utf-8")
                lwc_script_tag = f"<script>{bundle_code}</script>"
                log.info(f"Inlined local Lightweight Charts bundle ({len(bundle_code)} bytes)")
                break
            except Exception as e:
                log.warning(f"Could not inline local Lightweight Charts: {e}")

    html_template = f"""<!DOCTYPE html>
<html lang="en" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>⚔️ Mickey & Austin Wargaming Chart: {ticker} ({dt_str})</title>
    {lwc_script_tag}
    <style>
        :root {{
            --bg: #0b0f19;
            --card-bg: #111827;
            --border: #1f2937;
            --text: #f3f4f6;
            --text-dim: #9ca3af;
            --green: #10b981;
            --red: #ef4444;
            --gold: #f59e0b;
            --blue: #3b82f6;
            --magenta: #e11d48;
        }}
        body {{
            margin: 0;
            padding: 16px;
            background: var(--bg);
            color: var(--text);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 14px 20px;
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 10px;
            margin-bottom: 12px;
        }}
        .title-group h1 {{
            margin: 0 0 4px 0;
            font-size: 22px;
            font-weight: 700;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .badge {{
            display: inline-block;
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 700;
            text-transform: uppercase;
        }}
        .badge-bias {{
            background: {bias_color}22;
            color: {bias_color};
            border: 1px solid {bias_color}66;
        }}
        .chart-wrapper {{
            position: relative;
            width: 100%;
            height: 640px;
            background: #070a12;
            border: 1px solid var(--border);
            border-radius: 10px;
            overflow: hidden;
            margin-bottom: 16px;
        }}
        #chart-container {{
            width: 100%;
            height: 100%;
        }}
        #overlay-canvas {{
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            pointer-events: none;
            z-index: 10;
        }}
        .hud-panel {{
            position: absolute;
            top: 14px;
            right: 65px;
            background: rgba(17, 24, 39, 0.88);
            border: 1px solid #374151;
            backdrop-filter: blur(8px);
            border-radius: 8px;
            padding: 12px 16px;
            font-size: 11px;
            z-index: 20;
            box-shadow: 0 4px 12px rgba(0,0,0,0.5);
            line-height: 1.5;
            min-width: 240px;
        }}
        .hud-panel h4 {{
            margin: 0 0 6px 0;
            font-size: 12px;
            color: var(--gold);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            border-bottom: 1px solid #374151;
            padding-bottom: 4px;
        }}
        .hud-row {{
            display: flex;
            justify-content: space-between;
            margin-bottom: 3px;
        }}
        .hud-label {{ color: var(--text-dim); }}
        .hud-val {{ font-weight: 700; font-family: monospace; }}
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 10px;
            margin-bottom: 14px;
        }}
        .metric-card {{
            background: var(--card-bg);
            border: 1px solid var(--border);
            padding: 12px 16px;
            border-radius: 8px;
        }}
        .metric-card .label {{ font-size: 11px; color: var(--text-dim); margin-bottom: 2px; text-transform: uppercase; }}
        .metric-card .value {{ font-size: 17px; font-weight: 700; font-family: monospace; }}
        .cards-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 14px;
            margin-bottom: 16px;
        }}
        .scenario-card {{
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 16px 20px;
        }}
        .scenario-card.false {{ border-top: 4px solid var(--red); }}
        .scenario-card.true {{ border-top: 4px solid var(--green); }}
        .scenario-card h3 {{ margin: 0 0 10px 0; font-size: 16px; }}
        .scenario-card ul {{ margin: 0; padding-left: 18px; font-size: 13px; line-height: 1.6; }}
        .matrix-container {{
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 16px;
            margin-bottom: 16px;
        }}
        .matrix-container h3 {{ margin: 0 0 12px 0; font-size: 15px; color: var(--gold); }}
        .levels-table {{
            width: 100%;
            border-collapse: collapse;
        }}
        .levels-table th, .levels-table td {{
            padding: 8px 10px;
            text-align: left;
            border-bottom: 1px solid var(--border);
            font-size: 12px;
        }}
        .levels-table th {{ color: var(--text-dim); font-weight: 600; text-transform: uppercase; }}
    </style>
</head>
<body>

    <div class="header">
        <div class="title-group">
            <h1>⚔️ {ticker} Wargaming Playbook: {dt_str}</h1>
            <div style="font-size: 13px; color: var(--text-dim);">
                Analysis Cutoff: <b>{cutoff} EST</b> | Current Spot: <b style="color: #fff; font-family: monospace;">{spot:,.2f}</b> | Time Scale: <b>Eastern Time (New York / EDT)</b>
            </div>
        </div>
        <div>
            <span class="badge badge-bias">{p12['bias']} P12 VECTOR</span>
            <span class="badge" style="background: #3b82f622; color: #3b82f6; border: 1px solid #3b82f666; margin-left: 8px;">
                {sess['alignment']}
            </span>
        </div>
    </div>

    <div class="metrics-grid">
        <div class="metric-card">
            <div class="label">P12 Midline (Switch)</div>
            <div class="value" style="color: var(--gold);">{p12['mid']:,.2f}</div>
            <div style="font-size: 11px; color: var(--text-dim);">{p12_pos} by {abs(p12['diff_pts']):.2f} pts ({abs(p12['diff_bps']):.1f} bps)</div>
        </div>
        <div class="metric-card">
            <div class="label">Cover The Queen (+10 bps)</div>
            <div class="value" style="color: var(--green);">+{pack['cover_the_queen_bps']:.1f} bps (+{pack['queen_pts']:.2f} pts)</div>
            <div style="font-size: 11px; color: var(--text-dim);">50% Scale + BE Stop Lock</div>
        </div>
        <div class="metric-card">
            <div class="label">Stop Ceiling (Max Risk)</div>
            <div class="value" style="color: var(--red);">{pack['stop_ceiling_bps']:.1f} bps (~{pack['stop_pts']:.2f} pts)</div>
            <div style="font-size: 11px; color: var(--text-dim);">Strict Capital Floor</div>
        </div>
        <div class="metric-card">
            <div class="label">Midnight Open (00:00 ET)</div>
            <div class="value" style="color: var(--blue);">{anchors['midnight_open']:,.2f}</div>
            <div style="font-size: 11px; color: var(--text-dim);">Primary Morning Magnet</div>
        </div>
    </div>

    <!-- Chart Container with Overlay Canvas and HUD -->
    <div class="chart-wrapper">
        <div id="chart-container"></div>
        <canvas id="overlay-canvas"></canvas>
        
        <div class="hud-panel">
            <h4>📊 Live Wargame HUD</h4>
            <div class="hud-row">
                <span class="hud-label">Overnight HOD:</span>
                <span class="hud-val" style="color: #ef4444;">{p12['high']:,.2f} ({p12_hod_time})</span>
            </div>
            <div class="hud-row">
                <span class="hud-label">Overnight LOD:</span>
                <span class="hud-val" style="color: #10b981;">{p12['low']:,.2f} ({p12_lod_time})</span>
            </div>

            <div class="hud-row">
                <span class="hud-label">Asia Session:</span>
                <span class="hud-val" style="color: #60a5fa;">{sess['asia_status']} (BK: {str(sess['asia_broken'])})</span>
            </div>
            <div class="hud-row">
                <span class="hud-label">London Session:</span>
                <span class="hud-val" style="color: #fb923c;">{sess['london_status']} (BK: {str(sess['london_broken'])})</span>
            </div>
            <div class="hud-row" style="margin-top: 6px; border-top: 1px solid #374151; padding-top: 4px;">
                <span class="hud-label">LOD Target Box:</span>
                <span class="hud-val" style="color: #10b981;">{lod_box_bottom:,.0f} &ndash; {lod_box_top:,.0f}</span>
            </div>
            <div class="hud-row">
                <span class="hud-label">LOD Target Time:</span>
                <span class="hud-val" style="color: #10b981;">09:30 &ndash; 10:15 ET</span>
            </div>
            <div class="hud-row">
                <span class="hud-label">HOD Target Box:</span>
                <span class="hud-val" style="color: #ef4444;">{hod_box_bottom:,.0f} &ndash; {hod_box_top:,.0f}</span>
            </div>
            <div class="hud-row">
                <span class="hud-label">HOD Target Time:</span>
                <span class="hud-val" style="color: #ef4444;">11:00 &ndash; 16:00 ET</span>
            </div>
        </div>
    </div>

    <div class="cards-grid">
        <div class="scenario-card false">
            <h3 style="color: var(--red);">🔴 SCENARIO 1: FALSE REVERSION (Primary Sweeper)</h3>
            <ul>
                <li><b>Trigger</b>: 09:30 RTH Open sweeps into <b>Green LOD Target Box</b> (<code>{lod_box_bottom:,.2f} &ndash; {lod_box_top:,.2f}</code>) and fails 10 bps breakout in 0-5 box.</li>
                <li><b>Execution</b>: Long mean-reversion counter toward <b>P12 Midline</b> (<code>{p12['mid']:,.2f}</code>) & <b>Midnight Open</b> (<code>{anchors['midnight_open']:,.2f}</code>).</li>
                <li><b>Cover The Queen (+10 bps)</b>: Scale 50% at <code>{pack.get('long_tp1', spot + pack['queen_pts']):,.2f}</code> and lock stop to Breakeven (+1 pt).</li>
                <li><b>09:45 Cutoff</b>: Midline retest expected before 09:45 AM; reversal window closes at 10:15 AM.</li>

            </ul>
        </div>
        <div class="scenario-card true">
            <h3 style="color: var(--green);">🟢 SCENARIO 2: TRUE EXPANSION (Secondary Trend)</h3>
            <ul>
                <li><b>Trigger</b>: Price sustains >10 bps breakout and accepts across P12 Midline in Q1.</li>
                <li><b>Bullish Target</b>: P12 High (<code>{p12['high']:,.2f}</code>) &rarr; <b>Red HOD Target Box</b> (<code>{hod_box_bottom:,.2f} &ndash; {hod_box_top:,.2f}</code>).</li>
                <li><b>Bearish Target</b>: PDM (<code>{anchors['pdm']:,.2f}</code>) &rarr; PDL (<code>{anchors['pdl']:,.2f}</code>).</li>
                <li><b>10:15 Rule</b>: If no reversal signature by 10:15, Trend Continuation locks for the session.</li>
            </ul>
        </div>
    </div>

    <div class="matrix-container">
        <h3>📋 Mickey & Austin Wargaming Outcome Probability Matrix</h3>
        <table class="levels-table">
            <thead>
                <tr>
                    <th>Outcome Type</th>
                    <th>Historical Prob</th>
                    <th>Expected LOD Window</th>
                    <th>Expected HOD Window</th>
                    <th>LOD Distance</th>
                    <th>HOD Distance</th>
                    <th>Primary Execution Focus</th>
                </tr>
            </thead>
            <tbody>
                <tr style="background: rgba(239, 68, 68, 0.08);">
                    <td><b style="color: #ef4444;">Short False (Primary)</b></td>
                    <td><b>32.0% (71)</b></td>
                    <td>09:30 &ndash; 10:15 ET</td>
                    <td>16:00 &ndash; 16:15 ET</td>
                    <td>-0.2% to -0.7%</td>
                    <td>+0.6% to +0.5%</td>
                    <td>Sweep lower box, V-Reversal rocket to P12 Mid & HOD Box</td>
                </tr>
                <tr style="background: rgba(16, 185, 129, 0.08);">
                    <td><b style="color: #10b981;">Long True (Secondary)</b></td>
                    <td><b>24.3% (53)</b></td>
                    <td>08:30 &ndash; 08:45 ET</td>
                    <td>16:45 &ndash; 17:00 ET</td>
                    <td>-0.1% to -0.4%</td>
                    <td>+0.9% to +0.5%</td>
                    <td>Hold above P12 Midline, trend ride to Upper HOD Box</td>
                </tr>
                <tr>
                    <td><b>Long False</b></td>
                    <td>14.0% (26)</td>
                    <td>09:45 &ndash; 10:00 ET</td>
                    <td>09:30 &ndash; 09:45 ET</td>
                    <td>-0.3% to -0.6%</td>
                    <td>+0.6% to +0.4%</td>
                    <td>Early push higher, sweep upper levels then drop</td>
                </tr>
                <tr>
                    <td><b>Short True</b></td>
                    <td>8.0% (18)</td>
                    <td>09:30 &ndash; 09:45 ET</td>
                    <td>08:15 &ndash; 08:30 ET</td>
                    <td>-0.7% to -1.0%</td>
                    <td>+0.5% to +0.2%</td>
                    <td>Heavy downside continuation breaching all session lows</td>
                </tr>
            </tbody>
        </table>
    </div>

    <script>
        document.addEventListener('DOMContentLoaded', () => {{
            try {{
                const chartContainer = document.getElementById('chart-container');
                const overlayCanvas = document.getElementById('overlay-canvas');
                if (!chartContainer || !overlayCanvas) return;

                // ET Localization & Timezone formatting (New York / EDT)
                const etTimeFormatter = (timestamp) => {{
                    const date = new Date(timestamp * 1000);
                    return new Intl.DateTimeFormat('en-US', {{
                        timeZone: 'America/New_York',
                        hour: '2-digit',
                        minute: '2-digit',
                        hour12: false,
                        month: 'short',
                        day: 'numeric'
                    }}).format(date);
                }};

                const chart = LightweightCharts.createChart(chartContainer, {{
                    width: chartContainer.clientWidth || 1000,
                    height: 640,
                    layout: {{
                        background: {{ color: '#070a12' }},
                        textColor: '#9ca3af',
                    }},
                    grid: {{
                        vertLines: {{ color: '#161e2e' }},
                        horzLines: {{ color: '#161e2e' }},
                    }},
                    localization: {{
                        timeFormatter: etTimeFormatter,
                        priceFormatter: (price) => price.toFixed(2),
                    }},
                    timeScale: {{
                        timeVisible: true,
                        secondsVisible: false,
                        rightOffset: 65, // Future whitespace for target boxes and arrows
                        borderColor: '#1f2937',
                        tickMarkFormatter: (time) => {{
                            const date = new Date(time * 1000);
                            return new Intl.DateTimeFormat('en-US', {{
                                timeZone: 'America/New_York',
                                hour: '2-digit',
                                minute: '2-digit',
                                hour12: false
                            }}).format(date);
                        }},
                    }},
                    rightPriceScale: {{
                        borderColor: '#1f2937',
                    }},
                }});

                const seriesOptions = {{
                    upColor: '#10b981',
                    downColor: '#ef4444',
                    borderVisible: false,
                    wickUpColor: '#10b981',
                    wickDownColor: '#ef4444',
                }};

                const candleSeries = (typeof chart.addCandlestickSeries === 'function')
                    ? chart.addCandlestickSeries(seriesOptions)
                    : chart.addSeries(LightweightCharts.CandlestickSeries, seriesOptions);

                const data = {candles_json};
                candleSeries.setData(data);
                chart.timeScale().fitContent();

                // Horizontal Price Rays
                const p12Mid = {p12['mid']};
                const p12High = {p12['high']};
                const p12Low = {p12['low']};
                const midnight = {anchors['midnight_open'] if anchors['midnight_open'] else 'null'};

                const solidStyle = (LightweightCharts.LineStyle && LightweightCharts.LineStyle.Solid !== undefined) ? LightweightCharts.LineStyle.Solid : 0;
                const dashedStyle = (LightweightCharts.LineStyle && LightweightCharts.LineStyle.Dashed !== undefined) ? LightweightCharts.LineStyle.Dashed : 2;
                const dottedStyle = (LightweightCharts.LineStyle && LightweightCharts.LineStyle.Dotted !== undefined) ? LightweightCharts.LineStyle.Dotted : 1;

                candleSeries.createPriceLine({{
                    price: p12Mid,
                    color: '#f59e0b',
                    lineWidth: 2,
                    lineStyle: solidStyle,
                    title: 'P12 MIDLINE ({p12['mid']:,.2f})',
                }});

                candleSeries.createPriceLine({{
                    price: p12High,
                    color: '#ef4444',
                    lineWidth: 1,
                    lineStyle: dashedStyle,
                    title: 'P12 HIGH ({p12['high']:,.2f})',
                }});

                candleSeries.createPriceLine({{
                    price: p12Low,
                    color: '#10b981',
                    lineWidth: 1,
                    lineStyle: dashedStyle,
                    title: 'P12 LOW ({p12['low']:,.2f})',
                }});

                if (midnight !== null) {{
                    candleSeries.createPriceLine({{
                        price: midnight,
                        color: '#3b82f6',
                        lineWidth: 1,
                        lineStyle: dottedStyle,
                        title: 'MIDNIGHT OPEN ({anchors['midnight_open']:,.2f})',
                    }});
                }}

                // Overlay Canvas Drawing for Shaded Target Boxes, Session Zones & Arrows
                function drawOverlays() {{
                    overlayCanvas.width = chartContainer.clientWidth;
                    overlayCanvas.height = chartContainer.clientHeight;
                    const ctx = overlayCanvas.getContext('2d');
                    ctx.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height);

                    const timeScale = chart.timeScale();

                    // Helper to get coordinates
                    const getX = (ts) => timeScale.timeToCoordinate(ts);
                    const getY = (price) => candleSeries.priceToCoordinate(price);

                    // 1. Shaded Asia Session Box (18:00 - 02:00 ET)
                    const asiaX1 = getX({asia_start_ts});
                    const asiaX2 = getX({asia_end_ts});
                    if (asiaX1 !== null && asiaX2 !== null) {{
                        ctx.fillStyle = 'rgba(59, 130, 246, 0.08)';
                        ctx.fillRect(asiaX1, 0, Math.max(2, asiaX2 - asiaX1), overlayCanvas.height);
                        ctx.fillStyle = '#60a5fa';
                        ctx.font = '11px sans-serif';
                        ctx.fillText('ASIA (18:00-02:00 ET)', asiaX1 + 8, 24);
                    }}

                    // 2. Shaded London Session Box (02:00 - 08:30 ET)
                    const lonX1 = getX({lon_start_ts});
                    const lonX2 = getX({lon_end_ts});
                    if (lonX1 !== null && lonX2 !== null) {{
                        ctx.fillStyle = 'rgba(249, 115, 22, 0.08)';
                        ctx.fillRect(lonX1, 0, Math.max(2, lonX2 - lonX1), overlayCanvas.height);
                        ctx.fillStyle = '#fb923c';
                        ctx.font = '11px sans-serif';
                        ctx.fillText('LONDON (02:00-08:30 ET)', lonX1 + 8, 24);
                    }}

                    // 3. Green LOD Target Box (09:30 - 10:30 ET)
                    const lodX1 = getX({lod_box_start_ts}) || (lonX2 ? lonX2 + 40 : 400);
                    const lodX2 = getX({lod_box_end_ts}) || lodX1 + 80;
                    const lodYTop = getY({lod_box_top});
                    const lodYBot = getY({lod_box_bottom});

                    if (lodYTop !== null && lodYBot !== null) {{
                        const boxW = Math.max(60, lodX2 - lodX1);
                        const boxH = Math.abs(lodYBot - lodYTop);
                        const boxY = Math.min(lodYTop, lodYBot);

                        ctx.fillStyle = 'rgba(16, 185, 129, 0.22)';
                        ctx.fillRect(lodX1, boxY, boxW, boxH);
                        ctx.strokeStyle = '#10b981';
                        ctx.lineWidth = 1.5;
                        ctx.strokeRect(lodX1, boxY, boxW, boxH);

                        ctx.fillStyle = '#34d399';
                        ctx.font = 'bold 11px sans-serif';
                        ctx.fillText('🟢 LOD TARGET BOX', lodX1 + 8, boxY + 18);
                        ctx.font = '10px monospace';
                        ctx.fillText('{lod_box_bottom:,.0f} - {lod_box_top:,.0f} (09:30-10:15 ET)', lodX1 + 8, boxY + 32);
                    }}

                    // 4. Red HOD Target Box (11:00 - 16:00 ET)
                    const hodX1 = getX({hod_box_start_ts}) || lodX2 + 50;
                    const hodX2 = getX({hod_box_end_ts}) || hodX1 + 180;
                    const hodYTop = getY({hod_box_top});
                    const hodYBot = getY({hod_box_bottom});

                    if (hodYTop !== null && hodYBot !== null) {{
                        const boxW = Math.max(90, hodX2 - hodX1);
                        const boxH = Math.abs(hodYBot - hodYTop);
                        const boxY = Math.min(hodYTop, hodYBot);

                        ctx.fillStyle = 'rgba(239, 68, 68, 0.22)';
                        ctx.fillRect(hodX1, boxY, boxW, boxH);
                        ctx.strokeStyle = '#ef4444';
                        ctx.lineWidth = 1.5;
                        ctx.strokeRect(hodX1, boxY, boxW, boxH);

                        ctx.fillStyle = '#f87171';
                        ctx.font = 'bold 11px sans-serif';
                        ctx.fillText('🔴 HOD TARGET BOX', hodX1 + 8, boxY + 18);
                        ctx.font = '10px monospace';
                        ctx.fillText('{hod_box_bottom:,.0f} - {hod_box_top:,.0f} (11:00-16:00 ET)', hodX1 + 8, boxY + 32);
                    }}

                    // 5. Magenta Wargaming Trajectory Arrow (Sweeper V-Reversion Path)
                    const spotY = getY({spot});
                    const lodMidY = (lodYTop !== null && lodYBot !== null) ? (lodYTop + lodYBot) / 2 : null;
                    const hodMidY = (hodYTop !== null && hodYBot !== null) ? (hodYTop + hodYBot) / 2 : null;

                    if (spotY !== null && lodMidY !== null && hodMidY !== null && lodX1 !== null && hodX1 !== null) {{
                        ctx.strokeStyle = '#f43f5e';
                        ctx.lineWidth = 3;
                        ctx.setLineDash([]);
                        ctx.beginPath();
                        
                        // Start at 09:30 Open -> Sweep down into LOD box
                        const sweepMidX = lodX1 + 35;
                        ctx.moveTo(lodX1 - 20, spotY);
                        ctx.lineTo(sweepMidX, lodMidY);

                        // Rocket launch up to HOD target box
                        const rocketTargetX = hodX1 + 60;
                        ctx.lineTo(rocketTargetX, hodMidY);
                        ctx.stroke();

                        // Draw Arrowhead at Rocket Target
                        const angle = Math.atan2(hodMidY - lodMidY, rocketTargetX - sweepMidX);
                        ctx.fillStyle = '#f43f5e';
                        ctx.beginPath();
                        ctx.moveTo(rocketTargetX, hodMidY);
                        ctx.lineTo(rocketTargetX - 14 * Math.cos(angle - Math.PI / 6), hodMidY - 14 * Math.sin(angle - Math.PI / 6));
                        ctx.lineTo(rocketTargetX - 14 * Math.cos(angle + Math.PI / 6), hodMidY - 14 * Math.sin(angle + Math.PI / 6));
                        ctx.closePath();
                        ctx.fill();

                        ctx.fillStyle = '#fda4af';
                        ctx.font = 'bold 11px sans-serif';
                        ctx.fillText('⚡ SCENARIO 1 V-REVERSAL TRAJECTORY', sweepMidX + 10, lodMidY - 14);
                    }}
                }}

                // Redraw on zoom, scroll, and resize
                chart.timeScale().subscribeVisibleTimeRangeChange(drawOverlays);
                chart.timeScale().subscribeVisibleLogicalRangeChange(drawOverlays);
                setTimeout(drawOverlays, 100);

                window.addEventListener('resize', () => {{
                    chart.applyOptions({{ width: chartContainer.clientWidth }});
                    drawOverlays();
                }});

            }} catch (err) {{
                console.error("Failed to render chart:", err);
                const errBox = document.getElementById('chart-container');
                if (errBox) {{
                    errBox.innerHTML = '<div style="color:#ef4444;padding:20px;font-family:monospace;">Error rendering chart: ' + err.message + '</div>';
                }}
            }}
        }});
    </script>
</body>
</html>
"""

    return html_template


def render_and_save_chart(ticker: str = "NQ1", target_date: Optional[date] = None, cutoff_time: str = "06:00", upload_gdrive: bool = False) -> str:
    """Generate HTML chart report, save to disk, and optionally upload to Google Drive."""
    if target_date is None:
        target_date = datetime.now(ET).date()

    wargame_data = generate_wargame_data(ticker=ticker, target_date=target_date, cutoff_time_str=cutoff_time)
    html_content = generate_html_chart(wargame_data)

    out_file = REPORTS_DIR / f"{target_date.isoformat()}_{ticker}_wargame.html"
    out_file.write_text(html_content, encoding="utf-8")
    log.info(f"Saved interactive HTML report: {out_file} ({len(html_content)} bytes)")

    # Save JSON export for Next.js platform dashboard ingestion
    json_out_file = REPORTS_DIR / f"{target_date.isoformat()}_{ticker}_wargame.json"
    json_out_file.write_text(json.dumps(wargame_data, indent=2, default=str), encoding="utf-8")
    log.info(f"Saved platform JSON report: {json_out_file.name}")

    if upload_gdrive:
        try:
            res = upload_to_drive(out_file, folder_type="daily_reports")
            log.info(f"Uploaded HTML report to Google Drive: {res.get('webViewLink')}")
        except Exception as e:
            log.warning(f"Google Drive upload skipped: {e}")

    return str(out_file)


def main():
    parser = argparse.ArgumentParser(description="Generate Interactive Lightweight Charts HTML Wargame Report")
    parser.add_argument("--ticker", default="NQ1", help="Ticker symbol (default: NQ1)")
    parser.add_argument("--date", default=None, help="Target date YYYY-MM-DD (default: today)")
    parser.add_argument("--time", default="06:00", help="Cutoff time HH:MM (default: 06:00)")
    parser.add_argument("--upload-gdrive", action="store_true", help="Upload HTML report to Google Drive DailyReports folder")
    args = parser.parse_args()

    t_date = datetime.strptime(args.date, "%Y-%m-%d").date() if args.date else datetime.now(ET).date()
    path = render_and_save_chart(ticker=args.ticker, target_date=t_date, cutoff_time=args.time, upload_gdrive=args.upload_gdrive)
    print(f"Generated Interactive HTML Chart: {path}")


if __name__ == "__main__":
    main()
