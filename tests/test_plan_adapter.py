"""Pytest suite for PlanAdapter (Milestone 0.2)."""

import sqlite3
import tempfile
from pathlib import Path
import pytest

from scripts.trading_brain.db.init_db import init_trading_brain_db
from scripts.trading_brain.plans.plan_adapter import PlanAdapter, PlanContext

@pytest.fixture
def temp_db():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        db_path = Path(tmpdir) / "test_trading_brain.sqlite"
        init_trading_brain_db(db_path=db_path, verbose=False)
        yield db_path

def test_save_and_resolve_single_plan(temp_db):
    plan = PlanContext(
        session_date="2026-08-28", ticker="NQ1", preparation_cutoff_utc="2026-08-28T12:45:00Z",
        verbatim_plan_text="Test Plan text", primary_bias="BULLISH", wargamed_scenarios={"sc1": "LPEU"},
        invalidation_levels={"inv1": 19950.0}, max_intended_risk_bps=10.0, permitted_strategies=["STRAT_ALN_LPEU_V0_1"]
    )
    plan_id = PlanAdapter.save_plan_snapshot(plan, db_path=temp_db)
    assert plan_id is not None

    resolved = PlanAdapter.get_plan_as_of("2026-08-28", "NQ1", "2026-08-28T13:00:00Z", db_path=temp_db)
    assert resolved is not None
    assert resolved.primary_bias == "BULLISH"
    assert resolved.effective_primary_bias == "BULLISH"

def test_post_hoc_plan_does_not_supersede_ex_ante_plan(temp_db):
    # Ex-ante plan
    plan_ante = PlanContext(
        session_date="2026-08-28", ticker="NQ1", preparation_cutoff_utc="2026-08-28T12:45:00Z",
        verbatim_plan_text="Ex-Ante Plan", primary_bias="BULLISH", wargamed_scenarios={},
        invalidation_levels={}, max_intended_risk_bps=10.0, permitted_strategies=["STRAT_1"],
        provenance_class="EX_ANTE"
    )
    ante_id = PlanAdapter.save_plan_snapshot(plan_ante, db_path=temp_db)

    # Post-hoc reconstruction referencing ex-ante plan
    plan_post = PlanContext(
        session_date="2026-08-28", ticker="NQ1", preparation_cutoff_utc="2026-08-28T20:00:00Z",
        verbatim_plan_text="Post-Hoc Plan", primary_bias="BEARISH", wargamed_scenarios={},
        invalidation_levels={}, max_intended_risk_bps=10.0, permitted_strategies=["STRAT_1"],
        provenance_class="POST_HOC_RECONSTRUCTION", supersedes_plan_snapshot_id=ante_id
    )
    PlanAdapter.save_plan_snapshot(plan_post, db_path=temp_db)

    # Historical query must STILL return the ex-ante plan with full authority
    resolved = PlanAdapter.get_plan_as_of("2026-08-28", "NQ1", "2026-08-28T13:00:00Z", db_path=temp_db)
    assert resolved is not None
    assert resolved.plan_snapshot_id == ante_id
    assert resolved.primary_bias == "BULLISH"

def test_plan_revision_supersession(temp_db):
    plan_v1 = PlanContext(
        session_date="2026-08-28", ticker="NQ1", preparation_cutoff_utc="2026-08-28T12:45:00Z",
        verbatim_plan_text="Plan Rev 1", primary_bias="BULLISH", wargamed_scenarios={},
        invalidation_levels={}, max_intended_risk_bps=10.0, permitted_strategies=["STRAT_1"]
    )
    v1_id = PlanAdapter.save_plan_snapshot(plan_v1, db_path=temp_db)

    plan_v2 = PlanContext(
        session_date="2026-08-28", ticker="NQ1", preparation_cutoff_utc="2026-08-28T12:45:00Z",
        verbatim_plan_text="Plan Rev 2 (Pre-cutoff revision)", primary_bias="NEUTRAL", wargamed_scenarios={},
        invalidation_levels={}, max_intended_risk_bps=5.0, permitted_strategies=["STRAT_1"],
        supersedes_plan_snapshot_id=v1_id
    )
    v2_id = PlanAdapter.save_plan_snapshot(plan_v2, db_path=temp_db)

    resolved = PlanAdapter.get_plan_as_of("2026-08-28", "NQ1", "2026-08-28T13:00:00Z", db_path=temp_db)
    assert resolved is not None
    assert resolved.plan_snapshot_id == v2_id
    assert resolved.primary_bias == "NEUTRAL"
    assert resolved.revision_seq == 2

def test_intraday_plan_amendments(temp_db):
    plan = PlanContext(
        session_date="2026-08-28", ticker="NQ1", preparation_cutoff_utc="2026-08-28T12:45:00Z",
        verbatim_plan_text="Base Plan", primary_bias="BULLISH", wargamed_scenarios={},
        invalidation_levels={}, max_intended_risk_bps=10.0, permitted_strategies=["STRAT_1"]
    )
    plan_id = PlanAdapter.save_plan_snapshot(plan, db_path=temp_db)

    with sqlite3.connect(str(temp_db)) as conn:
        conn.execute(
            """
            INSERT INTO plan_amendments (
                amendment_id, plan_snapshot_id, amendment_seq, effective_at_utc,
                reason_code, amendment_text, amended_bias, amended_risk_bps
            ) VALUES ('amd-1', ?, 1, '2026-08-28T14:30:00Z', 'REGIME_CHANGE', 'Invalidation breached', 'BEARISH', 5.0);
            """,
            (plan_id,)
        )

    # Before amendment (14:00 UTC)
    pre_amd = PlanAdapter.get_plan_as_of("2026-08-28", "NQ1", "2026-08-28T14:00:00Z", db_path=temp_db)
    assert pre_amd.effective_primary_bias == "BULLISH"
    assert pre_amd.effective_max_intended_risk_bps == 10.0

    # After amendment (15:00 UTC)
    post_amd = PlanAdapter.get_plan_as_of("2026-08-28", "NQ1", "2026-08-28T15:00:00Z", db_path=temp_db)
    assert post_amd.effective_primary_bias == "BEARISH"
    assert post_amd.effective_max_intended_risk_bps == 5.0
    assert len(post_amd.effective_permitted_strategies) == 1
