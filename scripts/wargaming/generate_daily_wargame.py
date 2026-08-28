"""Mickey & Austin Daily Wargaming Generation Engine

Generates the canonical 6-Section Pre-Market Wargaming Briefing & Scenario Cards
from live/fused 1-minute OHLCV data. Enforces zero look-ahead bias, InStat timing
verification, P12 directional vector switches, Candle Science excursion targets,
and Pack Trading 2-tier execution brackets.

Usage:
    python scripts/wargaming/generate_daily_wargame.py --ticker NQ1 --time 06:00
    python scripts/wargaming/generate_daily_wargame.py --ticker NQ1 --date 2026-08-28 --time 08:30
"""
from __future__ import annotations

import sys
import json
import logging
import argparse
from pathlib import Path
from datetime import datetime, date, time, timedelta
from typing import Any, Dict, Optional
import pandas as pd
import numpy as np
import pytz

REPO_ROOT = Path(__file__).parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from scripts.utils.fused_data_loader import load_fused_data
from scripts.libs_py.profiler.live_prediction import compute_live_prediction
from scripts.wargaming.wargame_trajectory_engine import compute_wargame_probabilities_and_trajectories
from scripts.trader.signals.candle_science import get_candle_science_read
from scripts.wargaming.htf_ema_analysis import compute_htf_ema_analysis
from scripts.risk.position_sizer import calculate_position_size, load_ticker_config
from scripts.libs_py.profiler.engine import SessionBoxEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

ET = pytz.timezone("America/New_York")

TICKER_MAP = {
    "NQ": "NQ1", "/NQ": "NQ1", "MNQ": "NQ1", "NQ1": "NQ1",
    "ES": "ES1", "/ES": "ES1", "MES": "ES1", "ES1": "ES1",
    "CL": "CL1", "/CL": "CL1", "MCL": "CL1", "CL1": "CL1",
    "GC": "GC1", "/GC": "GC1", "MGC": "GC1", "GC1": "GC1",
    "YM": "YM1", "/YM": "YM1", "MYM": "YM1", "YM1": "YM1",
    "RTY": "RTY1", "/RTY": "RTY1", "M2K": "RTY1", "RTY1": "RTY1",
}


def time_in_bucket(t_str: str, bucket: str) -> bool:
    """Return True if HH:MM falls within 'HH:MM-HH:MM' bucket."""
    if not t_str or t_str == "N/A" or not bucket:
        return False
    try:
        parts = bucket.split("-")
        t_h, t_m = int(t_str[:2]), int(t_str[3:5])
        s_h, s_m = int(parts[0][:2]), int(parts[0][3:5])
        e_h, e_m = int(parts[1][:2]), int(parts[1][3:5])
        t_mins = t_h * 60 + t_m
        return (s_h * 60 + s_m) <= t_mins <= (e_h * 60 + e_m)
    except Exception:
        return False


def generate_wargame_data(
    ticker: str = "NQ1",
    target_date: Optional[date] = None,
    cutoff_time_str: str = "06:00",
    df_1m: Optional[pd.DataFrame] = None,
    account_equity: float = 50000.0,
    risk_pct: float = 1.0,
) -> Dict[str, Any]:
    """Extract all quantitative wargaming parameters as of cutoff time."""
    if target_date is None:
        target_date = datetime.now(ET).date()

    t_dt = target_date
    prev_date = t_dt - timedelta(days=1)
    
    c_h, c_m = map(int, cutoff_time_str.split(":"))
    cutoff_dt = pd.Timestamp(datetime.combine(t_dt, time(c_h, c_m)), tz="America/New_York")

    # Normalize ticker
    raw_ticker = ticker.upper().strip()
    ticker_clean = TICKER_MAP.get(raw_ticker, raw_ticker)
    ticker = ticker_clean

    # 1. Load Data
    if df_1m is None or df_1m.empty:
        df_1m = load_fused_data(ticker, timeframe="1m", require_historical=False)
        if df_1m is None or df_1m.empty:
            raise ValueError(f"Unable to load 1m data for {ticker}")


    if df_1m.index.tz is None:
        df_1m.index = df_1m.index.tz_localize("US/Eastern")
    else:
        df_1m.index = df_1m.index.tz_convert("US/Eastern")

    df_cutoff = df_1m[df_1m.index <= cutoff_dt].copy()
    if df_cutoff.empty:
        raise ValueError(f"No bars found on or before {cutoff_dt}")

    spot_price = float(df_cutoff.iloc[-1]["close"])

    # 2. P12 Extraction (18:00 prev day to 06:00 target day)
    p12_start = pd.Timestamp(datetime.combine(prev_date, time(18, 0)), tz="America/New_York")
    p12_end = pd.Timestamp(datetime.combine(t_dt, time(6, 0)), tz="America/New_York")
    p12_df = df_1m[(df_1m.index >= p12_start) & (df_1m.index < p12_end)]

    if not p12_df.empty:
        p12_high = float(p12_df["high"].max())
        p12_low = float(p12_df["low"].min())
        p12_mid = (p12_high + p12_low) / 2.0
        p12_hod_ts = p12_df[p12_df["high"] == p12_high].index[0]
        p12_lod_ts = p12_df[p12_df["low"] == p12_low].index[0]
        p12_hod_time = p12_hod_ts.strftime("%H:%M")
        p12_lod_time = p12_lod_ts.strftime("%H:%M")
    else:
        p12_high, p12_low, p12_mid = spot_price, spot_price, spot_price
        p12_hod_time, p12_lod_time = "N/A", "N/A"

    p12_bias = "BULLISH" if spot_price >= p12_mid else "BEARISH"
    p12_diff_pts = spot_price - p12_mid
    p12_diff_bps = (p12_diff_pts / p12_mid) * 10000.0 if p12_mid > 0 else 0.0

    # 3. Anchor Levels (Midnight Open, Globex Open, PDH, PDL, PDC, PDM)
    midnight_ts = pd.Timestamp(datetime.combine(t_dt, time(0, 0)), tz="America/New_York")
    globex_ts = pd.Timestamp(datetime.combine(prev_date, time(18, 0)), tz="America/New_York")

    midnight_bar = df_1m[df_1m.index == midnight_ts]
    globex_bar = df_1m[df_1m.index == globex_ts]

    midnight_open = float(midnight_bar.iloc[0]["open"]) if not midnight_bar.empty else None
    globex_open = float(globex_bar.iloc[0]["open"]) if not globex_bar.empty else None

    prev_rth_start = pd.Timestamp(datetime.combine(prev_date, time(9, 30)), tz="America/New_York")
    prev_rth_end = pd.Timestamp(datetime.combine(prev_date, time(16, 0)), tz="America/New_York")
    prev_rth = df_1m[(df_1m.index >= prev_rth_start) & (df_1m.index <= prev_rth_end)]

    if not prev_rth.empty:
        pdh = float(prev_rth["high"].max())
        pdl = float(prev_rth["low"].min())
        pdc = float(prev_rth.iloc[-1]["close"])
        pdo = float(prev_rth.iloc[0]["open"])
        pdm = (pdh + pdl) / 2.0
    else:
        pdh, pdl, pdc, pdo, pdm = None, None, None, None, None

    # 4. SessionBoxEngine for Asia / London states & broken status
    engine = SessionBoxEngine(df_cutoff, ticker=ticker).process()
    live_sessions = engine.get_live_sessions()

    asia_info = live_sessions.get("Asia", {})
    london_info = live_sessions.get("London", {})

    asia_status = asia_info.get("status", "None")
    asia_broken = asia_info.get("broken", False)
    london_status = london_info.get("status", "None")
    london_broken = london_info.get("broken", False)

    is_broken_broken = bool(asia_broken and london_broken)
    session_alignment = "Broken-Broken / Goalpost Setup" if is_broken_broken else ("Aligned Expansion" if ("True" in asia_status and "True" in london_status) else "Rotational / Chop")

    # 5. Candle Science Read
    cs_read = get_candle_science_read(ticker=ticker, mode="open", target_date=t_dt.isoformat())
    mfe = cs_read.get("mfe", {}) if cs_read else {}
    mae = cs_read.get("mae", {}) if cs_read else {}

    cs_targets = {
        "bull": {
            "p30": float(mfe.get("p30", 0.85)),
            "p50": float(mfe.get("p50", 1.28)),
            "p70": float(mfe.get("p70", 1.88)),
        },
        "bear": {
            "p30": float(mae.get("p30", -0.42)),
            "p50": float(mae.get("p50", -0.79)),
            "p70": float(mae.get("p70", -1.40)),
        }
    }

    # 6. Weekly EMA Excursion
    ema_res = compute_htf_ema_analysis(ticker=ticker, target_date=t_dt.isoformat())

    # 7. Pack Trading Brackets (bps conversion)
    cover_the_queen_bps = 10.0
    runner_bps = 30.0
    stop_ceiling_bps = 12.0

    queen_pts = (cover_the_queen_bps / 10000.0) * spot_price
    runner_pts = (runner_bps / 10000.0) * spot_price
    stop_pts = (stop_ceiling_bps / 10000.0) * spot_price

    long_tp1 = spot_price + queen_pts
    long_tp2 = spot_price + runner_pts
    long_sl = spot_price - stop_pts

    short_tp1 = spot_price - queen_pts
    short_tp2 = spot_price - runner_pts
    short_sl = spot_price + stop_pts

    # 8. Profiler Live Level Hit Rates & Algorithmic Trajectories
    profiler_pred = compute_live_prediction(ticker=ticker, target_date=t_dt, now_et=cutoff_dt)
    traj_data = compute_wargame_probabilities_and_trajectories(
        ticker=ticker,
        target_date=t_dt,
        spot_price=spot_price,
        p12={
            "high": p12_high,
            "low": p12_low,
            "mid": p12_mid,
            "hod_time": p12_hod_time,
            "lod_time": p12_lod_time,
            "bias": p12_bias,
            "diff_pts": p12_diff_pts,
            "diff_bps": p12_diff_bps,
        },
        anchors={
            "midnight_open": midnight_open,
            "globex_open": globex_open,
            "pdh": pdh,
            "pdl": pdl,
            "pdm": pdm,
            "pdc": pdc,
        },
        sessions={
            "asia_status": asia_status,
            "asia_broken": asia_broken,
            "london_status": london_status,
            "london_broken": london_broken,
            "alignment": session_alignment,
        },
        cs=cs_targets,
        profiler_prediction=profiler_pred,
    )

    return {
        "ticker": ticker,
        "date": t_dt.isoformat(),
        "cutoff_time": cutoff_time_str,
        "spot_price": spot_price,
        "p12": {
            "high": p12_high,
            "low": p12_low,
            "mid": p12_mid,
            "hod_time": p12_hod_time,
            "lod_time": p12_lod_time,
            "bias": p12_bias,
            "diff_pts": p12_diff_pts,
            "diff_bps": p12_diff_bps,
        },
        "anchors": {
            "midnight_open": midnight_open,
            "globex_open": globex_open,
            "pdh": pdh,
            "pdl": pdl,
            "pdm": pdm,
            "pdc": pdc,
        },
        "sessions": {
            "asia_status": asia_status,
            "asia_broken": asia_broken,
            "london_status": london_status,
            "london_broken": london_broken,
            "alignment": session_alignment,
        },
        "candle_science": cs_targets,
        "htf_ema": ema_res,
        "pack_trading": {
            "cover_the_queen_bps": cover_the_queen_bps,
            "runner_bps": runner_bps,
            "stop_ceiling_bps": stop_ceiling_bps,
            "queen_pts": queen_pts,
            "runner_pts": runner_pts,
            "stop_pts": stop_pts,
            "long_tp1": long_tp1,
            "long_tp2": long_tp2,
            "long_sl": long_sl,
            "short_tp1": short_tp1,
            "short_tp2": short_tp2,
            "short_sl": short_sl,
        },
        "trajectory_engine": traj_data,
    }


def format_wargame_markdown(data: Dict[str, Any]) -> str:
    """Format extracted wargame parameters into canonical Mickey & Austin Markdown Playbook."""
    p12 = data["p12"]
    anchors = data["anchors"]
    sess = data["sessions"]
    cs = data["candle_science"]
    pack = data["pack_trading"]
    spot = data["spot_price"]
    ticker = data["ticker"]
    dt_str = data["date"]
    cutoff = data["cutoff_time"]

    p12_pos = "ABOVE" if p12["diff_pts"] >= 0 else "BELOW"

    lines = [
        f"# ⚔️ Mickey & Austin Wargaming Playbook: {ticker}",
        f"**Session Date:** {dt_str}  ",
        f"**Analysis Time:** {cutoff} EST (Pre-Market Preparation)  ",
        f"**Current Price:** `{spot:,.2f}` | **P12 Midline:** `{p12['mid']:,.2f}` ({p12_pos} by `{abs(p12['diff_pts']):.2f} pts` / `{abs(p12['diff_bps']):.1f} bps`)  ",
        "",
        "---",
        "",
        "## 🧭 1. OVERNIGHT CONTEXT & SESSION STRUCTURE",
        f"* **Asia Session**: `{sess['asia_status']}` (Broken: `{sess['asia_broken']}`)  ",
        f"* **London Session**: `{sess['london_status']}` (Broken: `{sess['london_broken']}`)  ",
        f"* **Session Alignment**: **{sess['alignment']}**  ",
        f"* **P12 Range (18:00–06:00 EST)**: High `{p12['high']:,.2f}` (@ {p12['hod_time']}) | Low `{p12['low']:,.2f}` (@ {p12['lod_time']}) | Midline `{p12['mid']:,.2f}`  ",
        f"* **P12 Directional Switch**: **{p12['bias']}** (Holding {'above' if p12['bias']=='BULLISH' else 'below'} P12 Midline targets {'P12 High' if p12['bias']=='BULLISH' else 'P12 Low'})  ",
        "",
        "---",
        "",
        "## 📊 2. KEY ANCHOR LEVELS & LIQUIDITY MAP",
        "```",
        f"               [{p12['high']:,.2f}] ── P12 High ({p12['hod_time']} ET)",
        f"               [{anchors['pdh']:,.2f}] ── Previous Day High (PDH)" if anchors['pdh'] else "",
        f"               [{anchors['midnight_open']:,.2f}] ── Midnight Open (00:00 ET)" if anchors['midnight_open'] else "",
        f"               [{p12['mid']:,.2f}] ── P12 MIDLINE (Directional Switch)",
        f"  LIVE PRICE ──► {spot:,.2f} (as of {cutoff} EST)",
        f"               [{p12['low']:,.2f}] ── P12 Low ({p12['lod_time']} ET)",
        f"               [{anchors['pdm']:,.2f}] ── Previous Day Midpoint (PDM)" if anchors['pdm'] else "",
        f"               [{anchors['pdl']:,.2f}] ── Previous Day Low (PDL)" if anchors['pdl'] else "",
        "```",
        "",
        "---",
        "",
        "## ⚔️ 3. ACTIONABLE IF-THEN SCENARIO CARDS",
        "",
        "### 🔴 SCENARIO CARD 1: THE FALSE BRANCH (Reversion / Sweeper) ── PRIMARY BIAS",
        f"* **If** 09:30 RTH Open sweeps toward `P12 Low ({p12['low']:,.2f})` or session extremes and fails to sustain a 10 bps breakout in the 0–5 Box:",
        "* **THEN** execute **Mean Reversion** back toward primary magnets:",
        f"  1. **P12 Midline**: `{p12['mid']:,.2f}` (Primary morning liquidity magnet)",
        f"  2. **Midnight Open**: `{anchors['midnight_open']:,.2f}`" if anchors['midnight_open'] else "  2. **Midnight Open**",
        "* **Statistical Cutoff Rules**:",
        "  - **09:45 AM Cutoff**: P12 Midline / Midnight Open retest expected before 09:45 AM.",
        "  - **10:15 AM Cutoff**: Morning mean-reversion window expires. If price holds across P12 Mid at 10:15, transition to range consolidation.",
        "",
        "### 🟢 SCENARIO CARD 2: THE TRUE BRANCH (Trend Expansion) ── SECONDARY BIAS",
        f"* **Bullish Expansion**: If 09:30 Open breaches and accepts above `P12 Mid ({p12['mid']:,.2f})` by >10 bps in Q1:",
        f"  - Target: `P12 High ({p12['high']:,.2f})` → `PDH ({anchors['pdh']:,.2f})`.",
        "  - HOD Mode Window: 16:00–17:00 PM (Late-day expansion).",
        f"* **Bearish Continuation**: If price rejects `P12 Mid ({p12['mid']:,.2f})` and breaches `P12 Low ({p12['low']:,.2f})` with hourly red line signature:",
        f"  - Target: `PDM ({anchors['pdm']:,.2f})` → `PDL ({anchors['pdl']:,.2f})`.",
        "  - Rule: If no reversal signature forms by 10:15 AM, Trend Continuation locks for the session.",
        "",
        "---",
        "",
        "## 🎯 4. CANDLE SCIENCE EXCURSION TARGET BOXES",
        f"* **Upside Expansion ($C_1$ Bullish MFE)**: P30 `+{cs['bull']['p30']:.2f}%` (`{spot*(1+cs['bull']['p30']/100):,.2f}`) | P50 (Med) `+{cs['bull']['p50']:.2f}%` (`{spot*(1+cs['bull']['p50']/100):,.2f}`) | P70 `+{cs['bull']['p70']:.2f}%` (`{spot*(1+cs['bull']['p70']/100):,.2f}`)",
        f"* **Downside Depth ($C_1$ Bearish MAE)**: P30 `{cs['bear']['p30']:.2f}%` (`{spot*(1+cs['bear']['p30']/100):,.2f}`) | P50 (Med) `{cs['bear']['p50']:.2f}%` (`{spot*(1+cs['bear']['p50']/100):,.2f}`) | P70 `{cs['bear']['p70']:.2f}%` (`{spot*(1+cs['bear']['p70']/100):,.2f}`)",
        "",
        "---",
        "",
        "## 🛡️ 5. PACK TRADING EXECUTION & BASIS POINTS (bps) BRACKETS",
        f"* **Risk Stop Ceiling**: Max **{pack['stop_ceiling_bps']:.1f} bps (~{pack['stop_pts']:.2f} pts)**  ",
        f"* **Target 1 ('Cover The Queen')**: **+{pack['cover_the_queen_bps']:.1f} bps (+{pack['queen_pts']:.2f} pts)**  ",
        "  - *Rule*: Scale out 50% of the position immediately at +10 bps and lock the stop to breakeven (+1 pt). Instantly secures a risk-free trade.",
        f"* **Target 2 ('Runner')**: **+{pack['runner_bps']:.1f} bps (+{pack['runner_pts']:.2f} pts)** trailing for HTF structural targets.",
        f"  - *Long Execution*: TP1 `{pack['long_tp1']:,.2f}` | TP2 `{pack['long_tp2']:,.2f}` | Stop `{pack['long_sl']:,.2f}`",
        f"  - *Short Execution*: TP1 `{pack['short_tp1']:,.2f}` | TP2 `{pack['short_tp2']:,.2f}` | Stop `{pack['short_sl']:,.2f}`",
        "",
        "---",
        "",
        "## 🚦 6. MICKEY & AUSTIN 4-STEP REVERSAL COUNTER (Intraday Checklist)",
        "Track price action step-by-step between 09:30 and 10:30 AM:",
        "1. **[ ] Step 1**: Does price cross back over the **09:30 AM Open print**?",
        "2. **[ ] Step 2**: Does price trade through the **09:00 AM Hour 50% Midpoint**?",
        "3. **[ ] Step 3**: Does the **10:00 AM Candle** sweep the 09:00 AM extreme?",
        "4. **[ ] Step 4**: Does the **10:00 AM Q1 (10:00–10:14)** establish an instant statistical extreme?",
        "   - **4/4 Steps Completed**: Major Reversal confirmed $\\rightarrow$ Execute Scenario 1 (False Branch).",
        "   - **0–1 Steps Completed**: Trend Continuation confirmed $\\rightarrow$ Ride Scenario 2 (True Branch).",
    ]

    return "\n".join([l for l in lines if l is not None])




def main():
    parser = argparse.ArgumentParser(description="Mickey & Austin Wargaming Playbook Generator")
    parser.add_argument("--ticker", default="NQ1", help="Ticker symbol (default: NQ1)")
    parser.add_argument("--date", default=None, help="Target date YYYY-MM-DD (default: today)")
    parser.add_argument("--time", default="06:00", help="Cutoff time HH:MM (default: 06:00)")
    parser.add_argument("--json", action="store_true", help="Output raw JSON instead of Markdown")
    parser.add_argument("--html", action="store_true", help="Generate interactive Lightweight Charts HTML report")
    parser.add_argument("--no-db", action="store_true", help="Do not save to system_wargames.sqlite")
    args = parser.parse_args()

    t_date = datetime.strptime(args.date, "%Y-%m-%d").date() if args.date else datetime.now(ET).date()
    data = generate_wargame_data(ticker=args.ticker, target_date=t_date, cutoff_time_str=args.time)
    md_output = format_wargame_markdown(data)

    if not args.no_db:
        try:
            from scripts.wargaming.wargame_db import save_system_wargame
            pred_id = save_system_wargame(data, markdown_report=md_output)
            log.info(f"Auto-saved prediction to system_wargames.sqlite: {pred_id}")
        except Exception as e:
            log.warning(f"Failed to auto-save to database: {e}")

    if args.html:
        try:
            from scripts.wargaming.render_wargame_chart import render_and_save_chart
            html_path = render_and_save_chart(ticker=args.ticker, target_date=t_date, cutoff_time=args.time)
            log.info(f"Generated HTML Chart: {html_path}")
        except Exception as e:
            log.warning(f"Failed to render HTML chart: {e}")

    if args.json:
        print(json.dumps(data, indent=2, default=str))
    else:
        print(md_output)


if __name__ == "__main__":
    main()

