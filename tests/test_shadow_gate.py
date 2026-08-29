"""Pytest suite for ShadowGate (Milestone 3.3)."""

import sqlite3
import tempfile
from pathlib import Path

import pytest

from scripts.trading_brain.db.init_db import init_trading_brain_db
from scripts.trading_brain.research.shadow_gate import ShadowGate


@pytest.fixture
def temp_db():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        db_path = Path(tmpdir) / "test_trading_brain.sqlite"
        init_trading_brain_db(db_path=db_path, verbose=False)
        yield db_path


def test_shadow_evaluation_promotion_and_inconclusive_states(temp_db):
    """Tests statistical power check and promotion vs inconclusive states."""
    # 1. Underpowered test (N=10) -> INCONCLUSIVE_WAITING
    res_under = ShadowGate.evaluate_candidate_finding(
        finding_id="f-under",
        model_version_id="MOD_V1",
        sample_size=10,
        realized_metric=0.15,
        benchmark_metric=0.10,
        effect_size_d=0.3,
        fdr_q_value=0.04,
        db_path=temp_db
    )
    assert res_under.pipeline_stage == "INCONCLUSIVE_WAITING"
    assert res_under.statistical_power < 0.80
    
    # 2. Well-powered test (N=100) with FDR q <= 0.05 -> PROMOTED
    res_promo = ShadowGate.evaluate_candidate_finding(
        finding_id="f-promo",
        model_version_id="MOD_V2",
        sample_size=100,
        realized_metric=0.25,
        benchmark_metric=0.10,
        effect_size_d=0.5,
        fdr_q_value=0.01,
        db_path=temp_db
    )
    assert res_promo.pipeline_stage == "PROMOTED"
    assert res_promo.statistical_power >= 0.80
    
    # Verify recorded in candidate_finding_events and resolved via view
    with sqlite3.connect(str(temp_db)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM v_candidate_findings_staged WHERE finding_id = 'f-promo';").fetchone()
        assert row is not None
        assert row["pipeline_stage"] == "PROMOTED"
