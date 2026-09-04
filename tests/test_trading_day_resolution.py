"""Regression: premarket/open/intraday narratives must anchor on the trading
day whose session is about to run (or is running), not the last completed RTH
day.

Defect observed 2026-09-04: the premarket narrative ran at 05:46 ET on
Friday and resolved target_date via get_latest_rth_date() -> Thursday
(Friday had no RTH bars yet), so the weekly event timeline marked Thursday
as today, Thursday's red-folder events got [TODAY], and the day type read
"Thursday" instead of "NFP Friday".

close mode keeps the completed-session anchor on purpose (EOD narrative
running after midnight ET analyzes the finished session).
"""

from __future__ import annotations

import inspect
import re
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest


ET_TZ = ZoneInfo("America/New_York")

from scripts.trader.trader_narrative import _resolve_upcoming_trading_day


class TestResolveUpcomingTradingDay:
    def test_friday_premarket_resolves_friday(self) -> None:
        # The live defect: 05:46 ET Friday must be Friday, not Thursday.
        now = datetime(2026, 9, 4, 5, 46, tzinfo=ET_TZ)
        assert _resolve_upcoming_trading_day(now) == date(2026, 9, 4)

    def test_monday_overnight_resolves_monday(self) -> None:
        # Monday 00:30 ET — Monday's Globex session is underway.
        now = datetime(2026, 9, 7, 0, 30, tzinfo=ET_TZ)
        assert _resolve_upcoming_trading_day(now) == date(2026, 9, 7)

    def test_evening_run_resolves_next_weekday(self) -> None:
        # Friday 18:30 ET — Asia session belongs to Monday.
        now = datetime(2026, 9, 4, 18, 30, tzinfo=ET_TZ)
        assert _resolve_upcoming_trading_day(now) == date(2026, 9, 7)

    def test_weekend_run_rolls_back_to_friday(self) -> None:
        now = datetime(2026, 9, 5, 10, 0, tzinfo=ET_TZ)  # Saturday
        assert _resolve_upcoming_trading_day(now) == date(2026, 9, 4)

    def test_sunday_run_rolls_back_to_friday(self) -> None:
        now = datetime(2026, 9, 6, 15, 0, tzinfo=ET_TZ)  # Sunday
        assert _resolve_upcoming_trading_day(now) == date(2026, 9, 4)

    def test_friday_evening_skips_weekend(self) -> None:
        now = datetime(2026, 9, 4, 19, 0, tzinfo=ET_TZ)
        assert _resolve_upcoming_trading_day(now) == date(2026, 9, 7)


class TestModeAwareResolution:
    """close keeps the RTH-anchored fallback; the other three modes use the
    upcoming-day resolution. Guard the source so the split cannot regress."""

    def test_close_mode_uses_rth_anchor(self) -> None:
        from scripts.trader import trader_narrative
        src = inspect.getsource(trader_narrative)
        close_branch = re.search(
            r'if mode == "close":\n(.*?)else:\n\s*# premarket', src, re.DOTALL
        )
        assert close_branch, "close branch of target_date resolution not found"
        assert "get_latest_rth_date" in close_branch.group(1)

    def test_non_close_modes_use_upcoming_day_helper(self) -> None:
        from scripts.trader import trader_narrative
        src = inspect.getsource(trader_narrative)
        m = re.search(r"_resolve_upcoming_trading_day\(datetime\.now\(ET\)\)", src)
        assert m, "premarket/open/intraday must resolve via _resolve_upcoming_trading_day"