"""Pytest suite for TapeMetricsExtractor (Milestone 0.7)."""

import sqlite3
import tempfile
from datetime import datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from scripts.derived.precompute_daily_classification import analyze_day
from scripts.trading_brain.db.init_db import init_trading_brain_db
from scripts.trading_brain.tape.tape_extractor import TapeMetricsExtractor
from scripts.utils.live_storage_resolver import load_session_bars

EASTERN_TZ = ZoneInfo("America/New_York")


@pytest.fixture
def temp_db():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        db_path = Path(tmpdir) / "test_trading_brain.sqlite"
        init_trading_brain_db(db_path=db_path, verbose=False)
        yield db_path


def test_canonical_day_type_classification_and_tape_record(temp_db):
    """Tests extracting metrics and canonical classification across 390 1m bars."""
    session_date = "2026-08-28"
    ticker = "NQ1"
    
    # Construct 390 clean 1m bars from 09:30 to 16:00 ET
    start_dt = datetime(2026, 8, 28, 9, 30, tzinfo=EASTERN_TZ)
    records = []
    base_price = 20000.0
    
    for i in range(390):
        dt = start_dt + timedelta(minutes=i)
        p = base_price + (i * 0.5)
        records.append({
            "dt": dt.astimezone(ZoneInfo("UTC")),
            "dt_et": dt,
            "open": p,
            "high": p + 2.0,
            "low": p - 1.0,
            "close": p + 1.0,
            "volume": 100
        })
        
    df = pd.DataFrame(records)
    
    metrics = TapeMetricsExtractor.extract_from_dataframe(df, session_date, ticker)
    assert metrics.session_open == 20000.0
    assert metrics.actual_bar_count == 390
    assert metrics.quality_state == "CLEAN"
    assert metrics.day_type_classification in ("R1", "R2", "DNP", "DWP", "ROTATIONAL_CHOP")
    assert metrics.session_range_bps > 0.0


def test_classifier_parity_with_canonical_precompute():
    """Parity Test: verifies TapeMetricsExtractor (4_CLASS taxonomy) matches canonical analyze_day 100% on golden historical dates."""
    golden_dates = ["2026-08-28", "2026-08-27", "2026-08-26", "2026-08-25"]
    
    for d in golden_dates:
        df = load_session_bars("NQ1", d)
        
        # Run canonical analyze_day
        df_canon = df.copy()
        df_canon.index = df_canon["dt_et"]
        df_canon["time_only"] = df_canon["dt_et"].dt.time
        canon_res = analyze_day(d, df_canon, "NQ1")
        assert canon_res is not None
        canon_type = canon_res["type"]
        if canon_type == "Range 1":
            canon_type = "R1"
            
        # Run TapeMetricsExtractor 4-class
        tape_type_4class = TapeMetricsExtractor.classify_day_type(df, ticker="NQ1", taxonomy="4_CLASS")
        
        assert tape_type_4class == canon_type, f"Parity mismatch on {d}: canonical={canon_type}, tape_extractor={tape_type_4class}"


def test_scheduled_short_session_handling():
    """Tests 210-bar half-day session classified as SCHEDULED_SHORT_SESSION."""
    session_date = "2026-11-27"  # Day after Thanksgiving
    ticker = "NQ1"
    start_dt = datetime(2026, 11, 27, 9, 30, tzinfo=EASTERN_TZ)
    records = []
    for i in range(210):
        dt = start_dt + timedelta(minutes=i)
        records.append({
            "dt": dt.astimezone(ZoneInfo("UTC")),
            "dt_et": dt,
            "open": 20000.0,
            "high": 20010.0,
            "low": 19990.0,
            "close": 20005.0,
            "volume": 100
        })
    df = pd.DataFrame(records)
    metrics = TapeMetricsExtractor.extract_from_dataframe(df, session_date, ticker)
    assert metrics.quality_state == "SCHEDULED_SHORT_SESSION"
    assert metrics.expected_bar_count == 210
