"""ICT Features Computation Pipeline
=====================================

Batch-computes ICT (Inner Circle Trader) features from raw OHLC data and
persists them as per-symbol, per-feature-type parquet files under
``data/derived/ICT/``.

This is the canonical derived-data generator for all ICT features. It
uses ``scripts.libs_py.ict_engine`` (the unified library) for all
detection logic — no duplicate implementations.

Output files
------------
::

    data/derived/ICT/
    ├── {sym}_imbalance_{tf}.parquet   — FVG + Volume Imbalance (per-bar, per-TF)
    ├── {sym}_gaps.parquet             — NWOG + NDOG + RTH gaps (per-event)
    ├── {sym}_kz_pivots.parquet        — Killzone pivots AS/LO/NYAM (per-day)
    ├── {sym}_ipda.parquet             — IPDA 20/40/60 ranges (per-day)
    └── {sym}_htf_levels.parquet       — PDH/PDL/PWH/PWL/PMH/PML (per-day)

Usage
-----
::

    # All features, all symbols, incremental
    python -m scripts.context.compute_ict_features

    # Specific symbols and features
    python -m scripts.context.compute_ict_features --symbols NQ1,ES1 --features imbalance,gaps

    # Full rebuild from scratch
    python -m scripts.context.compute_ict_features --full-regen

    # Single feature for one symbol (narrative-triggered refresh)
    python -m scripts.context.compute_ict_features --symbols NQ1 --features kz_pivots --incremental
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd
import numpy as np

_REPO_ROOT = Path(__file__).parent.parent.parent
_DERIVED_DIR = _REPO_ROOT / "data" / "derived"
_ICT_DIR = _DERIVED_DIR / "ICT"

if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.edgeful.lib.data_loader import get_loader
from scripts.libs_py.ict_engine import (
    detect_fvg,
    detect_volume_imbalance,
    detect_opening_gaps,
    detect_rth_gaps,
    detect_gap_fills,
    get_gap_consequent_encroachment,
    detect_htf_levels,
    detect_ipda_ranges,
    get_session_data,
    detect_swings,
    detect_structure_breaks,
    detect_cisd,
    detect_orderblock,
    detect_liquidity,
    detect_smt,
    KILLZONES,
    RTH_SESSIONS,
)
from scripts.libs_py.nqstats.sessions import (
    normalize_to_eastern,
    get_logical_trading_date,
)

logger = logging.getLogger(__name__)

DEFAULT_SYMBOLS = ["NQ1", "ES1", "YM1", "RTY1", "CL1", "GC1"]
ALL_FEATURES = ["imbalance", "gaps", "kz_pivots", "ipda", "htf_levels",
                 "structure", "orderblocks", "liquidity", "smt"]

# Timeframes for imbalance detection (FVG + VI)
IMBALANCE_TIMEFRAMES = {
    "5m": "5min",
    "15m": "15min",
    "1h": "1h",
    "4h": "4h",
}


# ═══════════════════════════════════════════════════════════════════════
#  Imbalance Pipeline (FVG + VI)
# ═══════════════════════════════════════════════════════════════════════

def _imbalance_path(symbol: str, tf: str) -> Path:
    return _ICT_DIR / f"{symbol}_imbalance_{tf}.parquet"


def compute_imbalances(symbol: str, df_1m: pd.DataFrame, tf: str) -> pd.DataFrame:
    """Compute FVG + Volume Imbalance for one symbol at one timeframe.

    Returns only rows where at least one imbalance is detected (~1-2% of bars).
    Schema:
        bar_time, symbol, timeframe, logical_date,
        fvg_type, fvg_top, fvg_bottom, fvg_low, fvg_high, fvg_finalized_time,
        vi_type, vi_top, vi_bottom, vi_finalized_time
    """
    rule = IMBALANCE_TIMEFRAMES[tf]
    df_et = normalize_to_eastern(df_1m)

    # Resample to target TF
    df_rs = (
        df_et[["open", "high", "low", "close"]]
        .resample(rule, origin="start_day")
        .agg({"open": "first", "high": "max", "low": "min", "close": "last"})
        .dropna()
    )

    # Detect FVG and VI using the library
    fvg_df = detect_fvg(df_rs, resample_rule=None)  # already resampled
    vi_df = detect_volume_imbalance(df_rs, resample_rule=None)

    # Merge
    merged = pd.DataFrame(index=df_rs.index)
    merged["fvg_type"] = fvg_df["fvg_type"].values
    merged["fvg_top"] = fvg_df["fvg_top"].values
    merged["fvg_bottom"] = fvg_df["fvg_bottom"].values
    merged["fvg_low"] = fvg_df["fvg_low"].values
    merged["fvg_high"] = fvg_df["fvg_high"].values
    merged["fvg_finalized_time"] = fvg_df["fvg_finalized_time"].values
    merged["vi_type"] = vi_df["vi_type"].values
    merged["vi_top"] = vi_df["vi_top"].values
    merged["vi_bottom"] = vi_df["vi_bottom"].values
    merged["vi_finalized_time"] = vi_df["vi_finalized_time"].values

    # Keep only rows where at least one imbalance exists
    has_imbalance = (merged["fvg_type"] != 0) | (merged["vi_type"] != 0)
    result = merged[has_imbalance].copy()

    result.index.name = "bar_time"
    result.insert(0, "symbol", symbol)
    result["timeframe"] = tf
    result["logical_date"] = get_logical_trading_date(result.index)

    return result


def update_imbalances(symbol: str, tf: str, df_1m_full: pd.DataFrame, full_regen: bool) -> int:
    """Incrementally update or fully rebuild the imbalance parquet for one symbol+TF."""
    out = _imbalance_path(symbol, tf)
    start_date = None

    if not full_regen and out.exists():
        existing = pd.read_parquet(out)
        if not existing.empty:
            last_bar = existing.index.max()
            start_date = (last_bar + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
            logger.info("  [%s] Incremental from %s (%s existing rows)", tf, start_date, f"{len(existing):,}")
    else:
        logger.info("  [%s] Full build from scratch", tf)

    df_1m = df_1m_full
    if start_date:
        df_1m = df_1m[df_1m.index >= pd.to_datetime(start_date)]

    if df_1m.empty:
        logger.info("  [%s] No new bars — up to date", tf)
        return 0

    new_rows = compute_imbalances(symbol, df_1m, tf)
    logger.info("  [%s] %s new imbalance rows", tf, f"{len(new_rows):,}")

    if new_rows.empty:
        return 0

    if out.exists() and not full_regen:
        existing = pd.read_parquet(out)
        combined = pd.concat([existing, new_rows])
        combined = combined[~combined.index.duplicated(keep="last")].sort_index()
    else:
        combined = new_rows.sort_index()

    combined.to_parquet(out)
    logger.info("  [%s] Wrote %s total rows -> %s", tf, f"{len(combined):,}", out.name)
    return len(new_rows)


# ═══════════════════════════════════════════════════════════════════════
#  Gaps Pipeline (NWOG + NDOG + RTH)
# ═══════════════════════════════════════════════════════════════════════

def _gaps_path(symbol: str) -> Path:
    return _ICT_DIR / f"{symbol}_gaps.parquet"


def compute_gaps(symbol: str, df_1m: pd.DataFrame) -> pd.DataFrame:
    """Compute NWOG, NDOG, and RTH gaps with fill tracking.

    Schema:
        session_date, symbol, gap_type, open_time, close_time,
        open_price, close_price, gap_high, gap_low, gap_size, gap_ce,
        filled, fill_time, fill_price
    """
    df_et = normalize_to_eastern(df_1m)

    # Detect opening gaps (NWOG + NDOG)
    opening_gaps = detect_opening_gaps(df_et)
    # Detect RTH gaps
    rth_gaps = detect_rth_gaps(df_et, ticker=symbol)

    # Track fills for both
    opening_fills = detect_gap_fills(df_et, opening_gaps)
    rth_fills = detect_gap_fills(df_et, rth_gaps)

    # Compute consequent encroachment
    opening_ce = get_gap_consequent_encroachment(opening_gaps)
    rth_ce = get_gap_consequent_encroachment(rth_gaps)

    rows = []

    # ── Opening gaps (NWOG + NDOG) ──
    gap_mask = ~opening_gaps["gap_top"].isna()
    for idx in opening_gaps.index[gap_mask]:
        row = opening_gaps.loc[idx]
        fill = opening_fills.loc[idx]
        is_nwog = row["nwog"] == 1
        is_ndog = row["ndog"] == 1
        gap_type = "NWOG" if is_nwog else ("NDOG" if is_ndog else None)
        if gap_type is None:
            continue

        # Find the close bar (previous bar before the gap)
        pos = df_et.index.get_loc(idx)
        if pos > 0:
            close_idx = df_et.index[pos - 1]
            close_price = df_et.loc[close_idx, "close"]
            close_time = close_idx
        else:
            close_price = np.nan
            close_time = pd.NaT

        gap_high = row["gap_top"]
        gap_low = row["gap_bottom"]
        rows.append({
            "session_date": idx.date(),
            "symbol": symbol,
            "gap_type": gap_type,
            "open_time": idx,
            "close_time": close_time,
            "open_price": df_et.loc[idx, "open"],
            "close_price": close_price,
            "gap_high": gap_high,
            "gap_low": gap_low,
            "gap_size": gap_high - gap_low,
            "gap_ce": opening_ce.loc[idx],
            "filled": bool(fill["filled"]),
            "fill_time": fill["fill_time"],
            "fill_price": fill["fill_price"],
        })

    # ── RTH gaps ──
    rth_mask = rth_gaps["rth_gap"] == 1
    for idx in rth_gaps.index[rth_mask]:
        row = rth_gaps.loc[idx]
        fill = rth_fills.loc[idx]
        gap_high = row["gap_top"]
        gap_low = row["gap_bottom"]
        rows.append({
            "session_date": idx.date(),
            "symbol": symbol,
            "gap_type": "RTH_GAP",
            "open_time": idx,
            "close_time": pd.NaT,  # RTH gap close is the prior day close (embedded in calculation)
            "open_price": df_et.loc[idx, "open"],
            "close_price": np.nan,  # Prior day close is embedded in gap calc
            "gap_high": gap_high,
            "gap_low": gap_low,
            "gap_size": gap_high - gap_low,
            "gap_ce": rth_ce.loc[idx],
            "filled": bool(fill["filled"]),
            "fill_time": fill["fill_time"],
            "fill_price": fill["fill_price"],
        })

    if not rows:
        return pd.DataFrame()

    result = pd.DataFrame(rows)
    result = result.sort_values("open_time").reset_index(drop=True)
    return result


def update_gaps(symbol: str, df_1m_full: pd.DataFrame, full_regen: bool) -> int:
    """Incrementally update or fully rebuild the gaps parquet."""
    out = _gaps_path(symbol)
    start_date = None

    if not full_regen and out.exists():
        existing = pd.read_parquet(out)
        if not existing.empty:
            last_open = pd.to_datetime(existing["open_time"]).max()
            start_date = (last_open - pd.Timedelta(days=7)).strftime("%Y-%m-%d")
            logger.info("  [gaps] Incremental from %s (%s existing)", start_date, f"{len(existing):,}")
    else:
        logger.info("  [gaps] Full build from scratch")

    df_1m = df_1m_full
    if start_date:
        df_1m = df_1m[df_1m.index >= pd.to_datetime(start_date)]

    if df_1m.empty:
        logger.info("  [gaps] No new bars — up to date")
        return 0

    new_rows = compute_gaps(symbol, df_1m)
    logger.info("  [gaps] %s new gap events", f"{len(new_rows):,}")

    if new_rows.empty:
        return 0

    if out.exists() and not full_regen:
        existing = pd.read_parquet(out)
        # Deduplicate on (symbol, gap_type, open_time) keeping the newer row (with updated fill status)
        combined = pd.concat([existing, new_rows])
        combined = combined.drop_duplicates(
            subset=["symbol", "gap_type", "open_time"], keep="last"
        ).sort_values("open_time").reset_index(drop=True)
    else:
        combined = new_rows

    combined.to_parquet(out, index=False)
    logger.info("  [gaps] Wrote %s total rows -> %s", f"{len(combined):,}", out.name)

    # Also write backward-compatible JSON for existing consumers
    _write_gaps_json(symbol, combined)
    return len(new_rows)


def _write_gaps_json(symbol: str, gaps_df: pd.DataFrame) -> None:
    """Write backward-compatible ict_nwog_ndog.json for legacy consumers."""
    json_path = _DERIVED_DIR / "ict_nwog_ndog.json"
    existing: dict = {}
    if json_path.exists():
        try:
            import json
            with open(json_path, "r") as f:
                existing = json.load(f)
        except Exception:
            existing = {}

    sym_data = existing.get(symbol, {"NWOG": [], "NDOG": []})

    for _, row in gaps_df.iterrows():
        entry = {
            "session_date": str(row["session_date"]),
            "close_time": row["close_time"].isoformat() if pd.notna(row["close_time"]) else None,
            "open_time": row["open_time"].isoformat() if pd.notna(row["open_time"]) else None,
            "close_price": float(row["close_price"]) if pd.notna(row["close_price"]) else None,
            "open_price": float(row["open_price"]) if pd.notna(row["open_price"]) else None,
            "high": float(row["gap_high"]),
            "low": float(row["gap_low"]),
            "gap_size": float(row["gap_size"]),
        }
        gt = row["gap_type"]
        if gt in ("NWOG", "NDOG"):
            # Replace any existing entry with same session_date
            sym_data[gt] = [e for e in sym_data.get(gt, []) if e.get("session_date") != entry["session_date"]]
            sym_data[gt].append(entry)
            sym_data[gt].sort(key=lambda x: x.get("open_time", ""), reverse=True)

    existing[symbol] = sym_data
    try:
        import json
        with open(json_path, "w") as f:
            json.dump(existing, f, indent=2)
        logger.info("  [gaps] Updated JSON -> %s", json_path.name)
    except Exception as e:
        logger.warning("  [gaps] Failed to write JSON: %s", e)


# ═══════════════════════════════════════════════════════════════════════
#  Killzone Pivots Pipeline
# ═══════════════════════════════════════════════════════════════════════

def _kz_pivots_path(symbol: str) -> Path:
    return _ICT_DIR / f"{symbol}_kz_pivots.parquet"


def compute_kz_pivots(symbol: str, df_1m: pd.DataFrame) -> pd.DataFrame:
    """Compute ICT killzone pivots (AS.H/AS.L, LO.H/LO.L, NYAM.H/NYAM.L).

    Uses the ICT killzone definitions from ict_engine.core.sessions.KILLZONES.
    One row per (symbol, trading_date) with H/L/mid/range for each killzone.
    Fully vectorized — no per-date loops.

    Schema:
        trading_date, symbol,
        asia_high, asia_low, asia_mid, asia_range,
        london_high, london_low, london_mid, london_range,
        nyam_high, nyam_low, nyam_mid, nyam_range
    """
    from datetime import time as dt_time

    df_et = normalize_to_eastern(df_1m)
    # Drop any NaT timestamps
    df_et = df_et[~df_et.index.isna()]
    if df_et.empty:
        return pd.DataFrame()

    # ICT Killzone windows (ET) — from ict_engine.core.sessions.KILLZONES
    kz_windows = {
        "asia":   (dt_time(20, 0), dt_time(0, 0)),   # Asian session 20:00-00:00
        "london": (dt_time(2, 0),  dt_time(5, 0)),    # London KZ 02:00-05:00
        "nyam":   (dt_time(8, 30), dt_time(11, 0)),   # NY AM KZ 08:30-11:00
    }

    logical_dates = get_logical_trading_date(df_et.index)
    times = df_et.index.time
    ld_series = pd.Series(logical_dates.values, index=df_et.index)

    # Build masks and compute per-killzone H/L using groupby (vectorized)
    results = {}
    for prefix, (start_t, end_t) in kz_windows.items():
        if start_t < end_t:
            mask = pd.Series((times >= start_t) & (times < end_t), index=df_et.index)
        else:
            # Overnight wrap (asia 20:00-00:00)
            mask = pd.Series((times >= start_t) | (times < end_t), index=df_et.index)

        if not mask.any():
            continue

        # Filter to active bars and group by logical date
        active_df = df_et.loc[mask, ["high", "low"]].copy()
        active_df["_ld"] = ld_series[mask]

        agg = active_df.groupby("_ld").agg(
            **{f"{prefix}_high": ("high", "max"), f"{prefix}_low": ("low", "min")}
        )
        agg[f"{prefix}_mid"] = (agg[f"{prefix}_high"] + agg[f"{prefix}_low"]) / 2.0
        agg[f"{prefix}_range"] = agg[f"{prefix}_high"] - agg[f"{prefix}_low"]
        results[prefix] = agg

    if not results:
        return pd.DataFrame()

    # Merge all killzone results on logical date index
    merged = None
    for prefix, agg in results.items():
        if merged is None:
            merged = agg
        else:
            merged = merged.join(agg, how="outer")

    # Round and format
    for col in merged.columns:
        merged[col] = merged[col].round(2)

    merged.index.name = "trading_date"
    merged = merged.reset_index()
    merged.insert(1, "symbol", symbol)
    merged = merged.sort_values("trading_date").reset_index(drop=True)

    return merged


def update_kz_pivots(symbol: str, df_1m_full: pd.DataFrame, full_regen: bool) -> int:
    """Incrementally update or fully rebuild the KZ pivots parquet."""
    out = _kz_pivots_path(symbol)
    start_date = None

    if not full_regen and out.exists():
        existing = pd.read_parquet(out)
        if not existing.empty:
            last_date = pd.to_datetime(existing["trading_date"]).max()
            start_date = (last_date - pd.Timedelta(days=3)).strftime("%Y-%m-%d")
            logger.info("  [kz_pivots] Incremental from %s (%s existing)", start_date, f"{len(existing):,}")
    else:
        logger.info("  [kz_pivots] Full build from scratch")

    df_1m = df_1m_full
    if start_date:
        df_1m = df_1m[df_1m.index >= pd.to_datetime(start_date)]

    if df_1m.empty:
        logger.info("  [kz_pivots] No new bars — up to date")
        return 0

    new_rows = compute_kz_pivots(symbol, df_1m)
    logger.info("  [kz_pivots] %s new pivot rows", f"{len(new_rows):,}")

    if new_rows.empty:
        return 0

    if out.exists() and not full_regen:
        existing = pd.read_parquet(out)
        combined = pd.concat([existing, new_rows])
        combined = combined.drop_duplicates(
            subset=["symbol", "trading_date"], keep="last"
        ).sort_values("trading_date").reset_index(drop=True)
    else:
        combined = new_rows

    combined.to_parquet(out, index=False)
    logger.info("  [kz_pivots] Wrote %s total rows -> %s", f"{len(combined):,}", out.name)
    return len(new_rows)


# ═══════════════════════════════════════════════════════════════════════
#  IPDA Pipeline (20/40/60)
# ═══════════════════════════════════════════════════════════════════════

def _ipda_path(symbol: str) -> Path:
    return _ICT_DIR / f"{symbol}_ipda.parquet"


def compute_ipda(symbol: str, df_1d: pd.DataFrame) -> pd.DataFrame:
    """Compute IPDA 20/40/60 rolling ranges from daily data.

    Schema:
        trading_date, symbol,
        ipda20_high, ipda20_low, ipda20_eq, ipda20_pct,
        ipda40_high, ipda40_low, ipda40_eq, ipda40_pct,
        ipda60_high, ipda60_low, ipda60_eq, ipda60_pct
    """
    if df_1d.empty:
        return pd.DataFrame()

    ipda = detect_ipda_ranges(df_1d)

    # Resample to one row per day (take last value of each day)
    ipda_daily = ipda.resample("D").last().dropna(how="all")
    ipda_daily.index.name = "trading_date"

    result = ipda_daily.copy()
    result.insert(0, "symbol", symbol)
    result = result.reset_index()
    result["trading_date"] = pd.to_datetime(result["trading_date"]).dt.date

    return result


def update_ipda(symbol: str, df_1d_full: pd.DataFrame, full_regen: bool) -> int:
    """Full rebuild IPDA parquet (always recomputes from full daily history)."""
    out = _ipda_path(symbol)
    logger.info("  [ipda] Computing from daily data (%s bars)", f"{len(df_1d_full):,}")

    if df_1d_full.empty:
        logger.info("  [ipda] No daily data — skipping")
        return 0

    result = compute_ipda(symbol, df_1d_full)
    if result.empty:
        return 0

    # IPDA is always a full recomputation (cheap on daily data)
    result.to_parquet(out, index=False)
    logger.info("  [ipda] Wrote %s rows -> %s", f"{len(result):,}", out.name)
    return len(result)


# ═══════════════════════════════════════════════════════════════════════
#  HTF Levels Pipeline (PDH/PDL/PWH/PWL/PMH/PML)
# ═══════════════════════════════════════════════════════════════════════

def _htf_levels_path(symbol: str) -> Path:
    return _ICT_DIR / f"{symbol}_htf_levels.parquet"


def compute_htf_levels(symbol: str, df_1d: pd.DataFrame) -> pd.DataFrame:
    """Compute HTF levels (PDH/PDL/PWH/PWL/PMH/PML + mids) from daily data.

    Schema:
        trading_date, symbol,
        pdh, pdl, pdm, pwh, pwl, pwm, pmh, pml, pmm
    """
    if df_1d.empty:
        return pd.DataFrame()

    htf = detect_htf_levels(df_1d)

    # One row per day
    htf_daily = htf.resample("D").last().dropna(how="all")
    htf_daily.index.name = "trading_date"

    result = htf_daily.copy()
    result.insert(0, "symbol", symbol)
    result = result.reset_index()
    result["trading_date"] = pd.to_datetime(result["trading_date"]).dt.date

    return result


def update_htf_levels(symbol: str, df_1d_full: pd.DataFrame, full_regen: bool) -> int:
    """Full rebuild HTF levels parquet."""
    out = _htf_levels_path(symbol)
    logger.info("  [htf_levels] Computing from daily data (%s bars)", f"{len(df_1d_full):,}")

    if df_1d_full.empty:
        logger.info("  [htf_levels] No daily data — skipping")
        return 0

    result = compute_htf_levels(symbol, df_1d_full)
    if result.empty:
        return 0

    result.to_parquet(out, index=False)
    logger.info("  [htf_levels] Wrote %s rows -> %s", f"{len(result):,}", out.name)
    return len(result)


# ═══════════════════════════════════════════════════════════════════════
#  Structure Pipeline (Swings + MSS/BOS/CISD)
# ═══════════════════════════════════════════════════════════════════════

def _structure_path(symbol: str, tf: str) -> Path:
    return _ICT_DIR / f"{symbol}_structure_{tf}.parquet"


def compute_structure(symbol: str, df_1m: pd.DataFrame, tf: str) -> pd.DataFrame:
    """Compute swings, structure breaks, and CISD for one symbol at one timeframe.

    Returns only rows where a swing or structure event is detected.
    Schema:
        bar_time (index), symbol, timeframe, logical_date,
        swing_type (1=high, -1=low, 0=none),
        swing_level,
        break_high (bool), break_low (bool),
        cisd_type (1=bullish, -1=bearish, 0=none)
    """
    rule = IMBALANCE_TIMEFRAMES[tf]
    df_et = normalize_to_eastern(df_1m)

    # Resample to target TF
    df_rs = (
        df_et[["open", "high", "low", "close"]]
        .resample(rule, origin="start_day")
        .agg({"open": "first", "high": "max", "low": "min", "close": "last"})
        .dropna()
    )

    # Detect swings
    swings = detect_swings(df_rs)
    # Detect structure breaks
    breaks = detect_structure_breaks(df_rs, swings)
    # Detect CISD
    cisd = detect_cisd(df_rs, swings)

    result = pd.DataFrame(index=df_rs.index)
    result["swing_type"] = swings["shl"].values
    result["swing_level"] = swings["level"].values
    result["break_high"] = breaks["break_high"].astype(int).values
    result["break_low"] = breaks["break_low"].astype(int).values
    result["cisd_type"] = cisd["cisd"].values

    # Keep only rows where something happened
    has_event = (result["swing_type"] != 0) | (result["break_high"] != 0) | (result["break_low"] != 0) | (result["cisd_type"] != 0)
    result = result[has_event].copy()

    result.index.name = "bar_time"
    result.insert(0, "symbol", symbol)
    result["timeframe"] = tf
    result["logical_date"] = get_logical_trading_date(result.index)

    return result


def update_structure(symbol: str, tf: str, df_1m_full: pd.DataFrame, full_regen: bool) -> int:
    """Incrementally update or fully rebuild the structure parquet."""
    out = _structure_path(symbol, tf)
    start_date = None

    if not full_regen and out.exists():
        existing = pd.read_parquet(out)
        if not existing.empty:
            last_bar = existing.index.max()
            start_date = (last_bar + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
            logger.info("  [%s] Incremental from %s (%s existing)", tf, start_date, f"{len(existing):,}")
    else:
        logger.info("  [%s] Full build from scratch", tf)

    df_1m = df_1m_full
    if start_date:
        df_1m = df_1m[df_1m.index >= pd.to_datetime(start_date)]

    if df_1m.empty:
        logger.info("  [%s] No new bars — up to date", tf)
        return 0

    new_rows = compute_structure(symbol, df_1m, tf)
    logger.info("  [%s] %s new structure rows", tf, f"{len(new_rows):,}")

    if new_rows.empty:
        return 0

    if out.exists() and not full_regen:
        existing = pd.read_parquet(out)
        combined = pd.concat([existing, new_rows])
        combined = combined[~combined.index.duplicated(keep="last")].sort_index()
    else:
        combined = new_rows.sort_index()

    combined.to_parquet(out)
    logger.info("  [%s] Wrote %s total rows -> %s", tf, f"{len(combined):,}", out.name)
    return len(new_rows)


# ═══════════════════════════════════════════════════════════════════════
#  Order Blocks Pipeline
# ═══════════════════════════════════════════════════════════════════════

def _ob_path(symbol: str, tf: str) -> Path:
    return _ICT_DIR / f"{symbol}_ob_{tf}.parquet"


def compute_orderblocks(symbol: str, df_1m: pd.DataFrame, tf: str) -> pd.DataFrame:
    """Compute order blocks for one symbol at one timeframe.

    Returns only rows where an OB is detected.
    Schema:
        bar_time (index), symbol, timeframe, logical_date,
        ob_type (1=bullish, -1=bearish, 0=none),
        ob_top, ob_bottom
    """
    rule = IMBALANCE_TIMEFRAMES[tf]
    df_et = normalize_to_eastern(df_1m)

    df_rs = (
        df_et[["open", "high", "low", "close"]]
        .resample(rule, origin="start_day")
        .agg({"open": "first", "high": "max", "low": "min", "close": "last"})
        .dropna()
    )

    swings = detect_swings(df_rs)
    obs = detect_orderblock(df_rs, swings)

    result = pd.DataFrame(index=df_rs.index)
    result["ob_type"] = obs["ob"].values
    result["ob_top"] = obs["top"].values
    result["ob_bottom"] = obs["bottom"].values

    # Keep only OB-positive rows
    result = result[result["ob_type"] != 0].copy()

    result.index.name = "bar_time"
    result.insert(0, "symbol", symbol)
    result["timeframe"] = tf
    result["logical_date"] = get_logical_trading_date(result.index)

    return result


def update_orderblocks(symbol: str, tf: str, df_1m_full: pd.DataFrame, full_regen: bool) -> int:
    """Incrementally update or fully rebuild the OB parquet."""
    out = _ob_path(symbol, tf)
    start_date = None

    if not full_regen and out.exists():
        existing = pd.read_parquet(out)
        if not existing.empty:
            last_bar = existing.index.max()
            start_date = (last_bar + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
            logger.info("  [ob/%s] Incremental from %s (%s existing)", tf, start_date, f"{len(existing):,}")
    else:
        logger.info("  [ob/%s] Full build from scratch", tf)

    df_1m = df_1m_full
    if start_date:
        df_1m = df_1m[df_1m.index >= pd.to_datetime(start_date)]

    if df_1m.empty:
        logger.info("  [ob/%s] No new bars — up to date", tf)
        return 0

    new_rows = compute_orderblocks(symbol, df_1m, tf)
    logger.info("  [ob/%s] %s new OB rows", tf, f"{len(new_rows):,}")

    if new_rows.empty:
        return 0

    if out.exists() and not full_regen:
        existing = pd.read_parquet(out)
        combined = pd.concat([existing, new_rows])
        combined = combined[~combined.index.duplicated(keep="last")].sort_index()
    else:
        combined = new_rows.sort_index()

    combined.to_parquet(out)
    logger.info("  [ob/%s] Wrote %s total rows -> %s", tf, f"{len(combined):,}", out.name)
    return len(new_rows)


# ═══════════════════════════════════════════════════════════════════════
#  Liquidity Pipeline (BSL/SSL/EQH/EQL)
# ═══════════════════════════════════════════════════════════════════════

def _liquidity_path(symbol: str, tf: str) -> Path:
    return _ICT_DIR / f"{symbol}_liquidity_{tf}.parquet"


def compute_liquidity(symbol: str, df_1m: pd.DataFrame, tf: str) -> pd.DataFrame:
    """Compute liquidity pools (BSL/SSL/EQH/EQL) for one symbol at one timeframe.

    Returns only rows where a liquidity pool is detected.
    Schema:
        bar_time (index), symbol, timeframe, logical_date,
        liq_type (1=BSL, -1=SSL), liq_level, liq_kind (BSL/SSL/EQH/EQL)
    """
    rule = IMBALANCE_TIMEFRAMES[tf]
    df_et = normalize_to_eastern(df_1m)

    df_rs = (
        df_et[["open", "high", "low", "close"]]
        .resample(rule, origin="start_day")
        .agg({"open": "first", "high": "max", "low": "min", "close": "last"})
        .dropna()
    )

    swings = detect_swings(df_rs)
    liq = detect_liquidity(df_rs, swings)

    result = pd.DataFrame(index=df_rs.index)
    result["liq_type"] = liq["liquidity"].values
    result["liq_level"] = liq["level"].values
    result["liq_kind"] = liq["type"].values

    # Keep only liquidity-positive rows
    result = result[result["liq_type"].notna() & (result["liq_type"] != 0)].copy()

    result.index.name = "bar_time"
    result.insert(0, "symbol", symbol)
    result["timeframe"] = tf
    result["logical_date"] = get_logical_trading_date(result.index)

    return result


def update_liquidity(symbol: str, tf: str, df_1m_full: pd.DataFrame, full_regen: bool) -> int:
    """Incrementally update or fully rebuild the liquidity parquet."""
    out = _liquidity_path(symbol, tf)
    start_date = None

    if not full_regen and out.exists():
        existing = pd.read_parquet(out)
        if not existing.empty:
            last_bar = existing.index.max()
            start_date = (last_bar + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
            logger.info("  [liq/%s] Incremental from %s (%s existing)", tf, start_date, f"{len(existing):,}")
    else:
        logger.info("  [liq/%s] Full build from scratch", tf)

    df_1m = df_1m_full
    if start_date:
        df_1m = df_1m[df_1m.index >= pd.to_datetime(start_date)]

    if df_1m.empty:
        logger.info("  [liq/%s] No new bars — up to date", tf)
        return 0

    new_rows = compute_liquidity(symbol, df_1m, tf)
    logger.info("  [liq/%s] %s new liquidity rows", tf, f"{len(new_rows):,}")

    if new_rows.empty:
        return 0

    if out.exists() and not full_regen:
        existing = pd.read_parquet(out)
        combined = pd.concat([existing, new_rows])
        combined = combined[~combined.index.duplicated(keep="last")].sort_index()
    else:
        combined = new_rows.sort_index()

    combined.to_parquet(out)
    logger.info("  [liq/%s] Wrote %s total rows -> %s", tf, f"{len(combined):,}", out.name)
    return len(new_rows)


# ═══════════════════════════════════════════════════════════════════════
#  SMT Divergence Pipeline (NQ vs ES)
# ═══════════════════════════════════════════════════════════════════════

def _smt_path(symbol: str) -> Path:
    """SMT parquet path — keyed by the primary symbol (NQ1)."""
    return _ICT_DIR / f"{symbol}_smt.parquet"


def compute_smt(primary: str = "NQ1", secondary: str = "ES1", tf: str = "5m") -> pd.DataFrame:
    """Compute SMT divergence between NQ and ES.

    Schema:
        bar_time (index), symbol (primary), timeframe, logical_date,
        smt_type (1=bullish, -1=bearish, 0=none)
    """
    rule = IMBALANCE_TIMEFRAMES[tf]

    # Load both symbols
    df_a = loader_load_1m(primary)
    df_b = loader_load_1m(secondary)

    if df_a.empty or df_b.empty:
        return pd.DataFrame()

    df_a_et = normalize_to_eastern(df_a)
    df_b_et = normalize_to_eastern(df_b)

    # Resample both to same timeframe
    df_a_rs = df_a_et[["open", "high", "low", "close"]].resample(rule, origin="start_day").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    df_b_rs = df_b_et[["open", "high", "low", "close"]].resample(rule, origin="start_day").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()

    # Align on common index
    common_idx = df_a_rs.index.intersection(df_b_rs.index)
    df_a_aligned = df_a_rs.loc[common_idx]
    df_b_aligned = df_b_rs.loc[common_idx]

    # Detect swings for both
    swings_a = detect_swings(df_a_aligned)
    swings_b = detect_swings(df_b_aligned)

    # Detect SMT
    smt = detect_smt(df_a_aligned, df_b_aligned, swings_a, swings_b)

    result = pd.DataFrame(index=common_idx)
    result["smt_type"] = smt["smt"].values

    # Keep only SMT-positive rows
    result = result[result["smt_type"] != 0].copy()

    result.index.name = "bar_time"
    result.insert(0, "symbol", primary)
    result["timeframe"] = tf
    result["logical_date"] = get_logical_trading_date(result.index)

    return result


def loader_load_1m(symbol: str) -> pd.DataFrame:
    """Helper to load 1m data via the global loader."""
    from scripts.edgeful.lib.data_loader import get_loader
    return get_loader().load_1m(symbol)


def update_smt(primary: str, secondary: str, tf: str, full_regen: bool) -> int:
    """Full rebuild SMT parquet."""
    out = _smt_path(primary)
    logger.info("  [smt] Computing %s vs %s at %s", primary, secondary, tf)

    new_rows = compute_smt(primary, secondary, tf)
    logger.info("  [smt] %s SMT divergence rows", f"{len(new_rows):,}")

    if new_rows.empty:
        return 0

    new_rows.to_parquet(out)
    logger.info("  [smt] Wrote %s rows -> %s", f"{len(new_rows):,}", out.name)
    return len(new_rows)


# ═══════════════════════════════════════════════════════════════════════
#  Orchestration
# ═══════════════════════════════════════════════════════════════════════

def run_feature(feature: str, symbol: str, loader, full_regen: bool) -> int:
    """Run one feature for one symbol. Returns row count written."""
    if feature == "imbalance":
        df_1m = loader.load_1m(symbol)
        if df_1m.empty:
            logger.warning("No 1m data for %s", symbol)
            return 0
        total = 0
        for tf in IMBALANCE_TIMEFRAMES:
            total += update_imbalances(symbol, tf, df_1m, full_regen)
        return total

    elif feature == "gaps":
        df_1m = loader.load_1m(symbol)
        if df_1m.empty:
            logger.warning("No 1m data for %s", symbol)
            return 0
        return update_gaps(symbol, df_1m, full_regen)

    elif feature == "kz_pivots":
        df_1m = loader.load_1m(symbol)
        if df_1m.empty:
            logger.warning("No 1m data for %s", symbol)
            return 0
        return update_kz_pivots(symbol, df_1m, full_regen)

    elif feature == "ipda":
        df_1d = loader.load_daily(symbol)
        # Check if daily data is stale (last bar > 3 days ago)
        if not df_1d.empty:
            last_daily = df_1d.index[-1]
            if hasattr(last_daily, 'date'):
                last_date = last_daily.date()
            elif hasattr(last_daily, 'to_pydatetime'):
                last_date = last_daily.to_pydatetime().date()
            else:
                last_date = pd.Timestamp(last_daily).date()
            from datetime import datetime as _dt
            import pytz as _pytz
            today = _dt.now(_pytz.timezone("America/New_York")).date()
            if (today - last_date).days > 3:
                logger.info("  [ipda] Daily parquet stale (last=%s), using 1m data", last_date)
                df_1d = loader.load_1m(symbol)
        if df_1d.empty:
            # Fallback: use 1m data (library resamples to daily internally)
            df_1d = loader.load_1m(symbol)
            if not df_1d.empty:
                logger.info("  [ipda] Daily parquet empty, using 1m data (%s bars)", f"{len(df_1d):,}")
        if df_1d.empty:
            logger.warning("No data for %s", symbol)
            return 0
        return update_ipda(symbol, df_1d, full_regen)

    elif feature == "htf_levels":
        df_1d = loader.load_daily(symbol)
        # Check if daily data is stale
        if not df_1d.empty:
            last_daily = df_1d.index[-1]
            if hasattr(last_daily, 'date'):
                last_date = last_daily.date()
            elif hasattr(last_daily, 'to_pydatetime'):
                last_date = last_daily.to_pydatetime().date()
            else:
                last_date = pd.Timestamp(last_daily).date()
            from datetime import datetime as _dt
            import pytz as _pytz
            today = _dt.now(_pytz.timezone("America/New_York")).date()
            if (today - last_date).days > 3:
                logger.info("  [htf_levels] Daily parquet stale (last=%s), using 1m data", last_date)
                df_1d = loader.load_1m(symbol)
        if df_1d.empty:
            # Fallback: use 1m data (library resamples to daily internally)
            df_1d = loader.load_1m(symbol)
            if not df_1d.empty:
                logger.info("  [htf_levels] Daily parquet empty, using 1m data (%s bars)", f"{len(df_1d):,}")
        if df_1d.empty:
            logger.warning("No data for %s", symbol)
            return 0
        return update_htf_levels(symbol, df_1d, full_regen)

    elif feature == "structure":
        df_1m = loader.load_1m(symbol)
        if df_1m.empty:
            logger.warning("No 1m data for %s", symbol)
            return 0
        total = 0
        for tf in IMBALANCE_TIMEFRAMES:
            total += update_structure(symbol, tf, df_1m, full_regen)
        return total

    elif feature == "orderblocks":
        df_1m = loader.load_1m(symbol)
        if df_1m.empty:
            logger.warning("No 1m data for %s", symbol)
            return 0
        total = 0
        for tf in IMBALANCE_TIMEFRAMES:
            total += update_orderblocks(symbol, tf, df_1m, full_regen)
        return total

    elif feature == "liquidity":
        df_1m = loader.load_1m(symbol)
        if df_1m.empty:
            logger.warning("No 1m data for %s", symbol)
            return 0
        total = 0
        for tf in IMBALANCE_TIMEFRAMES:
            total += update_liquidity(symbol, tf, df_1m, full_regen)
        return total

    elif feature == "smt":
        # SMT requires NQ1 as primary and ES1 as secondary
        if symbol not in ("NQ1", "ES1"):
            logger.warning("SMT only computed for NQ1 (vs ES1). Skipping %s", symbol)
            return 0
        primary = "NQ1"
        secondary = "ES1"
        return update_smt(primary, secondary, "5m", full_regen)

    else:
        logger.error("Unknown feature: %s", feature)
        return 0


def main():
    parser = argparse.ArgumentParser(
        description="ICT Features Computation Pipeline — builds data/derived/ICT/*.parquet"
    )
    parser.add_argument(
        "--symbols", type=str,
        help=f"Comma-separated symbols (default: {','.join(DEFAULT_SYMBOLS)})",
    )
    parser.add_argument(
        "--features", type=str,
        default=",".join(ALL_FEATURES),
        help=f"Comma-separated features (default: all. Available: {','.join(ALL_FEATURES)})",
    )
    parser.add_argument(
        "--full-regen", action="store_true",
        help="Rebuild all parquets from scratch (ignores existing files)",
    )
    parser.add_argument(
        "--incremental", action="store_true",
        help="Force incremental update (default behavior, explicit flag for narrative triggers)",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Enable debug logging",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    target_symbols = args.symbols.split(",") if args.symbols else DEFAULT_SYMBOLS
    target_features = [f.strip() for f in args.features.split(",")]

    invalid = [f for f in target_features if f not in ALL_FEATURES]
    if invalid:
        print(f"[ERROR] Unknown features: {invalid}. Valid: {ALL_FEATURES}")
        return

    _ICT_DIR.mkdir(parents=True, exist_ok=True)
    loader = get_loader()

    total_rows = 0
    for symbol in target_symbols:
        logger.info("=" * 60)
        logger.info("Symbol: %s", symbol)
        logger.info("=" * 60)
        for feature in target_features:
            logger.info("-" * 40)
            logger.info("Feature: %s", feature)
            logger.info("-" * 40)
            try:
                rows = run_feature(feature, symbol, loader, args.full_regen)
                total_rows += rows
            except Exception as e:
                logger.error("FAILED %s/%s: %s", symbol, feature, e, exc_info=args.verbose)

    logger.info("=" * 60)
    logger.info("Done. Total new rows: %s", f"{total_rows:,}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()