"""Pytest suite for Market Calendar & Futures Session Date Derivation."""

from datetime import datetime, timezone
from scripts.utils.market_calendar import (
    derive_futures_session_date,
    get_session_cutoff_utc,
    is_market_weekday,
)

def test_dst_summer_cutoff():
    cutoff = get_session_cutoff_utc("2026-07-15", "08:45:00")
    assert cutoff.tzinfo == timezone.utc
    assert cutoff.hour == 12
    assert cutoff.minute == 45

def test_standard_winter_cutoff():
    cutoff = get_session_cutoff_utc("2026-01-15", "08:45:00")
    assert cutoff.tzinfo == timezone.utc
    assert cutoff.hour == 13
    assert cutoff.minute == 45

def test_is_market_weekday():
    assert is_market_weekday("2026-08-28") is True  # Friday
    assert is_market_weekday("2026-08-29") is False # Saturday
    assert is_market_weekday("2026-08-30") is False # Sunday

def test_derive_futures_session_date_globex_roll():
    # Trade on Monday at 14:00 ET (18:00 UTC during EDT) -> Monday session
    assert derive_futures_session_date("2026-08-24T18:00:00Z") == "2026-08-24"
    
    # Trade on Monday at 18:30 ET (22:30 UTC during EDT) -> Tuesday session
    assert derive_futures_session_date("2026-08-24T22:30:00Z") == "2026-08-25"
    
    # Trade on Sunday at 18:30 ET (22:30 UTC during EDT) -> Monday session
    assert derive_futures_session_date("2026-08-23T22:30:00Z") == "2026-08-24"
