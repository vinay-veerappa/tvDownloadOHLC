import sqlite3
import os
import datetime
import argparse
from typing import List, Optional, Dict, Any

# Define database path relative to this script
# Script location: .agent/skills/context_manager/scripts/memory_db.py
# Database location: .agent/memory.db
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
DB_PATH = os.path.join(BASE_DIR, "memory.db")

def get_db_connection():
    """Establishes a connection to the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes the database table if it doesn't exist."""
    print(f"Initializing database at: {DB_PATH}")
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            content TEXT NOT NULL,
            tags TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def add_memory(category: str, content: str, tags: str = ""):
    """Adds a new memory to the database."""
    conn = get_db_connection()
    c = conn.cursor()
    now = datetime.datetime.now().isoformat()
    c.execute('''
        INSERT INTO memories (category, content, tags, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
    ''', (category, content, tags, now, now))
    conn.commit()
    conn.close()
    print(f"Memory added: [{category}] {content}")

def search_memories(query: Optional[str] = None, category: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
    """Searches for memories matching the query string or category."""
    conn = get_db_connection()
    c = conn.cursor()
    
    sql = "SELECT * FROM memories WHERE 1=1"
    params = []

    if category:
        sql += " AND category = ?"
        params.append(category)
    
    if query:
        # Simple LIKE query for now, can be upgraded to FTS later
        sql += " AND (content LIKE ? OR tags LIKE ?)"
        like_query = f"%{query}%"
        params.append(like_query)
        params.append(like_query)

    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    c.execute(sql, params)
    rows = c.fetchall()
    conn.close()
    
    results = [dict(row) for row in rows]
    return results

if __name__ == "__main__":
    # If run directly, ensure DB is initialized
    init_db()
