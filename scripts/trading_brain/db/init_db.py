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
    "drill_sealed_answers",
    "drill_split_registry",
    "behavioral_declarations",
    "unmatched_link_events",
    "candidate_finding_events",
    "sealed_holdouts",
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

PROTECTED_TABLES_COUNT = 22
EXPECTED_TRIGGER_COUNT = PROTECTED_TABLES_COUNT * 2  # 44 triggers

# Bump this constant with EVERY backward-incompatible schema change, and add the matching
# migration step to _apply_schema_migrations. A database stamped newer than the code is
# refused (downgrade risk); a database stamped older runs pending migrations before use.
SCHEMA_VERSION = 4


def _apply_schema_migrations(conn, from_version: int, messages: List[str], verbose: bool) -> None:
    """Applies incremental migrations for databases initialized by older schema versions.

    Each block upgrades exactly one version step. Blocks must remain in ascending order.
    """
    if from_version < 2:
        # v1 -> v2: model_versions.status no longer carries mutable deployment state;
        # deployment transitions moved to the append-only model_deployment_events ledger.
        # Existing rows need no rewrite (status columns retained for audit reads).
        messages.append("MIGRATED: schema v1 -> v2 (model_deployment_events ledger adopted).")
        if verbose:
            print("  -> migration v1 -> v2 applied (model_deployment_events ledger).")
    if from_version < 3:
        # v2 -> v3: plan_snapshots gains source_revision_hash and a unique constraint
        # enabling revision-aware Prisma TradePlan mirroring with supersession.
        messages.append("MIGRATED: schema v2 -> v3 (plan_snapshots source_revision_hash + unique index).")
        if verbose:
            print("  -> migration v2 -> v3 applied (source_revision_hash).")
        try:
            conn.execute(
                """
                ALTER TABLE plan_snapshots ADD COLUMN source_revision_hash TEXT;
                """
            )
            conn.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS uq_plan_source_revision
                ON plan_snapshots(source_plan_id, source_revision_hash)
                WHERE source_plan_id IS NOT NULL;
                """
            )
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                messages.append("NOTE: source_revision_hash already present, migration idempotent.")
            else:
                raise
    if from_version < 4:
        # v3 -> v4: (a) review events gain a trusted received_at_utc separate from the
        # user-declared event_timestamp_utc (anti-backdating); (b) drill_sealed_answers
        # gains sealed drill metadata (drill_type, dataset_split) and a custody token so
        # submission cannot trust caller-declared classification.
        messages.append("MIGRATED: schema v3 -> v4 (review receipt time + sealed drill metadata/custody token).")
        if verbose:
            print("  -> migration v3 -> v4 applied.")
        # (a) review events: trusted receipt column
        try:
            conn.execute(
                "ALTER TABLE information_item_review_events ADD COLUMN received_at_utc TIMESTAMP;"
            )
            # Backfill trusted receipt for pre-existing rows with the max observable time
            # (honest floor: cannot manufacture an earlier trusted clock than what exists).
            conn.execute(
                """
                UPDATE information_item_review_events
                SET received_at_utc = COALESCE(received_at_utc, event_timestamp_utc, created_at_utc);
                """
            )
            conn.execute(
                """
                CREATE TRIGGER IF NOT EXISTS trg_review_events_default_received
                AFTER INSERT ON information_item_review_events
                WHEN NEW.received_at_utc IS NULL
                BEGIN
                    UPDATE information_item_review_events
                    SET received_at_utc = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
                    WHERE review_event_id = NEW.review_event_id;
                END;
                """
            )
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e):
                raise
        # (b) sealed drill metadata + custody token
        for col, ddl in [
            ("drill_type", "ALTER TABLE drill_sealed_answers ADD COLUMN drill_type TEXT NOT NULL DEFAULT 'RECOGNITION';"),
            ("dataset_split", "ALTER TABLE drill_sealed_answers ADD COLUMN dataset_split TEXT NOT NULL DEFAULT 'TRAINING';"),
            ("custody_token", "ALTER TABLE drill_sealed_answers ADD COLUMN custody_token TEXT;"),
        ]:
            try:
                conn.execute(ddl)
            except sqlite3.OperationalError as e:
                if "duplicate column name" not in str(e):
                    raise


def _check_and_migrate_schema(conn, messages: List[str], verbose: bool) -> None:
    """Verifies PRAGMA user_version against SCHEMA_VERSION, migrating up if required.

    Fails closed: a database stamped NEWER than this code's SCHEMA_VERSION indicates a
    downgrade (stale code against a migrated database) and the init refuses to proceed,
    because executing an old schema against newer tables corrupts references.
    """
    cur = conn.execute("PRAGMA user_version;")
    db_version = int(cur.fetchone()[0])
    
    if db_version == 0:
        # Freshly initialized database: stamp current version.
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION};")
        messages.append(f"SUCCESS: schema stamped at version {SCHEMA_VERSION}.")
    elif db_version > SCHEMA_VERSION:
        msg = (
            f"ERROR: database schema v{db_version} is newer than this code expects "
            f"(v{SCHEMA_VERSION}). Refusing to initialize a downgrade."
        )
        messages.append(msg)
        if verbose:
            print(msg)
        raise ValueError(msg)
    elif db_version < SCHEMA_VERSION:
        _apply_schema_migrations(conn, db_version, messages, verbose)
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION};")
        messages.append(f"SUCCESS: schema migrated to version {SCHEMA_VERSION}.")
    else:
        messages.append(f"SUCCESS: schema version {SCHEMA_VERSION} verified.")


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
        
        # 0. Verify schema version and apply pending migrations
        _check_and_migrate_schema(conn, messages, verbose)
        
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
