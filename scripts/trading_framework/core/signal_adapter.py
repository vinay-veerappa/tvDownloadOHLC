import os
import numpy as np
import pandas as pd
from pathlib import Path
import logging

# VIX buckets for regimes
VIX_REGIMES = [
    (0, 13, "Low"),
    (13, 20, "Normal"),
    (20, 30, "Elevated"),
    (30, 100, "High")
]

VVIX_REGIMES = [
    (0, 80, "Low"),
    (80, 110, "Normal"),
    (110, 140, "Elevated"),
    (140, 500, "High")
]

logger = logging.getLogger(__name__)

def _get_regime(val, buckets):
    if pd.isna(val): return "Unknown"
    for low, high, label in buckets:
        if low <= val < high:
            return label
    return "Extreme"

def _load_vix_context() -> pd.DataFrame:
    """Load and prepare VIX/VVIX daily context."""
    # Resolve project root relative to this file: scripts/trading_framework/core/signal_adapter.py
    root = Path(__file__).resolve().parents[3]
    vix_path = root / "data" / "VIX_1d.parquet"
    vvix_path = root / "data" / "VVIX_1d.parquet"
    
    if not vix_path.exists():
        return pd.DataFrame()
        
    vix_df = pd.read_parquet(vix_path)
    # Ensure index is datetime and normalized to UTC for comparison
    vix_df.index = pd.to_datetime(vix_df.index).tz_localize(None)
    vix_df = vix_df.rename(columns={"close": "vix_daily"})
    
    # Compute VIX regimes
    vix_df["vix_regime"] = vix_df["vix_daily"].apply(lambda x: _get_regime(x, VIX_REGIMES))
    
    if vvix_path.exists():
        vvix_df = pd.read_parquet(vvix_path)
        vvix_df.index = pd.to_datetime(vvix_df.index).tz_localize(None)
        vix_df["vvix_level"] = vvix_df["close"]
        vix_df["vvix_regime"] = vix_df["vvix_level"].apply(lambda x: _get_regime(x, VVIX_REGIMES))
    else:
        vix_df["vvix_regime"] = "Unknown"
        
    # Return vvix_level as well
    cols = ["vix_daily", "vix_regime", "vvix_level", "vvix_regime"]
    for col in cols:
        if col not in vix_df.columns:
            vix_df[col] = np.nan
    return vix_df[cols].sort_index()


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _load_daily_context(symbol: str) -> pd.DataFrame:
    """Load daily_context_{symbol}.parquet with event/day metadata for signal enrichment."""
    path = _repo_root() / "data" / "derived" / f"daily_context_{symbol}.parquet"
    if not path.exists():
        return pd.DataFrame()

    cols = ["trading_date", "day_of_week", "event_type"]
    df = pd.read_parquet(path)
    keep = [c for c in cols if c in df.columns]
    if not keep:
        return pd.DataFrame()

    out = df[keep].copy()
    out["trading_date"] = pd.to_datetime(out["trading_date"]).dt.date
    return out.drop_duplicates(subset=["trading_date"]).sort_values("trading_date")


def _load_range_first_boundary() -> pd.DataFrame:
    """Load per-day range first-break context from range_records.parquet."""
    path = _repo_root() / "data" / "derived" / "range_records.parquet"
    if not path.exists():
        return pd.DataFrame()

    need = ["symbol", "trading_date", "range_name", "first_boundary_broken"]
    df = pd.read_parquet(path)
    keep = [c for c in need if c in df.columns]
    if len(keep) < 4:
        return pd.DataFrame()

    out = df[need].copy()
    out["trading_date"] = pd.to_datetime(out["trading_date"]).dt.date
    return out.sort_values(["symbol", "trading_date", "range_name"])


def enrich_signals(
    signals: pd.DataFrame,
    df: pd.DataFrame,
    strategy_name: str,
    symbol: str,
    point_value: float = 50.0,
    contracts: int = 1,
    chop_score_col: str = "chop_score",
    chop_regime_col: str = "chop_regime",
    session_block_col: str = "session_block",
    vwap_distance_col: str = "vwap_distance_atr",
    chop_vwap_flag_col: str = "chop_vwap_flag",
) -> pd.DataFrame:
    """Enrich strategy signal DataFrame with full schema fields."""
    if signals is None or len(signals) == 0:
        return signals

    enriched = signals.copy()

    enriched["strategy_name"] = strategy_name
    enriched["symbol"] = symbol

    enriched["risk_points"] = (enriched["entry_price"] - enriched["stop_price"]).abs()
    enriched["risk_pct"] = (enriched["risk_points"] / enriched["entry_price"]) * 100.0
    enriched["risk_dollars"] = enriched["risk_points"] * point_value * contracts

    context_cols = {
        "context_chop_score": chop_score_col,
        "context_chop_regime": chop_regime_col,
        "context_session_block": session_block_col,
        "context_vwap_distance": vwap_distance_col,
        "context_chop_vwap_flag": chop_vwap_flag_col,
        "context_day_of_week": "day_of_week",
        "context_event_type": "event_type",
        "context_first_boundary_broken": "first_boundary_broken",
        "context_vix_regime": "vix_regime",
        "context_vix_level": "vix_daily",
        "context_vvix_regime": "vvix_regime",
        "context_vvix_level": "vvix_level",
    }
    # Load VIX context
    vix_context = _load_vix_context()

    # 1. Enrich from technical df (intraday indicators)
    # Ensure signal_time is datetime and matches df.index timezone
    enriched["signal_time"] = pd.to_datetime(enriched["signal_time"])
    if df.index.tz is not None:
        if enriched["signal_time"].dt.tz is None:
            # Assume UTC if naive, then convert
            enriched["signal_time"] = enriched["signal_time"].dt.tz_localize("UTC").dt.tz_convert(df.index.tz)
        else:
            enriched["signal_time"] = enriched["signal_time"].dt.tz_convert(df.index.tz)

    # Convert indexes to a common format for merge_asof
    enriched = enriched.sort_values("signal_time")
    enriched["trading_date"] = pd.to_datetime(enriched["signal_time"]).dt.tz_localize(None).dt.date
    enriched["context_day_of_week"] = pd.to_datetime(enriched["signal_time"]).dt.weekday
    
    # Inverting the mapping since tech_df needs original column names from df
    # src_col: chop_score, new_col: context_chop_score
    valid_tech_cols = {src_col: new_col for new_col, src_col in context_cols.items() 
                       if src_col in df.columns and src_col not in ["vix_regime", "vix_daily", "vvix_regime", "vvix_level"]}
    
    if valid_tech_cols:
        # Select only the relevant SOURCE columns from df for the merge
        src_cols = list(valid_tech_cols.keys())
        tech_df = df[src_cols].copy()
        # Ensure tech_df is sorted for merge_asof
        tech_df = tech_df.sort_index()
        
        # Vectorized backward merge (as-of join)
        # We merge onto enriched based on signal_time <= df.index
        enriched = pd.merge_asof(
            enriched,
            tech_df.rename(columns=valid_tech_cols),
            left_on="signal_time",
            right_index=True,
            direction="backward"
        )
    else:
        logger.warning(f"No technical context columns ({list(context_cols.values())}) found in df. Using available: {df.columns.tolist()[:5]}...")

    # 1b. Enrich from daily_context_{symbol} (event_type + canonical day_of_week)
    daily_ctx = _load_daily_context(symbol)
    if not daily_ctx.empty:
        enriched = enriched.merge(daily_ctx, on="trading_date", how="left", suffixes=("", "_daily"))
        if "day_of_week" in enriched.columns:
            enriched["context_day_of_week"] = pd.to_numeric(
                enriched["day_of_week"], errors="coerce"
            ).fillna(enriched["context_day_of_week"])
            enriched = enriched.drop(columns=["day_of_week"])
        if "event_type" in enriched.columns:
            enriched["context_event_type"] = enriched["event_type"]
            enriched = enriched.drop(columns=["event_type"])

    # 1c. Enrich ORB/IB signals with first_boundary_broken from range_records
    is_orb_ib = ("ORB" in strategy_name.upper()) or ("IB" in strategy_name.upper())
    if is_orb_ib:
        range_ctx = _load_range_first_boundary()
        if not range_ctx.empty:
            if "range_name" in enriched.columns:
                enriched = enriched.merge(
                    range_ctx,
                    on=["symbol", "trading_date", "range_name"],
                    how="left",
                )
            else:
                inferred_range = "IB_60" if "IB" in strategy_name.upper() else "OR_15"
                tmp = enriched.copy()
                tmp["range_name"] = inferred_range
                tmp = tmp.merge(
                    range_ctx,
                    on=["symbol", "trading_date", "range_name"],
                    how="left",
                )
                enriched = tmp.drop(columns=["range_name"])

            if "first_boundary_broken" in enriched.columns:
                enriched["context_first_boundary_broken"] = enriched["first_boundary_broken"].fillna("NONE")
                enriched = enriched.drop(columns=["first_boundary_broken"])

    if "context_first_boundary_broken" not in enriched.columns:
        enriched["context_first_boundary_broken"] = "NONE"

    # 2. Enrich from VIX daily context
    if not vix_context.empty:
        # Convert signal times to naive for asof merge with daily data (which is naive)
        enriched["_sig_time_naive"] = pd.to_datetime(enriched["signal_time"]).dt.tz_localize(None)
        
        # merge_asof requires sorted left and right
        enriched = enriched.sort_values("_sig_time_naive")
        vix_context = vix_context.sort_index()

        enriched = pd.merge_asof(
            enriched,
            vix_context,
            left_on="_sig_time_naive",
            right_index=True,
            direction="backward"
        )
        # Rename VIX columns to match context_cols mapping
        enriched = enriched.rename(columns={
            "vix_daily": "context_vix_level",
            "vix_regime": "context_vix_regime",
            "vvix_regime": "context_vvix_regime",
            "vvix_level": "context_vvix_level"
        })

        if "_sig_time_naive" in enriched.columns:
            enriched = enriched.drop(columns=["_sig_time_naive"])

    # Keep a compact dictionary context for downstream consumers that expect a single object field.
    enriched["context"] = enriched.apply(
        lambda row: {
            "chop_score": row.get("context_chop_score", np.nan),
            "chop_regime": row.get("context_chop_regime", np.nan),
            "session_block": row.get("context_session_block", np.nan),
            "vwap_distance": row.get("context_vwap_distance", np.nan),
            "chop_vwap_flag": row.get("context_chop_vwap_flag", np.nan),
            "day_of_week": row.get("context_day_of_week", np.nan),
            "event_type": row.get("context_event_type", None),
            "first_boundary_broken": row.get("context_first_boundary_broken", "NONE"),
            "vix_regime": row.get("context_vix_regime", None),
            "vix_level": row.get("context_vix_level", None),
            "vvix_regime": row.get("context_vvix_regime", None),
        },
        axis=1,
    )

    return enriched


def split_approved_vetoed(
    signals: pd.DataFrame,
    min_chop_score: int = 2,
    use_vwap_chop_flag: bool = True,
    chop_score_col: str = "context_chop_score",
    chop_vwap_flag_col: str = "context_chop_vwap_flag",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Split enriched signals into approved and vetoed sets with veto reasons.

    Args:
        signals: Enriched signal DataFrame
        min_chop_score: Minimum composite chop score to approve
        use_vwap_chop_flag: Whether to apply the VWAP cross count filter.
            Set to False for strategies that trade VWAP crosses (e.g., vwap_reclaim).
        chop_score_col: Column name for chop score
        chop_vwap_flag_col: Column name for VWAP chop flag

    Returns: (approved_df, vetoed_df)
    """
    if signals is None or len(signals) == 0:
        return signals, signals.iloc[0:0].copy()

    veto_reasons = []
    is_vetoed = []

    for _, row in signals.iterrows():
        reasons = []

        chop = row.get(chop_score_col, np.nan)
        if pd.notna(chop) and chop < min_chop_score:
            reasons.append(f"chop_score_{int(chop)}_below_{min_chop_score}")

        if use_vwap_chop_flag and bool(row.get(chop_vwap_flag_col, False)):
            reasons.append("vwap_chop_flag")

        if reasons:
            veto_reasons.append("; ".join(reasons))
            is_vetoed.append(True)
        else:
            veto_reasons.append(None)
            is_vetoed.append(False)

    out = signals.copy()
    out["veto_reason"] = veto_reasons
    out["is_vetoed"] = is_vetoed

    approved = out[~out["is_vetoed"]].drop(columns=["is_vetoed"])
    vetoed = out[out["is_vetoed"]].drop(columns=["is_vetoed"])

    return approved, vetoed
