"""Pytest suite for PlanAdapter (Milestone 0.2)."""

import os
import sqlite3
import tempfile
from pathlib import Path
import pytest

import pytest as _pytest

from scripts.trading_brain.db.init_db import init_trading_brain_db
from scripts.trading_brain.plans.plan_adapter import PlanAdapter, PlanContext

# Fixture capability: several of these tests verify MIGRATION-path semantics
# (historical receipt assertion). The capability flag simulates the migration
# tooling environment; production callers do not have it set.
os.environ.setdefault("TRADING_BRAIN_ALLOW_RECEIPT_OVERRIDE", "1")

@pytest.fixture
def temp_db():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        db_path = Path(tmpdir) / "test_trading_brain.sqlite"
        init_trading_brain_db(db_path=db_path, verbose=False)
        yield db_path

def test_receipt_override_capability_gate(temp_db):
    """F7/F10: without the migration capability, no receipt override is possible; with
    it, the plan is stamped HISTORICAL_SOURCE_ASSERTED (NOT live ex-ante authority)."""
    plan = PlanContext(
        session_date="2026-08-28", ticker="NQ1", preparation_cutoff_utc="2026-08-28T12:45:00Z",
        verbatim_plan_text="Asserted Plan", primary_bias="BULLISH", wargamed_scenarios={},
        invalidation_levels={}, max_intended_risk_bps=10.0, permitted_strategies=[]
    )
    env_flag = os.environ.pop("TRADING_BRAIN_ALLOW_RECEIPT_OVERRIDE", None)
    try:
        # Capability absent (production default) -> override refused outright.
        with _pytest.raises(ValueError, match="migration capability"):
            PlanAdapter.save_plan_snapshot(
                plan, db_path=temp_db, received_at_utc="2026-08-28T12:30:00Z",
                override_reason="attempt without capability", override_actor="ROGUE_CALLER",
            )
    finally:
        if env_flag is not None:
            os.environ["TRADING_BRAIN_ALLOW_RECEIPT_OVERRIDE"] = env_flag
    # Restore capability and verify the asserted provenance contract.
    os.environ["TRADING_BRAIN_ALLOW_RECEIPT_OVERRIDE"] = "1"
    plan_id = PlanAdapter.save_plan_snapshot(
        plan, db_path=temp_db, received_at_utc="2026-08-28T12:30:00Z",
        override_reason="migration fixture", override_actor="MIGRATION_TOOL",
    )
    with sqlite3.connect(str(temp_db)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT provenance_class FROM plan_snapshots WHERE plan_snapshot_id = ?;", (plan_id,)).fetchone()
    assert row["provenance_class"] == "HISTORICAL_SOURCE_ASSERTED"
    # Asserted provenance is NOT sufficient for live compliance evaluation (F10).
    resolved = PlanAdapter.get_plan_as_of("2026-08-28", "NQ1", "2026-08-28T13:00:00Z", db_path=temp_db)
    assert resolved is None

def test_save_and_resolve_single_plan(temp_db):
    plan = PlanContext(
        session_date="2026-08-28", ticker="NQ1", preparation_cutoff_utc="2026-08-28T12:45:00Z",
        verbatim_plan_text="Test Plan text", primary_bias="BULLISH", wargamed_scenarios={"sc1": "LPEU"},
        invalidation_levels={"inv1": 19950.0}, max_intended_risk_bps=10.0, permitted_strategies=["STRAT_ALN_LPEU_V0_1"]
    )
    plan_id = PlanAdapter.save_plan_snapshot(plan, db_path=temp_db, received_at_utc="2026-08-28T12:30:00Z", override_reason="historical migration fixture", override_actor="TEST_FIXTURE")
    assert plan_id is not None
    PlanAdapter.verify_historical_snapshot(plan_id, verifier="TEST_FIXTURE", reason="verified against exported chart", db_path=temp_db, verified_effective_from_utc="2026-08-28T12:00:00Z")

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
    ante_id = PlanAdapter.save_plan_snapshot(plan_ante, db_path=temp_db, received_at_utc="2026-08-28T12:30:00Z", override_reason="historical migration fixture", override_actor="TEST_FIXTURE")
    PlanAdapter.verify_historical_snapshot(ante_id, verifier="TEST_FIXTURE", reason="verified", db_path=temp_db, verified_effective_from_utc="2026-08-28T12:00:00Z")

    # Post-hoc reconstruction with a preparation cutoff AFTER the query time must not shadow the ex-ante plan
    plan_post = PlanContext(
        session_date="2026-08-28", ticker="NQ1", preparation_cutoff_utc="2026-08-28T20:00:00Z",
        verbatim_plan_text="Post-Hoc Plan", primary_bias="BEARISH", wargamed_scenarios={},
        invalidation_levels={}, max_intended_risk_bps=10.0, permitted_strategies=["STRAT_1"],
        provenance_class="POST_HOC_RECONSTRUCTION", supersedes_plan_snapshot_id=ante_id
    )
    PlanAdapter.save_plan_snapshot(plan_post, db_path=temp_db)

    # Historical query at 13:00 must STILL return the ex-ante plan with full authority
    resolved = PlanAdapter.get_plan_as_of("2026-08-28", "NQ1", "2026-08-28T13:00:00Z", db_path=temp_db)
    assert resolved is not None
    assert resolved.plan_snapshot_id == ante_id
    assert resolved.primary_bias == "BULLISH"
    # The post-hoc plan is in the DB but must not be eligible for as-of queries before its preparation cutoff
    post_rows = sqlite3.connect(str(temp_db)).execute(
        "SELECT COUNT(*) FROM plan_snapshots WHERE provenance_class='POST_HOC_RECONSTRUCTION'"
    ).fetchone()[0]
    assert post_rows == 1

def test_plan_revision_supersession(temp_db):
    plan_v1 = PlanContext(
        session_date="2026-08-28", ticker="NQ1", preparation_cutoff_utc="2026-08-28T12:45:00Z",
        verbatim_plan_text="Plan Rev 1", primary_bias="BULLISH", wargamed_scenarios={},
        invalidation_levels={}, max_intended_risk_bps=10.0, permitted_strategies=["STRAT_1"]
    )
    v1_id = PlanAdapter.save_plan_snapshot(plan_v1, db_path=temp_db, received_at_utc="2026-08-28T12:30:00Z", override_reason="historical migration fixture", override_actor="TEST_FIXTURE")
    PlanAdapter.verify_historical_snapshot(v1_id, verifier="TEST_FIXTURE", reason="verified", db_path=temp_db, verified_effective_from_utc="2026-08-28T12:00:00Z")

    plan_v2 = PlanContext(
        session_date="2026-08-28", ticker="NQ1", preparation_cutoff_utc="2026-08-28T12:45:00Z",
        verbatim_plan_text="Plan Rev 2 (Pre-cutoff revision)", primary_bias="NEUTRAL", wargamed_scenarios={},
        invalidation_levels={}, max_intended_risk_bps=5.0, permitted_strategies=["STRAT_1"],
        supersedes_plan_snapshot_id=v1_id
    )
    v2_id = PlanAdapter.save_plan_snapshot(plan_v2, db_path=temp_db, received_at_utc="2026-08-28T12:35:00Z", override_reason="historical migration fixture", override_actor="TEST_FIXTURE")
    PlanAdapter.verify_historical_snapshot(v2_id, verifier="TEST_FIXTURE", reason="verified", db_path=temp_db, verified_effective_from_utc="2026-08-28T12:00:00Z")

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
    plan_id = PlanAdapter.save_plan_snapshot(plan, db_path=temp_db, received_at_utc="2026-08-28T12:30:00Z", override_reason="historical migration fixture", override_actor="TEST_FIXTURE")
    PlanAdapter.verify_historical_snapshot(plan_id, verifier="TEST_FIXTURE", reason="verified", db_path=temp_db, verified_effective_from_utc="2026-08-28T12:00:00Z")

    with sqlite3.connect(str(temp_db)) as conn:
        conn.execute(
            """
            INSERT INTO plan_amendments (
                amendment_id, plan_snapshot_id, amendment_seq, effective_at_utc,
                received_at_utc, reason_code, amendment_text, amended_bias, amended_risk_bps
            ) VALUES ('amd-1', ?, 1, '2026-08-28T14:30:00Z', '2026-08-28T14:30:00Z',
                      'REGIME_CHANGE', 'Invalidation breached', 'BEARISH', 5.0);
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




def test_unverified_assertion_does_not_mask_verified_ex_ante(temp_db):
    """Round-5 F1 regression: an unverified HISTORICAL_SOURCE_ASSERTED revision must be
    excluded IN SQL so an older eligible EX_ANTE plan still resolves (never None)."""
    p1 = PlanContext(
        session_date="2020-01-02", ticker="NQ1", preparation_cutoff_utc="2020-01-02T13:45:00Z",
        verbatim_plan_text="Ex-ante", primary_bias="BULLISH", wargamed_scenarios={},
        invalidation_levels={}, max_intended_risk_bps=10.0, permitted_strategies=["S1"]
    )
    id1 = PlanAdapter.save_plan_snapshot(p1, db_path=temp_db, received_at_utc="2020-01-02T12:30:00Z",
        override_reason="migration", override_actor="MIG")
    PlanAdapter.verify_historical_snapshot(id1, verifier="V", reason="chart evidence E-9", db_path=temp_db,
        verified_effective_from_utc="2020-01-02T13:00:00Z")
    # Newer revision, UNVERIFIED -> excluded from eligibility entirely.
    id2 = PlanAdapter.save_plan_snapshot(
        PlanContext(session_date="2020-01-02", ticker="NQ1", preparation_cutoff_utc="2020-01-02T13:45:00Z",
            verbatim_plan_text="Asserted-unverified", primary_bias="BEARISH", wargamed_scenarios={},
            invalidation_levels={}, max_intended_risk_bps=5.0, permitted_strategies=["S1"]),
        db_path=temp_db, received_at_utc="2020-01-02T12:35:00Z", override_reason="migration", override_actor="MIG")

    resolved = PlanAdapter.get_plan_as_of("2020-01-02", "NQ1", "2020-01-02T14:00:00Z", db_path=temp_db)
    assert resolved is not None, "unverified assertion masked the eligible ex-ante plan"
    assert resolved.plan_snapshot_id == id1


def test_verification_is_not_retroactive_without_evidence(temp_db):
    """Round-5 F3: a verification performed in 2026 does not change a 2020 as-of query.
    Evidenced effective-from grants authority from that verified instant onward."""
    plan = PlanContext(
        session_date="2020-01-02", ticker="NQ1", preparation_cutoff_utc="2020-01-02T13:45:00Z",
        verbatim_plan_text="Asserted", primary_bias="BULLISH", wargamed_scenarios={},
        invalidation_levels={}, max_intended_risk_bps=10.0, permitted_strategies=["S1"]
    )
    pid = PlanAdapter.save_plan_snapshot(plan, db_path=temp_db, received_at_utc="2020-01-02T12:30:00Z",
        override_reason="migration", override_actor="MIG")

    # As recorded: bare 2026 verification (verifier is a migration action performed
    # now) must NOT grant authority for a 2020-01-02 14:00 query.
    PlanAdapter.verify_historical_snapshot(pid, verifier="V", reason="late bare verification", db_path=temp_db)
    resolved_asrecorded = PlanAdapter.get_plan_as_of("2020-01-02", "NQ1", "2020-01-02T14:00:00Z", db_path=temp_db)
    assert resolved_asrecorded is None, "bare verification retroactively rewrote history"

    # Evidenced contemporaneous validity: authority from the verified instant.
    pid2 = PlanAdapter.save_plan_snapshot(
        PlanContext(session_date="2020-01-02", ticker="NQ1", preparation_cutoff_utc="2020-01-02T13:45:00Z",
            verbatim_plan_text="Asserted-evidenced", primary_bias="BEARISH", wargamed_scenarios={},
            invalidation_levels={}, max_intended_risk_bps=5.0, permitted_strategies=["S1"]),
        db_path=temp_db, received_at_utc="2020-01-02T12:35:00Z", override_reason="migration", override_actor="MIG")
    PlanAdapter.verify_historical_snapshot(pid2, verifier="V", reason="broker export B-2", db_path=temp_db,
        verified_effective_from_utc="2020-01-02T13:00:00Z")
    before = PlanAdapter.get_plan_as_of("2020-01-02", "NQ1", "2020-01-02T12:45:00Z", db_path=temp_db)
    after = PlanAdapter.get_plan_as_of("2020-01-02", "NQ1", "2020-01-02T14:00:00Z", db_path=temp_db)
    assert before is None                      # prep cutoff + effective-from not yet reached
    assert after is not None and after.plan_snapshot_id == pid2

    # Administrative view explicitly names itself and bypasses the receipt bound
    # (still respects the preparation cutoff).
    admin = PlanAdapter.get_plan_as_of("2020-01-02", "NQ1", "2020-01-02T14:00:00Z",
        db_path=temp_db, knowledge_mode="CURRENTLY_VERIFIED_HISTORY")
    assert admin is not None and admin.plan_snapshot_id == pid2


def test_service_startup_refuses_migration_capability_flag():
    """Round-5 F4: the receipt-override capability is a migration-process license.
    A long-running service refuses to start with the flag enabled."""
    env_flag = os.environ.pop("TRADING_BRAIN_ALLOW_RECEIPT_OVERRIDE", None)
    os.environ["TRADING_BRAIN_ALLOW_RECEIPT_OVERRIDE"] = "1"
    try:
        with _pytest.raises(RuntimeError, match="SAFETY REFUSAL"):
            PlanAdapter.assert_next_process_is_migration()
    finally:
        if env_flag is None:
            os.environ.pop("TRADING_BRAIN_ALLOW_RECEIPT_OVERRIDE", None)
        else:
            os.environ["TRADING_BRAIN_ALLOW_RECEIPT_OVERRIDE"] = env_flag
    # Normal services (flag unset) boot fine.
    os.environ.pop("TRADING_BRAIN_ALLOW_RECEIPT_OVERRIDE", None)
    PlanAdapter.assert_next_process_is_migration()  # no raise
    if env_flag is not None:
        os.environ["TRADING_BRAIN_ALLOW_RECEIPT_OVERRIDE"] = env_flag
