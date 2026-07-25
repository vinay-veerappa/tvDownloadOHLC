"""
IB News + OpEx Impact Builder — Phase 2.5

Reads `ib_facts_{SYM}.parquet`, queries the Prisma `EconomicEvent` table, and
joins deterministic OpEx calendar fields plus news-impact flags.

Output:
    data/derived/ib_news_opex_{SYM}.parquet

One row per (trading_day, session_slot, time_basis), aligned 1:1 with the
facts and derived files so it can be merged by index or composite key.
"""

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Dict, List, Optional

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

from scripts.edgeful.calendar_generator import generate_calendar
from scripts.libs_py.nqstats.ib import SESSION_CONFIGS_V5

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
logger = logging.getLogger(__name__)

DERIVED_DIR = Path("data/derived")
INSTRUMENTS = ["NQ1", "ES1", "YM1", "RTY1", "CL1", "GC1"]

# News window definitions in minutes-from-midnight ET.
NEWS_WINDOWS = {
    "news_0945_today": time(9, 45),
    "news_1000_today": time(10, 0),
    "news_1030_today": time(10, 30),
}
NEWS_TOLERANCE_MIN = 2  # for ib_news_break detection

IMPACT_RANK = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "none": -1}


def _event_category(name: str) -> str:
    """Map an economic release name to a compact category token."""
    nl = name.lower()
    if "crude oil inventories" in nl or "eia" in nl or "petroleum" in nl:
        return "OilInventory"
    if "ism manufacturing" in nl:
        return "ISM_Mfg"
    if "ism services" in nl or "ism non-manufacturing" in nl:
        return "ISM_Svc"
    if "s&p global manufacturing" in nl or "s&p global services" in nl:
        return "S&P_PMI"
    if "composite pmi" in nl or "pmi" in nl:
        return "PMI"
    if "consumer confidence" in nl or "consumer sentiment" in nl or "michigan" in nl:
        return "ConsumerConf"
    if "jolts" in nl or "job openings" in nl:
        return "JOLTS"
    if "pce" in nl:
        return "PCE"
    if "existing home sales" in nl or "new home sales" in nl or "housing" in nl or "building permits" in nl:
        return "Housing"
    if "fed chair" in nl or "powell" in nl or "speak" in nl or "testifies" in nl or "press conference" in nl:
        return "FedSpeak"
    return "Other"


async def _load_usd_events() -> pd.DataFrame:
    """Load USD events from Prisma and normalize to ET."""
    # Prisma async client expects DATABASE_URL env var.
    from prisma import Prisma

    db = Prisma()
    await db.connect()
    try:
        rows = await db.economicevent.find_many(where={"country": "USD"})
    finally:
        await db.disconnect()

    df = pd.DataFrame([
        {"datetime": e.datetime, "name": e.name, "impact": e.impact}
        for e in rows
    ])
    if df.empty:
        raise RuntimeError("No USD EconomicEvent rows found in Prisma DB")

    df["datetime"] = pd.to_datetime(df["datetime"], utc=True)
    df["et"] = df["datetime"].dt.tz_convert("America/New_York").dt.tz_localize(None)
    df["date"] = df["et"].dt.date
    df["minute"] = df["et"].dt.strftime("%H:%M")
    df["category"] = df["name"].apply(_event_category)
    return df


def _build_daily_news_lookup(events: pd.DataFrame) -> pd.DataFrame:
    """Aggregate target-time events into one row per trading date."""
    target = events[events["minute"].isin(["09:45", "10:00", "10:30"])].copy()
    # Only count MEDIUM/HIGH releases as market-moving by default.
    target = target[target["impact"].isin(["MEDIUM", "HIGH"])].copy()

    if target.empty:
        return pd.DataFrame(
            columns=[
                "trading_day", "news_0945_today", "news_1000_today",
                "news_1030_today", "news_impact_level", "news_release_name",
                "news_release_minutes",
            ]
        )

    def _agg_group(g: pd.DataFrame) -> pd.Series:
        has_0945 = bool((g["minute"] == "09:45").any())
        has_1000 = bool((g["minute"] == "10:00").any())
        has_1030 = bool((g["minute"] == "10:30").any())
        impacts = sorted(set(g["impact"]), key=lambda x: IMPACT_RANK[x], reverse=True)
        top_impact = impacts[0] if impacts else "none"
        cats = sorted(set(g["category"]))
        minutes = sorted(set(g["minute"]))
        return pd.Series({
            "news_0945_today": has_0945,
            "news_1000_today": has_1000,
            "news_1030_today": has_1030,
            "news_impact_level": top_impact,
            "news_release_name": "|".join(cats),
            "news_release_minutes": "|".join(minutes),
        })

    daily = target.groupby("date").apply(_agg_group).reset_index()
    daily = daily.rename(columns={"date": "trading_day"})
    daily["trading_day"] = daily["trading_day"].astype(str)
    return daily


def _build_opex_calendar(facts_dates: pd.Series) -> pd.DataFrame:
    """Build OpEx flags covering the facts date range plus buffer."""
    min_d = pd.to_datetime(facts_dates.min()).normalize() - pd.Timedelta(days=30)
    max_d = pd.to_datetime(facts_dates.max()).normalize() + pd.Timedelta(days=30)
    cal = generate_calendar(min_d.strftime("%Y-%m-%d"), max_d.strftime("%Y-%m-%d"))

    # Rename to match plan field names and add missing helper fields.
    cal = cal.rename(columns={"is_monthly_opex": "is_opex_friday",
                              "is_triple_witching": "is_quarterly_opex",
                              "days_to_monthly_opex": "days_to_opex"})
    cal["trading_day"] = cal["date"].astype(str)

    # opex_phase
    conditions = [
        cal["is_opex_friday"],
        cal["is_opex_week"],
        cal["days_to_opex"] <= 7,   # within a week before monthly opex
    ]
    choices = ["opex_friday", "opex_week", "pre_opex"]
    # post_opex if just passed but still within 2 calendar days after
    post_opex = (cal["days_to_opex"] >= 28) & (~cal["is_opex_week"]) & (~cal["is_opex_friday"])
    cal["opex_phase"] = np.select(conditions, choices, default=np.where(post_opex, "post_opex", "normal"))

    return cal[["trading_day", "is_opex_week", "is_opex_friday",
                "is_quarterly_opex", "days_to_opex", "opex_phase"]].copy()


def _minutes_from_midnight(t: time) -> int:
    return t.hour * 60 + t.minute


def _ib_start_minutes(row: pd.Series) -> int:
    """Return ib_start in minutes-from-midnight, handling event_anchored shifts."""
    base = SESSION_CONFIGS_V5[row["session_slot"]]["ib_start"]
    base_min = _minutes_from_midnight(base)
    # Only Tokyo/London event_anchored have offsets stored in et_window_offset_hours.
    if row.get("time_basis") == "event_anchored":
        offset = row.get("et_window_offset_hours", 0)
        if pd.isna(offset):
            offset = 0
        return base_min + int(offset) * 60
    return base_min


def _compute_news_break_fields(df: pd.DataFrame, news_lookup: pd.DataFrame) -> pd.DataFrame:
    """Add fields that depend on both news timing and first-break minutes."""
    df = df.merge(news_lookup, on="trading_day", how="left")
    for col in ["news_0945_today", "news_1000_today", "news_1030_today"]:
        df[col] = df[col].fillna(False).astype(bool)
    df["news_impact_level"] = df["news_impact_level"].fillna("none")
    df["news_release_name"] = df["news_release_name"].fillna("")
    df["news_release_minutes"] = df["news_release_minutes"].fillna("")

    # ib_news_distorted: a 09:45 release occurred during NY AM IB formation (9:30-10:30)
    df["ib_start_min"] = df.apply(_ib_start_minutes, axis=1)
    df["ib_end_min"] = df["ib_start_min"] + 60  # IB is one hour by config
    news_0945_min = 9 * 60 + 45
    df["ib_news_distorted"] = (
        (df["session_slot"] == "NY AM IB")
        & df["news_0945_today"]
        & (news_0945_min >= df["ib_start_min"])
        & (news_0945_min < df["ib_end_min"])
    )

    # minutes_since_news: from the last 09:45/10:00/10:30 release to first break.
    # first_break_minutes is measured from ib_start.
    def _last_news_min(row):
        minutes = []
        if row["news_0945_today"]:
            minutes.append(9 * 60 + 45)
        if row["news_1000_today"]:
            minutes.append(10 * 60)
        if row["news_1030_today"]:
            minutes.append(10 * 60 + 30)
        if not minutes:
            return np.nan
        # Last release within or before IB outcome window.
        # Filter to releases at or after ib_start (only news during/after IB start matters).
        ib_start = row["ib_start_min"]
        valid = [m for m in minutes if m >= ib_start]
        if not valid:
            valid = minutes  # allow pre-IB releases for Tokyo/London sessions
        return max(valid)

    df["last_news_min_from_midnight"] = df.apply(_last_news_min, axis=1)
    df["minutes_since_news"] = df["first_break_minutes"] - (df["last_news_min_from_midnight"] - df["ib_start_min"])
    # Bucket to 5-min grid to match plan requirement.
    df["minutes_since_news_5min"] = (df["minutes_since_news"] // 5 * 5).where(df["minutes_since_news"].notna())

    # ib_news_break: first break within NEWS_TOLERANCE_MIN of 10:00 or 10:30 release,
    # and session is NY AM IB (the session most affected by these releases).
    def _news_break(row):
        if row["session_slot"] != "NY AM IB" or pd.isna(row["first_break_minutes"]):
            return False
        fb = row["first_break_minutes"]
        release_offsets = []
        if row["news_1000_today"]:
            release_offsets.append(10 * 60 - row["ib_start_min"])
        if row["news_1030_today"]:
            release_offsets.append(10 * 60 + 30 - row["ib_start_min"])
        return any(abs(fb - ro) <= NEWS_TOLERANCE_MIN for ro in release_offsets)

    df["ib_news_break"] = df.apply(_news_break, axis=1)

    return df


def _compute_opex_range_pctile(df: pd.DataFrame) -> pd.Series:
    """Compute IB range percentile within the last 12 months of opex-week rows."""
    df = df.copy()
    df["_dt"] = pd.to_datetime(df["trading_day"])
    df = df.sort_values(["symbol", "session_slot", "time_basis", "_dt"])

    def _pctile_within_opex(g: pd.DataFrame) -> pd.Series:
        # Collect opex-week rows; expand window as we move forward in time.
        opex_ranges: List[float] = []
        out = pd.Series(np.nan, index=g.index)
        for idx, row in g.iterrows():
            if row["is_opex_week"] and pd.notna(row["ib_range"]):
                # Compute percentile of current row within observed opex-week ranges so far.
                if opex_ranges:
                    out.loc[idx] = sum(r <= row["ib_range"] for r in opex_ranges) / len(opex_ranges)
                # Append current row after computing its percentile (causal).
                opex_ranges.append(row["ib_range"])
                # Keep rolling 12 months ~ 52 weeks of opex entries max.
                if len(opex_ranges) > 52:
                    opex_ranges.pop(0)
        return out

    return df.groupby(["symbol", "session_slot", "time_basis"], group_keys=False).apply(_pctile_within_opex)


def process_symbol(symbol: str, news_lookup: pd.DataFrame, opex_cal: pd.DataFrame) -> pd.DataFrame:
    """Build news/opex derived fields for one symbol."""
    logger.info("[%s] Loading facts", symbol)
    facts_path = DERIVED_DIR / f"ib_facts_{symbol}.parquet"
    if not facts_path.exists():
        raise FileNotFoundError(f"Missing {facts_path}")
    df = pd.read_parquet(facts_path)
    df["trading_day"] = df["trading_day"].astype(str)
    df["symbol"] = symbol

    logger.info("[%s] Joining OpEx calendar", symbol)
    df = df.merge(opex_cal, on="trading_day", how="left")
    df["is_opex_week"] = df["is_opex_week"].fillna(False).astype(bool)
    df["is_opex_friday"] = df["is_opex_friday"].fillna(False).astype(bool)
    df["is_quarterly_opex"] = df["is_quarterly_opex"].fillna(False).astype(bool)
    df["days_to_opex"] = df["days_to_opex"].fillna(np.nan)
    df["opex_phase"] = df["opex_phase"].fillna("normal")

    logger.info("[%s] Joining news fields", symbol)
    df = _compute_news_break_fields(df, news_lookup)

    logger.info("[%s] Computing OpEx range percentile", symbol)
    df["opex_ib_range_pctile"] = _compute_opex_range_pctile(df)

    keep = [
        "symbol", "trading_day", "session_slot", "time_basis",
        "news_0945_today", "news_1000_today", "news_1030_today",
        "news_impact_level", "news_release_name",
        "ib_news_distorted", "ib_news_break",
        "minutes_since_news", "minutes_since_news_5min",
        "is_opex_week", "is_opex_friday", "is_quarterly_opex",
        "days_to_opex", "opex_phase", "opex_ib_range_pctile",
    ]
    out = df[[c for c in keep if c in df.columns]].copy()
    return out


def main():
    parser = argparse.ArgumentParser(description="Build IB news/OpEx impact fields")
    parser.add_argument("--instruments", type=str, default=",".join(INSTRUMENTS),
                        help="Comma-separated symbols (default: all)")
    parser.add_argument("--prisma-url", type=str, default=None,
                        help="Prisma DATABASE_URL override")
    args = parser.parse_args()
    symbols = [s.strip().upper() for s in args.instruments.split(",") if s.strip()]

    if args.prisma_url:
        os.environ["DATABASE_URL"] = args.prisma_url
    elif "DATABASE_URL" not in os.environ:
        # Fallback to absolute file path if not set.
        os.environ["DATABASE_URL"] = "file:C:/Users/vinay/tvDownloadOHLC/web/prisma/dev.db"

    DERIVED_DIR.mkdir(parents=True, exist_ok=True)

    logger.info("Loading USD events from Prisma")
    events = asyncio.run(_load_usd_events())
    news_lookup = _build_daily_news_lookup(events)
    logger.info("News lookup ready: %s unique days", len(news_lookup))

    # Build OpEx calendar once using min/max trading_day across all facts.
    all_dates = []
    for sym in symbols:
        p = DERIVED_DIR / f"ib_facts_{sym}.parquet"
        if p.exists():
            td = pd.read_parquet(p, columns=["trading_day"])["trading_day"]
            all_dates.append(td)
    if not all_dates:
        raise FileNotFoundError("No fact files found for date range")
    all_dates = pd.concat(all_dates)
    all_dates = pd.to_datetime(all_dates).dt.date.astype(str)
    opex_cal = _build_opex_calendar(all_dates)

    for sym in symbols:
        out_path = DERIVED_DIR / f"ib_news_opex_{sym}.parquet"
        try:
            df = process_symbol(sym, news_lookup, opex_cal)
            df.to_parquet(out_path, index=False)
            logger.info("[%s] Wrote %s rows to %s", sym, len(df), out_path)
        except Exception as e:
            logger.error("[%s] Failed: %s", sym, e)
            raise


if __name__ == "__main__":
    main()
