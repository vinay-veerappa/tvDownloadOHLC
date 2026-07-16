import pandas as pd
import pytest
from datetime import time, date

import sys
from pathlib import Path

# Add project root to sys.path dynamically
_current_dir = Path(__file__).resolve().parent
while _current_dir.name and _current_dir.name != "scripts":
    _current_dir = _current_dir.parent
if _current_dir.name == "scripts":
    _root_dir = str(_current_dir.parent)
    if _root_dir not in sys.path:
        sys.path.insert(0, _root_dir)

from scripts.libs_py.nqstats.sessions import (
    get_logical_trading_date,
    get_dst_flags,
    get_event_anchored_times,
    get_time_mask_vectorized
)

def test_get_logical_trading_date():
    # Monday 17:59 ET -> Monday (shifted + 6 hours = 23:59 Monday)
    ts1 = pd.DatetimeIndex([pd.Timestamp("2026-06-01 17:59:00")])
    assert get_logical_trading_date(ts1).iloc[0] == date(2026, 6, 1)

    # Monday 18:00 ET -> Tuesday (shifted + 6 hours = 00:00 Tuesday)
    ts2 = pd.DatetimeIndex([pd.Timestamp("2026-06-01 18:00:00")])
    assert get_logical_trading_date(ts2).iloc[0] == date(2026, 6, 2)

    # Friday 18:00 ET -> Monday (shifted + 6 hours = 00:00 Saturday, which is weekend, rolls to Monday)
    ts3 = pd.DatetimeIndex([pd.Timestamp("2026-06-05 18:00:00")])
    assert get_logical_trading_date(ts3).iloc[0] == date(2026, 6, 8)


def test_get_dst_flags():
    # 2026 US DST: March 8 to Nov 1
    # 2026 UK DST: March 29 to Oct 25

    # Jan 15, 2026: Winter (Both EST/GMT)
    ts_winter = pd.DatetimeIndex([pd.Timestamp("2026-01-15 12:00:00", tz="UTC")])
    us_dst, uk_dst = get_dst_flags(ts_winter)
    assert not us_dst.iloc[0]
    assert not uk_dst.iloc[0]

    # Jun 15, 2026: Summer (Both EDT/BST)
    ts_summer = pd.DatetimeIndex([pd.Timestamp("2026-06-15 12:00:00", tz="UTC")])
    us_dst, uk_dst = get_dst_flags(ts_summer)
    assert us_dst.iloc[0]
    assert uk_dst.iloc[0]

    # March 15, 2026: US is in DST (EDT), UK is not (GMT)
    ts_march_shoulder = pd.DatetimeIndex([pd.Timestamp("2026-03-15 12:00:00", tz="UTC")])
    us_dst, uk_dst = get_dst_flags(ts_march_shoulder)
    assert us_dst.iloc[0]
    assert not uk_dst.iloc[0]

    # Oct 30, 2026: US is in DST (EDT), UK is not (GMT - transition was Oct 25)
    ts_oct_shoulder = pd.DatetimeIndex([pd.Timestamp("2026-10-30 12:00:00", tz="UTC")])
    us_dst, uk_dst = get_dst_flags(ts_oct_shoulder)
    assert us_dst.iloc[0]
    assert not uk_dst.iloc[0]


def test_get_event_anchored_times():
    # Tokyo IB:
    # US DST = True -> 20:00 - 21:00 ET
    start, end, offset, regime = get_event_anchored_times("Tokyo IB", us_dst=True, uk_dst=True)
    assert start == time(20, 0)
    assert end == time(21, 0)
    assert offset == 0
    assert regime == "aligned"

    # US DST = False -> 19:00 - 20:00 ET
    start, end, offset, regime = get_event_anchored_times("Tokyo IB", us_dst=False, uk_dst=False)
    assert start == time(19, 0)
    assert end == time(20, 0)
    assert offset == -1
    assert regime == "shifted"

    # London IB:
    # Aligned: US DST = UK DST = True -> 03:00 - 04:00 ET
    start, end, offset, regime = get_event_anchored_times("London IB", us_dst=True, uk_dst=True)
    assert start == time(3, 0)
    assert end == time(4, 0)
    assert offset == 0
    assert regime == "aligned"

    # March shoulder: US DST = True, UK DST = False -> 04:00 - 05:00 ET
    start, end, offset, regime = get_event_anchored_times("London IB", us_dst=True, uk_dst=False)
    assert start == time(4, 0)
    assert end == time(5, 0)
    assert offset == 1
    assert regime == "shifted"

    # Oct/Nov shoulder: US DST = False, UK DST = True -> 02:00 - 03:00 ET
    start, end, offset, regime = get_event_anchored_times("London IB", us_dst=False, uk_dst=True)
    assert start == time(2, 0)
    assert end == time(3, 0)
    assert offset == -1
    assert regime == "shifted"


def test_get_time_mask_vectorized_cross_midnight():
    # 20:59, 21:00, 01:00, 01:59, 02:00 ET in minutes
    bar_mins = pd.Series([20 * 60 + 59, 21 * 60, 1 * 60, 1 * 60 + 59, 2 * 60], dtype="int64").to_numpy()
    start_mins = pd.Series([21 * 60] * len(bar_mins), dtype="int64").to_numpy()
    end_mins = pd.Series([2 * 60] * len(bar_mins), dtype="int64").to_numpy()

    mask = get_time_mask_vectorized(bar_mins, start_mins, end_mins)

    # Cross-midnight interval is [21:00, 02:00): 21:00 and 01:xx are in, 20:59 and 02:00 are out.
    assert mask.tolist() == [False, True, True, True, False]
