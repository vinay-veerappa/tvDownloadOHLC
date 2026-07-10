"""Data freshness guard for the Narrative Engine v2.

Checks each Tier 1 data source for staleness before the narrative runs.
Returns warnings (not errors) — stale data is used but flagged.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)
_REPO = Path(__file__).resolve().parent.parent.parent  # tvDownloadOHLC root
_STALE_THRESHOLD_DAYS = 3


@dataclass
class FreshnessCheck:
    source: str
    last_date: str | None = None
    days_stale: int = 0
    is_stale: bool = False
    warning: str | None = None


def check_herman(ticker: str = "NQ1") -> FreshnessCheck:
    p = _REPO / "data" / "derived" / f"{ticker}_herman_stats.parquet"
    if not p.exists():
        return FreshnessCheck("herman", warning=f"File not found: {p.name}")
    df = pd.read_parquet(p)
    if df.empty:
        return FreshnessCheck("herman", warning="Empty parquet")
    last = df.iloc[-1].get("date")
    last_date = pd.to_datetime(last).date() if last is not None else None
    return _build_check("herman", last_date)


def check_classification(ticker: str = "NQ1") -> FreshnessCheck:
    p = _REPO / "data" / "derived" / f"{ticker}_daily_classification.parquet"
    if not p.exists():
        return FreshnessCheck("classification", warning=f"File not found: {p.name}")
    df = pd.read_parquet(p)
    if df.empty:
        return FreshnessCheck("classification", warning="Empty parquet")
    last = df.iloc[-1].get("date")
    last_date = pd.to_datetime(last).date() if last is not None else None
    return _build_check("classification", last_date)


def check_gex_levels() -> FreshnessCheck:
    p = _REPO / "data" / "options" / "unified_levels.json"
    if not p.exists():
        return FreshnessCheck("gex_levels", warning="File not found")
    import json
    em = json.load(open(p, "r", encoding="utf-8"))
    gen_at = em.get("generated_at", "")
    if not gen_at:
        return FreshnessCheck("gex_levels", warning="No generated_at timestamp")
    last_date = str(gen_at)[:10]
    return _build_check("gex_levels", pd.to_datetime(last_date).date() if last_date else None)


def _build_check(source: str, last_date: date | None) -> FreshnessCheck:
    if last_date is None:
        return FreshnessCheck(source, warning="No date found")
    days = (date.today() - last_date).days
    is_stale = days > _STALE_THRESHOLD_DAYS
    warn = f"STALE: {days} days behind" if is_stale else None
    return FreshnessCheck(source, str(last_date), days, is_stale, warn)


def check_all(ticker: str = "NQ1") -> list[FreshnessCheck]:
    """Check all Tier 1 data sources. Log warnings for stale ones."""
    checks = [
        check_herman(ticker),
        check_classification(ticker),
        check_gex_levels(),
    ]
    for c in checks:
        if c.warning:
            log.warning("[freshness] %s: %s (last=%s)", c.source, c.warning, c.last_date)
    return checks


def freshness_summary(checks: list[FreshnessCheck]) -> str:
    """One-line summary for the cheat sheet."""
    parts = []
    for c in checks:
        tag = "OK" if not c.is_stale else "STALE"
        parts.append(f"{c.source}:{tag}")
    return " | ".join(parts)