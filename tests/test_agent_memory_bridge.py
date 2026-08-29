"""Pytest suite for AgentMemoryBridge (Milestone 1.3)."""

import sqlite3
import tempfile
from pathlib import Path

import pytest

from scripts.trading_brain.bridges.agent_memory_bridge import AgentMemoryBridge
from scripts.trading_brain.db.init_db import init_trading_brain_db
from scripts.trading_brain.strategies.registry_v0 import register_all_v0_strategies


@pytest.fixture
def temp_db():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        db_path = Path(tmpdir) / "test_trading_brain.sqlite"
        init_trading_brain_db(db_path=db_path, verbose=False)
        yield db_path


def test_agent_memory_bridge_queries(temp_db):
    """Tests read-only query bridge for agent contexts."""
    register_all_v0_strategies(db_path=temp_db)
    
    bridge = AgentMemoryBridge(db_path=temp_db)
    
    # 1. Strategy Registry Summary
    strats = bridge.get_strategy_registry_summary()
    assert len(strats) >= 4
    assert strats[0]["strategy_version_id"].startswith("STRAT_")
    
    # 2. Doctrine items query
    with sqlite3.connect(str(temp_db)) as conn:
        conn.execute(
            """
            INSERT INTO information_items (information_id, evidence_class, time_orientation, source_type, title, verbatim_text, available_at_utc)
            VALUES ('info-doc-1', 'DOCTRINE', 'EX_ANTE', 'TRANSCRIPT', 'P12 Vector Core', 'Doctrine rule text', '2026-08-28T08:00:00Z');
            """
        )
        conn.execute(
            """
            INSERT INTO information_item_review_events (review_event_id, information_id, review_state, reviewer)
            VALUES ('rev-doc-1', 'info-doc-1', 'ACCEPTED', 'EXPERT');
            """
        )
        
    doctrines = bridge.get_doctrine_items()
    assert len(doctrines) == 1
    assert doctrines[0]["title"] == "P12 Vector Core"
