"""Universal Typed Intake Catalog Router (Milestone 4.1).

Manages universal typed intake for the 9 evidence classes:
- DOCTRINE, QUANT_HYPOTHESIS, WARGAME_SCENARIO, INDICATOR_CODE,
  MACRO_REPORT, JOURNAL, CONVERSATION_INSIGHT, INCIDENT_RECORD,
  DISCRETIONARY_OBSERVATION.

Enforces:
1. Temporal Availability & Creation Cutoffs: Decision retrieval strictly filters
   `available_at_utc <= decision_cutoff_utc` AND `created_at_utc <= decision_cutoff_utc`.
2. As-Of Review State Resolution: Resolves item review state as of the historical query timestamp
   by inspecting `information_item_review_events` where `event_timestamp_utc <= decision_cutoff_utc`.
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
        db_path: Optional[Union[str, Path]] = None,
        *,
        received_at_utc: Optional[Union[str, datetime]] = None,
        override_reason: Optional[str] = None,
        override_actor: Optional[str] = None,
    ) -> str:
        """Persists a new typed information item into information_items.

        Trust boundary: `received_at_utc` is normally the actual database receipt time.
        A caller override is a PRIVILEGED migration action: it requires non-empty
        `override_reason` and `override_actor` and is refused otherwise. Normal
        application writes must never accept receipt-time overrides - a caller-supplied
        receipt is what makes historical as-of queries forgeable.
        """
        ev_class = payload.evidence_class.upper()
        if ev_class not in VALID_EVIDENCE_CLASSES:
            raise ValueError(f"Invalid evidence_class '{payload.evidence_class}'. Must be one of {VALID_EVIDENCE_CLASSES}")

        time_ori = payload.time_orientation.upper()
        if time_ori not in VALID_TIME_ORIENTATIONS:
            raise ValueError(f"Invalid time_orientation '{payload.time_orientation}'. Must be one of {VALID_TIME_ORIENTATIONS}")

        info_id = payload.information_id or str(uuid.uuid4())
        avail_ts_iso = to_iso_utc(payload.available_at_utc)
        payload_json = json.dumps(payload.structured_payload) if payload.structured_payload else None
        if received_at_utc is not None and (not override_reason or not override_actor):
            raise ValueError(
                "received_at_utc override requires override_reason and override_actor "
                "(privileged migration path). Unaudited caller-supplied receipt times forge "
                "historical as-of evidence."
            )
        if received_at_utc is not None:
            import os
            if os.environ.get("TRADING_BRAIN_ALLOW_RECEIPT_OVERRIDE") != "1":
                raise ValueError(
                    "received_at_utc override requires the migration capability "
                    "(TRADING_BRAIN_ALLOW_RECEIPT_OVERRIDE=1). Normal application APIs must "
                    "not backdate evidence; run migrations through the migration tooling."
                )
        recv_iso = to_iso_utc(received_at_utc) if received_at_utc else now_iso_utc()

        with get_db_connection(db_path) as conn:
            conn.execute(
                """
                INSERT INTO information_items (
                    information_id, evidence_class, time_orientation, source_type,
                    title, verbatim_text, structured_payload_json, available_at_utc,
                    received_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    info_id,
                    ev_class,
                    time_ori,
                    payload.source_type,
                    payload.title,
                    payload.verbatim_text,
                    payload_json,
                    avail_ts_iso,
                    recv_iso
                )
            )
        return info_id

    @classmethod
    def query_as_of(
        cls,
        decision_cutoff_utc: Union[str, datetime],
        evidence_class: Optional[str] = None,
        only_accepted: bool = True,
        min_review_state: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        db_path: Optional[Union[str, Path]] = None
    ) -> List[Dict[str, Any]]:
        """Queries information items strictly available and received as of decision_cutoff_utc,
        resolving historical review state as of the cutoff.

        Trust boundary:
        - `available_at_utc` is the semantic availability boundary (declared by the producer).
        - `received_at_utc` is the trusted database receipt time (set by create_item).
        - Both must be <= decision_cutoff_utc to prevent hindsight ingestion from appearing
          as contemporaneous evidence.

        Review state can be filtered by `min_review_state` (e.g., 'ACCEPTED' requires an
        explicit ACCEPTED event; 'CAPTURED' accepts items that have not been reviewed).
        Pagination: `offset` skips the first N rows of the filtered, ordered result set
        (review-state filtering happens in SQL BEFORE the offset/limit window, so paging
        never hides older accepted evidence behind a page of rejected rows).
        """
        cutoff_iso = to_iso_utc(decision_cutoff_utc)

        with get_db_connection(db_path) as conn:
            # Review-state filtering happens IN SQL before LIMIT: Python-side filtering
            # after pagination would let a page of newer rejected/quarantined rows hide
            # older accepted evidence entirely.
            query = """
            WITH active_state AS (
                SELECT i.information_id,
                       COALESCE((
                           SELECT r.review_state FROM information_item_review_events r
                           WHERE r.information_id = i.information_id
                             AND COALESCE(r.received_at_utc, r.event_timestamp_utc) <= ?
                           ORDER BY COALESCE(r.received_at_utc, r.event_timestamp_utc) DESC,
                                    r.created_at_utc DESC, r.rowid DESC
                           LIMIT 1
                       ), 'CAPTURED') AS active_review_state
                FROM information_items i
            )
            SELECT i.*, a.active_review_state
            FROM information_items i
            JOIN active_state a ON a.information_id = i.information_id
            WHERE i.available_at_utc <= ?
              AND i.received_at_utc <= ?
            """
            # As-of review eligibility keyed on TRUSTED receipt time (falling back to
            # created_at for pre-migration rows). Caller-declared event timestamps are
            # display metadata, never the historical-evidence key.
            params: List[Any] = [cutoff_iso, cutoff_iso, cutoff_iso]

            if evidence_class:
                query += " AND i.evidence_class = ?"
                params.append(evidence_class.upper())

            if only_accepted:
                if min_review_state:
                    # Review-state hierarchy: negative states disqualify an item outright.
                    # CAPTURED is the neutral floor; only ACCEPTED is a positive credential.
                    state = min_review_state.upper()
                    if state == "CAPTURED":
                        query += " AND a.active_review_state = 'CAPTURED'"
                    elif state == "ACCEPTED":
                        query += " AND a.active_review_state = 'ACCEPTED'"
                    else:
                        raise ValueError(f"Invalid min_review_state '{min_review_state}'. Must be CAPTURED or ACCEPTED.")

                else:
                    query += " AND a.active_review_state = 'ACCEPTED'"

            query += " ORDER BY i.available_at_utc DESC, i.received_at_utc DESC, i.information_id LIMIT ? OFFSET ?;"
            params.append(limit)
            params.append(int(offset))

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
        event_timestamp_utc: Optional[str] = None,
        db_path: Optional[Union[str, Path]] = None
    ) -> str:
        """Appends an immutable transition event to information_item_review_events.

        Temporal trust boundary:
        - `received_at_utc` is set to the trusted server clock now(); it is the ONLY key
          used for as-of historical eligibility, so a review performed today can never
          create the appearance of having been accepted before a past cutoff.
        - `event_timestamp_utc` (optional caller override) is the user-declared/effective
          time; it is preserved for display and audit but has no as-of authority.
        """
        event_id = str(uuid.uuid4())
        declared_iso = to_iso_utc(event_timestamp_utc) if event_timestamp_utc else now_iso_utc()
        trusted_recv = now_iso_utc()

        with get_db_connection(db_path) as conn:
            conn.execute(
                """
                INSERT INTO information_item_review_events (
                    review_event_id, information_id, review_state,
                    reviewer, review_notes, event_timestamp_utc, received_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                (event_id, information_id, review_state.upper(), reviewer, review_notes, declared_iso, trusted_recv)
            )
        return event_id
