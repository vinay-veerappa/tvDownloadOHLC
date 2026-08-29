"""Read-Only Trading Second Brain Agent Memory Bridge (Milestone 1.3).

Preserves strict architectural boundaries:
- Development agent memory & skills remain in .agent/
- trading_brain.sqlite is the sole trading authority ledger.
- This bridge provides typed, read-only queries for agent contexts and prompts.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from scripts.trading_brain.db.connection import get_db_connection, resolve_db_path


class AgentMemoryBridge:
    """Read-only query bridge into Trading Second Brain for agents and LLMs."""

    def __init__(self, db_path: Optional[Union[str, Path]] = None):
        self.db_path = resolve_db_path(db_path)

    def get_recent_session_triage(self, n_sessions: int = 5, ticker: str = "NQ1") -> List[Dict[str, Any]]:
        """Retrieves recent session tape actuals and triage status."""
        with get_db_connection(self.db_path) as conn:
            cur = conn.execute(
                """
                SELECT session_date, ticker, day_type_classification, session_range_bps,
                       session_open, rth_close, quality_state
                FROM v_session_tape_actuals_current
                WHERE ticker = ?
                ORDER BY session_date DESC
                LIMIT ?;
                """,
                (ticker, n_sessions)
            )
            return [dict(r) for r in cur.fetchall()]

    def get_strategy_registry_summary(self) -> List[Dict[str, Any]]:
        """Retrieves all registered strategy versions and execution policies."""
        with get_db_connection(self.db_path) as conn:
            cur = conn.execute(
                "SELECT strategy_version_id, strategy_family, version_tag, content_hash, status, execution_policy_json FROM strategy_versions ORDER BY strategy_version_id ASC;"
            )
            results = []
            for r in cur.fetchall():
                d = dict(r)
                d["execution_policy"] = json.loads(r["execution_policy_json"]) if r["execution_policy_json"] else {}
                results.append(d)
            return results

    def get_active_unmatched_links(self) -> List[Dict[str, Any]]:
        """Retrieves currently open unmatched execution links requiring triage."""
        with get_db_connection(self.db_path) as conn:
            cur = conn.execute(
                """
                SELECT u.link_event_id, u.execution_id, u.candidate_opportunity_ids_json,
                       e.session_date, e.ticker, e.order_action, e.quantity, e.fill_price, e.event_timestamp_utc
                FROM v_unmatched_links_open u
                JOIN execution_events e ON u.execution_id = e.execution_id
                ORDER BY e.event_timestamp_utc DESC;
                """
            )
            results = []
            for r in cur.fetchall():
                d = dict(r)
                d["candidate_opportunity_ids"] = json.loads(r["candidate_opportunity_ids_json"]) if r["candidate_opportunity_ids_json"] else []
                results.append(d)
            return results

    def get_doctrine_items(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Retrieves accepted trading doctrine items from the intake catalog."""
        with get_db_connection(self.db_path) as conn:
            cur = conn.execute(
                """
                SELECT information_id, title, verbatim_text, available_at_utc, structured_payload_json
                FROM v_information_items_active
                WHERE active_review_state = 'ACCEPTED' AND evidence_class = 'DOCTRINE'
                ORDER BY available_at_utc DESC
                LIMIT ?;
                """,
                (limit,)
            )
            return [dict(r) for r in cur.fetchall()]
