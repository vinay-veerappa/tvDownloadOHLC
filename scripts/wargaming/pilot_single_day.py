"""Single-Day Pilot Wargame & EOD Reengineering Engine (Step 0.7)

Combines Pre-Market Wargaming (08:30 AM EST live features only — NO LOOK-AHEAD)
and EOD Reengineering Post-Mortem (16:00 PM EST intraday replay).
Includes position sizing from risk engine, signal confluence matrix,
5-stage Line vs Apex counter, and P12 Handshake Vector. Supports any futures ticker.
"""
from __future__ import annotations

import sys
import logging
import json
from pathlib import Path
from typing import Any
import pandas as pd
import numpy as np
import pytz
from datetime import datetime, time, timedelta

REPO_ROOT = Path(__file__).parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from scripts.utils.fused_data_loader import load_fused_data
from scripts.trader.signals.candle_science import get_candle_science_read
from scripts.wargaming.htf_ema_analysis import compute_htf_ema_analysis
from scripts.risk.position_sizer import calculate_position_size, load_ticker_config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

ET = pytz.timezone("America/New_York")


def et_timestamp(d: datetime.date, h: int, m: int = 0) -> pd.Timestamp:
    """Create a timezone-safe US/Eastern timestamp without DST crash risks."""
    ts = pd.Timestamp(datetime.combine(d, time(h, m)))
    return ts.tz_localize(ET, ambiguous="NaT", nonexistent="NaT")


def run_pilot_wargame_and_reengineering(
    ticker: str = "NQ1",
    target_date: str = "2026-08-03",
    account_equity: float = 4500.0,
    risk_pct: float = 5.0,
) -> dict[str, Any]:
    """Executes a full single-day pilot wargame and EOD reengineering post-mortem.
    
    Args:
        ticker: Futures ticker symbol (NQ1, ES1, CL1, GC1)
        target_date: Trading session date string (YYYY-MM-DD)
        account_equity: Trading account balance in USD
        risk_pct: Account risk percentage per trade
    """
    t_dt = pd.to_datetime(target_date).date()
    cfg = load_ticker_config(ticker)
    mom_threshold = float(cfg.get("momentum_threshold_points", 20.0))

    print(f"\n==========================================================================")
    print(f"   PILOT WARGAME & EOD REENGINEERING: {ticker} | DATE: {target_date}")
    print(f"==========================================================================")

    # Load Intraday Parquet Data
    try:
        df_1m = load_fused_data(ticker, timeframe="1m")
        if df_1m is None or df_1m.empty:
            log.error("Intraday 1m data is empty for %s", ticker)
            return {"error": f"Intraday 1m data missing for {ticker}"}
        if df_1m.index.tz is not None:
            df_1m.index = df_1m.index.tz_convert("US/Eastern")
        else:
            df_1m.index = df_1m.index.tz_localize("UTC").tz_convert("US/Eastern")
    except Exception as e:
        log.error("Failed to load 1m parquet data for %s: %s", ticker, e)
        return {"error": str(e)}

    # -------------------------------------------------------------------------
    # PART 1: PRE-MARKET WARGAME (08:30 AM EST — NO LOOK-AHEAD DATA)
    # -------------------------------------------------------------------------
    cutoff_0830 = et_timestamp(t_dt, 8, 30)
    df_pre = df_1m[df_1m.index <= cutoff_0830]

    # 1. HTF EMA Excursion
    ema_res = compute_htf_ema_analysis(ticker=ticker, target_date=target_date)

    # 2. Candle Science Open Mode
    cs_read = get_candle_science_read(ticker=ticker, mode="open", target_date=target_date)
    p_bull = float(cs_read.get("p_bull", 50.0)) if cs_read else 50.0
    p_bear = float(cs_read.get("p_bear", 50.0)) if cs_read else 50.0
    cs_bias = "BULLISH" if p_bull >= p_bear else "BEARISH"

    # Fix 4 — Both-sided Candle Science P30/P50/P70 target boxes
    # cs_read['mfe'] = upside MFE {p30, p50, p70}; cs_read['mae'] = downside depth {p30, p50, p70}
    cs_target_boxes = {}
    if cs_read:
        mfe = cs_read.get("mfe") or {}
        mae = cs_read.get("mae") or {}
        cs_target_boxes["bull"] = {"p30": mfe.get("p30"), "p50": mfe.get("p50"), "p70": mfe.get("p70")}
        cs_target_boxes["bear"] = {"p30": mae.get("p30"), "p50": mae.get("p50"), "p70": mae.get("p70")}

    # 3. P12 Range & Directional Switch (18:00 prev_day to 06:00 t_dt)
    prev_day = t_dt - timedelta(days=1)
    p12_start = et_timestamp(prev_day, 18, 0)
    p12_end = et_timestamp(t_dt, 6, 0)

    p12_bars = df_pre[(df_pre.index >= p12_start) & (df_pre.index < p12_end)]
    if p12_bars.empty:
        log.warning("Insufficient P12 bars for date %s", target_date)
        p12_high, p12_low, p12_mid = None, None, None
    else:
        p12_high = float(p12_bars["high"].max())
        p12_low = float(p12_bars["low"].min())
        p12_mid = float((p12_high + p12_low) / 2.0)

    # 06:00 to 08:30 ET Pre-Market Footing
    pre_start = et_timestamp(t_dt, 6, 0)
    pre_bars = df_pre[(df_pre.index >= pre_start) & (df_pre.index <= cutoff_0830)]

    if not pre_bars.empty and p12_mid is not None:
        last_pre_close = float(pre_bars.iloc[-1]["close"])
        p12_bias = "BULLISH" if last_pre_close >= p12_mid else "BEARISH"
        pre_handshake = "AGREEMENT" if (p12_bias == "BULLISH" and last_pre_close >= p12_mid) or (p12_bias == "BEARISH" and last_pre_close < p12_mid) else "DISAGREEMENT"
    else:
        last_pre_close = p12_mid
        p12_bias = "NEUTRAL"
        pre_handshake = "UNKNOWN"

    # 4. Overnight HOD/LOD actual print times (from pre-market bars)
    pre_hod_ts = pre_bars["high"].idxmax() if not pre_bars.empty else None
    pre_lod_ts = pre_bars["low"].idxmin() if not pre_bars.empty else None
    pre_hod_time_str = pre_hod_ts.strftime("%H:%M") if pre_hod_ts is not None else "N/A"
    pre_lod_time_str = pre_lod_ts.strftime("%H:%M") if pre_lod_ts is not None else "N/A"

    # Fix 1 — Wire compute_live_prediction() replacing the coarse CSV data source.
    # This provides per-outcome hod_lod_times, price_stats, and level_hit_rates.
    prior_type = "Unknown"
    overnight_key = "Unknown"
    ny1_pred: dict = {}
    profiler_context: dict = {}
    try:
        from scripts.analysis.analyze_daily_classification_bias import get_prior_classification
        prior_type = get_prior_classification(ticker, t_dt) or "Unknown"
    except Exception as e:
        log.warning("Prior classification lookup failed: %s", e)

    try:
        from scripts.libs_py.profiler.live_prediction import compute_live_prediction
        lp_result = compute_live_prediction(
            ticker=ticker,
            current_price=last_pre_close or 0.0,
            target_date=t_dt,
            now_et=cutoff_0830.to_pydatetime() if hasattr(cutoff_0830, "to_pydatetime") else cutoff_0830,
        )
        overnight_key = "|".join(
            f"{s}:{v}" for s, v in lp_result.get("context", {}).items()
        ) or "Unknown"
        profiler_context = lp_result.get("context", {})
        tgt_sess = lp_result.get("target_session", "NY1")
        ny1_pred = lp_result.get("predictions", {}).get(tgt_sess or "NY1", {})
    except Exception as e:
        log.warning("compute_live_prediction failed: %s", e)

    # Extract per-outcome data from profiler prediction
    ny1_probs      = ny1_pred.get("probabilities", {})
    ny1_hod_lod    = ny1_pred.get("hod_lod_times", {})
    ny1_price_stats = ny1_pred.get("price_stats", {})
    ny1_level_hits  = ny1_pred.get("level_hit_rates_per_outcome", {})
    ny1_samples     = ny1_pred.get("samples", 0)

    # Fix 2 — InStat: compare actual overnight HOD/LOD print time against profiler
    # expected time window per outcome (not P12 proximity).
    def _time_in_bucket(t_str: str, bucket: str) -> bool:
        """Return True if t_str (HH:MM) falls within bucket ('HH:MM-HH:MM')."""
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

    instat_status: dict = {}
    for outcome, timing in ny1_hod_lod.items():
        hod_mode = timing.get("hod_mode", "")
        lod_mode = timing.get("lod_mode", "")
        instat_status[outcome] = {
            "hod_mode": hod_mode,
            "lod_mode": lod_mode,
            "hod_in_stat": _time_in_bucket(pre_hod_time_str, hod_mode),
            "lod_in_stat": _time_in_bucket(pre_lod_time_str, lod_mode),
        }

    instat_lines = []
    for outcome, st in instat_status.items():
        hod_tag = "IN STAT" if st["hod_in_stat"] else "out of stat"
        lod_tag = "IN STAT" if st["lod_in_stat"] else "out of stat"
        instat_lines.append(
            f"{outcome}: HOD({pre_hod_time_str}) vs mode {st['hod_mode']} → {hod_tag} | "
            f"LOD({pre_lod_time_str}) vs mode {st['lod_mode']} → {lod_tag}"
        )
    instat_timing_status = f"Overnight HOD@{pre_hod_time_str} | LOD@{pre_lod_time_str}\n  " + "\n  ".join(instat_lines)

    # Confluence Matrix (Pre-Market 08:30 Cutoff)
    is_2to3 = bool(ema_res.get("is_2to3_zone", False))
    is_aligned = bool((cs_bias == p12_bias) and (pre_handshake == "AGREEMENT") and not is_2to3)
    confluence_status = "ALIGNED (High Conviction)" if is_aligned else "CONFLICTED (Caution / Reversion Risk)"

    # Pre-Market Position Sizing (Uses 08:30 pre-market price vs P12 Mid)
    default_stop = float(cfg.get("default_stop_points", 10.0))
    stop_dist = max(default_stop, abs(last_pre_close - p12_mid)) if (last_pre_close is not None and p12_mid is not None) else default_stop
    sizing = calculate_position_size(account_equity, risk_pct, stop_dist, ticker=ticker)

    # Fix 3 — True/False Scenarios with profiler per-outcome data + cutoff times.
    # Sort outcomes by probability descending
    sorted_outcomes = sorted(ny1_probs.items(), key=lambda x: x[1], reverse=True)
    # "False" outcomes = reversion (LF/SF); "True" = continuation (LT/ST)
    false_outcomes = [o for o, _ in sorted_outcomes if o in ("Long False", "Short False")]
    true_outcomes  = [o for o, _ in sorted_outcomes if o in ("Long True",  "Short True")]
    top_false = false_outcomes[0] if false_outcomes else (sorted_outcomes[1][0] if len(sorted_outcomes) > 1 else "")
    top_true  = true_outcomes[0]  if true_outcomes  else (sorted_outcomes[0][0] if sorted_outcomes else "")

    def _build_scenario(outcome: str) -> dict:
        prob     = ny1_probs.get(outcome, 0.0)
        timing   = ny1_hod_lod.get(outcome, {})
        ps       = ny1_price_stats.get(outcome, {})
        lhr      = ny1_level_hits.get(outcome, {})
        key_lvls = {lvl: lhr[lvl] for lvl in ["p12m", "midnight_open", "pdh", "pdl"] if lvl in lhr}
        return {
            "outcome": outcome,
            "probability": f"{prob*100:.1f}%",
            "hod_mode": timing.get("hod_mode", "N/A"),
            "lod_mode": timing.get("lod_mode", "N/A"),
            "hod_dist_span": ps.get("h_span", "N/A"),
            "lod_dist_span": ps.get("l_span", "N/A"),
            "hod_dist_median": ps.get("h_med"),
            "lod_dist_median": ps.get("l_med"),
            "cutoff_mode": "09:30-09:45",
            "cutoff_final": "10:15",
            "key_level_hits": key_lvls,
        }

    scenarios = {
        "false_scenario": _build_scenario(top_false) if top_false else {},
        "true_scenario":  _build_scenario(top_true)  if top_true  else {},
    }

    # -------------------------------------------------------------------------
    # PART 2: EOD REENGINEERING POST-MORTEM (16:00 PM EST — INTRADAY REPLAY)
    # -------------------------------------------------------------------------
    rth_start = et_timestamp(t_dt, 9, 30)
    rth_end = et_timestamp(t_dt, 16, 0)
    rth_bars = df_1m[(df_1m.index >= rth_start) & (df_1m.index <= rth_end)]

    if not rth_bars.empty:
        rth_open = float(rth_bars.iloc[0]["open"])
        actual_handshake = "AGREEMENT" if (p12_bias == "BULLISH" and rth_open >= (p12_mid or 0)) or (p12_bias == "BEARISH" and rth_open < (p12_mid or 0)) else "DISAGREEMENT"

        rth_high = float(rth_bars["high"].max())
        rth_low = float(rth_bars["low"].min())
        rth_close = float(rth_bars.iloc[-1]["close"])

        hod_time = rth_bars[rth_bars["high"] == rth_high].index[0].strftime("%H:%M")
        lod_time = rth_bars[rth_bars["low"] == rth_low].index[0].strftime("%H:%M")

        # Vectorized 3-Hour Line vs Apex Reversal Counter (09:00-12:00 block)
        h9_start = et_timestamp(t_dt, 9, 0)
        h9_end = et_timestamp(t_dt, 10, 0)
        h10_start = et_timestamp(t_dt, 10, 0)
        h10_end = et_timestamp(t_dt, 11, 0)
        block_end = et_timestamp(t_dt, 12, 0)

        bars_9 = df_1m[(df_1m.index >= h9_start) & (df_1m.index < h9_end)]
        bars_10 = df_1m[(df_1m.index >= h10_start) & (df_1m.index < h10_end)]
        bars_block = df_1m[(df_1m.index >= h9_start) & (df_1m.index <= block_end)]

        if not bars_9.empty and not bars_10.empty:
            h9_hi = float(bars_9["high"].max())
            h9_lo = float(bars_9["low"].min())
            h9_mid = (h9_hi + h9_lo) / 2.0
            h10_hi = float(bars_10["high"].max())
            h10_lo = float(bars_10["low"].min())

            step1 = bool(abs(h10_hi - rth_open) >= mom_threshold or abs(rth_open - h10_lo) >= mom_threshold)
            
            # Vectorized Step 2 (Close past midpoint + validation bar)
            close_prev = bars_10["close"].shift(1)
            cond_above = (close_prev > h9_mid) & (bars_10["low"] > h9_mid)
            cond_below = (close_prev < h9_mid) & (bars_10["high"] < h9_mid)
            step2 = bool((cond_above | cond_below).any())

            step3 = bool(h10_hi > h9_hi or h10_lo < h9_lo)
            # Fix 5 — Step 4: check Q1 of 10:00 AM hour establishes the hour extreme (InStat)
            q1_end_10 = h10_start + pd.Timedelta(minutes=15)
            bars_q1_10 = df_1m[(df_1m.index >= h10_start) & (df_1m.index < q1_end_10)]
            if not bars_q1_10.empty:
                q1_hi_10 = float(bars_q1_10["high"].max())
                q1_lo_10 = float(bars_q1_10["low"].min())
                step4 = bool(q1_hi_10 >= h10_hi or q1_lo_10 <= h10_lo)
            else:
                step4 = False
            
            step_score = sum([step1, step2, step3, step4])
            block_hi = float(bars_block["high"].max())
            block_lo = float(bars_block["low"].min())
            is_apex = bool((h10_hi == block_hi) or (h10_lo == block_lo))
            line_apex_result = f"{step_score}/4 ({'3-Hour Apex Pivot' if is_apex else '3-Hour Line Trend'})"
        else:
            line_apex_result = "N/A"

        # Winning Scenario Identification
        if p12_high and rth_high >= p12_high and rth_close > rth_open:
            winning_scenario = "Scenario A (Bullish Continuation)"
        elif p12_low and rth_low <= p12_low and rth_close < rth_open:
            winning_scenario = "Scenario B (Bearish Reversion)"
        else:
            winning_scenario = "Scenario C (Goalpost Chop / R1)"
    else:
        rth_open, rth_high, rth_low, rth_close = 0.0, 0.0, 0.0, 0.0
        actual_handshake = "N/A"
        hod_time, lod_time = "N/A", "N/A"
        line_apex_result = "N/A"
        winning_scenario = "N/A"

    report = {
        "ticker": ticker,
        "date": target_date,
        "premarket_0830": {
            "candle_science_bias": cs_bias,
            "candle_science_p_bull": p_bull,
            "candle_science_target_boxes": cs_target_boxes,
            "htf_ema_dist_pct": ema_res.get("dist_pct"),
            "is_2to3_magnet_zone": is_2to3,
            "p12_range": f"{p12_low or 0:.2f} - {p12_high or 0:.2f}",
            "p12_midline": round(p12_mid, 2) if p12_mid else None,
            "p12_premarket_bias": p12_bias,
            "premarket_handshake": pre_handshake,
            "prior_day_type": prior_type,
            "overnight_context": profiler_context,
            "overnight_key": overnight_key,
            "profiler_ny1_samples": ny1_samples,
            "profiler_ny1_probabilities": {k: f"{v*100:.1f}%" for k, v in ny1_probs.items()},
            "instat_timing": instat_timing_status,
            "instat_per_outcome": instat_status,
            "confluence_status": confluence_status,
            "position_sizing": sizing,
            "false_scenario": scenarios.get("false_scenario", {}),
            "true_scenario":  scenarios.get("true_scenario", {}),
        },
        "eod_reengineering_1600": {
            "rth_open": round(rth_open, 2),
            "actual_rth_handshake": actual_handshake,
            "rth_high": round(rth_high, 2),
            "rth_low": round(rth_low, 2),
            "rth_close": round(rth_close, 2),
            "hod_timestamp": hod_time,
            "lod_timestamp": lod_time,
            "line_vs_apex": line_apex_result,
            "4step_score": f"{sum([step1, step2, step3, step4])}/4" if 'step1' in dir() else "N/A",
            "step4_q1_instat": step4 if 'step4' in dir() else None,
            "winning_scenario": winning_scenario,
        }
    }

    # Print Formatted Report
    print("\n--- 1. PRE-MARKET WARGAME BRIEFING (08:30 AM EST — NO LOOK-AHEAD) ---")
    print(f"Ticker: {ticker} | Target Date: {target_date} | Account Equity: ${account_equity:,.2f}")
    print(f"Candle Science Bias: {cs_bias} (P_bull={p_bull:.1f}%)")
    if cs_target_boxes:
        bull = cs_target_boxes.get("bull", {})
        bear = cs_target_boxes.get("bear", {})
        print(f"  CS Targets → BULL: P30={bull.get('p30')} / P50={bull.get('p50')} / P70={bull.get('p70')} | BEAR: P30={bear.get('p30')} / P50={bear.get('p50')} / P70={bear.get('p70')}")
    print(f"HTF Weekly EMA Excursion: {ema_res.get('dist_pct', 0.0):+.2f}% | 2-3% Magnet: {'YES' if is_2to3 else 'NO'}")
    print(f"P12 Range (18:00-06:00): {p12_low or 0:.2f} - {p12_high or 0:.2f} | Midline: {p12_mid or 0:.2f}")
    print(f"06:00-08:30 Pre-Market Bias: {p12_bias} | 08:30 Pre-Market Handshake: {pre_handshake}")
    print(f"Overnight Context: {profiler_context}")
    print(f"NY1 Profiler ({ny1_samples} samples): {dict(sorted(ny1_probs.items(), key=lambda x: -x[1]))}")
    print(f"\nInStat HOD/LOD Timing:")
    print(f"  {instat_timing_status}")
    print(f"\nSignal Confluence: {confluence_status}")
    print(f"Position Sizing: {sizing['contract_count']} contracts (${sizing['dollars_at_risk']} at risk, {sizing['stop_distance_points']} pt stop)")
    print("\n📋 FALSE SCENARIO (Reversion):")
    fs = scenarios.get("false_scenario", {})
    if fs:
        print(f"  Outcome: {fs['outcome']} ({fs['probability']}) | HOD mode: {fs['hod_mode']} | LOD mode: {fs['lod_mode']}")
        print(f"  HOD dist: {fs['hod_dist_span']} | LOD dist: {fs['lod_dist_span']}")
        print(f"  Cutoff: mode={fs['cutoff_mode']} | final={fs['cutoff_final']}")
        for lvl, hr in fs.get("key_level_hits", {}).items():
            print(f"    {lvl}: {hr.get('hit_rate')}% (mode {hr.get('mode_time')})")
    print("\n📋 TRUE SCENARIO (Continuation):")
    ts = scenarios.get("true_scenario", {})
    if ts:
        print(f"  Outcome: {ts['outcome']} ({ts['probability']}) | HOD mode: {ts['hod_mode']} | LOD mode: {ts['lod_mode']}")
        print(f"  HOD dist: {ts['hod_dist_span']} | LOD dist: {ts['lod_dist_span']}")
        print(f"  Cutoff: mode={ts['cutoff_mode']} | final={ts['cutoff_final']} (if no reversal by 10:15 → True locks)")
        for lvl, hr in ts.get("key_level_hits", {}).items():
            print(f"    {lvl}: {hr.get('hit_rate')}% (mode {hr.get('mode_time')})")

    print("\n--- 2. EOD REENGINEERING POST-MORTEM (16:00 PM EST) ---")
    print(f"RTH Session: Open={rth_open:.2f} (Handshake: {actual_handshake}) | High={rth_high:.2f} ({hod_time}) | Low={rth_low:.2f} ({lod_time}) | Close={rth_close:.2f}")
    print(f"3-Hour Line vs Apex Score: {line_apex_result} | Step4 Q1 InStat: {step4 if 'step4' in dir() else 'N/A'}")
    print(f"🏆 WINNING SCENARIO: {winning_scenario}")
    print("==========================================================================\n")

    return report


if __name__ == "__main__":
    ticker_arg = sys.argv[1] if len(sys.argv) > 1 else "NQ1"
    date_arg = sys.argv[2] if len(sys.argv) > 2 else "2026-08-03"
    run_pilot_wargame_and_reengineering(ticker_arg, date_arg)
