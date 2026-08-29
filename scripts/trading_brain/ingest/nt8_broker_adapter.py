"""Hardened NT8 Broker Ingestion & Durable State Reconciliation Adapter (Milestone 0.6).

Provides:
1. Lossless execution fill ingestion with persistent cursor tracking in broker_ingest_state.
2. Lossless RiskGuard intervention & lockout logging in intervention_events.
3. Position reconstruction and drift reconciliation against broker positions.
4. Idempotent deduplication on (account_id, broker_execution_id) and (producer, account_id, idempotency_key).
"""

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from scripts.trading_brain.db.connection import REPO_ROOT, get_db_connection, resolve_db_path
from scripts.utils.market_calendar import now_iso_utc, parse_iso_utc, to_iso_utc


@dataclass
class ExecutionPayload:
    session_date: str
    ticker: str
    account_id: str
    broker_execution_id: str
    broker_order_id: str
    order_action: str                          # 'BUY', 'SELL', 'SELL_SHORT'
    order_type: str                            # 'MARKET', 'LIMIT', 'STOP_MARKET'
    quantity: int
    fill_price: float
    event_timestamp_utc: str
    client_order_id: Optional[str] = None
    commission_usd: float = 0.0
    slippage_bps: Optional[float] = None
    strategy_version_id: Optional[str] = None
    idempotency_key: Optional[str] = None


@dataclass
class InterventionPayload:
    session_date: str
    ticker: str
    account_id: str
    producer: str                              # 'NT8_RISKGUARD_CS', 'PYTHON_DEVIATION_ANNOTATOR', 'MANUAL'
    producer_version: str
    authority_class: str                       # 'HARD_LOCKOUT_ENFORCED', 'SOFT_FRICTION_PROMPTED', 'OBSERVED_DEVIATION_ANNOTATION'
    action_mode: str                           # 'ACTING', 'SHADOW'
    rule_id: str
    rule_version: str
    enforced: bool
    event_timestamp_utc: str
    idempotency_key: Optional[str] = None
    trade_id: Optional[str] = None
    client_order_id: Optional[str] = None
    broker_order_id: Optional[str] = None
    source_event_id: Optional[str] = None
    corrects_intervention_id: Optional[str] = None
    plan_snapshot_id: Optional[str] = None
    plan_amendment_id: Optional[str] = None
    strategy_version_id: Optional[str] = None
    guard_config_hash: Optional[str] = None
    observed_value: Optional[float] = None
    threshold_value: Optional[float] = None
    override_requested: bool = False
    override_accepted: bool = False
    override_actor: Optional[str] = None
    override_acknowledged_at_utc: Optional[str] = None


class NT8BrokerAdapter:
    """Service class for ingesting broker executions, risk interventions, and reconciling state."""

    @staticmethod
    def ingest_fills(
        fills: List[Dict[str, Any]],
        account_id: str,
        endpoint_name: str = "nt_fill_events",
        db_path: Optional[Union[str, Path]] = None
    ) -> Dict[str, Any]:
        """Ingests execution fills with cursor persistence and idempotency."""
        ingested = 0
        skipped = 0
        last_cursor = None
        last_timestamp = None
        
        with get_db_connection(db_path) as conn:
            for f in fills:
                exec_id = str(uuid.uuid4())
                b_exec_id = str(f["broker_execution_id"])
                s_date = f.get("session_date") or datetime.now(timezone.utc).strftime("%Y-%m-%d")
                ticker = f.get("ticker", "NQ1")
                b_order_id = str(f.get("broker_order_id", "b-ord-unknown"))
                client_order_id = f.get("client_order_id")
                action = f.get("order_action", "BUY").upper()
                order_type = f.get("order_type", "MARKET").upper()
                qty = int(f.get("quantity", 1))
                fill_price = float(f.get("fill_price", 0.0))
                comm = float(f.get("commission_usd", 0.0))
                slippage = float(f["slippage_bps"]) if "slippage_bps" in f and f["slippage_bps"] is not None else None
                strat_id = f.get("strategy_version_id")
                event_ts_iso = to_iso_utc(f.get("event_timestamp_utc") or now_iso_utc())
                idemp_key = f.get("idempotency_key") or f"{account_id}_{b_exec_id}"
                cursor_val = str(f.get("cursor", b_exec_id))
                
                # Check if already ingested
                cur = conn.execute(
                    "SELECT execution_id FROM execution_events WHERE account_id = ? AND broker_execution_id = ?;",
                    (account_id, b_exec_id)
                )
                if cur.fetchone():
                    skipped += 1
                else:
                    conn.execute(
                        """
                        INSERT INTO execution_events (
                            execution_id, session_date, ticker, account_id, broker_execution_id,
                            broker_order_id, client_order_id, order_action, order_type,
                            quantity, fill_price, commission_usd, slippage_bps,
                            strategy_version_id, idempotency_key, event_timestamp_utc
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                        """,
                        (
                            exec_id, s_date, ticker, account_id, b_exec_id,
                            b_order_id, client_order_id, action, order_type,
                            qty, fill_price, comm, slippage,
                            strat_id, idemp_key, event_ts_iso
                        )
                    )
                    ingested += 1
                    
                last_cursor = cursor_val
                last_timestamp = event_ts_iso
                
            # Update broker ingest state checkpoint
            if last_cursor and last_timestamp:
                conn.execute(
                    """
                    INSERT INTO broker_ingest_state (endpoint_name, account_id, last_cursor, last_event_timestamp_utc)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(endpoint_name, account_id) DO UPDATE SET
                        last_cursor = excluded.last_cursor,
                        last_event_timestamp_utc = excluded.last_event_timestamp_utc,
                        updated_at_utc = (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'));
                    """,
                    (endpoint_name, account_id, last_cursor, last_timestamp)
                )
                
        return {
            "account_id": account_id,
            "endpoint_name": endpoint_name,
            "ingested_count": ingested,
            "skipped_count": skipped,
            "last_cursor": last_cursor
        }

    @staticmethod
    def ingest_interventions(
        interventions: List[Dict[str, Any]],
        db_path: Optional[Union[str, Path]] = None
    ) -> Dict[str, Any]:
        """Ingests RiskGuard lockouts, soft friction prompts, and rule interventions."""
        ingested = 0
        skipped = 0
        
        with get_db_connection(db_path) as conn:
            for inv in interventions:
                int_id = str(uuid.uuid4())
                s_date = inv.get("session_date") or datetime.now(timezone.utc).strftime("%Y-%m-%d")
                ticker = inv.get("ticker", "NQ1")
                acc_id = inv.get("account_id", "PRIMARY")
                producer = inv.get("producer", "NT8_RISKGUARD_CS")
                version = inv.get("producer_version", "1.0.0")
                auth_class = inv.get("authority_class", "HARD_LOCKOUT_ENFORCED")
                action_mode = inv.get("action_mode", "ACTING")
                rule_id = inv.get("rule_id", "DAILY_MAX_LOSS")
                rule_version = inv.get("rule_version", "1.0.0")
                enforced = 1 if inv.get("enforced", True) else 0
                event_ts_iso = to_iso_utc(inv.get("event_timestamp_utc") or now_iso_utc())
                idemp_key = inv.get("idempotency_key") or str(uuid.uuid4())
                
                # Check for duplicate idempotency key
                cur = conn.execute(
                    "SELECT intervention_id FROM intervention_events WHERE producer = ? AND account_id = ? AND idempotency_key = ?;",
                    (producer, acc_id, idemp_key)
                )
                if cur.fetchone():
                    skipped += 1
                    continue
                    
                conn.execute(
                    """
                    INSERT INTO intervention_events (
                        intervention_id, session_date, ticker, account_id, trade_id,
                        client_order_id, broker_order_id, source_event_id, corrects_intervention_id,
                        plan_snapshot_id, plan_amendment_id, strategy_version_id, guard_config_hash,
                        producer, producer_version, authority_class, action_mode, rule_id,
                        rule_version, observed_value, threshold_value, enforced,
                        override_requested, override_accepted, override_actor,
                        override_acknowledged_at_utc, idempotency_key, event_timestamp_utc
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        int_id, s_date, ticker, acc_id, inv.get("trade_id"),
                        inv.get("client_order_id"), inv.get("broker_order_id"), inv.get("source_event_id"),
                        inv.get("corrects_intervention_id"), inv.get("plan_snapshot_id"), inv.get("plan_amendment_id"),
                        inv.get("strategy_version_id"), inv.get("guard_config_hash"),
                        producer, version, auth_class, action_mode, rule_id,
                        rule_version, inv.get("observed_value"), inv.get("threshold_value"), enforced,
                        1 if inv.get("override_requested") else 0,
                        1 if inv.get("override_accepted") else 0,
                        inv.get("override_actor"),
                        to_iso_utc(inv["override_acknowledged_at_utc"]) if inv.get("override_acknowledged_at_utc") else None,
                        idemp_key, event_ts_iso
                    )
                )
                ingested += 1
                
        return {
            "ingested_count": ingested,
            "skipped_count": skipped
        }

    @staticmethod
    def get_last_cursor(
        endpoint_name: str,
        account_id: str,
        db_path: Optional[Union[str, Path]] = None
    ) -> Optional[str]:
        """Retrieves the last cursor position for an endpoint and account."""
        with get_db_connection(db_path) as conn:
            cur = conn.execute(
                "SELECT last_cursor FROM broker_ingest_state WHERE endpoint_name = ? AND account_id = ?;",
                (endpoint_name, account_id)
            )
            row = cur.fetchone()
            return row["last_cursor"] if row else None

    @staticmethod
    def reconcile_positions(
        account_id: str,
        broker_position: int,
        session_date: Optional[str] = None,
        db_path: Optional[Union[str, Path]] = None
    ) -> Dict[str, Any]:
        """Reconstructs net position from execution fills and reconciles against broker position."""
        s_date = session_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
        with get_db_connection(db_path) as conn:
            cur = conn.execute(
                "SELECT order_action, quantity FROM execution_events WHERE account_id = ? AND session_date = ?;",
                (account_id, s_date)
            )
            rows = cur.fetchall()
            
            reconstructed_net = 0
            total_buys = 0
            total_sells = 0
            
            for r in rows:
                action = r["order_action"].upper()
                qty = r["quantity"]
                if action in ("BUY", "LONG"):
                    reconstructed_net += qty
                    total_buys += qty
                elif action in ("SELL", "SELL_SHORT", "SHORT"):
                    reconstructed_net -= qty
                    total_sells += qty
                    
            drift = broker_position - reconstructed_net
            reconciled = (drift == 0)
            
            return {
                "account_id": account_id,
                "session_date": s_date,
                "broker_position": broker_position,
                "reconstructed_position": reconstructed_net,
                "total_buys": total_buys,
                "total_sells": total_sells,
                "drift": drift,
                "reconciled": reconciled
            }
