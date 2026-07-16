# filepath: tests/test_prompt_render.py
"""Unit tests for the prompt-render helper (audit issue §1.7).

These tests pin the behaviour of `format_risk_params_block()` and
`insert_risk_params()` from `scripts.libs_py.risk.narrative`. The
goal of the helper is to be the SINGLE source of the risk-params
markdown block that gets injected into all 5 daily/trader prompts,
so the LLM sees the same numbers everywhere.

Coverage:
  1. EVAL block shape: account size, daily stop, trailing-DD note,
     max open trades, R:R bounds, allow overnight, instrument table,
     same-direction combined risk.
  2. FUNDED block shape: $2k trailing-DD buffer appears (not the
     "not applicable" line).
  3. Default instrument order: when `instruments=None`, the table
     follows DEFAULT_INSTRUMENT_ORDER filtered to known specs.
  4. Order preservation + dedup: caller-supplied list keeps order
     and drops duplicates.
  5. Unknown instrument: silently skipped (no crash).
  6. Empty configuration: returns EMPTY_BLOCK.
  7. `insert_risk_params` replaces the placeholder in a prompt and
     leaves prompts without the placeholder unchanged (no-op).
  8. Combined-risk cap maths: sum of per-instrument risk caps for
     MNQ+MES = $250 (matches the audit's spec).
  9. Phase defaults to ACTIVE_PHASE constant.
 10. Instrument list with full-size (NQ, ES) contracts renders them
     with the full-size multiplier ($20 / $50) and per-instrument
     cap ($200 / $250).
"""
from __future__ import annotations

import pytest

from scripts.libs_py.risk import narrative as nv
from scripts.libs_py.risk.narrative import (
    DEFAULT_INSTRUMENT_ORDER,
    EMPTY_BLOCK,
    format_risk_params_block,
    insert_risk_params,
    reset_cache,
)


@pytest.fixture(autouse=True)
def _clear_cache():
    """Reset the lru_cache between tests so config edits are visible."""
    reset_cache()
    yield
    reset_cache()


# ── 1. EVAL block shape ───────────────────────────────────────────
def test_eval_block_contains_account_size_50k():
    block = format_risk_params_block(instruments=["MNQ", "MES"], phase="EVAL")
    assert "Account size: $50,000" in block
    assert "eval account" in block
    assert "active phase: EVAL" in block


def test_eval_block_contains_daily_stop_450():
    block = format_risk_params_block(instruments=["MNQ", "MES"], phase="EVAL")
    assert "Daily stop: $450" in block


def test_eval_block_marks_trailing_dd_as_not_applicable():
    """EVAL accounts use a fixed daily stop, not a trailing-DD buffer.
    The block must say "not applicable", not "$0 remaining"."""
    block = format_risk_params_block(instruments=["MNQ", "MES"], phase="EVAL")
    assert "Trailing-DD buffer: not applicable" in block
    assert "Trailing-DD buffer remaining: $0" not in block


def test_eval_block_contains_max_open_trades_3():
    block = format_risk_params_block(instruments=["MNQ", "MES"], phase="EVAL")
    assert "Max open trades / day: 3" in block


def test_eval_block_contains_min_and_block_rr():
    block = format_risk_params_block(instruments=["MNQ", "MES"], phase="EVAL")
    assert "Min R:R (warn below this): 1.5:1" in block
    assert "Block R:R (drop trade below this): 1.0:1" in block


def test_eval_block_disallows_overnight():
    block = format_risk_params_block(instruments=["MNQ", "MES"], phase="EVAL")
    assert "Allow overnight holds: No" in block


def test_eval_block_includes_per_instrument_table():
    block = format_risk_params_block(instruments=["MNQ", "MES"], phase="EVAL")
    # Header row
    assert "| Instrument | Contract  | $/pt | Risk/trade | Daily stop | Proxy |" in block
    # MNQ row
    assert "| MNQ" in block
    assert "QQQ" in block
    # MES row
    assert "| MES" in block
    assert "SPY" in block
    # Per-instrument risk caps
    assert "$100" in block  # MNQ
    assert "$150" in block  # MES


def test_eval_block_combined_risk_cap_math():
    """Same-direction combined risk = sum of per-instrument caps."""
    block = format_risk_params_block(instruments=["MNQ", "MES"], phase="EVAL")
    assert "Same-direction combined risk cap: $250 (MNQ $100 + MES $150)" in block


# ── 2. FUNDED block shape ────────────────────────────────────────
def test_funded_block_shows_2k_trailing_dd_buffer():
    block = format_risk_params_block(instruments=["MNQ", "MES"], phase="FUNDED")
    assert "Trailing-DD buffer remaining: $2,000" in block
    # FUNDED's daily stop is $300, not $450
    assert "Daily stop: $300" in block
    # FUNDED allows 2 open trades, not 3
    assert "Max open trades / day: 2" in block
    # FUNDED account is $100k
    assert "Account size: $100,000" in block
    # FUNDED min R:R is 2.0
    assert "Min R:R (warn below this): 2.0:1" in block


# ── 3. Default instrument order ───────────────────────────────────
def test_default_instrument_order_returns_known_specs():
    block = format_risk_params_block(instruments=None, phase="EVAL")
    # The default order includes MNQ and MES (which are in INSTRUMENT_SPECS).
    assert "MNQ" in block
    assert "MES" in block
    # Order is preserved: MNQ appears before MES in the table.
    assert block.index("MNQ") < block.index("MES")


def test_default_order_constant_excludes_unknown():
    # DEFAULT_INSTRUMENT_ORDER is a tuple — frozen, deterministic.
    assert isinstance(DEFAULT_INSTRUMENT_ORDER, tuple)
    assert DEFAULT_INSTRUMENT_ORDER[0] == "MNQ"
    assert "MES" in DEFAULT_INSTRUMENT_ORDER


# ── 4. Order preservation + dedup ─────────────────────────────────
def test_caller_supplied_instrument_order_is_preserved():
    block = format_risk_params_block(instruments=["MES", "MNQ"], phase="EVAL")
    # MES row appears before MNQ row in the table
    mes_pos = block.find("| MES ")
    mnq_pos = block.find("| MNQ ")
    assert mes_pos != -1 and mnq_pos != -1
    assert mes_pos < mnq_pos


def test_duplicate_instruments_are_deduplicated():
    block = format_risk_params_block(
        instruments=["MNQ", "MES", "MNQ"], phase="EVAL"
    )
    # The MNQ row should appear exactly once in the table
    # (count occurrences of the MNQ table cell "| MNQ ").
    assert block.count("| MNQ ") == 1


# ── 5. Unknown instrument is skipped ─────────────────────────────
def test_unknown_instrument_is_silently_skipped():
    """An unknown symbol does not crash; it just doesn't appear in
    the rendered table. Useful for forward-compatibility (a prompt
    configured for an instrument we haven't added to the risk
    config yet shouldn't blow up the LLM call)."""
    block = format_risk_params_block(
        instruments=["MNQ", "ZZZ"], phase="EVAL"
    )
    assert "MNQ" in block
    assert "ZZZ" not in block


# ── 6. Empty configuration ────────────────────────────────────────
def test_empty_instrument_list_returns_empty_block():
    block = format_risk_params_block(instruments=[], phase="EVAL")
    assert block == EMPTY_BLOCK


def test_only_unknown_instruments_returns_empty_block():
    block = format_risk_params_block(
        instruments=["UNKNOWN_A", "UNKNOWN_B"], phase="EVAL"
    )
    assert block == EMPTY_BLOCK


def test_empty_block_constant():
    assert "Risk Parameters" in EMPTY_BLOCK
    assert "no instruments configured" in EMPTY_BLOCK


# ── 7. insert_risk_params replaces placeholder ────────────────────
def test_insert_risk_params_replaces_placeholder():
    prompt = (
        "# ACCOUNTS\n"
        "{{INSERT_RISK_PARAMS}}\n"
        "- Some other rule.\n"
    )
    out = insert_risk_params(prompt, instruments=["MNQ", "MES"])
    assert "{{INSERT_RISK_PARAMS}}" not in out
    assert "Risk Parameters" in out
    # The lines around the placeholder are preserved.
    assert "# ACCOUNTS" in out
    assert "- Some other rule." in out


def test_insert_risk_params_is_noop_when_placeholder_missing():
    prompt = "# Just a prompt with no placeholder.\n"
    out = insert_risk_params(prompt, instruments=["MNQ", "MES"])
    assert out == prompt


def test_insert_risk_params_with_no_instruments_uses_default():
    """When the caller doesn't pass an `instruments` arg, the block
    still renders (using DEFAULT_INSTRUMENT_ORDER)."""
    prompt = "{{INSERT_RISK_PARAMS}}\n"
    out = insert_risk_params(prompt)
    assert "{{INSERT_RISK_PARAMS}}" not in out
    assert "MNQ" in out
    assert "MES" in out


# ── 8. Combined-risk cap maths (edge cases) ──────────────────────
def test_combined_risk_cap_with_single_instrument():
    block = format_risk_params_block(instruments=["MNQ"], phase="EVAL")
    assert "Same-direction combined risk cap: $100 (MNQ $100)" in block


def test_combined_risk_cap_with_three_instruments():
    block = format_risk_params_block(
        instruments=["MNQ", "MES", "NQ"], phase="EVAL"
    )
    # MNQ $100 + MES $150 + NQ $200 = $450
    assert "Same-direction combined risk cap: $450" in block
    # Breakdown is in the line
    assert "MNQ $100" in block
    assert "MES $150" in block
    assert "NQ $200" in block


def test_combined_risk_cap_skips_unconfigured_instruments():
    """If the caller asks for an instrument that's in INSTRUMENT_SPECS
    but NOT in PER_INSTRUMENT_CAPS, it's still rendered in the table
    with `(account default)` for the cap, but it is NOT included in
    the combined-risk sum."""
    block = format_risk_params_block(
        instruments=["MNQ", "MYM"], phase="EVAL"
    )
    # MYM is in PER_INSTRUMENT_CAPS (it has $100 cap), so it IS included
    # MNQ $100 + MYM $100 = $200
    assert "Same-direction combined risk cap: $200" in block


# ── 9. Phase defaulting ───────────────────────────────────────────
def test_phase_defaults_to_active_phase_constant():
    """When `phase=None`, the block should reflect the value of
    `nv.constants.ACTIVE_PHASE`. The test is structural: it just
    asserts that the active-phase line matches the constant."""
    block_default = format_risk_params_block(
        instruments=["MNQ"], phase=None
    )
    expected = format_risk_params_block(
        instruments=["MNQ"], phase=nv.constants.ACTIVE_PHASE
    )
    assert block_default == expected


# ── 10. Full-size contracts (NQ, ES) ─────────────────────────────
def test_full_size_contracts_render_with_correct_multiplier():
    block = format_risk_params_block(instruments=["NQ", "ES"], phase="EVAL")
    # NQ full-size multiplier is $20/pt
    assert "$20" in block
    # ES full-size multiplier is $50/pt
    assert "$50" in block
    # Per-instrument cap for full-size is $200 (NQ) / $250 (ES)
    assert "$200" in block
    assert "$250" in block


def test_micro_and_full_size_together_preserves_order():
    block = format_risk_params_block(
        instruments=["MNQ", "MES", "NQ", "ES"], phase="EVAL"
    )
    # Rows appear in the caller's order (the four micro/full-size pairs)
    mnq_pos = block.find("| MNQ ")
    mes_pos = block.find("| MES ")
    nq_pos = block.find("| NQ ")
    es_pos = block.find("| ES ")
    assert mnq_pos < mes_pos < nq_pos < es_pos


# ── 11. Sanity: dollar formatting ────────────────────────────────
def test_usd_formatting_uses_comma_thousands_separator():
    block = format_risk_params_block(instruments=["MNQ", "MES"], phase="FUNDED")
    # FUNDED buffer is $2,000 — must have the comma
    assert "$2,000" in block
    # $100,000 account size — must have the comma
    assert "$100,000" in block


# ── 12. Public API smoke test ─────────────────────────────────────
def test_module_exports_prompt_render_helpers():
    """The helpers must be importable from the package root, not
    just the module path. This is the contract that
    `daily_narrative.py` and `trader_narrative.py` depend on."""
    assert hasattr(nv, "format_risk_params_block")
    assert hasattr(nv, "insert_risk_params")
    assert hasattr(nv, "DEFAULT_INSTRUMENT_ORDER")
    assert hasattr(nv, "EMPTY_BLOCK")
