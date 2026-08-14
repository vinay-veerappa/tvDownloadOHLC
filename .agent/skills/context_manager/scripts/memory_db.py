"""
memory_db.py — context_manager DB layer.

Schema is owned by store_schema.py (single source of truth, B1).
This module re-exports the connection/init helpers and wraps them with
the add_memory / search_memories signatures that recall.py and remember.py
have always used.
"""
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from store_schema import (
    DB_PATH,
    ensure_schema,
    get_db_connection,
    fts_search,
)


def init_db():
    """Initializes all tables + FTS5 index via the shared schema owner."""
    conn = get_db_connection()
    try:
        ensure_schema(conn)
    finally:
        conn.close()


def get_db_conn():
    """Alias kept for any legacy callers."""
    return get_db_connection()


def add_memory(category: str, content: str, tags: str = ""):
    """Adds a new memory to the database."""
    conn = get_db_connection()
    try:
        now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        conn.execute(
            "INSERT INTO memories (category, content, tags, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (category, content, tags, now, now),
        )
        conn.commit()
    finally:
        conn.close()
    print(f"Memory added: [{category}] {content}")


def search_memories(query=None, category=None, limit=10):
    """FTS5-first search with LIKE fallback. Returns list of dicts (unchanged contract)."""
    conn = get_db_connection()
    try:
        if query:
            return fts_search(conn, query, category, limit)
        # no query — category filter only
        sql = "SELECT * FROM memories WHERE 1=1"
        params = []
        if category:
            sql += " AND category = ?"
            params.append(category)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    print(f"Database initialized at {DB_PATH}")