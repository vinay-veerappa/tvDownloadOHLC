"""Plan Adapter & Authority Resolver (Milestone 0.2)."""

import json
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from scripts.trading_brain.db.connection import get_db_connection
from scripts.utils.market_calendar import (
    get_session_cutoff_utc,
    now_iso_utc,
    parse_iso_utc,
    to_iso_utc,
)


@dataclass
class PlanAmendment:
    amendment_id: str
    plan_snapshot_id: str
    amendment_seq: int
    effective_at_utc: str
    reason_code: str
    amendment_text: str
    amended_bias: Optional[str] = None
    amended_risk_bps: Optional[float] = None
    amended_strategies: Optional[List[str]] = None


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
    plan_snapshot_id: Optional[str] = None
    plan_family_id: Optional[str] = None
    revision_seq: int = 1
    provenance_class: str = "EX_ANTE_DECLARED"
    source_system: str = "MARKDOWN_CLI"
    source_plan_id: Optional[str] = None
    source_revision_hash: Optional[str] = None
    supersedes_plan_snapshot_id: Optional[str] = None
    amendments: List[PlanAmendment] = field(default_factory=list)
    
    effective_primary_bias: str = ""
    effective_max_intended_risk_bps: float = 0.0
    effective_permitted_strategies: List[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.effective_primary_bias:
            self.effective_primary_bias = self.primary_bias
        if self.effective_max_intended_risk_bps == 0.0:
            self.effective_max_intended_risk_bps = self.max_intended_risk_bps
        if not self.effective_permitted_strategies:
            self.effective_permitted_strategies = list(self.permitted_strategies)


class PlanAdapter:
    @classmethod
    def save_plan_snapshot(
        cls,
        plan: PlanContext,
        db_path: Optional[Union[str, Path]] = None,
        *,
        received_at_utc: Optional[Union[str, datetime]] = None,
    ) -> str:
        snapshot_id = plan.plan_snapshot_id or str(uuid.uuid4())
        plan_family_id = plan.plan_family_id or str(uuid.uuid4())
        
        cal_cutoff = get_session_cutoff_utc(plan.session_date, "08:45:00")
        cal_cutoff_iso = to_iso_utc(cal_cutoff)
        
        if plan.preparation_cutoff_utc:
            req_cutoff = parse_iso_utc(plan.preparation_cutoff_utc)
            cutoff_iso = cal_cutoff_iso if req_cutoff > cal_cutoff else to_iso_utc(req_cutoff)
        else:
            cutoff_iso = cal_cutoff_iso
            
        prov = "EX_ANTE_DECLARED" if plan.provenance_class in ("EX_ANTE", "EX_ANTE_DECLARED") else "POST_HOC_RECONSTRUCTION"

        # Trust boundary: received_at_utc must be the actual database receipt time unless an
        # explicit (audited) override is supplied. Ex-ante certification is awarded only if
        # the receipt is on or before the session cutoff; otherwise degrade honestly.
        real_recv_iso = to_iso_utc(received_at_utc) if received_at_utc else now_iso_utc()
        if prov == "EX_ANTE_DECLARED" and parse_iso_utc(real_recv_iso) > parse_iso_utc(cutoff_iso):
            prov = "POST_HOC_RECONSTRUCTION"
        recv_iso = real_recv_iso

        with get_db_connection(db_path) as conn:
            cur = conn.execute(
                "SELECT IFNULL(MAX(revision_seq), 0) + 1 AS next_seq FROM plan_snapshots WHERE session_date = ? AND ticker = ?;",
                (plan.session_date, plan.ticker)
            )
            rev_seq = cur.fetchone()["next_seq"]
            
            conn.execute(
                """
                INSERT INTO plan_snapshots (
                    plan_snapshot_id, plan_family_id, revision_seq, session_date, ticker,
                    preparation_cutoff_utc, source_system, source_plan_id, source_revision_hash,
                    supersedes_plan_snapshot_id, primary_bias, wargamed_scenarios_json, invalidation_levels_json,
                    max_intended_risk_bps, permitted_strategies_json, verbatim_plan_text, provenance_class,
                    received_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    snapshot_id, plan_family_id, rev_seq, plan.session_date, plan.ticker,
                    cutoff_iso, plan.source_system, plan.source_plan_id, plan.source_revision_hash,
                    plan.supersedes_plan_snapshot_id, plan.primary_bias,
                    json.dumps(plan.wargamed_scenarios), json.dumps(plan.invalidation_levels),
                    plan.max_intended_risk_bps, json.dumps(plan.permitted_strategies),
                    plan.verbatim_plan_text, prov, recv_iso
                )
            )
            
            event_id = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO plan_lifecycle_events (
                    event_id, plan_snapshot_id, event_type, recorded_at_utc, reason
                ) VALUES (?, ?, 'SUBMITTED', ?, 'Plan snapshot submission');
                """,
                (event_id, snapshot_id, now_iso_utc())
            )
            
            if plan.supersedes_plan_snapshot_id and prov == "EX_ANTE_DECLARED":
                sup_event_id = str(uuid.uuid4())
                conn.execute(
                    """
                    INSERT INTO plan_lifecycle_events (
                        event_id, plan_snapshot_id, event_type, recorded_at_utc, reason
                    ) VALUES (?, ?, 'SUPERSEDED', ?, 'Superseded by higher revision');
                    """,
                    (sup_event_id, plan.supersedes_plan_snapshot_id, now_iso_utc())
                )
                
        return snapshot_id

    @classmethod
    def get_plan_as_of(
        cls,
        session_date: str,
        ticker: str,
        as_of_time_utc: Union[str, datetime],
        db_path: Optional[Union[str, Path]] = None
    ) -> Optional[PlanContext]:
        as_of_iso = to_iso_utc(as_of_time_utc)
        
        with get_db_connection(db_path) as conn:
            cur = conn.execute(
                """
                SELECT p.* FROM plan_snapshots p
                WHERE p.session_date = ? AND p.ticker = ?
                  AND p.provenance_class IN ('EX_ANTE', 'EX_ANTE_DECLARED')
                  AND p.received_at_utc <= ?
                  AND p.preparation_cutoff_utc <= ?
                  AND NOT EXISTS (
                      SELECT 1 FROM plan_lifecycle_events e
                      WHERE e.plan_snapshot_id = p.plan_snapshot_id
                        AND e.event_type IN ('SUPERSEDED', 'CANCELLED')
                        AND e.recorded_at_utc <= ?
                  )
                ORDER BY p.revision_seq DESC, p.received_at_utc DESC, p.preparation_cutoff_utc DESC
                LIMIT 1;
                """,
                (session_date, ticker, as_of_iso, as_of_iso, as_of_iso)
            )
            row = cur.fetchone()
            if not row:
                return None
                
            snapshot_id = row["plan_snapshot_id"]
            strats = json.loads(row["permitted_strategies_json"]) if row["permitted_strategies_json"] else []
            scenarios = json.loads(row["wargamed_scenarios_json"]) if row["wargamed_scenarios_json"] else {}
            invalidations = json.loads(row["invalidation_levels_json"]) if row["invalidation_levels_json"] else {}
            
            amd_cur = conn.execute(
                """
                SELECT * FROM plan_amendments
                WHERE plan_snapshot_id = ?
                  AND effective_at_utc <= ?
                  AND received_at_utc <= ?
                ORDER BY amendment_seq ASC;
                """,
                (snapshot_id, as_of_iso, as_of_iso)
            )
            amd_rows = amd_cur.fetchall()
            amendments = []
            
            eff_bias = row["primary_bias"]
            eff_risk = row["max_intended_risk_bps"]
            eff_strats = list(strats)
            
            for a in amd_rows:
                amd = PlanAmendment(
                    amendment_id=a["amendment_id"],
                    plan_snapshot_id=a["plan_snapshot_id"],
                    amendment_seq=a["amendment_seq"],
                    effective_at_utc=a["effective_at_utc"],
                    reason_code=a["reason_code"],
                    amendment_text=a["amendment_text"],
                    amended_bias=a["amended_bias"],
                    amended_risk_bps=a["amended_risk_bps"]
                )
                amendments.append(amd)
                if amd.amended_bias:
                    eff_bias = amd.amended_bias
                if amd.amended_risk_bps is not None:
                    eff_risk = amd.amended_risk_bps
                    
            return PlanContext(
                session_date=row["session_date"],
                ticker=row["ticker"],
                preparation_cutoff_utc=row["preparation_cutoff_utc"],
                verbatim_plan_text=row["verbatim_plan_text"],
                primary_bias=row["primary_bias"],
                wargamed_scenarios=scenarios,
                invalidation_levels=invalidations,
                max_intended_risk_bps=row["max_intended_risk_bps"],
                permitted_strategies=strats,
                plan_snapshot_id=snapshot_id,
                plan_family_id=row["plan_family_id"],
                revision_seq=row["revision_seq"],
                provenance_class=row["provenance_class"],
                source_system=row["source_system"],
                source_plan_id=row["source_plan_id"],
                source_revision_hash=row["source_revision_hash"],
                supersedes_plan_snapshot_id=row["supersedes_plan_snapshot_id"],
                amendments=amendments,
                effective_primary_bias=eff_bias,
                effective_max_intended_risk_bps=eff_risk,
                effective_permitted_strategies=eff_strats
            )
