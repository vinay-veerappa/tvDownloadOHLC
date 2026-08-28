"""3-Way Daily Drift Reconciler & LoRA Learning Flywheel for Pack Wargaming

Executes post-market at 16:15 EST to reconcile the 3-bank triad:
1. System AI Prediction (`system_wargames.sqlite`)
2. Mickey Expert Ground Truth (`mickey_ground_truth.sqlite`)
3. Realized Market Tape Actuals (`market_actuals.sqlite`)

Derives alignment scores, market expectancy, delta gaps, and auto-generates
DPO preference pairs (`data/wargaming/training/dpo_preference_pairs.jsonl`).

Usage:
    python scripts/wargaming/reconcile_wargame.py --ticker NQ1
    python scripts/wargaming/reconcile_wargame.py --date 2026-08-28 --ticker NQ1
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

from scripts.wargaming.wargame_db import query_session_triad, save_market_actuals, get_connection, ACTUALS_DB_PATH
from scripts.utils.fused_data_loader import load_fused_data

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

TRAINING_DIR = REPO_ROOT / "data" / "wargaming" / "training"
TRAINING_DIR.mkdir(parents=True, exist_ok=True)
DPO_FILE = TRAINING_DIR / "dpo_preference_pairs.jsonl"

ET = pytz.timezone("America/New_York")


def compute_market_actuals(ticker: str, target_date: date, df_1m: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
    """Derive 100% mechanical RTH tape metrics from 1m data."""
    if df_1m is None or df_1m.empty:
        df_1m = load_fused_data(ticker, timeframe="1m", require_historical=False)
        if df_1m.index.tz is None:
            df_1m.index = df_1m.index.tz_localize("US/Eastern")
        else:
            df_1m.index = df_1m.index.tz_convert("US/Eastern")

    rth_start = pd.Timestamp(datetime.combine(target_date, time(9, 30)), tz="America/New_York")
    rth_end = pd.Timestamp(datetime.combine(target_date, time(16, 0)), tz="America/New_York")
    rth_df = df_1m[(df_1m.index >= rth_start) & (df_1m.index <= rth_end)].copy()

    if rth_df.empty:
        log.warning(f"No RTH data for {target_date}")
        return {"session_date": target_date.isoformat(), "ticker": ticker, "rth_open": 0.0, "winning_scenario": "UNKNOWN"}

    rth_open = float(rth_df.iloc[0]["open"])
    rth_high = float(rth_df["high"].max())
    rth_low = float(rth_df["low"].min())
    rth_close = float(rth_df.iloc[-1]["close"])

    hod_ts = rth_df[rth_df["high"] == rth_high].index[0]
    lod_ts = rth_df[rth_df["low"] == rth_low].index[0]
    hod_time = hod_ts.strftime("%H:%M")
    lod_time = lod_ts.strftime("%H:%M")

    # 4-Step Reversal Counter Evaluation
    # Step 1: Does price cross back over 09:30 open after 09:35?
    post_935 = rth_df[rth_df.index >= pd.Timestamp(datetime.combine(target_date, time(9, 35)), tz="America/New_York")]
    step1_met = bool(((post_935["low"] <= rth_open) & (post_935["high"] >= rth_open)).any()) if not post_935.empty else False

    # Step 2: 09:00 Midpoint check
    h09_start = pd.Timestamp(datetime.combine(target_date, time(9, 0)), tz="America/New_York")
    h09_end = pd.Timestamp(datetime.combine(target_date, time(10, 0)), tz="America/New_York")
    h09_df = df_1m[(df_1m.index >= h09_start) & (df_1m.index < h09_end)]
    if not h09_df.empty:
        h09_mid = (float(h09_df["high"].max()) + float(h09_df["low"].min())) / 2.0
        post_1000 = rth_df[rth_df.index >= pd.Timestamp(datetime.combine(target_date, time(10, 0)), tz="America/New_York")]
        step2_met = bool(((post_1000["low"] <= h09_mid) & (post_1000["high"] >= h09_mid)).any()) if not post_1000.empty else False
    else:
        step2_met = False


    # Step 3: 10:00 AM Candle sweeps 09:00 extreme
    h10_start = pd.Timestamp(datetime.combine(target_date, time(10, 0)), tz="America/New_York")
    h10_end = pd.Timestamp(datetime.combine(target_date, time(11, 0)), tz="America/New_York")
    h10_df = df_1m[(df_1m.index >= h10_start) & (df_1m.index < h10_end)]
    if not h10_df.empty and not h09_df.empty:
        h10_high = float(h10_df["high"].max())
        h10_low = float(h10_df["low"].min())
        h09_high = float(h09_df["high"].max())
        h09_low = float(h09_df["low"].min())
        step3_met = bool(h10_high > h09_high or h10_low < h09_low)
    else:
        step3_met = bool(hod_ts.hour >= 10 and lod_ts.hour >= 10)

    # Step 4: 10:00 AM Q1 (10:00-10:14) InStat Instant Extreme
    q1_start = pd.Timestamp(datetime.combine(target_date, time(10, 0)), tz="America/New_York")
    q1_end = pd.Timestamp(datetime.combine(target_date, time(10, 15)), tz="America/New_York")
    q1_df = df_1m[(df_1m.index >= q1_start) & (df_1m.index < q1_end)]
    if not q1_df.empty:
        q1_high = float(q1_df["high"].max())
        q1_low = float(q1_df["low"].min())
        step4_met = bool((q1_high == rth_high) or (q1_low == rth_low))
    else:
        step4_met = bool((hod_ts.hour == 10 and hod_ts.minute < 15) or (lod_ts.hour == 10 and lod_ts.minute < 15))

    four_step_score = sum([step1_met, step2_met, step3_met, step4_met])

    # Austin +40 bps Continuation Check (06:00-09:00 box expansion)
    box_start = pd.Timestamp(datetime.combine(target_date, time(6, 0)), tz="America/New_York")
    box_end = pd.Timestamp(datetime.combine(target_date, time(9, 0)), tz="America/New_York")
    box_df = df_1m[(df_1m.index >= box_start) & (df_1m.index < box_end)]
    continuation_40bps = False
    if not box_df.empty and rth_open > 0:
        box_high = float(box_df["high"].max())
        box_low = float(box_df["low"].min())
        bps_up = ((rth_high - box_high) / rth_open) * 10000.0
        bps_down = ((box_low - rth_low) / rth_open) * 10000.0
        if (bps_up >= 40.0 or bps_down >= 40.0) and four_step_score < 3:
            continuation_40bps = True

    if continuation_40bps:
        winning_scenario = "TRUE_CONTINUATION"
    else:
        winning_scenario = "FALSE_REVERSION" if four_step_score >= 3 else "TRUE_CONTINUATION"



    # EOD Day Type classification
    net_chg_pts = rth_close - rth_open
    net_chg_pct = (net_chg_pts / rth_open) * 100.0 if rth_open > 0 else 0.0
    rth_range_pct = ((rth_high - rth_low) / rth_open) * 100.0 if rth_open > 0 else 0.0

    if abs(net_chg_pct) < 0.25 and rth_range_pct < 0.80:
        day_type = "DNP"
    elif abs(net_chg_pct) < 0.35 and rth_range_pct >= 0.80:
        day_type = "DWP"
    elif net_chg_pct >= 0.50:
        day_type = "R1"
    else:
        day_type = "R2"

    actuals_data = {
        "session_id": f"{target_date.isoformat()}_{ticker}",
        "session_date": target_date.isoformat(),
        "ticker": ticker,
        "rth_open": rth_open,
        "rth_high": rth_high,
        "rth_low": rth_low,
        "rth_close": rth_close,
        "actual_hod_time": hod_time,
        "actual_lod_time": lod_time,
        "step1_met": step1_met,
        "step2_met": step2_met,
        "step3_met": step3_met,
        "step4_met": step4_met,
        "four_step_score": four_step_score,
        "three_hour_block_type": "APEX_REVERSAL" if winning_scenario == "FALSE_REVERSION" else "3_HOUR_LINE",
        "realized_day_type": day_type,
        "winning_scenario": winning_scenario,
    }

    save_market_actuals(actuals_data)
    return actuals_data


def reconcile_session(session_date_str: str, ticker: str = "NQ1") -> Dict[str, Any]:
    """Perform 3-way reconciliation across AI Prediction, Mickey Truth, and Actual Tape."""
    target_date = datetime.strptime(session_date_str, "%Y-%m-%d").date()
    
    # 1. Ensure actuals are computed
    actuals = compute_market_actuals(ticker=ticker, target_date=target_date)

    # 2. Retrieve triad
    triad = query_session_triad(session_date_str, ticker=ticker)
    pred = triad.get("system_prediction")
    mickey = triad.get("mickey_truth")

    # 3. Reconciliation Scores
    ai_predicted_scenario = "FALSE_REVERSION"
    if pred:
        p12_bias = pred.get("p12_bias", "NEUTRAL")

    winning = actuals.get("winning_scenario", "UNKNOWN")
    mickey_scenario = mickey.get("primary_scenario") if mickey else None

    ai_vs_tape_match = bool(ai_predicted_scenario == winning)
    ai_vs_mickey_match = bool(ai_predicted_scenario == mickey_scenario) if mickey_scenario else None

    # Delta Gap
    delta_gap = None
    if mickey_scenario and ai_predicted_scenario != mickey_scenario:
        delta_gap = f"AI favored {ai_predicted_scenario} while Mickey wargamed {mickey_scenario}."

    # Write DPO training pair if delta gap or rich reasoning exists
    if mickey and mickey.get("raw_transcript"):
        dpo_pair = {
            "prompt": f"Pre-market wargaming analysis for {ticker} on {session_date_str} with overnight structure.",
            "chosen": mickey.get("raw_transcript")[:2000],
            "rejected": pred.get("markdown_report", "")[:2000] if pred else "Generic prediction.",
            "metadata": {
                "date": session_date_str,
                "ticker": ticker,
                "ai_scenario": ai_predicted_scenario,
                "mickey_scenario": mickey_scenario,
                "realized_winning": winning,
            }
        }
        with open(DPO_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(dpo_pair) + "\n")
        log.info(f"Appended DPO training pair to {DPO_FILE.name}")



    reconciliation_report = {
        "date": session_date_str,
        "ticker": ticker,
        "realized_actuals": {
            "open": actuals.get("rth_open"),
            "high": actuals.get("rth_high"),
            "low": actuals.get("rth_low"),
            "close": actuals.get("rth_close"),
            "hod_time": actuals.get("actual_hod_time"),
            "lod_time": actuals.get("actual_lod_time"),
            "winning_scenario": winning,
            "realized_day_type": actuals.get("realized_day_type"),
            "four_step_score": actuals.get("four_step_score"),
        },
        "scores": {
            "ai_vs_tape_match": ai_vs_tape_match,
            "ai_vs_mickey_match": ai_vs_mickey_match,
        },
        "delta_gap": delta_gap,
    }

    return reconciliation_report


def main():
    parser = argparse.ArgumentParser(description="3-Way Daily Wargame Reconciler")
    parser.add_argument("--ticker", default="NQ1", help="Ticker symbol")
    parser.add_argument("--date", default=None, help="Target date YYYY-MM-DD (default: today)")
    args = parser.parse_args()

    s_date = args.date or datetime.now(ET).strftime("%Y-%m-%d")
    report = reconcile_session(session_date_str=s_date, ticker=args.ticker)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
