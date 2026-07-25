"""
IB Aggregate Stats Builder — Phase 1

Reads existing ib_facts_*.parquet, ib_play_detail_*.parquet, ib_ext_detail_*.parquet
and produces the aggregate tables defined in IB_STATS_PIPELINE_SPEC_v5 §3 and the
data-gathering plan (docs/plans/2026-07-24-ib-data-gathering-plan.md):

    ib_agg_bias_compare.parquet     Per variant: DIR%, HIT% 0.25/0.5/0.75/1x, LIFT, N
    ib_agg_timing.parquet             Per session/time_basis: mode break bucket,
                                      median break min, extension timing, mid-retest timing
    ib_agg_extension_ladder.parquet Per level: P(hit L+0.5 | hit L), N
    ib_agg_plays_by_regime.parquet  Per play × regime: WR, expectancy, N
    ib_agg_bias_conflict.parquet      Pairwise bias conflict matrix
    ib_agg_no_signal.parquet          No-signal / chop statistics

All computations are vectorized and operate on existing derived parquet files.
"""

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

# Make repo root importable
_current_dir = Path(__file__).resolve().parent
while _current_dir.name and _current_dir.name != "scripts":
    _current_dir = _current_dir.parent
if _current_dir.name == "scripts":
    _root_dir = str(_current_dir.parent)
    if _root_dir not in sys.path:
        sys.path.insert(0, _root_dir)

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
logger = logging.getLogger(__name__)

DERIVED_DIR = Path("data/derived")
OUT_DIR = DERIVED_DIR
INSTRUMENTS = ["NQ1", "ES1", "YM1", "RTY1", "CL1", "GC1"]

# Bias variants present in ib_facts. Each variant is measured against first_break_dir
# for direction accuracy (DIR%) and against extension hit flags for hit accuracy (HIT%).
BIAS_VARIANTS = [
    "formation_firstreach",
    "formation_lasttouch",
    "close_dir",
    "fvg",
    "fvg_ifvg",
    "fvg_rth",
    "fvg_1011",
    "combined",
]

BIAS_LEVELS = ["00x", "025x", "05x", "075x", "10x"]

PLAY_NAMES = {1: "breakout", 2: "retest_cont", 3: "fade_to_mid"}


def load_fact_frames(symbols: List[str]) -> pd.DataFrame:
    """Concatenate ib_facts_{SYM}.parquet files into one long frame.

    Adds 5-minute bucketed versions of all minute-based timing columns so that
    aggregate tables and downstream strategies operate on a common 5-min grid.
    """
    frames = []
    for sym in symbols:
        path = DERIVED_DIR / f"ib_facts_{sym}.parquet"
        if not path.exists():
            logger.warning("Missing %s", path)
            continue
        df = pd.read_parquet(path)
        df["symbol"] = sym

        # 5-min bucketed timing fields (raw minute columns are preserved)
        minute_cols = [
            "first_break_minutes",
            "mid_retest_minutes",
            "gap_fill_minutes",
            "front_run_activation_mins",
        ]
        for col in minute_cols:
            if col in df.columns:
                df[f"{col}_5min"] = _bucket_minutes_5min(df[col])

        frames.append(df)
    if not frames:
        raise FileNotFoundError("No ib_facts files found.")
    return pd.concat(frames, ignore_index=True)


def load_play_frames(symbols: List[str]) -> pd.DataFrame:
    frames = []
    for sym in symbols:
        path = DERIVED_DIR / f"ib_play_detail_{sym}.parquet"
        if not path.exists():
            continue
        frames.append(pd.read_parquet(path))
    if not frames:
        raise FileNotFoundError("No ib_play_detail files found.")
    return pd.concat(frames, ignore_index=True)


def load_ext_frames(symbols: List[str]) -> pd.DataFrame:
    frames = []
    for sym in symbols:
        path = DERIVED_DIR / f"ib_ext_detail_{sym}.parquet"
        if not path.exists():
            continue
        frames.append(pd.read_parquet(path))
    if not frames:
        raise FileNotFoundError("No ib_ext_detail files found.")
    return pd.concat(frames, ignore_index=True)


def _pctile(x: pd.Series) -> float:
    """Mean of bool-ish series (with NaN drop) for win rate / hit rate."""
    return float(x.mean()) if len(x.dropna()) else np.nan


def _safe_median(x: pd.Series) -> float:
    return float(x.median()) if len(x.dropna()) else np.nan


def _safe_mode_bucket(x: pd.Series) -> str:
    """Return most common non-null value."""
    vc = x.dropna().value_counts()
    return str(vc.index[0]) if len(vc) else ""


def _bucket_minutes_5min(x: pd.Series) -> pd.Series:
    """Floor minute counts to the nearest lower multiple of 5.

    All timing measurements are reported in 5-minute buckets so that
    strategies can align entries/exits to a common 5-minute grid.
    """
    return (x // 5 * 5).where(x.notna(), np.nan)


def build_bias_compare(df_facts: pd.DataFrame) -> pd.DataFrame:
    """
    Per variant, per session_slot/time_basis/symbol: DIR% and HIT% at each level,
    baseline, lift, N.
    """
    rows = []
    group_cols = ["symbol", "session_slot", "time_basis"]
    # Also produce an overall row per symbol/session/time_basis as baseline.

    for cols, frame in df_facts.groupby(group_cols, sort=False):
        sym, slot, basis = cols
        baseline_wr = _pctile(frame["first_break_dir"] == frame["bias_formation_firstreach"])
        rows.append({
            "symbol": sym,
            "session_slot": slot,
            "time_basis": basis,
            "variant": "baseline_formation_firstreach",
            "dir_pct": baseline_wr,
            "n_dir": int((frame["first_break_dir"].notna() & frame["bias_formation_firstreach"].notna()).sum()),
        })

        for variant in BIAS_VARIANTS:
            bias_col = f"bias_{variant}"
            if bias_col not in frame.columns:
                continue
            row = {
                "symbol": sym,
                "session_slot": slot,
                "time_basis": basis,
                "variant": variant,
            }
            valid = frame[bias_col].notna() & frame["first_break_dir"].notna()
            row["n_dir"] = int(valid.sum())
            row["dir_pct"] = _pctile(frame.loc[valid, "first_break_dir"] == frame.loc[valid, bias_col])

            for lvl in BIAS_LEVELS:
                hit_col = f"bias_correct_{variant}_{lvl}"
                if hit_col not in frame.columns:
                    continue
                valid_hit = frame[hit_col].notna()
                n_hit = int(valid_hit.sum())
                hit_pct = _pctile(frame.loc[valid_hit, hit_col])
                row[f"hit_pct_{lvl}"] = hit_pct
                row[f"n_hit_{lvl}"] = n_hit

            # lift = dir_pct relative to baseline
            row["lift_dir_pct"] = (row["dir_pct"] - baseline_wr) if not np.isnan(row["dir_pct"]) else np.nan
            rows.append(row)

    out = pd.DataFrame(rows)
    # reorder columns for readability
    first = ["symbol", "session_slot", "time_basis", "variant", "dir_pct", "n_dir"]
    hit_cols = [c for c in out.columns if c.startswith("hit_pct_") or c.startswith("n_hit_")]
    rest = ["lift_dir_pct"]
    keep = first + hit_cols + rest
    return out[[c for c in keep if c in out.columns]]


def build_timing(df_facts: pd.DataFrame) -> pd.DataFrame:
    """
    Per session/time_basis/symbol: mode break bucket, median break minutes (5-min
    bucketed), median extension minutes for 0.5x/1x/1.5x, mid-retest minutes/mode,
    etc. All minute-based timings are reported on a 5-minute grid.
    """
    rows = []
    for cols, frame in df_facts.groupby(["symbol", "session_slot", "time_basis"], sort=False):
        sym, slot, basis = cols
        brk_min = frame["first_break_minutes_5min"] if "first_break_minutes_5min" in frame.columns else frame["first_break_minutes"]
        ret_min = frame["mid_retest_minutes_5min"] if "mid_retest_minutes_5min" in frame.columns else frame["mid_retest_minutes"]
        gap_min = frame["gap_fill_minutes_5min"] if "gap_fill_minutes_5min" in frame.columns else frame["gap_fill_minutes"]

        row = {
            "symbol": sym,
            "session_slot": slot,
            "time_basis": basis,
            "n": len(frame),
            "mode_break_bucket": _safe_mode_bucket(frame["first_break_bucket"]),
            "mode_break_bucket_5min": _safe_mode_bucket(brk_min),
            "mode_break_dir": _safe_mode_bucket(frame["first_break_dir"]),
            "median_break_minutes": _safe_median(brk_min),
            "p25_break_minutes": brk_min.quantile(0.25) if brk_min.notna().any() else np.nan,
            "p75_break_minutes": brk_min.quantile(0.75) if brk_min.notna().any() else np.nan,
            "median_mid_retest_minutes": _safe_median(ret_min),
            "mode_mid_touch_bucket": _safe_mode_bucket(frame["mid_touch_bucket"]),
            "mode_mid_retest_bucket_5min": _safe_mode_bucket(ret_min),
            "mid_retest_pct": _pctile(frame["mid_retest"]),
            "front_run_pct": _pctile(frame["front_run_active"]),
            "double_break_pct": _pctile(frame["double_break"]),
            "median_gap_fill_minutes": _safe_median(gap_min),
        }

        # Extension timing from ext_detail requires separate join later, but we have
        # first-break-minutes distribution per level from ib_facts via max_ext_up/down.
        # We approximate median minutes to 0.5x/1.0x/1.5x from ext_detail in a separate pass.
        rows.append(row)
    return pd.DataFrame(rows)


def build_extension_timing(df_ext: pd.DataFrame) -> pd.DataFrame:
    """Return per (symbol, session_slot, time_basis, side, level) timing stats.

    Extension minutes are bucketed to 5-minute intervals before aggregation.
    """
    df = df_ext.copy()
    df["minutes_5min"] = _bucket_minutes_5min(df["minutes"])
    g = df.groupby(["symbol", "session_slot", "time_basis", "side", "level"], sort=False)
    agg = g.agg(
        n=("hit", "size"),
        hit_pct=("hit", lambda s: float(s.mean())),
        median_minutes=("minutes_5min", "median"),
        p25_minutes=("minutes_5min", lambda s: s.quantile(0.25) if s.notna().any() else np.nan),
        p75_minutes=("minutes_5min", lambda s: s.quantile(0.75) if s.notna().any() else np.nan),
        mode_minutes_bucket_5min=("minutes_5min", lambda s: _safe_mode_bucket(s)),
    ).reset_index()
    return agg


def build_extension_ladder(df_ext: pd.DataFrame) -> pd.DataFrame:
    """
    Conditional extension ladder: P(hit L+0.5 | hit L).
    Ext detail is one row per (symbol, day, session, time_basis, side, level).
    We compute pairwise transitions: given hit at level x, probability hit at x+0.5.
    """
    # Only positive side levels make sense for ladder; side is encoded separately.
    df = df_ext.copy()
    df["side_level"] = df["side"].astype(str) + "_" + df["level"].astype(str)

    rows = []
    for cols, frame in df.groupby(["symbol", "session_slot", "time_basis", "side"], sort=False):
        sym, slot, basis, side = cols
        levels = sorted(frame["level"].unique())
        if len(levels) < 2:
            continue
        # Build per-day hit map
        piv = frame.pivot_table(
            index=["trading_day"], columns="level", values="hit", aggfunc="first"
        )
        for i, lvl in enumerate(levels[:-1]):
            next_lvl = levels[i + 1]
            if lvl not in piv.columns or next_lvl not in piv.columns:
                continue
            hit_here = piv[lvl].fillna(False).astype(bool)
            hit_next = piv[next_lvl].fillna(False).astype(bool)
            valid = hit_here
            n = int(valid.sum())
            cond = float(hit_next[valid].mean()) if n > 0 else np.nan
            rows.append({
                "symbol": sym,
                "session_slot": slot,
                "time_basis": basis,
                "side": side,
                "level": lvl,
                "next_level": next_lvl,
                "n_hit_level": n,
                "p_hit_next_given_hit": cond,
            })
    return pd.DataFrame(rows)


def _play_stats(frame: pd.DataFrame) -> Dict[str, float]:
    """Compute win rate, expectancy, avg mfe, avg mae, n from play detail frame."""
    valid = frame.dropna(subset=["result"])
    n = len(valid)
    if n == 0:
        return {"wr": np.nan, "expectancy": np.nan, "avg_mfe": np.nan, "avg_mae": np.nan, "n": 0}
    wr = float((valid["result"] == 1).mean())
    # Use realized_r as expectancy when available, otherwise approximate
    if "realized_r" in valid.columns and valid["realized_r"].notna().any():
        expectancy = float(valid["realized_r"].mean())
    else:
        expectancy = wr - (1 - wr)  # +1 / -1 reward assumption
    return {
        "wr": wr,
        "expectancy": expectancy,
        "avg_mfe": float(valid["mfe"].mean()) if "mfe" in valid.columns else np.nan,
        "avg_mae": float(valid["mae"].mean()) if "mae" in valid.columns else np.nan,
        "n": n,
    }


def build_plays_by_regime(df_play: pd.DataFrame, df_facts: pd.DataFrame) -> pd.DataFrame:
    """
    Per play, per target level, per regime slice: WR, expectancy, N.
    Regime slices: range_bucket_trailing, vix_bucket_trailing/full, dow, dst_regime, bias agreement.
    """
    # Attach fact-derived regime keys to play rows
    fact_keys = [
        "symbol", "session_slot", "time_basis", "trading_day",
        "range_bucket_trailing", "range_bucket_full",
        "vix_bucket_trailing", "vix_bucket_full",
        "dow", "dst_regime",
        "bias_formation_firstreach", "bias_formation_lasttouch",
    ]
    fact_avail = [c for c in fact_keys if c in df_facts.columns]
    df_fact_sub = df_facts[fact_avail].copy()
    df_fact_sub["bias_agreement"] = np.where(
        df_fact_sub["bias_formation_firstreach"] == df_fact_sub["bias_formation_lasttouch"],
        "agree", "disagree"
    )
    if "bias_formation_firstreach" in df_fact_sub.columns and "bias_fvg" in df_facts.columns:
        df_fact_sub["fvg_agreement"] = np.where(
            df_fact_sub["bias_formation_firstreach"] == df_facts["bias_fvg"], "agree", "disagree"
        )

    merged = df_play.merge(df_fact_sub, on=["symbol", "session_slot", "time_basis", "trading_day"], how="left")

    rows = []
    groupers = [
        ["symbol", "session_slot", "time_basis", "play", "target_lvl"],
        ["symbol", "session_slot", "time_basis", "play", "target_lvl", "range_bucket_trailing"],
        ["symbol", "session_slot", "time_basis", "play", "target_lvl", "vix_bucket_trailing"],
        ["symbol", "session_slot", "time_basis", "play", "target_lvl", "dow"],
        ["symbol", "session_slot", "time_basis", "play", "target_lvl", "dst_regime"],
        ["symbol", "session_slot", "time_basis", "play", "target_lvl", "bias_agreement"],
    ]
    if "fvg_agreement" in merged.columns:
        groupers.append(["symbol", "session_slot", "time_basis", "play", "target_lvl", "fvg_agreement"])

    for grouper in groupers:
        missing = [c for c in grouper if c not in merged.columns]
        if missing:
            continue
        for cols, frame in merged.groupby(grouper, sort=False):
            stats = _play_stats(frame)
            row = dict(zip(grouper, cols))
            row.update(stats)
            rows.append(row)
    return pd.DataFrame(rows)


def build_bias_conflict(df_facts: pd.DataFrame) -> pd.DataFrame:
    """
    Pairwise bias conflict matrix per (symbol, session_slot, time_basis).
    When two bias variants disagree, which one wins?
    """
    variants = []
    for v in BIAS_VARIANTS:
        col = f"bias_{v}"
        if col in df_facts.columns:
            variants.append(v)

    rows = []
    for cols, frame in df_facts.groupby(["symbol", "session_slot", "time_basis"], sort=False):
        sym, slot, basis = cols
        for i, va in enumerate(variants):
            col_a = f"bias_{va}"
            if col_a not in frame.columns:
                continue
            for vb in variants[i + 1:]:
                col_b = f"bias_{vb}"
                if col_b not in frame.columns:
                    continue
                valid = frame[col_a].notna() & frame[col_b].notna() & frame["first_break_dir"].notna()
                n_conflict = int((frame.loc[valid, col_a] != frame.loc[valid, col_b]).sum())
                if n_conflict == 0:
                    continue
                mask_conflict = valid & (frame[col_a] != frame[col_b])
                a_wins = (frame.loc[mask_conflict, col_a] == frame.loc[mask_conflict, "first_break_dir"]).sum()
                b_wins = (frame.loc[mask_conflict, col_b] == frame.loc[mask_conflict, "first_break_dir"]).sum()
                neither = n_conflict - a_wins - b_wins
                rows.append({
                    "symbol": sym,
                    "session_slot": slot,
                    "time_basis": basis,
                    "variant_a": va,
                    "variant_b": vb,
                    "n_conflict": n_conflict,
                    "a_win_pct": float(a_wins / n_conflict),
                    "b_win_pct": float(b_wins / n_conflict),
                    "neither_pct": float(neither / n_conflict),
                    "winner": va if a_wins >= b_wins else vb,
                    "edge": float(abs(a_wins - b_wins) / n_conflict),
                })
    return pd.DataFrame(rows)


def build_no_signal(df_facts: pd.DataFrame) -> pd.DataFrame:
    """No-signal / chop statistics per session/time_basis."""
    rows = []
    for cols, frame in df_facts.groupby(["symbol", "session_slot", "time_basis"], sort=False):
        sym, slot, basis = cols
        # identify rows where primary bias variants are zero/undefined
        no_sig = pd.Series(True, index=frame.index)
        for variant in ["formation_firstreach", "formation_lasttouch", "close_dir"]:
            col = f"bias_{variant}"
            if col in frame.columns:
                no_sig &= (frame[col].fillna(0) == 0)
        chop = (frame["first_break_dir"] == 0) | frame["first_break_dir"].isna()
        rows.append({
            "symbol": sym,
            "session_slot": slot,
            "time_basis": basis,
            "n_total": len(frame),
            "n_no_signal": int(no_sig.sum()),
            "no_signal_rate": float(no_sig.mean()),
            "n_chop": int(chop.sum()),
            "chop_rate": float(chop.mean()),
            "double_break_pct": _pctile(frame["double_break"]),
            "median_range_pct": _safe_median(frame["range_pct"]),
        })
    return pd.DataFrame(rows)


def run_all(symbols: List[str]):
    logger.info("Loading facts for %s", symbols)
    df_facts = load_fact_frames(symbols)
    logger.info("Facts loaded: %s rows", len(df_facts))

    logger.info("Loading play detail")
    df_play = load_play_frames(symbols)
    logger.info("Plays loaded: %s rows", len(df_play))

    logger.info("Loading extension detail")
    df_ext = load_ext_frames(symbols)
    logger.info("Extensions loaded: %s rows", len(df_ext))

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    logger.info("Building bias compare")
    df_bias = build_bias_compare(df_facts)
    df_bias.to_parquet(OUT_DIR / "ib_agg_bias_compare.parquet", index=False)

    logger.info("Building timing")
    df_timing = build_timing(df_facts)
    df_ext_timing = build_extension_timing(df_ext)
    # merge extension timing into timing on keys
    df_timing = df_timing.merge(
        df_ext_timing,
        on=["symbol", "session_slot", "time_basis"],
        how="left",
        suffixes=("", "_ext"),
    )
    df_timing.to_parquet(OUT_DIR / "ib_agg_timing.parquet", index=False)

    logger.info("Building extension ladder")
    df_ladder = build_extension_ladder(df_ext)
    df_ladder.to_parquet(OUT_DIR / "ib_agg_extension_ladder.parquet", index=False)

    logger.info("Building plays by regime")
    df_regime = build_plays_by_regime(df_play, df_facts)
    df_regime.to_parquet(OUT_DIR / "ib_agg_plays_by_regime.parquet", index=False)

    logger.info("Building bias conflict")
    df_conflict = build_bias_conflict(df_facts)
    df_conflict.to_parquet(OUT_DIR / "ib_agg_bias_conflict.parquet", index=False)

    logger.info("Building no-signal stats")
    df_no_sig = build_no_signal(df_facts)
    df_no_sig.to_parquet(OUT_DIR / "ib_agg_no_signal.parquet", index=False)

    logger.info("Phase 1 complete. Wrote %s files to %s", 6, OUT_DIR)
    return {
        "bias_compare": df_bias,
        "timing": df_timing,
        "extension_ladder": df_ladder,
        "plays_by_regime": df_regime,
        "bias_conflict": df_conflict,
        "no_signal": df_no_sig,
    }


def main():
    parser = argparse.ArgumentParser(description="Build IB aggregate stats tables")
    parser.add_argument("--symbols", type=str, default=",".join(INSTRUMENTS),
                        help="Comma-separated symbols to process")
    args = parser.parse_args()
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    run_all(symbols)


if __name__ == "__main__":
    main()
