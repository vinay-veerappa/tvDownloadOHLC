"""Prisma TradePlan -> Canonical plan_snapshots Sync Bridge (Workstream 2.2).

Mirrors TradePlan rows from the Next.js Prisma SQLite database (web/prisma/dev.db) into
the canonical Trading Brain ledger via PlanAdapter. Revision-aware: a TradePlan edit
(updatedAt change or content hash change) creates a new plan snapshot that supersedes
the prior mirrored revision. Idempotent: the same (source_plan_id, source_revision_hash)
maps to a single canonical snapshot.

Field mapping (TradePlan has no explicit bias; everything else is verbatim):
    TradePlan.id             -> source_plan_id
    TradePlan.updatedAt      -> source_revision (hashed with content into source_revision_hash)
    TradePlan.date           -> session_date
    TradePlan.instrument     -> ticker
    TradePlan.setup          -> wargamed_scenarios.setup
    TradePlan.entryPlan      -> verbatim plan text (entry section)
    TradePlan.exitPlan       -> verbatim plan text (exit section)
    TradePlan.riskPlan       -> verbatim plan text + max_intended_risk_bps (parsed bps)

Bias honesty: TradePlan carries no bias field, so the mirrored plan declares
NEUTRAL unless entryPlan text contains an unambiguous directional keyword.
The plan text itself is never altered - interpretation lives in structured fields only.
"""

import hashlib
import json
import logging
import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from scripts.trading_brain.db.connection import REPO_ROOT, get_db_connection
from scripts.trading_brain.plans.plan_adapter import PlanAdapter, PlanContext

log = logging.getLogger(__name__)

DEFAULT_PRISMA_DB = REPO_ROOT / "web" / "prisma" / "dev.db"

# Directional keyword extraction (conservative whole-word; used only for primary_bias tag)
_BULLISH_HINTS = ("long", "buy", "bullish", "higher")
_BEARISH_HINTS = ("short", "sell", "bearish", "lower")


def _detect_bias(*texts: Optional[str]) -> str:
    """Conservative directional inference. NEUTRAL unless exactly one side matches.

    Uses whole-word boundaries so substrings like 'shortlist' or 'buying time' do not
    produce false directional labels.
    """
    import re as _re
    joined = " ".join(t for t in texts if t).lower()
    bull = any(_re.search(r"\b" + _re.escape(h) + r"\b", joined) for h in _BULLISH_HINTS)
    bear = any(_re.search(r"\b" + _re.escape(h) + r"\b", joined) for h in _BEARISH_HINTS)
    if bull and not bear:
        return "BULLISH"
    if bear and not bull:
        return "BEARISH"
    return "NEUTRAL"


def _parse_risk_bps(risk_plan: Optional[str]) -> float:
    """Extracts a bps risk declaration from free-form riskPlan text."""
    if not risk_plan:
        return 15.0
    m = re.search(r"([\d.]+)\s*(?:bps|basis points)", risk_plan.lower())
    if m:
        val = float(m.group(1))
        if 0 < val <= 100:
            return val
    return 15.0


def _content_hash(row: Dict[str, Any]) -> str:
    """Deterministic content hash over the Prisma fields that define a revision."""
    payload = json.dumps({
        "id": row["id"],
        "date": row["date"],
        "instrument": row["instrument"],
        "setup": row.get("setup"),
        "entryPlan": row.get("entryPlan"),
        "exitPlan": row.get("exitPlan"),
        "riskPlan": row.get("riskPlan"),
        "updatedAt": row.get("updatedAt"),
    }, sort_keys=True, default=str)
    return f"sha256:{hashlib.sha256(payload.encode('utf-8')).hexdigest()[:32]}"


def _tradplan_to_plan_context(row: Dict[str, Any], revision_hash: str,
                               supersedes_id: Optional[str] = None) -> PlanContext:
    session_date = str(row["date"]).split("T")[0]
    ticker = row["instrument"]
    entry = row.get("entryPlan") or ""
    exit_p = row.get("exitPlan") or ""
    risk = row.get("riskPlan") or ""
    setup = row.get("setup") or ""

    verbatim_text = (
        f"## Entry Plan\n{entry or '(not specified)'}\n\n"
        f"## Exit Plan\n{exit_p or '(not specified)'}\n\n"
        f"## Risk Plan\n{risk or '(not specified)'}\n\n"
        f"(Mirrored verbatim from Prisma TradePlan {row['id']} rev {revision_hash[:16]} "
        f"on {row.get('updatedAt', 'unknown')})"
    )

    bias = _detect_bias(entry, exit_p)

    # Calendar-derived cutoff (ET wall-clock 08:45 -> UTC, DST-aware). String-interpolated
    # '08:45Z' understates the boundary by 4-5 hours during EDT and misclassifies genuine
    # premarket mirrored plans as post-hoc reconstructions.
    from scripts.utils.market_calendar import get_session_cutoff_utc, to_iso_utc
    prep_cutoff_iso = to_iso_utc(get_session_cutoff_utc(session_date, "08:45:00"))

    return PlanContext(
        session_date=session_date,
        ticker=ticker,
        preparation_cutoff_utc=prep_cutoff_iso,
        verbatim_plan_text=verbatim_text,
        primary_bias=bias,
        wargamed_scenarios={"setup": setup, "source": "PRISMA_TRADEPLAN"},
        invalidation_levels={},
        max_intended_risk_bps=_parse_risk_bps(risk),
        permitted_strategies=[setup] if setup else [],
        source_system="PRISMA_WEB",
        source_plan_id=row["id"],
        source_revision_hash=revision_hash,
        supersedes_plan_snapshot_id=supersedes_id,
    )


def _load_mirrored_state(
    prisma_db_path: Optional[Path],
    canonical_db_path: Optional[Any]
) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    """Returns (all TradePlan rows, mapping source_plan_id -> latest mirrored snapshot metadata)."""
    target = Path(prisma_db_path) if prisma_db_path else DEFAULT_PRISMA_DB
    if not target.exists():
        raise FileNotFoundError(f"Prisma database not found: {target}")

    src = sqlite3.connect(str(target))
    src.row_factory = sqlite3.Row
    try:
        rows = [dict(r) for r in src.execute(
            """
            SELECT id, date, instrument, setup, entryPlan, exitPlan, riskPlan, updatedAt
            FROM TradePlan
            ORDER BY date ASC, id ASC;
            """
        ).fetchall()]
    finally:
        src.close()

    latest_by_source: Dict[str, Dict[str, Any]] = {}
    with get_db_connection(canonical_db_path) as conn:
        mirrored = conn.execute(
            """
            SELECT plan_snapshot_id, source_plan_id, source_revision_hash, revision_seq
            FROM plan_snapshots
            WHERE source_system = 'PRISMA_WEB' AND source_plan_id IS NOT NULL
            ORDER BY revision_seq ASC;
            """
        ).fetchall()
    for r in mirrored:
        latest_by_source[r["source_plan_id"]] = {
            "plan_snapshot_id": r["plan_snapshot_id"],
            "source_revision_hash": r["source_revision_hash"],
            "revision_seq": r["revision_seq"],
        }
    return rows, latest_by_source


def sync_tradplans(
    prisma_db_path: Optional[Path] = None,
    canonical_db_path: Optional[Any] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Mirrors new or changed TradePlan rows into plan_snapshots with supersession.

    Returns a sync report including counts for new mirrors, superseded revisions, and
    unchanged (already-mirrored) revisions.
    """
    rows, latest_by_source = _load_mirrored_state(prisma_db_path, canonical_db_path)
    report: Dict[str, Any] = {
        "found": len(rows),
        "mirrored": 0,
        "superseded": 0,
        "unchanged": 0,
        "skipped": 0,
        "provenance_counts": {},
        "mirrored_ids": [],
    }

    for row in rows:
        revision_hash = _content_hash(row)
        prior = latest_by_source.get(row["id"])
        if prior and prior["source_revision_hash"] == revision_hash:
            report["unchanged"] += 1
            continue

        supersedes_id = prior["plan_snapshot_id"] if prior else None
        ctx = _tradplan_to_plan_context(row, revision_hash, supersedes_id=supersedes_id)
        if dry_run:
            report["mirrored_ids"].append({
                "plan_snapshot_id": None,
                "source_plan_id": row["id"],
                "session_date": ctx.session_date,
                "supersedes_plan_snapshot_id": supersedes_id,
                "dry_run": True,
            })
            if supersedes_id:
                report["superseded"] += 1
            else:
                report["mirrored"] += 1
            continue

        snapshot_id = PlanAdapter.save_plan_snapshot(ctx, db_path=canonical_db_path)
        prov = "EX_ANTE_DECLARED" if ctx.provenance_class in ("EX_ANTE", "EX_ANTE_DECLARED") else "POST_HOC_RECONSTRUCTION"
        report["provenance_counts"][prov] = report["provenance_counts"].get(prov, 0) + 1
        report["mirrored_ids"].append({
            "plan_snapshot_id": snapshot_id,
            "source_plan_id": row["id"],
            "session_date": ctx.session_date,
            "supersedes_plan_snapshot_id": supersedes_id,
        })
        if supersedes_id:
            report["superseded"] += 1
            log.info(f"[WS-2.2] Superseded TradePlan {row['id']} rev {revision_hash[:16]} -> {snapshot_id}")
        else:
            report["mirrored"] += 1
            log.info(f"[WS-2.2] Mirrored TradePlan {row['id']} rev {revision_hash[:16]} -> {snapshot_id} ({prov})")

    log.info(
        f"[WS-2.2] Sync complete: found={report['found']} mirrored={report['mirrored']} "
        f"superseded={report['superseded']} unchanged={report['unchanged']}"
    )
    return report


def main():
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    if hasattr(__import__("sys").stdout, "reconfigure"):
        try:
            __import__("sys").stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    parser = argparse.ArgumentParser(description="Sync Prisma TradePlans into canonical plan_snapshots (WS-2.2)")
    parser.add_argument("--prisma-db", default=None, help="Path to web/prisma/dev.db")
    parser.add_argument("--db", default=None, help="Path to trading_brain.sqlite")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    report = sync_tradplans(
        prisma_db_path=Path(args.prisma_db) if args.prisma_db else None,
        canonical_db_path=args.db,
        dry_run=args.dry_run,
    )
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()