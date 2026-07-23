"""Strategy candidate registry — Phase 3 of the KB DESIGN.md roadmap.

Converts KB setup units (prose descriptions of ICT trading setups from
transcripts/PDFs/charts) into executable :class:`StrategyCandidate` objects
that reference detection functions from :mod:`scripts.knowledge_bridge.detection_catalog`
and strategy classes from :mod:`scripts.trading_framework.strategies.registry`.

Flow
----
1. Query the KB API for setup-type units (``POST /search`` with
   ``knowledge_type="setup"``).
2. For each unit, scan the setup payload text for ICT concept terms.
3. Map each concept to a detection function via
   :func:`~scripts.knowledge_bridge.detection_catalog.resolve_detection`.
4. Generate a :class:`StrategyCandidate` with the mapped detection steps,
   entry/invalidation/target rules, and a backreference to the source unit.
5. Optionally, use an LLM to refine the prose → function mapping when
   concepts are ambiguous.

ADR compliance
--------------
- ADR-017: All referenced detection functions are vectorized.
- ADR-020: Candidates carry ``max_exit_time="16:00 ET"`` by default.
- ADR-021: Candidates are designed to run through ``PropFirmSimulator``.
- ADR-001: All times are ET; storage is UTC epoch.
- ADR-002: Performance metrics as price %, not absolute points.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence

from .detection_catalog import (
    DETECTION_CATALOG,
    DetectionEntry,
    resolve_detection,
    search_concepts,
)


# ── Enums ────────────────────────────────────────────────────────────────────

class CandidateStatus(str, Enum):
    """Lifecycle state of a strategy candidate."""
    DRAFT = "draft"                    # generated but not reviewed
    REVIEWED = "reviewed"              # human/LLM reviewed, ready to test
    BACKTESTING = "backtesting"        # currently in backtest loop
    VALIDATED = "validated"            # backtest passed viability threshold
    REJECTED = "rejected"             # backtest failed or logic invalid
    DEPRECATED = "deprecated"         # superseded by newer version


# ── Dataclasses ──────────────────────────────────────────────────────────────

@dataclass
class DetectionStep:
    """One detection function call in a candidate's setup sequence.

    Attributes
    ----------
    step_order : int
        1-based sequence order.
    concept : str
        ICT concept name from the detection catalog.
    function_ref : str
        ``module.function_name`` of the detection function.
    params : dict
        Parameter overrides (e.g., ``{"session_name": "ny_open"}``).
    role : str
        How this step fits the setup: "regime", "bias", "timing",
        "trigger", "entry", "invalidation", "target".
    notes : str
        Free-text explanation from the KB source.
    """

    step_order: int
    concept: str
    function_ref: str
    params: Dict[str, Any] = field(default_factory=dict)
    role: str = "trigger"
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class StrategyCandidate:
    """An executable strategy candidate derived from KB setup units.

    This is the central data structure of Phase 3. It bridges KB prose
    descriptions to executable detection functions and strategy classes.

    Attributes
    ----------
    candidate_id : str
        Stable hash ID (``kb_candidate_{hash}``).
    name : str
        Human-readable name (from KB setup name or auto-generated).
    source_unit_ids : list[str]
        KB unit IDs this candidate was derived from. Bidirectional link:
        these IDs should be written back to ``KnowledgeMetadata.linked_stat_ids``.
    direction : str
        "long", "short", or "both".
    detection_steps : list[DetectionStep]
        Ordered detection function calls that implement the setup.
    strategy_key : str, optional
        If this candidate maps to an existing strategy in
        ``STRATEGY_FACTORY_REGISTRY``, the registry key.
    entry_rule : str
        Prose entry rule from the KB (preserved for audit).
    invalidation_rule : str
        Prose invalidation rule from the KB.
    target_rule : str
        Prose target logic from the KB.
    management_rule : str
        Prose management rules from the KB.
    max_exit_time : str
        ADR-020: max exit time. Default "16:00 ET".
    session_filter : str, optional
        Killzone/macro window filter (e.g., "ny_open", "london_sb").
    status : CandidateStatus
        Lifecycle state.
    created_at : str
        ISO timestamp of creation.
    epistemic_status : str
        Mirrors KB epistemic status: "unvalidated", "validated", "contradicted".
    backtest_result_id : str, optional
        ID of the backtest result (Phase 4 link).
    metadata : dict
        Extra fields (concepts_found, concepts_missing, extraction_confidence).
    """

    candidate_id: str
    name: str
    source_unit_ids: List[str]
    direction: str = "both"
    detection_steps: List[DetectionStep] = field(default_factory=list)
    strategy_key: Optional[str] = None
    entry_rule: str = ""
    invalidation_rule: str = ""
    target_rule: str = ""
    management_rule: str = ""
    max_exit_time: str = "16:00 ET"
    session_filter: Optional[str] = None
    status: CandidateStatus = CandidateStatus.DRAFT
    created_at: str = ""
    epistemic_status: str = "unvalidated"
    backtest_result_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        d["detection_steps"] = [s.to_dict() for s in self.detection_steps]
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StrategyCandidate":
        steps_data = data.pop("detection_steps", [])
        status_val = data.pop("status", "draft")
        steps = [DetectionStep(**s) for s in steps_data]
        return cls(
            detection_steps=steps,
            status=CandidateStatus(status_val),
            **data,
        )


# ── Role classification ─────────────────────────────────────────────────────

# Maps KB setup payload field names to detection step roles
_FIELD_ROLES: Dict[str, str] = {
    "regime_precondition": "regime",
    "bias_source": "bias",
    "timing_gate": "timing",
    "trigger": "trigger",
    "entry": "entry",
    "invalidation": "invalidation",
    "target_logic": "target",
    "management": "management",
    "stop_philosophy": "invalidation",
}

# Maps session-related concepts to session_filter values
_SESSION_CONCEPTS: Dict[str, str] = {
    "asian": "asian",
    "london_open": "london_open",
    "ny_open": "ny_open",
    "london_close": "london_close",
    "silver bullet": "silver_bullet",
    "silver_bullet": "silver_bullet",
    "killzone": "killzone",
    "macro": "macro",
}

# Maps strategy registry keys to common KB setup patterns
_STRATEGY_PATTERN_MAP: Dict[str, Sequence[str]] = {
    "ict_displacement": ("mss", "bos", "break of structure", "displacement"),
    "ict_liquidity_sweep": ("liquidity sweep", "sweep", "turtle soup"),
    "ict_fvg_rejection": ("fvg rejection", "fvg entry", "fair value gap rejection"),
    "ict_fvg_cisd_rejection": ("fvg cisd", "fvg + cisd", "composite fvg"),
    "ict_ny_session": ("ny session", "new york session", "ny killzone"),
    "ict_asia_volatility": ("judas", "asia range", "asia volatility", "judas swing"),
}


# ── Concept extraction ───────────────────────────────────────────────────────

def _scan_text_for_concepts(text: str) -> List[DetectionEntry]:
    """Scan prose text for ICT concept terms and return matching catalog entries."""
    if not text:
        return []
    text_lower = text.lower()
    found: List[DetectionEntry] = []
    seen_concepts: set[str] = set()
    for entry in DETECTION_CATALOG:
        # Check concept name
        if entry.concept.lower() in text_lower and entry.concept not in seen_concepts:
            found.append(entry)
            seen_concepts.add(entry.concept)
            continue
        # Check aliases
        for alias in entry.aliases:
            if alias.lower() in text_lower and entry.concept not in seen_concepts:
                found.append(entry)
                seen_concepts.add(entry.concept)
                break
    return found


def _classify_role(field_name: str) -> str:
    """Map a KB setup payload field name to a detection step role."""
    return _FIELD_ROLES.get(field_name, "trigger")


def _infer_strategy_key(text_blob: str) -> Optional[str]:
    """Try to match KB prose to an existing strategy registry key."""
    text_lower = text_blob.lower()
    for key, patterns in _STRATEGY_PATTERN_MAP.items():
        if any(p in text_lower for p in patterns):
            return key
    return None


def _infer_session_filter(text_blob: str) -> Optional[str]:
    """Try to extract a session filter from KB prose."""
    text_lower = text_blob.lower()
    for pattern, session_val in _SESSION_CONCEPTS.items():
        if pattern in text_lower:
            return session_val
    return None


def _infer_direction(text_blob: str) -> str:
    """Infer trade direction from KB prose."""
    text_lower = text_blob.lower()
    has_long = any(w in text_lower for w in ("long", "bullish", "buy", "bull"))
    has_short = any(w in text_lower for w in ("short", "bearish", "sell", "bear"))
    if has_long and has_short:
        return "both"
    if has_long:
        return "long"
    if has_short:
        return "short"
    return "both"


# ── Candidate ID generation ──────────────────────────────────────────────────

def _make_candidate_id(source_unit_ids: Sequence[str], name: str) -> str:
    """Generate a stable candidate ID from source unit IDs and name."""
    import hashlib

    raw = "|".join(sorted(source_unit_ids)) + "|" + name
    h = hashlib.md5(raw.encode()).hexdigest()[:12]
    return f"kb_candidate_{h}"


# ── Candidate generator ──────────────────────────────────────────────────────

class CandidateGenerator:
    """Generates :class:`StrategyCandidate` objects from KB setup units.

    Parameters
    ----------
    kb_api_url : str
        Base URL of the KB API (default ``http://127.0.0.1:8900``).
    """

    def __init__(self, kb_api_url: str = "http://127.0.0.1:8900"):
        self.kb_api_url = kb_api_url.rstrip("/")

    # ── KB API interaction ──────────────────────────────────────────────────

    def fetch_setup_units(
        self,
        query: str = "ICT trading setup",
        k: int = 50,
        knowledge_type: str = "setup",
    ) -> List[Dict[str, Any]]:
        """Fetch setup-type KB units via the KB API ``/search`` endpoint.

        Returns raw unit dicts as returned by the API.
        """
        import urllib.request

        body = json.dumps({
            "query": query,
            "k": k,
            "knowledge_type": knowledge_type,
        }).encode()
        req = urllib.request.Request(
            f"{self.kb_api_url}/search",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        # API returns list of unit dicts
        if isinstance(data, dict) and "results" in data:
            return data["results"]
        if isinstance(data, list):
            return data
        return []

    # ── Candidate generation ────────────────────────────────────────────────

    def generate_from_unit(self, unit: Dict[str, Any]) -> Optional[StrategyCandidate]:
        """Generate a :class:`StrategyCandidate` from a single KB setup unit.

        Returns ``None`` if the unit has no setup payload or no concepts found.
        """
        setup = unit.get("setup")
        if setup is None:
            return None

        unit_id = unit.get("unit_id", "")
        name = setup.get("name") or unit.get("summary", "")[:60]

        # Gather all prose fields
        prose_fields = [
            "regime_precondition", "bias_source", "timing_gate",
            "trigger", "entry", "invalidation", "target_logic",
            "management", "stop_philosophy",
        ]
        all_prose = " ".join(
            (setup.get(f) or "") for f in prose_fields
        )
        # Also include summary and concepts
        summary = unit.get("summary", "")
        concepts_raw = unit.get("metadata", {}).get("concepts_raw", [])
        concepts_canonical = unit.get("metadata", {}).get("concepts_canonical", [])
        all_prose += " " + summary + " " + " ".join(concepts_raw + concepts_canonical)

        if not all_prose.strip():
            return None

        # Scan for concepts
        found_entries = _scan_text_for_concepts(all_prose)
        if not found_entries:
            return None

        # Build detection steps from found concepts + field roles
        steps: List[DetectionStep] = []
        step_order = 0
        concepts_found_names: List[str] = []

        for field_name in prose_fields:
            field_text = setup.get(field_name) or ""
            if not field_text:
                continue
            role = _classify_role(field_name)
            field_entries = _scan_text_for_concepts(field_text)
            for entry in field_entries:
                step_order += 1
                params: Dict[str, Any] = {}
                # Auto-fill session_name for session-related concepts
                if entry.function_name == "get_session_data":
                    for alias in entry.aliases:
                        if alias in _SESSION_CONCEPTS:
                            params["session_name"] = alias
                            break
                elif entry.function_name == "get_silver_bullet_data":
                    for alias in entry.aliases:
                        if alias in _SESSION_CONCEPTS:
                            params["bullet_name"] = alias
                            break
                elif entry.function_name == "get_macro_data":
                    for alias in entry.aliases:
                        if alias in _SESSION_CONCEPTS:
                            params["macro_name"] = alias
                            break

                steps.append(DetectionStep(
                    step_order=step_order,
                    concept=entry.concept,
                    function_ref=entry.qualified_name,
                    params=params,
                    role=role,
                    notes=field_text[:200],
                ))
                if entry.concept not in concepts_found_names:
                    concepts_found_names.append(entry.concept)

        # Deduplicate steps by (concept, role) keeping first
        seen: set[tuple[str, str]] = set()
        deduped_steps: List[DetectionStep] = []
        for s in steps:
            key = (s.concept, s.role)
            if key not in seen:
                seen.add(key)
                deduped_steps.append(s)
        # Re-number
        for i, s in enumerate(deduped_steps, 1):
            s.step_order = i

        # Infer metadata
        strategy_key = _infer_strategy_key(all_prose)
        session_filter = _infer_session_filter(all_prose)
        direction = _infer_direction(all_prose)
        candidate_id = _make_candidate_id([unit_id], name)

        # Metadata
        all_concept_names = {e.concept for e in found_entries}
        found_concept_names = set(concepts_found_names)
        concepts_missing = sorted(all_concept_names - found_concept_names)
        extraction_confidence = unit.get("metadata", {}).get("extraction_confidence", 0.0)

        # Handle chart-derived setups with sequence
        sequence = setup.get("sequence")
        sequence_info = {}
        if sequence:
            sequence_info["has_sequence"] = True
            sequence_info["sequence_steps"] = len(sequence)
            sequence_info["reference_levels"] = setup.get("reference_levels", [])
        else:
            sequence_info["has_sequence"] = False

        return StrategyCandidate(
            candidate_id=candidate_id,
            name=name,
            source_unit_ids=[unit_id],
            direction=direction,
            detection_steps=deduped_steps,
            strategy_key=strategy_key,
            entry_rule=setup.get("entry") or "",
            invalidation_rule=setup.get("invalidation") or "",
            target_rule=setup.get("target_logic") or "",
            management_rule=setup.get("management") or "",
            max_exit_time="16:00 ET",
            session_filter=session_filter,
            status=CandidateStatus.DRAFT,
            created_at=datetime.now(timezone.utc).isoformat(),
            epistemic_status=unit.get("metadata", {}).get("epistemic_status", "unvalidated"),
            metadata={
                "concepts_found": concepts_found_names,
                "concepts_missing": concepts_missing,
                "extraction_confidence": extraction_confidence,
                "domains": unit.get("metadata", {}).get("domains", ["ict"]),
                "summary": summary,
                **sequence_info,
            },
        )

    def generate_batch(
        self,
        units: Optional[List[Dict[str, Any]]] = None,
        query: str = "ICT trading setup",
        k: int = 50,
    ) -> List[StrategyCandidate]:
        """Generate candidates from a batch of KB units.

        If ``units`` is ``None``, fetches from the KB API.
        """
        if units is None:
            units = self.fetch_setup_units(query=query, k=k)
        candidates: List[StrategyCandidate] = []
        for unit in units:
            cand = self.generate_from_unit(unit)
            if cand is not None:
                candidates.append(cand)
        return candidates


# ── Convenience function ─────────────────────────────────────────────────────

def generate_candidates(
    kb_api_url: str = "http://127.0.0.1:8900",
    query: str = "ICT trading setup",
    k: int = 50,
) -> List[StrategyCandidate]:
    """One-shot candidate generation from the KB API.

    Parameters
    ----------
    kb_api_url : str
        KB API base URL.
    query : str
        Semantic search query for setup units.
    k : int
        Max units to retrieve.

    Returns
    -------
    list[StrategyCandidate]
        Generated candidates (DRAFT status).
    """
    gen = CandidateGenerator(kb_api_url=kb_api_url)
    return gen.generate_batch(query=query, k=k)