"""ICT Bias Signal Generator — Phase 2B
=========================================

Generates ``data/derived/ICT/{sym}_bias_signals.parquet`` containing per-day,
per-eval-time bias signals from all 7 ICT daily bias models, plus the
actual outcome (close direction, max excursion direction, magnitude).

This is the DATA LAYER only. The analysis layer (win rates, weighting,
per-model stats) is a separate concern — see ``analyze_bias_signals()``.

Schema
-------
::

    trading_date        date
    symbol              str
    eval_time           str     "18:00", "02:00", "08:30", "09:30", "11:00", "13:30", "16:00"
    eval_price           float   price at eval_time (from 1m data)
    current_price        float   price at eval_time (alias)

    # Per-model signals (null = not valid for this eval_time):
    model_a_pd           str     "BULLISH" | "BEARISH" | "NEUTRAL" | null
    model_b_dol          str
    model_c_ipda         str
    model_d_htf          str
    model_e_pdc          str
    model_f_midnight     str     (only after 00:00)
    model_g_sweep        str     (only after 05:00)

    # Composite:
    composite_bias       str
    composite_conf       int
    bull_score           int
    bear_score           int

    # Outcomes (measured from eval_price to RTH close at 16:00):
    rth_close            float
    rth_close_dir        str     "BULLISH" | "BEARISH" | "FLAT"
    max_high             float   highest price after eval_time until 16:00
    max_low              float   lowest price after eval_time until 16:00
    max_excursion_dir    str     "BULLISH" | "BEARISH" | "BOTH" | "FLAT"
    excursion_magnitude  float   max abs move as % of eval_price

Usage
-----
::

    # Generate bias signals for NQ1 (all history)
    python -m scripts.context.generate_bias_signals --symbols NQ1

    # Specific symbols + lookback
    python -m scripts.context.generate_bias_signals --symbols NQ1,ES1 --lookback 2500

    # Full rebuild
    python -m scripts.context.generate_bias_signals --full-regen
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from datetime import datetime, time, date
from typing import Any

import pandas as pd
import numpy as np

_REPO_ROOT = Path(__file__).parent.parent.parent
_ICT_DIR = _REPO_ROOT / "data" / "derived" / "ICT"

if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

logger = logging.getLogger(__name__)

DEFAULT_SYMBOLS = ["NQ1", "ES1"]

# Evaluation times (skip 05:00 — covered by 08:30)
EVAL_TIMES = ["18:00", "02:00", "08:30", "09:30", "11:00", "13:30", "16:00"]

# Session boundaries: each eval time predicts a specific "next session candle"
# The session is defined as [session_start, session_end] in ET
# Outcomes: session_open (price at session_start), session_close (price at session_end)
#           session_dir = BULLISH if close > open, BEARISH if close < open, FLAT if equal
#           session_body_pct = (close - open) / open * 100  (ADR-002 compliant)
SESSION_WINDOWS = {
    "18:00": ("18:00", "02:00"),  # Asia session candle
    "02:00": ("02:00", "08:30"),  # London session candle
    "08:30": ("09:30", "11:00"),  # NY AM session candle
    "09:30": ("09:30", "16:00"),  # Full RTH candle (the "day")
    "11:00": ("11:00", "13:30"),  # NY Lunch candle
    "13:30": ("13:30", "16:00"),  # NY PM candle
    "16:00": ("16:00", "18:00"),  # After-close / overnight transition
}

# Eval times when each model becomes valid (earliest eval_time it can produce a signal)
# Models A-E are valid from 18:00 (prior day data available)
# Model F (midnight open) valid from 02:00 (midnight has passed)
# Model G (London/Asia sweep) valid from 08:30 (London session complete)
MODEL_VALID_FROM = {
    "model_a_pd": "18:00",
    "model_b_dol": "18:00",
    "model_c_ipda": "18:00",
    "model_d_htf": "18:00",
    "model_e_pdc": "18:00",
    "model_f_midnight": "02:00",
    "model_g_sweep": "08:30",
}

# Order of eval times for comparison
EVAL_ORDER = {t: i for i, t in enumerate(EVAL_TIMES)}


def _bias_signal_path(symbol: str) -> Path:
    return _ICT_DIR / f"{symbol}_bias_signals.parquet"


# ═══════════════════════════════════════════════════════════════════════
#  Data Loading
# ═══════════════════════════════════════════════════════════════════════

def _load_1m(symbol: str) -> pd.DataFrame:
    """Load 1m data, return ET-localized."""
    from scripts.edgeful.lib.data_loader import get_loader
    df = get_loader().load_1m(symbol)
    if df.empty:
        return df
    from scripts.libs_py.nqstats.sessions import normalize_to_eastern
    return normalize_to_eastern(df)


def _load_daily_resampled(df_1m: pd.DataFrame) -> pd.DataFrame:
    """Resample 1m to daily for IPDA/HTF when daily parquet is stale."""
    daily = (
        df_1m[["open", "high", "low", "close"]]
        .resample("D")
        .agg({"open": "first", "high": "max", "low": "min", "close": "last"})
        .dropna()
    )
    return daily


# ═══════════════════════════════════════════════════════════════════════
#  Per-Model Signal Computation
# ═══════════════════════════════════════════════════════════════════════

def _model_a_pd(pdh, pdl, current_price) -> str | None:
    """Premium/Discount — price position in PDH/PDL dealing range."""
    if pdh is None or pdl is None or current_price <= 0:
        return None
    rng = pdh - pdl
    if rng <= 0:
        return None
    pct = (current_price - pdl) / rng * 100
    if pct < 40:
        return "BULLISH"
    elif pct > 60:
        return "BEARISH"
    return "NEUTRAL"


def _model_b_dol(pdh, pdl, pwh, pwl, current_price) -> str | None:
    """Draw on Liquidity — proximity to BSL vs SSL."""
    if pdh is None or pdl is None or current_price <= 0:
        return None
    bsl_candidates = [pdh]
    ssl_candidates = [pdl]
    if pwh and pwh > current_price:
        bsl_candidates.append(pwh)
    if pwl and pwl < current_price:
        ssl_candidates.append(pwl)
    nearest_bsl = min(bsl_candidates, key=lambda x: abs(x - current_price))
    nearest_ssl = min(ssl_candidates, key=lambda x: abs(x - current_price))
    dist_bsl = abs(nearest_bsl - current_price)
    dist_ssl = abs(nearest_ssl - current_price)
    if dist_ssl < dist_bsl * 0.7:
        return "BEARISH"
    elif dist_bsl < dist_ssl * 0.7:
        return "BULLISH"
    return "NEUTRAL"


def _model_c_ipda(ipda_row, current_price) -> str | None:
    """IPDA Position — 20/40/60-day rolling range position."""
    if ipda_row is None or current_price <= 0:
        return None
    ipda20_pct = ipda_row.get("ipda20_pct")
    ipda60_pct = ipda_row.get("ipda60_pct")
    if pd.isna(ipda20_pct) or pd.isna(ipda60_pct):
        return None
    if ipda20_pct < 40 and ipda60_pct < 50:
        return "BULLISH"
    elif ipda20_pct > 60 and ipda60_pct > 60:
        return "BEARISH"
    return "NEUTRAL"


def _model_d_htf(pwh, pwl, current_price, weekly_pct) -> str | None:
    """HTF Structure — price vs PWH/PWL."""
    if pwh is None or pwl is None or current_price <= 0:
        return None
    if current_price > pwh:
        return "BULLISH"
    elif current_price < pwl:
        return "BEARISH"
    if weekly_pct is not None and not pd.isna(weekly_pct):
        if weekly_pct < 30:
            return "BEARISH"
        elif weekly_pct > 70:
            return "BULLISH"
    return "NEUTRAL"


def _model_e_pdc(pdh, pdl, pdc, current_price) -> str | None:
    """Prior Day Candle — close vs PDH/PDL."""
    if pdh is None or pdl is None or pdc is None or current_price <= 0:
        return None
    if pdc > pdh:
        return "BULLISH"
    elif pdc < pdl:
        return "BEARISH"
    if current_price > pdc:
        return "BULLISH"
    elif current_price < pdc:
        return "BEARISH"
    return "NEUTRAL"


def _model_f_midnight(midnight_open, current_price) -> str | None:
    """Midnight Open — price above/below midnight open."""
    if midnight_open is None or current_price <= 0:
        return None
    mid = float(midnight_open)
    if current_price < mid:
        return "BULLISH"
    elif current_price > mid:
        return "BEARISH"
    return "NEUTRAL"


def _model_g_sweep(kz_row, current_price) -> str | None:
    """London/Asia Sweep — London swept Asia H/L."""
    if kz_row is None or current_price <= 0:
        return None
    asia_h = kz_row.get("asia_high")
    asia_l = kz_row.get("asia_low")
    london_h = kz_row.get("london_high")
    london_l = kz_row.get("london_low")
    if pd.isna(asia_h) or pd.isna(asia_l) or pd.isna(london_h) or pd.isna(london_l):
        return None
    if london_l < asia_l and current_price > london_l:
        return "BULLISH"
    elif london_h > asia_h and current_price < london_h:
        return "BEARISH"
    return "NEUTRAL"


# ═══════════════════════════════════════════════════════════════════════
#  Per-Model Scores
# ═══════════════════════════════════════════════════════════════════════

MODEL_SCORES = {
    "model_a_pd": 25,
    "model_b_dol": 20,
    "model_c_ipda": 25,
    "model_d_htf": 20,
    "model_e_pdc": 20,
    "model_f_midnight": 15,
    "model_g_sweep": 15,
}

# Map signal to score direction
SIGNAL_SCORE = {"BULLISH": 1, "BEARISH": -1, "NEUTRAL": 0}


def _compute_composite(signals: dict) -> tuple[str, int, int, int]:
    """Compute composite bias from per-model signals.

    Returns (bias, confidence, bull_score, bear_score).
    """
    bull_score = 0
    bear_score = 0
    for model_name, signal in signals.items():
        if signal is None or signal not in SIGNAL_SCORE:
            continue
        score = MODEL_SCORES.get(model_name, 0)
        direction = SIGNAL_SCORE[signal]
        if direction > 0:
            bull_score += score
        elif direction < 0:
            bear_score += score

    max_score = sum(MODEL_SCORES.values())  # 140
    total = bull_score + bear_score
    if total == 0:
        return "NEUTRAL", 0, bull_score, bear_score
    elif bull_score > bear_score:
        conf = int((bull_score / max_score) * 100)
        return "BULLISH", min(conf, 100), bull_score, bear_score
    else:
        conf = int((bear_score / max_score) * 100)
        return "BEARISH", min(conf, 100), bull_score, bear_score


# ═══════════════════════════════════════════════════════════════════════
#  Main Generator
# ═══════════════════════════════════════════════════════════════════════

def generate_bias_signals(symbol: str, lookback_days: int = 5000, full_regen: bool = False) -> int:
    """Generate bias signal parquet for one symbol.

    For each trading day, computes bias at 7 eval times using the derived
    parquets (HTF levels, IPDA, KZ pivots) and 1m data (for eval_price,
    midnight open, and outcomes).

    Returns row count written.
    """
    logger.info("Generating bias signals for %s (lookback=%d days)...", symbol, lookback_days)

    # Load derived parquets
    htf_path = _ICT_DIR / f"{symbol}_htf_levels.parquet"
    ipda_path = _ICT_DIR / f"{symbol}_ipda.parquet"
    kz_path = _ICT_DIR / f"{symbol}_kz_pivots.parquet"

    if not htf_path.exists() or not ipda_path.exists() or not kz_path.exists():
        logger.error("Missing derived parquets for %s. Run compute_ict_features first.", symbol)
        return 0

    htf_df = pd.read_parquet(htf_path)
    ipda_df = pd.read_parquet(ipda_path)
    kz_df = pd.read_parquet(kz_path)

    # Normalize dates
    htf_df["trading_date"] = pd.to_datetime(htf_df["trading_date"]).dt.date
    ipda_df["trading_date"] = pd.to_datetime(ipda_df["trading_date"]).dt.date
    kz_df["trading_date"] = pd.to_datetime(kz_df["trading_date"]).dt.date

    # Load 1m data
    df_1m = _load_1m(symbol)
    if df_1m.empty:
        logger.error("No 1m data for %s", symbol)
        return 0

    # Determine date range
    all_dates = sorted(htf_df["trading_date"].unique())
    cutoff_date = pd.Timestamp.now().date() - pd.Timedelta(days=lookback_days)
    trading_dates = [d for d in all_dates if d >= cutoff_date]
    logger.info("  Processing %d trading days (%s to %s)",
                len(trading_dates), trading_dates[0] if trading_dates else "?",
                trading_dates[-1] if trading_dates else "?")

    rows = []

    for td in trading_dates:
        # Get HTF levels for this date (use the row matching this date)
        htf_row = htf_df[htf_df["trading_date"] == td]
        if htf_row.empty:
            continue
        htf = htf_row.iloc[0]
        pdh = htf.get("pdh")
        pdl = htf.get("pdl")
        pdc = None  # PDC not in HTF parquet — will get from 1d
        pwh = htf.get("pwh")
        pwl = htf.get("pwl")
        weekly_pct = None  # Compute from pwh/pwl if needed

        # Get IPDA for this date
        ipda_row_data = ipda_df[ipda_df["trading_date"] == td]
        ipda_row = ipda_row_data.iloc[0] if not ipda_row_data.empty else None

        # Get KZ pivots for this date
        kz_row_data = kz_df[kz_df["trading_date"] == td]
        kz_row = kz_row_data.iloc[0] if not kz_row_data.empty else None

        # Get PDC from daily data (prior day close)
        # We can approximate: find the HTF row for the prior day
        td_idx = all_dates.index(td)
        if td_idx > 0:
            prior_td = all_dates[td_idx - 1]
            prior_htf = htf_df[htf_df["trading_date"] == prior_td]
            if not prior_htf.empty:
                # PDC is the close of the day before td, but we don't have close in htf
                # We'll use the 1m data to get it
                pass

        # Compute weekly_pct from pwh/pwl
        if pdh is not None and pdl is not None and pwh is not None and pwl is not None:
            weekly_range = pwh - pwl
            if weekly_range > 0:
                # We need current price for weekly_pct, which varies by eval_time
                pass

        # Get 1m bars for this trading date
        td_ts = pd.Timestamp(td)
        next_td_ts = td_ts + pd.Timedelta(days=1)

        # For 18:00 eval, we need the prior day's 18:00 bar
        # The trading date rolls at 18:00 ET
        day_start = td_ts + pd.Timedelta(hours=18) - pd.Timedelta(days=1)  # 18:00 prior day
        day_end = td_ts + pd.Timedelta(hours=16, minutes=15)  # 16:15 today

        day_bars = df_1m[(df_1m.index >= day_start) & (df_1m.index <= day_end)]
        if day_bars.empty:
            continue

        # Get midnight open (00:00 ET bar open)
        midnight_start = td_ts + pd.Timedelta(hours=0)
        midnight_bars = day_bars[day_bars.index >= midnight_start]
        midnight_open = float(midnight_bars["open"].iloc[0]) if not midnight_bars.empty else None

        # Get PDC: close of the prior day's last bar (before 18:00)
        prior_day_end = day_start
        prior_bars = df_1m[df_1m.index < prior_day_end]
        if not prior_bars.empty:
            pdc = float(prior_bars["close"].iloc[-1])
        else:
            pdc = None

        # RTH close (16:00 ET bar close)
        rth_end = td_ts + pd.Timedelta(hours=16)
        rth_bars = day_bars[day_bars.index <= rth_end + pd.Timedelta(minutes=1)]
        rth_close = float(rth_bars["close"].iloc[-1]) if not rth_bars.empty else None

        # For each eval time, compute signals
        for eval_time_str in EVAL_TIMES:
            eval_hour, eval_min = int(eval_time_str.split(":")[0]), int(eval_time_str.split(":")[1])
            eval_ts = td_ts + pd.Timedelta(hours=eval_hour, minutes=eval_min)

            # Get eval_price: the close of the bar at or just before eval_ts
            eval_bars = day_bars[day_bars.index <= eval_ts]
            if eval_bars.empty:
                continue
            eval_price = float(eval_bars["close"].iloc[-1])

            # Compute weekly_pct
            if pwh and pwl and eval_price > 0:
                wr = pwh - pwl
                if wr > 0:
                    weekly_pct = (eval_price - pwl) / wr * 100
                else:
                    weekly_pct = None
            else:
                weekly_pct = None

            # Compute per-model signals
            signals = {}

            signals["model_a_pd"] = _model_a_pd(pdh, pdl, eval_price)
            signals["model_b_dol"] = _model_b_dol(pdh, pdl, pwh, pwl, eval_price)
            signals["model_c_ipda"] = _model_c_ipda(ipda_row, eval_price)
            signals["model_d_htf"] = _model_d_htf(pwh, pwl, eval_price, weekly_pct)
            signals["model_e_pdc"] = _model_e_pdc(pdh, pdl, pdc, eval_price)

            # Model F: only valid at 02:00 and later
            if EVAL_ORDER[eval_time_str] >= EVAL_ORDER["02:00"]:
                signals["model_f_midnight"] = _model_f_midnight(midnight_open, eval_price)
            else:
                signals["model_f_midnight"] = None

            # Model G: only valid at 08:30 and later
            if EVAL_ORDER[eval_time_str] >= EVAL_ORDER["08:30"]:
                signals["model_g_sweep"] = _model_g_sweep(kz_row, eval_price)
            else:
                signals["model_g_sweep"] = None

            # Compute composite
            composite_bias, composite_conf, bull_score, bear_score = _compute_composite(signals)

            # Compute outcomes (from eval_price to RTH close)
            future_bars = day_bars[day_bars.index > eval_ts]
            if rth_close is not None and eval_price > 0:
                rth_close_dir = "BULLISH" if rth_close > eval_price else ("BEARISH" if rth_close < eval_price else "FLAT")
            else:
                rth_close_dir = None

            # Max excursion
            if not future_bars.empty and eval_price > 0:
                max_high = float(future_bars["high"].max())
                max_low = float(future_bars["low"].min())
                up_exc = (max_high - eval_price) / eval_price * 100
                down_exc = (eval_price - max_low) / eval_price * 100
                if up_exc > 0.05 and down_exc > 0.05:
                    max_excursion_dir = "BOTH"
                elif up_exc > 0.05:
                    max_excursion_dir = "BULLISH"
                elif down_exc > 0.05:
                    max_excursion_dir = "BEARISH"
                else:
                    max_excursion_dir = "FLAT"
                excursion_magnitude = max(up_exc, down_exc)
            else:
                max_high = None
                max_low = None
                max_excursion_dir = None
                excursion_magnitude = None

            # Session candle outcome (per-session candle direction)
            sess_start_str, sess_end_str = SESSION_WINDOWS.get(eval_time_str, (None, None))
            session_open = None
            session_close = None
            session_high = None
            session_low = None
            session_dir = None
            session_body_pct = None
            if sess_start_str and sess_end_str:
                sess_start_h, sess_start_m = int(sess_start_str.split(":")[0]), int(sess_start_str.split(":")[1])
                sess_end_h, sess_end_m = int(sess_end_str.split(":")[0]), int(sess_end_str.split(":")[1])
                # Session start: same day (or next day for overnight sessions)
                if eval_hour >= 16:
                    # 16:00 and 18:00 evals: session is on the next trading day
                    sess_start_ts = td_ts + pd.Timedelta(days=1, hours=sess_start_h, minutes=sess_start_m)
                    sess_end_ts = td_ts + pd.Timedelta(days=1, hours=sess_end_h, minutes=sess_end_m) if sess_end_h < sess_start_h else td_ts + pd.Timedelta(days=1, hours=sess_end_h, minutes=sess_end_m)
                else:
                    sess_start_ts = td_ts + pd.Timedelta(hours=sess_start_h, minutes=sess_start_m)
                    if sess_end_h <= sess_start_h and sess_end_h < 12:
                        # Session wraps past midnight (e.g., 18:00 -> 02:00)
                        sess_end_ts = td_ts + pd.Timedelta(days=1, hours=sess_end_h, minutes=sess_end_m)
                    else:
                        sess_end_ts = td_ts + pd.Timedelta(hours=sess_end_h, minutes=sess_end_m)

                sess_bars = df_1m[(df_1m.index >= sess_start_ts) & (df_1m.index < sess_end_ts)]
                if not sess_bars.empty and eval_price > 0:
                    session_open = float(sess_bars["open"].iloc[0])
                    session_close = float(sess_bars["close"].iloc[-1])
                    session_high = float(sess_bars["high"].max())
                    session_low = float(sess_bars["low"].min())
                    session_dir = "BULLISH" if session_close > session_open else ("BEARISH" if session_close < session_open else "FLAT")
                    session_body_pct = round((session_close - session_open) / session_open * 100, 3)

            row = {
                "trading_date": td,
                "symbol": symbol,
                "eval_time": eval_time_str,
                "eval_price": round(eval_price, 2),
                "current_price": round(eval_price, 2),
            }
            for model_name in ["model_a_pd", "model_b_dol", "model_c_ipda", "model_d_htf",
                               "model_e_pdc", "model_f_midnight", "model_g_sweep"]:
                row[model_name] = signals[model_name]

            row["composite_bias"] = composite_bias
            row["composite_conf"] = composite_conf
            row["bull_score"] = bull_score
            row["bear_score"] = bear_score
            row["rth_close"] = round(rth_close, 2) if rth_close else None
            row["rth_close_dir"] = rth_close_dir
            row["max_high"] = round(max_high, 2) if max_high else None
            row["max_low"] = round(max_low, 2) if max_low else None
            row["max_excursion_dir"] = max_excursion_dir
            row["excursion_magnitude"] = round(excursion_magnitude, 2) if excursion_magnitude else None

            # Session candle outcomes
            row["session_open"] = round(session_open, 2) if session_open else None
            row["session_close"] = round(session_close, 2) if session_close else None
            row["session_high"] = round(session_high, 2) if session_high else None
            row["session_low"] = round(session_low, 2) if session_low else None
            row["session_dir"] = session_dir
            row["session_body_pct"] = session_body_pct

            rows.append(row)

    if not rows:
        logger.warning("  No rows generated for %s", symbol)
        return 0

    result = pd.DataFrame(rows)

    # Write
    out = _bias_signal_path(symbol)
    result.to_parquet(out, index=False)
    logger.info("  Wrote %s rows -> %s", f"{len(result):,}", out.name)
    return len(result)


# ═══════════════════════════════════════════════════════════════════════
#  Analysis Layer
# ═══════════════════════════════════════════════════════════════════════

def analyze_bias_signals(symbol: str, eval_time: str = "09:30",
                          outcome: str = "rth_close_dir") -> dict:
    """Analyze bias signals for one symbol at one eval time.

    Parameters
    ----------
    symbol : str
    eval_time : str
        Which evaluation time to analyze.
    outcome : str
        Which outcome to measure against: "rth_close_dir" or "max_excursion_dir".

    Returns
    -------
    dict with per-model stats and composite stats.
    """
    path = _bias_signal_path(symbol)
    if not path.exists():
        logger.error("No bias signals for %s. Run generate first.", symbol)
        return {}

    df = pd.read_parquet(path)
    df = df[df["eval_time"] == eval_time].copy()
    if df.empty:
        logger.error("No rows for eval_time=%s", eval_time)
        return {}

    df_valid = df[df[outcome].notna()].copy()
    if df_valid.empty:
        return {}

    results = {"symbol": symbol, "eval_time": eval_time, "outcome": outcome, "total_days": len(df_valid)}

    # Per-model analysis
    model_stats = {}
    for model_name in ["model_a_pd", "model_b_dol", "model_c_ipda", "model_d_htf",
                       "model_e_pdc", "model_f_midnight", "model_g_sweep"]:
        valid = df_valid[df_valid[model_name].notna()]
        if valid.empty:
            model_stats[model_name] = {"coverage": 0, "win_rate": None}
            continue
        # Win rate: signal matches outcome direction
        # For "BOTH" excursion, skip (ambiguous)
        if outcome == "max_excursion_dir":
            valid = valid[valid[outcome].isin(["BULLISH", "BEARISH"])]
            if valid.empty:
                model_stats[model_name] = {"coverage": 0, "win_rate": None}
                continue
        correct = (valid[model_name] == valid[outcome]).sum()
        total = len(valid)
        coverage = total / len(df_valid) * 100
        win_rate = correct / total * 100 if total > 0 else 0
        edge = win_rate - 50
        model_stats[model_name] = {
            "coverage": round(coverage, 1),
            "total_signals": total,
            "correct": correct,
            "win_rate": round(win_rate, 1),
            "edge": round(edge, 1),
        }
    results["models"] = model_stats

    # Composite analysis
    valid_comp = df_valid[df_valid["composite_bias"].notna() & (df_valid["composite_bias"] != "NEUTRAL")]
    if outcome == "max_excursion_dir":
        valid_comp = valid_comp[valid_comp[outcome].isin(["BULLISH", "BEARISH"])]
    if not valid_comp.empty:
        comp_correct = (valid_comp["composite_bias"] == valid_comp[outcome]).sum()
        comp_total = len(valid_comp)
        results["composite"] = {
            "coverage": round(comp_total / len(df_valid) * 100, 1),
            "total_signals": comp_total,
            "correct": comp_correct,
            "win_rate": round(comp_correct / comp_total * 100, 1) if comp_total > 0 else 0,
        }

        # Confidence bucket analysis
        buckets = {"0-30%": (0, 30), "30-60%": (30, 60), "60-80%": (60, 80), "80-100%": (80, 100)}
        conf_stats = {}
        for label, (lo, hi) in buckets.items():
            bucket = valid_comp[(valid_comp["composite_conf"] >= lo) & (valid_comp["composite_conf"] < hi)]
            if not bucket.empty:
                b_correct = (bucket["composite_bias"] == bucket[outcome]).sum()
                b_total = len(bucket)
                conf_stats[label] = {
                    "count": b_total,
                    "win_rate": round(b_correct / b_total * 100, 1),
                }
        results["confidence_buckets"] = conf_stats

    return results


# ═══════════════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="ICT Bias Signal Generator + Analyzer — Phase 2B"
    )
    parser.add_argument("--symbols", type=str, default="NQ1",
                        help="Comma-separated symbols (default: NQ1)")
    parser.add_argument("--lookback", type=int, default=5000,
                        help="Lookback in days (default: 5000 — uses all available history)")
    parser.add_argument("--full-regen", action="store_true",
                        help="Full rebuild (always — bias signals are a full recomputation)")
    parser.add_argument("--analyze", action="store_true",
                        help="Run analysis after generating")
    parser.add_argument("--eval-time", type=str, default="09:30",
                        help="Eval time to analyze (default: 09:30)")
    parser.add_argument("--outcome", type=str, default="rth_close_dir",
                        help="Outcome to measure: rth_close_dir, max_excursion_dir, or session_dir")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    symbols = args.symbols.split(",")
    for sym in symbols:
        generate_bias_signals(sym, lookback_days=args.lookback, full_regen=True)

        if args.analyze:
            print(f"\n{'='*60}")
            print(f"BIAS ANALYSIS: {sym} @ {args.eval_time}")
            print(f"Outcome: {args.outcome}")
            print(f"{'='*60}")
            results = analyze_bias_signals(sym, eval_time=args.eval_time, outcome=args.outcome)
            if not results:
                print("No results.")
                continue
            print(f"Total trading days: {results['total_days']}")
            print(f"\n--- Per-Model Stats ---")
            print(f"{'Model':<25s} {'Coverage':>8s} {'Signals':>7s} {'Correct':>7s} {'Win%':>6s} {'Edge':>6s}")
            print("-" * 65)
            for name, stats in results["models"].items():
                if stats["win_rate"] is None:
                    print(f"{name:<25s} {'N/A':>8s}")
                else:
                    print(f"{name:<25s} {stats['coverage']:>7.1f}% {stats['total_signals']:>7d} "
                          f"{stats['correct']:>7d} {stats['win_rate']:>5.1f}% {stats['edge']:>+5.1f}%")

            if "composite" in results:
                comp = results["composite"]
                print(f"\n--- Composite ---")
                print(f"Coverage: {comp['coverage']:.1f}% | Signals: {comp['total_signals']} | "
                      f"Correct: {comp['correct']} | Win Rate: {comp['win_rate']:.1f}%")

            if "confidence_buckets" in results:
                print(f"\n--- Confidence Buckets ---")
                for label, stats in results["confidence_buckets"].items():
                    print(f"  {label}: {stats['count']} signals, {stats['win_rate']:.1f}% win rate")

            print()


if __name__ == "__main__":
    main()