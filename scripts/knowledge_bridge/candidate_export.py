"""Candidate export and bidirectional linking — Phase 3 of the KB DESIGN.md
roadmap.

Exports :class:`StrategyCandidate` objects as JSON and provides bidirectional
linking between candidates and their source KB units.

Bidirectional link
-------------------
- Candidate → Unit: ``candidate.source_unit_ids`` lists the KB unit IDs.
- Unit → Candidate: ``KnowledgeMetadata.linked_stat_ids`` on the KB unit
  should contain the candidate ID. This module provides a helper to compute
  the updates needed; the actual write-back to the KB happens in Phase 4
  (backtest loop) via the KB API or direct DB access.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from .strategy_candidates import StrategyCandidate, CandidateStatus


# ── JSON export ──────────────────────────────────────────────────────────────

def export_candidates_json(
    candidates: Sequence[StrategyCandidate],
    output_path: str | Path,
    indent: int = 2,
) -> Path:
    """Export a list of candidates to a JSON file.

    Parameters
    ----------
    candidates : list[StrategyCandidate]
        Candidates to export.
    output_path : str | Path
        File path for the JSON output.
    indent : int
        JSON indentation level.

    Returns
    -------
    Path
        The resolved output path.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "version": "0.1.0",
        "exported_at": _utc_now_iso(),
        "candidate_count": len(candidates),
        "candidates": [c.to_dict() for c in candidates],
    }
    path.write_text(json.dumps(data, indent=indent, default=str), encoding="utf-8")
    return path


def load_candidates_json(input_path: str | Path) -> List[StrategyCandidate]:
    """Load candidates from a JSON file.

    Parameters
    ----------
    input_path : str | Path
        Path to a previously exported JSON file.

    Returns
    -------
    list[StrategyCandidate]
    """
    path = Path(input_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    candidates_data = data.get("candidates", data if isinstance(data, list) else [])
    return [StrategyCandidate.from_dict(c) for c in candidates_data]


# ── Bidirectional linking ────────────────────────────────────────────────────

def link_candidates_to_units(
    candidates: Sequence[StrategyCandidate],
) -> Dict[str, List[str]]:
    """Compute the unit → candidate_id mapping for bidirectional linking.

    For each candidate, maps every ``source_unit_id`` to the candidate ID.
    This is the data that should be written back to
    ``KnowledgeMetadata.linked_stat_ids`` on each KB unit.

    Parameters
    ----------
    candidates : list[StrategyCandidate]
        Candidates to compute links for.

    Returns
    -------
    dict[str, list[str]]
        Mapping ``{unit_id: [candidate_id, ...]}``. A unit may be the source
        for multiple candidates.
    """
    links: Dict[str, List[str]] = {}
    for cand in candidates:
        for unit_id in cand.source_unit_ids:
            links.setdefault(unit_id, []).append(cand.candidate_id)
    return links


def compute_unit_updates(
    candidates: Sequence[StrategyCandidate],
    existing_linked_stat_ids: Optional[Dict[str, List[str]]] = None,
) -> Dict[str, Dict[str, Any]]:
    """Compute the update payload for KB units to write back linked_stat_ids.

    Parameters
    ----------
    candidates : list[StrategyCandidate]
        Candidates linking to KB units.
    existing_linked_stat_ids : dict, optional
        Existing ``linked_stat_ids`` per unit_id (to merge rather than overwrite).

    Returns
    -------
    dict[str, dict]
        Per-unit update payloads: ``{unit_id: {"linked_stat_ids": [...]}}``.
        Ready to be sent to a KB API update endpoint or written directly.
    """
    new_links = link_candidates_to_units(candidates)
    existing = existing_linked_stat_ids or {}
    updates: Dict[str, Dict[str, Any]] = {}
    for unit_id, candidate_ids in new_links.items():
        existing_ids = set(existing.get(unit_id, []))
        merged = sorted(existing_ids | set(candidate_ids))
        updates[unit_id] = {"linked_stat_ids": merged}
    return updates


# ── Filtering / querying ────────────────────────────────────────────────────

def filter_by_status(
    candidates: Sequence[StrategyCandidate],
    status: CandidateStatus,
) -> List[StrategyCandidate]:
    """Filter candidates by lifecycle status."""
    return [c for c in candidates if c.status == status]


def filter_by_strategy_key(
    candidates: Sequence[StrategyCandidate],
    strategy_key: str,
) -> List[StrategyCandidate]:
    """Filter candidates by strategy registry key."""
    return [c for c in candidates if c.strategy_key == strategy_key]


def filter_by_session(
    candidates: Sequence[StrategyCandidate],
    session_filter: str,
) -> List[StrategyCandidate]:
    """Filter candidates by session filter."""
    return [c for c in candidates if c.session_filter == session_filter]


def summary_stats(candidates: Sequence[StrategyCandidate]) -> Dict[str, Any]:
    """Compute summary statistics for a set of candidates."""
    if not candidates:
        return {"total": 0}
    status_counts: Dict[str, int] = {}
    strategy_key_counts: Dict[str, int] = {}
    session_counts: Dict[str, int] = {}
    direction_counts: Dict[str, int] = {}
    all_concepts: Dict[str, int] = {}

    for c in candidates:
        status_counts[c.status.value] = status_counts.get(c.status.value, 0) + 1
        if c.strategy_key:
            strategy_key_counts[c.strategy_key] = strategy_key_counts.get(c.strategy_key, 0) + 1
        if c.session_filter:
            session_counts[c.session_filter] = session_counts.get(c.session_filter, 0) + 1
        direction_counts[c.direction] = direction_counts.get(c.direction, 0) + 1
        for concept in c.metadata.get("concepts_found", []):
            all_concepts[concept] = all_concepts.get(concept, 0) + 1

    return {
        "total": len(candidates),
        "by_status": status_counts,
        "by_strategy_key": strategy_key_counts,
        "by_session": session_counts,
        "by_direction": direction_counts,
        "top_concepts": dict(
            sorted(all_concepts.items(), key=lambda x: -x[1])[:10]
        ),
    }


# ── Helpers ──────────────────────────────────────────────────────────────────

def _utc_now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()