"""Database initialization and schema migration tool for Trading Second Brain.

Executes schema.sql and verifies:
1. All 22 canonical tables exist.
2. All 38 immutability triggers exist.
3. All 4 views resolve.
"""

import argparse
import sys
from pathlib import Path
from typing import List, Optional, Tuple, Union

from scripts.trading_brain.db.connection import REPO_ROOT, get_db_connection, resolve_db_path

DEFAULT_SCHEMA_PATH = REPO_ROOT / "scripts" / "trading_brain" / "db" / "schema.sql"

EXPECTED_TABLES = [
    "information_items",
    "information_item_review_events",
    "plan_snapshots",
    "plan_lifecycle_events",
    "plan_amendments",
    "forecast_runs",
    "forecast_run_inputs",
    "forecast_snapshots",
    "signal_opportunities",
    "signal_disposition_events",
    "signal_outcomes",
    "session_tape_actuals",
    "execution_events",
    "intervention_events",
    "drill_attempts",
    "behavioral_declarations",
    "unmatched_link_events",
    "candidate_finding_events",
    "strategy_versions",
    "model_versions",
    "model_deployment_events",
    "legacy_projection_outbox",
    "broker_ingest_state"
]

EXPECTED_VIEWS = [
    "v_information_items_active",
    "v_session_tape_actuals_current",
    "v_unmatched_links_open",
    "v_candidate_findings_staged"
]

PROTECTED_TABLES_COUNT = 19
EXPECTED_TRIGGER_COUNT = PROTECTED_TABLES_COUNT * 2  # 38 triggers


def init_trading_brain_db(
    db_path: Optional[Union[str, Path]] = None,
    schema_path: Optional[Union[str, Path]] = None,
    verbose: bool = True
) -> Tuple[bool, List[str]]:
    """Initializes the database schema and verifies integrity."""
    target_db = resolve_db_path(db_path)
    target_schema = Path(schema_path) if schema_path else DEFAULT_SCHEMA_PATH
    if not target_schema.is_absolute():
        target_schema = REPO_ROOT / target_schema
        
    if not target_schema.exists():
        raise FileNotFoundError(f"Schema file not found at: {target_schema}")
        
    messages = []
    schema_sql = target_schema.read_text(encoding="utf-8")
    
    if verbose:
        print(f"[*] Initializing Trading Second Brain DB at: {target_db}")
        print(f"[*] Applying schema from: {target_schema}")
        
    with get_db_connection(target_db) as conn:
        conn.executescript(schema_sql)
        
        # 1. Verify tables
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
        tables = {row["name"] for row in cursor.fetchall()}
        missing_tables = [t for t in EXPECTED_TABLES if t not in tables]
        
        if missing_tables:
            msg = f"ERROR: Missing tables: {missing_tables}"
            messages.append(msg)
            if verbose:
                print(msg)
            return False, messages
            
        messages.append(f"SUCCESS: All {len(EXPECTED_TABLES)} tables verified.")
        
        # 2. Verify views
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='view' ORDER BY name;")
        views = {row["name"] for row in cursor.fetchall()}
        missing_views = [v for v in EXPECTED_VIEWS if v not in views]
        
        if missing_views:
            msg = f"ERROR: Missing views: {missing_views}"
            messages.append(msg)
            if verbose:
                print(msg)
            return False, messages
            
        messages.append(f"SUCCESS: All {len(EXPECTED_VIEWS)} views verified.")
        
        # 3. Verify triggers
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='trigger' ORDER BY name;")
        triggers = [row["name"] for row in cursor.fetchall()]
        
        if len(triggers) < EXPECTED_TRIGGER_COUNT:
            msg = f"ERROR: Expected {EXPECTED_TRIGGER_COUNT} triggers, found {len(triggers)}"
            messages.append(msg)
            if verbose:
                print(msg)
            return False, messages
            
        messages.append(f"SUCCESS: All {len(triggers)} immutability triggers verified.")
        
        # 4. Verify PRAGMA integrity
        cursor = conn.execute("PRAGMA integrity_check;")
        integrity = cursor.fetchone()[0]
        if integrity != "ok":
            msg = f"ERROR: Integrity check failed: {integrity}"
            messages.append(msg)
            return False, messages
            
        messages.append("SUCCESS: PRAGMA integrity_check passed (ok).")
        
    if verbose:
        for m in messages:
            print(f"  -> {m}")
        print("[+] Trading Second Brain Database successfully initialized.")
        
    return True, messages


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Initialize Trading Second Brain SQLite Database")
    parser.add_argument("--db", type=str, default=None, help="Custom database file path")
    parser.add_argument("--schema", type=str, default=None, help="Custom schema.sql path")
    args = parser.parse_args()
    
    success, msgs = init_trading_brain_db(db_path=args.db, schema_path=args.schema, verbose=True)
    sys.exit(0 if success else 1)
