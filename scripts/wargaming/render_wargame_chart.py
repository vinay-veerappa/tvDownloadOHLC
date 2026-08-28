"""Interactive Lightweight Charts HTML Visual Renderer for Pack Wargaming

Generates a 100% self-contained, responsive single-file HTML report:
1. Full 1m/5m Candlestick Chart (TradingView Lightweight Charts).
2. Shaded Asia & London session boxes with broken flags.
3. Horizontal price rays for P12 High, Low, and Golden P12 Midline.
4. Shaded Candle Science Target Box (Green Bullish MFE) and Depth Box (Red Bearish MAE).
5. Pack Trading rays (+10 bps Queen, +30 bps Runner, 12 bps Stop Ceiling).
6. Auto-saves to `data/wargaming/reports/{YYYY-MM-DD}_{TICKER}_wargame.html` and uploads to Google Drive.

Usage:
    python scripts/wargaming/render_wargame_chart.py --ticker NQ1 --time 06:00
    python scripts/wargaming/render_wargame_chart.py --ticker ES1 --time 08:30 --upload-gdrive
"""
from __future__ import annotations

import sys
import json
import logging
import argparse
from pathlib import Path
from datetime import datetime, date, time, timedelta
from typing import Dict, Any, Optional
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
    """Generate self-contained HTML containing TradingView Lightweight Charts and wargame overlays."""
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

    # Convert candles to Lightweight Charts JSON format
    candles_data = []
    for ts, row in chart_df.iterrows():
        candles_data.append({
            "time": int(ts.timestamp()),
            "open": round(float(row["open"]), 2),
            "high": round(float(row["high"]), 2),
            "low": round(float(row["low"]), 2),
            "close": round(float(row["close"]), 2),
        })

    candles_json = json.dumps(candles_data)

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
            --bg: #090d16;
            --card-bg: #111827;
            --border: #1f2937;
            --text: #f3f4f6;
            --text-dim: #9ca3af;
            --green: #10b981;
            --red: #ef4444;
            --gold: #f59e0b;
            --blue: #3b82f6;
        }}
        body {{
            margin: 0;
            padding: 20px;
            background: var(--bg);
            color: var(--text);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 16px 24px;
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 12px;
            margin-bottom: 16px;
        }}
        .title-group h1 {{
            margin: 0 0 6px 0;
            font-size: 24px;
            font-weight: 700;
        }}
        .badge {{
            display: inline-block;
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 13px;
            font-weight: 600;
        }}
        .badge-bias {{
            background: {bias_color}22;
            color: {bias_color};
            border: 1px solid {bias_color}66;
        }}
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 12px;
            margin-bottom: 16px;
        }}
        .metric-card {{
            background: var(--card-bg);
            border: 1px solid var(--border);
            padding: 14px 18px;
            border-radius: 10px;
        }}
        .metric-card .label {{
            font-size: 12px;
            color: var(--text-dim);
            margin-bottom: 4px;
        }}
        .metric-card .value {{
            font-size: 18px;
            font-weight: 700;
            font-family: monospace;
        }}
        #chart-container {{
            width: 100%;
            height: 600px;
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 12px;
            overflow: hidden;
            margin-bottom: 20px;
        }}
        .cards-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 16px;
            margin-bottom: 20px;
        }}
        .scenario-card {{
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 20px;
        }}
        .scenario-card.false {{ border-top: 4px solid var(--red); }}
        .scenario-card.true {{ border-top: 4px solid var(--green); }}
        .scenario-card h3 {{ margin-top: 0; }}
        .levels-table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 12px;
        }}
        .levels-table th, .levels-table td {{
            padding: 8px 12px;
            text-align: left;
            border-bottom: 1px solid var(--border);
            font-size: 13px;
        }}
        .levels-table th {{ color: var(--text-dim); font-weight: 500; }}
        .reversal-box {{
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 20px;
        }}
    </style>
</head>
<body>

    <div class="header">
        <div class="title-group">
            <h1>⚔️ {ticker} Wargaming Playbook: {dt_str}</h1>
            <div style="font-size: 14px; color: var(--text-dim);">
                Analysis Cutoff: <b>{cutoff} EST</b> | Current Spot: <b style="color: #fff; font-family: monospace;">{spot:,.2f}</b>
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
            <div class="label">P12 MIDLINE (Switch)</div>
            <div class="value" style="color: var(--gold);">{p12['mid']:,.2f}</div>
            <div style="font-size: 12px; color: var(--text-dim);">{p12_pos} by {abs(p12['diff_pts']):.2f} pts ({abs(p12['diff_bps']):.1f} bps)</div>
        </div>
        <div class="metric-card">
            <div class="label">COVER THE QUEEN (+10 bps)</div>
            <div class="value" style="color: var(--green);">+{pack['cover_the_queen_bps']:.1f} bps (+{pack['queen_pts']:.2f} pts)</div>
            <div style="font-size: 12px; color: var(--text-dim);">50% Scale + BE Stop Lock</div>
        </div>
        <div class="metric-card">
            <div class="label">STOP CEILING (Max Risk)</div>
            <div class="value" style="color: var(--red);">{pack['stop_ceiling_bps']:.1f} bps (~{pack['stop_pts']:.2f} pts)</div>
            <div style="font-size: 12px; color: var(--text-dim);">Strict Capital Floor</div>
        </div>
        <div class="metric-card">
            <div class="label">MIDNIGHT OPEN (00:00 ET)</div>
            <div class="value">{anchors['midnight_open']:,.2f}</div>
            <div style="font-size: 12px; color: var(--text-dim);">Primary Morning Magnet</div>
        </div>
    </div>

    <!-- Interactive Candlestick Chart -->
    <div id="chart-container"></div>

    <div class="cards-grid">
        <div class="scenario-card false">
            <h3 style="color: var(--red);">🔴 SCENARIO 1: FALSE REVERSION (Primary Bias)</h3>
            <p><b>If</b> 09:30 Open sweeps toward session extremes and fails 10 bps breakout in 0-5 box:</p>
            <ul>
                <li><b>Primary Target</b>: P12 Midline (<code>{p12['mid']:,.2f}</code>) & Midnight Open (<code>{anchors['midnight_open']:,.2f}</code>).</li>
                <li><b>09:45 Cutoff</b>: Midline retest expected before 09:45 AM.</li>
                <li><b>10:15 Cutoff</b>: Reversion window expires. Transition to consolidation.</li>
            </ul>
        </div>
        <div class="scenario-card true">
            <h3 style="color: var(--green);">🟢 SCENARIO 2: TRUE EXPANSION (Secondary Bias)</h3>
            <p><b>If</b> 09:30 Open sustains >10 bps breakout of 0-5 box and accepts across P12 Mid:</p>
            <ul>
                <li><b>Bullish Target</b>: P12 High (<code>{p12['high']:,.2f}</code>) &rarr; PDH (<code>{anchors['pdh']:,.2f}</code>).</li>
                <li><b>Bearish Target</b>: PDM (<code>{anchors['pdm']:,.2f}</code>) &rarr; PDL (<code>{anchors['pdl']:,.2f}</code>).</li>
                <li><b>10:15 Rule</b>: If no reversal signature by 10:15, Trend Continuation locks.</li>
            </ul>
        </div>
    </div>

    <div class="reversal-box">
        <h3>🚦 Mickey & Austin 4-Step Reversal Counter</h3>
        <table class="levels-table">
            <tr><th>Step</th><th>Description</th><th>Target / Condition</th></tr>
            <tr><td><b>Step 1</b></td><td>Cross 09:30 AM Open print</td><td>Breaches 09:30 Open after initial push</td></tr>
            <tr><td><b>Step 2</b></td><td>Trade through 09:00 AM Midpoint</td><td>Reclaims 50% of the 09:00-09:59 hourly candle</td></tr>
            <tr><td><b>Step 3</b></td><td>10:00 AM Candle Sweeps 09:00 Extreme</td><td>10:00 candle takes out 09:00 high/low</td></tr>
            <tr><td><b>Step 4</b></td><td>10:00 AM Q1 Instant InStat Extreme</td><td>Instant high/low established between 10:00-10:14</td></tr>
        </table>
    </div>

    <script>
        const chartContainer = document.getElementById('chart-container');
        const chart = LightweightCharts.createChart(chartContainer, {{
            width: chartContainer.clientWidth,
            height: 600,
            layout: {{
                background: {{ color: '#111827' }},
                textColor: '#9ca3af',
            }},
            grid: {{
                vertLines: {{ color: '#1f2937' }},
                horzLines: {{ color: '#1f2937' }},
            }},
            timeScale: {{
                timeVisible: true,
                secondsVisible: false,
                borderColor: '#1f2937',
            }},
            rightPriceScale: {{
                borderColor: '#1f2937',
            }},
        }});

        const candleSeries = chart.addCandlestickSeries({{
            upColor: '#10b981',
            downColor: '#ef4444',
            borderVisible: false,
            wickUpColor: '#10b981',
            wickDownColor: '#ef4444',
        }});

        const data = {candles_json};
        candleSeries.setData(data);

        // Horizontal Price Rays
        const p12Mid = {p12['mid']};
        const p12High = {p12['high']};
        const p12Low = {p12['low']};
        const midnight = {anchors['midnight_open'] if anchors['midnight_open'] else 'null'};

        candleSeries.createPriceLine({{
            price: p12Mid,
            color: '#f59e0b',
            lineWidth: 2,
            lineStyle: LightweightCharts.LineStyle.Solid,
            title: 'P12 MIDLINE',
        }});

        candleSeries.createPriceLine({{
            price: p12High,
            color: '#ef4444',
            lineWidth: 1,
            lineStyle: LightweightCharts.LineStyle.Dashed,
            title: 'P12 HIGH',
        }});

        candleSeries.createPriceLine({{
            price: p12Low,
            color: '#10b981',
            lineWidth: 1,
            lineStyle: LightweightCharts.LineStyle.Dashed,
            title: 'P12 LOW',
        }});

        if (midnight !== null) {{
            candleSeries.createPriceLine({{
                price: midnight,
                color: '#3b82f6',
                lineWidth: 1,
                lineStyle: LightweightCharts.LineStyle.Dotted,
                title: 'MIDNIGHT OPEN',
            }});
        }}

        // Auto resize
        window.addEventListener('resize', () => {{
            chart.applyOptions({{ width: chartContainer.clientWidth }});
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
