"""Verdict Schema Registry — one schema per analytical perspective.

Each schema defines:
  - verdict_fields:        what the reasoner fills
  - verification_criteria:  what vision/you check each field against
  - correction_format:      the diff shape for corrections
  - action_mapping:         verdict -> posture (NOT entry)
  - open_questions:         unresolved design points
  - iteration_history:      version changelog

Schemas become unit `kind` values in the unified knowledge base.

See: docs/architecture/CHART_AGENT_PLAN.md §5 for the master plan.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class VerdictSchema:
    """A single analytical perspective schema."""

    kind: str
    version: str
    description: str
    verdict_fields: dict[str, str]
    verification_criteria: list[str]
    correction_format: dict[str, str]
    action_mapping: dict[str, str]
    open_questions: list[str] = field(default_factory=list)
    iteration_history: list[str] = field(default_factory=list)

    def to_yaml_skeleton(self) -> str:
        """Return a YAML skeleton the reasoner fills in."""
        lines = []
        for fname, fdesc in self.verdict_fields.items():
            lines.append(f"# {fdesc}")
            lines.append(f"{fname}:")
            lines.append("")
        return "\n".join(lines)

    def to_prompt_block(self) -> str:
        """Return a compact field spec for the LLM prompt."""
        lines = [f"## Schema: {self.kind} v{self.version}", f"{self.description}", ""]
        lines.append("### Fields to fill:")
        for fname, fdesc in self.verdict_fields.items():
            lines.append(f"- **{fname}**: {fdesc}")
        lines.append("")
        lines.append("### Verification criteria (self-check before emitting):")
        for vc in self.verification_criteria:
            lines.append(f"- {vc}")
        lines.append("")
        lines.append("### Action mapping (posture, NOT entry):")
        for situation, action in self.action_mapping.items():
            lines.append(f"- {situation}: {action}")
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════
#  Schema: daily_bias_mtf v0.4 (LOCKED — pending real-chart refinement)
# ═══════════════════════════════════════════════════════════════════════

DAILY_BIAS_MTF = VerdictSchema(
    kind="daily_bias_mtf",
    version="0.5",
    description=(
        "Verdict for 'what is today's directional bias and why', derived from "
        "HTF narrative via PD-array confluence. Frames which side to trade and "
        "where to seek liquidity — NOT an entry schema. Presents BOTH scenarios "
        "(primary bias + alternate) when price is in premium/discount after a sweep."
    ),
    verdict_fields={
        "horizon": "session | swing | positional — dynamic, NOT fixed by instrument",
        "timeframes_used": "configurable list; chosen because arrays are in play (e.g. [Q,M,W,D,1H,15m,5m])",
        "per_tf": "list of per-TF reads (HTF->LTF): target_pd_array, array_state, draw_on_liquidity, market_structure, premium_discount, key_levels (with status), notes",
        "pd_arrays": "confluence map: list of {tf, array, level, state, alignment, role} — multiple arrays held in play. Be specific with levels and status (swept/cleared, reclaimed, unmitigated/protected)",
        "primary_pd_array": "DERIVED — the array price is currently seeking; emerges as price approaches",
        "primary_array_tf": "DERIVED — which TF revealed the primary array",
        "htf_story": "the dominant HTF narrative / draw on liquidity — the 'what'",
        "price_delivery_narrative": "CHRONOLOGICAL price delivery — trace through the session(s) in order. What did Asia do? What did London do? Where is price now? What just happened?",
        "readiness": "ready | not_ready | forming — distinct from bias; 'not_ready' = LTF hasn't confirmed, bias holds",
        "readiness_reason": "why readiness is what it is (e.g. 'LTF hasn't retraced into discount')",
        "bias": "bullish | bearish | neutral | range — your PRIMARY call",
        "dealing_range": "{high, low, equilibrium}",
        "premium_discount_position": "premium | discount | equilibrium — where price sits now",
        "liquidity_pools": "{buy_side: [BSL targets above with status], sell_side: [SSL targets below with status]}",
        "alternate_scenario": "THE VALID COUNTER-NARRATIVE. If bearish, what's the bullish case? If bullish, what's the bearish case? Include specific levels and logic. NOT invalidation — it's the scenario that becomes primary if your call is wrong.",
        "invalidation": "level OR condition that breaks the primary bias — a real HTF break, not LTF noise",
        "rationale": "narrative tying arrays together — why is primary case stronger than alternate? Why are pending arrays timing, not wrong?",
    },
    verification_criteria=[
        "Does bias align with the HTF DOL across the TFs used?",
        "Are dealing_range bounds and equilibrium correct against the data?",
        "Is premium_discount_position correct vs current price?",
        "Do the named liquidity_pools really exist as un-swept raids on the chart?",
        "Is invalidation a real level/condition, or hand-waving?",
        "Does rationale match what's on each TF (the per-TF notes)?",
        "Are pd_arrays states correct (unmitigated/mitigated/swept/fresh)?",
        "Is primary_pd_array actually derived from pd_arrays, not declared up front?",
    ],
    correction_format={
        "field": "the field name",
        "was": "what the reasoner said",
        "should_be": "the correction",
        "reason": "why it's wrong",
    },
    action_mapping={
        "bullish + discount": "long-biased session; seek sell-side liquidity arrays + discount OB/FVG",
        "bearish + premium": "short-biased session; seek buy-side liquidity arrays + premium OB/FVG",
        "neutral / range": "no directional bias; trade range extremes (PDH/PDL reactions), no DOL chase",
        "readiness: not_ready": "bias holds; wait for LTF confirmation (don't flip bias)",
    },
    open_questions=[
        "The 'like me' X% threshold on held-out charts (user sets it)",
        "Probability computation (Phase 3) — likely from historical hit-rates of similar confluence",
        "Whether daily_bias_mtf splits into its own schema doc once entry schemas arrive",
        "Feature gaps discovered during Phase 0a refinement",
    ],
    iteration_history=[
        "v0.1: Fixed TF ladder (M->W->D->1H->15m), single bias label, confidence field",
        "v0.2: Made TF set configurable; introduced PD-array-driven structure",
        "v0.3: Added confluence map (pd_arrays with alignment/role); added readiness separate from bias; KB confirmed 'conflict = not ready, not invalidated'; changed alignment 'contradicting' to 'pending'",
        "v0.4: Removed confidence (probability comes in Phase 3). Made primary_pd_array derived (not declared). horizon/timeframes_used fully dynamic. Multiple arrays held in play simultaneously.",
        "v0.5: Added alternate_scenario (both cases must be presented). Added price_delivery_narrative (chronological session trace). More specific level status (swept/cleared, reclaimed, unmitigated/protected). Prompt now requires naming ICT concepts in context (CISD, MSS, CE, Turtle Soup, Judas Swing).",
    ],
)


# Registry: kind -> schema
REGISTRY: dict[str, VerdictSchema] = {
    "daily_bias_mtf": DAILY_BIAS_MTF,
}


def get_schema(kind: str) -> VerdictSchema:
    """Get a schema by kind name."""
    if kind not in REGISTRY:
        raise KeyError(f"Unknown schema kind: {kind}. Available: {list(REGISTRY.keys())}")
    return REGISTRY[kind]


def list_schemas() -> list[str]:
    """List all registered schema kinds."""
    return list(REGISTRY.keys())