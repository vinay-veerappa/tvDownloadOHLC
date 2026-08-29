"""Pre-Market Plan Snapshot, Revision & Deterministic As-Of Authority Adapter.

Implements:
1. Immutable plan snapshot recording with transactional revision sequencing.
2. Append-only lifecycle event tracking (SUBMITTED, SUPERSEDED, CANCELLED).
3. Intraday plan amendments with sequence uniqueness and received_at_utc audit.
4. Deterministic as-of authority resolution (`get_plan_as_of`).
5. Prisma TradePlan snapshot adapter.
"""

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from scripts.trading_brain.db.connection import get_db_connection


@dataclass
class PlanAmendment:
    amendment_id: str
    plan_snapshot_id: str
    amendment_seq: int
    effective_at_utc: str
    received_at_utc: str
    reason_code: str
    amendment_text: str
    amended_bias: Optional[str] = None
    amended_risk_bps: Optional[float] = None
    supersedes_amendment_id: Optional[str] = None


@dataclass
class PlanContext:
    session_date: str
    ticker: str
    preparation_cutoff_utc: str
    verbatim_plan_text: str
    primary_bias: str
    wargamed_scenarios: Dict[str, Any]
    invalidation_levels: Dict[str, Any]
    max_intended_risk_bps: float
    permitted_strategies: List[str]
    source_system: str = "PRISMA_WEB"
    source_plan_id: Optional[str] = None
    plan_snapshot_id: Optional[str] = None
    plan_family_id: Optional[str] = None
    revision_seq: int = 1
    supersedes_plan_snapshot_id: Optional[str] = None
    provenance_class: str = "EX_ANTE_DECLARED"
    received_at_utc: Optional[str] = None
    created_at_utc: Optional[str] = None
    amendments: List[PlanAmendment] = field(default_factory=list)


def parse_iso_utc(dt_val: Union[str, datetime]) -> datetime:
    """Normalizes string or datetime into UTC datetime object."""
    if isinstance(dt_val, str):
        # Handle 'Z' suffix
        cleaned = dt_val.replace("Z", "+00:00")
        dt = datetime.fromisoformat(cleaned)
    else:
        dt = dt_val
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class PlanAdapter:
    """Service class for managing immutable plan snapshots and resolving as-of authority."""

    @staticmethod
    def save_plan_snapshot(
        plan: PlanContext,
        db_path: Optional[Union[str, Path]] = None
    ) -> PlanContext:
        """Saves a plan snapshot and records its SUBMITTED/SUPERSEDED lifecycle events.
        
        Evaluates receipt timing: If received after cutoff, tags as POST_HOC_RECONSTRUCTION.
        """
        snapshot_id = plan.plan_snapshot_id or str(uuid.uuid4())
        family_id = plan.plan_family_id or str(uuid.uuid4())
        
        cutoff_dt = parse_iso_utc(plan.preparation_cutoff_utc)
        now_dt = datetime.now(timezone.utc)
        
        # Enforce provenance classification based on server clock
        provenance = "EX_ANTE_DECLARED" if now_dt <= cutoff_dt else "POST_HOC_RECONSTRUCTION"
        
        with get_db_connection(db_path) as conn:
            # Transactionally determine revision_seq within plan_family_id
            cursor = conn.execute(
                "SELECT IFNULL(MAX(revision_seq), 0) + 1 AS next_seq FROM plan_snapshots WHERE plan_family_id = ?;",
                (family_id,)
            )
            next_seq = cursor.fetchone()["next_seq"]
            
            # Insert immutable snapshot (omitting received_at_utc and created_at_utc so SQLite CURRENT_TIMESTAMP applies)
            conn.execute(
                """
                INSERT INTO plan_snapshots (
                    plan_snapshot_id, plan_family_id, revision_seq, session_date, ticker,
                    preparation_cutoff_utc, source_system, source_plan_id, supersedes_plan_snapshot_id,
                    verbatim_plan_text, primary_bias, wargamed_scenarios_json, invalidation_levels_json,
                    max_intended_risk_bps, permitted_strategies_json, provenance_class
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    snapshot_id,
                    family_id,
                    next_seq,
                    plan.session_date,
                    plan.ticker,
                    cutoff_dt.isoformat(),
                    plan.source_system,
                    plan.source_plan_id,
                    plan.supersedes_plan_snapshot_id,
                    plan.verbatim_plan_text,
                    plan.primary_bias,
                    json.dumps(plan.wargamed_scenarios),
                    json.dumps(plan.invalidation_levels),
                    plan.max_intended_risk_bps,
                    json.dumps(plan.permitted_strategies),
                    provenance
                )
            )
            
            # Fetch the server-generated received_at_utc
            cur = conn.execute("SELECT received_at_utc, created_at_utc FROM plan_snapshots WHERE plan_snapshot_id = ?;", (snapshot_id,))
            row = cur.fetchone()
            received_at = row["received_at_utc"]
            created_at = row["created_at_utc"]
            
            # Record SUBMITTED event
            conn.execute(
                """
                INSERT INTO plan_lifecycle_events (event_id, plan_snapshot_id, event_type, reason)
                VALUES (?, ?, 'SUBMITTED', ?);
                """,
                (str(uuid.uuid4()), snapshot_id, f"Revision {next_seq} declared")
            )
            
            # If this replaces an earlier snapshot, record SUPERSEDED on the old snapshot
            if plan.supersedes_plan_snapshot_id:
                conn.execute(
                    """
                    INSERT INTO plan_lifecycle_events (event_id, plan_snapshot_id, event_type, reason)
                    VALUES (?, ?, 'SUPERSEDED', ?);
                    """,
                    (str(uuid.uuid4()), plan.supersedes_plan_snapshot_id, f"Superseded by {snapshot_id}")
                )
                
        plan.plan_snapshot_id = snapshot_id
        plan.plan_family_id = family_id
        plan.revision_seq = next_seq
        plan.provenance_class = provenance
        plan.received_at_utc = received_at
        plan.created_at_utc = created_at
        return plan

    @staticmethod
    def cancel_plan(
        plan_snapshot_id: str,
        reason: str,
        db_path: Optional[Union[str, Path]] = None
    ) -> None:
        """Appends a CANCELLED event to plan_lifecycle_events."""
        with get_db_connection(db_path) as conn:
            conn.execute(
                """
                INSERT INTO plan_lifecycle_events (event_id, plan_snapshot_id, event_type, reason)
                VALUES (?, ?, 'CANCELLED', ?);
                """,
                (str(uuid.uuid4()), plan_snapshot_id, reason)
            )

    @staticmethod
    def amend_plan(
        plan_snapshot_id: str,
        amendment_text: str,
        reason_code: str,
        effective_at_utc: Union[str, datetime],
        amended_bias: Optional[str] = None,
        amended_risk_bps: Optional[float] = None,
        supersedes_amendment_id: Optional[str] = None,
        db_path: Optional[Union[str, Path]] = None
    ) -> PlanAmendment:
        """Appends an intraday amendment to plan_amendments."""
        effective_dt = parse_iso_utc(effective_at_utc)
        amendment_id = str(uuid.uuid4())
        
        with get_db_connection(db_path) as conn:
            cursor = conn.execute(
                "SELECT IFNULL(MAX(amendment_seq), 0) + 1 AS next_seq FROM plan_amendments WHERE plan_snapshot_id = ?;",
                (plan_snapshot_id,)
            )
            next_seq = cursor.fetchone()["next_seq"]
            
            conn.execute(
                """
                INSERT INTO plan_amendments (
                    amendment_id, plan_snapshot_id, supersedes_amendment_id, amendment_seq,
                    effective_at_utc, reason_code, amendment_text, amended_bias, amended_risk_bps
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    amendment_id,
                    plan_snapshot_id,
                    supersedes_amendment_id,
                    next_seq,
                    effective_dt.isoformat(),
                    reason_code,
                    amendment_text,
                    amended_bias,
                    amended_risk_bps
                )
            )
            
            cur = conn.execute("SELECT received_at_utc FROM plan_amendments WHERE amendment_id = ?;", (amendment_id,))
            received_at = cur.fetchone()["received_at_utc"]
            
        return PlanAmendment(
            amendment_id=amendment_id,
            plan_snapshot_id=plan_snapshot_id,
            amendment_seq=next_seq,
            effective_at_utc=effective_dt.isoformat(),
            received_at_utc=received_at,
            reason_code=reason_code,
            amendment_text=amendment_text,
            amended_bias=amended_bias,
            amended_risk_bps=amended_risk_bps,
            supersedes_amendment_id=supersedes_amendment_id
        )

    @staticmethod
    def get_plan_as_of(
        session_date: str,
        ticker: str,
        decision_time_utc: Union[str, datetime],
        db_path: Optional[Union[str, Path]] = None
    ) -> Optional[PlanContext]:
        """Deterministically resolves the authoritative plan as of a historical decision time.
        
        Invariants:
        1. Only considers snapshots with received_at_utc <= decision_time_utc AND provenance_class = 'EX_ANTE_DECLARED'.
        2. Filters out snapshots where a CANCELLED or SUPERSEDED event was recorded by decision_time_utc.
        3. Filters out snapshots referenced as supersedes_plan_snapshot_id in newer eligible snapshots.
        4. Resolves highest priority by (received_at_utc DESC, revision_seq DESC).
        5. Attaches valid amendments where received_at_utc <= decision_time_utc AND effective_at_utc <= decision_time_utc.
        """
        decision_dt = parse_iso_utc(decision_time_utc)
        decision_iso = decision_dt.isoformat()
        
        with get_db_connection(db_path) as conn:
            # Query eligible ex-ante snapshots
            query = """
            SELECT p.*
            FROM plan_snapshots p
            WHERE p.session_date = ?
              AND p.ticker = ?
              AND p.provenance_class = 'EX_ANTE_DECLARED'
              AND p.received_at_utc <= ?
              AND NOT EXISTS (
                  SELECT 1 FROM plan_lifecycle_events e
                  WHERE e.plan_snapshot_id = p.plan_snapshot_id
                    AND e.event_type IN ('CANCELLED', 'SUPERSEDED')
                    AND e.recorded_at_utc <= ?
              )
              AND NOT EXISTS (
                  SELECT 1 FROM plan_snapshots p2
                  WHERE p2.supersedes_plan_snapshot_id = p.plan_snapshot_id
                    AND p2.provenance_class = 'EX_ANTE_DECLARED'
                    AND p2.received_at_utc <= ?
              )
            ORDER BY p.received_at_utc DESC, p.revision_seq DESC
            LIMIT 1;
            """
            cursor = conn.execute(query, (session_date, ticker, decision_iso, decision_iso, decision_iso))
            row = cursor.fetchone()
            
            if not row:
                return None
                
            snapshot_id = row["plan_snapshot_id"]
            
            # Query amendments active as of decision_time
            amend_cursor = conn.execute(
                """
                SELECT * FROM plan_amendments
                WHERE plan_snapshot_id = ?
                  AND received_at_utc <= ?
                  AND effective_at_utc <= ?
                ORDER BY amendment_seq ASC;
                """,
                (snapshot_id, decision_iso, decision_iso)
            )
            amendments = [
                PlanAmendment(
                    amendment_id=a["amendment_id"],
                    plan_snapshot_id=a["plan_snapshot_id"],
                    amendment_seq=a["amendment_seq"],
                    effective_at_utc=a["effective_at_utc"],
                    received_at_utc=a["received_at_utc"],
                    reason_code=a["reason_code"],
                    amendment_text=a["amendment_text"],
                    amended_bias=a["amended_bias"],
                    amended_risk_bps=a["amended_risk_bps"],
                    supersedes_amendment_id=a["supersedes_amendment_id"]
                )
                for a in amend_cursor.fetchall()
            ]
            
            return PlanContext(
                session_date=row["session_date"],
                ticker=row["ticker"],
                preparation_cutoff_utc=row["preparation_cutoff_utc"],
                verbatim_plan_text=row["verbatim_plan_text"],
                primary_bias=row["primary_bias"],
                wargamed_scenarios=json.loads(row["wargamed_scenarios_json"]),
                invalidation_levels=json.loads(row["invalidation_levels_json"]),
                max_intended_risk_bps=row["max_intended_risk_bps"],
                permitted_strategies=json.loads(row["permitted_strategies_json"]),
                source_system=row["source_system"],
                source_plan_id=row["source_plan_id"],
                plan_snapshot_id=snapshot_id,
                plan_family_id=row["plan_family_id"],
                revision_seq=row["revision_seq"],
                supersedes_plan_snapshot_id=row["supersedes_plan_snapshot_id"],
                provenance_class=row["provenance_class"],
                received_at_utc=row["received_at_utc"],
                created_at_utc=row["created_at_utc"],
                amendments=amendments
            )

    @staticmethod
    def snapshot_prisma_plan(
        prisma_plan: Dict[str, Any],
        preparation_cutoff_utc: Union[str, datetime],
        db_path: Optional[Union[str, Path]] = None
    ) -> PlanContext:
        """Adapts a Prisma TradePlan dictionary into a canonical PlanContext and persists it."""
        cutoff_iso = parse_iso_utc(preparation_cutoff_utc).isoformat()
        
        # Extract fields with sensible defaults if Prisma format varies
        session_date = prisma_plan.get("sessionDate") or prisma_plan.get("date") or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        ticker = prisma_plan.get("symbol") or prisma_plan.get("ticker") or "NQ1"
        plan_text = prisma_plan.get("planText") or prisma_plan.get("content") or "Ex-ante trading plan"
        bias = prisma_plan.get("bias") or "NEUTRAL"
        
        scenarios = prisma_plan.get("scenarios") or {}
        if isinstance(scenarios, str):
            scenarios = json.loads(scenarios)
            
        invalidation = prisma_plan.get("invalidationLevels") or {}
        if isinstance(invalidation, str):
            invalidation = json.loads(invalidation)
            
        max_risk = float(prisma_plan.get("maxRiskBps") or prisma_plan.get("riskBps") or 15.0)
        
        strategies = prisma_plan.get("permittedStrategies") or prisma_plan.get("strategies") or []
        if isinstance(strategies, str):
            strategies = json.loads(strategies)
            
        plan_ctx = PlanContext(
            session_date=session_date,
            ticker=ticker,
            preparation_cutoff_utc=cutoff_iso,
            verbatim_plan_text=plan_text,
            primary_bias=bias,
            wargamed_scenarios=scenarios,
            invalidation_levels=invalidation,
            max_intended_risk_bps=max_risk,
            permitted_strategies=strategies,
            source_system="PRISMA_WEB",
            source_plan_id=str(prisma_plan.get("id")) if prisma_plan.get("id") else None
        )
        
        return PlanAdapter.save_plan_snapshot(plan_ctx, db_path=db_path)
