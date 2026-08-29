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
    @staticmethod
    def _require_migration_capability() -> None:
        """Capability gate for receipt overrides and historical re-certification.

        The flag TRADING_BRAIN_ALLOW_RECEIPT_OVERRIDE=1 licenses receipt-time
        overrides. It is a MIGRATION-PROCESS capability: with the flag set, any code
        in the process can backdate receipts (override_actor/reason are self-asserted
        strings). Long-running services must therefore REFUSE to start with the flag
        enabled via assert_next_process_is_migration() - the audited strings record
        intent, only the process boundary authorizes it.
        """
        import os
        if os.environ.get("TRADING_BRAIN_ALLOW_RECEIPT_OVERRIDE") != "1":
            raise ValueError(
                "received_at_utc override requires the migration capability "
                "(TRADING_BRAIN_ALLOW_RECEIPT_OVERRIDE=1). Normal application APIs must "
                "not backdate evidence; run migrations through the migration tooling."
            )

    @staticmethod
    def assert_next_process_is_migration() -> None:
        """Startup guard for NORMAL LONG-RUNNING SERVICES (F4): refuses to boot a
        service process when the receipt-override capability flag is enabled - the
        capability must exist only inside short-lived offline migration commands.

        Call this from API/server startup paths; migration entry points do not call it.
        """
        import os
        if os.environ.get("TRADING_BRAIN_ALLOW_RECEIPT_OVERRIDE") == "1":
            raise RuntimeError(
                "SAFETY REFUSAL: TRADING_BRAIN_ALLOW_RECEIPT_OVERRIDE=1 makes receipt "
                "backdating possible for ANY code in this process. Long-running services "
                "must not start with the migration capability enabled - run migrations "
                "in a separate short-lived command/process."
            )

    @classmethod
    def save_plan_snapshot(
        cls,
        plan: PlanContext,
        db_path: Optional[Union[str, Path]] = None,
        *,
        received_at_utc: Optional[Union[str, datetime]] = None,
        override_reason: Optional[str] = None,
        override_actor: Optional[str] = None,
    ) -> str:
        """Persists a plan snapshot.

        Trust boundary: `received_at_utc` is the actual database receipt time by default.
        An override is a capability-gated MIGRATION action: it requires
        (a) override_reason and override_actor, and (b) the migration capability flag
        (env TRADING_BRAIN_ALLOW_RECEIPT_OVERRIDE=1) set by migration tooling. Normal
        application code cannot grant itself this capability. A plan saved through the
        override path gets provenance HISTORICAL_SOURCE_ASSERTED - NOT live ex-ante
        authority - so get_plan_as_of excludes it from compliance evaluation unless a
        separate verification step re-certifies it as EX_ANTE_DECLARED.
        """
        if received_at_utc is not None:
            if not override_reason or not override_actor:
                raise ValueError(
                    "received_at_utc override requires override_reason and override_actor "
                    "(privileged migration path). Unaudited caller-supplied receipt times can "
                    "forge ex-ante provenance."
                )
            cls._require_migration_capability()
        snapshot_id = plan.plan_snapshot_id or str(uuid.uuid4())
        plan_family_id = plan.plan_family_id or str(uuid.uuid4())
        is_receipt_override = received_at_utc is not None

        cal_cutoff = get_session_cutoff_utc(plan.session_date, "08:45:00")
        cal_cutoff_iso = to_iso_utc(cal_cutoff)

        # Ex-ante status is certified exclusively against the CALENDAR cutoff. A caller
        # cutoff later than the calendar one never broadens the boundary (fail-closed):
        # the earlier of the two governs, so a forged late-cutoff plan cannot win ex-ante.
        if plan.preparation_cutoff_utc:
            req_cutoff = parse_iso_utc(plan.preparation_cutoff_utc)
            cutoff_iso = cal_cutoff_iso if req_cutoff > cal_cutoff else to_iso_utc(req_cutoff)
        else:
            cutoff_iso = cal_cutoff_iso

        prov = "EX_ANTE_DECLARED" if plan.provenance_class in ("EX_ANTE", "EX_ANTE_DECLARED") else "POST_HOC_RECONSTRUCTION"

        # Trust boundary: receipt must be on or before the session cutoff for ex-ante;
        # otherwise degrade honestly. Receipt OVERRIDE degrades further: a historical
        # receipt ASSERTED by migration tooling carries HISTORICAL_SOURCE_ASSERTED, which
        # get_plan_as_of does not treat as live ex-ante authority (F10).
        real_recv_iso = to_iso_utc(received_at_utc) if received_at_utc else now_iso_utc()
        if is_receipt_override:
            prov = "HISTORICAL_SOURCE_ASSERTED"
        elif prov == "EX_ANTE_DECLARED" and parse_iso_utc(real_recv_iso) > parse_iso_utc(cutoff_iso):
            prov = "POST_HOC_RECONSTRUCTION"
        recv_iso = real_recv_iso

        with get_db_connection(db_path) as conn:
            # Revision allocation is race-prone (MAX+1 before INSERT). Retry on the
            # UNIQUE(plan_family_id, revision_seq) conflict; concurrent writers each get
            # a bounded recompute instead of a hard failure.
            last_err: Optional[Exception] = None
            for attempt in range(5):
                cur = conn.execute(
                    "SELECT IFNULL(MAX(revision_seq), 0) + 1 AS next_seq FROM plan_snapshots WHERE session_date = ? AND ticker = ?;",
                    (plan.session_date, plan.ticker)
                )
                rev_seq = cur.fetchone()["next_seq"]

                try:
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
                    last_err = None
                    break
                except sqlite3.IntegrityError as exc:
                    last_err = exc
                    snapshot_id = plan.plan_snapshot_id or snapshot_id  # keep id; only revision retries
                    continue
            if last_err is not None:
                raise last_err

            event_id = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO plan_lifecycle_events (
                    event_id, plan_snapshot_id, event_type, recorded_at_utc, reason
                ) VALUES (?, ?, 'SUBMITTED', ?, 'Plan snapshot submission');
                """,
                (event_id, snapshot_id, now_iso_utc())
            )

            if is_receipt_override:
                # Auditable privileged receipt override: records the claimed historical
                # receipt, the actor, and the source/reason so ex-ante claims made through
                # this path are always traceable.
                override_event_id = str(uuid.uuid4())
                conn.execute(
                    """
                    INSERT INTO plan_lifecycle_events (
                        event_id, plan_snapshot_id, event_type, recorded_at_utc, reason
                    ) VALUES (?, ?, 'RECEIPT_OVERRIDE', ?, ?);
                    """,
                    (
                        override_event_id, snapshot_id, now_iso_utc(),
                        f"actor={override_actor}; claimed_receipt={recv_iso}; reason={override_reason}"
                    ),
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
    def verify_historical_snapshot(
        cls,
        plan_snapshot_id: str,
        verifier: str,
        reason: str,
        db_path: Optional[Union[str, Path]] = None,
        verified_effective_from_utc: Optional[Union[str, datetime]] = None,
    ) -> None:
        """Re-certifies a HISTORICAL_SOURCE_ASSERTED snapshot for plan authority.

        Capability-gated like the receipt override: a migration tooling step verifies
        the asserted plan against INDEPENDENT evidence (e.g. exported chart screenshots,
        broker statements, VPS/audit logs). The ledger records the explicit
        HISTORICAL_VERIFIED lifecycle event; without it, asserted snapshots have no
        live-plan authority.

        Temporal semantics (F3): the recorded_at_utc of this event is the moment the
        verification BECAME available, so AS_RECORDED as-of queries only honor the
        verification from that instant forward (no retrospective rewriting). When the
        verification itself establishes that the plan was contemporaneously valid since
        an earlier verified instant (evidenced, not claimed), the migration tool sets
        verified_effective_from_utc - the event's reason must then cite that evidence.
        """
        import os
        if os.environ.get("TRADING_BRAIN_ALLOW_RECEIPT_OVERRIDE") != "1":
            raise ValueError(
                "verify_historical_snapshot requires the migration capability "
                "(TRADING_BRAIN_ALLOW_RECEIPT_OVERRIDE=1)."
            )
        import os
        if os.environ.get("TRADING_BRAIN_ALLOW_RECEIPT_OVERRIDE") != "1":
            raise ValueError(
                "verify_historical_snapshot requires the migration capability "
                "(TRADING_BRAIN_ALLOW_RECEIPT_OVERRIDE=1)."
            )
        if not verifier or not reason:
            raise ValueError("verify_historical_snapshot requires verifier and reason.")
        effective_iso = (
            to_iso_utc(verified_effective_from_utc) if verified_effective_from_utc else None
        )
        with get_db_connection(db_path) as conn:
            row = conn.execute(
                "SELECT provenance_class FROM plan_snapshots WHERE plan_snapshot_id = ?;",
                (plan_snapshot_id,)
            ).fetchone()
            if not row:
                raise ValueError(f"plan snapshot '{plan_snapshot_id}' not found.")
            if row["provenance_class"] != "HISTORICAL_SOURCE_ASSERTED":
                raise ValueError(
                    f"snapshot '{plan_snapshot_id}' is '{row['provenance_class']}'; only "
                    "HISTORICAL_SOURCE_ASSERTED snapshots can be re-certified."
                )
            # plan_snapshots is immutable by trigger; re-certification is therefore
            # granted via the append-only HISTORICAL_VERIFIED lifecycle event, which
            # get_plan_as_of treats as the authority grant (event + verifier recorded).
            conn.execute(
                """
                INSERT INTO plan_lifecycle_events (
                    event_id, plan_snapshot_id, event_type, recorded_at_utc, reason
                ) VALUES (?, ?, 'HISTORICAL_VERIFIED', ?, ?);
                """,
                (str(uuid.uuid4()), plan_snapshot_id, now_iso_utc(),
                 f"Re-certified by {verifier}: {reason}"
                 + (f" (verified effective from {effective_iso})" if effective_iso else ""))
            )
            if effective_iso:
                # The verifier asserts - backed by the evidence named in `reason` -
                # that the verification's substantive validity starts at
                # verified_effective_from_utc. get_plan_as_of accepts either this
                # explicit effective-from OR the event receipt (AS_RECORDED mode).
                conn.execute(
                    """
                    INSERT INTO plan_lifecycle_events (
                        event_id, plan_snapshot_id, event_type, recorded_at_utc, reason
                    ) VALUES (?, ?, 'HISTORICAL_VERIFIED_EFFECTIVE_FROM', ?, ?);
                    """,
                    (str(uuid.uuid4()), plan_snapshot_id, now_iso_utc(),
                     f"VERIFIED_EFFECTIVE_FROM={effective_iso} | by {verifier}: {reason}")
                )

    @classmethod
    def get_plan_as_of(
        cls,
        session_date: str,
        ticker: str,
        as_of_time_utc: Union[str, datetime],
        db_path: Optional[Union[str, Path]] = None,
        knowledge_mode: str = "AS_RECORDED",
    ) -> Optional[PlanContext]:
        """Resolves the effective plan as of a historical instant.

        Authority semantics (F1/F3 of the fifth audit):
        - Provenance eligibility is resolved IN SQL BEFORE ordering/limiting: an
          unverified HISTORICAL_SOURCE_ASSERTED row can never mask an eligible
          EX_ANTE_DECLARED plan, because it is filtered out of the candidate set.
        - HISTORICAL_VERIFIED re-certification has NO retrospective authority: the
          verification event must itself be RECEIVED by the as-of time. Otherwise a
          2026 verification would silently rewrite 2020 query results. The explicit
          escape hatch is knowledge_mode='CURRENTLY_VERIFIED_HISTORY', which is an
          administrative view (clearly named, never the compliance default).
        """
        as_of_iso = to_iso_utc(as_of_time_utc)
        mode = str(knowledge_mode).upper()
        if mode not in ("AS_RECORDED", "CURRENTLY_VERIFIED_HISTORY"):
            raise ValueError("knowledge_mode must be 'AS_RECORDED' or 'CURRENTLY_VERIFIED_HISTORY'.")

        with get_db_connection(db_path) as conn:
            if mode == "AS_RECORDED":
                # Verification must itself be RECEIVED by the as-of time: a 2026
                # re-certification never rewrites a 2020 query result. EXCEPTION: a
                # HISTORICAL_VERIFIED_EFFECTIVE_FROM event records an EVIDENCED
                # earlier validity start; the effective-from instant (parsed from the
                # event reason) grants authority from that verified instant.
                verified_condition = """
                        OR (
                            p.provenance_class = 'HISTORICAL_SOURCE_ASSERTED'
                            AND EXISTS (
                                SELECT 1 FROM plan_lifecycle_events v
                                WHERE v.plan_snapshot_id = p.plan_snapshot_id
                                  AND v.event_type = 'HISTORICAL_VERIFIED'
                                  AND v.recorded_at_utc <= :as_of
                            )
                        )
                        OR (
                            p.provenance_class = 'HISTORICAL_SOURCE_ASSERTED'
                            AND EXISTS (
                                SELECT 1 FROM plan_lifecycle_events v
                                WHERE v.plan_snapshot_id = p.plan_snapshot_id
                                  AND v.event_type = 'HISTORICAL_VERIFIED_EFFECTIVE_FROM'
                                  AND substr(v.reason, instr(v.reason, 'VERIFIED_EFFECTIVE_FROM=') + 25, 20) <= :as_of
                                  AND EXISTS (
                                      SELECT 1 FROM plan_lifecycle_events v2
                                      WHERE v2.plan_snapshot_id = p.plan_snapshot_id
                                        AND v2.event_type = 'HISTORICAL_VERIFIED'
                                  )
                            )
                        )
                """
            else:
                # Administrative view: verification grants authority whenever recorded,
                # explicitly named and never the compliance default (F3 option 2).
                verified_condition = """
                        OR (
                            p.provenance_class = 'HISTORICAL_SOURCE_ASSERTED'
                            AND EXISTS (
                                SELECT 1 FROM plan_lifecycle_events v
                                WHERE v.plan_snapshot_id = p.plan_snapshot_id
                                  AND v.event_type = 'HISTORICAL_VERIFIED'
                            )
                        )
                """
            cur = conn.execute(
                f"""
                SELECT p.* FROM plan_snapshots p
                WHERE p.session_date = :session_date AND p.ticker = :ticker
                  AND p.received_at_utc <= :as_of
                  AND p.preparation_cutoff_utc <= :as_of
                  AND (
                        p.provenance_class IN ('EX_ANTE', 'EX_ANTE_DECLARED')
                        {verified_condition}
                      )
                  AND NOT EXISTS (
                      SELECT 1 FROM plan_lifecycle_events e
                      WHERE e.plan_snapshot_id = p.plan_snapshot_id
                        AND e.event_type IN ('SUPERSEDED', 'CANCELLED')
                        AND e.recorded_at_utc <= :as_of
                  )
                ORDER BY p.revision_seq DESC, p.received_at_utc DESC, p.preparation_cutoff_utc DESC
                LIMIT 1;
                """,
                {"session_date": session_date, "ticker": ticker, "as_of": as_of_iso}
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
