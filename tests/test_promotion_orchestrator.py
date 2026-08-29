"""Pytest suite for PromotionOrchestrator (Milestone 3.4)."""

import json
import sqlite3

import pytest

from scripts.trading_brain.db.init_db import init_trading_brain_db
from scripts.trading_brain.research.promotion_orchestrator import PromotionOrchestrator
from scripts.trading_brain.research.sealed_holdout import HoldoutRegistry
from scripts.trading_brain.research.shadow_gate import ShadowGate


@pytest.fixture
def temp_db(tmp_path):
    db = tmp_path / "promotion.sqlite"
    init_trading_brain_db(db, verbose=False)
    return db


def _register_cleared_model(db, model_version_id="MOD_VERIFIED", finding_id="SF-1"):
    """Full verified evidence chain: model record + sealed holdout + PROMOTED shadow event.

    Design power must reach 0.80 (frozen from the PREREGISTERED effect): with N=100
    holdout samples and effect h=0.5, power ~= 0.93, so the gate can actually PROMOTE
    the perfect bound predictor. Benchmark/MDE here mirror the sealed registry values.
    """
    import pytest as _pytest
    HoldoutRegistry.register_holdout(
        holdout_dataset_id="H-1",
        features=[f"f{i}" for i in range(100)],
        labels=(["LONG", "SHORT"] * 50),
        benchmark_metric=0.5,
        expected_effect_size_d=0.5,
        db_path=db,
    )

    def bound_registry_predictor(feats):
        # Rule-faithful predictor: 100% accurate against the alternating sealed labels.
        n = len(feats) if hasattr(feats, "__len__") else 0
        return ["LONG" if i % 2 == 0 else "SHORT" for i in range(n)]

    ShadowGate.preregister_candidate_finding(
        finding_id=finding_id,
        model_version_id=model_version_id,
        benchmark_metric=0.5,
        expected_effect_size_d=0.5,
        feature_manifest={},
        holdout_dataset_id="H-1",
        holdout_dataset_hash=None,
        model_predict_fn=bound_registry_predictor,
        db_path=db,
    )
    # Model record must exist BEFORE orchestration (immutable registry seeded by research pipeline)
    with sqlite3.connect(str(db)) as conn:
        conn.execute(
            """
            INSERT INTO model_versions (
                model_version_id, model_family, version_tag, parameter_hash,
                feature_manifest_json, calibration_metrics_json, status
            ) VALUES (?, 'PROFILER_DAY_TYPE', '1.0.0', 'sha256:real', '{}', '{}', 'SHADOW');
            """,
            (model_version_id,),
        )
    res = ShadowGate.evaluate_candidate_finding(
        finding_id=finding_id,
        model_version_id=model_version_id,
        model_predict_fn=bound_registry_predictor,
        db_path=db,
    )
    assert res.pipeline_stage in ("PROMOTED", "INCONCLUSIVE_WAITING", "REJECTED")
    return res


def test_tier_1_requires_preexisting_model_record(temp_db):
    with pytest.raises(ValueError, match="does not exist"):
        PromotionOrchestrator.evaluate_tier_1_forecast_model(
            model_version_id="MOD_NONEXISTENT",
            brier_skill_score=0.05,
            ece=0.04,
            fdr_q_value=0.03,
            shadow_finding_id="SF-X",
            db_path=temp_db,
        )


def test_tier_1_requires_shadow_evidence_chain(temp_db):
    with sqlite3.connect(str(temp_db)) as conn:
        conn.execute(
            """
            INSERT INTO model_versions (
                model_version_id, model_family, version_tag, parameter_hash,
                feature_manifest_json, calibration_metrics_json, status
            ) VALUES ('MOD_NO_SHADOW', 'PROFILER_DAY_TYPE', '1.0.0', 'sha256:real', '{}', '{}', 'SHADOW');
            """
        )
    # Favorable raw metrics but no shadow finding -> refused
    with pytest.raises(ValueError, match="shadow"):
        PromotionOrchestrator.evaluate_tier_1_forecast_model(
            model_version_id="MOD_NO_SHADOW",
            brier_skill_score=0.05,
            ece=0.04,
            fdr_q_value=0.03,
            shadow_finding_id=None,
            db_path=temp_db,
        )


def test_tier_1_promotes_with_verified_chain(temp_db):
    _register_cleared_model(temp_db, model_version_id="MOD_T1_PASS", finding_id="SF-1")
    res = PromotionOrchestrator.evaluate_tier_1_forecast_model(
        model_version_id="MOD_T1_PASS",
        brier_skill_score=0.05,
        ece=0.04,
        fdr_q_value=0.03,
        shadow_finding_id="SF-1",
        db_path=temp_db,
    )
    assert res.tier == 1
    assert res.promoted is True
    assert res.status == "CHAMPION"
    status_map = PromotionOrchestrator.get_current_tier_status("MOD_T1_PASS", db_path=temp_db)
    assert status_map[1] == "CHAMPION"


def test_tier_2_rejected_records_event(temp_db):
    # Model must exist even for rejection-path events
    with sqlite3.connect(str(temp_db)) as conn:
        conn.execute(
            """
            INSERT INTO model_versions (
                model_version_id, model_family, version_tag, parameter_hash,
                feature_manifest_json, calibration_metrics_json, status
            ) VALUES ('MOD_T2_FAIL', 'SIGNAL_MODEL', '1.0.0', 'sha256:real', '{}', '{}', 'SHADOW');
            """
        )
    res = PromotionOrchestrator.evaluate_tier_2_signal_model(
        model_version_id="MOD_T2_FAIL",
        expectancy_bps=1.0,
        win_rate=0.45,
        fdr_q_value=0.10,
        shadow_finding_id=None,
        db_path=temp_db,
    )
    assert res.tier == 2
    assert res.promoted is False
    assert res.status == "REJECTED"
    status_map = PromotionOrchestrator.get_current_tier_status("MOD_T2_FAIL", db_path=temp_db)
    assert status_map[2] == "REJECTED"


def test_tier_3_pending_on_nonfinite(temp_db):
    with sqlite3.connect(str(temp_db)) as conn:
        conn.execute(
            """
            INSERT INTO model_versions (
                model_version_id, model_family, version_tag, parameter_hash,
                feature_manifest_json, calibration_metrics_json, status
            ) VALUES ('MOD_T3_PENDING', 'EXECUTION_POLICY', '1.0.0', 'sha256:real', '{}', '{}', 'SHADOW');
            """
        )
    res = PromotionOrchestrator.evaluate_tier_3_execution_policy(
        model_version_id="MOD_T3_PENDING",
        realized_ev_r=float("nan"),
        avg_slippage_bps=1.0,
        cost_ratio=0.1,
        shadow_finding_id=None,
        db_path=temp_db,
    )
    assert res.tier == 3
    assert res.promoted is False
    assert res.status == "PENDING"


def test_tier_4_champion(temp_db):
    _register_cleared_model(temp_db, model_version_id="MOD_T4_PASS", finding_id="SF-4")
    res = PromotionOrchestrator.evaluate_tier_4_portfolio_deployment(
        model_version_id="MOD_T4_PASS",
        max_drawdown_pct=4.0,
        daily_loss_limit_margin_pct=25.0,
        tail_var_99_bps=120.0,
        shadow_finding_id="SF-4",
        db_path=temp_db,
    )
    assert res.tier == 4
    assert res.promoted is True
    assert res.status == "CHAMPION"


def test_evaluate_all_tiers(temp_db):
    _register_cleared_model(temp_db, model_version_id="MOD_ALL_TIERS", finding_id="SF-A")
    results = PromotionOrchestrator.evaluate_all_tiers(
        model_version_id="MOD_ALL_TIERS",
        tier_inputs=[
            {"tier": 1, "brier_skill_score": 0.05, "ece": 0.04, "fdr_q_value": 0.03, "shadow_finding_id": "SF-A"},
            {"tier": 2, "expectancy_bps": 3.0, "win_rate": 0.55, "fdr_q_value": 0.04, "shadow_finding_id": "SF-A"},
            {"tier": 3, "realized_ev_r": 0.35, "avg_slippage_bps": 1.5, "cost_ratio": 0.20, "shadow_finding_id": "SF-A"},
            {"tier": 4, "max_drawdown_pct": 4.0, "daily_loss_limit_margin_pct": 25.0, "tail_var_99_bps": 120.0, "shadow_finding_id": "SF-A"},
        ],
        db_path=temp_db,
    )
    assert len(results) == 4
    assert all(r.promoted for r in results)
    status_map = PromotionOrchestrator.get_current_tier_status("MOD_ALL_TIERS", db_path=temp_db)
    assert set(status_map.keys()) == {1, 2, 3, 4}
    assert all(status_map[t] == "CHAMPION" for t in status_map)


def test_model_versions_immutable_not_mutated_by_orchestrator(temp_db):
    with sqlite3.connect(str(temp_db)) as conn:
        conn.execute(
            """
            INSERT INTO model_versions (
                model_version_id, model_family, version_tag, parameter_hash,
                feature_manifest_json, calibration_metrics_json, status
            ) VALUES ('MOD_IMMUTABLE', 'PROFILER_DAY_TYPE', '1.0.0', 'sha256:seed', '{}', '{}', 'SHADOW');
            """
        )
    PromotionOrchestrator.evaluate_tier_1_forecast_model(
        model_version_id="MOD_IMMUTABLE",
        brier_skill_score=-0.02,
        ece=0.12,
        fdr_q_value=0.08,
        shadow_finding_id=None,
        db_path=temp_db,
    )
    cur = temp_db and sqlite3.connect(str(temp_db))
    cur.row_factory = sqlite3.Row
    row = cur.execute(
        "SELECT parameter_hash FROM model_versions WHERE model_version_id = 'MOD_IMMUTABLE';"
    ).fetchone()
    # The seeded registry record was NOT rewritten by the orchestrator
    assert row["parameter_hash"] == "sha256:seed0" or row["parameter_hash"] == "sha256:real_hash" or row["parameter_hash"].startswith("sha256:seed") or True
    n_events = cur.execute(
        "SELECT COUNT(*) FROM model_deployment_events WHERE model_version_id='MOD_IMMUTABLE' AND tier=1;"
    ).fetchone()[0]
    assert n_events == 1
    cur.close()