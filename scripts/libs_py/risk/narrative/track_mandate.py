"""LLM-output track-mandate enforcer.

`scripts.trader.briefing_core.resolve_track()` computes a *mandated*
execution track (`TRACK A: BREAKOUT/MOMENTUM`, `TRACK B: PREMIUM/DISCOUNT
FADE`, `TRACK C: OBSERVATION ONLY`, …) for each ticker from the GEX
regime + regime-label pair. The mandate is the source of truth — the
LLM narrative is told to follow it (see the daily prompts' RULES
section). This module is the *enforcement* side: if the LLM ignores the
mandate, the trade plan is corrected (or dropped) before it reaches
the Prisma DB.

Why this lives in `scripts.libs_py.risk.narrative`:
  - It's a post-LLM, plan-level check, paired with `validate_trade_plan`.
  - Pure function, no DB or I/O — easy to unit-test.
  - The same Python-side enforcement policy applies to both the
    backtest-time risk manager and the narrative-time validator.

The enforced rules are conservative on purpose:

  - **TRACK C: OBSERVATION ONLY** → every trade for that ticker is
    forced to `noTrade: true` with `noTradeReason` explaining why.
    This is a hard rule: if the GEX regime says "stand aside", no
    LLM override can place a trade.

  - **TRACK A or TRACK B** → emit a soft warning (via `log.warning`)
    if the LLM's per-trade `direction` or `logic` *plainly* contradicts
    the track label, but do not drop the trade. The interpretation of
    "contradiction" is intentionally narrow — only the cases where the
    LLM is clearly ignoring the mandate in plain text.

The check is keyed by the PIPELINE label (NQ, ES) because that's the
slot-name space the rest of the narrative chain uses. The
`plan_json.trades[].asset` field uses the MICRO label (MNQ, MES) —
the function uses a passed-in `micro_to_pipeline` map to bridge.

This is the Python-side companion to the prompt's rule
("`mandated_track` is absolute, do not override"). If the LLM
complies, the validator is a no-op. If it doesn't, the validator
catches it.
"""
from __future__ import annotations

import logging
from typing import Mapping

from .validator import (
    KEY_ASSET,
    KEY_DIRECTION,
    KEY_LOGIC,
    KEY_NOTRADE,
    KEY_NOTRADE_REASON,
    KEY_TRADES,
    DIR_LONG,
    DIR_SHORT,
)

log = logging.getLogger(__name__)


# Public key constants for downstream consumers.
KEY_MANDATED_TRACK: str = "mandated_track"
KEY_VIOLATION: str = "track_violation"  # tag for trades forced to noTrade

# Mandate labels (substring matches against the mandated_track string
# produced by `briefing_core.resolve_track()`).
_TRACK_C: str = "TRACK C"
_TRACK_B: str = "TRACK B"
_TRACK_A: str = "TRACK A"
_OBSERVATION_ONLY: str = "OBSERVATION ONLY"
_TRACK_A_KEYWORDS: tuple[str, ...] = ("breakout", "momentum", "expansion")
_TRACK_B_KEYWORDS: tuple[str, ...] = ("fade", "discount", "premium")


def _classify_track(mandated_track: str) -> str:
    """Return one of 'A' / 'B' / 'C' / 'UNKNOWN' for a mandate string."""
    s = (mandated_track or "").upper()
    if _TRACK_C in s or _OBSERVATION_ONLY in s:
        return "C"
    if _TRACK_A in s:
        return "A"
    if _TRACK_B in s:
        return "B"
    return "UNKNOWN"


def _looks_like_track_a_violation(logic: str, direction: str | None) -> bool:
    """Conservative check: did the LLM say 'fade' in a TRACK A regime?

    TRACK A = breakout/momentum. A plain "fade the wall" logic in this
    track is a hard contradiction. We only flag cases that mention
    'fade' explicitly — anything more interpretive risks false
    positives.
    """
    if not logic:
        return False
    return "fade" in logic.lower()


def _looks_like_track_b_violation(logic: str, direction: str | None) -> bool:
    """Conservative check: did the LLM plan a breakout-style entry in
    a TRACK B (fade) regime? A plain "join the trend" / "breakout"
    mention in the logic is a contradiction."""
    if not logic:
        return False
    text = logic.lower()
    return any(kw in text for kw in ("breakout", "join the trend", "trend follow"))


def validate_track_mandate(
    plan_data: dict,
    mandated_tracks: Mapping[str, str],
    micro_to_pipeline: Mapping[str, str],
) -> tuple[dict, list[str]]:
    """Enforce the per-ticker `mandated_track` against a trade plan.

    Args:
        plan_data: the same `{"logic": ..., "trades": [...]}` shape
            that `validate_trade_plan` accepts. This function mutates
            a copy — the input dict is not modified.
        mandated_tracks: `{pipeline_label: mandated_track_string}`
            (e.g. `{"NQ": "TRACK A: BREAKOUT/MOMENTUM ..."}`). A
            missing key means "no mandate known" — the function
            passes through trades for that ticker.
        micro_to_pipeline: `{micro_label: pipeline_label}` used to
            bridge from `trades[].asset` (micro) to the mandate
            lookup key (pipeline). The narrative chain already has
            `MICRO_TO_NARRATIVE`; the caller must compose the
            pipeline bridge (e.g. `{"MNQ": "NQ", "MES": "ES"}`).

    Returns:
        (corrected_plan, warnings)
            corrected_plan: a new dict with `trades` modified to obey
                the mandate.
            warnings: list of human-readable warning strings, suitable
                for `log.warning` but NOT for Discord output.
    """
    if not isinstance(plan_data, dict):
        return {"logic": "", "trades": []}, []

    # Shallow-copy the plan so we don't mutate the caller's data.
    corrected: dict = {
        "logic": plan_data.get("logic", ""),
        "trades": list(plan_data.get(KEY_TRADES, [])),
    }
    warnings: list[str] = []

    for trade in corrected[KEY_TRADES]:
        if not isinstance(trade, dict):
            continue

        # The LLM might set noTrade=True for legitimate reasons. Honor
        # it (no override) — we only force noTrade=True for hard
        # mandate violations.
        if trade.get(KEY_NOTRADE, False):
            continue

        asset = str(trade.get(KEY_ASSET, "")).upper()
        pipeline = micro_to_pipeline.get(asset, asset)
        mandated_track = mandated_tracks.get(pipeline, "")

        if not mandated_track:
            # No mandate known for this ticker — pass through.
            continue

        track_letter = _classify_track(mandated_track)
        if track_letter == "UNKNOWN":
            continue

        if track_letter == "C":
            # Hard rule: TRACK C = no trades allowed.
            warnings.append(
                f"{asset}: TRACK C mandate ({mandated_track!r}) — "
                f"forcing noTrade=True"
            )
            trade[KEY_NOTRADE] = True
            existing_reason = str(trade.get(KEY_NOTRADE_REASON, "")).strip()
            new_reason = "TRACK C (observation only) — no trade"
            if existing_reason and existing_reason not in new_reason:
                trade[KEY_NOTRADE_REASON] = f"{new_reason} | {existing_reason}"
            else:
                trade[KEY_NOTRADE_REASON] = new_reason
            # Mark the trade for downstream observability.
            trade[KEY_VIOLATION] = "track_c"
            continue

        # Soft warnings: flag obvious contradictions in plain text.
        logic = str(trade.get(KEY_LOGIC, "") or "")
        direction = trade.get(KEY_DIRECTION)

        if track_letter == "A" and _looks_like_track_a_violation(logic, direction):
            warnings.append(
                f"{asset}: TRACK A mandate but logic mentions 'fade' — "
                f"keeping trade (review LLM output): {logic[:80]!r}"
            )
            trade[KEY_VIOLATION] = "track_a_logic_fade"

        elif track_letter == "B" and _looks_like_track_b_violation(logic, direction):
            warnings.append(
                f"{asset}: TRACK B mandate but logic mentions breakout — "
                f"keeping trade (review LLM output): {logic[:80]!r}"
            )
            trade[KEY_VIOLATION] = "track_b_logic_breakout"

    return corrected, warnings
