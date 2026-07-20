import pytest
from datetime import datetime, timedelta, date
import os
import sys

# Add project root to sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from scripts.market_data.sync_earnings_calendar import (
    fetch_nasdaq_earnings_for_date,
    fetch_earnings_range,
    run_sync
)

def test_fetch_nasdaq_earnings_for_date():
    """Verify Nasdaq Earnings API returns valid structured event list."""
    # Test with a known past date or upcoming weekday
    test_date = date.today()
    # Adjust to recent weekday if today is weekend
    if test_date.weekday() == 5: # Saturday
        test_date -= timedelta(days=1)
    elif test_date.weekday() == 6: # Sunday
        test_date += timedelta(days=1)
        
    events = fetch_nasdaq_earnings_for_date(test_date.strftime("%Y-%m-%d"))
    assert isinstance(events, list)
    if len(events) > 0:
        event = events[0]
        assert "ticker" in event
        assert "earningsDate" in event
        assert "beforeMarket" in event
        assert "source" in event
        assert event["source"] == "nasdaq_api"

def test_fetch_earnings_range_dual_provider():
    """Verify dual-provider fetch handles range query."""
    start_date = datetime.now().date()
    end_date = start_date + timedelta(days=3)
    events = fetch_earnings_range(start_date, end_date)
    assert isinstance(events, list)
