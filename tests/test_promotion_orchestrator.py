"""Pytest suite for PromotionOrchestrator (Milestone 3.4)."""

import sqlite3
import tempfile
from pathlib import Path

import pytest

from scripts.trading_brain.db.init_db import init_trading_brain_db
from scripts.trading_brain.research.promotion_orchestrator import PromotionOrchestrator


@pytest.fixture
def temp_db():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        db_path = Path(tmpdir) / "test_trading_brain.sqlite"
        init_trading_brain_db(db_path=db_path, verbose=False)
        yield db_path


def test_tier_1_forecast_model_promotion(temp_db):
    """Tests promoting Tier 1 forecast model to CHAMPION in model_versions."""
    res = PromotionOrchestrator.evaluate_tier_1_forecast_model(
        model_version_id="MOD_CHAMPION_V1",
        brier_skill_score=0.12,
        ece=0.04,
        fdr_q_value=0.01,
        db_path=temp_db
    )
    assert res.promoted is True
    assert res.status == "CHAMPION"
    
    with sqlite3.connect(str(temp_db)) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute("SELECT * FROM model_versions WHERE model_version_id = 'MOD_CHAMPION_V1';")
        row = cur.fetchone()
        assert row is not None
        assert row["status"] == "CHAMPION"


def test_tier_2_signal_model_promotion():
    """Tests evaluating Tier 2 signal model criteria."""
    res = PromotionOrchestrator.evaluate_tier_2_signal_model(
        strategy_version_id="STRAT_V2_PROMO",
        expectancy_bps=4.5,
        win_rate=0.62,
        fdr_q_value=0.02
    )
    assert res.promoted is True
    assert res.status == "PROMOTED"
