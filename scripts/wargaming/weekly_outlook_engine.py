"""Weekly Outlook & Candle Structure Analysis Engine

Mickey & Austin Weekly Framework:
1. Day-of-Week Cycle (Monday/Tuesday Low/High Formation vs. Thursday/Friday Expansion).
2. Weekly Candle State (W-Open, W-High, W-Low, W-Mid, PWH, PWL, PWM, PWC).
3. Multi-Expiry Expected Moves (0DTE to Next Friday).
4. Current Cycle Status & Tactical Weekly Road Map.
"""
from __future__ import annotations

import sys
import json
import argparse
import logging
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import Dict, Any, Optional, List
import pandas as pd
import numpy as np
import pytz

REPO_ROOT = Path(__file__).parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

ET = pytz.timezone("America/New_York")


def compute_weekly_outlook(ticker: str = "NQ1", target_date: Optional[str] = None) -> Dict[str, Any]:
    """Computes Weekly Candle progression, Day-of-Week cycle analysis, and Expected Moves."""
    daily_file = REPO_ROOT / "data" / f"{ticker}_1d.parquet"
    if not daily_file.exists():
        daily_file = REPO_ROOT / "data" / "historical" / f"{ticker}_1d.parquet"

    if not daily_file.exists():
        return {"error": f"Daily parquet not found for {ticker}"}

    df_1d = pd.read_parquet(daily_file)
    if df_1d.index.tz is not None:
        df_1d.index = df_1d.index.tz_convert("US/Eastern")
    else:
        df_1d.index = df_1d.index.tz_localize("UTC").tz_convert("US/Eastern")

    # Map session dates
    df_1d["session_date"] = [
        (t + timedelta(days=1)).date() if t.hour >= 17 else t.date()
        for t in df_1d.index
    ]

    if target_date:
        t_dt = pd.to_datetime(target_date).date()
        df_1d = df_1d[df_1d["session_date"] <= t_dt]

    if len(df_1d) < 20:
        return {"error": f"Insufficient historical daily data for {ticker}"}

    spot = float(df_1d["close"].iloc[-1])
    eval_date = t_dt if target_date else df_1d["session_date"].iloc[-1]

    # Find the Monday of the current trading week
    day_of_week_idx = eval_date.weekday()
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    current_day_name = day_names[day_of_week_idx]

    monday_date = eval_date - timedelta(days=day_of_week_idx)
    prior_friday_date = monday_date - timedelta(days=3)
    prior_monday_date = monday_date - timedelta(days=7)

    # Current week bars so far
    current_wk_df = df_1d[df_1d["session_date"] >= monday_date]
    prior_wk_df = df_1d[(df_1d["session_date"] >= prior_monday_date) & (df_1d["session_date"] <= prior_friday_date)]

    # Current Week Metrics
    if not current_wk_df.empty:
        w_open = float(current_wk_df["open"].iloc[0])
        w_high = float(current_wk_df["high"].max())
        w_low = float(current_wk_df["low"].min())
        w_mid = (w_high + w_low) / 2.0
        w_change_pts = round(spot - w_open, 2)
        w_change_pct = round((w_change_pts / w_open) * 100.0, 2)

        high_row = current_wk_df.loc[current_wk_df["high"] == w_high].iloc[0]
        low_row = current_wk_df.loc[current_wk_df["low"] == w_low].iloc[0]
        high_day_name = day_names[high_row["session_date"].weekday()]
        low_day_name = day_names[low_row["session_date"].weekday()]
    else:
        w_open, w_high, w_low, w_mid = spot, spot, spot, spot
        w_change_pts, w_change_pct = 0.0, 0.0
        high_day_name, low_day_name = current_day_name, current_day_name

    # Prior Week Metrics
    if not prior_wk_df.empty:
        pwh = float(prior_wk_df["high"].max())
        pwl = float(prior_wk_df["low"].min())
        pwc = float(prior_wk_df["close"].iloc[-1])
        pwm = (pwh + pwl) / 2.0
    else:
        pwh, pwl, pwc, pwm = w_high * 1.01, w_low * 0.99, spot, spot

    # Day-of-Week Cycle Analysis
    mon_tue_extreme = "NONE"
    if low_day_name in ["Monday", "Tuesday"] and high_day_name not in ["Monday", "Tuesday"]:
        mon_tue_extreme = f"Weekly Low printed on {low_day_name} ({w_low:,.2f})"
        cycle_phase = "Thursday/Friday Bullish Expansion Phase"
        cycle_edge = "Favors upside continuation to test/expand Weekly High into Friday close."
    elif high_day_name in ["Monday", "Tuesday"] and low_day_name not in ["Monday", "Tuesday"]:
        mon_tue_extreme = f"Weekly High printed on {high_day_name} ({w_high:,.2f})"
        cycle_phase = "Thursday/Friday Bearish Expansion Phase"
        cycle_edge = "Favors downside continuation to test/expand Weekly Low into Friday close."
    elif low_day_name in ["Monday", "Tuesday"] and high_day_name in ["Monday", "Tuesday"]:
        mon_tue_extreme = f"Both extremes printed on Mon/Tue (Low: {w_low:,.2f}, High: {w_high:,.2f})"
        cycle_phase = "Consolidation / Mid-Week Inside Week"
        cycle_edge = "Market is coiled inside Mon/Tue goalposts; watch for breakout expansion."
    else:
        cycle_phase = "Forming Early Week Extremes"
        cycle_edge = "Monday/Tuesday baseline formation in progress."

    # Multi-Expiry Expected Moves (EM) Calculation (Rule: up to next Friday)
    daily_vol = (0.18 / np.sqrt(252)) * spot
    em_table = []
    
    days_to_next_friday = (4 - day_of_week_idx) + 7
    for offset in range(0, days_to_next_friday + 1):
        target_exp = eval_date + timedelta(days=offset)
        if target_exp.weekday() in [5, 6]:
            continue
        dte = offset
        em_pts = round(daily_vol * np.sqrt(max(0.5, dte)), 2)
        em_pct = round((em_pts / spot) * 100.0, 2)
        upper_em = round(spot + em_pts, 2)
        lower_em = round(spot - em_pts, 2)

        dte_label = "0DTE (Today)" if dte == 0 else f"{dte}DTE"
        if offset == days_to_next_friday:
            dte_label += " (Next Friday)"
        elif offset == (4 - day_of_week_idx):
            dte_label += " (This Friday)"

        em_table.append({
            "expiry_date": target_exp.strftime("%Y-%m-%d"),
            "dte_label": dte_label,
            "em_pts": em_pts,
            "em_pct": em_pct,
            "upper_em": upper_em,
            "lower_em": lower_em
        })

    return {
        "ticker": ticker,
        "eval_date": eval_date.strftime("%Y-%m-%d"),
        "day_of_week": current_day_name,
        "spot_price": spot,
        "current_week": {
            "week_open": round(w_open, 2),
            "week_high": round(w_high, 2),
            "week_high_day": high_day_name,
            "week_low": round(w_low, 2),
            "week_low_day": low_day_name,
            "week_mid": round(w_mid, 2),
            "week_change_pts": w_change_pts,
            "week_change_pct": w_change_pct,
            "candle_bias": "BULLISH" if w_change_pts >= 0 else "BEARISH",
        },
        "prior_week": {
            "pwh": round(pwh, 2),
            "pwl": round(pwl, 2),
            "pwm": round(pwm, 2),
            "pwc": round(pwc, 2),
        },
        "cycle_analysis": {
            "mon_tue_extreme": mon_tue_extreme,
            "cycle_phase": cycle_phase,
            "cycle_edge": cycle_edge,
        },
        "expected_moves": em_table
    }


def format_weekly_outlook_markdown(data: Dict[str, Any]) -> str:
    """Format Weekly Outlook as GitHub flavored markdown report."""
    w = data["current_week"]
    pw = data["prior_week"]
    c = data["cycle_analysis"]

    em_lines = []
    for em in data["expected_moves"]:
        em_lines.append(f"| **{em['expiry_date']}** | `{em['dte_label']}` | `±{em['em_pts']:,.2f} pts` (`±{em['em_pct']:.2f}%`) | `{em['lower_em']:,.2f}` &ndash; `{em['upper_em']:,.2f}` |")
    em_rows = chr(10).join(em_lines)

    md = f"""# 🗓️ Weekly Outlook & Candle Structure Report: {data['ticker']} ({data['eval_date']})
* **Current Day**: `{data['day_of_week']}` | **Current Spot**: `{data['spot_price']:,.2f}` | **Weekly Bias**: `{w['candle_bias']}` (`{w['week_change_pct']:+.2f}%`)

---

### 🕯️ 1. Current Weekly Candle Progress
* **Weekly Open**: `{w['week_open']:,.2f}`
* **Weekly High**: `{w['week_high']:,.2f}` (Locked on **{w['week_high_day']}**)
* **Weekly Low**: `{w['week_low']:,.2f}` (Locked on **{w['week_low_day']}**)
* **Weekly Midpoint (50%)**: `{w['week_mid']:,.2f}`
* **Prior Week Reference Levels**:
  * **Prior Week High (PWH)**: `{pw['pwh']:,.2f}`
  * **Prior Week Mid (PWM)**: `{pw['pwm']:,.2f}`
  * **Prior Week Low (PWL)**: `{pw['pwl']:,.2f}`
  * **Prior Week Close (PWC)**: `{pw['pwc']:,.2f}`

---

### 🔄 2. Day-of-Week Macro Cycle Analysis
* **Mon/Tue Structural Extreme**: `{c['mon_tue_extreme']}`
* **Active Cycle Phase**: **{c['cycle_phase']}**
* **Mickey Tactical Edge**: {c['cycle_edge']}

---

### 🎯 3. Multi-Expiry Expected Move (EM) Matrix (0DTE &rarr; Next Friday)
| Expiry Date | DTE Horizon | Expected Move (±) | Implied Target Range |
| :--- | :--- | :--- | :--- |
{em_rows}
"""
    return md


def main():
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="Weekly Outlook & Candle Structure Engine")
    parser.add_argument("--ticker", default="NQ1", help="Ticker symbol (default: NQ1)")
    parser.add_argument("--date", default=None, help="Target date YYYY-MM-DD (default: today)")
    parser.add_argument("--json", action="store_true", help="Output raw JSON format")
    args = parser.parse_args()

    data = compute_weekly_outlook(ticker=args.ticker, target_date=args.date)
    if args.json:
        print(json.dumps(data, indent=2))
    else:
        print(format_weekly_outlook_markdown(data))


if __name__ == "__main__":
    main()
