"""Database connection and lifecycle context manager for Trading Second Brain.

Enforces:
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

DEFAULT_DB_PATH = Path("data/wargaming/db/trading_brain.sqlite")


def resolve_db_path(db_path: Optional[Union[str, Path]] = None) -> Path:
    """Resolves the canonical SQLite database path."""
    if db_path is not None:
        return Path(db_path)
    env_path = os.environ.get("TRADING_BRAIN_DB_PATH")
    if env_path:
        return Path(env_path)
    return DEFAULT_DB_PATH


@contextmanager
def get_db_connection(
    db_path: Optional[Union[str, Path]] = None,
    autocommit: bool = True
) -> Generator[sqlite3.Connection, None, None]:
    """Yields a configured SQLite connection with foreign keys and WAL mode enabled.
    
    Args:
        db_path: Optional path to SQLite file. If None, resolves canonical path.
        autocommit: If True, commits transaction on clean exit and rolls back on exception.
    """
    target_path = resolve_db_path(db_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(
        str(target_path),
        timeout=60.0
    )
    conn.row_factory = sqlite3.Row
    
    # Enforce mandatory PRAGMAs
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
