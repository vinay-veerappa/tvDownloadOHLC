"""Comprehensive Pytest suite for Trading Second Brain Database Schema & Immutability Triggers."""

import sqlite3
import tempfile
from pathlib import Path

import pytest

from scripts.trading_brain.db.connection import get_db_connection
from scripts.trading_brain.db.init_db import EXPECTED_TABLES, EXPECTED_VIEWS, init_trading_brain_db


@pytest.fixture
def temp_db():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        db_path = Path(tmpdir) / "test_trading_brain.sqlite"
        success, msgs = init_trading_brain_db(db_path=db_path, verbose=False)
        assert success, f"Failed to initialize temp db: {msgs}"
        yield db_path


def test_schema_initialization(temp_db):
    """Verifies that all 22 tables and 4 views are initialized."""
    with get_db_connection(temp_db) as conn:
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = {row["name"] for row in cursor.fetchall()}
        for t in EXPECTED_TABLES:
            assert t in tables, f"Expected table {t} missing"

        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='view';")
        views = {row["name"] for row in cursor.fetchall()}
        for v in EXPECTED_VIEWS:
            assert v in views, f"Expected view {v} missing"

        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='trigger';")
        triggers = {row["name"] for row in cursor.fetchall()}
        assert len(triggers) == 38, f"Expected 38 triggers, found {len(triggers)}"


def test_immutability_triggers_all_tables(temp_db):
    """Tests that UPDATE and DELETE are strictly prohibited on all 19 protected tables."""
    protected_tables_sample_inserts = {
        "information_items": (
            "INSERT INTO information_items (information_id, evidence_class, time_orientation, source_type, title, verbatim_text, available_at_utc) "
            "VALUES ('info-1', 'DOCTRINE', 'EX_ANTE', 'TRANSCRIPT', 'Title 1', 'Doctrine text', '2026-08-28T08:00:00Z');"
        ),
        "information_item_review_events": (
            "INSERT INTO information_item_review_events (review_event_id, information_id, review_state, reviewer) "
            "VALUES ('rev-1', 'info-1', 'ACCEPTED', 'EXPERT_JUDGE');"
        ),
        "plan_snapshots": (
            "INSERT INTO plan_snapshots (plan_snapshot_id, plan_family_id, revision_seq, session_date, ticker, preparation_cutoff_utc, source_system, verbatim_plan_text, primary_bias, wargamed_scenarios_json, invalidation_levels_json, max_intended_risk_bps, permitted_strategies_json, provenance_class) "
            "VALUES ('plan-1', 'fam-1', 1, '2026-08-28', 'NQ1', '2026-08-28T08:45:00Z', 'PRISMA_WEB', 'Plan text', 'BULLISH', '{}', '{}', 10.0, '[]', 'EX_ANTE_DECLARED');"
        ),
        "plan_lifecycle_events": (
            "INSERT INTO plan_lifecycle_events (event_id, plan_snapshot_id, event_type, reason) "
            "VALUES ('evt-1', 'plan-1', 'SUBMITTED', 'Initial declaration');"
        ),
        "plan_amendments": (
            "INSERT INTO plan_amendments (amendment_id, plan_snapshot_id, amendment_seq, effective_at_utc, reason_code, amendment_text) "
            "VALUES ('amend-1', 'plan-1', 1, '2026-08-28T10:00:00Z', 'MACRO_NEWS', 'Amended plan text');"
        ),
        "forecast_run_inputs": (
            "INSERT INTO forecast_runs (forecast_run_id, session_date, ticker, model_version_id, effective_cutoff_utc, commit_grace_period_sec, status) "
            "VALUES ('run-1', '2026-08-28', 'NQ1', 'MOD_V1', '2026-08-28T08:45:00Z', 120, 'CREATED');\n"
            "INSERT INTO forecast_run_inputs (input_id, forecast_run_id, provider_name, data_type, max_timestamp_utc, content_hash) "
            "VALUES ('inp-1', 'run-1', 'ALN', 'BARS', '2026-08-28T08:45:00Z', 'hash-1');"
        ),
        "forecast_snapshots": (
            "INSERT INTO forecast_snapshots (forecast_id, session_date, ticker, model_version_id, forecast_mode, effective_cutoff_utc, prob_r1, prob_r2, prob_dnp, prob_dwp, prob_rotational_chop, git_hash, config_hash) "
            "VALUES ('fc-1', '2026-08-28', 'NQ1', 'MOD_V1', 'LIVE_PRODUCTION', '2026-08-28T08:45:00Z', 0.2, 0.2, 0.2, 0.2, 0.2, 'githash', 'confighash');"
        ),
        "signal_opportunities": (
            "INSERT INTO signal_opportunities (opportunity_id, session_date, ticker, strategy_version_id, bar_timestamp_utc, decision_time_utc, trigger_price, declared_stop_price, declared_target_1_price, stop_distance_bps, target_1_bps, feature_manifest_json, evaluation_mode) "
            "VALUES ('opp-1', '2026-08-28', 'NQ1', 'STRAT_V1', '2026-08-28T09:35:00Z', '2026-08-28T09:35:00Z', 20000.0, 19980.0, 20020.0, 10.0, 10.0, '{}', 'LIVE_CAPTURE');"
        ),
        "signal_disposition_events": (
            "INSERT INTO signal_disposition_events (disposition_id, opportunity_id, disposition_state, source_system) "
            "VALUES ('disp-1', 'opp-1', 'EXECUTED', 'MECHANICAL_RECONCILER');"
        ),
        "signal_outcomes": (
            "INSERT INTO signal_outcomes (outcome_id, opportunity_id, observed_outcome, pessimistic_bound, optimistic_bound, realized_mfe_bps, realized_mae_bps, bars_held, evaluated_at_utc) "
            "VALUES ('out-1', 'opp-1', 'TARGET_REACHED', 'STOP_HIT', 'TARGET_REACHED', 15.0, 3.0, 5, '2026-08-28T16:00:00Z');"
        ),
        "session_tape_actuals": (
            "INSERT INTO session_tape_actuals (actual_id, session_date, ticker, revision_seq, contract_id, source_system, session_open, session_high, session_low, session_close, rth_close, hod_timestamp_utc, lod_timestamp_utc, session_range_bps, day_type_classification, content_hash, quality_state) "
            "VALUES ('act-1', '2026-08-28', 'NQ1', 1, 'NQU6', 'LIVE_STORAGE_PARQUET', 20000.0, 20100.0, 19950.0, 20050.0, 20050.0, '2026-08-28T14:00:00Z', '2026-08-28T10:00:00Z', 75.0, 'ROTATIONAL_CHOP', 'hash', 'CLEAN');"
        ),
        "execution_events": (
            "INSERT INTO execution_events (execution_id, session_date, ticker, account_id, broker_execution_id, broker_order_id, order_action, order_type, quantity, fill_price, idempotency_key, event_timestamp_utc) "
            "VALUES ('exec-1', '2026-08-28', 'NQ1', 'ACC1', 'b-exec-1', 'b-ord-1', 'BUY', 'MARKET', 1, 20000.0, 'idemp-1', '2026-08-28T09:35:01Z');"
        ),
        "intervention_events": (
            "INSERT INTO intervention_events (intervention_id, session_date, ticker, account_id, producer, producer_version, authority_class, action_mode, rule_id, rule_version, enforced, idempotency_key, event_timestamp_utc) "
            "VALUES ('int-1', '2026-08-28', 'NQ1', 'ACC1', 'NT8_RISKGUARD_CS', '1.0', 'HARD_LOCKOUT_ENFORCED', 'ACTING', 'DAILY_FLOOR', '1.0', 1, 'int-idemp-1', '2026-08-28T11:00:00Z');"
        ),
        "drill_attempts": (
            "INSERT INTO drill_attempts (attempt_id, drill_id, drill_type, dataset_split, declared_bias, declared_setup, answer_locked_at_utc, process_adherence_score, rule_match_flag, latency_ms) "
            "VALUES ('drill-1', 'd-1', 'RECOGNITION', 'TRAINING', 'BULLISH', 'ALN_LPEU', '2026-08-28T08:00:00Z', 95.0, 1, 1200);"
        ),
        "behavioral_declarations": (
            "INSERT INTO behavioral_declarations (declaration_id, session_date, user_id, declaration_type, reflection_notes) "
            "VALUES ('beh-1', '2026-08-28', 'user-1', 'POST_SESSION_REFLECTION', 'Followed the wargame rules.');"
        ),
        "unmatched_link_events": (
            "INSERT INTO unmatched_link_events (link_event_id, execution_id, candidate_opportunity_ids_json, resolution_status) "
            "VALUES ('link-1', 'exec-1', '[]', 'OPEN');"
        ),
        "candidate_finding_events": (
            "INSERT INTO candidate_finding_events (finding_event_id, finding_id, model_version_id, pipeline_stage, evaluation_result_json, actor) "
            "VALUES ('find-1', 'f-1', 'MOD_V1', 'DISCOVERY', '{}', 'RESEARCH_AGENT');"
        ),
        "strategy_versions": (
            "INSERT INTO strategy_versions (strategy_version_id, strategy_family, version_tag, content_hash, rules_doc_path, execution_policy_json, status) "
            "VALUES ('STRAT_V1', 'ALN_LPEU', '0.1.0', 'hash', 'docs/strat.md', '{}', 'EXPERIMENTAL_CAPTURE_ONLY');"
        ),
        "model_versions": (
            "INSERT INTO model_versions (model_version_id, model_family, version_tag, parameter_hash, feature_manifest_json, calibration_metrics_json, status) "
            "VALUES ('MOD_V1', 'PROFILER_DAY_TYPE', '1.0.0', 'hash', '{}', '{}', 'SHADOW');"
        )
    }

    with get_db_connection(temp_db) as conn:
        for table, insert_sql in protected_tables_sample_inserts.items():
            conn.executescript(insert_sql)

        for table in protected_tables_sample_inserts.keys():
            with pytest.raises(sqlite3.DatabaseError) as excinfo:
                conn.execute(f"UPDATE {table} SET rowid = rowid + 0;")
            assert f"UPDATE operation prohibited on immutable table {table}" in str(excinfo.value)

            with pytest.raises(sqlite3.DatabaseError) as excinfo:
                conn.execute(f"DELETE FROM {table};")
            assert f"DELETE operation prohibited on immutable table {table}" in str(excinfo.value)


def test_session_tape_actuals_revisions_and_view(temp_db):
    """Tests that session_tape_actuals allows revisions (v1 suspect -> v2 clean) and view resolves latest."""
    with get_db_connection(temp_db) as conn:
        # Revision 1 (Suspect)
        conn.execute(
            """
            INSERT INTO session_tape_actuals (
                actual_id, session_date, ticker, revision_seq, source_system,
                session_open, session_high, session_low, session_close, rth_close,
                session_range_bps, day_type_classification, content_hash, quality_state
            ) VALUES ('act-v1', '2026-08-28', 'NQ1', 1, 'STORAGE', 20000.0, 20100.0, 19900.0, 20050.0, 20050.0, 100.0, 'R1', 'h1', 'SUSPECT_TICKS');
            """
        )
        
        # Revision 2 (Clean respun) supersedes v1
        conn.execute(
            """
            INSERT INTO session_tape_actuals (
                actual_id, session_date, ticker, revision_seq, supersedes_actual_id, source_system,
                session_open, session_high, session_low, session_close, rth_close,
                session_range_bps, day_type_classification, content_hash, quality_state
            ) VALUES ('act-v2', '2026-08-28', 'NQ1', 2, 'act-v1', 'STORAGE', 20000.0, 20100.0, 19950.0, 20050.0, 20050.0, 75.0, 'ROTATIONAL_CHOP', 'h2', 'CLEAN');
            """
        )
        
        # View resolves Revision 2
        cur = conn.execute("SELECT * FROM v_session_tape_actuals_current WHERE session_date = '2026-08-28' AND ticker = 'NQ1';")
        row = cur.fetchone()
        assert row is not None
        assert row["actual_id"] == "act-v2"
        assert row["revision_seq"] == 2
        assert row["quality_state"] == "CLEAN"
        assert row["day_type_classification"] == "ROTATIONAL_CHOP"


def test_information_item_review_events_and_view(temp_db):
    """Tests that information_items review transitions are recorded in ledger and resolved via view."""
    with get_db_connection(temp_db) as conn:
        conn.execute(
            """
            INSERT INTO information_items (information_id, evidence_class, time_orientation, source_type, title, verbatim_text, available_at_utc)
            VALUES ('info-item-1', 'DOCTRINE', 'EX_ANTE', 'TRANSCRIPT', 'Item 1', 'Content', '2026-08-28T08:00:00Z');
            """
        )
        
        # Initial view state is default 'CAPTURED'
        cur = conn.execute("SELECT * FROM v_information_items_active WHERE information_id = 'info-item-1';")
        assert cur.fetchone()["active_review_state"] == "CAPTURED"
        
        # Add ACCEPTED review event
        conn.execute(
            """
            INSERT INTO information_item_review_events (review_event_id, information_id, review_state, reviewer)
            VALUES ('rev-1', 'info-item-1', 'ACCEPTED', 'EXPERT_USER');
            """
        )
        
        # View now reflects ACCEPTED
        cur = conn.execute("SELECT * FROM v_information_items_active WHERE information_id = 'info-item-1';")
        assert cur.fetchone()["active_review_state"] == "ACCEPTED"
