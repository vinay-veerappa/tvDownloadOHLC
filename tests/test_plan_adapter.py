"""Pytest suite for PlanAdapter and deterministic as-of authority resolution."""

import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from scripts.trading_brain.db.init_db import init_trading_brain_db
from scripts.trading_brain.plans.plan_adapter import PlanAdapter, PlanContext


@pytest.fixture
def temp_db():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_trading_brain.sqlite"
        init_trading_brain_db(db_path=db_path, verbose=False)
        yield db_path


def test_save_and_resolve_single_plan(temp_db):
    """Tests saving a basic ex-ante plan and resolving it as-of decision time."""
    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(minutes=30)  # in the future -> EX_ANTE_DECLARED
    
    plan = PlanContext(
        session_date="2026-08-28",
        ticker="NQ1",
        preparation_cutoff_utc=cutoff.isoformat(),
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
    
    # Query as-of 10 minutes later
    resolved = PlanAdapter.get_plan_as_of(
        session_date="2026-08-28",
        ticker="NQ1",
        decision_time_utc=now + timedelta(minutes=10),
        db_path=temp_db
    )
    assert resolved is not None
    assert resolved.plan_snapshot_id == saved.plan_snapshot_id
    assert resolved.primary_bias == "BULLISH"
    assert resolved.max_intended_risk_bps == 12.0


def test_plan_revision_supersession(temp_db):
    """Tests that a pre-cutoff revision supersedes the initial plan deterministically."""
    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(minutes=45)
    
    # Initial 08:20 Plan
    plan_v1 = PlanAdapter.save_plan_snapshot(
        PlanContext(
            session_date="2026-08-28",
            ticker="NQ1",
            preparation_cutoff_utc=cutoff.isoformat(),
            verbatim_plan_text="Plan Revision 1",
            primary_bias="BULLISH",
            wargamed_scenarios={},
            invalidation_levels={},
            max_intended_risk_bps=10.0,
            permitted_strategies=["STRAT_V1"]
        ),
        db_path=temp_db
    )
    
    # Revision 08:35 Plan (Supersedes v1)
    plan_v2 = PlanAdapter.save_plan_snapshot(
        PlanContext(
            session_date="2026-08-28",
            ticker="NQ1",
            preparation_cutoff_utc=cutoff.isoformat(),
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
    
    # Resolving now returns plan_v2
    resolved = PlanAdapter.get_plan_as_of(
        session_date="2026-08-28",
        ticker="NQ1",
        decision_time_utc=now + timedelta(minutes=5),
        db_path=temp_db
    )
    assert resolved is not None
    assert resolved.plan_snapshot_id == plan_v2.plan_snapshot_id
    assert resolved.primary_bias == "NEUTRAL"
    assert resolved.max_intended_risk_bps == 8.0


def test_intraday_plan_amendments(temp_db):
    """Tests that intraday amendments are attached properly when decision_time >= effective_at_utc."""
    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(minutes=30)
    
    plan = PlanAdapter.save_plan_snapshot(
        PlanContext(
            session_date="2026-08-28",
            ticker="NQ1",
            preparation_cutoff_utc=cutoff.isoformat(),
            verbatim_plan_text="Initial Plan",
            primary_bias="BULLISH",
            wargamed_scenarios={},
            invalidation_levels={},
            max_intended_risk_bps=12.0,
            permitted_strategies=["STRAT_V1"]
        ),
        db_path=temp_db
    )
    
    # Add an amendment effective at 10:00 ET (now + 1 hour)
    amend_time = now + timedelta(hours=1)
    PlanAdapter.amend_plan(
        plan_snapshot_id=plan.plan_snapshot_id,
        amendment_text="Macro CPI release showed hot inflation. Halving risk to 6 bps.",
        reason_code="MACRO_NEWS",
        effective_at_utc=amend_time,
        amended_risk_bps=6.0,
        db_path=temp_db
    )
    
    # 1. Query before amendment effective time (09:45 ET) -> 0 amendments attached
    res_early = PlanAdapter.get_plan_as_of(
        session_date="2026-08-28",
        ticker="NQ1",
        decision_time_utc=now + timedelta(minutes=15),
        db_path=temp_db
    )
    assert res_early is not None
    assert len(res_early.amendments) == 0
    
    # 2. Query after amendment effective time (10:15 ET) -> 1 amendment attached
    res_late = PlanAdapter.get_plan_as_of(
        session_date="2026-08-28",
        ticker="NQ1",
        decision_time_utc=now + timedelta(hours=2),
        db_path=temp_db
    )
    assert res_late is not None
    assert len(res_late.amendments) == 1
    assert res_late.amendments[0].amended_risk_bps == 6.0
    assert res_late.amendments[0].reason_code == "MACRO_NEWS"


def test_post_hoc_plan_never_supersedes_ex_ante(temp_db):
    """Tests that a plan created after cutoff is tagged POST_HOC_RECONSTRUCTION and ignored by get_plan_as_of."""
    past_cutoff = datetime.now(timezone.utc) - timedelta(hours=2)
    
    post_hoc_plan = PlanAdapter.save_plan_snapshot(
        PlanContext(
            session_date="2026-08-28",
            ticker="NQ1",
            preparation_cutoff_utc=past_cutoff.isoformat(),
            verbatim_plan_text="Late submitted plan at 16:30",
            primary_bias="BEARISH",
            wargamed_scenarios={},
            invalidation_levels={},
            max_intended_risk_bps=10.0,
            permitted_strategies=[]
        ),
        db_path=temp_db
    )
    
    assert post_hoc_plan.provenance_class == "POST_HOC_RECONSTRUCTION"
    
    # get_plan_as_of should find no ex-ante plan
    resolved = PlanAdapter.get_plan_as_of(
        session_date="2026-08-28",
        ticker="NQ1",
        decision_time_utc=datetime.now(timezone.utc),
        db_path=temp_db
    )
    assert resolved is None


def test_prisma_adapter(temp_db):
    """Tests adapting a Prisma TradePlan dictionary."""
    cutoff = datetime.now(timezone.utc) + timedelta(minutes=30)
    prisma_dict = {
        "id": "prisma-c12345",
        "symbol": "NQ1",
        "date": "2026-08-28",
        "bias": "BULLISH",
        "planText": "Wargame Plan from Web UI",
        "maxRiskBps": 14.0,
        "strategies": ["STRAT_FIRECRACKER_V0_1"],
        "scenarios": {"expansion": "Drive up at 09:30"}
    }
    
    saved = PlanAdapter.snapshot_prisma_plan(prisma_dict, preparation_cutoff_utc=cutoff, db_path=temp_db)
    assert saved.source_system == "PRISMA_WEB"
    assert saved.source_plan_id == "prisma-c12345"
    assert saved.primary_bias == "BULLISH"
    assert saved.max_intended_risk_bps == 14.0
