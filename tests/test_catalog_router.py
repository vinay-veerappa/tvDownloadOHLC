"""Pytest suite for CatalogRouter (Milestone 4.1)."""

import sqlite3
import tempfile
import uuid
from pathlib import Path

import pytest

from scripts.trading_brain.db.init_db import init_trading_brain_db
from scripts.trading_brain.intake.catalog_router import CatalogRouter, InformationItemPayload

import os as _os
# Fixture capability: these tests verify MIGRATION-path receipt semantics (historical
# receipts asserted by tooling). Production callers do not have this capability flag.
_os.environ.setdefault("TRADING_BRAIN_ALLOW_RECEIPT_OVERRIDE", "1")


@pytest.fixture
def temp_db():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        db_path = Path(tmpdir) / "test_trading_brain.sqlite"
        init_trading_brain_db(db_path=db_path, verbose=False)
        yield db_path


def _migration_review_event(
    db_path,
    information_id: str,
    review_state: str,
    effective_at_utc: str,
    received_at_utc: str,
    reviewer: str = "TEST_FIXTURE",
):
    """Privileged migration fixture: writes a historical review event whose trusted
    receipt is explicitly in the simulated past. Mirrors what a real historical
    migration would record (declared effective time + verified historical receipt)."""
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            """
            INSERT INTO information_item_review_events (
                review_event_id, information_id, review_state, reviewer,
                review_notes, event_timestamp_utc, received_at_utc
            ) VALUES (?, ?, ?, ?, '', ?, ?);
            """,
            (str(uuid.uuid4()), information_id, review_state, reviewer,
             effective_at_utc, received_at_utc)
        )


def test_catalog_router_creation_and_as_of_retrieval(temp_db):
    """Tests typed information intake and temporal as-of boundary queries."""
    # 1. Insert item available at 08:00 UTC on 2026-08-28
    item_1 = InformationItemPayload(
        evidence_class="DOCTRINE",
        time_orientation="EX_ANTE",
        source_type="TRANSCRIPT",
        title="Cover The Queen Principle",
        verbatim_text="At +10 bps, lock in breakeven stop unconditionally.",
        available_at_utc="2026-08-28T08:00:00Z",
        structured_payload={"principle": "risk_management", "bracket_bps": 10.0}
    )
    id_1 = CatalogRouter.create_item(item_1, db_path=temp_db, received_at_utc="2026-08-28T07:55:00Z", override_reason="historical migration fixture", override_actor="MIGRATION_TOOL")
    # Review the item in RECENT time (trusted receipt = now). The as-of query at
    # 09:30 on 08-28 uses trusted receipt, so this review only becomes visible after it
    # actually happened - exactly the anti-backdating contract.
    CatalogRouter.transition_review_state(id_1, "ACCEPTED", reviewer="EXPERT_TRADER", db_path=temp_db)

    # 2. Insert item available at 16:00 UTC (Post-hoc)
    item_2 = InformationItemPayload(
        evidence_class="JOURNAL",
        time_orientation="POST_HOC",
        source_type="JOURNAL",
        title="Post-Market Reflection",
        verbatim_text="Market formed clean R1 trend day.",
        available_at_utc="2026-08-28T16:00:00Z"
    )
    id_2 = CatalogRouter.create_item(item_2, db_path=temp_db, received_at_utc="2026-08-28T16:00:00Z", override_reason="historical migration fixture", override_actor="MIGRATION_TOOL")
    CatalogRouter.transition_review_state(id_2, "ACCEPTED", reviewer="TRADER", db_path=temp_db)

    # 3. Query as of 09:30 UTC on 2026-08-28: item 1 EXISTS (available+received pre-cutoff)
    # but its ACCEPTED review has today's trusted receipt -> not yet visible. CAPTURED
    # items are excluded by default -> zero accepted items.
    items_early = CatalogRouter.query_as_of("2026-08-28T09:30:00Z", db_path=temp_db)
    assert len(items_early) == 0

    # 4. Historical migration path grants the review true historical custody (trusted
    # receipt recorded in the past, mirroring a verified migration).
    _migration_review_event(
        temp_db, id_1, "ACCEPTED",
        effective_at_utc="2026-08-28T08:15:00Z",
        received_at_utc="2026-08-28T08:15:00Z",
    )
    items_early_after_migration = CatalogRouter.query_as_of("2026-08-28T09:30:00Z", db_path=temp_db)
    assert len(items_early_after_migration) == 1
    assert items_early_after_migration[0]["information_id"] == id_1

    # 5. Query as of 17:00 -> only the migration-backed item is accepted; item_2's
    # review also lands with today's receipt but item_2 was available at 16:00 <
    # 17:00 cutoff and its ACCEPTED review is still future-dated relative to the
    # trusted receipt, so it stays hidden until backed by migration.
    _migration_review_event(
        temp_db, id_2, "ACCEPTED",
        effective_at_utc="2026-08-28T16:15:00Z",
        received_at_utc="2026-08-28T16:15:00Z",
    )
    items_late = CatalogRouter.query_as_of("2026-08-28T17:00:00Z", db_path=temp_db)
    assert len(items_late) == 2


def test_catalog_router_hindsight_item_blocked_by_received_at(temp_db):
    """A post-hoc item with an early available_at but late actual receipt must not appear as ex-ante evidence."""
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
        # Review event with backdated *declared* time but trusted receipt also backdated
        # via the explicit migration path (mirrors verified historical migration).
        conn.execute(
            """
            INSERT INTO information_item_review_events (
                review_event_id, information_id, review_state, reviewer, review_notes,
                event_timestamp_utc, received_at_utc
            ) VALUES (?, ?, 'ACCEPTED', 'TEST', '', '2026-08-28T16:05:00Z', '2026-08-28T16:05:00Z');
            """,
            (str(uuid.uuid4()), info_id)
        )

    items = CatalogRouter.query_as_of("2026-08-28T09:30:00Z", db_path=temp_db)
    assert all(i["information_id"] != info_id for i in items)

    # At 17:00 the item is available and received, so it appears
    items_late = CatalogRouter.query_as_of("2026-08-28T17:00:00Z", db_path=temp_db)
    assert any(i["information_id"] == info_id for i in items_late)


def test_catalog_router_backdated_review_cannot_create_hindsight_history(temp_db):
    """A review performed TODAY with a backdated declared time must NOT appear accepted
    before its actual (trusted) receipt."""
    item = InformationItemPayload(
        evidence_class="MACRO_REPORT",
        time_orientation="EX_ANTE",
        source_type="MACRO_REPORT",
        title="Backdated review attempt",
        verbatim_text="...",
        available_at_utc="2026-08-28T08:00:00Z"
    )
    info_id = CatalogRouter.create_item(item, db_path=temp_db, received_at_utc="2026-08-28T07:50:00Z", override_reason="historical migration fixture", override_actor="MIGRATION_TOOL")
    # Declared acceptance claims 08:05 on 08-28, but the review actually happens now.
    CatalogRouter.transition_review_state(
        information_id=info_id, review_state="ACCEPTED", reviewer="OPERATOR",
        event_timestamp_utc="2026-08-28T08:05:00Z", db_path=temp_db,
    )
    # As-of 09:00 on 08-28 the accepted state must NOT exist (trusted receipt is today).
    items = CatalogRouter.query_as_of(
        "2026-08-28T09:00:00Z", db_path=temp_db, only_accepted=True, min_review_state="ACCEPTED"
    )
    assert all(i["information_id"] != info_id for i in items)


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
    info_id = CatalogRouter.create_item(item, db_path=temp_db, received_at_utc="2026-08-28T10:00:00Z", override_reason="historical migration fixture", override_actor="MIGRATION_TOOL")

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



def test_catalog_router_receipt_override_requires_audit_metadata(temp_db):
    """F5: normal writes cannot backdate receipt times - the override is a privileged,
    audited migration action requiring reason + actor."""
    item = InformationItemPayload(
        evidence_class="DOCTRINE",
        time_orientation="EX_ANTE",
        source_type="TRANSCRIPT",
        title="Override attempt",
        verbatim_text="...",
        available_at_utc="2026-08-28T08:00:00Z"
    )
    with pytest.raises(ValueError, match="override_reason and override_actor"):
        CatalogRouter.create_item(item, db_path=temp_db, received_at_utc="2026-08-28T07:00:00Z")


def test_catalog_router_as_of_pagination_offset(temp_db):
    """F21: offset pagination over the SAME filtered, ordered result set."""
    for i in range(5):
        item = InformationItemPayload(
            evidence_class="DOCTRINE",
            time_orientation="EX_ANTE",
            source_type="TRANSCRIPT",
            title=f"Item {i}",
            verbatim_text="...",
            available_at_utc=f"2026-08-28T0{i}:00:00Z",
            information_id=f"page-{i}",
        )
        CatalogRouter.create_item(item, db_path=temp_db, override_reason="migration", override_actor="MIGRATION_TOOL", received_at_utc=f"2026-08-28T0{i}:05:00Z")

    page_one = CatalogRouter.query_as_of("2026-08-28T23:00:00Z", db_path=temp_db, min_review_state="CAPTURED", limit=2)
    page_two = CatalogRouter.query_as_of("2026-08-28T23:00:00Z", db_path=temp_db, min_review_state="CAPTURED", limit=2, offset=2)
    ids_one = {r["information_id"] for r in page_one}
    ids_two = {r["information_id"] for r in page_two}
    assert len(ids_one) == 2 and len(ids_two) == 2
    assert ids_one.isdisjoint(ids_two)




def test_catalog_router_capability_flag_gates_override(temp_db):
    """F7: with the capability flag explicitly REMOVED, the override is refused even
    with reason+actor supplied (production default)."""
    item = InformationItemPayload(
        evidence_class="DOCTRINE",
        time_orientation="EX_ANTE",
        source_type="TRANSCRIPT",
        title="Capability gate",
        verbatim_text="...",
        available_at_utc="2026-08-28T08:00:00Z"
    )
    env_flag = _os.environ.pop("TRADING_BRAIN_ALLOW_RECEIPT_OVERRIDE", None)
    try:
        with pytest.raises(ValueError, match="migration capability"):
            CatalogRouter.create_item(
                item, db_path=temp_db,
                received_at_utc="2026-08-28T07:00:00Z",
                override_reason="attempt", override_actor="ROGUE",
            )
    finally:
        if env_flag is not None:
            _os.environ["TRADING_BRAIN_ALLOW_RECEIPT_OVERRIDE"] = env_flag
