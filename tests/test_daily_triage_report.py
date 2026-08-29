"""Pytest suite for DailyTriageReportGenerator (Milestone 1.2)."""

import sqlite3
import tempfile
from pathlib import Path

import pytest

from scripts.trading_brain.db.init_db import init_trading_brain_db
from scripts.trading_brain.forecast.forecast_registrar import ForecastRegistrar, ForecastSnapshotPayload
from scripts.trading_brain.plans.plan_adapter import PlanAdapter, PlanContext
from scripts.trading_brain.reports.daily_triage_report import DailyTriageReportGenerator
from scripts.trading_brain.signals.opportunity_logger import OpportunityLogger, SignalOpportunity
from scripts.trading_brain.strategies.registry_v0 import register_all_v0_strategies


@pytest.fixture
def temp_db():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        db_path = Path(tmpdir) / "test_trading_brain.sqlite"
        init_trading_brain_db(db_path=db_path, verbose=False)
        yield db_path


def test_generate_triage_report_markdown_and_json(temp_db):
    """Tests generating Markdown and JSON daily process delta reports."""
    session_date = "2026-08-28"
    ticker = "NQ1"
    
    register_all_v0_strategies(db_path=temp_db)
    
    PlanAdapter.save_plan_snapshot(
        PlanContext(
            session_date=session_date,
            ticker=ticker,
            preparation_cutoff_utc="2026-08-28T12:45:00Z",
            verbatim_plan_text="Bullish morning trend plan",
            primary_bias="BULLISH",
            wargamed_scenarios={},
            invalidation_levels={},
            max_intended_risk_bps=12.0,
            permitted_strategies=["STRAT_ALN_LPEU_V0_1"]
        ),
        db_path=temp_db
    )
    
    with sqlite3.connect(str(temp_db)) as conn:
        conn.execute(
            """
            INSERT INTO session_tape_actuals (
                actual_id, session_date, ticker, revision_seq, source_system,
                session_open, session_high, session_low, session_close, rth_close,
                session_range_bps, day_type_classification, quality_state, content_hash
            ) VALUES ('act-1', ?, ?, 1, 'STORAGE', 20000.0, 20150.0, 19980.0, 20140.0, 20140.0, 85.0, 'R1', 'CLEAN', 'h1');
            """,
            (session_date, ticker)
        )
        
    md, report_dict = DailyTriageReportGenerator.generate_report(session_date, ticker, db_path=temp_db)
    
    assert "# Daily Process Delta & Triage Report: 2026-08-28 (NQ1)" in md
    assert "## 1. 4-Way Reconciliation Quadrant" in md
    assert "## 2. Signal Opportunities & Execution Realization" in md
    assert "## 3. Measured Tape Actuals" in md
    assert report_dict["session_date"] == "2026-08-28"
    assert report_dict["ticker"] == "NQ1"


def test_review_queue_resolution_handlers(temp_db):
    """Tests resolving unmatched links and reviewing information items."""
    # 1. Test information item review
    with sqlite3.connect(str(temp_db)) as conn:
        conn.execute(
            """
            INSERT INTO information_items (information_id, evidence_class, time_orientation, source_type, title, verbatim_text, available_at_utc)
            VALUES ('info-triage-1', 'DOCTRINE', 'EX_ANTE', 'TRANSCRIPT', 'Item 1', 'Content', '2026-08-28T08:00:00Z');
            """
        )
        
    DailyTriageReportGenerator.review_information_item(
        information_id="info-triage-1",
        review_state="ACCEPTED",
        reviewer="SENIOR_TRADER",
        review_notes="Verified against video stream",
        db_path=temp_db
    )
    
    with sqlite3.connect(str(temp_db)) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute("SELECT active_review_state FROM v_information_items_active WHERE information_id = 'info-triage-1';")
        assert cur.fetchone()["active_review_state"] == "ACCEPTED"
        
    # 2. Test unmatched link resolution
    with sqlite3.connect(str(temp_db)) as conn:
        conn.execute(
            """
            INSERT INTO execution_events (
                execution_id, session_date, ticker, account_id, broker_execution_id,
                broker_order_id, order_action, order_type, quantity, fill_price,
                idempotency_key, event_timestamp_utc
            ) VALUES ('exec-triage-1', '2026-08-28', 'NQ1', 'ACC1', 'b-ex', 'b-ord', 'BUY', 'MARKET', 1, 20000.0, 'id-triage', '2026-08-28T09:35:00Z');
            """
        )
        conn.execute(
            """
            INSERT INTO unmatched_link_events (link_event_id, execution_id, candidate_opportunity_ids_json, resolution_status)
            VALUES ('link-triage-1', 'exec-triage-1', '[]', 'OPEN');
            """
        )
        
    DailyTriageReportGenerator.resolve_unmatched_link(
        link_event_id="link-triage-1",
        resolution_status="RESOLVED_DISCRETIONARY",
        resolution_notes="Discretionary add-on after IB high breach",
        db_path=temp_db
    )
    
    with sqlite3.connect(str(temp_db)) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute("SELECT COUNT(*) AS c FROM v_unmatched_links_open;")
        assert cur.fetchone()["c"] == 0
