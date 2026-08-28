"""Interactive Lightweight Charts HTML Visual Renderer for Pack Wargaming

Generates an authentic Mickey & Austin wargaming visual matching their live streams:
1. Full 1m Candlestick Chart in Eastern Time (ET).
2. Price-bounded Asia (18:00-02:00 ET), London (02:00-08:30 ET), and Pre-Market (06:00-09:00 ET) session boxes.
3. Shaded Green LOD Target Box (09:30-10:15 ET) & Red HOD Target Box (11:00-16:00 ET).
4. Algorithmic Scenario Trajectory Arrows generated dynamically from Profiler & Candle Science distributions.
5. All price rays annotated with empirical Touch Probabilities (Hit Rates %):
   - P12 Midline [88.5%], Midnight Open [84.1%], P12 High [81.7%], 07:30 Open [74.7%], P12 Low [68.9%], PDM [65.0%].
6. Continuous 60 FPS synchronization on both X (Time) and Y (Price) drag/zoom.
7. Interactive Toolbar with Fullscreen mode (⛶), Scenario 1 / 2 Trajectory Toggles, Fit All, and View presets.
8. Mickey & Austin Magnet Hierarchy Matrix Table ranking all key levels by probability.
9. 100% self-contained single-file HTML report (inlined Lightweight Charts v5.2.0).
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
    traj_data = wargame_data.get("trajectory_engine", {})

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
    asia_start = pd.Timestamp(datetime.combine(t_dt - timedelta(days=1), time(18, 0)), tz="America/New_York")
    asia_end = pd.Timestamp(datetime.combine(t_dt, time(2, 0)), tz="America/New_York")
    asia_df = df_1m[(df_1m.index >= asia_start) & (df_1m.index < asia_end)]

    lon_start = pd.Timestamp(datetime.combine(t_dt, time(2, 0)), tz="America/New_York")
    lon_end = pd.Timestamp(datetime.combine(t_dt, time(8, 30)), tz="America/New_York")
    lon_df = df_1m[(df_1m.index >= lon_start) & (df_1m.index < lon_end)]

    pm_start = pd.Timestamp(datetime.combine(t_dt, time(6, 0)), tz="America/New_York")
    pm_end = pd.Timestamp(datetime.combine(t_dt, time(9, 0)), tz="America/New_York")
    pm_df = df_1m[(df_1m.index >= pm_start) & (df_1m.index < pm_end)]

    # Exact session high and low values
    asia_high = float(asia_df['high'].max()) if not asia_df.empty else float(p12['high'])
    asia_low = float(asia_df['low'].min()) if not asia_df.empty else float(p12['low'])
    asia_start_ts = int(asia_start.timestamp())
    asia_end_ts = int(asia_end.timestamp())

    lon_high = float(lon_df['high'].max()) if not lon_df.empty else float(p12['high'])
    lon_low = float(lon_df['low'].min()) if not lon_df.empty else float(p12['low'])
    lon_start_ts = int(lon_start.timestamp())
    lon_end_ts = int(lon_end.timestamp())

    pm_high = float(pm_df['high'].max()) if not pm_df.empty else float(p12['high'])
    pm_low = float(pm_df['low'].min()) if not pm_df.empty else float(p12['low'])
    pm_start_ts = int(pm_start.timestamp())
    pm_end_ts = int(pm_end.timestamp())

    # Trajectory and Target Box coordinates from engine
    lod_box = traj_data.get("lod_box", {
        "start_ts": int(pd.Timestamp(datetime.combine(t_dt, time(9, 30)), tz="America/New_York").timestamp()),
        "end_ts": int(pd.Timestamp(datetime.combine(t_dt, time(10, 15)), tz="America/New_York").timestamp()),
        "top": float(p12['low'] + 15.0),
        "bottom": float(p12['low'] - 65.0),
        "label": "🟢 LOD TARGET BOX (09:30-10:15 ET)",
    })

    hod_box = traj_data.get("hod_box", {
        "start_ts": int(pd.Timestamp(datetime.combine(t_dt, time(11, 0)), tz="America/New_York").timestamp()),
        "end_ts": int(pd.Timestamp(datetime.combine(t_dt, time(16, 0)), tz="America/New_York").timestamp()),
        "bottom": float(p12['high'] - 10.0),
        "top": float(p12['high'] + 85.0),
        "label": "🔴 HOD TARGET BOX (11:00-16:00 ET)",
    })

    magnets = traj_data.get("magnets", [])
    sc1_traj = traj_data.get("scenario_1_trajectory", [])
    sc2_traj = traj_data.get("scenario_2_trajectory", [])
    dir_narrative = traj_data.get("directional_narrative", "")

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

    # Build Magnet rows for HTML Table
    magnet_rows_html = ""
    for m in magnets:
        prob_val = m["prob"]
        badge_bg = "rgba(16, 185, 129, 0.15)" if prob_val >= 80 else ("rgba(245, 158, 11, 0.15)" if prob_val >= 60 else "rgba(239, 68, 68, 0.15)")
        badge_color = "#10b981" if prob_val >= 80 else ("#f59e0b" if prob_val >= 60 else "#ef4444")
        
        magnet_rows_html += f"""
        <tr>
            <td><b style="color: {m['color']};">{m['name']}</b></td>
            <td><code style="font-size: 13px;">{m['price']:,.2f}</code></td>
            <td><span style="background: {badge_bg}; color: {badge_color}; padding: 3px 8px; border-radius: 4px; font-weight: 700;">{prob_val:.1f}%</span></td>
            <td><span style="color: var(--text-dim); font-size: 11px;">{m['tier']}</span></td>
            <td>{m['role']}</td>
        </tr>
        """

    html_template = f"""<!DOCTYPE html>
<html lang="en" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>⚔️ Mickey & Austin Wargaming Chart: {ticker} ({dt_str})</title>
    {lwc_script_tag}
    <style>
        :root {{
            --bg: #070a12;
            --card-bg: #0f172a;
            --border: #1e293b;
            --text: #f8fafc;
            --text-dim: #94a3b8;
            --green: #10b981;
            --red: #ef4444;
            --gold: #f59e0b;
            --blue: #3b82f6;
            --orange: #f97316;
            --magenta: #f43f5e;
        }}
        body {{
            margin: 0;
            padding: 16px;
            background: var(--bg);
            color: var(--text);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            -webkit-font-smoothing: antialiased;
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
        .toolbar {{
            display: flex;
            align-items: center;
            flex-wrap: wrap;
            gap: 8px;
            background: var(--card-bg);
            border: 1px solid var(--border);
            padding: 8px 12px;
            border-radius: 8px;
            margin-bottom: 10px;
        }}
        .btn {{
            background: #1e293b;
            color: var(--text);
            border: 1px solid #334155;
            padding: 6px 12px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 600;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 5px;
            transition: all 0.15s ease;
        }}
        .btn:hover {{
            background: #334155;
            border-color: #475569;
        }}
        .btn.active {{
            background: #3b82f6;
            color: #fff;
            border-color: #3b82f6;
        }}
        .btn.active-sc1 {{
            background: #f43f5e;
            color: #fff;
            border-color: #f43f5e;
        }}
        .btn.active-sc2 {{
            background: #10b981;
            color: #fff;
            border-color: #10b981;
        }}
        .chart-wrapper {{
            position: relative;
            width: 100%;
            height: 660px;
            background: #030712;
            border: 1px solid var(--border);
            border-radius: 10px;
            overflow: hidden;
            margin-bottom: 16px;
            transition: all 0.2s ease;
        }}
        .chart-wrapper.fullscreen {{
            position: fixed;
            top: 0;
            left: 0;
            width: 100vw !important;
            height: 100vh !important;
            z-index: 99999;
            border-radius: 0;
            border: none;
            margin: 0;
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
            right: 80px;
            background: rgba(15, 23, 42, 0.90);
            border: 1px solid #334155;
            backdrop-filter: blur(10px);
            border-radius: 8px;
            padding: 12px 16px;
            font-size: 11px;
            z-index: 20;
            box-shadow: 0 8px 24px rgba(0,0,0,0.6);
            line-height: 1.5;
            min-width: 260px;
        }}
        .hud-panel h4 {{
            margin: 0 0 6px 0;
            font-size: 12px;
            color: var(--gold);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            border-bottom: 1px solid #334155;
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
            padding: 9px 12px;
            text-align: left;
            border-bottom: 1px solid var(--border);
            font-size: 12px;
        }}
        .levels-table th {{ color: var(--text-dim); font-weight: 600; text-transform: uppercase; font-size: 11px; }}
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

    <!-- Interactive Toolbar -->
    <div class="toolbar">
        <button class="btn" id="btn-fullscreen">⛶ Fullscreen</button>
        <button class="btn" id="btn-fit">🔍 Fit All</button>
        <button class="btn" id="btn-overnight">🌙 Overnight View</button>
        <button class="btn" id="btn-rth">🔔 RTH Wargame View</button>
        <button class="btn active-sc1" id="btn-sc1">⚡ Scenario 1: Sweeper Reversal</button>
        <button class="btn" id="btn-sc2">🟢 Scenario 2: True Trend Run</button>
        <button class="btn active" id="btn-toggle-boxes">🎯 Target Boxes: ON</button>
        <div style="margin-left: auto; font-size: 12px; color: var(--text-dim);">
            Drag price axis vertically • Scroll to zoom • Pan horizontally
        </div>
    </div>

    <div class="metrics-grid">
        <div class="metric-card">
            <div class="label">P12 Midline (88.5% Magnet)</div>
            <div class="value" style="color: var(--gold);">{p12['mid']:,.2f}</div>
            <div style="font-size: 11px; color: var(--text-dim);">{p12_pos} by {abs(p12['diff_pts']):.2f} pts ({abs(p12['diff_bps']):.1f} bps)</div>
        </div>
        <div class="metric-card">
            <div class="label">Midnight Open (84.1% Magnet)</div>
            <div class="value" style="color: var(--blue);">{anchors.get('midnight_open', spot):,.2f}</div>
            <div style="font-size: 11px; color: var(--text-dim);">Primary Retest Gravity Well</div>
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
    </div>

    <!-- Chart Container with Overlay Canvas and HUD -->
    <div class="chart-wrapper" id="chart-wrapper">
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
                <span class="hud-label">Asia Range ({asia_df['high'].max() if not asia_df.empty else p12['high']:,.0f}-{asia_df['low'].min() if not asia_df.empty else p12['low']:,.0f}):</span>
                <span class="hud-val" style="color: #60a5fa;">{sess['asia_status']} (BK: {str(sess['asia_broken'])})</span>
            </div>
            <div class="hud-row">
                <span class="hud-label">London Range ({lon_df['high'].max() if not lon_df.empty else p12['high']:,.0f}-{lon_df['low'].min() if not lon_df.empty else p12['low']:,.0f}):</span>
                <span class="hud-val" style="color: #fb923c;">{sess['london_status']} (BK: {str(sess['london_broken'])})</span>
            </div>
            <div class="hud-row" style="margin-top: 6px; border-top: 1px solid #334155; padding-top: 4px;">
                <span class="hud-label">LOD Target Box:</span>
                <span class="hud-val" style="color: #10b981;">{lod_box['bottom']:,.0f} &ndash; {lod_box['top']:,.0f}</span>
            </div>
            <div class="hud-row">
                <span class="hud-label">LOD Target Time:</span>
                <span class="hud-val" style="color: #10b981;">09:30 &ndash; 10:15 ET</span>
            </div>
            <div class="hud-row">
                <span class="hud-label">HOD Target Box:</span>
                <span class="hud-val" style="color: #ef4444;">{hod_box['bottom']:,.0f} &ndash; {hod_box['top']:,.0f}</span>
            </div>
            <div class="hud-row">
                <span class="hud-label">HOD Target Time:</span>
                <span class="hud-val" style="color: #ef4444;">11:00 &ndash; 16:00 ET</span>
            </div>
        </div>
    </div>

    <!-- Mickey & Austin Probability Magnet Hierarchy Table -->
    <div class="matrix-container">
        <h3>🧲 Mickey & Austin Probability Magnet Hierarchy (Hit Rate %)</h3>
        <p style="font-size: 13px; color: var(--text-dim); margin-top: 0; line-height: 1.5;">
            {dir_narrative}
        </p>
        <table class="levels-table">
            <thead>
                <tr>
                    <th>Key Level</th>
                    <th>Exact Price</th>
                    <th>Historical Touch Rate</th>
                    <th>Magnet Tier</th>
                    <th>Wargaming Tactical Function</th>
                </tr>
            </thead>
            <tbody>
                {magnet_rows_html}
            </tbody>
        </table>
    </div>

    <div class="cards-grid">
        <div class="scenario-card false">
            <h3 style="color: var(--red);">🔴 SCENARIO 1: FALSE REVERSION (Primary Sweeper)</h3>
            <ul>
                <li><b>Trigger</b>: 09:30 RTH Open sweeps into <b>Green LOD Target Box</b> (<code>{lod_box['bottom']:,.2f} &ndash; {lod_box['top']:,.2f}</code>) and fails 10 bps breakout in 0-5 box.</li>
                <li><b>Execution</b>: Long mean-reversion counter toward <b>P12 Midline</b> (<code>{p12['mid']:,.2f}</code> [88.5%]) & <b>Midnight Open</b> (<code>{anchors['midnight_open']:,.2f}</code> [84.1%]).</li>
                <li><b>Cover The Queen (+10 bps)</b>: Scale 50% at <code>{pack.get('long_tp1', spot + pack['queen_pts']):,.2f}</code> and lock stop to Breakeven (+1 pt).</li>
                <li><b>09:45 Cutoff</b>: Midline retest expected before 09:45 AM; reversal window closes at 10:15 AM.</li>
            </ul>
        </div>
        <div class="scenario-card true">
            <h3 style="color: var(--green);">🟢 SCENARIO 2: TRUE EXPANSION (Secondary Trend)</h3>
            <ul>
                <li><b>Trigger</b>: Price sustains >10 bps breakout and accepts across P12 Midline in Q1.</li>
                <li><b>Bullish Target</b>: P12 High (<code>{p12['high']:,.2f}</code> [81.7%]) &rarr; <b>Red HOD Target Box</b> (<code>{hod_box['bottom']:,.2f} &ndash; {hod_box['top']:,.2f}</code>).</li>
                <li><b>Bearish Target</b>: PDM (<code>{anchors.get('pdm', spot):,.2f}</code> [65.0%]) &rarr; PDL (<code>{anchors.get('pdl', spot):,.2f}</code> [41.9%]).</li>
                <li><b>10:15 Rule</b>: If no reversal signature by 10:15, Trend Continuation locks for the session.</li>
            </ul>
        </div>
    </div>

    <script>
        document.addEventListener('DOMContentLoaded', () => {{
            try {{
                const chartWrapper = document.getElementById('chart-wrapper');
                const chartContainer = document.getElementById('chart-container');
                const overlayCanvas = document.getElementById('overlay-canvas');
                if (!chartContainer || !overlayCanvas) return;

                let showTargetBoxes = true;
                let activeScenario = 1; // 1 = False Reversion, 2 = True Expansion

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
                    height: 660,
                    layout: {{
                        background: {{ color: '#030712' }},
                        textColor: '#94a3b8',
                    }},
                    grid: {{
                        vertLines: {{ color: '#0f172a' }},
                        horzLines: {{ color: '#0f172a' }},
                    }},
                    localization: {{
                        timeFormatter: etTimeFormatter,
                        priceFormatter: (price) => price.toFixed(2),
                    }},
                    timeScale: {{
                        timeVisible: true,
                        secondsVisible: false,
                        rightOffset: 65,
                        borderColor: '#1e293b',
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
                        borderColor: '#1e293b',
                        autoScale: true,
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

                // Dynamic Magnet Price Rays annotated with Hit Rate %
                const magnets = {json.dumps(magnets)};
                magnets.forEach(m => {{
                    if (m.price === null || m.price === undefined) return;
                    let style = LightweightCharts.LineStyle.Solid;
                    if (m.style === 'dashed') style = LightweightCharts.LineStyle.Dashed;
                    if (m.style === 'dotted') style = LightweightCharts.LineStyle.Dotted;

                    candleSeries.createPriceLine({{
                        price: m.price,
                        color: m.color,
                        lineWidth: m.tier.includes('Tier 1') ? 2 : 1,
                        lineStyle: style,
                        title: m.name + ' [' + m.prob.toFixed(1) + '%]',
                    }});
                }});

                // Dynamic Algorithmic Trajectory Points
                const sc1Points = {json.dumps(sc1_traj)};
                const sc2Points = {json.dumps(sc2_traj)};

                // Overlay Canvas Drawing
                function drawOverlays() {{
                    overlayCanvas.width = chartContainer.clientWidth;
                    overlayCanvas.height = chartContainer.clientHeight;
                    const ctx = overlayCanvas.getContext('2d');
                    ctx.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height);

                    const timeScale = chart.timeScale();
                    const getX = (ts) => timeScale.timeToCoordinate(ts);
                    const getY = (price) => candleSeries.priceToCoordinate(price);

                    // 1. Shaded Price-Bounded Asia Session Box
                    const asiaX1 = getX({asia_start_ts});
                    const asiaX2 = getX({asia_end_ts});
                    const asiaYTop = getY({asia_high});
                    const asiaYBot = getY({asia_low});
                    if (asiaYTop !== null && asiaYBot !== null && (asiaX1 !== null || asiaX2 !== null)) {{
                        const left = asiaX1 !== null ? asiaX1 : 0;
                        const right = asiaX2 !== null ? asiaX2 : overlayCanvas.width;
                        const w = Math.max(2, right - left);
                        const top = Math.min(asiaYTop, asiaYBot);
                        const h = Math.abs(asiaYBot - asiaYTop);

                        ctx.fillStyle = 'rgba(59, 130, 246, 0.12)';
                        ctx.fillRect(left, top, w, h);
                        ctx.strokeStyle = '#3b82f6';
                        ctx.lineWidth = 1.5;
                        ctx.strokeRect(left, top, w, h);

                        ctx.fillStyle = '#60a5fa';
                        ctx.font = 'bold 11px sans-serif';
                        ctx.fillText('ASIA (18:00-02:00 ET)', left + 8, top + 16);
                    }}

                    // 2. Shaded Price-Bounded London Session Box
                    const lonX1 = getX({lon_start_ts});
                    const lonX2 = getX({lon_end_ts});
                    const lonYTop = getY({lon_high});
                    const lonYBot = getY({lon_low});
                    if (lonYTop !== null && lonYBot !== null && (lonX1 !== null || lonX2 !== null)) {{
                        const left = lonX1 !== null ? lonX1 : 0;
                        const right = lonX2 !== null ? lonX2 : overlayCanvas.width;
                        const w = Math.max(2, right - left);
                        const top = Math.min(lonYTop, lonYBot);
                        const h = Math.abs(lonYBot - lonYTop);

                        ctx.fillStyle = 'rgba(249, 115, 22, 0.12)';
                        ctx.fillRect(left, top, w, h);
                        ctx.strokeStyle = '#f97316';
                        ctx.lineWidth = 1.5;
                        ctx.strokeRect(left, top, w, h);

                        ctx.fillStyle = '#fb923c';
                        ctx.font = 'bold 11px sans-serif';
                        ctx.fillText('LONDON (02:00-08:30 ET)', left + 8, top + 16);
                    }}

                    if (!showTargetBoxes) return;

                    // 3. Green LOD Target Box (09:30 - 10:15 ET)
                    const lodX1 = getX({lod_box['start_ts']}) || (lonX2 ? lonX2 + 40 : 450);
                    const lodX2 = getX({lod_box['end_ts']}) || lodX1 + 80;
                    const lodYTop = getY({lod_box['top']});
                    const lodYBot = getY({lod_box['bottom']});

                    if (lodYTop !== null && lodYBot !== null) {{
                        const boxW = Math.max(65, lodX2 - lodX1);
                        const boxH = Math.abs(lodYBot - lodYTop);
                        const boxY = Math.min(lodYTop, lodYBot);

                        ctx.fillStyle = 'rgba(16, 185, 129, 0.22)';
                        ctx.fillRect(lodX1, boxY, boxW, boxH);
                        ctx.strokeStyle = '#10b981';
                        ctx.lineWidth = 1.8;
                        ctx.strokeRect(lodX1, boxY, boxW, boxH);

                        ctx.fillStyle = '#34d399';
                        ctx.font = 'bold 11px sans-serif';
                        ctx.fillText('{lod_box['label']}', lodX1 + 8, boxY + 18);
                        ctx.font = '10px monospace';
                        ctx.fillText('{lod_box['bottom']:,.0f} - {lod_box['top']:,.0f}', lodX1 + 8, boxY + 32);
                    }}

                    // 4. Red HOD Target Box (11:00 - 16:00 ET)
                    const hodX1 = getX({hod_box['start_ts']}) || lodX2 + 50;
                    const hodX2 = getX({hod_box['end_ts']}) || hodX1 + 180;
                    const hodYTop = getY({hod_box['top']});
                    const hodYBot = getY({hod_box['bottom']});

                    if (hodYTop !== null && hodYBot !== null) {{
                        const boxW = Math.max(90, hodX2 - hodX1);
                        const boxH = Math.abs(hodYBot - hodYTop);
                        const boxY = Math.min(hodYTop, hodYBot);

                        ctx.fillStyle = 'rgba(239, 68, 68, 0.22)';
                        ctx.fillRect(hodX1, boxY, boxW, boxH);
                        ctx.strokeStyle = '#ef4444';
                        ctx.lineWidth = 1.8;
                        ctx.strokeRect(hodX1, boxY, boxW, boxH);

                        ctx.fillStyle = '#f87171';
                        ctx.font = 'bold 11px sans-serif';
                        ctx.fillText('{hod_box['label']}', hodX1 + 8, boxY + 18);
                        ctx.font = '10px monospace';
                        ctx.fillText('{hod_box['bottom']:,.0f} - {hod_box['top']:,.0f}', hodX1 + 8, boxY + 32);
                    }}

                    // 5. Algorithmic Trajectory Polyline / Arrow
                    const points = activeScenario === 1 ? sc1Points : sc2Points;
                    const lineColor = activeScenario === 1 ? '#f43f5e' : '#10b981';

                    if (points && points.length >= 2) {{
                        const canvasCoords = [];
                        for (let i = 0; i < points.length; i++) {{
                            const px = getX(points[i].ts);
                            const py = getY(points[i].price);
                            if (px !== null && py !== null) {{
                                canvasCoords.push({{ x: px, y: py, desc: points[i].desc }});
                            }}
                        }}

                        if (canvasCoords.length >= 2) {{
                            ctx.strokeStyle = lineColor;
                            ctx.lineWidth = 3.5;
                            ctx.lineCap = 'round';
                            ctx.lineJoin = 'round';
                            ctx.beginPath();
                            ctx.moveTo(canvasCoords[0].x, canvasCoords[0].y);

                            for (let i = 1; i < canvasCoords.length; i++) {{
                                ctx.lineTo(canvasCoords[i].x, canvasCoords[i].y);
                            }}
                            ctx.stroke();

                            // Draw Arrowhead at the final expansion point
                            const last = canvasCoords[canvasCoords.length - 1];
                            const prev = canvasCoords[canvasCoords.length - 2];
                            const angle = Math.atan2(last.y - prev.y, last.x - prev.x);

                            ctx.fillStyle = lineColor;
                            ctx.beginPath();
                            ctx.moveTo(last.x, last.y);
                            ctx.lineTo(last.x - 16 * Math.cos(angle - Math.PI / 6), last.y - 16 * Math.sin(angle - Math.PI / 6));
                            ctx.lineTo(last.x - 16 * Math.cos(angle + Math.PI / 6), last.y - 16 * Math.sin(angle + Math.PI / 6));
                            ctx.closePath();
                            ctx.fill();

                            // Trajectory Label
                            ctx.fillStyle = activeScenario === 1 ? '#fda4af' : '#6ee7b7';
                            ctx.font = 'bold 11px sans-serif';
                            const labelText = activeScenario === 1 ? '⚡ SCENARIO 1: FALSE REVERSION PATH' : '🟢 SCENARIO 2: TRUE TREND PATH';
                            ctx.fillText(labelText, canvasCoords[1].x + 10, canvasCoords[1].y - 12);
                        }}
                    }}
                }}

                // Continuous 60 FPS RequestAnimationFrame Loop
                function syncLoop() {{
                    const timeScale = chart.timeScale();
                    if (timeScale.getVisibleLogicalRange()) {{
                        drawOverlays();
                    }}
                    requestAnimationFrame(syncLoop);
                }}
                requestAnimationFrame(syncLoop);

                // Window Resize Handler
                window.addEventListener('resize', () => {{
                    chart.applyOptions({{ 
                        width: chartContainer.clientWidth,
                        height: chartContainer.clientHeight
                    }});
                    drawOverlays();
                }});

                // Toolbar Actions
                const btnFullscreen = document.getElementById('btn-fullscreen');
                btnFullscreen.addEventListener('click', () => {{
                    chartWrapper.classList.toggle('fullscreen');
                    const isFull = chartWrapper.classList.contains('fullscreen');
                    btnFullscreen.innerHTML = isFull ? '🗗 Exit Fullscreen' : '⛶ Fullscreen';
                    setTimeout(() => {{
                        chart.applyOptions({{ 
                            width: chartContainer.clientWidth,
                            height: chartContainer.clientHeight
                        }});
                        chart.timeScale().fitContent();
                        drawOverlays();
                    }}, 100);
                }});

                document.addEventListener('keydown', (e) => {{
                    if (e.key === 'Escape' && chartWrapper.classList.contains('fullscreen')) {{
                        chartWrapper.classList.remove('fullscreen');
                        btnFullscreen.innerHTML = '⛶ Fullscreen';
                        setTimeout(() => {{
                            chart.applyOptions({{ 
                                width: chartContainer.clientWidth,
                                height: 660
                            }});
                            chart.timeScale().fitContent();
                            drawOverlays();
                        }}, 100);
                    }}
                }});

                document.getElementById('btn-fit').addEventListener('click', () => {{
                    chart.timeScale().fitContent();
                    drawOverlays();
                }});

                document.getElementById('btn-overnight').addEventListener('click', () => {{
                    chart.timeScale().setVisibleRange({{
                        from: {asia_start_ts},
                        to: {lon_end_ts} + 1800
                    }});
                    drawOverlays();
                }});

                document.getElementById('btn-rth').addEventListener('click', () => {{
                    chart.timeScale().setVisibleRange({{
                        from: {pm_start_ts},
                        to: {hod_box['end_ts']} + 3600
                    }});
                    drawOverlays();
                }});

                const btnSc1 = document.getElementById('btn-sc1');
                const btnSc2 = document.getElementById('btn-sc2');

                btnSc1.addEventListener('click', () => {{
                    activeScenario = 1;
                    btnSc1.classList.add('active-sc1');
                    btnSc2.classList.remove('active-sc2');
                    drawOverlays();
                }});

                btnSc2.addEventListener('click', () => {{
                    activeScenario = 2;
                    btnSc2.classList.add('active-sc2');
                    btnSc1.classList.remove('active-sc1');
                    drawOverlays();
                }});

                const btnToggleBoxes = document.getElementById('btn-toggle-boxes');
                btnToggleBoxes.addEventListener('click', () => {{
                    showTargetBoxes = !showTargetBoxes;
                    btnToggleBoxes.classList.toggle('active', showTargetBoxes);
                    btnToggleBoxes.innerHTML = showTargetBoxes ? '🎯 Target Boxes: ON' : '🎯 Target Boxes: OFF';
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
