"""Pytest suite for LegacyShadowImporter (Milestone 0.3a)."""

import sqlite3
import tempfile
from pathlib import Path

import pytest

from scripts.trading_brain.db.init_db import init_trading_brain_db
from scripts.trading_brain.migrations.import_legacy_shadow import LegacyShadowImporter, compute_sha256


@pytest.fixture
def mock_legacy_environment():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        tmp_path = Path(tmpdir)
        canon_db = tmp_path / "canonical_trading_brain.sqlite"
        init_trading_brain_db(db_path=canon_db, verbose=False)
        
        sys_db = tmp_path / "system_wargames.sqlite"
        mkt_db = tmp_path / "market_actuals.sqlite"
        mick_db = tmp_path / "mickey_ground_truth.sqlite"
        
        # Populate mock system_wargames
        with sqlite3.connect(str(sys_db)) as conn:
            conn.execute(
                """
                CREATE TABLE system_wargames (
                    prediction_id TEXT PRIMARY KEY,
                    session_date DATE,
                    ticker TEXT,
                    cutoff_time TEXT,
                    spot_price REAL,
                    p12_high REAL,
                    p12_low REAL,
                    p12_mid REAL,
                    p12_bias TEXT,
                    p12_diff_pts REAL,
                    p12_diff_bps REAL,
                    asia_status TEXT,
                    asia_broken INTEGER,
                    london_status TEXT,
                    london_broken INTEGER,
                    session_alignment TEXT,
                    anchors_json TEXT,
                    false_scenario_json TEXT,
                    true_scenario_json TEXT,
                    candle_science_json TEXT,
                    pack_brackets_json TEXT,
                    markdown_report TEXT,
                    gdrive_file_id TEXT,
                    created_at TIMESTAMP
                );
                """
            )
            conn.execute(
                """
                INSERT INTO system_wargames (prediction_id, session_date, ticker, cutoff_time, spot_price, p12_mid, p12_bias, markdown_report)
                VALUES ('pred-1', '2026-08-28', 'NQ1', '08:45', 20000.0, 19990.0, 'BULLISH', '# Markdown Wargame');
                """
            )
            
        # Populate mock market_actuals
        with sqlite3.connect(str(mkt_db)) as conn:
            conn.execute(
                """
                CREATE TABLE market_actuals (
                    session_id TEXT PRIMARY KEY,
                    session_date DATE,
                    ticker TEXT,
                    rth_open REAL,
                    rth_high REAL,
                    rth_low REAL,
                    rth_close REAL,
                    actual_hod_time TEXT,
                    actual_lod_time TEXT,
                    realized_day_type TEXT
                );
                """
            )
            conn.execute(
                """
                INSERT INTO market_actuals (session_id, session_date, ticker, rth_open, rth_high, rth_low, rth_close, realized_day_type)
                VALUES ('mkt-1', '2026-08-28', 'NQ1', 20000.0, 20100.0, 19950.0, 20050.0, 'ROTATIONAL_CHOP');
                """
            )
            
        # Populate mock mickey_ground_truth
        with sqlite3.connect(str(mick_db)) as conn:
            conn.execute(
                """
                CREATE TABLE mickey_wargames (
                    session_id TEXT PRIMARY KEY,
                    session_date DATE,
                    ticker TEXT,
                    stream_type TEXT,
                    title TEXT,
                    raw_transcript TEXT,
                    p12_bias TEXT,
                    primary_scenario TEXT
                );
                """
            )
            conn.execute(
                """
                INSERT INTO mickey_wargames (session_id, session_date, ticker, title, raw_transcript, p12_bias, primary_scenario)
                VALUES ('mick-1', '2026-08-28', 'NQ1', 'Mickey Stream 28 Aug', 'Transcript text here', 'BULLISH', 'False Reversion');
                """
            )
            
        yield {
            "canonical_db": canon_db,
            "sys_db": sys_db,
            "mkt_db": mkt_db,
            "mick_db": mick_db
        }


def test_legacy_shadow_importer_zero_fabrication(mock_legacy_environment):
    """Tests that LegacyShadowImporter migrates records with zero probability fabrication and passes dual-hash checks."""
    env = mock_legacy_environment
    importer = LegacyShadowImporter(
        canonical_db_path=env["canonical_db"],
        system_wargames_path=env["sys_db"],
        market_actuals_path=env["mkt_db"],
        mickey_ground_truth_path=env["mick_db"]
    )
    
    # 1. Test backups
    backups = importer.run_pre_cutover_backups()
    assert len(backups) == 3
    
    # 2. Test migration & verification
    success, report = importer.import_and_verify_all(verbose=False)
    assert success
    assert report["hash_verification_passed"]
    assert report["system_wargames_migrated"] == 1
    assert report["market_actuals_migrated"] == 1
    assert report["mickey_wargames_migrated"] == 1
    
    # 3. Verify forecast_snapshots has zero fabricated probabilities (abstain_flag=1, probs=None)
    with sqlite3.connect(str(env["canonical_db"])) as conn:
        conn.row_factory = sqlite3.Row
        fc = conn.execute("SELECT * FROM forecast_snapshots WHERE session_date = '2026-08-28';").fetchone()
        assert fc is not None
        assert fc["abstain_flag"] == 1
        assert fc["prob_r1"] is None
        assert fc["prob_r2"] is None
        assert fc["prob_dnp"] is None
        assert fc["prob_dwp"] is None
        assert fc["prob_rotational_chop"] is None
        # Effective cutoff is DST-correct 12:45 UTC (08:45 EDT)
        assert fc["effective_cutoff_utc"] == "2026-08-28T12:45:00Z"
