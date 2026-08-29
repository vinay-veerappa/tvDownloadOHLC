"""Transactional Outbox Projector for Legacy Database Rollback Fence (Milestone 0.3b).

Guarantees crash-resilient asynchronous replay of canonical Trading Brain records to legacy databases:
1. Canonical transaction commits canonical row + legacy_projection_outbox row in a single atomic transaction.
2. Supports WARGAME_DB_TARGET environment variable ('CANONICAL', 'DUAL_OUTBOX', 'LEGACY_DIRECT', 'PAUSED').
3. OutboxProjector acquires leases on PENDING outbox records.
4. Projects payloads into legacy SQLite databases (system_wargames.sqlite, market_actuals.sqlite, mickey_ground_truth.sqlite).
5. Marks outbox records as PROJECTED (or DEAD_LETTER after max_retries).
"""

import json
import os
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from scripts.trading_brain.db.connection import REPO_ROOT, get_db_connection, resolve_db_path
from scripts.utils.market_calendar import now_iso_utc

LEGACY_SYSTEM_WARGAMES = REPO_ROOT / "data" / "wargaming" / "db" / "system_wargames.sqlite"
LEGACY_MARKET_ACTUALS = REPO_ROOT / "data" / "wargaming" / "db" / "market_actuals.sqlite"
LEGACY_MICKEY_GROUND_TRUTH = REPO_ROOT / "data" / "wargaming" / "db" / "mickey_ground_truth.sqlite"


class DatabasePausedError(Exception):
    """Raised when writes are attempted while WARGAME_DB_TARGET is set to PAUSED."""
    pass


class OutboxProjector:
    """Projects canonical outbox records to legacy databases with retry and lease token semantics."""

    def __init__(
        self,
        canonical_db_path: Optional[Union[str, Path]] = None,
        system_wargames_path: Optional[Union[str, Path]] = None,
        market_actuals_path: Optional[Union[str, Path]] = None,
        mickey_ground_truth_path: Optional[Union[str, Path]] = None,
        max_retries: int = 3,
        lease_duration_sec: int = 30
    ):
        self.canonical_db = resolve_db_path(canonical_db_path)
        self.sys_db = Path(system_wargames_path) if system_wargames_path else LEGACY_SYSTEM_WARGAMES
        self.mkt_db = Path(market_actuals_path) if market_actuals_path else LEGACY_MARKET_ACTUALS
        self.mick_db = Path(mickey_ground_truth_path) if mickey_ground_truth_path else LEGACY_MICKEY_GROUND_TRUTH
        self.max_retries = max_retries
        self.lease_duration_sec = lease_duration_sec

    @staticmethod
    def get_target_mode() -> str:
        """Returns active database target mode: 'CANONICAL', 'DUAL_OUTBOX', 'LEGACY_DIRECT', 'PAUSED'."""
        return os.environ.get("WARGAME_DB_TARGET", "DUAL_OUTBOX").upper()

    @staticmethod
    def enqueue_outbox_item(
        conn: sqlite3.Connection,
        destination_db: str,
        canonical_table: str,
        canonical_id: str,
        payload: Dict[str, Any],
        schema_version: str = "1.0.0"
    ) -> str:
        """Enqueues an outbox record within an existing canonical transaction."""
        target_mode = OutboxProjector.get_target_mode()
        if target_mode == "PAUSED":
            raise DatabasePausedError("Database writes are PAUSED via WARGAME_DB_TARGET=PAUSED")
            
        outbox_id = str(uuid.uuid4())
        conn.execute(
            """
            INSERT INTO legacy_projection_outbox (
                outbox_id, destination_db, canonical_table, canonical_id,
                schema_version, payload_json, status, attempt_count
            ) VALUES (?, ?, ?, ?, ?, ?, 'PENDING', 0);
            """,
            (outbox_id, destination_db, canonical_table, canonical_id, schema_version, json.dumps(payload))
        )
        return outbox_id

    def project_pending(self, limit: int = 50) -> Dict[str, int]:
        """Claims and projects pending outbox records to their legacy database destinations."""
        target_mode = self.get_target_mode()
        if target_mode == "PAUSED":
            return {"projected": 0, "failed": 0, "dead_letter": 0}
            
        now_dt = datetime.now(timezone.utc)
        now_iso = now_dt.isoformat()
        lease_expires = (now_dt + timedelta(seconds=self.lease_duration_sec)).isoformat()
        lease_token = str(uuid.uuid4())
        
        counts = {"projected": 0, "failed": 0, "dead_letter": 0}
        
        with get_db_connection(self.canonical_db) as conn:
            conn.execute(
                """
                UPDATE legacy_projection_outbox
                SET lease_token = ?, lease_expires_at_utc = ?
                WHERE outbox_id IN (
                    SELECT outbox_id FROM legacy_projection_outbox
                    WHERE status = 'PENDING'
                      AND (lease_expires_at_utc IS NULL OR lease_expires_at_utc < ?)
                    LIMIT ?
                );
                """,
                (lease_token, lease_expires, now_iso, limit)
            )
            
            cur = conn.execute(
                "SELECT * FROM legacy_projection_outbox WHERE lease_token = ? AND status = 'PENDING';",
                (lease_token,)
            )
            records = cur.fetchall()
            
            for r in records:
                outbox_id = r["outbox_id"]
                dest_db = r["destination_db"]
                payload = json.loads(r["payload_json"])
                attempt_count = r["attempt_count"] + 1
                
                try:
                    self._dispatch_to_legacy(dest_db, payload)
                    
                    conn.execute(
                        """
                        UPDATE legacy_projection_outbox
                        SET status = 'PROJECTED', projected_at_utc = ?, lease_token = NULL, lease_expires_at_utc = NULL, last_error = NULL
                        WHERE outbox_id = ?;
                        """,
                        (now_iso_utc(), outbox_id)
                    )
                    counts["projected"] += 1
                except Exception as ex:
                    error_msg = str(ex)
                    new_status = "DEAD_LETTER" if attempt_count >= self.max_retries else "PENDING"
                    
                    conn.execute(
                        """
                        UPDATE legacy_projection_outbox
                        SET status = ?, attempt_count = ?, last_error = ?, lease_token = NULL, lease_expires_at_utc = NULL
                        WHERE outbox_id = ?;
                        """,
                        (new_status, attempt_count, error_msg, outbox_id)
                    )
                    if new_status == "DEAD_LETTER":
                        counts["dead_letter"] += 1
                    else:
                        counts["failed"] += 1
                        
        return counts

    def _dispatch_to_legacy(self, destination_db: str, payload: Dict[str, Any]) -> None:
        """Dispatches an individual payload to the corresponding legacy SQLite database."""
        if destination_db == "system_wargames":
            target_file = self.sys_db
            target_file.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(str(target_file)) as conn:
                cols = list(payload.keys())
                placeholders = ", ".join(["?"] * len(cols))
                col_names = ", ".join(cols)
                conn.execute(
                    f"INSERT OR REPLACE INTO system_wargames ({col_names}) VALUES ({placeholders});",
                    [payload[c] for c in cols]
                )
        elif destination_db == "market_actuals":
            target_file = self.mkt_db
            target_file.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(str(target_file)) as conn:
                cols = list(payload.keys())
                placeholders = ", ".join(["?"] * len(cols))
                col_names = ", ".join(cols)
                conn.execute(
                    f"INSERT OR REPLACE INTO market_actuals ({col_names}) VALUES ({placeholders});",
                    [payload[c] for c in cols]
                )
        elif destination_db == "mickey_ground_truth":
            target_file = self.mick_db
            target_file.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(str(target_file)) as conn:
                cols = list(payload.keys())
                placeholders = ", ".join(["?"] * len(cols))
                col_names = ", ".join(cols)
                conn.execute(
                    f"INSERT OR REPLACE INTO mickey_wargames ({col_names}) VALUES ({placeholders});",
                    [payload[c] for c in cols]
                )
        else:
            raise ValueError(f"Unknown legacy destination database: '{destination_db}'")
