"""C4: ICT Context from HTF Parquet.

Computes PDH/PDL/midnight open/weekly H/L from 1d and 1W parquet files.
No full 1m historical needed — uses HTF parquet (~0.5s vs 3-5s).
"""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)
_REPO = Path(__file__).parent.parent.parent.parent

# ET session anchors
RTH_START_HOUR = 9
RTH_START_MIN = 30
RTH_END_HOUR = 16
MIDNIGHT_HOUR = 0


def compute_ict_from_htf(ticker: str = "NQ1", current_price: float = 0) -> dict:
    """Compute ICT levels from daily + weekly parquet.

    Returns:
        dict with pdh, pdl, midnight_open, pwh, pwl, premium_discount, dealing_range_pct
    """
    result = {
        "pdh": None, "pdl": None, "pdc": None, "midnight_open": None,
        "pwh": None, "pwl": None,
        "dealing_range_pct": None, "premium_discount": "unknown",
        "bsl_target": None, "ssl_target": None,
        "weekly_range_pct": None,
    }

    # ── Daily: PDH/PDL/PDC ──
    try:
        df_1d = pd.read_parquet(_REPO / "data" / f"{ticker}_1d.parquet")
        if df_1d.index.tz is not None:
            df_1d.index = df_1d.index.tz_convert("US/Eastern")
        else:
            df_1d.index = df_1d.index.tz_localize("UTC").tz_convert("US/Eastern")

        if len(df_1d) >= 2:
            prior = df_1d.iloc[-2]
            result["pdh"] = round(float(prior["high"]), 2)
            result["pdl"] = round(float(prior["low"]), 2)
            result["pdc"] = round(float(prior["close"]), 2)
    except Exception as e:
        log.warning("[ict] Daily parquet error: %s", e)

    # ── Midnight open: from 1m parquet, last midnight 00:00 ET ──
    try:
        from scripts.utils.fused_data_loader import load_fused_data
        df_1m = load_fused_data(ticker, timeframe="1m", require_historical=False)
        if df_1m is not None and not df_1m.empty:
            if df_1m.index.tz is None:
                df_1m.index = pd.DatetimeIndex(df_1m.index).tz_localize("UTC").tz_convert("US/Eastern")
            else:
                df_1m.index = df_1m.index.tz_convert("US/Eastern")

            now_et = pd.Timestamp.now(tz="US/Eastern")
            midnight = now_et.normalize()
            midnight_bars = df_1m[df_1m.index >= midnight]
            if not midnight_bars.empty:
                result["midnight_open"] = round(float(midnight_bars["open"].iloc[0]), 2)
    except Exception as e:
        log.warning("[ict] Midnight open error: %s", e)

    # ── Weekly: PWH/PWL ──
    try:
        df_1w = pd.read_parquet(_REPO / "data" / f"{ticker}_1W.parquet")
        if df_1w.index.tz is not None:
            df_1w.index = df_1w.index.tz_convert("US/Eastern")
        else:
            df_1w.index = df_1w.index.tz_localize("UTC").tz_convert("US/Eastern")

        if len(df_1w) >= 2:
            prior_week = df_1w.iloc[-2]
            result["pwh"] = round(float(prior_week["high"]), 2)
            result["pwl"] = round(float(prior_week["low"]), 2)
    except Exception as e:
        log.warning("[ict] Weekly parquet error: %s", e)

    # ── Premium/Discount ──
    if result["pdh"] and result["pdl"] and current_price > 0:
        dealing_range = result["pdh"] - result["pdl"]
        if dealing_range > 0:
            pct = (current_price - result["pdl"]) / dealing_range * 100
            result["dealing_range_pct"] = round(pct, 1)
            result["premium_discount"] = "PREMIUM" if pct > 50 else "DISCOUNT"
            result["bsl_target"] = result["pdh"]  # buy-side liquidity above PDH
            result["ssl_target"] = result["pdl"]  # sell-side liquidity below PDL

    # ── Weekly range position ──
    if result["pwh"] and result["pwl"] and current_price > 0:
        weekly_range = result["pwh"] - result["pwl"]
        if weekly_range > 0:
            result["weekly_range_pct"] = round((current_price - result["pwl"]) / weekly_range * 100, 1)

    return result


def format_ict_block(ict: dict) -> str:
    lines = ["== ICT DEALING RANGE =="]
    if ict["pdh"] is None:
        return "== ICT DEALING RANGE ==\nNo daily parquet data"
    lines.append(f"PDH: {ict['pdh']:.2f} | PDL: {ict['pdl']:.2f} | PDC: {ict['pdc']:.2f}")
    if ict["midnight_open"]:
        lines.append(f"Midnight Open: {ict['midnight_open']:.2f}")
    if ict["dealing_range_pct"] is not None:
        lines.append(f"Price in {ict['premium_discount']} ({ict['dealing_range_pct']:.1f}% of PDH-PDL range)")
        lines.append(f"  R:R filter — {'longs poor R:R in premium' if ict['premium_discount'] == 'PREMIUM' else 'shorts poor R:R in discount'}")
    if ict["pwh"]:
        lines.append(f"Weekly: PWH {ict['pwh']:.2f} | PWL {ict['pwl']:.2f} | Position: {ict.get('weekly_range_pct', 'N/A')}%")
    lines.append(f"BSL: {ict.get('bsl_target', 'N/A')} | SSL: {ict.get('ssl_target', 'N/A')}")
    return "\n".join(lines)