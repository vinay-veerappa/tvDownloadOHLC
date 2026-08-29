"""Pytest suite for CatalogRouter (Milestone 4.1)."""

import sqlite3
import tempfile
import uuid
from pathlib import Path

import pytest

from scripts.trading_brain.db.init_db import init_trading_brain_db
from scripts.trading_brain.intake.catalog_router import CatalogRouter, InformationItemPayload


@pytest.fixture
def temp_db():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        db_path = Path(tmpdir) / "test_trading_brain.sqlite"
        init_trading_brain_db(db_path=db_path, verbose=False)
        yield db_path


def test_catalog_router_creation_and_as_of_retrieval(temp_db):
    """Tests typed information intake and temporal as-of boundary queries."""
    # 1. Insert item available at 08:00 UTC
    item_1 = InformationItemPayload(
        evidence_class="DOCTRINE",
        time_orientation="EX_ANTE",
        source_type="TRANSCRIPT",
        title="Cover The Queen Principle",
        verbatim_text="At +10 bps, lock in breakeven stop unconditionally.",
        available_at_utc="2026-08-28T08:00:00Z",
        structured_payload={"principle": "risk_management", "bracket_bps": 10.0}
    )
    id_1 = CatalogRouter.create_item(item_1, db_path=temp_db, received_at_utc="2026-08-28T07:55:00Z")
    CatalogRouter.transition_review_state(id_1, "ACCEPTED", reviewer="EXPERT_TRADER", event_timestamp_utc="2026-08-28T08:15:00Z", db_path=temp_db)

    # 2. Insert item available at 16:00 UTC (Post-hoc)
    item_2 = InformationItemPayload(
        evidence_class="JOURNAL",
        time_orientation="POST_HOC",
        source_type="JOURNAL",
        title="Post-Market Reflection",
        verbatim_text="Market formed clean R1 trend day.",
        available_at_utc="2026-08-28T16:00:00Z"
    )
    id_2 = CatalogRouter.create_item(item_2, db_path=temp_db, received_at_utc="2026-08-28T16:00:00Z")
    CatalogRouter.transition_review_state(id_2, "ACCEPTED", reviewer="TRADER", event_timestamp_utc="2026-08-28T16:15:00Z", db_path=temp_db)

    # 3. Query as of 09:30 UTC -> only item 1 must be returned
    items_early = CatalogRouter.query_as_of("2026-08-28T09:30:00Z", db_path=temp_db)
    assert len(items_early) == 1
    assert items_early[0]["information_id"] == id_1
    assert items_early[0]["title"] == "Cover The Queen Principle"

    # 4. Query as of 17:00 UTC -> both items returned
    items_late = CatalogRouter.query_as_of("2026-08-28T17:00:00Z", db_path=temp_db)
    assert len(items_late) == 2


def test_catalog_router_hindsight_item_blocked_by_received_at(temp_db):
    """A post-hoc item with an early available_at but late actual receipt must not appear as ex-ante evidence."""
    # The only way to simulate a late receipt is to back-date available_at while create_item stamps now.
    # Because create_item sets received_at_utc to now, we use the explicit DB directly.
    import sqlite3
    info_id = "hindsight-1"
    with sqlite3.connect(str(temp_db)) as conn:
        conn.execute(
            """
            INSERT INTO information_items (
                information_id, evidence_class, time_orientation, source_type,
                title, verbatim_text, structured_payload_json, available_at_utc, received_at_utc
            ) VALUES (?, 'DOCTRINE', 'EX_ANTE', 'TRANSCRIPT', 'Hindsight', 'Text', NULL, ?, ?);
            """,
            (info_id, "2026-08-28T08:00:00Z", "2026-08-28T16:00:00Z")
        )
        conn.execute(
            """
            INSERT INTO information_item_review_events (
                review_event_id, information_id, review_state, reviewer, review_notes, event_timestamp_utc
            ) VALUES (?, ?, 'ACCEPTED', 'TEST', '', '2026-08-28T16:05:00Z');
            """,
            (str(uuid.uuid4()), info_id)
        )

    items = CatalogRouter.query_as_of("2026-08-28T09:30:00Z", db_path=temp_db)
    assert all(i["information_id"] != info_id for i in items)

    # At 17:00 the item is available and received, so it appears
    items_late = CatalogRouter.query_as_of("2026-08-28T17:00:00Z", db_path=temp_db)
    assert any(i["information_id"] == info_id for i in items_late)


def test_catalog_router_min_review_state_filter(temp_db):
    """only_accepted with min_review_state lets CAPTURED items through when requested."""
    item = InformationItemPayload(
        evidence_class="INCIDENT_RECORD",
        time_orientation="INTRADAY",
        source_type="JOURNAL",
        title="Unreviewed incident",
        verbatim_text="...",
        available_at_utc="2026-08-28T10:00:00Z"
    )
    info_id = CatalogRouter.create_item(item, db_path=temp_db, received_at_utc="2026-08-28T10:00:00Z")

    # Default only_accepted excludes CAPTURED items.
    accepted_items = CatalogRouter.query_as_of("2026-08-28T11:00:00Z", db_path=temp_db)
    assert all(i["information_id"] != info_id for i in accepted_items)

    # With min_review_state='CAPTURED', the item is eligible.
    captured_items = CatalogRouter.query_as_of(
        "2026-08-28T11:00:00Z", db_path=temp_db, only_accepted=True, min_review_state="CAPTURED"
    )
    assert any(i["information_id"] == info_id for i in captured_items)





def test_catalog_router_invalid_evidence_class_rejected(temp_db):
    """Tests that invalid evidence class is rejected with ValueError."""
    with pytest.raises(ValueError):
        CatalogRouter.create_item(
            InformationItemPayload(
                evidence_class="INVALID_UNKNOWN_CLASS",
                time_orientation="EX_ANTE",
                source_type="NOTE",
                title="Test",
                verbatim_text="Test",
                available_at_utc="2026-08-28T08:00:00Z"
            ),
            db_path=temp_db
        )
