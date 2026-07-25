"""
IB Master Confluence Table — Phase 3

Joins the four Phase 2 outputs on (symbol, session_slot, time_basis, trading_day):
    * ib_facts_{SYM}.parquet         (core IB stats and outcome labels)
    * ib_derived_{SYM}.parquet       (multi-day context, break speed/failure)
    * ib_news_opex_{SYM}.parquet     (scheduled news impact and OpEx effects)
    * ib_avwap_{SYM}.parquet         (custom-anchor VWAP + trend confirmations)

Output:
    data/derived/ib_confluence_{SYM}.parquet
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import List

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
INSTRUMENTS = ["NQ1", "ES1", "YM1", "RTY1", "CL1", "GC1"]

KEY_COLS = ["symbol", "session_slot", "time_basis", "trading_day"]

# Columns that exist in every facts file and should always be kept.
FACTS_CORE = [
    "ib_high", "ib_low", "ib_range", "ib_mid", "open_price", "opening_minute_bar",
    "first_break_minutes", "break_direction", "extension_target",
    "ib_extension_pct", "ib_volume", "session_volume_pct",
    "outside_day", "inside_day",
]


def _read_or_empty(path: Path) -> pd.DataFrame:
    if not path.exists():
        logger.warning("Missing %s, returning empty frame", path)
        return pd.DataFrame()
    return pd.read_parquet(path)


def _prepare(df: pd.DataFrame, suffix: str, keep_cols: List[str] = None) -> pd.DataFrame:
    df = df.copy()
    df["trading_day"] = df["trading_day"].astype(str)
    if keep_cols is not None:
        # Always keep key columns if present.
        available = [c for c in KEY_COLS if c in df.columns]
        keep = [c for c in keep_cols if c in df.columns]
        df = df[available + [c for c in keep if c not in available]]
    # Suffix collisions: avoid unless explicitly asked.
    overlap = [c for c in df.columns if c in KEY_COLS]
    rename_map = {c: f"{c}{suffix}" for c in df.columns if c not in overlap}
    df = df.rename(columns=rename_map)
    return df


def build_confluence(symbol: str) -> pd.DataFrame:
    logger.info("[%s] Loading Phase 2 outputs", symbol)

    facts = _read_or_empty(DERIVED_DIR / f"ib_facts_{symbol}.parquet")
    derived = _read_or_empty(DERIVED_DIR / f"ib_derived_{symbol}.parquet")
    news = _read_or_empty(DERIVED_DIR / f"ib_news_opex_{symbol}.parquet")
    avwap = _read_or_empty(DERIVED_DIR / f"ib_avwap_{symbol}.parquet")

    if facts.empty:
        raise FileNotFoundError(f"Missing ib_facts_{symbol}.parquet")

    # Keep all facts columns as the base; derived/news/avwap get suffixed copies of overlapping non-key columns.
    facts["trading_day"] = facts["trading_day"].astype(str)
    base = facts.copy()

    # Select informative derived columns (avoid raw duplicate IB stats).
    derived_keep = [c for c in derived.columns if c not in base.columns or c in KEY_COLS]
    derived_sub = _prepare(derived[derived_keep], "")

    news_keep = [c for c in news.columns if c not in base.columns or c in KEY_COLS]
    news_sub = _prepare(news[news_keep], "")

    avwap_keep = [c for c in avwap.columns if c not in base.columns or c in KEY_COLS]
    avwap_sub = _prepare(avwap[avwap_keep], "")

    for src in (derived_sub, news_sub, avwap_sub):
        if src.empty:
            continue
        overlap = [c for c in src.columns if c in base.columns and c not in KEY_COLS]
        if overlap:
            logger.info("[%s] Renaming overlap columns: %s", symbol, overlap)
            src = src.rename(columns={c: f"{c}_dup" for c in overlap})
        base = base.merge(src, on=KEY_COLS, how="left")

    # ---- Synthetic confluence flags (heuristic starting points) ----

    # 1. News pressure flag: any high-impact red news overlapping IB or OpEx day.
    news_cols = [c for c in base.columns if "high_impact" in c]
    if news_cols:
        base["news_high_impact_present"] = (
            base[news_cols].fillna(0).gt(0).any(axis=1).astype(int)
        )

    # 2. AVWAP aligned flag: confluence score near maximum (6 or 7 out of 7).
    if "avwap_confluence_score" in base.columns:
        base["avwap_aligned"] = (base["avwap_confluence_score"] >= 6).astype(int)
    if "avwap_disagreement_count" in base.columns:
        base["avwap_mixed"] = (base["avwap_disagreement_count"] >= 2).astype(int)

    # 3. Trend confirmation aligned with first break direction.
    break_dir_col = "first_break_dir" if "first_break_dir" in base.columns else None
    if break_dir_col and "ema_20_gt_50" in base.columns:
        ema_dir = np.where(base["ema_20_gt_50"], 1, -1)
        base["trend_aligned_with_break"] = (
            (base[break_dir_col].fillna(0) * ema_dir) > 0
        ).astype(int)
        base["trend_misaligned_with_break"] = (
            (base[break_dir_col].fillna(0) * ema_dir) < 0
        ).astype(int)

    # 4. First break direction vs 09:30 AVWAP agreement.
    if break_dir_col and "break_vs_avwap_0930" in base.columns:
        base["break_dir_matches_avwap0930"] = (
            base[break_dir_col].fillna(0) == base["break_vs_avwap_0930"].fillna(0)
        ).astype(int)

    # 5. Failure-prediction starter: conditions that historically predict break failure.
    failure_conditions = pd.Series(False, index=base.index)
    if "break_speed_bars" in base.columns:
        failure_conditions |= base["break_speed_bars"].fillna(999) > 30
    if "avwap_mixed" in base.columns:
        failure_conditions |= base["avwap_mixed"] == 1
    if "news_high_impact_present" in base.columns:
        # High-impact news overlapping IB raises noise; potential failure contributor.
        failure_conditions |= base["news_high_impact_present"] == 1
    # Also flag slow, late first breaks as candidate failures.
    if "first_break_minutes" in base.columns:
        failure_conditions |= base["first_break_minutes"].fillna(0) > 60
    base["fail_setup_score"] = failure_conditions.astype(int)

    return base


def main():
    parser = argparse.ArgumentParser(description="Build IB master confluence table")
    parser.add_argument(
        "--instruments", type=str, default=",".join(INSTRUMENTS),
        help="Comma-separated symbols (default: all)",
    )
    args = parser.parse_args()
    symbols = [s.strip().upper() for s in args.instruments.split(",") if s.strip()]

    DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    for sym in symbols:
        out_path = DERIVED_DIR / f"ib_confluence_{sym}.parquet"
        try:
            df = build_confluence(sym)
            df.to_parquet(out_path, index=False)
            logger.info("[%s] Wrote %s rows x %s cols to %s", sym, len(df), len(df.columns), out_path)
        except Exception as e:
            logger.error("[%s] Failed: %s", sym, e)
            raise


if __name__ == "__main__":
    main()
