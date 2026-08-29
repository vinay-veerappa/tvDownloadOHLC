"""Database connection and lifecycle context manager for Trading Second Brain.

Enforces:
- Absolute REPO_ROOT path anchoring
- Foreign key constraints (PRAGMA foreign_keys = ON)
- WAL journaling mode (PRAGMA journal_mode = WAL)
- Busy timeout 60s (PRAGMA busy_timeout = 60000)
- Normal synchronization (PRAGMA synchronous = NORMAL)
- sqlite3.Row row factory for clean dict-like mapping
"""

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional, Union

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB_PATH = REPO_ROOT / "data" / "wargaming" / "db" / "trading_brain.sqlite"


def resolve_db_path(db_path: Optional[Union[str, Path]] = None) -> Path:
    """Resolves the canonical SQLite database path anchored to REPO_ROOT."""
    if db_path is not None:
        p = Path(db_path)
        return p if p.is_absolute() else (REPO_ROOT / p)
    env_path = os.environ.get("TRADING_BRAIN_DB_PATH")
    if env_path:
        p = Path(env_path)
        return p if p.is_absolute() else (REPO_ROOT / p)
    return DEFAULT_DB_PATH


@contextmanager
def get_db_connection(
    db_path: Optional[Union[str, Path]] = None,
    autocommit: bool = True
) -> Generator[sqlite3.Connection, None, None]:
    """Yields a configured SQLite connection with foreign keys and WAL mode enabled."""
    target_path = resolve_db_path(db_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(
        str(target_path),
        timeout=60.0
    )
    conn.row_factory = sqlite3.Row
    
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA busy_timeout = 60000;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    
    try:
        yield conn
        if autocommit:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def assert_monotonic_timestamp(conn: sqlite3.Connection, table_name: str, timestamp_col: str, new_ts: str) -> None:
    """Verifies that new_ts is strictly greater than or equal to the maximum observed timestamp in table."""
    cur = conn.execute(f"SELECT MAX({timestamp_col}) AS max_ts FROM {table_name};")
    row = cur.fetchone()
    if row and row["max_ts"]:
        max_ts = row["max_ts"]
        if new_ts < max_ts:
            raise ValueError(f"Clock monotonicity violation on {table_name}.{timestamp_col}: new={new_ts} < max={max_ts}")
