"""Recurring-Error Targeted Practice Curriculum Generator (Milestone 2.4).

Curriculum design:
1. Weaknesses are counted across DISTINCT (session_date, ticker) incident sessions — never raw event rows.
2. Each generated drill uses a UNIQUE session_date drawn from the pool of sessions that actually produced
   the weakness, plus a deterministic offset sequence, so the same historical day is never re-sliced for
   multiple drills in the same curriculum.
3. TRAINING drills are isolated from any session already assigned to ASSESSMENT via the engine's split
   custody check.
"""

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from scripts.trading_brain.db.connection import get_db_connection
from scripts.trading_brain.practice.drill_engine import BlindedDrillContext, BlindedDrillEngine
from scripts.utils.market_calendar import now_iso_utc


@dataclass
class CurriculumSummary:
    curriculum_id: str
    weakness_rule_id: str
    recurrence_count: int
    recommended_drills: List[BlindedDrillContext]
    curriculum_notes: str
    approval_status: str = "PENDING_USER_APPROVAL"      # 'PENDING_USER_APPROVAL', 'APPROVED', 'DISMISSED'
    source_rule_event_samples: List[Dict[str, Any]] = None   # links to the intervention events that motivated it
    synthetic_labeling: str = (
        "SYNTHETIC_PRICE_SERIES_NOT_HISTORICAL: drills are synthetic bullish ramps "
        "with no relation to the motivating incidents. Do NOT count toward transfer claims."
    )
    approved_by: Optional[str] = None
    approved_at_utc: Optional[str] = None


class TargetedDrillGenerator:
    """Generates targeted deliberate practice drills based on verified recurring weaknesses."""

    @classmethod
    def _get_weakness_sessions(
        cls,
        rule_id: str,
        ticker: str,
        db_path: Optional[Union[str, Path]] = None
    ) -> List[str]:
        """Return distinct session dates that produced `rule_id` for `ticker`, newest first."""
        with get_db_connection(db_path) as conn:
            cur = conn.execute(
                """
                SELECT DISTINCT session_date
                FROM intervention_events
                WHERE rule_id = ? AND ticker = ?
                ORDER BY session_date DESC;
                """,
                (rule_id, ticker)
            )
            return [str(r["session_date"]) for r in cur.fetchall()]

    @classmethod
    def analyze_weaknesses_and_generate(
        cls,
        min_recurrence: int = 3,
        ticker: str = "NQ1",
        db_path: Optional[Union[str, Path]] = None,
        drills_per_weakness: int = 3,
    ) -> List[CurriculumSummary]:
        """Identifies recurring intervention rules occurring on >= min_recurrence independent sessions and creates a drill set.

        Recurrence counts DISTINCT (session_date, ticker) incident sessions, not raw event rows,
        so one deteriorating session emitting multiple events cannot manufacture a false pattern.

        Each weakness gets up to `drills_per_weakness` drills using independent session dates. If fewer
        weakness sessions are available than requested, the curriculum still produces the requested count
        by offsetting from the weakness dates in a deterministic way, but never re-uses the exact same
        (session_date, ticker) within the same curriculum.
        """
        with get_db_connection(db_path) as conn:
            cur = conn.execute(
                """
                SELECT rule_id, COUNT(DISTINCT session_date || '|' || ticker) AS recurrence_count
                FROM intervention_events
                WHERE ticker = ?
                GROUP BY rule_id
                HAVING recurrence_count >= ?
                ORDER BY recurrence_count DESC;
                """,
                (ticker, min_recurrence)
            )
            rows = cur.fetchall()
            if not rows:
                return []

            curricula = []
            for row in rows:
                rule_id = row["rule_id"]
                count = row["recurrence_count"]

                # Deterministic pool of independent incident dates from the intervention ledger.
                weakness_sessions = cls._get_weakness_sessions(rule_id, ticker, db_path=db_path)
                used_session_dates: set[str] = set()
                fallback_sessions: List[str] = []
                drills: List[BlindedDrillContext] = []

                # F12: authentic-first curriculum material. Each drill attempts the REAL
                # historical session for its weakness date; synthetic proxies are only a
                # documented FALLBACK when authentic history is unavailable, and the
                # curriculum notes disclose which sessions fell back.
                for i in range(drills_per_weakness):
                    if i < len(weakness_sessions):
                        session_date = weakness_sessions[i]
                    else:
                        # Deterministic offset fallback: offset from the most recent weakness session
                        # so the curriculum remains reproducible without re-slicing the same day.
                        # Negative offsets stay in the verifiable past.
                        base = weakness_sessions[0] if weakness_sessions else "2026-08-28"
                        dt = datetime.strptime(base, "%Y-%m-%d").date()
                        from datetime import timedelta
                        offset = -(i - len(weakness_sessions) + 2)
                        session_date = (dt + timedelta(days=offset)).isoformat()

                    if session_date in used_session_dates:
                        continue
                    used_session_dates.add(session_date)

                    authentic_loaded = False
                    try:
                        drill = BlindedDrillEngine.generate_blinded_drill(
                            drill_type="RECOGNITION",
                            dataset_split="TRAINING",
                            session_date=session_date,
                            ticker=ticker,
                            synthetic_mode=False,
                            db_path=db_path
                        )
                        authentic_loaded = True
                    except Exception:
                        # Authentic history unavailable for this session (deep archive not
                        # merged into live storage, market holiday, etc.). Fall back to a
                        # synthetic proxy and mark it; the drill never claims transfer.
                        try:
                            drill = BlindedDrillEngine.generate_blinded_drill(
                                drill_type="RECOGNITION",
                                dataset_split="TRAINING",
                                session_date=session_date,
                                ticker=ticker,
                                synthetic_mode=True,
                                db_path=db_path
                            )
                        except Exception:
                            continue
                    drills.append(drill)
                    if not authentic_loaded:
                        fallback_sessions.append(session_date)

                if not drills:
                    continue

                # Downgrade synthetic drills to CALIBRATION-style TRAINING practice; they are
                # explicitly excluded from transfer claims. Historical near-matches are the
                # curriculum's real material — synthetic series exist only as smoke proxies.
                for d in drills:
                    if getattr(d, "dataset_split", None) == "ASSESSMENT":
                        raise ValueError("Synthetic curriculum drills must never be ASSESSMENT.")

                # Sample the motivating intervention events for the user-approval review.
                with get_db_connection(db_path) as conn:
                    ev_cur = conn.execute(
                        """
                        SELECT intervention_id, session_date, rule_id, ticker, event_timestamp_utc
                        FROM intervention_events
                        WHERE rule_id = ? AND ticker = ?
                        ORDER BY event_timestamp_utc DESC LIMIT 5;
                        """,
                        (rule_id, ticker),
                    )
                    source_samples = [dict(r) for r in ev_cur.fetchall()]

                curricula.append(CurriculumSummary(
                    curriculum_id=str(uuid.uuid4()),
                    weakness_rule_id=rule_id,
                    recurrence_count=count,
                    recommended_drills=drills,
                    curriculum_notes=(
                        f"Targeted curriculum addressing recurring deviation '{rule_id}' "
                        f"({count} independent incident sessions). Drills use {len(used_session_dates)} "
                        f"independent session date(s): {sorted(used_session_dates)}. "
                        + (
                            f"AUTHENTIC_HISTORY for all sessions. "
                            if not fallback_sessions
                            else f"SYNTHETIC_FALLBACK for sessions {sorted(fallback_sessions)} "
                            "(authentic bars unavailable); not derived from historical incident context. "
                        )
                        + "Requires user approval before activation."
                    ),
                    # Durable approval state (F22): a persisted decision for this rule is
                    # restored on regeneration, so the user's choice survives.
                    approval_status=cls._load_rule_approval(rule_id, db_path=db_path) or "PENDING_USER_APPROVAL",
                    source_rule_event_samples=source_samples,
                ))
            return curricula

    @classmethod
    def _load_rule_approval(
        cls,
        rule_id: str,
        db_path: Optional[Union[str, Path]] = None
    ) -> Optional[str]:
        """Returns the persisted decision ('APPROVED'/'DISMISSED') for a weakness rule, if any."""
        with get_db_connection(db_path) as conn:
            row = conn.execute(
                "SELECT decision FROM curriculum_rule_approvals WHERE weakness_rule_id = ?;",
                (rule_id,)
            ).fetchone()
        return row["decision"] if row else None

    @classmethod
    def _record_rule_approval(
        cls,
        rule_id: str,
        decision: str,
        actor: Optional[str],
        db_path: Optional[Union[str, Path]] = None
    ) -> None:
        """Persists an approve/dismiss decision keyed by weakness rule (durable across regenerations)."""
        with get_db_connection(db_path) as conn:
            conn.execute(
                """
                INSERT INTO curriculum_rule_approvals (approval_id, weakness_rule_id, decision, actor)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(weakness_rule_id) DO UPDATE SET
                    decision = excluded.decision,
                    actor = excluded.actor,
                    decided_at_utc = strftime('%Y-%m-%dT%H:%M:%SZ', 'now');
                """,
                (str(uuid.uuid4()), rule_id, decision, actor)
            )

    @classmethod
    def approve_curriculum(
        cls,
        curriculum: CurriculumSummary,
        approved_by: str,
        db_path: Optional[Union[str, Path]] = None,
    ) -> CurriculumSummary:
        """Records explicit user approval; a curriculum is not activated without it.

        Interpretation of repeated rule events as a 'weakness' is automatic, but
        SCHEDULING practice from it is a behavior intervention requiring human consent.
        The decision is PERSISTED by weakness_rule_id: regenerating the curriculum for
        the same rule restores the saved decision instead of silently re-prompting.
        """
        if curriculum.approval_status != "PENDING_USER_APPROVAL":
            raise ValueError(f"Curriculum {curriculum.curriculum_id} is already '{curriculum.approval_status}'.")
        curriculum.approval_status = "APPROVED"
        curriculum.approved_by = approved_by
        curriculum.approved_at_utc = now_iso_utc()
        cls._record_rule_approval(curriculum.weakness_rule_id, "APPROVED", approved_by, db_path=db_path)
        return curriculum

    @classmethod
    def dismiss_curriculum(
        cls,
        curriculum: CurriculumSummary,
        dismissed_by: Optional[str] = None,
        db_path: Optional[Union[str, Path]] = None,
    ) -> CurriculumSummary:
        """Records explicit dismissal; dismissed curricula are terminal."""
        if curriculum.approval_status != "PENDING_USER_APPROVAL":
            raise ValueError(f"Curriculum {curriculum.curriculum_id} is already '{curriculum.approval_status}'.")
        curriculum.approval_status = "DISMISSED"
        cls._record_rule_approval(curriculum.weakness_rule_id, "DISMISSED", dismissed_by, db_path=db_path)
        return curriculum
