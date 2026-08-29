"""Universal Typed Intake Catalog Router (Milestone 4.1).

Manages universal typed intake for the 9 evidence classes:
- DOCTRINE, QUANT_HYPOTHESIS, WARGAME_SCENARIO, INDICATOR_CODE,
  MACRO_REPORT, JOURNAL, CONVERSATION_INSIGHT, INCIDENT_RECORD,
  DISCRETIONARY_OBSERVATION.

Enforces:
1. Temporal Availability Cutoff: Decision retrieval queries strictly filter `available_at_utc <= decision_cutoff_utc`.
2. Append-Only Immutability: Information items are immutable; review state transitions are recorded in `information_item_review_events`.
"""

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from scripts.trading_brain.db.connection import get_db_connection
from scripts.utils.market_calendar import now_iso_utc, parse_iso_utc, to_iso_utc

VALID_EVIDENCE_CLASSES = {
    "DOCTRINE",
    "QUANT_HYPOTHESIS",
    "WARGAME_SCENARIO",
    "INDICATOR_CODE",
    "MACRO_REPORT",
    "JOURNAL",
    "CONVERSATION_INSIGHT",
    "INCIDENT_RECORD",
    "DISCRETIONARY_OBSERVATION"
}

VALID_TIME_ORIENTATIONS = {"EX_ANTE", "INTRADAY", "POST_HOC"}


@dataclass
class InformationItemPayload:
    evidence_class: str                        # One of 9 valid classes
    time_orientation: str                      # 'EX_ANTE', 'INTRADAY', 'POST_HOC'
    source_type: str                           # 'TRANSCRIPT', 'INDICATOR_CODE', 'MACRO_REPORT', 'JOURNAL'
    title: str
    verbatim_text: str
    available_at_utc: str                      # Temporal availability boundary
    structured_payload: Optional[Dict[str, Any]] = None
    information_id: Optional[str] = None


class CatalogRouter:
    """Service class for routing, cataloging, and retrieving typed information items."""

    @classmethod
    def create_item(
        cls,
        payload: InformationItemPayload,
        db_path: Optional[Union[str, Path]] = None
    ) -> str:
        """Persists a new typed information item into information_items."""
        ev_class = payload.evidence_class.upper()
        if ev_class not in VALID_EVIDENCE_CLASSES:
            raise ValueError(f"Invalid evidence_class '{payload.evidence_class}'. Must be one of {VALID_EVIDENCE_CLASSES}")
            
        time_ori = payload.time_orientation.upper()
        if time_ori not in VALID_TIME_ORIENTATIONS:
            raise ValueError(f"Invalid time_orientation '{payload.time_orientation}'. Must be one of {VALID_TIME_ORIENTATIONS}")
            
        info_id = payload.information_id or str(uuid.uuid4())
        avail_ts_iso = to_iso_utc(payload.available_at_utc)
        payload_json = json.dumps(payload.structured_payload) if payload.structured_payload else None
        
        with get_db_connection(db_path) as conn:
            conn.execute(
                """
                INSERT INTO information_items (
                    information_id, evidence_class, time_orientation, source_type,
                    title, verbatim_text, structured_payload_json, available_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    info_id,
                    ev_class,
                    time_ori,
                    payload.source_type,
                    payload.title,
                    payload.verbatim_text,
                    payload_json,
                    avail_ts_iso
                )
            )
        return info_id

    @classmethod
    def query_as_of(
        cls,
        decision_cutoff_utc: Union[str, datetime],
        evidence_class: Optional[str] = None,
        only_accepted: bool = True,
        limit: int = 50,
        db_path: Optional[Union[str, Path]] = None
    ) -> List[Dict[str, Any]]:
        """Queries information items strictly available as of decision_cutoff_utc."""
        cutoff_iso = to_iso_utc(decision_cutoff_utc)
        
        with get_db_connection(db_path) as conn:
            conditions = ["available_at_utc <= ?"]
            params: List[Any] = [cutoff_iso]
            
            if evidence_class:
                conditions.append("evidence_class = ?")
                params.append(evidence_class.upper())
                
            if only_accepted:
                conditions.append("active_review_state = 'ACCEPTED'")
                
            where_clause = " AND ".join(conditions)
            query = f"""
            SELECT * FROM v_information_items_active
            WHERE {where_clause}
            ORDER BY available_at_utc DESC
            LIMIT ?;
            """
            params.append(limit)
            
            cur = conn.execute(query, params)
            results = []
            for r in cur.fetchall():
                d = dict(r)
                if d.get("structured_payload_json"):
                    d["structured_payload"] = json.loads(d["structured_payload_json"])
                results.append(d)
            return results

    @classmethod
    def transition_review_state(
        cls,
        information_id: str,
        review_state: str,      # 'ACCEPTED', 'REJECTED', 'QUARANTINED'
        reviewer: str,
        review_notes: Optional[str] = None,
        db_path: Optional[Union[str, Path]] = None
    ) -> str:
        """Appends an immutable transition event to information_item_review_events."""
        event_id = str(uuid.uuid4())
        now_iso = now_iso_utc()
        
        with get_db_connection(db_path) as conn:
            conn.execute(
                """
                INSERT INTO information_item_review_events (
                    review_event_id, information_id, review_state,
                    reviewer, review_notes, event_timestamp_utc
                ) VALUES (?, ?, ?, ?, ?, ?);
                """,
                (event_id, information_id, review_state.upper(), reviewer, review_notes, now_iso)
            )
        return event_id
