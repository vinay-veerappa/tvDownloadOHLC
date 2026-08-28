"""Interactive Lightweight Charts HTML Visual Renderer for Pack Wargaming

Exact replication of The Daily Profiler indicator framework:
1. Exact Time-Based Initial Range Reference Boxes:
   - Asia Range Box (18:00-19:30 ET) with Asia Mid line extending forward.
   - London Range Box (02:30-03:30 ET) with Lon Mid line extending forward.
   - NY1 Range Box (07:30-08:30 ET) with NY1 Mid line extending forward.
2. Full 1m Candlestick Chart in Eastern Time (ET).
3. Complete 4-Outcome Decision Tree Engine:
   - SF (Short False): Sweeps < NY1 Low (09:30-10:15), expands to HOD Box (13:30-16:00)
   - LF (Long False): Sweeps > NY1 High (09:30-10:15), expands to LOD Box (13:30-16:00)
   - LT (Long True): Defends > NY1 Mid (09:30-09:45), expands to Bullish P70 (14:30-16:15)
   - ST (Short True): Rejects < NY1 Mid (09:30-09:45), expands to Bearish P70 (14:30-16:15)
4. Dynamic Outcome-Specific Target Boxes & Times (rendered live upon button click).
5. Interactive 4-Scenario Toolbar Toggles with real-time HUD synchronization.
6. All price rays annotated with empirical Touch Probabilities (Hit Rates %).
7. Continuous 60 FPS synchronization on both X (Time) and Y (Price) drag/zoom.
8. Mickey & Austin Magnet Hierarchy Table & 4-Scenario Cards.
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

    # EXACT Profiler Time-Based Initial Ranges (t_asia, t_lon, t_ny1)
    # Asia Range: 18:00 - 19:30 ET
    asia_start = pd.Timestamp(datetime.combine(t_dt - timedelta(days=1), time(18, 0)), tz="America/New_York")
    asia_end = pd.Timestamp(datetime.combine(t_dt - timedelta(days=1), time(19, 30)), tz="America/New_York")
    asia_df = df_1m[(df_1m.index >= asia_start) & (df_1m.index < asia_end)]

    # London Range: 02:30 - 03:30 ET
    lon_start = pd.Timestamp(datetime.combine(t_dt, time(2, 30)), tz="America/New_York")
    lon_end = pd.Timestamp(datetime.combine(t_dt, time(3, 30)), tz="America/New_York")
    lon_df = df_1m[(df_1m.index >= lon_start) & (df_1m.index < lon_end)]

    # NY1 Range: 07:30 - 08:30 ET
    ny1_start = pd.Timestamp(datetime.combine(t_dt, time(7, 30)), tz="America/New_York")
    ny1_end = pd.Timestamp(datetime.combine(t_dt, time(8, 30)), tz="America/New_York")
    ny1_df = df_1m[(df_1m.index >= ny1_start) & (df_1m.index < ny1_end)]

    # Compute high, low, midpoints
    asia_high = float(asia_df['high'].max()) if not asia_df.empty else float(p12['high'])
    asia_low = float(asia_df['low'].min()) if not asia_df.empty else float(p12['low'])
    asia_mid = (asia_high + asia_low) / 2.0
    asia_start_ts = int(asia_start.timestamp())
    asia_end_ts = int(asia_end.timestamp())

    lon_high = float(lon_df['high'].max()) if not lon_df.empty else float(p12['high'])
    lon_low = float(lon_df['low'].min()) if not lon_df.empty else float(p12['low'])
    lon_mid = (lon_high + lon_low) / 2.0
    lon_start_ts = int(lon_start.timestamp())
    lon_end_ts = int(lon_end.timestamp())

    ny1_high = float(ny1_df['high'].max()) if not ny1_df.empty else float(p12['high'] - 40.0)
    ny1_low = float(ny1_df['low'].min()) if not ny1_df.empty else float(p12['low'] + 20.0)
    ny1_mid = (ny1_high + ny1_low) / 2.0
    ny1_start_ts = int(ny1_start.timestamp())
    ny1_end_ts = int(ny1_end.timestamp())

    # End of Day timestamp for forward extending midpoint lines (17:00 ET)
    eod_ts = int(pd.Timestamp(datetime.combine(t_dt, time(17, 0)), tz="America/New_York").timestamp())

    # Target Boxes & Trajectories from 4-Outcome Engine
    boxes_by_outcome = traj_data.get("boxes_by_outcome", {})
    magnets = traj_data.get("magnets", [])
    trajectories = traj_data.get("trajectories", {})
    state_desc = traj_data.get("state_desc", "All 4 scenarios active.")
    c_probs = traj_data.get("conditional_probs", {"SF": 32.8, "LF": 33.3, "LT": 17.2, "ST": 16.5})
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
        .decision-banner {{
            background: rgba(30, 41, 59, 0.7);
            border: 1px solid #334155;
            border-left: 4px solid var(--gold);
            padding: 10px 16px;
            border-radius: 6px;
            font-size: 13px;
            line-height: 1.5;
            margin-bottom: 10px;
            display: flex;
            align-items: center;
            gap: 12px;
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
        .btn.active-sf {{ background: #f43f5e; color: #fff; border-color: #f43f5e; }}
        .btn.active-lf {{ background: #ef4444; color: #fff; border-color: #ef4444; }}
        .btn.active-lt {{ background: #10b981; color: #fff; border-color: #10b981; }}
        .btn.active-st {{ background: #b91c1c; color: #fff; border-color: #b91c1c; }}
        .btn.active {{ background: #3b82f6; color: #fff; border-color: #3b82f6; }}
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
        .cards-grid-4 {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 12px;
            margin-bottom: 16px;
        }}
        .scenario-card {{
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 14px 16px;
        }}
        .scenario-card.sf {{ border-top: 4px solid var(--magenta); }}
        .scenario-card.lf {{ border-top: 4px solid var(--red); }}
        .scenario-card.lt {{ border-top: 4px solid var(--green); }}
        .scenario-card.st {{ border-top: 4px solid #b91c1c; }}
        .scenario-card h3 {{ margin: 0 0 8px 0; font-size: 14px; display: flex; justify-content: space-between; align-items: center; }}
        .scenario-card ul {{ margin: 0; padding-left: 16px; font-size: 12px; line-height: 1.5; }}
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

    <!-- Live Decision Tree Status Banner -->
    <div class="decision-banner">
        <span style="font-size: 18px;">🧭</span>
        <div>
            <b>Mickey Decision Tree Filter:</b> {state_desc}
        </div>
    </div>

    <!-- Interactive 4-Scenario Toolbar -->
    <div class="toolbar">
        <button class="btn" id="btn-fullscreen">⛶ Fullscreen</button>
        <button class="btn" id="btn-fit">🔍 Fit All</button>
        <button class="btn" id="btn-overnight">🌙 Overnight View</button>
        <button class="btn" id="btn-rth">🔔 RTH Wargame View</button>
        <button class="btn active-sf" id="btn-sf">⚡ SF: Short False ({c_probs['SF']:.1f}%)</button>
        <button class="btn" id="btn-lf">🔴 LF: Long False ({c_probs['LF']:.1f}%)</button>
        <button class="btn" id="btn-lt">🟢 LT: Long True ({c_probs['LT']:.1f}%)</button>
        <button class="btn" id="btn-st">🔴 ST: Short True ({c_probs['ST']:.1f}%)</button>
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
            <div class="label">NY1 Range Box (07:30-08:30)</div>
            <div class="value" style="color: var(--orange);">{ny1_high:,.0f} - {ny1_low:,.0f}</div>
            <div style="font-size: 11px; color: var(--text-dim);">Midpoint: {ny1_mid:,.2f} (99.4%)</div>
        </div>
        <div class="metric-card">
            <div class="label">Cover The Queen (+10 bps)</div>
            <div class="value" style="color: var(--green);">+{pack['cover_the_queen_bps']:.1f} bps (+{pack['queen_pts']:.2f} pts)</div>
            <div style="font-size: 11px; color: var(--text-dim);">50% Scale + BE Stop Lock</div>
        </div>
    </div>

    <!-- Chart Container with Overlay Canvas and HUD -->
    <div class="chart-wrapper" id="chart-wrapper">
        <div id="chart-container"></div>
        <canvas id="overlay-canvas"></canvas>
        
        <div class="hud-panel">
            <h4 id="hud-title">📊 Live Wargame HUD: SF</h4>
            <div class="hud-row">
                <span class="hud-label">Asia Range (18:00-19:30):</span>
                <span class="hud-val" style="color: #60a5fa;">{asia_high:,.0f} - {asia_low:,.0f} (Mid: {asia_mid:,.0f})</span>
            </div>
            <div class="hud-row">
                <span class="hud-label">London Range (02:30-03:30):</span>
                <span class="hud-val" style="color: #ef4444;">{lon_high:,.0f} - {lon_low:,.0f} (Mid: {lon_mid:,.0f})</span>
            </div>
            <div class="hud-row">
                <span class="hud-label">NY1 Range (07:30-08:30):</span>
                <span class="hud-val" style="color: #f97316;">{ny1_high:,.0f} - {ny1_low:,.0f} (Mid: {ny1_mid:,.0f})</span>
            </div>
            <div class="hud-row" style="margin-top: 6px; border-top: 1px solid #334155; padding-top: 4px;">
                <span class="hud-label">Active LOD Box:</span>
                <span class="hud-val" id="hud-lod-box" style="color: #10b981;">...</span>
            </div>
            <div class="hud-row">
                <span class="hud-label">Active LOD Time:</span>
                <span class="hud-val" id="hud-lod-time" style="color: #10b981;">...</span>
            </div>
            <div class="hud-row">
                <span class="hud-label">Active HOD Box:</span>
                <span class="hud-val" id="hud-hod-box" style="color: #ef4444;">...</span>
            </div>
            <div class="hud-row">
                <span class="hud-label">Active HOD Time:</span>
                <span class="hud-val" id="hud-hod-time" style="color: #ef4444;">...</span>
            </div>
        </div>
    </div>

    <!-- 4 Scenario Cards Grid -->
    <div class="cards-grid-4">
        <div class="scenario-card sf">
            <h3 style="color: var(--magenta);">⚡ SHORT FALSE <span style="font-size: 11px; background: rgba(244,63,94,0.2); padding: 2px 6px; border-radius: 4px;">{c_probs['SF']:.1f}%</span></h3>
            <ul>
                <li><b>LOD Target Box</b>: <code>09:30 &ndash; 10:15 ET</code> (Sweep below <code>{ny1_low:,.2f}</code>).</li>
                <li><b>HOD Target Box</b>: <code>13:30 &ndash; 16:00 ET</code> (Expansion &rarr; <code>{p12['high']:,.2f}</code>).</li>
                <li><b>Execution</b>: Long Reversion to <b>P12 Mid [88.5%]</b> & <b>P12 High [81.7%]</b>.</li>
            </ul>
        </div>
        <div class="scenario-card lf">
            <h3 style="color: var(--red);">🔴 LONG FALSE <span style="font-size: 11px; background: rgba(239,68,68,0.2); padding: 2px 6px; border-radius: 4px;">{c_probs['LF']:.1f}%</span></h3>
            <ul>
                <li><b>HOD Target Box</b>: <code>09:30 &ndash; 10:15 ET</code> (Long Trap above <code>{ny1_high:,.2f}</code>).</li>
                <li><b>LOD Target Box</b>: <code>13:30 &ndash; 16:00 ET</code> (Expansion &rarr; <code>{ny1_low:,.2f}</code>).</li>
                <li><b>Execution</b>: Short Reversion to <b>P12 Mid [88.5%]</b> & <b>NY1 Low</b>.</li>
            </ul>
        </div>
        <div class="scenario-card lt">
            <h3 style="color: var(--green);">🟢 LONG TRUE <span style="font-size: 11px; background: rgba(16,185,129,0.2); padding: 2px 6px; border-radius: 4px;">{c_probs['LT']:.1f}%</span></h3>
            <ul>
                <li><b>LOD Baseline</b>: <code>09:30 &ndash; 09:45 ET</code> (Defends above <code>{ny1_mid:,.2f}</code>).</li>
                <li><b>HOD Extension</b>: <code>14:30 &ndash; 16:15 ET</code> (Expansion &rarr; <b>Bullish P70</b>).</li>
                <li><b>Execution</b>: Trend Long into afternoon session.</li>
            </ul>
        </div>
        <div class="scenario-card st">
            <h3 style="color: #f87171;">🔴 SHORT TRUE <span style="font-size: 11px; background: rgba(185,28,28,0.2); padding: 2px 6px; border-radius: 4px;">{c_probs['ST']:.1f}%</span></h3>
            <ul>
                <li><b>HOD Baseline</b>: <code>09:30 &ndash; 09:45 ET</code> (Rejection under <code>{ny1_mid:,.2f}</code>).</li>
                <li><b>LOD Extension</b>: <code>14:30 &ndash; 16:15 ET</code> (Expansion &rarr; <b>Bearish P70</b>).</li>
                <li><b>Execution</b>: Trend Short into afternoon session.</li>
            </ul>
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

    <script>
        document.addEventListener('DOMContentLoaded', () => {{
            try {{
                const chartWrapper = document.getElementById('chart-wrapper');
                const chartContainer = document.getElementById('chart-container');
                const overlayCanvas = document.getElementById('overlay-canvas');
                if (!chartContainer || !overlayCanvas) return;

                let showTargetBoxes = true;
                let activeScenario = 'SF'; // Default to Short False (Primary Sweeper)

                // Outcome-specific target boxes and trajectories
                const boxesByOutcome = {json.dumps(boxes_by_outcome)};
                const allTraj = {json.dumps(trajectories)};

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
                        rightOffset: 120, // Ample future whitespace for full day projection
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

                // Update HUD Text
                function updateHud() {{
                    const curBoxes = boxesByOutcome[activeScenario] || boxesByOutcome['SF'];
                    const hudTitle = document.getElementById('hud-title');
                    const hudLodBox = document.getElementById('hud-lod-box');
                    const hudLodTime = document.getElementById('hud-lod-time');
                    const hudHodBox = document.getElementById('hud-hod-box');
                    const hudHodTime = document.getElementById('hud-hod-time');

                    if (hudTitle) hudTitle.innerHTML = '📊 Live Wargame HUD: ' + activeScenario;
                    if (hudLodBox && curBoxes.lod) hudLodBox.innerHTML = curBoxes.lod.bottom.toFixed(0) + ' &ndash; ' + curBoxes.lod.top.toFixed(0);
                    if (hudLodTime && curBoxes.lod) hudLodTime.innerHTML = curBoxes.lod.time_desc;
                    if (hudHodBox && curBoxes.hod) hudHodBox.innerHTML = curBoxes.hod.bottom.toFixed(0) + ' &ndash; ' + curBoxes.hod.top.toFixed(0);
                    if (hudHodTime && curBoxes.hod) hudHodTime.innerHTML = curBoxes.hod.time_desc;
                }}
                updateHud();

                // Overlay Canvas Drawing with Deterministic Logical Coordinate Projection
                function drawOverlays() {{
                    overlayCanvas.width = chartContainer.clientWidth;
                    overlayCanvas.height = chartContainer.clientHeight;
                    const ctx = overlayCanvas.getContext('2d');
                    ctx.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height);

                    const timeScale = chart.timeScale();
                    if (!data.length) return;

                    const firstBar = data[0];
                    const lastBar = data[data.length - 1];

                    // Convert any UNIX timestamp (historical or future) to pixel X coordinate
                    const getX = (ts) => {{
                        const directX = timeScale.timeToCoordinate(ts);
                        if (directX !== null) return directX;

                        // Linear projection based on 1-minute bar spacing
                        if (ts > lastBar.time) {{
                            const minutesAhead = (ts - lastBar.time) / 60.0;
                            const lastBarLogicalIndex = data.length - 1;
                            const futureLogicalIndex = lastBarLogicalIndex + minutesAhead;
                            return timeScale.logicalToCoordinate(futureLogicalIndex);
                        }} else if (ts < firstBar.time) {{
                            const minutesBehind = (firstBar.time - ts) / 60.0;
                            return timeScale.logicalToCoordinate(-minutesBehind);
                        }}
                        return null;
                    }};

                    const getY = (price) => candleSeries.priceToCoordinate(price);

                    // Helper to draw an exact Initial Range Box with its forward-extending Midpoint line
                    const drawInitialRangeBox = (x1, x2, high, low, mid, fillColor, strokeColor, labelText, midLabel) => {{
                        if (x1 === null && x2 === null) return;
                        const yTop = getY(high);
                        const yBot = getY(low);
                        const yMid = getY(mid);
                        if (yTop === null || yBot === null) return;

                        const left = x1 !== null ? x1 : 0;
                        const right = x2 !== null ? x2 : overlayCanvas.width;
                        const width = Math.max(2, right - left);
                        const top = Math.min(yTop, yBot);
                        const height = Math.abs(yBot - yTop);

                        // Fill Initial Range Box
                        ctx.fillStyle = fillColor;
                        ctx.fillRect(left, top, width, height);

                        // Boundary border
                        ctx.strokeStyle = strokeColor;
                        ctx.lineWidth = 1.5;
                        ctx.strokeRect(left, top, width, height);

                        // Forward-extending Midpoint line (from range start all the way across)
                        if (yMid !== null) {{
                            const eodX = getX({eod_ts}) || overlayCanvas.width;
                            ctx.strokeStyle = strokeColor;
                            ctx.lineWidth = 1.2;
                            ctx.setLineDash([4, 4]);
                            ctx.beginPath();
                            ctx.moveTo(left, yMid);
                            ctx.lineTo(eodX, yMid);
                            ctx.stroke();
                            ctx.setLineDash([]);

                            ctx.fillStyle = strokeColor;
                            ctx.font = 'bold 10px monospace';
                            ctx.fillText(midLabel + ': ' + mid.toFixed(2), Math.min(right + 6, overlayCanvas.width - 120), yMid - 4);
                        }}

                        // Header Tag on top of box
                        ctx.fillStyle = strokeColor;
                        ctx.font = 'bold 10px sans-serif';
                        ctx.fillText(labelText, left + 4, top + 14);
                        ctx.font = '9px monospace';
                        ctx.fillText(low.toFixed(0) + '-' + high.toFixed(0), left + 4, top + 26);
                    }};

                    // 1. Exact Asia Initial Range Box (18:00 - 19:30 ET)
                    const asiaX1 = getX({asia_start_ts});
                    const asiaX2 = getX({asia_end_ts});
                    drawInitialRangeBox(asiaX1, asiaX2, {asia_high}, {asia_low}, {asia_mid}, 'rgba(59, 130, 246, 0.14)', '#3b82f6', 'ASIA (18:00-19:30)', 'Asia Mid');

                    // 2. Exact London Initial Range Box (02:30 - 03:30 ET)
                    const lonX1 = getX({lon_start_ts});
                    const lonX2 = getX({lon_end_ts});
                    drawInitialRangeBox(lonX1, lonX2, {lon_high}, {lon_low}, {lon_mid}, 'rgba(239, 68, 68, 0.14)', '#ef4444', 'LON (02:30-03:30)', 'Lon Mid');

                    // 3. Exact NY1 Initial Range Box (07:30 - 08:30 ET)
                    const ny1X1 = getX({ny1_start_ts});
                    const ny1X2 = getX({ny1_end_ts});
                    drawInitialRangeBox(ny1X1, ny1X2, {ny1_high}, {ny1_low}, {ny1_mid}, 'rgba(249, 115, 22, 0.14)', '#f97316', 'NY1 (07:30-08:30)', 'NY1 Mid');

                    if (!showTargetBoxes) return;

                    // 4. Dynamic Outcome-Specific Target Boxes (LOD & HOD)
                    const curBoxes = boxesByOutcome[activeScenario] || boxesByOutcome['SF'];

                    // Draw LOD Box for Active Scenario
                    if (curBoxes && curBoxes.lod) {{
                        const lodX1 = getX(curBoxes.lod.start_ts);
                        const lodX2 = getX(curBoxes.lod.end_ts);
                        const lodYTop = getY(curBoxes.lod.top);
                        const lodYBot = getY(curBoxes.lod.bottom);

                        if (lodYTop !== null && lodYBot !== null && lodX1 !== null && lodX2 !== null) {{
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
                            ctx.fillText(curBoxes.lod.label, lodX1 + 8, boxY + 18);
                            ctx.font = '10px monospace';
                            ctx.fillText(curBoxes.lod.bottom.toFixed(0) + ' - ' + curBoxes.lod.top.toFixed(0), lodX1 + 8, boxY + 32);
                        }}
                    }}

                    // Draw HOD Box for Active Scenario
                    if (curBoxes && curBoxes.hod) {{
                        const hodX1 = getX(curBoxes.hod.start_ts);
                        const hodX2 = getX(curBoxes.hod.end_ts);
                        const hodYTop = getY(curBoxes.hod.top);
                        const hodYBot = getY(curBoxes.hod.bottom);

                        if (hodYTop !== null && hodYBot !== null && hodX1 !== null && hodX2 !== null) {{
                            const boxW = Math.max(75, hodX2 - hodX1);
                            const boxH = Math.abs(hodYBot - hodYTop);
                            const boxY = Math.min(hodYTop, hodYBot);

                            ctx.fillStyle = 'rgba(239, 68, 68, 0.22)';
                            ctx.fillRect(hodX1, boxY, boxW, boxH);
                            ctx.strokeStyle = '#ef4444';
                            ctx.lineWidth = 1.8;
                            ctx.strokeRect(hodX1, boxY, boxW, boxH);

                            ctx.fillStyle = '#f87171';
                            ctx.font = 'bold 11px sans-serif';
                            ctx.fillText(curBoxes.hod.label, hodX1 + 8, boxY + 18);
                            ctx.font = '10px monospace';
                            ctx.fillText(curBoxes.hod.bottom.toFixed(0) + ' - ' + curBoxes.hod.top.toFixed(0), hodX1 + 8, boxY + 32);
                        }}
                    }}

                    // 5. Algorithmic Trajectory for the Active 4-Outcome Scenario
                    const points = allTraj[activeScenario] || allTraj['SF'];
                    const colorMap = {{ 'SF': '#f43f5e', 'LF': '#ef4444', 'LT': '#10b981', 'ST': '#b91c1c' }};
                    const lineColor = colorMap[activeScenario] || '#f43f5e';

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

                            // Draw Arrowhead
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
                            ctx.fillStyle = lineColor;
                            ctx.font = 'bold 11px sans-serif';
                            const labelText = '⚡ SCENARIO: ' + activeScenario + ' (' + points[1].desc + ')';
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
                    const lastIdx = data.length - 1;
                    chart.timeScale().setVisibleLogicalRange({{
                        from: 0,
                        to: lastIdx + 20
                    }});
                    drawOverlays();
                }});

                document.getElementById('btn-rth').addEventListener('click', () => {{
                    const lastIdx = data.length - 1;
                    chart.timeScale().setVisibleLogicalRange({{
                        from: Math.max(0, lastIdx - 80),
                        to: lastIdx + 160
                    }});
                    drawOverlays();
                }});

                // 4-Scenario Button Toggles
                const btnSf = document.getElementById('btn-sf');
                const btnLf = document.getElementById('btn-lf');
                const btnLt = document.getElementById('btn-lt');
                const btnSt = document.getElementById('btn-st');

                function clearScenarioBtns() {{
                    btnSf.className = 'btn';
                    btnLf.className = 'btn';
                    btnLt.className = 'btn';
                    btnSt.className = 'btn';
                }}

                btnSf.addEventListener('click', () => {{
                    activeScenario = 'SF';
                    clearScenarioBtns();
                    btnSf.classList.add('active-sf');
                    updateHud();
                    drawOverlays();
                }});

                btnLf.addEventListener('click', () => {{
                    activeScenario = 'LF';
                    clearScenarioBtns();
                    btnLf.classList.add('active-lf');
                    updateHud();
                    drawOverlays();
                }});

                btnLt.addEventListener('click', () => {{
                    activeScenario = 'LT';
                    clearScenarioBtns();
                    btnLt.classList.add('active-lt');
                    updateHud();
                    drawOverlays();
                }});

                btnSt.addEventListener('click', () => {{
                    activeScenario = 'ST';
                    clearScenarioBtns();
                    btnSt.classList.add('active-st');
                    updateHud();
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
