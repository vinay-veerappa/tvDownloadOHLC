"""
Daily Confluence Records Computation Pipeline  (Module 5 — Phase 6)

Generates ``data/derived/daily_confluence_records.parquet`` by joining all
derived datasets and computing per-day conditional edge probabilities.

For each (symbol, trading_date) the pipeline computes:
  - gap_fill_probability         — P(gap fills | DOW, vix_regime)
    - or_breakout_probability      — P(OR-15 BO_1X wins on day | DOW, vix_regime)
    - ib_single_break_probability  — P(IB-60 BO_1X wins on day | DOW, vix_regime)
  - occ_continuation_probability — P(OCC continuation | DOW, vix_regime)
  - mop_retrace_probability      — P(MOP retrace | DOW, vix_regime)
  - pdh_pdl_break_probability    — P(PDH or PDL broken | DOW, vix_regime)
  - streak_reversal_probability  — P(streak reversal | DOW, streak_direction)

All probabilities are strictly causal (expanding window, shift(1) before mean),
falling back to unconditional symbol-level rates when N < MIN_SAMPLE.

Bias voting:
    Each forward-looking signal votes +1 (bullish/continuation) or -1
    (bearish/reversal) using only context available before (or very early in)
    the session.
  Totals produce dominant_bias (BULLISH/BEARISH/NEUTRAL) and
  confidence (LOW/MEDIUM/HIGH).

Usage:
    python -m scripts.context.compute_daily_confluence
    python -m scripts.context.compute_daily_confluence --symbols NQ1,ES1
"""
from __future__ import annotations

import argparse
import logging
from pathlib import Path
import sys
from typing import List

import numpy as np
import pandas as pd

_REPO_ROOT = Path(__file__).parent.parent.parent
_DERIVED    = _REPO_ROOT / "data" / "derived"
_OUTPUT     = _DERIVED / "daily_confluence_records.parquet"

if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

DEFAULT_SYMBOLS: List[str] = ["NQ1", "ES1", "YM1", "RTY1", "CL1", "GC1"]
MIN_SAMPLE = 15          # min rows for conditional prob; falls back to unconditional
BIAS_THRESHOLD = 0.52    # probability must exceed this to cast a directional vote

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Data loading helpers
# ─────────────────────────────────────────────────────────────────────────────

def _read(path: Path, cols: list[str] | None = None) -> pd.DataFrame:
    """Read a parquet, return empty DataFrame if missing."""
    if not path.exists():
        logger.warning("parquet not found: %s", path)
        return pd.DataFrame()
    df = pd.read_parquet(path, columns=cols) if cols else pd.read_parquet(path)
    if "trading_date" in df.columns:
        df["trading_date"] = pd.to_datetime(df["trading_date"]).dt.date
    return df


def _load_context(symbols: List[str]) -> pd.DataFrame:
    frames = []
    for sym in symbols:
        p = _DERIVED / f"daily_context_{sym}.parquet"
        df = _read(p)
        if not df.empty:
            frames.append(df)
    if not frames:
        raise FileNotFoundError("No daily_context parquet files found in " + str(_DERIVED))
    return pd.concat(frames, ignore_index=True)


# ─────────────────────────────────────────────────────────────────────────────
# Probability computation
# ─────────────────────────────────────────────────────────────────────────────

def _expanding_cond_prob(
    df: pd.DataFrame,
    event_col: str,
    group_cols: list[str],
    min_sample: int = MIN_SAMPLE,
) -> pd.Series:
    """
    For each row compute P(event_col | symbol, group_cols) using all *prior*
    rows with the same group values (shift(1) expanding mean — no lookahead).
    Falls back to symbol-level unconditional rate when group N < min_sample.
    """
    # Ensure events are float
    df = df.copy()
    df[event_col] = pd.to_numeric(df[event_col], errors="coerce")

    # Conditional expanding mean per (symbol, group_cols)
    cond_mean = df.groupby(["symbol"] + group_cols, sort=False)[event_col].transform(
        lambda x: x.shift(1).expanding().mean()
    )
    cond_n = df.groupby(["symbol"] + group_cols, sort=False)[event_col].transform(
        lambda x: x.shift(1).expanding().count()
    )

    # Unconditional expanding mean per symbol (fallback)
    uncond_mean = df.groupby("symbol", sort=False)[event_col].transform(
        lambda x: x.shift(1).expanding().mean()
    )

    return cond_mean.where(cond_n >= min_sample, uncond_mean)


# ─────────────────────────────────────────────────────────────────────────────
# Merge pipeline
# ─────────────────────────────────────────────────────────────────────────────

def _build_master(symbols: List[str]) -> pd.DataFrame:
    """Load and join all derived datasets onto (symbol, trading_date)."""

    # 1. Daily context — master frame
    df = _load_context(symbols)
    df = df.sort_values(["symbol", "trading_date"]).reset_index(drop=True)

    # Normalise boolean cols in context
    for col in ["pdh_broken", "pdl_broken", "gap_filled", "is_event_day"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # 2. Gap records — prefer full details from standalone file
    gap = _read(_DERIVED / "gap_records.parquet",
                ["symbol", "trading_date", "gap_filled", "gap_direction",
                 "gap_size_bucket", "open_vs_pd_range"])
    if not gap.empty:
        # drop context's own gap cols if present, use dedicated file
        for gc in ["gap_filled", "gap_direction", "gap_size_bucket", "open_vs_pd_range"]:
            if gc in df.columns:
                df.drop(columns=[gc], inplace=True)
        df = df.merge(gap, on=["symbol", "trading_date"], how="left")

    # 3. Reference levels — PDH/PDL/MOP details
    ref = _read(_DERIVED / "reference_levels.parquet",
                ["symbol", "trading_date", "mop_retrace", "pdh_broken", "pdl_broken",
                 "pdh_break_continuation", "pdl_break_continuation"])
    if not ref.empty:
        ref = ref.rename(columns={
            "pdh_broken": "ref_pdh_broken",
            "pdl_broken": "ref_pdl_broken",
        })
        for col in ["pdh_broken", "pdl_broken"]:
            if col in df.columns:
                df.drop(columns=[col], inplace=True)
        df = df.merge(ref, on=["symbol", "trading_date"], how="left")
        df.rename(columns={"ref_pdh_broken": "pdh_broken",
                            "ref_pdl_broken": "pdl_broken"}, inplace=True)

    # 4. Range trades — OR-15 and IB-60 BO_1X day outcomes
    # Count non-trigger days as non-wins so probability reflects day-level edge.
    rt = _read(_DERIVED / "range_trades.parquet",
               ["symbol", "range_name", "strategy_name", "trading_date",
                "entry_triggered", "pnl_r_multiple"])
    if not rt.empty:
        for rname, out_col in [("OR_15", "or_bo_winner"), ("IB_60", "ib_bo_winner")]:
            mask = (
                (rt["range_name"] == rname) &
                (rt["strategy_name"] == "BO_1X")
            )
            sub = (
                rt[mask]
                .assign(**{
                    out_col: (
                        rt.loc[mask, "entry_triggered"].fillna(False).astype(bool)
                        & (rt.loc[mask, "pnl_r_multiple"].fillna(0) > 0)
                    )
                })
                .groupby(["symbol", "trading_date"])[out_col]
                .first()
                .reset_index()
            )
            df = df.merge(sub, on=["symbol", "trading_date"], how="left")
            df[out_col] = pd.to_numeric(df[out_col], errors="coerce").fillna(0.0)
    else:
        df["or_bo_winner"] = np.nan
        df["ib_bo_winner"] = np.nan

    # 5. OCC records — 5-minute opening candle
    occ = _read(_DERIVED / "occ_records.parquet",
                ["symbol", "trading_date", "candle_duration_minutes",
                 "continuation", "first_candle_direction"])
    if not occ.empty:
        # Prefer 15-min opening candle; fall back to smallest available duration.
        if (occ["candle_duration_minutes"] == 15).any():
            best_dur = 15
        else:
            best_dur = occ["candle_duration_minutes"].min()
        occ5 = (
            occ[occ["candle_duration_minutes"] == best_dur]
            [["symbol", "trading_date", "continuation", "first_candle_direction"]]
            .copy()
            .rename(columns={"continuation": "occ_continuation",
                              "first_candle_direction": "occ_first_direction"})
        )
        df = df.merge(occ5, on=["symbol", "trading_date"], how="left")
    else:
        df["occ_continuation"]  = np.nan
        df["occ_first_direction"] = np.nan

    # 6. Streak records — next_day_continuation outcome
    stk = _read(_DERIVED / "streak_records.parquet",
                ["symbol", "trading_date", "streak_direction",
                 "streak_length", "next_day_continuation"])
    if not stk.empty:
        stk["streak_reversal"] = (~stk["next_day_continuation"].fillna(True)).astype(float)
        merge_cols = ["symbol", "trading_date", "streak_reversal"]
        # bring in streak_direction if not already in context
        if "streak_direction" not in df.columns:
            merge_cols.append("streak_direction")
        df = df.merge(stk[merge_cols], on=["symbol", "trading_date"], how="left")
    else:
        df["streak_reversal"] = np.nan

    return df


# ─────────────────────────────────────────────────────────────────────────────
# Bias vote helpers
# ─────────────────────────────────────────────────────────────────────────────

def _safe(row: pd.Series, col: str, default=np.nan):
    v = row.get(col, default)
    return default if pd.isna(v) else v


def _direction_sign(value: str | None) -> int:
    """Map mixed direction labels to +1/-1/0."""
    if not value:
        return 0
    v = str(value).upper()
    if v in {"UP", "GREEN", "ABOVE", "ABOVE_PDH"}:
        return 1
    if v in {"DOWN", "RED", "BELOW", "BELOW_PDL"}:
        return -1
    return 0


def _context_direction_sign(row: pd.Series) -> int:
    """Best-available directional context known pre-session."""
    gap_dir = _safe(row, "gap_direction", None)
    sign = _direction_sign(gap_dir)
    if sign != 0:
        return sign

    open_vs_pd = _safe(row, "open_vs_pd_range", None)
    sign = _direction_sign(open_vs_pd)
    if sign != 0:
        return sign

    open_vs_midnight = _safe(row, "open_vs_midnight", None)
    sign = _direction_sign(open_vs_midnight)
    if sign != 0:
        return sign

    streak_dir = _safe(row, "streak_direction", None)
    return _direction_sign(streak_dir)


def _gap_vote(row: pd.Series) -> int:
    """Gap fills are mean-reversion signals — direction depends on gap side."""
    prob = _safe(row, "gap_fill_probability")
    gdir = _safe(row, "gap_direction", "NONE")
    if pd.isna(prob) or gdir == "NONE" or prob <= BIAS_THRESHOLD:
        return 0
    if gdir == "UP":
        return -1   # Gap up likely fills → bearish leaning
    if gdir == "DOWN":
        return 1    # Gap down likely fills → bullish leaning
    return 0


def _occ_vote(row: pd.Series) -> int:
    """High OCC continuation → directionally amplifies opening candle."""
    prob = _safe(row, "occ_continuation_probability")
    cdir = _safe(row, "occ_first_direction", None)
    if pd.isna(prob) or not cdir or prob <= BIAS_THRESHOLD:
        return 0
    return _direction_sign(cdir)


def _or_vote(row: pd.Series) -> int:
    """High OR breakout probability follows contextual direction."""
    prob = _safe(row, "or_breakout_probability")
    if pd.isna(prob) or prob <= BIAS_THRESHOLD:
        return 0
    return _context_direction_sign(row)


def _ib_vote(row: pd.Series) -> int:
    """High IB single-break probability follows contextual direction."""
    prob = _safe(row, "ib_single_break_probability")
    if pd.isna(prob) or prob <= BIAS_THRESHOLD:
        return 0
    return _context_direction_sign(row)


def _pdh_pdl_vote(row: pd.Series) -> int:
    """PDH/PDL breakout with follow-through."""
    pdh     = bool(_safe(row, "pdh_broken", False))
    pdl     = bool(_safe(row, "pdl_broken", False))
    pdh_cnt = _safe(row, "pdh_break_continuation", None)
    pdl_cnt = _safe(row, "pdl_break_continuation", None)
    if pdh and pdh_cnt is True:
        return 1
    if pdl and pdl_cnt is True:
        return -1
    if pdh and pdh_cnt is False:
        return -1   # failed PDH break is bearish
    if pdl and pdl_cnt is False:
        return 1    # failed PDL break is bullish
    return 0


def _streak_vote(row: pd.Series) -> int:
    """High streak reversal probability → fades the streak direction."""
    prob = _safe(row, "streak_reversal_probability")
    sdir = _safe(row, "streak_direction", None)
    if pd.isna(prob) or not sdir or prob <= BIAS_THRESHOLD:
        return 0
    return -_direction_sign(sdir)


def _mop_vote(row: pd.Series) -> int:
    """High MOP retrace probability — mean-reversion signal."""
    prob = _safe(row, "mop_retrace_probability")
    open_vs_midnight = _safe(row, "open_vs_midnight", None)
    if pd.isna(prob) or not open_vs_midnight or prob <= BIAS_THRESHOLD:
        return 0
    # Mean reversion: opening above midnight leans bearish retrace, below leans bullish retrace.
    return -_direction_sign(open_vs_midnight)


# ─────────────────────────────────────────────────────────────────────────────
# Main computation
# ─────────────────────────────────────────────────────────────────────────────

def compute_confluence(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(["symbol", "trading_date"]).reset_index(drop=True)

    # ── Conditional probabilities (all causal) ───────────────────────────────
    prob_specs: list[tuple[str, str, list[str]]] = [
        ("gap_fill_probability",         "gap_filled",       ["day_of_week", "vix_regime"]),
        ("or_breakout_probability",      "or_bo_winner",     ["day_of_week", "vix_regime"]),
        ("ib_single_break_probability",  "ib_bo_winner",     ["day_of_week", "vix_regime"]),
        ("occ_continuation_probability", "occ_continuation", ["day_of_week", "vix_regime"]),
        ("mop_retrace_probability",      "mop_retrace",      ["day_of_week", "vix_regime"]),
        ("streak_reversal_probability",  "streak_reversal",  ["day_of_week", "streak_direction"]),
    ]

    # Combined PDH-or-PDL break event
    pdh = pd.to_numeric(df.get("pdh_broken", pd.Series(dtype=float)), errors="coerce").fillna(0)
    pdl = pd.to_numeric(df.get("pdl_broken", pd.Series(dtype=float)), errors="coerce").fillna(0)
    df["_pd_level_broken"] = ((pdh > 0) | (pdl > 0)).astype(float)
    prob_specs.append(("pdh_pdl_break_probability", "_pd_level_broken", ["day_of_week", "vix_regime"]))

    # Ensure vix_regime and streak_direction have no NaN (replace with "UNKNOWN")
    df["vix_regime"]      = df["vix_regime"].fillna("UNKNOWN")
    df["streak_direction"] = df.get("streak_direction", pd.Series("UNKNOWN", index=df.index)).fillna("UNKNOWN")

    for out_col, event_col, group_cols in prob_specs:
        if event_col in df.columns:
            df[out_col] = _expanding_cond_prob(df, event_col, group_cols)
        else:
            df[out_col] = np.nan

    # ── Directional bias votes ────────────────────────────────────────────────
    vote_fns = {
        "v_gap":      _gap_vote,
        "v_or":       _or_vote,
        "v_ib":       _ib_vote,
        "v_occ":      _occ_vote,
        "v_streak":   _streak_vote,
        "v_mop":      _mop_vote,
    }
    for vcol, fn in vote_fns.items():
        df[vcol] = df.apply(fn, axis=1).astype(int)

    vote_cols = list(vote_fns.keys())
    df["total_vote"]                 = df[vote_cols].sum(axis=1)
    df["continuation_confluence_count"] = (df[vote_cols] == 1).sum(axis=1).astype(int)
    df["reversal_confluence_count"]     = (df[vote_cols] == -1).sum(axis=1).astype(int)

    # dominant bias: need net |vote| >= 2 to declare directional
    df["dominant_bias"] = "NEUTRAL"
    df.loc[df["total_vote"] >= 2,  "dominant_bias"] = "BULLISH"
    df.loc[df["total_vote"] <= -2, "dominant_bias"] = "BEARISH"

    # confidence from net vote magnitude (6 votes total)
    # This prevents contradictory labels like NEUTRAL + HIGH.
    vote_abs = df["total_vote"].abs()
    conditions = [vote_abs >= 3, vote_abs == 2, vote_abs <= 1]
    df["confidence"] = np.select(conditions, ["HIGH", "MEDIUM", "LOW"], default="LOW")

    # ── Clean up internal columns ─────────────────────────────────────────────
    df.drop(columns=vote_cols + ["_pd_level_broken"], inplace=True, errors="ignore")

    return df


# ─────────────────────────────────────────────────────────────────────────────
# Output selection
# ─────────────────────────────────────────────────────────────────────────────

_OUTPUT_COLS = [
    "symbol", "trading_date", "day_of_week", "vix_regime",
    "gap_direction", "gap_size_bucket", "open_vs_pd_range",
    "streak_direction", "streak_length",
    "session_direction", "occ_first_direction",
    "is_event_day", "event_type", "is_opex_week",
    "atr_14d", "atr_usage_pct",
    # probabilities
    "gap_fill_probability", "or_breakout_probability",
    "ib_single_break_probability", "occ_continuation_probability",
    "mop_retrace_probability", "pdh_pdl_break_probability",
    "streak_reversal_probability",
    # bias
    "total_vote", "continuation_confluence_count", "reversal_confluence_count",
    "dominant_bias", "confidence",
    # per-signal outcomes (for drill-down in dashboard)
    "gap_filled", "mop_retrace", "pdh_broken", "pdl_broken",
    "pdh_break_continuation", "pdl_break_continuation",
    "occ_continuation", "or_bo_winner", "ib_bo_winner",
]


def _select_output(df: pd.DataFrame) -> pd.DataFrame:
    keep = [c for c in _OUTPUT_COLS if c in df.columns]
    return df[keep].copy()


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main(symbols: List[str]) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    logger.info("Loading & merging derived datasets for %s", symbols)
    master = _build_master(symbols)
    logger.info("Master frame: %d rows, %d columns", len(master), len(master.columns))

    logger.info("Computing conditional probabilities and bias votes …")
    result = compute_confluence(master)

    out = _select_output(result)
    out = out.sort_values(["symbol", "trading_date"]).reset_index(drop=True)

    _DERIVED.mkdir(parents=True, exist_ok=True)
    out.to_parquet(_OUTPUT, index=False)
    logger.info("Wrote %d rows → %s", len(out), _OUTPUT)

    # Quick validation
    logger.info("Dominant bias distribution:\n%s",
                out["dominant_bias"].value_counts().to_string())
    logger.info("Confidence distribution:\n%s",
                out["confidence"].value_counts().to_string())
    blank = out["gap_fill_probability"].isna().sum()
    logger.info("NaN gap_fill_probability: %d / %d", blank, len(out))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compute DailyConfluenceRecord parquet")
    parser.add_argument(
        "--symbols",
        default=",".join(DEFAULT_SYMBOLS),
        help="Comma-separated symbol list",
    )
    args = parser.parse_args()
    main(args.symbols.split(","))
