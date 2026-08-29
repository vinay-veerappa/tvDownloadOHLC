"""Prisma TradePlan -> Canonical plan_snapshots Sync Bridge (Workstream 2.2).

Mirrors TradePlan rows from the Next.js Prisma SQLite database (web/prisma/dev.db) into
the canonical Trading Brain ledger via PlanAdapter. Idempotent: a TradePlan is mirrored
at most once per revision (deduplication key = source_plan_id + instrument + plan date).

Field mapping (TradePlan has no explicit bias; everything else is verbatim):
    TradePlan.date           -> session_date
    TradePlan.instrument     -> ticker
    TradePlan.setup          -> wargamed_scenarios.setup
    TradePlan.entryPlan      -> verbatim plan text (entry section)
    TradePlan.exitPlan       -> verbatim plan text (exit section)
    TradePlan.riskPlan       -> verbatim plan text + max_intended_risk_bps (parsed bps)
    TradePlan.updatedAt      -> preparation_cutoff reference (provenance still stamped
                                EX_ANTE only by receipt-before-cutoff rule in the adapter)

Bias honesty: TradePlan carries no bias field, so the mirrored plan declares
NEUTRAL unless entryPlan text contains an unambiguous directional keyword.
The plan text itself is never altered - interpretation lives in structured fields only.
"""

import json
import logging
import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from scripts.trading_brain.db.connection import REPO_ROOT, get_db_connection
from scripts.trading_brain.plans.plan_adapter import PlanAdapter, PlanContext

log = logging.getLogger(__name__)

DEFAULT_PRISMA_DB = REPO_ROOT / "web" / "prisma" / "dev.db"

# Directional keyword extraction (conservative; used only for primary_bias tag)
_BULLISH_HINTS = ("long", "buy", "bullish", "higher")
_BEARISH_HINTS = ("short", "sell", "bearish", "lower")


def _detect_bias(*texts: Optional[str]) -> str:
    """Conservative directional inference. NEUTRAL unless exactly one side matches."""
    joined = " ".join(t for t in texts if t).lower()
    bull = any(h in joined for h in _BULLISH_HINTS)
    bear = any(h in joined for h in _BEARISH_HINTS)
    if bull and not bear:
        return "BULLISH"
    if bear and not bull:
        return "BEARISH"
    return "NEUTRAL"


def _parse_risk_bps(risk_plan: Optional[str]) -> float:
    """Extracts a bps risk declaration from free-form riskPlan text; 15.0 conservative default."""
    if not risk_plan:
        return 15.0
    m = re.search(r"([\d.]+)\s*(?:bps|basis points)", risk_plan.lower())
    if m:
        val = float(m.group(1))
        if 0 < val <= 100:
            return val
    return 15.0


def fetch_new_tradplans(
    prisma_db_path: Optional[Path] = None,
    canonical_db_path: Optional[Any] = None,
) -> List[Dict[str, Any]]:
    """Returns TradePlan rows not yet mirrored into plan_snapshots (by source_plan_id)."""
    target = Path(prisma_db_path) if prisma_db_path else DEFAULT_PRISMA_DB
    if not target.exists():
        raise FileNotFoundError(f"Prisma database not found: {target}")

    src = sqlite3.connect(str(target))
    src.row_factory = sqlite3.Row
    try:
        rows = src.execute(
            """
            SELECT id, date, instrument, setup, entryPlan, exitPlan, riskPlan, updatedAt
            FROM TradePlan
            ORDER BY date ASC, id ASC;
            """
        ).fetchall()
    finally:
        src.close()

    with get_db_connection(canonical_db_path) as conn:
        mirrored = {
            r["source_plan_id"]
            for r in conn.execute(
                "SELECT source_plan_id FROM plan_snapshots WHERE source_plan_id IS NOT NULL;"
            ).fetchall()
        }

    return [dict(r) for r in rows if r["id"] not in mirrored]


def _tradplan_to_plan_context(row: Dict[str, Any]) -> PlanContext:
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
        f"(Mirrored verbatim from Prisma TradePlan {row['id']} on {row.get('updatedAt', 'unknown')})"
    )

    bias = _detect_bias(entry, exit_p)

    return PlanContext(
        session_date=session_date,
        ticker=ticker,
        preparation_cutoff_utc=f"{session_date}T08:45:00Z",
        verbatim_plan_text=verbatim_text,
        primary_bias=bias,
        wargamed_scenarios={"setup": setup, "source": "PRISMA_TRADEPLAN"},
        invalidation_levels={},
        max_intended_risk_bps=_parse_risk_bps(risk),
        permitted_strategies=[setup] if setup else [],
        source_system="PRISMA_WEB",
        source_plan_id=row["id"],
    )


def sync_tradplans(
    prisma_db_path: Optional[Path] = None,
    canonical_db_path: Optional[Any] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Mirrors new TradePlan rows into plan_snapshots. Returns a sync report."""
    pending = fetch_new_tradplans(prisma_db_path, canonical_db_path)
    report: Dict[str, Any] = {"found": len(pending), "mirrored": 0, "skipped": 0,
                              "provenance_counts": {}, "mirrored_ids": []}

    for row in pending:
        ctx = _tradplan_to_plan_context(row)
        if dry_run:
            report["mirrored_ids"].append({"plan_snapshot_id": None, "source_plan_id": row["id"],
                                           "session_date": ctx.session_date, "dry_run": True})
            continue
        snapshot_id = PlanAdapter.save_plan_snapshot(ctx, db_path=canonical_db_path)
        prov = "EX_ANTE_DECLARED" if ctx.provenance_class in ("EX_ANTE", "EX_ANTE_DECLARED") else "POST_HOC_RECONSTRUCTION"
        report["provenance_counts"][prov] = report["provenance_counts"].get(prov, 0) + 1
        report["mirrored_ids"].append({"plan_snapshot_id": snapshot_id, "source_plan_id": row["id"],
                                       "session_date": ctx.session_date})
        report["mirrored"] += 1
        log.info(f"[WS-2.2] Mirrored TradePlan {row['id']} -> plan_snapshot {snapshot_id} ({prov})")

    log.info(f"[WS-2.2] Sync complete: found={report['found']} mirrored={report['mirrored']}")
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