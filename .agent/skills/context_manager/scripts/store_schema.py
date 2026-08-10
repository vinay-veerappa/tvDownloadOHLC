"""
store_schema.py — single schema owner for .agent/memory.db.

Both memory_db.py (context_manager CLI) and data_server.py (nq-data-bridge MCP)
import this module so there is one DDL definition, not two divergent copies (B1).

Tables: memories (existing), memories_fts (FTS5, P0), user_prefs (P1),
outcomes (P2), process_queue (P3).

All helpers are stdlib + sqlite3 only — no heavy imports, preserves the
lazy-import startup weight of data_server.py.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

# Script location: .agent/skills/context_manager/scripts/store_schema.py
# Database location: .agent/memory.db
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
DB_PATH = os.path.join(BASE_DIR, "memory.db")

# ---------------------------------------------------------------------------
# DDL
# ---------------------------------------------------------------------------

MEMORIES_DDL = """
CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    content TEXT NOT NULL,
    tags TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""

MEMORIES_INDEX_DDL = "CREATE INDEX IF NOT EXISTS idx_category ON memories(category)"

FTS_DDL = """
CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(content, tags)
"""

FTS_TRIGGER_INSERT = """
CREATE TRIGGER IF NOT EXISTS memories_fts_ai AFTER INSERT ON memories BEGIN
  INSERT INTO memories_fts(rowid, content, tags) VALUES (new.id, new.content, new.tags);
END;
"""

FTS_TRIGGER_DELETE = """
CREATE TRIGGER IF NOT EXISTS memories_fts_ad AFTER DELETE ON memories BEGIN
  DELETE FROM memories_fts WHERE rowid = old.id;
END;
"""

UPDATED_AT_TRIGGER = """
CREATE TRIGGER IF NOT EXISTS memories_fts_au AFTER UPDATE ON memories BEGIN
  DELETE FROM memories_fts WHERE rowid = old.id;
  INSERT INTO memories_fts(rowid, content, tags) VALUES (new.id, new.content, new.tags);
  UPDATE memories SET updated_at = CURRENT_TIMESTAMP WHERE id = new.id AND updated_at = old.updated_at;
END;
"""

USER_PREFS_DDL = """
CREATE TABLE IF NOT EXISTS user_prefs (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    confidence REAL NOT NULL DEFAULT 1.0,
    source TEXT DEFAULT '',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""

OUTCOMES_DDL = """
CREATE TABLE IF NOT EXISTS outcomes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    tag TEXT NOT NULL,
    subject TEXT,
    outcome TEXT,
    pnl_local REAL,
    ticker TEXT,
    entry_price REAL,
    exit_price REAL,
    run_id TEXT,
    symbol TEXT,
    session TEXT,
    verdict TEXT NOT NULL,
    metadata TEXT,
    archived INTEGER DEFAULT 0
)
"""

OUTCOMES_INDEX_DDL = """
CREATE INDEX IF NOT EXISTS idx_outcomes_tag ON outcomes(tag)
"""

PROCESS_QUEUE_DDL = """
CREATE TABLE IF NOT EXISTS process_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,
    payload TEXT,
    status TEXT DEFAULT 'proposed',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    approved_at TIMESTAMP
)
"""


def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Create all tables, FTS5 index, and triggers. Idempotent."""
    cur = conn.cursor()
    cur.execute(MEMORIES_DDL)
    cur.execute(MEMORIES_INDEX_DDL)
    cur.execute(USER_PREFS_DDL)
    cur.execute(OUTCOMES_DDL)
    cur.execute(OUTCOMES_INDEX_DDL)
    cur.execute(PROCESS_QUEUE_DDL)

    # FTS5 — guard with try/except so the store works even on sqlite without fts5
    try:
        cur.execute(FTS_DDL)
        cur.execute(FTS_TRIGGER_INSERT)
        cur.execute(FTS_TRIGGER_DELETE)
        cur.execute(UPDATED_AT_TRIGGER)
        # backfill existing rows if FTS is empty but memories isn't
        n = cur.execute("SELECT count(*) FROM memories").fetchone()[0]
        nf = cur.execute("SELECT count(*) FROM memories_fts").fetchone()[0]
        if n > 0 and nf == 0:
            cur.execute(
                "INSERT INTO memories_fts(rowid, content, tags) SELECT id, content, tags FROM memories"
            )
    except sqlite3.OperationalError:
        pass  # FTS5 not available — LIKE fallback covers this

    conn.commit()


# ---------------------------------------------------------------------------
# FTS5 search helpers
# ---------------------------------------------------------------------------

def _build_fts_match(query: str) -> str:
    """Tokenize, strip quotes, wrap each token as a phrase, join with AND."""
    tokens = []
    for t in query.split():
        t = t.strip().strip('"')
        if t:
            tokens.append(f'"{t}"')
    return " AND ".join(tokens)


def fts_search(
    conn: sqlite3.Connection,
    query: str,
    category: Optional[str] = None,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """FTS5-first search with LIKE fallback. Returns list of dicts."""
    match = _build_fts_match(query)
    if match:
        try:
            sql = (
                "SELECT m.id, m.category, m.content, m.tags, m.created_at, m.updated_at "
                "FROM memories m, memories_fts "
                "WHERE m.id = memories_fts.rowid AND memories_fts MATCH ?"
            )
            params: list = [match]
            if category:
                sql += " AND m.category = ?"
                params.append(category)
            sql += " ORDER BY bm25(memories_fts) LIMIT ?"
            params.append(limit)
            rows = conn.execute(sql, params).fetchall()
            if rows:
                return [dict(r) for r in rows]
        except sqlite3.OperationalError:
            pass  # fall through to LIKE

    # LIKE fallback
    sql = "SELECT * FROM memories WHERE 1=1"
    params = []
    if category:
        sql += " AND category = ?"
        params.append(category)
    if match:
        sql += " AND (content LIKE ? OR tags LIKE ?)"
        like = f"%{query}%"
        params.extend([like, like])
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# user_prefs helpers (P1)
# ---------------------------------------------------------------------------

def upsert_pref(
    conn: sqlite3.Connection,
    key: str,
    value: str,
    confidence: float = 1.0,
    source: str = "",
) -> None:
    conn.execute(
        """INSERT INTO user_prefs (key, value, confidence, source, updated_at)
           VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
           ON CONFLICT(key) DO UPDATE SET
             value = excluded.value,
             confidence = excluded.confidence,
             source = excluded.source,
             updated_at = CURRENT_TIMESTAMP""",
        (key, value, confidence, source),
    )
    conn.commit()


def get_prefs(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    rows = conn.execute(
        "SELECT key, value, confidence, source, updated_at FROM user_prefs ORDER BY confidence DESC, key"
    ).fetchall()
    return [dict(r) for r in rows]


def render_profile_md(conn: sqlite3.Connection) -> str:
    prefs = get_prefs(conn)
    mem_rows = conn.execute(
        "SELECT category, content, tags, created_at FROM memories "
        "WHERE category IN ('user_profile', 'standard') "
        "ORDER BY created_at DESC LIMIT 25"
    ).fetchall()

    lines = ["# USER.md — Compiled Profile", ""]
    lines.append("> Auto-rendered from `user_prefs` + select `memories`. "
                  "Absent key = no info, never the opposite.")
    lines.append("")

    if prefs:
        lines.append("## Preferences")
        for p in prefs:
            conf = f" (conf={p['confidence']:.1f})" if p["confidence"] < 1.0 else ""
            lines.append(f"- **{p['key']}**: {p['value']}{conf}")
        lines.append("")

    if mem_rows:
        lines.append("## Recent user_profile / standard memories")
        for m in mem_rows:
            topic = (m["tags"] or "").split(",")[0].strip() if m["tags"] else ""
            content_preview = m["content"][:120].replace("\n", " ")
            lines.append(f"- [{m['category']}] {topic}: {content_preview}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# outcomes helpers (P2)
# ---------------------------------------------------------------------------

_VERDICT_MAP = {
    "win": {"win", "profit", "hit", "target", "success", "winner"},
    "loss": {"loss", "miss", "stop", "fail", "drawdown", "stopped", "stoploss"},
    "flat": {"flat", "scratch", "scratched", "breakeven", "be-neutral"},
    "mixed": {"mixed", "partial", "split"},
}


def infer_verdict(outcome_text: str) -> str:
    text = (outcome_text or "").lower()
    for verdict, keywords in _VERDICT_MAP.items():
        if any(re.search(r'\b' + re.escape(kw) + r'\b', text) for kw in keywords):
            return verdict
    return "n/a"


def add_outcome(
    conn: sqlite3.Connection,
    tag: str,
    subject: str,
    outcome: str,
    pnl_local: float = 0.0,
    ticker: Optional[str] = None,
    entry_price: Optional[float] = None,
    exit_price: Optional[float] = None,
    run_id: Optional[str] = None,
    symbol: Optional[str] = None,
    session: Optional[str] = None,
    verdict: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> int:
    v = verdict or infer_verdict(outcome)
    meta_str = json.dumps(metadata) if metadata else None
    cur = conn.execute(
        """INSERT INTO outcomes
           (tag, subject, outcome, pnl_local, ticker, entry_price, exit_price,
            run_id, symbol, session, verdict, metadata)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (tag, subject, outcome, pnl_local, ticker, entry_price, exit_price,
         run_id, symbol, session, v, meta_str),
    )
    conn.commit()
    return cur.lastrowid


def aggregate_outcomes(
    conn: sqlite3.Connection,
    tag: Optional[str] = None,
    period_days: int = 7,
) -> List[Dict[str, Any]]:
    """Vectorized SQL GROUP BY — no Python loops over rows."""
    since = (datetime.utcnow() - timedelta(days=period_days)).strftime('%Y-%m-%d %H:%M:%S')
    params: list = [since]
    tag_filter = ""
    if tag:
        tag_filter = " AND tag = ?"
        params.append(tag)
    rows = conn.execute(
        f"""SELECT tag,
               SUM(CASE WHEN verdict = 'win' THEN 1 ELSE 0 END) AS n_wins,
               SUM(CASE WHEN verdict = 'loss' THEN 1 ELSE 0 END) AS n_losses,
               SUM(CASE WHEN verdict = 'flat' THEN 1 ELSE 0 END) AS n_flats,
               SUM(CASE WHEN verdict = 'mixed' THEN 1 ELSE 0 END) AS n_mixed,
               SUM(CASE WHEN verdict = 'n/a' THEN 1 ELSE 0 END) AS n_na,
               COUNT(*) AS total,
               CASE WHEN SUM(CASE WHEN verdict IN ('win','loss') THEN 1 ELSE 0 END) > 0
                    THEN ROUND(100.0 * SUM(CASE WHEN verdict = 'win' THEN 1 ELSE 0 END)
                               / SUM(CASE WHEN verdict IN ('win','loss') THEN 1 ELSE 0 END), 1)
                    ELSE NULL END AS win_rate_pct
            FROM outcomes
            WHERE archived = 0 AND ts >= ?{tag_filter}
            GROUP BY tag
            ORDER BY total DESC""",
        params,
    ).fetchall()
    return [dict(r) for r in rows]


def get_outcome_rows(
    conn: sqlite3.Connection,
    tag: Optional[str] = None,
    period_days: int = 7,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    since = (datetime.utcnow() - timedelta(days=period_days)).strftime('%Y-%m-%d %H:%M:%S')
    params: list = [since]
    tag_filter = ""
    if tag:
        tag_filter = " AND tag = ?"
        params.append(tag)
    params.append(limit)
    rows = conn.execute(
        f"""SELECT id, ts, tag, subject, outcome, pnl_local, ticker,
                  entry_price, exit_price, run_id, symbol, session, verdict
            FROM outcomes
            WHERE archived = 0 AND ts >= ?{tag_filter}
            ORDER BY ts DESC LIMIT ?""",
        params,
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# process_queue helpers (P3)
# ---------------------------------------------------------------------------

def enqueue(conn: sqlite3.Connection, item_type: str, payload: str) -> int:
    cur = conn.execute(
        "INSERT INTO process_queue (type, payload, status) VALUES (?, ?, 'proposed')",
        (item_type, payload),
    )
    conn.commit()
    return cur.lastrowid


def list_queue(conn: sqlite3.Connection, status: Optional[str] = None) -> List[Dict[str, Any]]:
    sql = "SELECT id, type, payload, status, created_at, approved_at FROM process_queue"
    params: list = []
    if status:
        sql += " WHERE status = ?"
        params.append(status)
    sql += " ORDER BY created_at DESC"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def approve_queue_item(conn: sqlite3.Connection, item_id: int) -> Optional[Dict[str, Any]]:
    conn.execute(
        "UPDATE process_queue SET status = 'approved', approved_at = CURRENT_TIMESTAMP WHERE id = ?",
        (item_id,),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM process_queue WHERE id = ?", (item_id,)).fetchone()
    return dict(row) if row else None


def prune_queue(conn: sqlite3.Connection, older_than_days: int = 30) -> int:
    since = (datetime.utcnow() - timedelta(days=older_than_days)).strftime('%Y-%m-%d %H:%M:%S')
    cur = conn.execute(
        "DELETE FROM process_queue WHERE status = 'proposed' AND created_at < ?",
        (since,),
    )
    conn.commit()
    return cur.rowcount


# ---------------------------------------------------------------------------
# propose_skill helpers (P3)
# ---------------------------------------------------------------------------

SKILLS_DIR = os.path.join(BASE_DIR, "skills")
SKILL_NAMES_FILE = os.path.join(SKILLS_DIR, "_skill_names.txt")


def get_skill_names() -> List[str]:
    if not os.path.exists(SKILL_NAMES_FILE):
        return []
    with open(SKILL_NAMES_FILE, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def get_skill_descriptions() -> List[Tuple[str, str]]:
    """Scan .agent/skills/*/SKILL.md for front-matter name + description."""
    results = []
    if not os.path.isdir(SKILLS_DIR):
        return results
    for d in os.listdir(SKILLS_DIR):
        skill_md = os.path.join(SKILLS_DIR, d, "SKILL.md")
        if not os.path.isfile(skill_md):
            continue
        try:
            with open(skill_md, "r", encoding="utf-8") as f:
                content = f.read()
            name = d
            desc = ""
            # simple front-matter parse
            if content.startswith("---"):
                end = content.find("---", 3)
                if end > 0:
                    fm = content[3:end]
                    for line in fm.split("\n"):
                        if line.strip().startswith("name:"):
                            name = line.split(":", 1)[1].strip()
                        if line.strip().startswith("description:"):
                            desc = line.split(":", 1)[1].strip()
            results.append((name, desc))
        except Exception:
            continue
    return results


def check_skill_dedupe(tag: str) -> Optional[str]:
    """Return the name of an existing skill whose description covers the tag, or None."""
    tag_lower = tag.lower()
    tag_tokens = {t for t in re.split(r"[\s_\-]+", tag_lower) if t and len(t) > 2}
    for name, desc in get_skill_descriptions():
        desc_lower = (desc or "").lower()
        if tag_lower in desc_lower:
            return name
        # token overlap: if all tag tokens appear in the description
        if tag_tokens and tag_tokens.issubset(set(re.split(r"[\s,.\-]+", desc_lower))):
            return name
    return None


def propose_skill_draft(conn: sqlite3.Connection, tag: str) -> Tuple[bool, str, Optional[int]]:
    """Returns (eligible, message, queue_id). Never writes a skill file."""
    # threshold: >=3 distinct win subjects, zero losses, last 30 days
    since = (datetime.utcnow() - timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
    wins = conn.execute(
        "SELECT DISTINCT subject FROM outcomes WHERE tag = ? AND verdict = 'win' AND ts >= ? AND archived = 0",
        (tag, since),
    ).fetchall()
    losses = conn.execute(
        "SELECT count(*) FROM outcomes WHERE tag = ? AND verdict = 'loss' AND ts >= ? AND archived = 0",
        (tag, since),
    ).fetchone()[0]
    distinct_subjects = [r["subject"] for r in wins if r["subject"]]
    if len(distinct_subjects) < 3:
        return False, f"Not enough distinct wins for tag '{tag}': {len(distinct_subjects)} found (need >=3).", None
    if losses > 0:
        return False, f"Tag '{tag}' has {losses} interleaved loss(es) in the last 30d — gate refuses.", None

    dup = check_skill_dedupe(tag)
    if dup:
        return False, f"Tag '{tag}' already covered by existing skill '{dup}'. Refusing to propose duplicate.", None

    # build draft
    draft_lines = [
        "---",
        f"name: {tag.replace(' ', '-')}",
        f"description: Procedure distilled from {len(distinct_subjects)} successful executions of tag '{tag}'.",
        f"based_on: outcome tag {tag} ({len(distinct_subjects)} matched)",
        "---",
        "",
        f"# Skill: {tag}",
        "",
        f"This procedure was distilled from {len(distinct_subjects)} distinct successful outcomes "
        f"tagged '{tag}' in the last 30 days, with zero interleaved failures.",
        "",
        "## Successful subjects",
    ]
    for s in distinct_subjects:
        draft_lines.append(f"- {s}")

    # related memories
    related = fts_search(conn, tag, limit=5)
    if related:
        draft_lines.append("")
        draft_lines.append("## Related memories")
        for m in related:
            topic = (m["tags"] or "").split(",")[0].strip() if m["tags"] else ""
            draft_lines.append(f"- [{m['category']}] {topic}")

    draft = "\n".join(draft_lines)
    qid = enqueue(conn, "skill_proposal", draft)
    return True, draft, qid