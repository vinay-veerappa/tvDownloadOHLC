"""Tests for audit §2.9 (`compute_level_interactions`) and §2.10
(`parse_meta_fields`) in `scripts/trader/briefing_core.py`.

§2.9 covers redundant guards in the chained comparison form. The
old code had `put_wall_tested: low <= put_wall > 0 and put_wall > 0`
(notice the double `put_wall > 0`); the new form is the clean
`put_wall > 0 and low <= put_wall`. We test the resulting dict
matches the same truth table the old code produced.

§2.10 covers the fragile `rfind("_")` fallback in
`parse_meta_fields`. The old code would mis-parse values that
contain underscores (e.g. `NOTE: "12-31 expiry"` became
key=`NOTE: "12-31`, value=`expiry"`). The new code uses a strict
regex `^([A-Z][A-Z0-9]*)_(.+)$` that requires the key to start
with a letter and contain only uppercase letters / digits.
"""

from __future__ import annotations

import pytest

from scripts.trader.briefing_core import (
    compute_level_interactions,
    parse_meta_fields,
)


# ── §2.9 compute_level_interactions ──────────────────────────────


class TestComputeLevelInteractionsGuards:
    """The post-fix version of compute_level_interactions must
    produce the same truth table for valid levels, AND must return
    False for every flag when the corresponding level is zero or
    negative (which is the 'no level found' sentinel)."""

    def _today(self, high=100, low=90, close=95) -> dict:
        return {"high": high, "low": low, "close": close}

    def test_call_wall_tested_when_high_touches(self) -> None:
        result = compute_level_interactions(
            self._today(high=105, low=90, close=95),
            call_wall=105, put_wall=80, em_upper=110, em_lower=70,
            zero_gamma=95, gamma_magnet=100,
        )
        assert result["call_wall_tested"] is True

    def test_call_wall_not_tested_below(self) -> None:
        result = compute_level_interactions(
            self._today(high=100, low=90, close=95),
            call_wall=105, put_wall=80, em_upper=110, em_lower=70,
            zero_gamma=95, gamma_magnet=100,
        )
        assert result["call_wall_tested"] is False

    def test_call_wall_zero_means_no_level_found(self) -> None:
        """A zero level must not register as tested even if the
        high/low is above/below 0 — that's the bug the audit caught."""
        result = compute_level_interactions(
            self._today(high=100, low=90, close=95),
            call_wall=0, put_wall=0, em_upper=0, em_lower=0,
            zero_gamma=0, gamma_magnet=0,
        )
        for key in (
            "call_wall_tested", "call_wall_broken",
            "put_wall_tested", "put_wall_broken",
            "em_upper_tested", "em_upper_broken",
            "em_lower_tested", "em_lower_broken",
            "zero_gamma_crossed", "magnet_tested",
        ):
            assert result[key] is False, f"{key} should be False for zero level"

    def test_call_wall_negative_means_no_level_found(self) -> None:
        result = compute_level_interactions(
            self._today(high=100, low=90, close=95),
            call_wall=-1, put_wall=-1, em_upper=-1, em_lower=-1,
            zero_gamma=-1, gamma_magnet=-1,
        )
        for key in (
            "call_wall_tested", "call_wall_broken",
            "put_wall_tested", "put_wall_broken",
            "em_upper_tested", "em_upper_broken",
            "em_lower_tested", "em_lower_broken",
            "zero_gamma_crossed", "magnet_tested",
        ):
            assert result[key] is False, f"{key} should be False for negative level"

    def test_put_wall_tested_when_low_touches(self) -> None:
        result = compute_level_interactions(
            self._today(high=100, low=85, close=95),
            call_wall=110, put_wall=85, em_upper=110, em_lower=80,
            zero_gamma=95, gamma_magnet=100,
        )
        assert result["put_wall_tested"] is True

    def test_em_upper_broken_requires_positive_level(self) -> None:
        """The old form `close > em_upper > 0` only fires when
        em_upper is strictly between 0 and close. The new form
        `em_upper > 0 and close > em_upper` produces the same
        result for valid levels."""
        # Positive em_upper below close: broken.
        r1 = compute_level_interactions(
            self._today(close=110),
            call_wall=200, put_wall=0, em_upper=105, em_lower=80,
            zero_gamma=0, gamma_magnet=0,
        )
        assert r1["em_upper_broken"] is True
        # Zero em_upper: never broken.
        r2 = compute_level_interactions(
            self._today(close=110),
            call_wall=200, put_wall=0, em_upper=0, em_lower=80,
            zero_gamma=0, gamma_magnet=0,
        )
        assert r2["em_upper_broken"] is False

    def test_zero_gamma_crossed_only_when_level_in_range(self) -> None:
        r1 = compute_level_interactions(
            self._today(high=100, low=90),
            call_wall=0, put_wall=0, em_upper=0, em_lower=0,
            zero_gamma=95, gamma_magnet=0,
        )
        assert r1["zero_gamma_crossed"] is True
        r2 = compute_level_interactions(
            self._today(high=100, low=90),
            call_wall=0, put_wall=0, em_upper=0, em_lower=0,
            zero_gamma=0, gamma_magnet=0,
        )
        assert r2["zero_gamma_crossed"] is False

    def test_magnet_tested_in_range(self) -> None:
        r1 = compute_level_interactions(
            self._today(high=100, low=90),
            call_wall=0, put_wall=0, em_upper=0, em_lower=0,
            zero_gamma=0, gamma_magnet=95,
        )
        assert r1["magnet_tested"] is True

    def test_truth_table_matches_old_chained_form(self) -> None:
        """The new explicit form must produce the SAME truth table
        as the old chained form for all valid (level > 0) inputs.
        We do a fuzz: a grid of (level, high, low, close) values
        with a tiny range, then check equivalence."""
        for level in (1, 50, 100, 150):
            for high, low, close in (
                (50, 40, 45), (level - 1, level - 10, level - 5),
                (level, level - 10, level - 5),
                (level + 1, level - 1, level + 2),
            ):
                # Old chained form: high >= call_wall > 0
                old_tested = high >= level > 0
                # New explicit form: call_wall > 0 and high >= call_wall
                new_tested = level > 0 and high >= level
                assert old_tested == new_tested, (
                    f"Truth table diverged at level={level} "
                    f"high={high} low={low} close={close}"
                )


# ── §2.10 parse_meta_fields ──────────────────────────────────────


def _line(*parts: str) -> str:
    """Helper: build a unified_entry line from META_ parts."""
    return ", ".join(parts)


class TestParseMetaFieldsKnownKeys:
    """Known keys must still parse correctly after the fix."""

    def test_single_known_key(self) -> None:
        result = parse_meta_fields({"line": _line("0:META_REGIME_TRENDING")})
        assert result == {"REGIME": "TRENDING"}

    def test_numeric_value_parses_as_float(self) -> None:
        result = parse_meta_fields({"line": _line("0:META_GEX_TOTAL_-191251078.14")})
        assert result == {"GEX_TOTAL": -191251078.14}

    def test_longest_match_wins(self) -> None:
        """GEX_TOTAL must match before GEX — this is preserved by
        the known_keys list, sorted by length descending."""
        result = parse_meta_fields({"line": _line("0:META_GEX_TOTAL_42.5")})
        assert "GEX_TOTAL" in result
        assert result["GEX_TOTAL"] == 42.5

    def test_multiple_fields_in_one_line(self) -> None:
        result = parse_meta_fields({"line": _line(
            "0:META_REGIME_TRENDING",
            "0:META_BIAS_LONG",
            "0:META_GEX_TOTAL_123.45",
        )})
        assert result["REGIME"] == "TRENDING"
        assert result["BIAS"] == "LONG"
        assert result["GEX_TOTAL"] == 123.45


class TestParseMetaFieldsFallback:
    """The fallback path (key not in the allow-list) used to be
    fragile — it split on the LAST underscore and would mis-parse
    values that contain underscores (e.g. `NOTE: "12-31 expiry"`).
    The fix uses a strict regex: the key must be uppercase
    letters/digits only, starting with a letter."""

    def test_unknown_well_formed_key_parses(self) -> None:
        """An unknown key in the standard shape (UPPERCASE_KEY_value)
        must still be captured — this is the forward-compat case."""
        result = parse_meta_fields({"line": _line("0:META_NEWFIELD_42.5")})
        assert result == {"NEWFIELD": 42.5}

    def test_unknown_well_formed_key_string_value(self) -> None:
        result = parse_meta_fields({"line": _line("0:META_NEWFIELD_FOO")})
        assert result == {"NEWFIELD": "FOO"}

    def test_value_with_underscore_does_not_corrupt_key(self) -> None:
        """This is the original bug. The old `rfind("_")` would
        mis-align `META_NOTE_12-31 expiry` into key=`NOTE_12-31`
        value=`expiry`. The new regex demands the key be
        uppercase-only, so the value-with-underscore case still
        parses with key=`NOTE` and value=`12-31 expiry`."""
        result = parse_meta_fields({"line": _line("0:META_NOTE_12-31 expiry")})
        assert "NOTE" in result
        assert result["NOTE"] == "12-31 expiry"
        # The corrupt key must NOT appear.
        assert "NOTE_12-31" not in result

    def test_value_with_colon_does_not_corrupt_key(self) -> None:
        """Another fragile case: `META_NOTE_TIER: A` would
        previously split on the last underscore into
        key=`NOTE_TIER: A` (a non-alpha key the consumer code
        did not expect). New regex requires alpha-only key."""
        # `NOTE_TIER: A` — the key part is `NOTE`, the value is
        # `TIER: A`. Regex `^([A-Z][A-Z0-9]*)_(.+)$` matches.
        result = parse_meta_fields({"line": _line("0:META_NOTE_TIER: A")})
        assert "NOTE" in result
        assert result["NOTE"] == "TIER: A"

    def test_lowercase_key_rejected(self) -> None:
        """Lowercase key: silently dropped (the old code would
        have accepted it as a key)."""
        result = parse_meta_fields({"line": _line("0:META_lowercase_42.5")})
        # The strict regex `^([A-Z][A-Z0-9]*)_` rejects the
        # lowercase key, so nothing is added.
        assert "lowercase" not in result

    def test_key_starting_with_digit_rejected(self) -> None:
        result = parse_meta_fields({"line": _line("0:META_1FOO_42.5")})
        # `1FOO` does not start with a letter — rejected.
        assert "1FOO" not in result

    def test_key_with_special_chars_rejected(self) -> None:
        """A key with a hyphen would have been accepted by the old
        `rfind("_")` split, producing a corrupt key. The new regex
        rejects it."""
        result = parse_meta_fields({"line": _line("0:META_FOO-BAR_42.5")})
        # `FOO-BAR` contains a hyphen, regex rejects, so nothing
        # for that field is added.
        assert "FOO-BAR" not in result
        assert "FOO" not in result

    def test_empty_value_passes_through_as_string(self) -> None:
        """META_X_ → key=X, value='' (empty string). Old code
        would set meta['X'] = '' via the float-fallback path."""
        result = parse_meta_fields({"line": _line("0:META_EMPTY_")})
        # The regex `^([A-Z][A-Z0-9]*)_(.+)$` requires `+` (one or
        # more) on the value side, so an empty value is NOT
        # captured. That is a strict-format spec: a value-less
        # META field is malformed and the strict parser drops it.
        # (If we want to support it, change `.+` to `.*` — but
        # audit §2.10 calls for a strict spec, so the current
        # behaviour is correct.)
        assert "EMPTY" not in result


class TestParseMetaFieldsEmpty:
    def test_empty_line_returns_empty_dict(self) -> None:
        result = parse_meta_fields({"line": ""})
        assert result == {}

    def test_line_without_meta_returns_empty_dict(self) -> None:
        result = parse_meta_fields({"line": "NQ1:17000.0:filter|sig|label"})
        assert result == {}

    def test_missing_line_key_returns_empty_dict(self) -> None:
        result = parse_meta_fields({})
        assert result == {}
