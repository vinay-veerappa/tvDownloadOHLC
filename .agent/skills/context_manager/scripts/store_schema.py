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
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

# Script location: .agent/skills/context_manager/scripts/store_schema.py
# Database location: .agent/memory.db
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
DB_PATH = os.path.join(BASE_DIR, "memory.db")
USER_MD_PATH = os.path.join(BASE_DIR, "USER.md")

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
    base_confidence REAL NOT NULL DEFAULT 1.0,
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

OUTCOMES_TS_INDEX_DDL = """
CREATE INDEX IF NOT EXISTS idx_outcomes_ts_tag ON outcomes(ts, tag)
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
    cur.execute(OUTCOMES_TS_INDEX_DDL)
    cur.execute(PROCESS_QUEUE_DDL)

    # Additive migration: add base_confidence column to pre-existing user_prefs tables.
    # SQLite's IF NOT EXISTS doesn't cover ADD COLUMN, so we introspect and add if missing.
    try:
        cols = [r[1] for r in cur.execute("PRAGMA table_info(user_prefs)").fetchall()]
        if "base_confidence" not in cols:
            cur.execute(
                "ALTER TABLE user_prefs ADD COLUMN base_confidence REAL NOT NULL DEFAULT 1.0"
            )
            # Backfill base_confidence from confidence for existing rows.
            cur.execute(
                "UPDATE user_prefs SET base_confidence = confidence WHERE base_confidence = 1.0"
            )
    except sqlite3.OperationalError:
        pass

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
    """Insert or update a user preference row.

    `confidence` is the live (possibly decayed) value; `base_confidence` records
    the original seeded value so that periodic decay can recompute from a stable
    anchor rather than a value that has already been decayed.
    """
    conn.execute(
        """INSERT INTO user_prefs (key, value, confidence, base_confidence, source, updated_at)
           VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
           ON CONFLICT(key) DO UPDATE SET
             value = excluded.value,
             confidence = excluded.confidence,
             base_confidence = excluded.base_confidence,
             source = excluded.source,
             updated_at = CURRENT_TIMESTAMP""",
        (key, value, confidence, confidence, source),
    )
    conn.commit()


def get_prefs(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    rows = conn.execute(
        "SELECT key, value, confidence, base_confidence, source, updated_at "
        "FROM user_prefs ORDER BY confidence DESC, key"
    ).fetchall()
    return [dict(r) for r in rows]


def _display_topic(tags: Optional[str]) -> str:
    """Pick the first non-internal tag as the display topic."""
    if not tags:
        return ""
    for t in tags.split(","):
        t = t.strip()
        if t and not t.startswith("linked_file:"):
            return t
    return ""


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
            topic = _display_topic(m["tags"])
            content_preview = m["content"][:120].replace("\n", " ")
            lines.append(f"- [{m['category']}] {topic}: {content_preview}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# outcomes helpers (P2)
# ---------------------------------------------------------------------------

# Scoring table: each keyword family contributes to a verdict bucket.
# A keyword matches if its stem appears as a whole word (or word prefix) in the text.
# Past-tense and common variants are included explicitly. "hit" is intentionally absent
# as a standalone win keyword because it appears in both "hit target" (win) and
# "hit stop" (loss). Compound phrases are scored separately.
_VERDICT_KEYWORDS = {
    "win": {
        "win", "won", "wins", "winning", "winner", "winners",
        "profit", "profits", "profitable", "profitably", "profiting",
        "target", "targets", "targeted", "success", "successful", "succeeded",
        "gain", "gains", "made money", "in the money", "itm",
    },
    "loss": {
        "loss", "losses", "lost", "lose", "losing", "loser",
        "miss", "missed", "misses", "missing",
        "stop", "stopped", "stops", "stoploss", "stop-loss", "stopped out",
        "fail", "failed", "fails", "failing", "failure",
        "drawdown", "drawdowns", "dd",
        "unprofitable", "unprofitably",
    },
    "flat": {
        "flat", "scratch", "scratched", "breakeven", "break-even", "be-neutral",
        "no gain", "unchanged", "unchange",
    },
    "mixed": {
        "mixed", "partial", "partials", "split", "splits", "scaled out", "scale out",
        "some win some loss", "win and loss", "won and lost",
    },
}

# Compound phrases override the raw keyword score. Each phrase is checked first
# and gives a strong directional push.
_VERDICT_PHRASES = {
    "win": {
        "hit target", "hit the target", "target hit", "target reached",
        "took profit", "profit taken", "profit hit", "made profit",
        "won the trade", "winning trade", "closed profitable", "closed for profit",
    },
    "loss": {
        "hit stop", "hit the stop", "stop hit", "stop loss hit", "stop-loss hit",
        "stopped out", "got stopped", "took the loss", "took a loss", "loss taken",
        "missed the setup", "missed setup", "setup missed", "failed trade",
        "closed for loss", "closed at a loss", "stopped out at",
    },
    "flat": {
        "scratched the trade", "trade scratched", "breakeven trade", "flat trade",
        "closed flat", "closed even", "no profit no loss",
    },
    "mixed": {
        "scaled out winners", "scaled out losers", "partial profit", "partial loss",
        "some wins some losses", "won morning lost afternoon", "lost morning won afternoon",
    },
}


def _word_matches(keyword: str, text: str) -> bool:
    """Match a keyword as a whole word, or as a whole-word prefix for short stems."""
    # Escape keyword, but allow keyword to be a phrase; phrase matching handled separately.
    if " " in keyword:
        return keyword in text
    pattern = r'\b' + re.escape(keyword) + r'\w*\b'
    return bool(re.search(pattern, text))


def _negate_scores(text: str, scores: Dict[str, int]) -> None:
    """Zero-out keyword-family hits that are explicitly negated (e.g., 'no losses')."""
    negation_pattern = re.compile(
        r"\b(no|not|none|never|without|didn\'t|did not|doesn\'t|does not|wasn\'t|was not|isn\'t|is not)\b"
        r"[\s\w\-]{0,15}"
        r"\b(loss|losses|lost|miss|missed|stop|stopped|fail|failed|drawdown|profit|profits|win|wins|won|target)\b"
    )
    for match in negation_pattern.finditer(text):
        word = match.group(2)
        if word in {"loss", "losses", "lost", "miss", "missed", "stop", "stopped", "fail", "failed", "drawdown"}:
            scores["loss"] = 0
        elif word in {"profit", "profits", "win", "wins", "won", "target"}:
            scores["win"] = 0


def infer_verdict(outcome_text: str) -> str:
    """Score outcome text into win/loss/flat/mixed/n/a.

    Compound phrases are checked first and scored heavily. Remaining keyword families
    are scored with word-boundary prefix matching so past-tense and derived forms
    are recognized. Explicit negations ("no losses") zero out the hit. A tie or
    conflicting strong signals default to 'mixed'.
    """
    text = (outcome_text or "").lower()
    scores: Dict[str, int] = {"win": 0, "loss": 0, "flat": 0, "mixed": 0}

    # Phrase hits count for more than isolated keywords.
    for verdict, phrases in _VERDICT_PHRASES.items():
        for phrase in phrases:
            if phrase in text:
                scores[verdict] += 3

    # Word-family hits.
    for verdict, keywords in _VERDICT_KEYWORDS.items():
        for kw in keywords:
            if _word_matches(kw, text):
                scores[verdict] += 1

    # Negation pass: "no losses", "didn't win", etc. zero the corresponding family.
    _negate_scores(text, scores)

    max_score = max(scores.values())
    if max_score == 0:
        return "n/a"

    winners = [v for v, s in scores.items() if s == max_score]
    if len(winners) > 1 or "mixed" in winners:
        return "mixed"
    return winners[0]


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
    since = (datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=period_days)).strftime('%Y-%m-%d %H:%M:%S')
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
    since = (datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=period_days)).strftime('%Y-%m-%d %H:%M:%S')
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


def archive_outcome(conn: sqlite3.Connection, outcome_id: int) -> bool:
    """Soft-delete an outcome by setting archived=1."""
    cur = conn.execute("UPDATE outcomes SET archived = 1 WHERE id = ?", (outcome_id,))
    conn.commit()
    return cur.rowcount > 0


def discard_outcome(conn: sqlite3.Connection, outcome_id: int) -> bool:
    """Hard-delete an outcome row."""
    cur = conn.execute("DELETE FROM outcomes WHERE id = ?", (outcome_id,))
    conn.commit()
    return cur.rowcount > 0


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


def reject_queue_item(conn: sqlite3.Connection, item_id: int) -> Optional[Dict[str, Any]]:
    conn.execute(
        "UPDATE process_queue SET status = 'rejected', approved_at = CURRENT_TIMESTAMP WHERE id = ?",
        (item_id,),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM process_queue WHERE id = ?", (item_id,)).fetchone()
    return dict(row) if row else None


def prune_queue(conn: sqlite3.Connection, older_than_days: int = 30) -> int:
    since = (datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=older_than_days)).strftime('%Y-%m-%d %H:%M:%S')
    cur = conn.execute(
        "DELETE FROM process_queue WHERE status = 'proposed' AND created_at < ?",
        (since,),
    )
    conn.commit()
    return cur.rowcount


# ---------------------------------------------------------------------------
# Phase 4: maintenance + alerting helpers
# ---------------------------------------------------------------------------

LOSS_RATE_ALERT_THRESHOLD = 2.0  # losses >= 2x wins triggers a warning
LOSS_RATE_ALERT_MIN_DECISIONS = 3  # need at least 3 win/loss rows before alerting

CONFIDENCE_DECAY_START_DAYS = 90
CONFIDENCE_DECAY_STEP_DAYS = 30
CONFIDENCE_DECAY_AMOUNT = 0.1
CONFIDENCE_DECAY_FLOOR = 0.2


def generate_outcome_warnings(
    aggregates: List[Dict[str, Any]],
    period_days: int = 7,
) -> List[str]:
    """Return human-readable warnings for tags whose loss-rate is elevated.

    A tag is flagged when it has at least `LOSS_RATE_ALERT_MIN_DECISIONS`
    win/loss decisions and losses are at least `LOSS_RATE_ALERT_THRESHOLD` times wins
    (or wins are zero and losses meet the minimum).
    """
    warnings: List[str] = []
    for a in aggregates:
        n_wins = int(a.get("n_wins", 0) or 0)
        n_losses = int(a.get("n_losses", 0) or 0)
        total_decisions = n_wins + n_losses
        if total_decisions < LOSS_RATE_ALERT_MIN_DECISIONS:
            continue
        if n_losses == 0:
            continue
        if n_wins == 0 or n_losses >= LOSS_RATE_ALERT_THRESHOLD * n_wins:
            loss_pct = 100.0 * n_losses / total_decisions
            warnings.append(
                f"[WARNING] Tag '{a['tag']}' loss-rate is {loss_pct:.1f}% "
                f"({n_wins} wins / {n_losses} losses in last {period_days}d) — "
                "recommended to review procedure before executing."
            )
    return warnings


def apply_confidence_decay(
    conn: sqlite3.Connection,
    dry_run: bool = False,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Apply recency decay to `user_prefs` confidence.

    Spec (SELF_LEARNING_LAYER_DESIGN.md §4.1):
    - Rows not written to in 90 days drop 0.1 per 30 days.
    - Floor is 0.2.
    - Each 30-day period beyond the 90-day window reduces confidence by 0.1.

    Decay is computed from `base_confidence` (the seeded value), not from the
    already-decayed `confidence`. This makes the operation idempotent: running it
    twice in a row produces the same result, and the cadence is continuous (a
    row 150 days stale is always decayed by 0.2 regardless of when decay last ran).
    `updated_at` is NOT modified — it stays anchored to the last real write so
    the inactivity calculation remains stable.
    """
    if now is None:
        now = datetime.now(timezone.utc).replace(tzinfo=None)

    rows = conn.execute(
        "SELECT key, value, confidence, base_confidence, updated_at FROM user_prefs"
    ).fetchall()

    affected: List[Dict[str, Any]] = []
    for r in rows:
        updated_at = r["updated_at"]
        if updated_at is None:
            continue
        if isinstance(updated_at, str):
            try:
                updated_at = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
                updated_at = updated_at.replace(tzinfo=None)
            except ValueError:
                continue
        inactive_days = (now - updated_at).days
        if inactive_days <= CONFIDENCE_DECAY_START_DAYS:
            continue

        steps = (inactive_days - CONFIDENCE_DECAY_START_DAYS) // CONFIDENCE_DECAY_STEP_DAYS
        base = r["base_confidence"] if r["base_confidence"] is not None else r["confidence"]
        new_confidence = max(
            CONFIDENCE_DECAY_FLOOR,
            base - steps * CONFIDENCE_DECAY_AMOUNT,
        )
        # Round to avoid floating-point noise in stored confidence.
        new_confidence = round(new_confidence, 2)
        if new_confidence < r["confidence"]:
            affected.append({
                "key": r["key"],
                "old_confidence": r["confidence"],
                "new_confidence": new_confidence,
                "inactive_days": inactive_days,
            })
            if not dry_run:
                # Only update confidence; leave updated_at anchored to the last real write.
                conn.execute(
                    "UPDATE user_prefs SET confidence = ? WHERE key = ?",
                    (new_confidence, r["key"]),
                )

    if affected and not dry_run:
        conn.commit()

    return {
        "rows_affected": len(affected),
        "dry_run": dry_run,
        "details": affected,
    }


def maintain_store(
    conn: sqlite3.Connection,
    render: bool = False,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Run periodic maintenance on the memory store.

    - Apply confidence decay to stale `user_prefs` rows.
    - Prune unapproved `process_queue` proposals older than 30 days.
    - Optionally re-render `USER.md`.
    """
    decay_report = apply_confidence_decay(conn, dry_run=dry_run)
    pruned = prune_queue(conn, older_than_days=30) if not dry_run else 0

    rendered_path: Optional[str] = None
    if render and not dry_run:
        md = render_profile_md(conn)
        with open(USER_MD_PATH, "w", encoding="utf-8") as f:
            f.write(md)
        rendered_path = USER_MD_PATH

    return {
        "decay": decay_report,
        "pruned_proposals": pruned,
        "rendered_user_md": rendered_path,
        "dry_run": dry_run,
    }


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


def _simple_stem(word: str) -> str:
    """Very light stemmer for English trade/computing terms."""
    word = word.lower()
    for suffix in ("ing", "edly", "edly", "ed", "es", "ers", "er", "s"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            return word[: -len(suffix)]
    return word


def _token_set(text: str) -> set[str]:
    """Tokenize and stem."""
    raw = re.split(r"[\s,._\-/:()\[\]]+", (text or "").lower())
    return {_simple_stem(t) for t in raw if t and len(t) > 2}


def check_skill_dedupe(tag: str) -> Optional[str]:
    """Return the name of an existing skill whose name/description covers the tag.

    Matching hierarchy:
      1. Exact case-insensitive match against skill slug or front-matter name,
         after normalizing spaces/underscores/hyphens.
      2. The full tag phrase (>= 2 tokens) appears in name or description.
      3. Token-stem Jaccard similarity >= 0.65 between tag and (name + description).
    """
    tag_lower = tag.lower()
    tag_normalized = tag_lower.replace("_", " ").replace("-", " ")
    tag_tokens = _token_set(tag)
    multi_token = len(tag.split()) >= 2 or "_" in tag or "-" in tag

    if not tag_tokens:
        return None

    for name, desc in get_skill_descriptions():
        name_lower = name.lower()
        desc_lower = (desc or "").lower()
        haystack = f"{name_lower} {desc_lower}"

        # 1. exact / normalized exact
        if tag_lower == name_lower:
            return name
        if tag_normalized == name_lower.replace("-", " "):
            return name

        # 2. phrase contained (only for multi-token tags; single words are too noisy)
        if multi_token:
            if tag_lower in haystack or tag_normalized in haystack:
                return name

        # 3. token-stem overlap with a threshold
        haystack_tokens = _token_set(haystack)
        if not haystack_tokens:
            continue
        intersection = tag_tokens & haystack_tokens
        union = tag_tokens | haystack_tokens
        if len(union) > 0 and len(intersection) / len(union) >= 0.65:
            return name

    return None


PROPOSE_SKILL_WINDOW_DAYS = 30


def propose_skill_draft(conn: sqlite3.Connection, tag: str) -> Tuple[bool, str, Optional[int]]:
    """Returns (eligible, message, queue_id). Never writes a skill file."""
    # threshold: >=3 distinct win run_ids, zero losses, last N days.
    # run_id is the authoritative key for distinct executions; subject is freeform
    # and must NOT be used as the gate key.
    since = (datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=PROPOSE_SKILL_WINDOW_DAYS)).strftime('%Y-%m-%d %H:%M:%S')

    # Count distinct run_ids that produced wins.
    n_run_ids = conn.execute(
        "SELECT COUNT(DISTINCT run_id) FROM outcomes "
        "WHERE tag = ? AND verdict = 'win' AND ts >= ? AND archived = 0 AND run_id IS NOT NULL AND run_id != ''",
        (tag, since),
    ).fetchone()[0]

    # Count win rows that lack run_id (informational only).
    n_no_run = conn.execute(
        "SELECT COUNT(*) FROM outcomes "
        "WHERE tag = ? AND verdict = 'win' AND ts >= ? AND archived = 0 AND (run_id IS NULL OR run_id = '')",
        (tag, since),
    ).fetchone()[0]

    losses = conn.execute(
        "SELECT count(*) FROM outcomes WHERE tag = ? AND verdict = 'loss' AND ts >= ? AND archived = 0",
        (tag, since),
    ).fetchone()[0]

    if n_run_ids < 3:
        detail = f"{n_run_ids} distinct run_id(s)"
        if n_no_run:
            detail += f" (plus {n_no_run} win row(s) with no run_id, ignored)"
        return False, (
            f"Not enough distinct wins for tag '{tag}': {detail} found (need >=3 distinct run_ids). "
            "Each successful outcome should include a unique run_id."
        ), None

    if losses > 0:
        return False, f"Tag '{tag}' has {losses} interleaved loss(es) in the last {PROPOSE_SKILL_WINDOW_DAYS}d — gate refuses.", None

    # Build a human-readable subject list for the draft, one per run_id.
    win_rows = conn.execute(
        "SELECT run_id, MAX(subject) AS subject FROM outcomes "
        "WHERE tag = ? AND verdict = 'win' AND ts >= ? AND archived = 0 AND run_id IS NOT NULL AND run_id != '' "
        "GROUP BY run_id",
        (tag, since),
    ).fetchall()

    distinct_run_ids = [r["run_id"] for r in win_rows]
    distinct_subjects = []
    seen = set()
    for r in win_rows:
        label = r["subject"] or r["run_id"]
        if label not in seen:
            seen.add(label)
            distinct_subjects.append(label)

    dup = check_skill_dedupe(tag)
    if dup:
        return False, f"Tag '{tag}' already covered by existing skill '{dup}'. Refusing to propose duplicate.", None

    # build draft
    draft_lines = [
        "---",
        f"name: {tag.replace(' ', '-')}",
        f"description: Procedure distilled from {len(distinct_run_ids)} successful executions of tag '{tag}'.",
        f"based_on: outcome tag {tag} ({len(distinct_run_ids)} distinct run_ids matched)",
        "---",
        "",
        f"# Skill: {tag}",
        "",
        f"This procedure was distilled from {len(distinct_run_ids)} distinct successful run_ids "
        f"tagged '{tag}' in the last {PROPOSE_SKILL_WINDOW_DAYS} days, with zero interleaved failures.",
        "",
        "## Successful subjects / run_ids",
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