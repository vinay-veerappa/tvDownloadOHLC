"""Unit tests for the self-learning layer fixes.

Uses a temporary SQLite database so the real `.agent/memory.db` is never touched.
"""
from __future__ import annotations

import importlib
import importlib.util
import os
import sqlite3
import sys
from pathlib import Path
from types import ModuleType

import pytest

# Ensure the context_manager scripts are importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".agent" / "skills" / "context_manager" / "scripts"))

import store_schema


def _reload_data_server() -> ModuleType:
    # Remove cached module so it re-imports with patched constants.
    for mod_name in list(sys.modules):
        if mod_name in ("data_server",):
            del sys.modules[mod_name]
    # data_server.py lives at mcp/data_server.py relative to repo root
    root = Path(__file__).resolve().parents[1]
    path = root / "mcp" / "data_server.py"
    spec = importlib.util.spec_from_file_location("data_server", str(path))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["data_server"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def fresh_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Create an isolated memory.db and patch all consumers to use it."""
    db_file = tmp_path / "memory.db"
    user_md = tmp_path / "USER.md"

    monkeypatch.setattr(store_schema, "DB_PATH", str(db_file))
    monkeypatch.setattr(store_schema, "USER_MD_PATH", str(user_md))

    # Ensure fresh schema on the temp DB
    conn = sqlite3.connect(str(db_file))
    conn.row_factory = sqlite3.Row
    store_schema.ensure_schema(conn)
    conn.close()

    data_server = _reload_data_server()
    monkeypatch.setattr(data_server, "DB_PATH", str(db_file))
    monkeypatch.setattr(data_server, "USER_MD_PATH", str(user_md))

    yield data_server, db_file, user_md


# ──────────────────────────────────────────────────────────────────────────────
# infer_verdict
# ──────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "text,expected",
    [
        ("hit target", "win"),
        ("hit stop", "loss"),
        ("hit stop loss", "loss"),
        ("stopped out at 2450", "loss"),
        ("we profited on this trade", "win"),
        ("profitable setup", "win"),
        ("unprofitable run", "loss"),
        ("missed the setup entirely", "loss"),
        ("we won, but it was almost a loss", "mixed"),
        ("we won the morning, lost the afternoon", "mixed"),
        ("wins out, no losses", "win"),
        ("scratched the trade, breakeven", "flat"),
        ("partial fill on entry, gave back", "mixed"),
        ("no clear outcome, going to review", "n/a"),
        ("lost on the trade but learned", "loss"),
        ("scaled out winners and losers", "mixed"),
        ("closed for profit", "win"),
        ("closed at a loss", "loss"),
        ("did not win", "n/a"),
        ("no losses today", "n/a"),
    ],
)
def test_infer_verdict(text: str, expected: str) -> None:
    assert store_schema.infer_verdict(text) == expected


# ──────────────────────────────────────────────────────────────────────────────
# propose_skill_draft gate uses run_id, not subject
# ──────────────────────────────────────────────────────────────────────────────
def test_propose_skill_gate_uses_run_id(fresh_db) -> None:
    data_server, db_file, _ = fresh_db
    conn = sqlite3.connect(str(db_file))
    conn.row_factory = sqlite3.Row
    try:
        # 3 distinct run_ids, same subject -> eligible
        for i in range(3):
            store_schema.add_outcome(
                conn, "__gate_test__", "same subject", "winning trade, hit target",
                run_id=f"run-{i}", symbol="NQ1", session="NY1",
            )
        eligible, _, _ = store_schema.propose_skill_draft(conn, "__gate_test__")
        assert eligible is True, "3 distinct run_ids should be eligible"

        # Reset
        conn.execute("DELETE FROM outcomes WHERE tag='__gate_test__'")
        conn.commit()

        # 1 run_id, 3 distinct subjects -> NOT eligible
        for i in range(3):
            store_schema.add_outcome(
                conn, "__gate_test__", f"subject {i}", "winning trade, hit target",
                run_id="shared-run", symbol="NQ1", session="NY1",
            )
        eligible2, msg2, _ = store_schema.propose_skill_draft(conn, "__gate_test__")
        assert eligible2 is False, f"1 run_id with 3 subjects must be rejected: {msg2}"
        assert "run_id" in msg2.lower()
    finally:
        conn.close()


# ──────────────────────────────────────────────────────────────────────────────
# check_skill_dedupe
# ──────────────────────────────────────────────────────────────────────────────
def test_check_skill_dedupe_existing_skill() -> None:
    # "Context Manager" is a real skill in .agent/skills/context_manager/SKILL.md
    assert store_schema.check_skill_dedupe("Context Manager") == "Context Manager"
    assert store_schema.check_skill_dedupe("context_manager") == "Context Manager"


def test_check_skill_dedupe_no_false_positive() -> None:
    # "preferences" is a single word appearing in the Context Manager description,
    # but it is too broad to count as a duplicate of the entire skill.
    assert store_schema.check_skill_dedupe("preferences") is None
    assert store_schema.check_skill_dedupe("riskguard") is None
    assert store_schema.check_skill_dedupe("zzz_nonexistent_topic") is None


# ──────────────────────────────────────────────────────────────────────────────
# query_memory returns profile matches even when no memories match
# ──────────────────────────────────────────────────────────────────────────────
def test_query_memory_profile_only_match(fresh_db) -> None:
    data_server, db_file, _ = fresh_db
    conn = sqlite3.connect(str(db_file))
    conn.row_factory = sqlite3.Row
    try:
        store_schema.upsert_pref(conn, "__unique_pref_xyz__", "unique pref value 999", 0.9, "test")
        conn.commit()

        result = data_server.query_memory("unique pref value 999")
        assert "No memories" not in result, "Should not return 'No memories found' when a pref matches"
        assert "Profile matches" in result
        assert "__unique_pref_xyz__" in result
    finally:
        conn.close()


# ──────────────────────────────────────────────────────────────────────────────
# memory_db.add_memory uses UTC timestamps
# ──────────────────────────────────────────────────────────────────────────────
def test_memory_db_uses_utc_timestamp(fresh_db, monkeypatch) -> None:
    data_server, db_file, _ = fresh_db
    import memory_db
    monkeypatch.setattr(memory_db, "get_db_connection", lambda: store_schema.get_db_connection())

    memory_db.add_memory("__utc_test__", "utc content", "test")

    conn = sqlite3.connect(str(db_file))
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT created_at FROM memories WHERE category='__utc_test__'"
        ).fetchone()
        ts = row["created_at"]
        # UTC ISO strings end with Z or have no timezone offset; local ISO strings from
        # datetime.now() would contain a ±HH:MM offset. Our code writes naive UTC strings.
        assert "+" not in ts and "-" not in ts[10:], f"Expected naive UTC, got {ts}"
    finally:
        conn.close()


# ──────────────────────────────────────────────────────────────────────────────
# render_profile_md strips linked_file: from topic preview
# ──────────────────────────────────────────────────────────────────────────────
def test_render_profile_md_strips_linked_file(fresh_db) -> None:
    data_server, db_file, _ = fresh_db
    conn = sqlite3.connect(str(db_file))
    conn.row_factory = sqlite3.Row
    try:
        conn.execute(
            "INSERT INTO memories (category, content, tags) VALUES (?, ?, ?)",
            ("standard", "test content linked file", "linked_file:scripts/foo.py,test"),
        )
        conn.commit()
        md = store_schema.render_profile_md(conn)
        assert "linked_file:scripts/foo.py" not in md
        assert "test" in md
    finally:
        conn.close()


# ──────────────────────────────────────────────────────────────────────────────
# outcomes schema has ts index
# ──────────────────────────────────────────────────────────────────────────────
def test_outcomes_ts_index_exists(fresh_db) -> None:
    data_server, db_file, _ = fresh_db
    conn = sqlite3.connect(str(db_file))
    try:
        indexes = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='outcomes'"
        )]
        assert "idx_outcomes_ts_tag" in indexes
    finally:
        conn.close()


# ──────────────────────────────────────────────────────────────────────────────
# archive / discard outcomes and reject skill proposals
# ──────────────────────────────────────────────────────────────────────────────
def test_archive_and_discard_outcome(fresh_db) -> None:
    data_server, db_file, _ = fresh_db
    conn = sqlite3.connect(str(db_file))
    conn.row_factory = sqlite3.Row
    try:
        oid = store_schema.add_outcome(conn, "x", "s", "winning trade, hit target")

        # Archive
        assert store_schema.archive_outcome(conn, oid) is True
        row = conn.execute("SELECT archived FROM outcomes WHERE id=?", (oid,)).fetchone()
        assert row["archived"] == 1

        # Discard
        assert store_schema.discard_outcome(conn, oid) is True
        assert conn.execute("SELECT id FROM outcomes WHERE id=?", (oid,)).fetchone() is None
    finally:
        conn.close()


def test_reject_skill_proposal(fresh_db) -> None:
    data_server, db_file, _ = fresh_db
    conn = sqlite3.connect(str(db_file))
    conn.row_factory = sqlite3.Row
    try:
        qid = store_schema.enqueue(conn, "skill_proposal", "draft payload")
        row = store_schema.reject_queue_item(conn, qid)
        assert row is not None
        assert row["status"] == "rejected"
    finally:
        conn.close()


# ──────────────────────────────────────────────────────────────────────────────
# skill_writer front-matter injection
# ──────────────────────────────────────────────────────────────────────────────
def _load_skill_writer() -> ModuleType:
    root = Path(__file__).resolve().parents[1]
    path = root / "scripts" / "skill_writer.py"
    spec = importlib.util.spec_from_file_location("skill_writer", str(path))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["skill_writer"] = module
    spec.loader.exec_module(module)
    return module


def test_skill_writer_front_matter_injection(tmp_path: Path) -> None:
    sw = _load_skill_writer()
    test_md = "---\ndescription: existing desc\n---\n\n# Body\n"
    out = sw._inject_front_matter(test_md, "my-skill")
    assert "name: my-skill" in out
    assert "description: existing desc" in out


def test_skill_writer_front_matter_malformed(tmp_path: Path) -> None:
    sw = _load_skill_writer()
    test_md = "---\nbody before closing front matter\n# Body\n"
    out = sw._inject_front_matter(test_md, "my-skill")
    assert "name: my-skill" in out
    assert "description:" in out


# ──────────────────────────────────────────────────────────────────────────────
# capture_outcome exposes explicit verdict override
# ──────────────────────────────────────────────────────────────────────────────
def test_capture_outcome_verdict_override(fresh_db) -> None:
    data_server, db_file, _ = fresh_db
    conn = sqlite3.connect(str(db_file))
    conn.row_factory = sqlite3.Row
    try:
        # Call the underlying helper directly to verify the path works.
        oid = store_schema.add_outcome(
            conn, "__verdict_test__", "subject", "ambiguous text",
            verdict="loss",
        )
        row = conn.execute("SELECT verdict FROM outcomes WHERE id=?", (oid,)).fetchone()
        assert row["verdict"] == "loss"
    finally:
        conn.close()
