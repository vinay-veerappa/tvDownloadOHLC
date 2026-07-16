# filepath: tests/test_track_mandate.py
"""Unit tests for the narrative trade-plan track-mandate enforcer.

These tests pin the behaviour of `validate_track_mandate()` from
`scripts.libs_py.risk.narrative`. The validator enforces the
per-ticker `mandated_track` computed in Python (briefing_core
`resolve_track()`) against the LLM's `plan_json` output. The full
behaviour matrix is:

  1. Empty `mandated_tracks` → all trades pass through unchanged.
  2. TRACK C mandate → forces noTrade=True on every trade for that
     ticker (hard rule).
  3. TRACK A mandate + logic mentions "fade" → soft warning,
     `track_a_logic_fade` violation tag, trade kept.
  4. TRACK B mandate + logic mentions "breakout"/"join the trend"/
     "trend follow" → soft warning, `track_b_logic_breakout` tag,
     trade kept.
  5. Mandate exists for a different ticker → trade for unmatched
     ticker passes through.
  6. Asset is micro (MNQ, MES) but mandate key is pipeline (NQ, ES)
     → `micro_to_pipeline` bridge works.
  7. Trade with `noTrade=True` already → preserved (no override).
  8. Mandate string doesn't match A/B/C → passes through.
  9. Plan is not a dict → returns empty plan, no errors.
 10. Plan with no `trades` key → returns plan with empty trades.
 11. Soft warnings are collected and returned to the caller.
 12. Plan copy is shallow — input dict is not mutated.
"""
from __future__ import annotations

import pytest

from scripts.libs_py.risk.narrative import (
    KEY_MANDATED_TRACK,
    KEY_NOTRADE,
    KEY_NOTRADE_REASON,
    KEY_TRADES,
    KEY_VIOLATION,
    validate_track_mandate,
)


# ── Fixtures ────────────────────────────────────────────────────────
def _trade(asset: str, *, logic: str = "join the trend", no_trade: bool = False) -> dict:
    """Build a minimal LLM-style trade dict for tests."""
    return {
        "asset": asset,
        "direction": "LONG",
        "logic": logic,
        "entryPrice": 100.0,
        "stopLoss": 99.0,
        "takeProfit": 102.0,
        "contracts": 1,
        "noTrade": no_trade,
    }


_MICRO_TO_PIPELINE: dict[str, str] = {"MNQ": "NQ", "MES": "ES"}


# ── 1. Empty mandated_tracks → no-op ──────────────────────────────
class TestEmptyMandates:
    def test_empty_dict_passes_trade_through(self):
        trade = _trade("MNQ", logic="join the trend")
        plan = {"logic": "trend follow", "trades": [trade]}

        corrected, warnings = validate_track_mandate(plan, {}, _MICRO_TO_PIPELINE)

        assert corrected["logic"] == "trend follow"
        assert len(corrected["trades"]) == 1
        assert corrected["trades"][0]["asset"] == "MNQ"
        assert corrected["trades"][0][KEY_NOTRADE] is False
        assert KEY_VIOLATION not in corrected["trades"][0]
        assert warnings == []

    def test_no_mandate_for_ticker_passes_through(self):
        """Mandate exists for ES but trade is MNQ — passes through."""
        mandates = {"ES": "TRACK A: BREAKOUT/MOMENTUM ..."}
        trade = _trade("MNQ", logic="fade the wall")
        plan = {"trades": [trade]}

        corrected, warnings = validate_track_mandate(plan, mandates, _MICRO_TO_PIPELINE)

        assert corrected["trades"][0][KEY_NOTRADE] is False
        assert warnings == []


# ── 2. TRACK C → hard noTrade ──────────────────────────────────────
class TestTrackCMandate:
    def test_track_c_forces_no_trade(self):
        mandates = {"NQ": "TRACK C: OBSERVATION ONLY — stand aside"}
        trade = _trade("MNQ", logic="fade the wall")
        plan = {"trades": [trade]}

        corrected, warnings = validate_track_mandate(plan, mandates, _MICRO_TO_PIPELINE)

        assert corrected["trades"][0][KEY_NOTRADE] is True
        assert "TRACK C" in corrected["trades"][0][KEY_NOTRADE_REASON]
        assert corrected["trades"][0][KEY_VIOLATION] == "track_c"
        assert len(warnings) == 1
        assert "TRACK C" in warnings[0]
        assert "MNQ" in warnings[0]

    def test_track_c_preserves_existing_no_trade_reason(self):
        """If LLM already explained a no-trade, we keep that reason too."""
        mandates = {"NQ": "TRACK C: OBSERVATION ONLY"}
        trade = _trade(
            "MNQ",
            logic="plan was: trade the breakout",
            no_trade=False,
        )
        # Manually set an existing reason (LLM did not noTrade, just
        # wrote a reason).
        trade[KEY_NOTRADE_REASON] = "tight consolidation"

        corrected, _ = validate_track_mandate(
            {"trades": [trade]}, mandates, _MICRO_TO_PIPELINE,
        )
        reason = corrected["trades"][0][KEY_NOTRADE_REASON]
        assert "TRACK C" in reason
        assert "tight consolidation" in reason

    def test_track_c_does_not_override_existing_no_trade(self):
        """If LLM already set noTrade=True, leave it alone (no double-tag)."""
        mandates = {"NQ": "TRACK C: OBSERVATION ONLY"}
        trade = _trade("MNQ", no_trade=True)
        trade[KEY_NOTRADE_REASON] = "user-flagged: stale levels"

        corrected, _ = validate_track_mandate(
            {"trades": [trade]}, mandates, _MICRO_TO_PIPELINE,
        )
        # noTrade stays True, the reason is preserved verbatim (no
        # TRACK C tag) because the early `continue` skipped this trade.
        assert corrected["trades"][0][KEY_NOTRADE] is True
        assert corrected["trades"][0][KEY_NOTRADE_REASON] == "user-flagged: stale levels"
        assert KEY_VIOLATION not in corrected["trades"][0]

    def test_track_c_affects_only_matched_ticker(self):
        """ES trade passes through; NQ trade forced to noTrade."""
        mandates = {"NQ": "TRACK C: OBSERVATION ONLY"}
        nq_trade = _trade("MNQ", logic="any")
        es_trade = _trade("MES", logic="any")
        plan = {"trades": [nq_trade, es_trade]}

        corrected, _ = validate_track_mandate(plan, mandates, _MICRO_TO_PIPELINE)

        assert corrected["trades"][0][KEY_NOTRADE] is True  # NQ
        assert corrected["trades"][1][KEY_NOTRADE] is False  # ES


# ── 3. TRACK A with "fade" logic → soft warning ────────────────────
class TestTrackAMandate:
    def test_track_a_with_fade_logic_warns_but_keeps_trade(self):
        mandates = {"NQ": "TRACK A: BREAKOUT/MOMENTUM ..."}
        trade = _trade("MNQ", logic="fade the call wall into the close")
        plan = {"trades": [trade]}

        corrected, warnings = validate_track_mandate(plan, mandates, _MICRO_TO_PIPELINE)

        # Trade is NOT forced to noTrade.
        assert corrected["trades"][0][KEY_NOTRADE] is False
        # Tagged with the violation kind.
        assert corrected["trades"][0][KEY_VIOLATION] == "track_a_logic_fade"
        # Soft warning emitted.
        assert len(warnings) == 1
        assert "TRACK A" in warnings[0]
        assert "fade" in warnings[0]

    def test_track_a_with_breakout_logic_passes_through(self):
        """TRACK A with consistent breakout logic is fine."""
        mandates = {"NQ": "TRACK A: BREAKOUT/MOMENTUM ..."}
        trade = _trade("MNQ", logic="breakout above the call wall on volume")
        plan = {"trades": [trade]}

        corrected, warnings = validate_track_mandate(plan, mandates, _MICRO_TO_PIPELINE)

        assert corrected["trades"][0][KEY_NOTRADE] is False
        assert KEY_VIOLATION not in corrected["trades"][0]
        assert warnings == []


# ── 4. TRACK B with breakout logic → soft warning ──────────────────
class TestTrackBMandate:
    def test_track_b_with_breakout_logic_warns_but_keeps_trade(self):
        mandates = {"ES": "TRACK B: PREMIUM/DISCOUNT FADE ..."}
        trade = _trade("MES", logic="join the trend after the breakout")
        plan = {"trades": [trade]}

        corrected, warnings = validate_track_mandate(plan, mandates, _MICRO_TO_PIPELINE)

        assert corrected["trades"][0][KEY_NOTRADE] is False
        assert corrected["trades"][0][KEY_VIOLATION] == "track_b_logic_breakout"
        assert len(warnings) == 1
        assert "TRACK B" in warnings[0]
        assert "breakout" in warnings[0]

    def test_track_b_with_trend_follow_keyword_warns(self):
        mandates = {"ES": "TRACK B: PREMIUM/DISCOUNT FADE ..."}
        trade = _trade("MES", logic="trend follow above VWAP")
        plan = {"trades": [trade]}

        corrected, warnings = validate_track_mandate(plan, mandates, _MICRO_TO_PIPELINE)

        assert corrected["trades"][0][KEY_VIOLATION] == "track_b_logic_breakout"
        assert len(warnings) == 1

    def test_track_b_with_fade_logic_passes_through(self):
        """TRACK B with consistent fade logic is fine."""
        mandates = {"ES": "TRACK B: PREMIUM/DISCOUNT FADE ..."}
        trade = _trade("MES", logic="fade the put wall at discount")
        plan = {"trades": [trade]}

        corrected, warnings = validate_track_mandate(plan, mandates, _MICRO_TO_PIPELINE)

        assert corrected["trades"][0][KEY_NOTRADE] is False
        assert KEY_VIOLATION not in corrected["trades"][0]
        assert warnings == []


# ── 5. Micro-to-pipeline bridge ────────────────────────────────────
class TestMicroToPipelineBridge:
    def test_uppercase_asset_key_uses_micro_to_pipeline(self):
        """Trade asset 'MNQ' (uppercase) maps to pipeline 'NQ'."""
        mandates = {"NQ": "TRACK C: OBSERVATION ONLY"}
        trade = _trade("MNQ")
        plan = {"trades": [trade]}

        corrected, _ = validate_track_mandate(plan, mandates, _MICRO_TO_PIPELINE)

        assert corrected["trades"][0][KEY_NOTRADE] is True

    def test_missing_bridge_entry_passes_through(self):
        """If asset isn't in micro_to_pipeline, fall back to asset-as-pipeline."""
        mandates = {"MNQ": "TRACK C: OBSERVATION ONLY"}  # key is micro, not pipeline
        trade = _trade("MNQ")
        # Bridge only has "MNQ" -> "NQ", not "MNQ" -> "MNQ", so the
        # pipeline lookup key is "NQ" → no match → trade passes through.
        plan = {"trades": [trade]}

        corrected, warnings = validate_track_mandate(plan, mandates, _MICRO_TO_PIPELINE)

        assert corrected["trades"][0][KEY_NOTRADE] is False
        assert warnings == []

    def test_empty_bridge_uses_asset_as_pipeline(self):
        """With no bridge, the asset is treated as the pipeline key."""
        mandates = {"MNQ": "TRACK C: OBSERVATION ONLY"}
        trade = _trade("MNQ")
        plan = {"trades": [trade]}

        corrected, _ = validate_track_mandate(plan, mandates, {})

        # Empty bridge → asset=MNQ, pipeline=MNQ (fallback), matches mandate.
        assert corrected["trades"][0][KEY_NOTRADE] is True


# ── 6. Mandate classification edge cases ───────────────────────────
class TestMandateClassification:
    def test_unknown_mandate_letter_passes_through(self):
        """Mandate string without TRACK A/B/C label → passes through."""
        mandates = {"NQ": "Some unrelated analysis"}
        trade = _trade("MNQ", logic="fade the wall")
        plan = {"trades": [trade]}

        corrected, warnings = validate_track_mandate(plan, mandates, _MICRO_TO_PIPELINE)

        assert corrected["trades"][0][KEY_NOTRADE] is False
        assert KEY_VIOLATION not in corrected["trades"][0]
        assert warnings == []

    def test_empty_mandate_string_passes_through(self):
        mandates = {"NQ": ""}
        trade = _trade("MNQ", logic="fade the wall")
        plan = {"trades": [trade]}

        corrected, _ = validate_track_mandate(plan, mandates, _MICRO_TO_PIPELINE)

        assert corrected["trades"][0][KEY_NOTRADE] is False

    def test_observation_only_keyword_classified_as_c(self):
        """Mandate with 'OBSERVATION ONLY' (no 'TRACK C' prefix) is C."""
        mandates = {"NQ": "OBSERVATION ONLY — no trade"}
        trade = _trade("MNQ", logic="any")
        plan = {"trades": [trade]}

        corrected, _ = validate_track_mandate(plan, mandates, _MICRO_TO_PIPELINE)

        assert corrected["trades"][0][KEY_NOTRADE] is True
        assert corrected["trades"][0][KEY_VIOLATION] == "track_c"


# ── 7. Plan-shape safety ───────────────────────────────────────────
class TestPlanShapeSafety:
    def test_non_dict_plan_returns_empty(self):
        corrected, warnings = validate_track_mandate(
            "not a dict", {"NQ": "TRACK C"}, _MICRO_TO_PIPELINE,
        )
        assert corrected == {"logic": "", "trades": []}
        assert warnings == []

    def test_plan_with_no_trades_key(self):
        plan = {"logic": "trend follow"}  # no "trades"
        corrected, warnings = validate_track_mandate(plan, {}, _MICRO_TO_PIPELINE)
        assert corrected["trades"] == []
        assert warnings == []

    def test_trade_dict_skipped_if_not_dict(self):
        """Non-dict items in `trades` are silently passed through unchanged.

        The mandate validator's job is mandate enforcement — it does
        not police structural shape (that's `validate_trade_plan`'s
        job). A bad entry is preserved verbatim so downstream code
        sees the same data the LLM emitted.
        """
        plan = {"trades": ["not a dict", _trade("MNQ")]}
        corrected, _ = validate_track_mandate(plan, {}, _MICRO_TO_PIPELINE)
        # Both entries are preserved (shallow list copy).
        assert len(corrected["trades"]) == 2
        assert corrected["trades"][0] == "not a dict"
        assert corrected["trades"][1]["asset"] == "MNQ"

    def test_plan_input_top_level_not_mutated(self):
        """Top-level plan dict/list is a fresh shallow copy, but trade
        dicts share references with the input (consistent with
        `validate_trade_plan`).

        This is the intended contract: mandate enforcement mutates
        trade dicts in place (setting `noTrade`, `track_violation`,
        `noTradeReason`). The shallow copy protects the *plan shell*
        so callers can keep their own reference, but per-trade fields
        are part of the corrected output.
        """
        mandates = {"NQ": "TRACK C: OBSERVATION ONLY"}
        trade = _trade("MNQ")
        plan = {"trades": [trade]}

        corrected, _ = validate_track_mandate(plan, mandates, _MICRO_TO_PIPELINE)

        # The corrected plan's trade list is a *new* list (so the
        # caller's list reference is not aliased). This protects
        # against callers appending to their own list and seeing
        # changes in the validator's output.
        assert corrected["trades"] is not plan["trades"]
        # But the trade dicts are shared references — the validator
        # mutates them in place (same as `validate_trade_plan`).
        assert corrected["trades"][0] is plan["trades"][0]
        # The shared trade dict has been updated by the validator.
        assert plan["trades"][0][KEY_NOTRADE] is True
        assert plan["trades"][0][KEY_VIOLATION] == "track_c"


# ── 8. Mixed plan: A, B, C all in one ───────────────────────────────
class TestMixedPlan:
    def test_multi_ticker_mixed_tracks(self):
        """NQ is TRACK C, ES is TRACK A with a fade → both flagged."""
        mandates = {
            "NQ": "TRACK C: OBSERVATION ONLY",
            "ES": "TRACK A: BREAKOUT/MOMENTUM ...",
        }
        nq_trade = _trade("MNQ", logic="any")
        es_trade = _trade("MES", logic="fade the call wall")
        plan = {"trades": [nq_trade, es_trade]}

        corrected, warnings = validate_track_mandate(plan, mandates, _MICRO_TO_PIPELINE)

        # NQ: forced noTrade.
        assert corrected["trades"][0][KEY_NOTRADE] is True
        assert corrected["trades"][0][KEY_VIOLATION] == "track_c"
        # ES: soft warn, kept.
        assert corrected["trades"][1][KEY_NOTRADE] is False
        assert corrected["trades"][1][KEY_VIOLATION] == "track_a_logic_fade"
        # Two warnings total.
        assert len(warnings) == 2

    def test_logic_lower_and_upper_case_both_match(self):
        """The 'fade' check is case-insensitive."""
        mandates = {"NQ": "TRACK A: BREAKOUT/MOMENTUM ..."}
        trade = _trade("MNQ", logic="FADE the breakout — wait, that doesn't work")
        plan = {"trades": [trade]}

        corrected, _ = validate_track_mandate(plan, mandates, _MICRO_TO_PIPELINE)

        # 'FADE' uppercase still matches.
        assert corrected["trades"][0][KEY_VIOLATION] == "track_a_logic_fade"


# ── 9. Constant surface (KEY_MANDATED_TRACK, KEY_VIOLATION) ────────
class TestPublicConstants:
    def test_key_violation_is_track_violation_string(self):
        assert KEY_VIOLATION == "track_violation"

    def test_key_mandated_track_is_string(self):
        """Stable string for downstream consumers (DB tag, alerts)."""
        assert isinstance(KEY_MANDATED_TRACK, str)
        assert KEY_MANDATED_TRACK == "mandated_track"
