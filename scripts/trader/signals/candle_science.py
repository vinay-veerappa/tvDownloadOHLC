"""C8: Candle Science auto-detect signal.

Reads last 2 daily candles, builds auto-detect filters (mirroring Pine v17.5
Standard preset), calls CandleScienceService, and reports P(C3 bull/bear),
P(C3H > C2H), P(C3L < C2L), P(C3C > C2C), plus MFE/MAE percentiles.
Supports Open and Close modes (with multi-scenario projection for tomorrow's open).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd
import pytz
from datetime import datetime

log = logging.getLogger(__name__)
_REPO = Path(__file__).parent.parent.parent.parent


def _dir(o: float, c: float) -> str:
    return "bull" if c >= o else "bear"


def _resolve_auto_preset(enabled: list[str]) -> set[str]:
    """Translate Pine-style preset booleans into the set of active dimensions."""
    dims = set()
    if "minimal" in enabled:
        dims |= {"c1_dir", "c2_dir", "c3o_c2h", "c3o_c2l", "c3o_c2c", "c3o_c2o"}
    if "standard" in enabled:
        dims |= {"c2h_c1h", "c2l_c1l", "c2h_c1o", "c2l_c1o", "c2c_c1o", "c2o_c1o"}
    if "detailed" in enabled:
        dims |= {"c2c_c1c", "c2o_c1c"}
    if "full" in enabled:
        dims |= {"c2c_c1h", "c2c_c1l"}
    return dims


def _build_filters_from_candles(
    c1: pd.Series,
    c2: pd.Series,
    c3o_price: float,
    dims: set[str],
) -> dict[str, Any]:
    """Map the selected auto-detect dimensions to service filter keys."""
    filters: dict[str, Any] = {}

    c1_dir = _dir(c1["open"], c1["close"])
    c2_dir = _dir(c2["open"], c2["close"])
    c1_open, c1_high, c1_low, c1_close = c1["open"], c1["high"], c1["low"], c1["close"]
    c2_open, c2_high, c2_low, c2_close = c2["open"], c2["high"], c2["low"], c2["close"]

    if "c1_dir" in dims:
        filters["c1Direction"] = c1_dir
    if "c2_dir" in dims:
        filters["c2Direction"] = c2_dir

    if "c2h_c1h" in dims:
        filters["c2HighVsC1High"] = "above" if c2_high > c1_high else "below"
    if "c2h_c1o" in dims:
        filters["c2HighVsC1Open"] = "above" if c2_high > c1_open else "below"
    if "c2l_c1l" in dims:
        filters["c2LowVsC1Low"] = "above" if c2_low > c1_low else "below"
    if "c2l_c1o" in dims:
        filters["c2LowVsC1Open"] = "above" if c2_low > c1_open else "below"
    if "c2c_c1h" in dims:
        filters["c2CloseVsC1High"] = "above" if c2_close > c1_high else "below"
    if "c2c_c1l" in dims:
        filters["c2CloseVsC1Low"] = "above" if c2_close > c1_low else "below"
    if "c2c_c1c" in dims:
        filters["c2CloseVsC1Close"] = "above" if c2_close > c1_close else "below"
    if "c2c_c1o" in dims:
        filters["c2CloseVsC1Open"] = "above" if c2_close > c1_open else "below"
    if "c2o_c1c" in dims:
        filters["c2OpenVsC1Close"] = "above" if c2_open > c1_close else "below"
    if "c2o_c1o" in dims:
        filters["c2OpenVsC1Open"] = "above" if c2_open > c1_open else "below"

    if "c3o_c2h" in dims:
        filters["c3OpenVsC2High"] = "above" if c3o_price > c2_high else "below"
    if "c3o_c2l" in dims:
        filters["c3OpenVsC2Low"] = "above" if c3o_price > c2_low else "below"
    if "c3o_c2c" in dims:
        filters["c3OpenVsC2Close"] = "above" if c3o_price > c2_close else "below"
    if "c3o_c2o" in dims:
        filters["c3OpenVsC2Open"] = "above" if c3o_price > c2_open else "below"

    return filters


def _process_stats_endpoint(
    ticker: str,
    c1: pd.Series,
    c2: pd.Series,
    c3o_price: float,
    active_dims: set[str],
    pcts_mfe: list[int],
    pcts_mae: list[int],
) -> dict:
    """Helper to call CandleScienceService and construct statistics for a single open price."""
    from api.features.candle_science.service import CandleScienceService

    res = {
        "n_matches": 0,
        "p_bull": 50.0, "p_bear": 50.0,
        "p_break_high": None, "p_break_low": None,
        "p_close_gt_c2c": None,
        "edge": 0.0,
        "mfe": {}, "mae": {},
        "rr_envelope": None,
    }

    try:
        filters = _build_filters_from_candles(c1, c2, c3o_price, active_dims)
        stats = CandleScienceService.calculate_stats(ticker, "1d", filters)
        if not stats or stats.get("error"):
            return res

        sample = stats.get("sample_count", 0)
        res["n_matches"] = sample
        if sample == 0:
            return res

        # Directional probabilities
        dir3 = stats.get("direction", {}).get("c3", {})
        bull_pct = dir3.get("bull", 50.0)
        bear_pct = dir3.get("bear", 50.0)
        res["p_bull"] = round(bull_pct, 1)
        res["p_bear"] = round(bear_pct, 1)
        res["edge"] = round(abs(bull_pct - bear_pct), 1)

        # Break/containment probabilities
        hw = stats.get("high_wicks", {}).get("c3_vs_c2", {}).get("high_vs_high", {})
        lw = stats.get("low_wicks", {}).get("c3_vs_c2", {}).get("low_vs_low", {})
        cb = stats.get("body", {}).get("c3_vs_c2", {}).get("close_vs_close", {})
        res["p_break_high"] = hw.get("above")
        res["p_break_low"] = lw.get("below")
        res["p_close_gt_c2c"] = cb.get("above")

        # MFE/MAE percentiles
        dist = stats.get("distributions", {})
        res["mfe"] = _extract_percentiles(
            dist.get("c3_high_vs_c2_open", []), pcts_mfe, direction="positive"
        )
        res["mae"] = _extract_percentiles(
            dist.get("c3_low_vs_c2_open", []), pcts_mae, direction="negative"
        )

        # Fallback to C2H/C2L base comparison if O-based is empty
        if not res["mfe"]:
            res["mfe"] = _extract_percentiles(
                dist.get("c3_high_vs_c2_high", []), pcts_mfe, direction="positive"
            )
        if not res["mae"]:
            res["mae"] = _extract_percentiles(
                dist.get("c3_low_vs_c2_low", []), pcts_mae, direction="negative"
            )

        # R:R envelope
        mfe_median = res["mfe"].get("p50")
        mae_median = res["mae"].get("p50")
        if mfe_median is not None and mae_median is not None and mae_median != 0:
            res["rr_envelope"] = round(abs(mfe_median / mae_median), 2)

    except Exception as e:
        log.warning("[cs] Scenario processing failed: %s", e)

    return res


def get_candle_science_read(ticker: str = "NQ1", mode: str = "open", target_date: str | None = None) -> dict:
    """Get Candle Science C1→C2→C3 pattern match.

    Returns:
        For open mode: Dict with pattern details + probabilities/MFE/MAE
        For close mode: Dict with scenarios dictionary containing separate runs.
    """
    from scripts.trader.config_loader import get_config
    cfg = get_config()
    cs_cfg = cfg["candle_science"]
    auto_preset = str(cs_cfg.get("auto_preset", "standard")).lower()
    active_dims = _resolve_auto_preset([auto_preset])
    pcts_mfe = cs_cfg.get("mfe_percentiles", [30, 50, 70])
    pcts_mae = cs_cfg.get("mae_percentiles", [30, 50, 70])

    result = {
        "mode": mode,
        "c1_dir": "N/A", "c2_dir": "N/A",
        "pattern_desc": "N/A",
        "preset": auto_preset,
        "active_dims": sorted(active_dims),
        "n_matches": 0,
        "p_bull": 50.0, "p_bear": 50.0,
        "p_break_high": None, "p_break_low": None,
        "p_close_gt_c2c": None,
        "edge": 0.0,
        "mfe": {}, "mae": {},
        "rr_envelope": None,
        "scenarios": {},
    }

    # ── Read daily candles and align dates ──
    try:
        df_1d = pd.read_parquet(_REPO / "data" / f"{ticker}_1d.parquet")
        if df_1d.index.tz is not None:
            df_1d.index = df_1d.index.tz_convert("US/Eastern")
        else:
            df_1d.index = df_1d.index.tz_localize("UTC").tz_convert("US/Eastern")

        if target_date:
            t_dt = pd.to_datetime(target_date).date()
            df_1d = df_1d[df_1d.index.date <= t_dt]

        if len(df_1d) < 4:
            log.warning("[cs] Not enough daily bars")
            return result

        last_bar_date = df_1d.index[-1].date()
        today_et = datetime.now(pytz.timezone("America/New_York")).date()

        # Date Alignment Check
        if last_bar_date == today_et:
            if mode == "open":
                # Today's active bar is already in the file; ignore it to predict today
                c1 = df_1d.iloc[-3]
                c2 = df_1d.iloc[-2]
            else:
                # Close mode: Today's completed bar is in the file; predict tomorrow
                c1 = df_1d.iloc[-2]
                c2 = df_1d.iloc[-1]
        else:
            # Last bar in the file represents yesterday (or older)
            if mode == "open":
                # Predict today using yesterday and two days ago
                c1 = df_1d.iloc[-2]
                c2 = df_1d.iloc[-1]
            else:
                # Close mode: but today's completed bar is not yet written to the file
                log.warning(f"[cs] Close mode run, but today's bar ({today_et}) is missing from daily parquet. Last is {last_bar_date}.")
                c1 = df_1d.iloc[-2]
                c2 = df_1d.iloc[-1]

        result["c1_dir"] = _dir(c1["open"], c1["close"])
        result["c2_dir"] = _dir(c2["open"], c2["close"])
        result["pattern_desc"] = f"C1={result['c1_dir']} C2={result['c2_dir']}"

    except Exception as e:
        log.warning("[cs] Parquet load failed: %s", e)
        return result

    # ── Process based on Mode ──
    if mode == "close":
        # Predict tomorrow's candle (C3) by evaluating different scenarios for tomorrow's open price
        # Target scenarios: Gap Up (+10 pts above high), Inside (at close), Gap Down (-10 pts below low)
        scenarios = {
            "Gap Up (opens above today's High)": c2["high"] + 10.0,
            "Flat / Inside (opens at today's Close)": c2["close"],
            "Gap Down (opens below today's Low)": c2["low"] - 10.0,
        }
        for name, open_price in scenarios.items():
            sc_res = _process_stats_endpoint(
                ticker, c1, c2, open_price, active_dims, pcts_mfe, pcts_mae
            )
            result["scenarios"][name] = sc_res
    else:
        # Open mode: Predict today's candle (C3). Use yesterday's close as the open price proxy.
        c3o_price = c2["close"]
        res = _process_stats_endpoint(
            ticker, c1, c2, c3o_price, active_dims, pcts_mfe, pcts_mae
        )
        result.update(res)

    return result


def _extract_percentiles(values: list[float] | None, pcts: list[int], direction: str) -> dict[str, float | None]:
    """Return {pX: value} for selected percentiles from a distribution list."""
    if not values:
        return {}
    s = pd.Series(values, dtype=float).dropna()
    if s.empty:
        return {}
    if direction == "positive":
        s = s[s > 0]
    elif direction == "negative":
        s = s[s < 0]
    if s.empty:
        return {}
    return {f"p{p}": round(float(s.quantile(p / 100.0)), 2) for p in pcts}


def format_candle_science_block(data: dict) -> str:
    if not data or (data.get("mode") == "open" and data.get("n_matches", 0) == 0):
        return "== CANDLE SCIENCE ==\nNo pattern match available"

    if data.get("mode") == "close":
        lines = ["== CANDLE SCIENCE (EOD Review / Tomorrow's Setup) =="]
        lines.append(f"C1: {data['c1_dir']} | C2: {data['c2_dir']} | Pattern: {data['pattern_desc']}")
        lines.append("SCENARIOS FOR TOMORROW'S OPEN:")

        for name, sc in data.get("scenarios", {}).items():
            lines.append(f"\n  ➤ {name}:")
            if not sc or sc.get("n_matches", 0) == 0:
                lines.append("    No pattern matches found for this scenario.")
                continue
            lines.append(
                f"    P(C3 Bull): {sc['p_bull']}% | P(C3 Bear): {sc['p_bear']}% "
                f"| n={sc['n_matches']} | edge={sc['edge']}%"
            )
            if sc.get("p_break_high") is not None or sc.get("p_break_low") is not None:
                lines.append(
                    f"    P(C3H>C2H): {sc.get('p_break_high', '?')}% | "
                    f"P(C3L<C2L): {sc.get('p_break_low', '?')}% | "
                    f"P(C3C>C2C): {sc.get('p_close_gt_c2c', '?')}%"
                )
            if sc["mfe"]:
                mfe_str = " | ".join(f"{k}={v:+.2f}%" for k, v in sc["mfe"].items())
                lines.append(f"    MFE: {mfe_str}")
            if sc["mae"]:
                mae_str = " | ".join(f"{k}={v:+.2f}%" for k, v in sc["mae"].items())
                lines.append(f"    MAE: {mae_str}")
            if sc["rr_envelope"]:
                lines.append(f"    R:R envelope: {sc['rr_envelope']}x (median MFE/MAE)")
        return "\n".join(lines)
    else:
        # Open Mode Format
        lines = ["== CANDLE SCIENCE (C1→C2→C3) =="]
        preset = data.get("preset", "standard")
        lines.append(
            f"C1: {data['c1_dir']} | C2: {data['c2_dir']} | Preset: {preset} "
            f"| Active dims: {len(data.get('active_dims', []))}"
        )
        lines.append(
            f"P(C3 Bull): {data['p_bull']}% | P(C3 Bear): {data['p_bear']}% "
            f"| n={data['n_matches']} | edge={data['edge']}%"
        )
        if data.get("p_break_high") is not None or data.get("p_break_low") is not None:
            lines.append(
                f"P(C3H>C2H): {data.get('p_break_high', '?')}% | "
                f"P(C3L<C2L): {data.get('p_break_low', '?')}% | "
                f"P(C3C>C2C): {data.get('p_close_gt_c2c', '?')}%"
            )
        if data["mfe"]:
            mfe_str = " | ".join(f"{k}={v:+.2f}%" for k, v in data["mfe"].items())
            lines.append(f"MFE: {mfe_str}")
        if data["mae"]:
            mae_str = " | ".join(f"{k}={v:+.2f}%" for k, v in data["mae"].items())
            lines.append(f"MAE: {mae_str}")
        if data["rr_envelope"]:
            lines.append(f"R:R envelope: {data['rr_envelope']}x (median MFE/MAE)")
        return "\n".join(lines)