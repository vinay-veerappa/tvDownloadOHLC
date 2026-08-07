"""
live_prediction.py — End-to-end live profiler prediction for automated trading.

Wires SessionBoxEngine → compute_profiler() → structured prediction output.

Usage:
    from scripts.libs_py.profiler.live_prediction import compute_live_prediction

    pred = compute_live_prediction("NQ1")
    # → {
    #     "ticker": "NQ1",
    #     "timestamp": "2026-07-17T14:30:00-04:00",
    #     "target_session": "NY2",
    #     "context": {"Asia": "Long True", "London": "Short False", ...},
    #     "predictions": {
    #       "NY2": {
    #         "probabilities": {"Long True": 0.45, ...},
    #         "price_stats": {...},
    #         "level_hit_rates": {...},
    #         "samples": 127,
    #       }
    #     },
    #     "bias": "BULLISH",
    #     "confidence": "high",
    #   }
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, date
from typing import Any, Dict, Optional

import pytz

from .engine import SessionBoxEngine

log = logging.getLogger(__name__)

ET = pytz.timezone("US/Eastern")


def compute_live_prediction(
    ticker: str = "NQ1",
    current_price: float = 0,
    target_date: Optional[date] = None,
    now_et: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Compute live profiler predictions for automated trading.

    End-to-end pipeline:
      1. Load live 1m data via SessionBoxEngine
      2. Extract current session box statuses (live_sessions)
      3. Pass to compute_profiler() for historical filtering
      4. Return structured prediction data

    Args:
        ticker: Ticker symbol (e.g. "NQ1", "ES1").
        current_price: Current/live price for level proximity.
        target_date: Trading date. Defaults to today.
        now_et: Current ET datetime. Defaults to now.

    Returns:
        Structured dict with predictions, bias, and confidence.
        All values are JSON-serializable.
    """
    if target_date is None:
        target_date = date.today()
    if now_et is None:
        now_et = datetime.now(ET)

    result: Dict[str, Any] = {
        "ticker": ticker,
        "timestamp": now_et.isoformat(),
        "target_date": target_date.isoformat(),
        "target_session": None,
        "context": {},
        "predictions": {},
        "bias": "NEUTRAL",
        "confidence": "low",
        "error": None,
    }

    # 1. Get live session box statuses
    try:
        engine = SessionBoxEngine.from_live(ticker, cutoff_time=now_et)
        live_sessions = engine.get_live_sessions()
        prev_context = engine.get_prev_context()
    except Exception as e:
        result["error"] = f"SessionBoxEngine failed: {e}"
        log.warning("[live_prediction] %s", e)
        return result

    # 2. Build context for display
    context = {}
    for session_name, data in live_sessions.items():
        if data.get("status") and data["status"] != "None":
            context[session_name] = data["status"]
    result["context"] = context

    # 3. Run profiler predictions
    try:
        from scripts.trader.signals.profiler import compute_profiler

        # Convert prev_context to sessions_prev format for compute_profiler
        # prev_context has keys like "prev_ny1_status", "prev_ny2_broken"
        # We need {session_name: {status, broken}} format
        sessions_prev = {}
        for key, val in prev_context.items():
            if key.startswith("prev_") and key.endswith("_status"):
                sess = key[5:-7]  # "prev_ny1_status" -> "ny1"
                sess_name = {"ny1": "NY1", "ny2": "NY2", "asia": "Asia", "london": "London"}.get(sess, sess.upper())
                broken_key = f"prev_{sess}_broken"
                sessions_prev[sess_name] = {
                    "status": val,
                    "broken": prev_context.get(broken_key, False),
                }

        profiler_data = compute_profiler(
            ticker=ticker,
            current_price=current_price,
            target_date=target_date,
            now_et=now_et,
            live_sessions=live_sessions,
            prev_sessions=sessions_prev if sessions_prev else None,
        )
    except Exception as e:
        result["error"] = f"compute_profiler failed: {e}"
        log.warning("[live_prediction] %s", e)
        return result

    result["target_session"] = profiler_data.get("target_session")

    # 4. Extract predictions for the target session
    predictions = profiler_data.get("predictions", {})
    tgt_session = result["target_session"]
    tgt_pred = predictions.get(tgt_session) if tgt_session else None

    if tgt_pred:
        result["predictions"][tgt_session] = _extract_prediction_summary(tgt_pred)

        # Determine bias from top outcome
        probs = tgt_pred.get("probabilities", {})
        if probs:
            top_outcome = max(probs, key=probs.get)
            if top_outcome in ("Long True", "Long False"):
                result["bias"] = "BULLISH"
            elif top_outcome in ("Short True", "Short False"):
                result["bias"] = "BEARISH"

            # Confidence based on sample size and probability spread
            samples = tgt_pred.get("samples", 0)
            top_prob = probs[top_outcome]
            if samples >= 100 and top_prob >= 0.50:
                result["confidence"] = "high"
            elif samples >= 30 and top_prob >= 0.40:
                result["confidence"] = "medium"
            else:
                result["confidence"] = "low"

    # 5. Include base rates for all sessions
    base_rates = profiler_data.get("base_rates", {})
    if base_rates:
        result["base_rates"] = {
            sess: {
                k: v for k, v in rates.items()
                if not k.startswith("_")
            }
            for sess, rates in base_rates.items()
        }

    # 6. Include level hit rates (conditional on filtered days)
    hr_cond = profiler_data.get("level_hit_rates_conditional", {})
    if hr_cond:
        result["level_hit_rates"] = hr_cond

    return result


def _extract_prediction_summary(pred: Dict) -> Dict[str, Any]:
    """Extract a clean summary from a prediction block.

    Strips internal fields (matched_dates, dates_by_outcome) and
    keeps only the actionable data.
    """
    return {
        "probabilities": pred.get("probabilities", {}),
        "price_stats": pred.get("price_stats", {}),
        "broken_rates": pred.get("broken_rates", {}),
        "hod_lod_times": pred.get("hod_lod_times", {}),
        "samples": pred.get("samples", 0),
        "fallback_level": pred.get("fallback_level", 0),
        "context": pred.get("context", ""),
        "level_hit_rates_per_outcome": pred.get("level_hit_rates_per_outcome", {}),
    }


def compute_live_prediction_json(
    ticker: str = "NQ1",
    current_price: float = 0,
    **kwargs,
) -> str:
    """Convenience: compute_live_prediction() → JSON string."""
    result = compute_live_prediction(ticker, current_price, **kwargs)
    return json.dumps(result, indent=2, default=str, ensure_ascii=False)
