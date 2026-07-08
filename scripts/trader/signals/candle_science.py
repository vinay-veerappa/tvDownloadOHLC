"""C8: Candle Science auto-detect signal.

Reads last 2 daily candles, builds auto-detect filters, calls CandleScienceService.
Reports P(C3 bull/bear), MFE/MAE percentiles for target/drawdown estimation.
n=12 is normal on daily charts — don't filter on sample size.
"""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)
_REPO = Path(__file__).parent.parent.parent.parent


def get_candle_science_read(ticker: str = "NQ1") -> dict:
    """Get Candle Science C1→C2→C3 pattern match and MFE/MAE.

    Returns:
        dict with pattern description, probabilities, MFE/MAE percentiles, edge, rr_envelope
    """
    from scripts.trader.config_loader import get_config
    cfg = get_config()
    cs_cfg = cfg["candle_science"]

    result = {
        "c1_dir": "N/A", "c2_dir": "N/A",
        "pattern_desc": "N/A",
        "n_matches": 0,
        "p_bull": 50.0, "p_bear": 50.0,
        "p_break_high": None, "p_break_low": None,
        "p_close_gt_c2c": None,
        "edge": 0.0,
        "mfe": {}, "mae": {},
        "rr_envelope": None,
        "agrees_with_bias": None,
    }

    # ── Read last 2 daily candles for auto-detect ──
    try:
        df_1d = pd.read_parquet(_REPO / "data" / f"{ticker}_1d.parquet")
        if df_1d.index.tz is not None:
            df_1d.index = df_1d.index.tz_convert("US/Eastern")
        else:
            df_1d.index = df_1d.index.tz_localize("UTC").tz_convert("US/Eastern")

        if len(df_1d) < 4:
            log.warning("[cs] Not enough daily bars")
            return result

        c1 = df_1d.iloc[-3]
        c2 = df_1d.iloc[-2]
        result["c1_dir"] = "bull" if c1["close"] > c1["open"] else "bear"
        result["c2_dir"] = "bull" if c2["close"] > c2["open"] else "bear"
        result["pattern_desc"] = f"C1={result['c1_dir']} C2={result['c2_dir']}"
    except Exception as e:
        log.warning("[cs] Could not read 1d parquet: %s", e)
        return result

    # ── Call CandleScienceService ──
    try:
        from api.features.candle_science.service import CandleScienceService

        # Build auto-detect filters from the last 2 candles
        filters = {
            "c1_direction": result["c1_dir"],
            "c2_direction": result["c2_dir"],
            # Additional structural filters can be added here
            # The service will match historical triplets with the same C1/C2 direction
        }

        stats = CandleScienceService.calculate_stats(ticker, "1d", filters)
        if not stats or stats.get("error"):
            log.warning("[cs] Service returned error: %s", stats.get("error", "unknown"))
            return result

        # Extract probabilities
        sample = stats.get("sample_count", 0)
        result["n_matches"] = sample

        if sample > 0:
            bull_pct = stats.get("c3_bull_pct", 50.0)
            bear_pct = stats.get("c3_bear_pct", 50.0)
            result["p_bull"] = round(bull_pct, 1)
            result["p_bear"] = round(bear_pct, 1)
            result["edge"] = round(abs(bull_pct - bear_pct), 1)

            # MFE/MAE percentiles (the real value)
            mfe_data = stats.get("mfe", {})
            mae_data = stats.get("mae", {})
            pcts = cs_cfg.get("mfe_percentiles", [30, 50, 70])

            result["mfe"] = {f"p{p}": mfe_data.get(f"p{p}") for p in pcts if mfe_data.get(f"p{p}") is not None}
            result["mae"] = {f"p{p}": mae_data.get(f"p{p}") for p in pcts if mae_data.get(f"p{p}") is not None}

            # R:R envelope
            mfe_median = result["mfe"].get("p50")
            mae_median = result["mae"].get("p50")
            if mfe_median and mae_median and mae_median != 0:
                result["rr_envelope"] = round(abs(mfe_median / mae_median), 2)

    except Exception as e:
        log.warning("[cs] CandleScienceService error: %s", e)

    return result


def format_candle_science_block(data: dict) -> str:
    lines = ["== CANDLE SCIENCE (C1→C2→C3) =="]
    lines.append(f"Pattern: {data['pattern_desc']} | n={data['n_matches']} matches")
    lines.append(f"P(C3 Bull): {data['p_bull']}% | P(C3 Bear): {data['p_bear']}% | Edge: +{data['edge']}%")
    if data["mfe"]:
        mfe_str = " | ".join(f"{k}={v:+.2f}%" for k, v in data["mfe"].items())
        lines.append(f"MFE: {mfe_str}")
    if data["mae"]:
        mae_str = " | ".join(f"{k}={v:+.2f}%" for k, v in data["mae"].items())
        lines.append(f"MAE: {mae_str}")
    if data["rr_envelope"]:
        lines.append(f"R:R envelope: {data['rr_envelope']}x (median MFE/MAE)")
    return "\n".join(lines)