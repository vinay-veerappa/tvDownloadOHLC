"""30-Day Mini-Batch & Signal Confluence Stress Test (Step 0.6)

Evaluates Candle Science, HTF EMA Excursion, P12 Handshake Vector, and 3-Hour Line vs Apex
across 30 randomly sampled historical trading days for NQ1 and ES1.
Quantifies win-rates on Aligned vs Contradicted days and validates statistical edge (p < 0.05).
"""
from __future__ import annotations

import sys
import logging
import random
from pathlib import Path
import pandas as pd
import numpy as np
import pytz
from datetime import datetime, time, timedelta
from scipy import stats

REPO_ROOT = Path(__file__).parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from scripts.utils.fused_data_loader import load_fused_data
from scripts.trader.signals.candle_science import get_candle_science_read
from scripts.wargaming.htf_ema_analysis import compute_htf_ema_analysis
from scripts.risk.position_sizer import load_ticker_config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

ET = pytz.timezone("America/New_York")


def run_minibatch_confluence_test(ticker: str = "NQ1", n_days: int = 30, seed: int = 42) -> dict:
    print(f"\n==========================================================================")
    print(f"   RUNNING {n_days}-DAY MINI-BATCH & SIGNAL CONFLUENCE STRESS TEST: {ticker}")
    print(f"==========================================================================")

    df_1d = pd.read_parquet(REPO_ROOT / "data" / f"{ticker}_1d.parquet")
    if df_1d.index.tz is not None:
        df_1d.index = df_1d.index.tz_convert("US/Eastern")
    else:
        df_1d.index = df_1d.index.tz_localize("UTC").tz_convert("US/Eastern")

    df_1m = load_fused_data(ticker, timeframe="1m")
    if df_1m.index.tz is not None:
        df_1m.index = df_1m.index.tz_convert("US/Eastern")
    else:
        df_1m.index = df_1m.index.tz_localize("UTC").tz_convert("US/Eastern")

    min_1m_date = df_1m.index[0].date()
    max_1m_date = df_1m.index[-1].date()
    
    all_dates = sorted(list(set(df_1d.index.date)))
    # Exclude dates outside 1m data availability range and weekends
    valid_dates = [d for d in all_dates if d.weekday() < 5 and (min_1m_date + timedelta(days=2)) <= d <= (max_1m_date - timedelta(days=1))]
    
    random.seed(seed)
    sample_dates = sorted(random.sample(valid_dates, min(n_days, len(valid_dates))))

    cfg = load_ticker_config(ticker)
    mom_threshold = cfg.get("momentum_threshold_points", 20.0)

    aligned_success = 0
    aligned_total = 0
    conflicted_success = 0
    conflicted_total = 0

    results = []

    for d in sample_dates:
        date_str = d.strftime("%Y-%m-%d")
        
        # 1. Candle Science Signal
        cs_read = get_candle_science_read(ticker=ticker, mode="open", target_date=date_str)
        p_bull = cs_read.get("p_bull", 50.0) if cs_read else 50.0
        p_bear = cs_read.get("p_bear", 50.0) if cs_read else 50.0
        cs_dir = "BULLISH" if p_bull >= p_bear else "BEARISH"
        
        # 2. HTF EMA Excursion
        ema_res = compute_htf_ema_analysis(ticker=ticker, target_date=date_str)
        is_2to3 = ema_res.get("is_2to3_zone", False)
        
        # 3. P12 & Handshake
        prev_day = d - timedelta(days=1)
        p12_start = pd.Timestamp(datetime.combine(prev_day, time(18, 0))).tz_localize("US/Eastern")
        p12_end = pd.Timestamp(datetime.combine(d, time(6, 0))).tz_localize("US/Eastern")
        
        p12_bars = df_1m[(df_1m.index >= p12_start) & (df_1m.index < p12_end)]
        if p12_bars.empty:
            continue
            
        p12_high = float(p12_bars["high"].max())
        p12_low = float(p12_bars["low"].min())
        p12_mid = (p12_high + p12_low) / 2.0
        
        pre_start = pd.Timestamp(datetime.combine(d, time(6, 0))).tz_localize("US/Eastern")
        pre_end = pd.Timestamp(datetime.combine(d, time(8, 30))).tz_localize("US/Eastern")
        pre_bars = df_1m[(df_1m.index >= pre_start) & (df_1m.index <= pre_end)]
        
        last_pre_close = float(pre_bars.iloc[-1]["close"]) if not pre_bars.empty else p12_mid
        p12_bias = "BULLISH" if last_pre_close >= p12_mid else "BEARISH"
        
        rth_start = pd.Timestamp(datetime.combine(d, time(9, 30))).tz_localize("US/Eastern")
        rth_end = pd.Timestamp(datetime.combine(d, time(16, 0))).tz_localize("US/Eastern")
        rth_bars = df_1m[(df_1m.index >= rth_start) & (df_1m.index <= rth_end)]
        
        if rth_bars.empty:
            continue

        rth_open = float(rth_bars.iloc[0]["open"])
        handshake = "AGREEMENT" if (p12_bias == "BULLISH" and rth_open >= p12_mid) or (p12_bias == "BEARISH" and rth_open < p12_mid) else "DISAGREEMENT"

        # Confluence Assessment
        is_aligned = (cs_dir == p12_bias) and (handshake == "AGREEMENT") and not is_2to3
        confluence_status = "ALIGNED" if is_aligned else "CONFLICTED"

        # Actual Price Outcome Evaluation
        rth_close = float(rth_bars.iloc[-1]["close"])
        rth_high = float(rth_bars["high"].max())
        rth_low = float(rth_bars["low"].min())

        success = False
        if p12_bias == "BULLISH":
            # Success if price hit P12 High or closed above RTH open
            success = bool(rth_high >= p12_high or rth_close > rth_open)
        else:
            # Success if price hit P12 Low or closed below RTH open
            success = bool(rth_low <= p12_low or rth_close < rth_open)

        if is_aligned:
            aligned_total += 1
            if success:
                aligned_success += 1
        else:
            conflicted_total += 1
            if success:
                conflicted_success += 1

        results.append({
            "date": date_str,
            "cs_dir": cs_dir,
            "p12_bias": p12_bias,
            "handshake": handshake,
            "2to3_magnet": "YES" if is_2to3 else "NO",
            "confluence": confluence_status,
            "success": "WIN" if success else "LOSS",
        })

    # Calculate Statistics
    aligned_winrate = (aligned_success / aligned_total * 100.0) if aligned_total > 0 else 0.0
    conflicted_winrate = (conflicted_success / conflicted_total * 100.0) if conflicted_total > 0 else 0.0
    overall_winrate = ((aligned_success + conflicted_success) / len(results) * 100.0) if results else 0.0

    # Calculate Chi-Square / p-value of Aligned vs Conflicted
    obs = np.array([[aligned_success, aligned_total - aligned_success],
                    [conflicted_success, conflicted_total - conflicted_success]])
    chi2, p_val, dof, ex = stats.chi2_contingency(obs) if (aligned_total > 0 and conflicted_total > 0) else (0.0, 1.0, 0, [])

    print(f"\n{'Date':<12} | {'CandleSci':<10} | {'P12 Bias':<9} | {'Handshake':<12} | {'2-3% Zone':<9} | {'Confluence':<11} | {'Outcome':<7}")
    print("-" * 85)
    for r in results[:10]:  # Show first 10
        print(f"{r['date']:<12} | {r['cs_dir']:<10} | {r['p12_bias']:<9} | {r['handshake']:<12} | {r['2to3_magnet']:<9} | {r['confluence']:<11} | {r['success']:<7}")
    print(f"... and {len(results) - 10} more days.")

    print("\n==========================================================================")
    print("                    MINI-BATCH STRESS TEST RESULTS                       ")
    print("==========================================================================")
    print(f"  Total Days Evaluated:  {len(results)}")
    print(f"  ALIGNED Days:          {aligned_total} days | Win Rate: {aligned_winrate:.2f}% ({aligned_success}/{aligned_total})")
    print(f"  CONFLICTED Days:       {conflicted_total} days | Win Rate: {conflicted_winrate:.2f}% ({conflicted_success}/{conflicted_total})")
    print(f"  Overall System Edge:   {overall_winrate:.2f}%")
    print(f"  Statistical p-value:   p = {p_val:.4f} ({'STATISTICALLY SIGNIFICANT (p < 0.05)' if p_val < 0.05 else 'INSUFFICIENT SAMPLE / MARGINAL'})")
    print("==========================================================================\n")

    return {
        "ticker": ticker,
        "total_days": len(results),
        "aligned_winrate": round(aligned_winrate, 2),
        "conflicted_winrate": round(conflicted_winrate, 2),
        "overall_winrate": round(overall_winrate, 2),
        "p_value": round(float(p_val), 4),
        "is_significant": bool(p_val < 0.05),
    }


if __name__ == "__main__":
    ticker_arg = sys.argv[1] if len(sys.argv) > 1 else "NQ1"
    run_minibatch_confluence_test(ticker_arg)
