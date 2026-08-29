"""Pytest suite for Market Calendar."""

from datetime import timezone
from scripts.utils.market_calendar import get_session_cutoff_utc, is_market_weekday


def test_dst_summer_cutoff():
    """August is in EDT (UTC-4), so 08:45:00 ET = 12:45:00 UTC."""
    cutoff = get_session_cutoff_utc("2026-08-28", "08:45:00")
    assert cutoff.tzinfo == timezone.utc
    assert cutoff.hour == 12
    assert cutoff.minute == 45
    assert cutoff.second == 0


def test_standard_winter_cutoff():
    """January is in EST (UTC-5), so 08:45:00 ET = 13:45:00 UTC."""
    cutoff = get_session_cutoff_utc("2026-01-15", "08:45:00")
    assert cutoff.tzinfo == timezone.utc
    assert cutoff.hour == 13
    assert cutoff.minute == 45
    assert cutoff.second == 0


def test_is_market_weekday():
    assert is_market_weekday("2026-08-28")  # Friday -> True
    assert not is_market_weekday("2026-08-29")  # Saturday -> False
    assert not is_market_weekday("2026-08-30")  # Sunday -> False
    assert is_market_weekday("2026-08-31")  # Monday -> True
