"""
Daily Context Computation

Computes comprehensive once-per-day context variables for all symbols.
Builds DailyContext dataclass with VIX, gap, PDH/PDL, streaks, event flags, etc.

This is the architectural centerpiece: every module reads from daily_context.parquet
instead of computing context independently. Ensures consistency and eliminates duplication.
"""

import pandas as pd
import numpy as np
import sqlite3
from pathlib import Path
from dataclasses import dataclass, asdict, fields
from typing import Optional, List, Dict
from datetime import date, datetime, timedelta
import logging

logger = logging.getLogger(__name__)

# Event type categorization: expanded beyond just FOMC/CPI/NFP/OPEX
# Maps event name patterns to categories
EVENT_CATEGORIES = {
    # Highest impact
    "FOMC": ["FOMC", "federal open market committee"],
    "NFP": ["nonfarm payroll", "employment situation", "jobs report", "payroll"],
    "CPI": ["consumer price", "CPI", "inflation"],
    "PPI": ["producer price", "PPI"],
    
    # Major
    "OPEX": ["opex", "options expiration"],
    "ECB": ["ECB", "european central bank"],
    "BOE": ["bank of england", "BOE"],
    "BOJ": ["bank of japan", "BOJ"],
    "PMI": ["PMI", "purchasing managers"],
    "ISM": ["ISM", "manufacturing", "services"],
    "GDP": ["GDP", "gross domestic"],
    "EARNINGS": ["earnings", "earnings season"],
    
    # Medium
    "RETAIL": ["retail sales", "retail"],
    "HOUSING": ["housing", "home sales", "construction starts", "building permits"],
    "INCOME": ["consumer income", "wages", "wage growth"],
    "CLAIMS": ["jobless claims", "initial claims", "unemployment claims"],
    "CONFERENCE": ["conference board", "consumer confidence"],
    "DURABLE": ["durable goods"],
    "OIL": ["crude oil", "inventory"],
    "ENERGY": ["energy"],
    "RATES": ["interest rate", "rate decision", "rate cut", "rate hike"],
}


@dataclass
class DailyContext:
    """
    One row per (symbol, trading_date). Canonical source for all context variables.
    
    Written to: data/derived/daily_context.parquet
    Used by: All modules for universal filter dimensions and context joins.
    """
    
    symbol: str
    trading_date: date
    day_of_week: int                    # 0=Mon..4=Fri
    
    # ── VIX / Volatility ────────────────────────────────────────
    vix_close: Optional[float]           # Prior day VIX close
    vix_regime: str                     # LOW (<15), NORMAL (15-25), HIGH (25-35), EXTREME (>35)
    vix_pctile_60d: Optional[float]     # Percentile rank over trailing 60d
    
    # ── ATR ─────────────────────────────────────────────────────
    atr_14d: float                      # 14-day ATR (points)
    session_range: float                # Today's RTH high - low
    atr_usage_pct: float                # session_range / atr_14d * 100
    atr_respected: bool                 # session_range <= atr_14d
    
    # ── Prior Day Levels ────────────────────────────────────────
    pdh: float                          # Prior Day High (RTH)
    pdl: float                          # Prior Day Low (RTH)
    pdc: float                          # Prior Day Close
    pd_mid: float                       # (PDH + PDL) / 2
    pd_range: float                     # PDH - PDL
    
    # ── Gap ─────────────────────────────────────────────────────
    session_open: float                 # First RTH bar open (09:30)
    gap_size_points: float              # session_open - pdc (signed)
    gap_size_pct: float                 # gap / pdc * 100
    gap_direction: str                  # "UP", "DOWN", "NONE" (threshold: ±0.05%)
    gap_size_bucket: str                # "NONE", "SMALL" (<0.25%), "MEDIUM" (0.25-0.5%), "LARGE" (>0.5%)
    gap_filled: bool                    # Did price reach pdc during session?
    gap_fill_time_minutes: Optional[float]  # Minutes to fill gap
    
    # ── Overnight / Globex ──────────────────────────────────────
    overnight_high: float               # ETH high between prior RTH close and today's RTH open
    overnight_low: float
    midnight_open: float                # Open of 00:00 ET candle
    
    # ── Open Location ───────────────────────────────────────────
    open_vs_pd_range: str               # "ABOVE_PDH", "INSIDE", "BELOW_PDL"
    open_vs_midnight: str               # "ABOVE", "BELOW"
    is_inside_day: bool                 # Today's developing range inside PD range
    is_outside_day: bool                # Opened outside PD range
    
    # ── Session Outcome (filled at end of day) ──────────────────
    session_close: Optional[float]      # Close at 16:00 (or NaT if intraday)
    session_direction: Optional[str]    # "GREEN" (close > open), "RED"
    pdh_broken: bool
    pdl_broken: bool
    both_pd_broken: bool                # Outside day — broke both PDH and PDL
    pdh_break_time_minutes: Optional[float]
    pdl_break_time_minutes: Optional[float]
    
    # ── Streaks ─────────────────────────────────────────────────
    streak_length: int                  # Consecutive same-direction days (including today)
    streak_direction: str               # "GREEN" or "RED"
    
    # ── Events ──────────────────────────────────────────────────
    is_event_day: bool
    event_type: Optional[str]           # "FOMC", "NFP", "CPI", "PMI", etc. (None if no match)
    event_types: List[str]              # Multiple possible categories
    is_opex_week: bool
    
    # ── Weekly Levels ───────────────────────────────────────────
    prior_week_high: Optional[float]
    prior_week_low: Optional[float]
    prior_week_close: Optional[float]
    weekly_open: Optional[float]        # Monday's open


def classify_event_type(event_name: str) -> Optional[str]:
    """
    Map economic event name to category.
    
    Returns the first matching category, or None if no match.
    Used for filtering and analysis.
    """
    if not event_name:
        return None
    
    event_lower = event_name.lower()
    for category, keywords in EVENT_CATEGORIES.items():
        for keyword in keywords:
            if keyword.lower() in event_lower:
                return category
    
    return None


def classify_event_types(event_name: str) -> List[str]:
    """
    Map economic event name to all matching categories.
    
    Returns list of matching categories (could be multiple,  e.g., "FOMC Decision" -> ["FOMC", "RATES"]).
    """
    if not event_name:
        return []
    
    matches = []
    event_lower = event_name.lower()
    
    for category, keywords in EVENT_CATEGORIES.items():
        for keyword in keywords:
            if keyword.lower() in event_lower:
                matches.append(category)
                break  # Only count once per category
    
    return matches


class DailyContextBuilder:
    """
    Builds DailyContext records for all symbols and dates.
    
    Requires:
      - 1m OHLCV data (from DataLoader)
      - VIX daily data (from DataLoader)
      - Economic events (from Prisma DB)
      - Prior day levels (from yesterday's close)
    """
    
    def __init__(self, data_loader, prisma_db_path: Path = None):
        self.loader = data_loader
        self.prisma_db = prisma_db_path or Path("web/prisma/dev.db")
        self._vix_cache = None
        self._events_cache = None
    
    def compute_for_symbol(self, symbol: str) -> pd.DataFrame:
        """
        Compute DailyContext for all available trading dates for a symbol.
        
        Returns:
            DataFrame with columns matching DailyContext fields.
        """
        logger.info(f"Computing DailyContext for {symbol}...")

        # 1) Load + tag once (ADR-001 boundary: ET naive inside pipeline)
        df_1m = self.loader.load_1m(symbol)
        if df_1m.empty:
            logger.warning(f"No data for {symbol}")
            return pd.DataFrame()

        from .session_tagger import tag_session
        df_1m = tag_session(df_1m)

        df_1m = df_1m.sort_index()
        rth = df_1m[df_1m["is_rth"]].copy()
        if rth.empty:
            logger.warning(f"No valid trading days for {symbol}")
            return pd.DataFrame()

        # 2) One-pass daily RTH aggregation
        daily = rth.groupby("trading_date", sort=True).agg(
            session_open=("open", "first"),
            session_high=("high", "max"),
            session_low=("low", "min"),
            session_close=("close", "last"),
        )
        daily.index.name = "trading_date"

        td_index = pd.to_datetime(daily.index)
        daily["day_of_week"] = td_index.weekday
        daily["session_range"] = daily["session_high"] - daily["session_low"]

        # 3) Prior-day levels and ATR (vectorized)
        daily["pdh"] = daily["session_high"].shift(1)
        daily["pdl"] = daily["session_low"].shift(1)
        daily["pdc"] = daily["session_close"].shift(1)
        daily["pd_mid"] = (daily["pdh"] + daily["pdl"]) / 2.0
        daily["pd_range"] = daily["pdh"] - daily["pdl"]

        true_range = pd.concat([
            daily["session_high"] - daily["session_low"],
            (daily["session_high"] - daily["pdc"]).abs(),
            (daily["session_low"] - daily["pdc"]).abs(),], axis=1).max(axis=1)

        daily["atr_14d"] = true_range.rolling(14, min_periods=1).mean()
        daily["atr_usage_pct"] = np.where(
            daily["atr_14d"] > 0,
            (daily["session_range"] / daily["atr_14d"]) * 100.0,
            0.0,
        )
        daily["atr_respected"] = daily["session_range"] <= daily["atr_14d"]

        # 4) Gap and open-location features
        daily["gap_size_points"] = daily["session_open"] - daily["pdc"]
        daily["gap_size_pct"] = np.where(
            daily["pdc"].notna() & (daily["pdc"] != 0),
            (daily["gap_size_points"] / daily["pdc"]) * 100.0,
            0.0,
        )
        abs_gap_pct = daily["gap_size_pct"].abs()
        daily["gap_direction"] = np.where(
            abs_gap_pct < 0.05,
            "NONE",
            np.where(daily["gap_size_pct"] > 0, "UP", "DOWN"),
        )
        daily["gap_size_bucket"] = np.select(
            [
                daily["gap_direction"] == "NONE",
                abs_gap_pct < 0.25,
                abs_gap_pct < 0.5,
            ],
            ["NONE", "SMALL", "MEDIUM"],
            default="LARGE",
        )

        has_pd = daily["pdh"].notna() & daily["pdl"].notna()
        daily["open_vs_pd_range"] = np.select(
            [
                has_pd & (daily["session_open"] > daily["pdh"]),
                has_pd & (daily["session_open"] < daily["pdl"]),
            ],
            ["ABOVE_PDH", "BELOW_PDL"],
            default="INSIDE",
        )
        daily["is_outside_day"] = daily["open_vs_pd_range"] != "INSIDE"
        daily["is_inside_day"] = has_pd & (daily["session_high"] <= daily["pdh"]) & (daily["session_low"] >= daily["pdl"])

        # 5) Prior-day break outcomes
        daily["pdh_broken"] = has_pd & (daily["session_high"] > daily["pdh"])
        daily["pdl_broken"] = has_pd & (daily["session_low"] < daily["pdl"])
        daily["both_pd_broken"] = daily["pdh_broken"] & daily["pdl_broken"]

        daily["session_direction"] = np.where(daily["session_close"] >= daily["session_open"], "GREEN", "RED")
        direction_change = daily["session_direction"].ne(daily["session_direction"].shift(1))
        streak_groups = direction_change.cumsum()
        daily["streak_length"] = daily.groupby(streak_groups).cumcount() + 1
        daily["streak_direction"] = daily["session_direction"]

        # 6) Intraday timing metrics (gap fill, PD breaks)
        rth_idx = rth.reset_index().rename(columns={"index": "datetime"})
        rth_open = rth_idx.groupby("trading_date", as_index=True)["datetime"].min().rename("rth_open_ts")
        rth_idx = rth_idx.merge(rth_open, on="trading_date", how="left")
        rth_enriched = rth_idx.merge(
            daily[["pdc", "pdh", "pdl", "gap_direction"]],
            left_on="trading_date",
            right_index=True,
            how="left",
        )

        gap_fill_minutes = self._first_hit_minutes(
            rth_enriched,
            ((rth_enriched["gap_direction"] == "UP") & (rth_enriched["low"] <= rth_enriched["pdc"]))
            | ((rth_enriched["gap_direction"] == "DOWN") & (rth_enriched["high"] >= rth_enriched["pdc"])),
        )
        pdh_break_minutes = self._first_hit_minutes(
            rth_enriched,
            rth_enriched["pdh"].notna() & (rth_enriched["high"] > rth_enriched["pdh"]),
        )
        pdl_break_minutes = self._first_hit_minutes(
            rth_enriched,
            rth_enriched["pdl"].notna() & (rth_enriched["low"] < rth_enriched["pdl"]),
        )

        daily["gap_fill_time_minutes"] = gap_fill_minutes.reindex(daily.index)
        daily["gap_filled"] = daily["gap_fill_time_minutes"].notna()
        daily["pdh_break_time_minutes"] = pdh_break_minutes.reindex(daily.index)
        daily["pdl_break_time_minutes"] = pdl_break_minutes.reindex(daily.index)

        # 7) Overnight and midnight features (pre-RTH only, avoids lookahead)
        full_idx = df_1m.reset_index().rename(columns={"index": "datetime"})
        full_idx = full_idx.merge(rth_open, on="trading_date", how="left")
        pre_rth = full_idx[(full_idx["datetime"] < full_idx["rth_open_ts"]) & (~full_idx["is_rth"])]
        overnight = pre_rth.groupby("trading_date").agg(
            overnight_high=("high", "max"),
            overnight_low=("low", "min"),
        )
        daily = daily.join(overnight, how="left")

        midnight_mask = (full_idx["datetime"].dt.hour == 0) & (full_idx["datetime"].dt.minute == 0)
        midnight_open = (
            full_idx[midnight_mask]
            .groupby("trading_date")["open"]
            .first()
            .rename("midnight_open")
        )
        daily = daily.join(midnight_open, how="left")
        daily["open_vs_midnight"] = np.where(
            daily["midnight_open"].notna() & (daily["session_open"] < daily["midnight_open"]),
            "BELOW",
            "ABOVE",
        )

        # 8) VIX context (single vectorized merge_asof)
        vix_context = self._build_vix_context(daily.index)
        daily = daily.join(vix_context, how="left")
        daily["vix_regime"] = daily["vix_regime"].fillna("NORMAL")

        # 9) Economic events (single DB load, date-level join)
        events = self._load_events_by_date()
        if not events.empty:
            daily = daily.join(events, how="left")
        else:
            daily["is_event_day"] = False
            daily["event_type"] = None
            daily["event_types"] = [[] for _ in range(len(daily))]

        daily["is_event_day"] = daily["is_event_day"].where(daily["is_event_day"].notna(), False).astype(bool)
        daily["event_type"] = daily["event_type"].where(daily["event_type"].notna(), None)
        daily["event_types"] = daily["event_types"].apply(lambda v: v if isinstance(v, list) else [])

        # 10) OPEX week (vectorized calendar math)
        td_series = pd.Series(pd.to_datetime(daily.index), index=daily.index)
        month_start = td_series.dt.to_period("M").dt.to_timestamp()
        first_friday = month_start + pd.to_timedelta((4 - month_start.dt.weekday) % 7, unit="D")
        opex_date = first_friday + pd.to_timedelta(14, unit="D")
        week_start = td_series - pd.to_timedelta(td_series.dt.weekday, unit="D")
        week_end = week_start + pd.to_timedelta(4, unit="D")
        daily["is_opex_week"] = (opex_date >= week_start) & (opex_date <= week_end)

        # 11) Weekly levels
        out = daily.reset_index().rename(columns={"index": "trading_date"})
        out["td"] = pd.to_datetime(out["trading_date"])
        out["week_start"] = out["td"] - pd.to_timedelta(out["td"].dt.weekday, unit="D")

        week_agg = out.groupby("week_start").agg(
            week_high=("session_high", "max"),
            week_low=("session_low", "min"),
            week_close=("session_close", "last"),
            weekly_open=("session_open", "first"),
        )
        week_agg["prior_week_high"] = week_agg["week_high"].shift(1)
        week_agg["prior_week_low"] = week_agg["week_low"].shift(1)
        week_agg["prior_week_close"] = week_agg["week_close"].shift(1)

        out = out.merge(
            week_agg[["prior_week_high", "prior_week_low", "prior_week_close", "weekly_open"]],
            left_on="week_start",
            right_index=True,
            how="left",
        )

        # 12) Final shape + defaults in dataclass field order
        out["symbol"] = symbol
        out["trading_date"] = out["td"].dt.date

        out = out.rename(
            columns={
                "session_open": "session_open",
                "session_close": "session_close",
            }
        )

        numeric_zero_defaults = [
            "pdh", "pdl", "pdc", "pd_mid", "pd_range",
            "gap_size_points", "gap_size_pct",
            "overnight_high", "overnight_low", "midnight_open",
        ]
        for col in numeric_zero_defaults:
            out[col] = out[col].fillna(0.0)

        out["vix_regime"] = out["vix_regime"].fillna("NORMAL")
        out["gap_direction"] = out["gap_direction"].fillna("NONE")
        out["gap_size_bucket"] = out["gap_size_bucket"].fillna("NONE")
        out["open_vs_pd_range"] = out["open_vs_pd_range"].fillna("INSIDE")
        out["open_vs_midnight"] = out["open_vs_midnight"].fillna("ABOVE")

        # Ensure booleans are proper bool dtype
        bool_cols = [
            "atr_respected", "gap_filled", "is_inside_day", "is_outside_day",
            "pdh_broken", "pdl_broken", "both_pd_broken", "is_event_day", "is_opex_week",
        ]
        for col in bool_cols:
            out[col] = out[col].fillna(False).astype(bool)

        required_cols = [f.name for f in fields(DailyContext)]
        for col in required_cols:
            if col not in out.columns:
                out[col] = None

        out = out[required_cols]
        return out.sort_values("trading_date").reset_index(drop=True)

    def _first_hit_minutes(self, frame: pd.DataFrame, condition: pd.Series) -> pd.Series:
        """Return first-hit minutes from RTH open for each trading_date where condition is met."""
        hits = frame.loc[condition, ["trading_date", "datetime", "rth_open_ts"]]
        if hits.empty:
            return pd.Series(dtype="float64")

        first_hits = hits.sort_values(["trading_date", "datetime"]).drop_duplicates("trading_date")
        minutes = (first_hits["datetime"] - first_hits["rth_open_ts"]).dt.total_seconds() / 60.0
        minutes.index = first_hits["trading_date"]
        return minutes

    def _build_vix_context(self, trading_dates: pd.Index) -> pd.DataFrame:
        """Build prior-day VIX context aligned to trading_date using merge_asof."""
        try:
            if self._vix_cache is not None:
                return self._vix_cache.reindex(trading_dates)

            vix_df = self.loader.load_vix()
            if vix_df.empty:
                self._vix_cache = pd.DataFrame(index=pd.Index([], name="trading_date"))
                return self._vix_cache.reindex(trading_dates)

            vix_daily = (
                vix_df.reset_index()
                .assign(vix_date=lambda x: pd.to_datetime(x["datetime"]).dt.normalize())
                .groupby("vix_date", as_index=False)["close"].last()
                .sort_values("vix_date")
            )

            vix_daily["vix_pctile_60d"] = (
                vix_daily["close"]
                .rolling(60, min_periods=1)
                .apply(lambda x: float((x < x[-1]).sum()) / float(len(x)) * 100.0, raw=True)
            )
            vix_daily["vix_regime"] = np.select(
                [
                    vix_daily["close"] < 15,
                    vix_daily["close"] < 25,
                    vix_daily["close"] < 35,
                ],
                ["LOW", "NORMAL", "HIGH"],
                default="EXTREME",
            )

            td = pd.DataFrame({"trading_date": pd.to_datetime(pd.Index(trading_dates).astype(str)).normalize()})
            td = td.sort_values("trading_date")
            td["lookup_date"] = td["trading_date"] - pd.Timedelta(days=1)

            merged = pd.merge_asof(
                td,
                vix_daily[["vix_date", "close", "vix_regime", "vix_pctile_60d"]].sort_values("vix_date"),
                left_on="lookup_date",
                right_on="vix_date",
                direction="backward",
            )
            merged = merged.rename(columns={"close": "vix_close"})
            merged["trading_date"] = merged["trading_date"].dt.date
            self._vix_cache = merged.set_index("trading_date")[["vix_close", "vix_regime", "vix_pctile_60d"]]
            return self._vix_cache.reindex(trading_dates)
        except Exception as e:
            logger.warning(f"Failed to build VIX context: {e}")
            return pd.DataFrame(index=trading_dates)

    def _load_events_by_date(self) -> pd.DataFrame:
        """Load high/medium impact events once and aggregate by ET date."""
        if self._events_cache is not None:
            return self._events_cache

        if not self.prisma_db.exists():
            self._events_cache = pd.DataFrame(index=pd.Index([], name="trading_date"))
            return self._events_cache

        try:
            conn = sqlite3.connect(str(self.prisma_db))
            events = pd.read_sql_query(
                """
                SELECT datetime, name
                FROM EconomicEvent
                WHERE impact IN ('HIGH', 'MEDIUM')
                  AND datetime IS NOT NULL
                  AND name IS NOT NULL
                ORDER BY datetime
                """,
                conn,
            )
            conn.close()

            if events.empty:
                self._events_cache = pd.DataFrame(index=pd.Index([], name="trading_date"))
                return self._events_cache

            dt_utc = pd.to_datetime(events["datetime"], utc=True, errors="coerce")
            dt_et = dt_utc.dt.tz_convert("America/New_York").dt.tz_localize(None)
            events["trading_date"] = dt_et.dt.date

            grouped = (
                events.dropna(subset=["trading_date", "name"])
                .groupby("trading_date")["name"]
                .apply(lambda s: sorted(set(s.tolist())))
                .to_frame(name="event_names")
            )

            grouped["is_event_day"] = True
            grouped["event_type"] = grouped["event_names"].apply(
                lambda names: classify_event_type(names[0]) if names else None
            )

            def _collect_types(names: List[str]) -> List[str]:
                all_types = set()
                for n in names:
                    all_types.update(classify_event_types(n))
                return sorted(all_types)

            grouped["event_types"] = grouped["event_names"].apply(_collect_types)
            self._events_cache = grouped[["is_event_day", "event_type", "event_types"]]
            return self._events_cache
        except Exception as e:
            logger.warning(f"Failed to load economic events: {e}")
            self._events_cache = pd.DataFrame(index=pd.Index([], name="trading_date"))
            return self._events_cache
