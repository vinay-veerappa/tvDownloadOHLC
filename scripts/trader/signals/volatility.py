"""C1: VIX + VVIX Regime + Divergence signal.

Graduated 6-tier response model. Uses VIX/VVIX absolute level + rate of change.
No VVIX/VIX ratio (non-stationary, triggers in calm not panic).
"""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)
_REPO = Path(__file__).parent.parent.parent.parent


def _classify_vix_regime(vix: float, thresholds: dict) -> str:
    for name, threshold in thresholds.items():
        if vix <= threshold:
            return name
    return "crisis"


def get_vix_vvix_checkpoint() -> dict:
    """Returns VIX + VVIX regime, ROC, divergence, and sizing multiplier."""
    from scripts.trader.config_loader import get_config
    cfg = get_config()
    vix_thresh = cfg["vix_regimes"]
    vvix_thresh = cfg["vvix_regimes"]
    vix_sizing = cfg["vix_sizing"]
    vvix_roc_cfg = cfg["vvix_roc"]

    result = {
        "vix_close": None, "vix_prev": None, "vix_chg": None, "vix_regime": "unknown",
        "vvix_close": None, "vvix_prev": None, "vvix_chg": None, "vvix_regime": "unknown",
        "vvix_roc_regime": "unknown", "divergence_read": "unknown",
        "sizing_multiplier": 1.0,
    }

    # ── VIX ──
    try:
        vix_live = pd.read_parquet(_REPO / "data" / "live" / "live_storage_VIX.parquet")
        if not vix_live.empty:
            vix_close = float(vix_live["close"].iloc[-1])
            vix_prev = float(vix_live["close"].iloc[-2]) if len(vix_live) > 1 else vix_close
            result["vix_close"] = round(vix_close, 2)
            result["vix_prev"] = round(vix_prev, 2)
            result["vix_chg"] = round((vix_close / vix_prev - 1) * 100, 2) if vix_prev > 0 else 0.0
            result["vix_regime"] = _classify_vix_regime(vix_close, vix_thresh)
    except Exception as e:
        log.warning("[vix] Failed: %s", e)

    # ── VVIX ──
    try:
        vvix_live = pd.read_parquet(_REPO / "data" / "live" / "live_storage_VVIX.parquet")
        if not vvix_live.empty:
            vvix_close = float(vvix_live["close"].iloc[-1])
            vvix_prev = float(vvix_live["close"].iloc[-2]) if len(vvix_live) > 1 else vvix_close
            result["vvix_close"] = round(vvix_close, 2)
            result["vvix_prev"] = round(vvix_prev, 2)
            result["vvix_chg"] = round((vvix_close / vvix_prev - 1) * 100, 2) if vvix_prev > 0 else 0.0
            result["vvix_regime"] = _classify_vix_regime(vvix_close, vvix_thresh)
    except Exception as e:
        log.warning("[vvix] Failed: %s", e)

    # ── VVIX Rate of Change ──
    if result["vvix_chg"] is not None:
        chg = result["vvix_chg"]
        if chg > vvix_roc_cfg["fear_building"]:
            result["vvix_roc_regime"] = "fear_building"
        elif chg > vvix_roc_cfg["caution"]:
            result["vvix_roc_regime"] = "caution"
        elif chg < vvix_roc_cfg["unwinding"]:
            result["vvix_roc_regime"] = "unwinding"
        elif chg < vvix_roc_cfg["neutral"]:
            result["vvix_roc_regime"] = "neutral_down"
        else:
            result["vvix_roc_regime"] = "neutral"

    # ── VIX-VVIX Divergence ──
    vix_up = (result["vix_chg"] or 0) > 1.0
    vix_dn = (result["vix_chg"] or 0) < -1.0
    vvix_up = (result["vvix_chg"] or 0) > 1.0
    vvix_dn = (result["vvix_chg"] or 0) < -1.0
    vvix_faster = abs(result["vvix_chg"] or 0) > abs(result["vix_chg"] or 0) * cfg["vix_vvix_divergence"]["panic_multiplier"]

    if vix_up and vvix_up and vvix_faster:
        result["divergence_read"] = "panic"
    elif vix_up and not vvix_up:
        result["divergence_read"] = "hedging"
    elif vix_dn and vvix_dn:
        result["divergence_read"] = "complacency"
    elif vix_dn and vvix_up:
        result["divergence_read"] = "smart_money_divergence"
    else:
        result["divergence_read"] = "calm"

    # ── Sizing ── (take the more conservative of VIX/VVIX regime)
    vix_size = vix_sizing.get(result["vix_regime"], 1.0)
    vvix_size = vix_sizing.get(result["vvix_regime"], 1.0)
    result["sizing_multiplier"] = min(vix_size, vvix_size)

    return result


def format_volatility_block(data: dict) -> str:
    """Format the intermarket + volatility cheat sheet block."""
    lines = ["== INTERMARKET + VOLATILITY =="]
    if data["vix_close"] is not None:
        lines.append(f"VIX: {data['vix_close']} [{data['vix_regime'].upper()}] (chg {data['vix_chg']}%)")
    else:
        lines.append("VIX: unavailable")
    if data["vvix_close"] is not None:
        lines.append(f"VVIX: {data['vvix_close']} [{data['vvix_regime'].upper()}] (chg {data['vvix_chg']}%)")
        lines.append(f"VVIX ROC: {data['vvix_roc_regime']} | Divergence: {data['divergence_read']}")
    else:
        lines.append("VVIX: unavailable")
    lines.append(f"Vol sizing: {data['sizing_multiplier']:.0%} of normal")
    return "\n".join(lines)