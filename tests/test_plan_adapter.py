"""Pytest suite for PlanAdapter and deterministic as-of authority resolution."""

import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from scripts.trading_brain.db.init_db import init_trading_brain_db
from scripts.trading_brain.plans.plan_adapter import PlanAdapter, PlanContext
from scripts.utils.market_calendar import get_session_cutoff_utc


@pytest.fixture
def temp_db():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        db_path = Path(tmpdir) / "test_trading_brain.sqlite"
        init_trading_brain_db(db_path=db_path, verbose=False)
        yield db_path


def test_save_and_resolve_single_plan(temp_db):
    """Tests saving a basic ex-ante plan and resolving it as-of decision time."""
    session_date = "2026-09-01"  # Future session date -> EX_ANTE_DECLARED
    
    plan = PlanContext(
        session_date=session_date,
        ticker="NQ1",
        preparation_cutoff_utc="2026-09-01T12:45:00Z",
        verbatim_plan_text="Primary bias Bullish above 20000",
        primary_bias="BULLISH",
        wargamed_scenarios={"scenario_a": "Breakout above Asia High"},
        invalidation_levels={"bearish_invalidation": 19950.0},
        max_intended_risk_bps=12.0,
        permitted_strategies=["STRAT_ALN_LPEU_V0_1"]
    )
    
    saved = PlanAdapter.save_plan_snapshot(plan, db_path=temp_db)
    assert saved.plan_snapshot_id is not None
    assert saved.revision_seq == 1
    assert saved.provenance_class == "EX_ANTE_DECLARED"
    
    # Query as-of decision time
    resolved = PlanAdapter.get_plan_as_of(
        session_date=session_date,
        ticker="NQ1",
        decision_time_utc="2026-09-01T13:30:00Z",
        db_path=temp_db
    )
    assert resolved is not None
    assert resolved.plan_snapshot_id == saved.plan_snapshot_id
    assert resolved.primary_bias == "BULLISH"
    assert resolved.max_intended_risk_bps == 12.0


def test_calendar_derived_cutoff_prevents_caller_bypass(temp_db):
    """Tests that a caller supplying an artificial future cutoff cannot self-certify ex-ante for a past session."""
    past_session = "2026-01-01"
    fake_future_cutoff = "2026-12-31T23:59:59Z"
    
    plan = PlanAdapter.save_plan_snapshot(
        PlanContext(
            session_date=past_session,
            ticker="NQ1",
            preparation_cutoff_utc=fake_future_cutoff,  # Attempting to bypass cutoff
            verbatim_plan_text="Late submitted plan claiming to be ex-ante",
            primary_bias="BEARISH",
            wargamed_scenarios={},
            invalidation_levels={},
            max_intended_risk_bps=10.0,
            permitted_strategies=[]
        ),
        db_path=temp_db
    )
    
    # Must be demoted to POST_HOC_RECONSTRUCTION because now > 2026-01-01 08:45 ET
    assert plan.provenance_class == "POST_HOC_RECONSTRUCTION"
    assert plan.preparation_cutoff_utc == "2026-01-01T13:45:00Z"


def test_plan_revision_supersession(temp_db):
    """Tests that a pre-cutoff revision supersedes the initial plan deterministically."""
    session_date = "2026-09-01"
    
    plan_v1 = PlanAdapter.save_plan_snapshot(
        PlanContext(
            session_date=session_date,
            ticker="NQ1",
            preparation_cutoff_utc="2026-09-01T12:45:00Z",
            verbatim_plan_text="Plan Revision 1",
            primary_bias="BULLISH",
            wargamed_scenarios={},
            invalidation_levels={},
            max_intended_risk_bps=10.0,
            permitted_strategies=["STRAT_V1"]
        ),
        db_path=temp_db
    )
    
    plan_v2 = PlanAdapter.save_plan_snapshot(
        PlanContext(
            session_date=session_date,
            ticker="NQ1",
            preparation_cutoff_utc="2026-09-01T12:45:00Z",
            verbatim_plan_text="Plan Revision 2 (Amended bias to Neutral)",
            primary_bias="NEUTRAL",
            wargamed_scenarios={},
            invalidation_levels={},
            max_intended_risk_bps=8.0,
            permitted_strategies=["STRAT_V1", "STRAT_V2"],
            plan_family_id=plan_v1.plan_family_id,
            supersedes_plan_snapshot_id=plan_v1.plan_snapshot_id
        ),
        db_path=temp_db
    )
    
    assert plan_v2.revision_seq == 2
    assert plan_v2.plan_family_id == plan_v1.plan_family_id
    
    resolved = PlanAdapter.get_plan_as_of(
        session_date=session_date,
        ticker="NQ1",
        decision_time_utc="2026-09-01T13:30:00Z",
        db_path=temp_db
    )
    assert resolved is not None
    assert resolved.plan_snapshot_id == plan_v2.plan_snapshot_id
    assert resolved.primary_bias == "NEUTRAL"
    assert resolved.max_intended_risk_bps == 8.0


def test_intraday_plan_amendments(temp_db):
    """Tests that intraday amendments are attached properly when decision_time >= effective_at_utc."""
    session_date = "2026-09-01"
    
    plan = PlanAdapter.save_plan_snapshot(
        PlanContext(
            session_date=session_date,
            ticker="NQ1",
            preparation_cutoff_utc="2026-09-01T12:45:00Z",
            verbatim_plan_text="Initial Plan",
            primary_bias="BULLISH",
            wargamed_scenarios={},
            invalidation_levels={},
            max_intended_risk_bps=12.0,
            permitted_strategies=["STRAT_V1"]
        ),
        db_path=temp_db
    )
    
    amend_time = "2026-09-01T14:00:00Z"
    PlanAdapter.amend_plan(
        plan_snapshot_id=plan.plan_snapshot_id,
        amendment_text="Macro CPI release showed hot inflation. Halving risk to 6 bps.",
        reason_code="MACRO_NEWS",
        effective_at_utc=amend_time,
        amended_risk_bps=6.0,
        db_path=temp_db
    )
    
    # Query before amendment effective time -> 0 amendments attached
    res_early = PlanAdapter.get_plan_as_of(
        session_date=session_date,
        ticker="NQ1",
        decision_time_utc="2026-09-01T13:45:00Z",
        db_path=temp_db
    )
    assert res_early is not None
    assert len(res_early.amendments) == 0
    
    # Query after amendment effective time -> 1 amendment attached
    res_late = PlanAdapter.get_plan_as_of(
        session_date=session_date,
        ticker="NQ1",
        decision_time_utc="2026-09-01T14:30:00Z",
        db_path=temp_db
    )
    assert res_late is not None
    assert len(res_late.amendments) == 1
    assert res_late.amendments[0].amended_risk_bps == 6.0
