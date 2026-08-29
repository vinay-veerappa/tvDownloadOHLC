"""Pytest suite for TapeMetricsExtractor (Milestone 0.7)."""

import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest

from scripts.trading_brain.db.init_db import init_trading_brain_db
from scripts.trading_brain.tape.tape_extractor import TapeMetricsExtractor


@pytest.fixture
def temp_db():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        db_path = Path(tmpdir) / "test_trading_brain.sqlite"
        init_trading_brain_db(db_path=db_path, verbose=False)
        yield db_path


def generate_synthetic_session_bars(session_date: str = "2026-08-28") -> pd.DataFrame:
    """Generates 390 synthetic 1-minute RTH bars (09:30 to 16:00 ET)."""
    start_dt = pd.to_datetime(f"{session_date} 09:30:00").tz_localize("America/New_York")
    times = [start_dt + timedelta(minutes=i) for i in range(391)]
    
    data = []
    price = 20000.0
    for i, t in enumerate(times):
        o = price
        # Create a trend expansion
        h = o + 5.0
        l = o - 2.0
        c = o + 3.0
        price = c
        data.append({
            "timestamp": t.tz_convert("UTC").isoformat(),
            "open": o,
            "high": h,
            "low": l,
            "close": c,
            "volume": 100
        })
    df = pd.DataFrame(data)
    df["dt"] = pd.to_datetime(df["timestamp"], utc=True)
    df["dt_et"] = df["dt"].dt.tz_convert("America/New_York")
    return df


def test_extract_from_dataframe_and_record(temp_db):
    """Tests extracting tape metrics from DataFrame and saving to database."""
    session_date = "2026-08-28"
    df = generate_synthetic_session_bars(session_date)
    
    metrics = TapeMetricsExtractor.extract_from_dataframe(df, session_date, "NQ1")
    assert metrics.session_open == 20000.0
    assert metrics.session_high > 20000.0
    assert metrics.actual_bar_count >= 390
    assert metrics.quality_state == "CLEAN"
    assert metrics.day_type_classification in ("R1", "R2", "DNP", "DWP", "ROTATIONAL_CHOP")
    
    # Save to database
    with sqlite3.connect(str(temp_db)) as conn:
        conn.execute(
            """
            INSERT INTO session_tape_actuals (
                actual_id, session_date, ticker, revision_seq, source_system,
                session_open, session_high, session_low, session_close, rth_close,
                hod_timestamp_utc, lod_timestamp_utc, session_range_bps,
                day_type_classification, content_hash, quality_state
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                metrics.actual_id, metrics.session_date, metrics.ticker, metrics.revision_seq,
                metrics.source_system, metrics.session_open, metrics.session_high,
                metrics.session_low, metrics.session_close, metrics.rth_close,
                metrics.hod_timestamp_utc, metrics.lod_timestamp_utc,
                metrics.session_range_bps, metrics.day_type_classification,
                metrics.content_hash, metrics.quality_state
            )
        )
        
        # Verify view resolution
        conn.row_factory = sqlite3.Row
        cur = conn.execute("SELECT * FROM v_session_tape_actuals_current WHERE session_date = '2026-08-28';")
        row = cur.fetchone()
        assert row is not None
        assert row["session_open"] == 20000.0
