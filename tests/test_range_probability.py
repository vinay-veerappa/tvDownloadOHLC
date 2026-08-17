"""
Unit tests for Range Probability Engine and Mathematical Verification
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timezone
import zoneinfo

from src.range_prob.calculator import (
    get_bucket_index,
    get_bucket_char,
    get_bucket_name,
    build_ranges_from_ohlc,
    compute_probability_matrix,
)
from src.range_prob.backtest_adapter import RangeProbBacktester

NY_TZ = zoneinfo.ZoneInfo("America/New_York")


def test_bucket_classification():
    # Below prior low (< 0.0) -> Bucket 0
    assert get_bucket_index(-0.05) == 0
    assert get_bucket_char(0) == "0"
    assert get_bucket_name(0) == "below prev low"

    # Deciles 1 through 10
    assert get_bucket_index(0.00) == 1
    assert get_bucket_char(1) == "1"
    assert get_bucket_name(1) == "0.0 - 0.1"

    assert get_bucket_index(0.05) == 1
    assert get_bucket_index(0.15) == 2
    assert get_bucket_index(0.55) == 6
    assert get_bucket_char(6) == "6"
    assert get_bucket_name(6) == "0.5 - 0.6"

    assert get_bucket_index(0.95) == 10
    assert get_bucket_char(10) == "a"
    assert get_bucket_name(10) == "0.9 - 1.0"

    # At or above prior high (>= 1.0) -> Bucket 11
    assert get_bucket_index(1.00) == 11
    assert get_bucket_index(1.25) == 11
    assert get_bucket_char(11) == "b"
    assert get_bucket_name(11) == "at/above prev high"


def test_range_construction():
    # Create synthetic 1-minute OHLC bars
    # Session starts at 18:00 ET (23:00 UTC)
    base_time = pd.Timestamp("2026-08-10 23:00:00", tz="UTC")
    bars = []

    # Range 1: 18:00 to 19:00 ET (60 mins) -> Open: 100, High: 120, Low: 90, Close: 110
    for i in range(60):
        t = base_time + pd.Timedelta(minutes=i)
        bars.append({
            "time": t,
            "open": 100.0 if i == 0 else 105.0,
            "high": 120.0 if i == 30 else 115.0,
            "low": 90.0 if i == 15 else 95.0,
            "close": 110.0 if i == 59 else 105.0,
            "volume": 100,
        })

    # Range 2: 19:00 to 20:00 ET (60 mins) -> Open: 95 (Pos = (95-90)/(120-90) = 5/30 = 0.167 -> Decile 2)
    # Closes at 130 -> UP outcome (Close 130 > Prior High 120)
    for i in range(60):
        t = base_time + pd.Timedelta(minutes=60 + i)
        bars.append({
            "time": t,
            "open": 95.0 if i == 0 else 100.0,
            "high": 135.0 if i == 45 else 125.0,
            "low": 92.0 if i == 10 else 94.0,
            "close": 130.0 if i == 59 else 128.0,
            "volume": 150,
        })

    df = pd.DataFrame(bars)
    ranges = build_ranges_from_ohlc(df, range_minutes=60, anchor_hour_et=18)

    assert len(ranges) == 2

    r1 = ranges.iloc[0]
    assert r1["open"] == 100.0
    assert r1["high"] == 120.0
    assert r1["low"] == 90.0
    assert r1["close"] == 110.0

    r2 = ranges.iloc[1]
    assert r2["open"] == 95.0
    assert r2["prior_high"] == 120.0
    assert r2["prior_low"] == 90.0
    assert np.isclose(r2["open_pos"], (95.0 - 90.0) / 30.0) # 0.166667
    assert r2["bucket"] == 2 # Decile 2
    assert r2["outcome"] == "UP"
    assert r2["is_resolved"] == True


def test_matrix_probability_computation():
    # Construct multiple ranges and verify transition matrix
    np.random.seed(42)
    records = []
    base_time = pd.Timestamp("2026-01-01 23:00:00", tz="UTC")

    # Generate 100 simulated ranges for slot 10:00 ET, bucket 2
    # 75 Up, 25 Down
    cur_p = 100.0
    for i in range(100):
        t_start = base_time + pd.Timedelta(hours=i)
        p_high = cur_p + 10.0
        p_low = cur_p - 10.0
        # open at low + 2 points (pos = 2/20 = 0.10 -> bucket 2)
        r_open = p_low + 2.0
        outcome = "UP" if i < 75 else "DOWN"
        r_close = p_high + 5.0 if outcome == "UP" else p_low - 5.0

        records.append({
            "start_time_utc": t_start,
            "end_time_utc": t_start + pd.Timedelta(minutes=59),
            "start_time_ny": t_start.tz_convert(NY_TZ),
            "slot": "1000",
            "range_minutes": 60,
            "open": r_open,
            "high": p_high + 6.0,
            "low": p_low - 6.0,
            "close": r_close,
            "prior_high": p_high,
            "prior_low": p_low,
            "prior_open": p_low,
            "prior_close": p_high,
            "prior_start_time_utc": t_start - pd.Timedelta(hours=1),
            "is_adjacent": True,
            "open_pos": 0.10,
            "bucket": 2,
            "bucket_char": "2",
            "bucket_name": "0.1 - 0.2",
            "outcome": outcome,
            "is_resolved": True,
        })
        cur_p = r_close

    df = pd.DataFrame(records)
    matrix = compute_probability_matrix(df, min_prob_threshold=70.0, min_sample_size=20)

    assert matrix["qualified_count"] >= 1
    rec = [r for r in matrix["records"] if r["slot"] == "1000" and r["bucket"] == 2][0]

    assert rec["direction"] == "U"
    assert rec["prob_all"] == 75.0
    assert rec["sample_size"] == 100
    assert rec["resolve_rate"] == 100.0
    assert rec["is_qualified"] == True


def test_backtester_execution():
    # Build trade test feed with clean target hit (prior_high=120, prior_low=60 -> mid=90)
    # Entry at open=100, low=95 (above stop 90), high=125 (hits target 120)
    feed = pd.DataFrame([{
        "start_time_ny": pd.Timestamp("2026-08-10 10:00:00", tz=NY_TZ),
        "slot": "1000",
        "open": 100.0,
        "high": 125.0,
        "low": 95.0,
        "close": 122.0,
        "prior_high": 120.0,
        "prior_low": 60.0,
        "open_pos": 0.67,
        "bucket": 7,
        "bucket_name": "0.6 - 0.7",
        "is_adjacent": True,
        "s_dir": "U",
        "s_prob": 80.0,
        "s_res_rate": 60.0,
        "s_n": 100,
        "outcome": "UP",
        "is_resolved": True,
    }])

    tester = RangeProbBacktester(
        min_prob=70.0,
        min_resolve_rate=40.0,
        min_sample_size=20,
        target_mode="prior_boundary",
        stop_mode="prior_midpoint",
        point_value=20.0,
    )

    res = tester.run_backtest(feed)
    assert res["total_trades"] == 1
    assert res["winning_trades"] == 1
    assert res["win_rate"] == 100.0
    # Prior High = 120, Entry = 100 -> Gain = 20 pts - 0.5 slip = 19.5 pts * $20 - $2 comm = $388.00
    assert np.isclose(res["net_profit"], 388.00)
