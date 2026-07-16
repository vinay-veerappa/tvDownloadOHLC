"""Tests for audit §2.7 fix: `load_daily_price_context` now reads
the daily-timeframe parquet directly, with a freshness check and
RTH-filtered 1m fallback.

The fix replaces the original implementation (which resampled
the full 1m feed to a daily bar — the audit flagged that the
`last` aggregator picks up a 20:00 Globex print, not the 16:00
settlement).
"""

from __future__ import annotations

import importlib
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

import pandas as pd
import pytest


# ── _rth_filter_1m_to_daily ──────────────────────────────────────


class TestRthFilter:
    """The RTH filter drops Globex bars and keeps only the
    09:30-16:00 ET window."""

    def _df_with_index(self, times: list[str], closes: list[float]) -> pd.DataFrame:
        idx = pd.DatetimeIndex([pd.Timestamp(t).tz_localize("America/New_York") for t in times])
        return pd.DataFrame(
            {"open": closes, "high": closes, "low": closes, "close": closes, "volume": [1] * len(closes)},
            index=idx,
        )

    def test_keeps_rth_bars_drops_globex(self) -> None:
        from scripts.trader.briefing_core import _rth_filter_1m_to_daily
        df = self._df_with_index(
            [
                "2026-07-14 08:00:00",  # Globex pre-open
                "2026-07-14 09:30:00",  # RTH open
                "2026-07-14 12:00:00",  # midday
                "2026-07-14 16:00:00",  # RTH close (settlement)
                "2026-07-14 20:00:00",  # Globex post-close
            ],
            [100.0, 101.0, 102.0, 103.0, 999.0],
        )
        rth = _rth_filter_1m_to_daily(df)
        # 4 bars in, 1 out.
        assert len(rth) == 1
        row = rth.iloc[0]
        # close is the last RTH bar (16:00 = 103.0), NOT the 20:00 Globex print.
        assert row["close"] == 103.0
        assert row["open"] == 101.0
        assert row["high"] == 103.0
        assert row["low"] == 101.0

    def test_returns_empty_for_non_datetimeindex(self) -> None:
        from scripts.trader.briefing_core import _rth_filter_1m_to_daily
        df = pd.DataFrame({"close": [1.0, 2.0]})  # RangeIndex, no datetime
        out = _rth_filter_1m_to_daily(df)
        assert out.empty

    def test_handles_16_00_inclusive(self) -> None:
        """The 16:00 bar is the settlement print — `between_time`
        is inclusive on both ends, so the 16:00 bar's open is
        included as the daily open/close depending on aggregator."""
        from scripts.trader.briefing_core import _rth_filter_1m_to_daily
        df = self._df_with_index(
            ["2026-07-14 16:00:00", "2026-07-14 16:01:00"],
            [100.0, 200.0],
        )
        rth = _rth_filter_1m_to_daily(df)
        # 16:00 included, 16:01 excluded.
        assert len(rth) == 1
        assert rth.iloc[0]["close"] == 100.0


# ── _is_daily_fresh ──────────────────────────────────────────────


class TestIsDailyFresh:
    """The freshness check decides whether to trust the daily
    parquet or fall back to the RTH-filtered 1m."""

    def _df(self, unix_ts: int) -> pd.DataFrame:
        return pd.DataFrame({"time": [unix_ts], "open": [1.0], "close": [1.0]})

    def test_today_is_fresh(self) -> None:
        from scripts.trader.briefing_core import _is_daily_fresh
        et = ZoneInfo("America/New_York")
        now = datetime.now(tz=et)
        today_ts = int(now.timestamp())
        assert _is_daily_fresh(self._df(today_ts), max_age_days=1) is True

    def test_yesterday_is_fresh(self) -> None:
        from scripts.trader.briefing_core import _is_daily_fresh
        et = ZoneInfo("America/New_York")
        now = datetime.now(tz=et)
        from datetime import timedelta
        yesterday_ts = int((now - timedelta(days=1)).timestamp())
        assert _is_daily_fresh(self._df(yesterday_ts), max_age_days=1) is True

    def test_three_days_old_is_stale(self) -> None:
        from scripts.trader.briefing_core import _is_daily_fresh
        et = ZoneInfo("America/New_York")
        now = datetime.now(tz=et)
        from datetime import timedelta
        three_days_ago_ts = int((now - timedelta(days=3)).timestamp())
        assert _is_daily_fresh(self._df(three_days_ago_ts), max_age_days=1) is False

    def test_empty_df_is_not_fresh(self) -> None:
        from scripts.trader.briefing_core import _is_daily_fresh
        assert _is_daily_fresh(pd.DataFrame(), max_age_days=1) is False

    def test_none_is_not_fresh(self) -> None:
        from scripts.trader.briefing_core import _is_daily_fresh
        assert _is_daily_fresh(None, max_age_days=1) is False

    def test_handles_millisecond_timestamps(self) -> None:
        """Some parquet files store time as ms, not s. The freshness
        check should auto-detect and convert."""
        from scripts.trader.briefing_core import _is_daily_fresh
        et = ZoneInfo("America/New_York")
        now = datetime.now(tz=et)
        today_ms = int(now.timestamp() * 1000)
        assert _is_daily_fresh(self._df(today_ms), max_age_days=1) is True


# ── load_daily_price_context ─────────────────────────────────────


def _make_daily_df(rows: list[dict]) -> pd.DataFrame:
    """Build a daily-parquet-shaped DataFrame. Each row has
    time (unix s), open, high, low, close."""
    return pd.DataFrame(rows)


def _make_1m_df(rth_bars: list[dict], globex_bars: list[dict] | None = None) -> pd.DataFrame:
    """Build a 1m-parquet-shaped DataFrame with US/Eastern index.
    `rth_bars` and `globex_bars` are lists of dicts with `time`
    (string, ET) and OHLCV."""
    rows = []
    for b in rth_bars:
        ts = pd.Timestamp(b["time"]).tz_localize("America/New_York")
        rows.append({"ts": ts, "open": b["open"], "high": b["high"],
                     "low": b["low"], "close": b["close"], "volume": b.get("volume", 1)})
    if globex_bars:
        for b in globex_bars:
            ts = pd.Timestamp(b["time"]).tz_localize("America/New_York")
            rows.append({"ts": ts, "open": b["open"], "high": b["high"],
                         "low": b["low"], "close": b["close"], "volume": b.get("volume", 1)})
    df = pd.DataFrame(rows).set_index("ts").sort_index()
    return df


class TestLoadDailyPriceContext:
    """End-to-end tests for the loader wrapper. The fix picks up
    the daily timeframe parquet (with settlement-grade OHLCV) and
    falls back to RTH-filtered 1m when the daily file is stale."""

    def test_uses_daily_parquet_when_fresh(self) -> None:
        from scripts.trader import briefing_core
        from datetime import datetime
        from zoneinfo import ZoneInfo

        et = ZoneInfo("America/New_York")
        now = datetime.now(tz=et)
        today_ts = int(now.timestamp())

        # Daily parquet with today's bar (the settlement print).
        daily = _make_daily_df([
            {"time": today_ts - 86400, "open": 100, "high": 102, "low": 99, "close": 101},
            {"time": today_ts, "open": 101, "high": 105, "low": 100, "close": 104},
        ])

        fake_loader = mock.MagicMock()
        fake_loader.load_parquet.return_value = daily
        # The 1m loader must NOT be called when the daily is fresh.
        fake_loader.load_price.return_value = pd.DataFrame()

        result = briefing_core.load_daily_price_context(fake_loader, "ES1")

        assert result is not None
        # The 16:00-style settlement from the daily file.
        assert result["close"] == 104
        assert result["open"] == 101
        assert result["high"] == 105
        assert result["low"] == 100
        # change_pct = 104/101 - 1 = +2.97%
        assert abs(result["change_pct"] - 2.97) < 0.05
        assert result["body"] == "bullish"
        # Daily was trusted, so load_price (1m) was NOT called.
        fake_loader.load_price.assert_not_called()

    def test_falls_back_to_1m_when_daily_is_stale(self) -> None:
        """If the daily parquet's last bar is 3 days old, the
        function must NOT trust it — it falls back to the
        RTH-filtered 1m resample."""
        from scripts.trader import briefing_core
        from datetime import datetime, timedelta
        from zoneinfo import ZoneInfo

        et = ZoneInfo("America/New_York")
        now = datetime.now(tz=et)
        stale_ts = int((now - timedelta(days=3)).timestamp())

        # Stale daily parquet (3 days old).
        daily = _make_daily_df([{"time": stale_ts, "open": 50, "high": 51, "low": 49, "close": 50}])

        # 1m bars for today, with a 20:00 Globex print that would
        # pollute the old code's `last` aggregator.
        today_str = now.strftime("%Y-%m-%d")
        df_1m = _make_1m_df(
            rth_bars=[
                {"time": f"{today_str} 09:30:00", "open": 100, "high": 100, "low": 100, "close": 100},
                {"time": f"{today_str} 16:00:00", "open": 105, "high": 105, "low": 105, "close": 105},
            ],
            globex_bars=[
                {"time": f"{today_str} 20:00:00", "open": 999, "high": 999, "low": 999, "close": 999},
            ],
        )

        fake_loader = mock.MagicMock()
        fake_loader.load_parquet.return_value = daily
        fake_loader.load_price.return_value = df_1m

        result = briefing_core.load_daily_price_context(fake_loader, "ES1")

        assert result is not None
        # The fix must pick the 16:00 RTH settlement (105), NOT the
        # 20:00 Globex print (999).
        assert result["close"] == 105, (
            f"Expected 16:00 RTH close (105), got {result['close']} "
            "— the fix did not filter out the 20:00 Globex bar."
        )
        # load_price (1m) was called because the daily was stale.
        fake_loader.load_price.assert_called_once()

    def test_returns_empty_dict_when_daily_load_fails_and_no_1m(self) -> None:
        from scripts.trader import briefing_core
        fake_loader = mock.MagicMock()
        fake_loader.load_parquet.side_effect = RuntimeError("schwab down")
        fake_loader.load_price.side_effect = RuntimeError("schwab down")
        result = briefing_core.load_daily_price_context(fake_loader, "ES1")
        assert result == {}

    def test_returns_empty_dict_when_daily_fresh_but_empty_1m(self) -> None:
        """Daily file is fresh and trusted; no 1m fallback needed.
        The 1m loader is not called."""
        from scripts.trader import briefing_core
        from datetime import datetime
        from zoneinfo import ZoneInfo
        et = ZoneInfo("America/New_York")
        now = datetime.now(tz=et)
        daily = _make_daily_df([{"time": int(now.timestamp()), "open": 100, "high": 105, "low": 99, "close": 103}])
        fake_loader = mock.MagicMock()
        fake_loader.load_parquet.return_value = daily
        result = briefing_core.load_daily_price_context(fake_loader, "ES1")
        assert result["close"] == 103
        fake_loader.load_price.assert_not_called()
