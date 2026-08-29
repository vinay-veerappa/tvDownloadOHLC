"""Hardened NinjaTrader 8 Broker Ingestion Adapter (Milestone 0.6)."""

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from scripts.trading_brain.db.connection import get_db_connection
from scripts.utils.market_calendar import (
    derive_futures_session_date,
    now_iso_utc,
    parse_iso_utc,
    to_iso_utc,
)


class NT8BrokerAdapter:
    @classmethod
    def ingest_fills(
        cls,
        fills: List[Dict[str, Any]],
        account_id: str = "PRIMARY",
        endpoint_name: str = "nt_fill_events",
        db_path: Optional[Union[str, Path]] = None
    ) -> Dict[str, Any]:
        if not fills:
            return {"ingested_count": 0, "inserted": 0, "skipped_count": 0, "skipped": 0, "last_cursor": None, "latest_cursor": None}
            
        inserted = 0
        skipped = 0
        latest_cursor = None
        event_ts_iso = now_iso_utc()
        
        with get_db_connection(db_path) as conn:
            for fill in fills:
                broker_exec_id = fill["broker_execution_id"]
                raw_ts = fill.get("event_timestamp_utc", now_iso_utc())
                event_ts_iso = to_iso_utc(raw_ts)
                
                ticker = fill.get("ticker", "NQ1")
                session_date = fill.get("session_date") or derive_futures_session_date(event_ts_iso)
                
                cur = conn.execute(
                    "SELECT execution_id FROM execution_events WHERE account_id = ? AND broker_execution_id = ?;",
                    (account_id, broker_exec_id)
                )
                if cur.fetchone():
                    skipped += 1
                    continue
                    
                exec_id = fill.get("execution_id") or str(uuid.uuid4())
                order_id = fill.get("broker_order_id", f"ord-{broker_exec_id}")
                action = fill["order_action"].upper()
                order_type = fill.get("order_type", "LIMIT").upper()
                qty = int(fill["quantity"])
                price = float(fill["fill_price"])
                strat_id = fill.get("strategy_version_id")
                
                idemp_payload = f"{account_id}:{broker_exec_id}:{event_ts_iso}"
                idemp_key = fill.get("idempotency_key") or hashlib.sha256(idemp_payload.encode("utf-8")).hexdigest()
                
                cur_idemp = conn.execute(
                    "SELECT execution_id FROM execution_events WHERE account_id = ? AND idempotency_key = ?;",
                    (account_id, idemp_key)
                )
                if cur_idemp.fetchone():
                    skipped += 1
                    continue
                
                conn.execute(
                    """
                    INSERT INTO execution_events (
                        execution_id, session_date, ticker, account_id,
                        broker_execution_id, broker_order_id, order_action,
                        order_type, quantity, fill_price, strategy_version_id,
                        idempotency_key, event_timestamp_utc
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        exec_id, session_date, ticker, account_id,
                        broker_exec_id, order_id, action, order_type,
                        qty, price, strat_id, idemp_key, event_ts_iso
                    )
                )
                inserted += 1
                latest_cursor = fill.get("cursor") or broker_exec_id
                
            if latest_cursor:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO broker_ingest_state (
                        endpoint_name, account_id, last_cursor,
                        last_event_timestamp_utc, updated_at_utc
                    ) VALUES (?, ?, ?, ?, ?);
                    """,
                    (endpoint_name, account_id, latest_cursor, event_ts_iso, now_iso_utc())
                )
                
        return {
            "ingested_count": inserted, "inserted": inserted,
            "skipped_count": skipped, "skipped": skipped,
            "last_cursor": latest_cursor, "latest_cursor": latest_cursor
        }

    @classmethod
    def get_last_cursor(
        cls,
        endpoint_name: str,
        account_id: str,
        db_path: Optional[Union[str, Path]] = None
    ) -> Optional[str]:
        with get_db_connection(db_path) as conn:
            cur = conn.execute(
                "SELECT last_cursor FROM broker_ingest_state WHERE endpoint_name = ? AND account_id = ?;",
                (endpoint_name, account_id)
            )
            row = cur.fetchone()
            return row["last_cursor"] if row else None

    @classmethod
    def ingest_interventions(
        cls,
        interventions: List[Dict[str, Any]],
        account_id: Optional[str] = None,
        source_system: str = "NT8_RISKGUARD_CS",
        db_path: Optional[Union[str, Path]] = None
    ) -> Dict[str, Any]:
        inserted = 0
        skipped = 0
        with get_db_connection(db_path) as conn:
            for item in interventions:
                interv_id = item.get("intervention_id") or str(uuid.uuid4())
                raw_ts = item.get("event_timestamp_utc", now_iso_utc())
                event_ts_iso = to_iso_utc(raw_ts)
                session_date = item.get("session_date") or derive_futures_session_date(event_ts_iso)
                item_account = account_id or item.get("account_id", "PRIMARY")
                
                idemp_payload = f"{item_account}:{item['rule_id']}:{event_ts_iso}"
                idemp_key = item.get("idempotency_key") or hashlib.sha256(idemp_payload.encode("utf-8")).hexdigest()
                
                cur = conn.execute(
                    "SELECT intervention_id FROM intervention_events WHERE account_id = ? AND idempotency_key = ?;",
                    (item_account, idemp_key)
                )
                if cur.fetchone():
                    skipped += 1
                    continue
                    
                conn.execute(
                    """
                    INSERT INTO intervention_events (
                        intervention_id, session_date, ticker, account_id,
                        source_event_id, plan_snapshot_id, strategy_version_id,
                        producer, producer_version, authority_class, action_mode,
                        rule_id, rule_version, observed_value, threshold_value,
                        enforced, idempotency_key, event_timestamp_utc
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        interv_id, session_date, item.get("ticker", "NQ1"), item_account,
                        item.get("source_event_id"), item.get("plan_snapshot_id"),
                        item.get("strategy_version_id"), item.get("producer", source_system),
                        item.get("producer_version", "1.0.0"),
                        item.get("authority_class", "HARD_LOCKOUT_ENFORCED"),
                        item.get("action_mode", "ACTING"), item["rule_id"],
                        item.get("rule_version", "1.0.0"), item.get("observed_value"),
                        item.get("threshold_value"), 1 if item.get("enforced", True) else 0,
                        idemp_key, event_ts_iso
                    )
                )
                inserted += 1
        return {"ingested_count": inserted, "inserted": inserted, "skipped_count": skipped, "skipped": skipped}

    @classmethod
    def reconcile_positions(
        cls,
        account_id: str,
        expected_position: Optional[int] = None,
        broker_position: Optional[int] = None,
        actual_position: Optional[int] = None,
        session_date: Optional[str] = None,
        ticker: str = "NQ1",
        db_path: Optional[Union[str, Path]] = None
    ) -> Dict[str, Any]:
        with get_db_connection(db_path) as conn:
            cur = conn.execute(
                """
                SELECT SUM(CASE WHEN order_action IN ('BUY', 'LONG') THEN quantity
                                ELSE -quantity END) AS net_pos
                FROM execution_events
                WHERE account_id = ? AND ticker = ?;
                """,
                (account_id, ticker)
            )
            row = cur.fetchone()
            calculated_internal = row["net_pos"] if row and row["net_pos"] is not None else 0
            
        target_broker = broker_position if broker_position is not None else actual_position
        if target_broker is None:
            target_broker = expected_position if expected_position is not None else 0
            
        drift = target_broker - calculated_internal
        reconciled = (drift == 0)
        
        if not reconciled:
            now_iso = now_iso_utc()
            s_date = session_date or derive_futures_session_date(now_iso)
            cls.ingest_interventions(
                interventions=[{
                    "ticker": ticker,
                    "session_date": s_date,
                    "account_id": account_id,
                    "rule_id": "POSITION_DRIFT_DETECTED",
                    "authority_class": "POSITION_RECONCILIATION",
                    "action_mode": "LOGGING",
                    "observed_value": float(target_broker),
                    "threshold_value": float(calculated_internal),
                    "enforced": False
                }],
                account_id=account_id,
                db_path=db_path
            )
            
        return {
            "reconciled": reconciled,
            "reconstructed_position": calculated_internal,
            "drift": drift
        }
