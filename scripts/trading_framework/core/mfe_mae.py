"""
Vectorized MFE/MAE analysis logic.

Performance Principles:
- Use pandas rolling().max()/.min() shifts for forward-looking windows.
- No Python loops in calculation.
- Memory: use float32 for large datasets.
"""
from dataclasses import dataclass, field
import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Optional
from scripts.trading_framework.config.config_loader import AppConfig

logger = logging.getLogger(__name__)


@dataclass
class MfeMaeResult:
    """Rich per-signal MFE/MAE analysis result."""

    signal_time: pd.Timestamp
    direction: str
    entry_price: float
    stop_price: float
    risk_points: float

    mfe_points: list[float] = field(default_factory=list)
    mae_points: list[float] = field(default_factory=list)

    mfe_atr: list[float] = field(default_factory=list)
    mae_atr: list[float] = field(default_factory=list)
    mfe_pct: list[float] = field(default_factory=list)
    mae_pct: list[float] = field(default_factory=list)

    forward_returns: Dict[int, float] = field(default_factory=dict)
    forward_returns_pct: Dict[int, float] = field(default_factory=dict)

    reached_1r: bool = False
    reached_2r: bool = False
    reached_3r: bool = False
    time_to_1r: Optional[int] = None
    time_to_2r: Optional[int] = None
    time_to_3r: Optional[int] = None

    mfe_peak_bar: int = 0
    mae_trough_bar: int = 0

    path: list[float] = field(default_factory=list)
    atr_at_entry: float = 0.0


def compute_mfe_mae(
    df: pd.DataFrame, 
    signal_col: str, 
    horizons: List[int], 
    atr_col: str = "atr_14"
) -> pd.DataFrame:
    """
    Calculate MFE and MAE for all signals in the DataFrame.

    MFE = Maximum Favorable Excursion
    MAE = Maximum Adverse Excursion

    Args:
        df: Enriched DataFrame containing price (high, low, close), signal, and ATR.
            Signal column should have 1 for Long, -1 for Short, 0 otherwise.
        signal_col: Name of the column containing signals.
        horizons: List of forward horizons in bars (e.g. [5, 15, 30, 60, 120]).
        atr_col: Name of the ATR column for normalization.

    Returns:
        DataFrame containing only the signal bars, with additional MFE/MAE 
        columns for each horizon (e.g., 'mfe_15', 'mae_15').
    """
    # 1. Isolate signals
    signals = df[df[signal_col] != 0].copy()
    if signals.empty:
        return signals

    # 2. Extract price components to float32 for speed/memory
    high = df["high"].astype(np.float32)
    low = df["low"].astype(np.float32)
    close = df["close"].astype(np.float32)

    # 3. For each horizon, compute the max/min looking AHEAD
    for h in horizons:
        # High-water mark for the next H bars (including current bar's close as potential start)
        # rolling(h).max().shift(-h) gives the max of the NEXT h bars.
        # e.g., for h=5 at time T, we get max(T, T+1, T+2, T+3, T+4)
        # Use 'min_periods=1' to handle end-of-data tapering.
        fwd_high = high.rolling(window=h, min_periods=1).max().shift(-h+1)
        fwd_low  = low.rolling(window=h, min_periods=1).min().shift(-h+1)
        
        # Pull these back to the signal bars
        sig_fwd_high = fwd_high.reindex(signals.index)
        sig_fwd_low  = fwd_low.reindex(signals.index)
        sig_entry    = signals["close"].astype(np.float32) # Assume entry on signal bar close
        sig_atr      = signals[atr_col].astype(np.float32)

        # 4. Long vs Short Logic
        long_mask = signals[signal_col] == 1
        short_mask = signals[signal_col] == -1

        mfe = pd.Series(np.nan, index=signals.index, dtype=np.float32)
        mae = pd.Series(np.nan, index=signals.index, dtype=np.float32)

        # Longs: MFE is (MaxHigh - Entry) / ATR, MAE is (MinLow - Entry) / ATR
        mfe.loc[long_mask] = ((sig_fwd_high.loc[long_mask] - sig_entry.loc[long_mask]) / sig_atr.loc[long_mask]).astype(np.float32)
        mae.loc[long_mask] = ((sig_fwd_low.loc[long_mask] - sig_entry.loc[long_mask]) / sig_atr.loc[long_mask]).astype(np.float32)

        # Shorts: MFE is (Entry - MinLow) / ATR, MAE is (Entry - MaxHigh) / ATR
        mfe.loc[short_mask] = ((sig_entry.loc[short_mask] - sig_fwd_low.loc[short_mask]) / sig_atr.loc[short_mask]).astype(np.float32)
        mae.loc[short_mask] = ((sig_entry.loc[short_mask] - sig_fwd_high.loc[short_mask]) / sig_atr.loc[short_mask]).astype(np.float32)

        signals[f"mfe_{h}"] = mfe
        signals[f"mae_{h}"] = mae

    # Clean up any potential divide-by-zero or NaNs
    signals = signals.replace([np.inf, -np.inf], np.nan)
    
    logger.debug("Computed MFE/MAE for %d signals across %d horizons", len(signals), len(horizons))
    return signals


def compute_mfe_mae_rich(
    df: pd.DataFrame,
    signals: pd.DataFrame,
    max_forward_bars: int = 120,
    horizons: Optional[list[int]] = None,
    atr_col: str = "atr_14",
) -> list[MfeMaeResult]:
    """Compute rich MFE/MAE analysis for each signal."""
    if horizons is None:
        horizons = [5, 15, 30, 60, 120]

    if signals is None or signals.empty:
        return []

    df = df.sort_index()
    index_map = {ts: i for i, ts in enumerate(df.index)}

    results: list[MfeMaeResult] = []

    for _, sig_row in signals.iterrows():
        sig_time = pd.Timestamp(sig_row["signal_time"])
        direction = str(sig_row["direction"]).lower()
        entry_price = float(sig_row["entry_price"])
        stop_price = float(sig_row["stop_price"])
        risk_points = abs(entry_price - stop_price)

        if sig_time in index_map:
            start_idx = index_map[sig_time]
        else:
            start_idx = df.index.get_indexer([sig_time], method="bfill")[0]
            if start_idx < 0 or start_idx >= len(df):
                continue

        atr_at_entry = float(df.iloc[start_idx][atr_col]) if atr_col in df.columns else 1.0
        if pd.isna(atr_at_entry) or atr_at_entry <= 0:
            atr_at_entry = 1.0

        end_idx = min(start_idx + max_forward_bars, len(df) - 1)
        forward_bars = df.iloc[start_idx + 1 : end_idx + 1]
        if forward_bars.empty:
            continue

        highs = forward_bars["high"].astype(float).values
        lows = forward_bars["low"].astype(float).values
        closes = forward_bars["close"].astype(float).values

        path = closes.tolist()
        n_bars = len(path)

        if direction == "long":
            inst_favorable = highs - entry_price
            inst_adverse = entry_price - lows
        else:
            inst_favorable = entry_price - lows
            inst_adverse = highs - entry_price

        inst_favorable = np.maximum(inst_favorable, 0.0)
        inst_adverse = np.maximum(inst_adverse, 0.0)

        cum_mfe = np.maximum.accumulate(inst_favorable).astype(float).tolist()
        cum_mae = np.maximum.accumulate(inst_adverse).astype(float).tolist()

        mfe_atr = [m / atr_at_entry for m in cum_mfe]
        mae_atr = [m / atr_at_entry for m in cum_mae]
        mfe_pct = [m / entry_price * 100.0 for m in cum_mfe]
        mae_pct = [m / entry_price * 100.0 for m in cum_mae]

        reached_1r = False
        reached_2r = False
        reached_3r = False
        time_to_1r = None
        time_to_2r = None
        time_to_3r = None

        if risk_points > 0:
            for bar_i, mfe_val in enumerate(cum_mfe):
                r_mult = mfe_val / risk_points
                if not reached_1r and r_mult >= 1.0:
                    reached_1r = True
                    time_to_1r = bar_i + 1
                if not reached_2r and r_mult >= 2.0:
                    reached_2r = True
                    time_to_2r = bar_i + 1
                if not reached_3r and r_mult >= 3.0:
                    reached_3r = True
                    time_to_3r = bar_i + 1

        mfe_peak_bar = int(np.argmax(cum_mfe)) if cum_mfe else 0
        mae_trough_bar = int(np.argmax(cum_mae)) if cum_mae else 0

        forward_returns: Dict[int, float] = {}
        forward_returns_pct: Dict[int, float] = {}

        for h in horizons:
            if h <= n_bars:
                ret_price = closes[h - 1]
                if direction == "long":
                    ret = ret_price - entry_price
                else:
                    ret = entry_price - ret_price
                forward_returns[h] = float(ret)
                forward_returns_pct[h] = float(ret / entry_price * 100.0)
            else:
                forward_returns[h] = float("nan")
                forward_returns_pct[h] = float("nan")

        results.append(
            MfeMaeResult(
                signal_time=sig_time,
                direction=direction,
                entry_price=entry_price,
                stop_price=stop_price,
                risk_points=risk_points,
                mfe_points=cum_mfe,
                mae_points=cum_mae,
                mfe_atr=mfe_atr,
                mae_atr=mae_atr,
                mfe_pct=mfe_pct,
                mae_pct=mae_pct,
                forward_returns=forward_returns,
                forward_returns_pct=forward_returns_pct,
                reached_1r=reached_1r,
                reached_2r=reached_2r,
                reached_3r=reached_3r,
                time_to_1r=time_to_1r,
                time_to_2r=time_to_2r,
                time_to_3r=time_to_3r,
                mfe_peak_bar=mfe_peak_bar,
                mae_trough_bar=mae_trough_bar,
                path=path,
                atr_at_entry=atr_at_entry,
            )
        )

    return results


def summarize_mfe_mae_rich(results: list[MfeMaeResult]) -> dict:
    """Aggregate statistics across rich per-signal MFE/MAE results."""
    if not results:
        return {}

    peak_mfe = [r.mfe_points[-1] if r.mfe_points else 0.0 for r in results]
    peak_mae = [r.mae_points[-1] if r.mae_points else 0.0 for r in results]
    peak_mfe_pct = [r.mfe_pct[-1] if r.mfe_pct else 0.0 for r in results]
    peak_mae_pct = [r.mae_pct[-1] if r.mae_pct else 0.0 for r in results]
    peak_mfe_atr = [r.mfe_atr[-1] if r.mfe_atr else 0.0 for r in results]
    peak_mae_atr = [r.mae_atr[-1] if r.mae_atr else 0.0 for r in results]

    summary: dict = {"total_signals": len(results)}

    def add_pctiles(prefix: str, data: list[float]) -> None:
        for p in [10, 25, 50, 75, 90]:
            summary[f"{prefix}_p{p}"] = float(np.percentile(data, p))

    add_pctiles("mfe", peak_mfe)
    add_pctiles("mae", peak_mae)
    add_pctiles("mfe_pct", peak_mfe_pct)
    add_pctiles("mae_pct", peak_mae_pct)
    add_pctiles("mfe_atr", peak_mfe_atr)
    add_pctiles("mae_atr", peak_mae_atr)

    summary["pct_reach_1r"] = sum(1 for r in results if r.reached_1r) / len(results)
    summary["pct_reach_2r"] = sum(1 for r in results if r.reached_2r) / len(results)
    summary["pct_reach_3r"] = sum(1 for r in results if r.reached_3r) / len(results)

    times_1r = [r.time_to_1r for r in results if r.time_to_1r is not None]
    times_2r = [r.time_to_2r for r in results if r.time_to_2r is not None]

    summary["avg_time_to_1r"] = float(np.mean(times_1r)) if times_1r else None
    summary["median_time_to_1r"] = float(np.median(times_1r)) if times_1r else None
    summary["avg_time_to_2r"] = float(np.mean(times_2r)) if times_2r else None
    summary["median_time_to_2r"] = float(np.median(times_2r)) if times_2r else None

    winners_2r = [r for r in results if r.reached_2r]
    if winners_2r:
        w_mae = [r.mae_points[-1] if r.mae_points else 0.0 for r in winners_2r]
        w_mae_pct = [r.mae_pct[-1] if r.mae_pct else 0.0 for r in winners_2r]
        for p in [50, 75, 90]:
            summary[f"winner_2r_mae_p{p}"] = float(np.percentile(w_mae, p))
            summary[f"winner_2r_mae_pct_p{p}"] = float(np.percentile(w_mae_pct, p))

    atrs_at_entry = [r.atr_at_entry for r in results if r.atr_at_entry > 0]
    if atrs_at_entry:
        best_score = -1.0
        best_stop_atr = 1.0

        for stop_mult in np.arange(0.5, 5.25, 0.25):
            survivors = []
            for r in results:
                stop_level = float(stop_mult) * max(r.atr_at_entry, 0.0)
                peak_mae_for_signal = r.mae_points[-1] if r.mae_points else 0.0
                if peak_mae_for_signal < stop_level:
                    peak_mfe_for_signal = r.mfe_points[-1] if r.mfe_points else 0.0
                    survivors.append(peak_mfe_for_signal)

            if survivors:
                score = len(survivors) * float(np.mean(survivors))
                if score > best_score:
                    best_score = score
                    best_stop_atr = float(stop_mult)

        avg_atr = float(np.mean(atrs_at_entry))
        avg_entry = float(np.mean([r.entry_price for r in results]))
        summary["optimal_stop_atr"] = best_stop_atr
        summary["optimal_stop_points"] = best_stop_atr * avg_atr
        summary["optimal_stop_pct"] = (summary["optimal_stop_points"] / avg_entry) * 100.0 if avg_entry > 0 else 0.0

    return summary
