# filepath: tests/test_risk_validator.py
"""Unit tests for the narrative trade-plan validator.

These tests pin the behaviour of `validate_trade_plan()` from
`scripts.libs_py.risk.narrative`. They cover every rule in the
validator's behaviour summary (see `validator.py` docstring):

  1. noTrade=True entries are dropped silently.
  2. Missing asset / unknown instrument / non-numeric prices → drop.
  3. entryPrice <= 0 → drop.
  4. Stop on wrong side of entry → invert (with warning).
  5. Target on wrong side of entry → drop.
  6. contracts > max_for_risk_cap → cap (with warning).
  7. contracts < 1 after cap → drop.
  8. Compute stopDistancePts / dollarRisk / rewardToRisk from Python.
  9. R:R < block_reward_to_risk → drop.
 10. R:R < min_reward_to_risk → warn (kept).
 11. Happy path: correct trade round-trips with computed fields.
 12. Mixed plan: some valid, some dropped, some noTrade.
 13. Non-LONG direction normalisation (lowercase, missing, unknown).
 14. Cache behaviour: reset_cache() works.
"""
from __future__ import annotations

import logging
from typing import Any

import pytest

from scripts.libs_py.risk import narrative as nv
from scripts.libs_py.risk.narrative import (
    AccountPhase,
    DIR_LONG,
    DIR_SHORT,
    InstrumentSpec,
    RiskConfig,
    ValidatorRules,
    get_risk_config,
    reset_cache,
    validate_trade_plan,
)


# ── Fixtures ────────────────────────────────────────────────────────
def _full_config(
    *,
    active_phase: str = "EVAL",
    mnq_cap: float | None = None,
    mes_cap: float | None = None,
    min_rr: float = 1.5,
    block_rr: float = 1.0,
) -> RiskConfig:
    """Build a RiskConfig with a deterministic shape for tests."""
    instruments = {
        "MNQ": InstrumentSpec(
            name="Micro E-mini Nasdaq-100",
            multiplier_dollar_per_pt=2.0,
            tick_size=0.25,
            tick_value_dollar=0.50,
        ),
        "MES": InstrumentSpec(
            name="Micro E-mini S&P 500",
            multiplier_dollar_per_pt=5.0,
            tick_size=0.25,
            tick_value_dollar=1.25,
        ),
        "M2K": InstrumentSpec(
            name="Micro E-mini Russell 2000",
            multiplier_dollar_per_pt=5.0,
            tick_size=0.10,
            tick_value_dollar=0.50,
        ),
    }
    phases = {
        "EVAL": AccountPhase(
            label="EVAL",
            description="eval",
            default_risk_cap_per_trade_usd=150.0,
            daily_stop_usd=450.0,
            total_dd_buffer_usd=0.0,
            max_open_trades=3,
            min_reward_to_risk=min_rr,
            block_reward_to_risk=block_rr,
            allow_overnight=False,
        ),
        "FUNDED": AccountPhase(
            label="FUNDED",
            description="funded",
            default_risk_cap_per_trade_usd=100.0,
            daily_stop_usd=300.0,
            total_dd_buffer_usd=2000.0,
            max_open_trades=2,
            min_reward_to_risk=2.0,
            block_reward_to_risk=1.0,
            allow_overnight=False,
        ),
    }
    per_caps: dict[str, dict] = {}
    if mnq_cap is not None:
        per_caps["MNQ"] = {"risk_cap_per_trade_usd": mnq_cap}
    if mes_cap is not None:
        per_caps["MES"] = {"risk_cap_per_trade_usd": mes_cap}

    rules = ValidatorRules(
        max_price_decimals=2,
        drop_on_unknown_asset=True,
        log_warnings=False,  # don't pollute test output
    )
    return RiskConfig(
        version="0.1.0-test",
        active_phase=active_phase,
        instruments=instruments,
        account_phases=phases,
        per_instrument_caps=per_caps,
        validator_rules=rules,
    )


def _valid_mnq_long(overrides: dict[str, Any] | None = None) -> dict:
    """Default valid MNQ long trade at 17000 with 50-pt stop, 100-pt target."""
    base = {
        "asset": "MNQ",
        "direction": "LONG",
        "entryPrice": 17000.0,
        "stopLoss": 16950.0,        # 50 pt stop → $100 risk
        "takeProfit": 17100.0,      # 100 pt target → 2.0 R:R
        "contracts": 1,
        "regime": "TREND_UP",
    }
    if overrides:
        base.update(overrides)
    return base


def _valid_mes_long(overrides: dict[str, Any] | None = None) -> dict:
    """Default valid MES long trade at 5000 with 30-pt stop, 60-pt target."""
    base = {
        "asset": "MES",
        "direction": "LONG",
        "entryPrice": 5000.0,
        "stopLoss": 4970.0,         # 30 pt stop → $150 risk
        "takeProfit": 5060.0,       # 60 pt target → 2.0 R:R
        "contracts": 1,
    }
    if overrides:
        base.update(overrides)
    return base


# ── Public API shape ────────────────────────────────────────────────
def test_public_api_exports_present() -> None:
    """The narrative sub-package's `__all__` should expose the
    expected public surface."""
    assert hasattr(nv, "validate_trade_plan")
    assert hasattr(nv, "get_risk_config")
    assert hasattr(nv, "reset_cache")
    assert hasattr(nv, "RiskConfig")
    assert hasattr(nv, "AccountPhase")
    assert hasattr(nv, "InstrumentSpec")
    assert hasattr(nv, "ValidatorRules")
    # Key constants
    assert nv.KEY_ASSET == "asset"
    assert nv.KEY_ENTRY == "entryPrice"
    assert nv.KEY_STOP == "stopLoss"
    assert nv.KEY_TARGET == "takeProfit"
    assert nv.KEY_CONTRACTS == "contracts"


# ── Happy path ──────────────────────────────────────────────────────
def test_valid_long_passes_through_with_computed_fields() -> None:
    cfg = _full_config()
    plan = {"logic": "long MNQ on breakout", "trades": [_valid_mnq_long()]}

    validated, warnings = validate_trade_plan(plan, cfg=cfg)

    assert warnings == []
    assert validated["logic"] == "long MNQ on breakout"
    assert len(validated["trades"]) == 1
    t = validated["trades"][0]
    assert t["asset"] == "MNQ"
    assert t["direction"] == "LONG"
    assert t["entryPrice"] == 17000.0
    assert t["stopLoss"] == 16950.0
    assert t["takeProfit"] == 17100.0
    assert t["contracts"] == 1
    # Python-computed fields
    assert t["stopDistancePts"] == 50.0
    assert t["dollarRisk"] == 100.0          # 50 pts × $2/pt × 1c
    assert t["rewardToRisk"] == 2.0          # 100 / 50


def test_valid_short_passes_through() -> None:
    cfg = _full_config()
    plan = {
        "logic": "short",
        "trades": [{
            "asset": "MES",
            "direction": "SHORT",
            "entryPrice": 5000.0,
            "stopLoss": 5030.0,    # 30 pt stop above entry (correct for SHORT)
            "takeProfit": 4940.0,  # 60 pt target below entry
            "contracts": 1,
        }],
    }

    validated, warnings = validate_trade_plan(plan, cfg=cfg)
    assert warnings == []
    t = validated["trades"][0]
    assert t["direction"] == "SHORT"
    assert t["dollarRisk"] == 150.0
    assert t["rewardToRisk"] == 2.0


# ── Rule 1: noTrade ─────────────────────────────────────────────────
def test_no_trade_entry_dropped_silently_no_warning() -> None:
    cfg = _full_config()
    plan = {
        "logic": "skip",
        "trades": [{
            "asset": "MNQ",
            "direction": "LONG",
            "noTrade": True,
            "noTradeReason": "Waiting on CPI",
            "entryPrice": 17000.0,
            "stopLoss": 16950.0,
            "takeProfit": 17100.0,
            "contracts": 1,
        }],
    }
    validated, warnings = validate_trade_plan(plan, cfg=cfg)
    assert warnings == []
    assert validated["trades"] == []


# ── Rule 2: invalid geometry / unknown asset ────────────────────────
def test_missing_asset_drops_with_warning() -> None:
    cfg = _full_config()
    plan = {"trades": [{"direction": "LONG", "entryPrice": 1.0, "stopLoss": 0.5, "takeProfit": 2.0}]}
    validated, warnings = validate_trade_plan(plan, cfg=cfg)
    assert validated["trades"] == []
    assert any("missing asset" in w for w in warnings)


def test_unknown_asset_drops_with_warning() -> None:
    cfg = _full_config()
    plan = {"trades": [{
        "asset": "BTC", "direction": "LONG",
        "entryPrice": 60000.0, "stopLoss": 59000.0, "takeProfit": 65000.0,
    }]}
    validated, warnings = validate_trade_plan(plan, cfg=cfg)
    assert validated["trades"] == []
    assert any("unknown asset" in w and "BTC" in w for w in warnings)


def test_non_numeric_prices_drop_with_warning() -> None:
    cfg = _full_config()
    plan = {"trades": [{
        "asset": "MNQ", "direction": "LONG",
        "entryPrice": "not_a_number", "stopLoss": 16950.0, "takeProfit": 17100.0,
    }]}
    validated, warnings = validate_trade_plan(plan, cfg=cfg)
    assert validated["trades"] == []
    assert any("non-numeric" in w for w in warnings)


# ── Rule 3: zero entry ──────────────────────────────────────────────
def test_zero_entry_drops_with_warning() -> None:
    cfg = _full_config()
    plan = {"trades": [{
        "asset": "MNQ", "direction": "LONG",
        "entryPrice": 0, "stopLoss": 16950.0, "takeProfit": 17100.0,
    }]}
    validated, warnings = validate_trade_plan(plan, cfg=cfg)
    assert validated["trades"] == []
    assert any("entry=0" in w for w in warnings)


def test_negative_entry_drops_with_warning() -> None:
    cfg = _full_config()
    plan = {"trades": [{
        "asset": "MNQ", "direction": "LONG",
        "entryPrice": -100.0, "stopLoss": 16950.0, "takeProfit": 17100.0,
    }]}
    validated, warnings = validate_trade_plan(plan, cfg=cfg)
    assert validated["trades"] == []


# ── Rule 4: stop on wrong side → invert ─────────────────────────────
def test_long_stop_above_entry_is_inverted() -> None:
    cfg = _full_config()
    # entry 17000, stop 17050 (50 pts ABOVE entry) — should invert to 16950
    plan = {"trades": [{
        "asset": "MNQ", "direction": "LONG",
        "entryPrice": 17000.0, "stopLoss": 17050.0, "takeProfit": 17100.0,
        "contracts": 1,
    }]}
    validated, warnings = validate_trade_plan(plan, cfg=cfg)
    assert len(validated["trades"]) == 1
    assert validated["trades"][0]["stopLoss"] == 16950.0
    assert any("inverted to 16950" in w for w in warnings)


def test_short_stop_below_entry_is_inverted() -> None:
    cfg = _full_config()
    # MES short: entry 5000, stop 4970 (30 pts BELOW) — should invert to 5030
    plan = {"trades": [{
        "asset": "MES", "direction": "SHORT",
        "entryPrice": 5000.0, "stopLoss": 4970.0, "takeProfit": 4940.0,
        "contracts": 1,
    }]}
    validated, warnings = validate_trade_plan(plan, cfg=cfg)
    assert len(validated["trades"]) == 1
    assert validated["trades"][0]["stopLoss"] == 5030.0
    assert any("inverted to 5030" in w for w in warnings)


# ── Rule 5: target on wrong side → drop ─────────────────────────────
def test_long_target_below_entry_drops() -> None:
    cfg = _full_config()
    plan = {"trades": [{
        "asset": "MNQ", "direction": "LONG",
        "entryPrice": 17000.0, "stopLoss": 16950.0, "takeProfit": 16900.0,
        "contracts": 1,
    }]}
    validated, warnings = validate_trade_plan(plan, cfg=cfg)
    assert validated["trades"] == []
    assert any("target 16900.0 <= entry 17000.0" in w for w in warnings)


def test_short_target_above_entry_drops() -> None:
    cfg = _full_config()
    plan = {"trades": [{
        "asset": "MES", "direction": "SHORT",
        "entryPrice": 5000.0, "stopLoss": 5030.0, "takeProfit": 5100.0,
        "contracts": 1,
    }]}
    validated, warnings = validate_trade_plan(plan, cfg=cfg)
    assert validated["trades"] == []
    assert any("target 5100.0 >= entry 5000.0" in w for w in warnings)


# ── Rule 6: cap contracts to risk cap ──────────────────────────────
def test_oversized_contract_count_is_capped() -> None:
    cfg = _full_config()  # MNQ default cap $100; 50pt stop × $2/pt = $100/c
    # 5 contracts × $100 = $500 — exceeds the $100 cap; should cap to 1.
    plan = {"trades": [_valid_mnq_long({"contracts": 5})]}
    validated, warnings = validate_trade_plan(plan, cfg=cfg)
    assert len(validated["trades"]) == 1
    assert validated["trades"][0]["contracts"] == 1
    assert any("contracts 5 -> 1" in w for w in warnings)


def test_per_instrument_cap_overrides_phase_default() -> None:
    # Tighten MNQ cap to $50; with a 50-pt stop ($100 risk) the validator
    # cannot fit a single contract → drops the trade.
    cfg = _full_config(mnq_cap=50.0)
    plan = {"trades": [_valid_mnq_long()]}
    validated, warnings = validate_trade_plan(plan, cfg=cfg)
    assert validated["trades"] == []
    assert any("contracts=0 after cap" in w for w in warnings)


def test_cap_handles_wide_stop() -> None:
    # 200-pt stop on MNQ = $400 risk on 1 contract — exceeds $100 cap.
    cfg = _full_config()
    plan = {"trades": [_valid_mnq_long({
        "stopLoss": 16800.0,        # 200 pt stop
        "takeProfit": 17200.0,      # 200 pt target → 1.0 R:R
    })]}
    validated, warnings = validate_trade_plan(plan, cfg=cfg)
    # contracts must be 0 (100 / (200*2) = 0.25 → int = 0) → drop
    assert validated["trades"] == []
    assert any("contracts=0" in w for w in warnings)


# ── Rule 8: Python-computed fields ──────────────────────────────────
def test_python_computes_fields_when_llm_omits_them() -> None:
    cfg = _full_config()
    # LLM omits stopDistancePts / dollarRisk / rewardToRisk
    plan = {"trades": [{
        "asset": "MNQ", "direction": "LONG",
        "entryPrice": 17000.0, "stopLoss": 16950.0, "takeProfit": 17100.0,
        "contracts": 1,
        # no stopDistancePts, no dollarRisk, no rewardToRisk
    }]}
    validated, _ = validate_trade_plan(plan, cfg=cfg)
    t = validated["trades"][0]
    assert t["stopDistancePts"] == 50.0
    assert t["dollarRisk"] == 100.0
    assert t["rewardToRisk"] == 2.0


def test_python_uses_llm_value_when_present() -> None:
    """If the LLM supplies a risk field, the validator respects it.

    This preserves backward compatibility for LLM responses that
    already include the field. Only missing/zero fields are
    recomputed.
    """
    cfg = _full_config()
    plan = {"trades": [{
        "asset": "MNQ", "direction": "LONG",
        "entryPrice": 17000.0, "stopLoss": 16950.0, "takeProfit": 17100.0,
        "contracts": 1,
        "stopDistancePts": 49.5,   # LLM says 49.5
        "dollarRisk": 99.0,        # LLM says 99.0
        "rewardToRisk": 2.02,      # LLM says 2.02
    }]}
    validated, _ = validate_trade_plan(plan, cfg=cfg)
    t = validated["trades"][0]
    assert t["stopDistancePts"] == 49.5
    assert t["dollarRisk"] == 99.0
    assert t["rewardToRisk"] == 2.02


# ── Rule 9: block R:R threshold ────────────────────────────────────
def test_rr_below_block_threshold_drops() -> None:
    cfg = _full_config(block_rr=1.0)  # block anything < 1.0
    # 1:0.5 R:R
    plan = {"trades": [{
        "asset": "MNQ", "direction": "LONG",
        "entryPrice": 17000.0, "stopLoss": 16950.0, "takeProfit": 17025.0,
        "contracts": 1,
    }]}
    validated, warnings = validate_trade_plan(plan, cfg=cfg)
    assert validated["trades"] == []
    assert any("R:R 1:" in w and "block threshold" in w for w in warnings)


# ── Rule 10: warn-only R:R threshold ───────────────────────────────
def test_rr_below_min_threshold_warns_but_keeps() -> None:
    cfg = _full_config(min_rr=1.5)  # warn anything < 1.5
    # 1:1.2 R:R
    plan = {"trades": [{
        "asset": "MNQ", "direction": "LONG",
        "entryPrice": 17000.0, "stopLoss": 16950.0, "takeProfit": 17060.0,
        "contracts": 1,
    }]}
    validated, warnings = validate_trade_plan(plan, cfg=cfg)
    assert len(validated["trades"]) == 1
    assert any("below min 1:1.5 (kept)" in w for w in warnings)


def test_rr_at_min_threshold_kept_without_warning() -> None:
    cfg = _full_config(min_rr=1.5, block_rr=1.0)
    # 1:1.5 R:R (exactly at min)
    plan = {"trades": [{
        "asset": "MNQ", "direction": "LONG",
        "entryPrice": 17000.0, "stopLoss": 16950.0, "takeProfit": 17075.0,
        "contracts": 1,
    }]}
    validated, warnings = validate_trade_plan(plan, cfg=cfg)
    assert len(validated["trades"]) == 1
    assert warnings == []  # 1.5 is NOT < 1.5, so no warning


# ── Direction normalisation ────────────────────────────────────────
@pytest.mark.parametrize("raw_dir,expected", [
    ("LONG", DIR_LONG),
    ("long", DIR_LONG),
    ("  Long ", DIR_LONG),
    ("buy", DIR_LONG),       # unknown → default LONG
    ("", DIR_LONG),          # empty → default LONG
    (None, DIR_LONG),        # missing → default LONG
])
def test_direction_long_normalised(raw_dir, expected) -> None:
    cfg = _full_config()
    trade = _valid_mnq_long()
    if raw_dir is None:
        trade.pop("direction", None)
    else:
        trade["direction"] = raw_dir
    plan = {"trades": [trade]}
    validated, _ = validate_trade_plan(plan, cfg=cfg)
    assert len(validated["trades"]) == 1
    assert validated["trades"][0]["direction"] == expected


@pytest.mark.parametrize("raw_dir,expected", [
    ("SHORT", DIR_SHORT),
    ("short", DIR_SHORT),
    ("  Short ", DIR_SHORT),
    ("SELL", DIR_SHORT),     # unknown → default LONG (per current impl)
])
def test_direction_short_normalised(raw_dir, expected) -> None:
    """SHORT direction tests use SHORT-valid geometry (target below
    entry) so the validator does not drop them on target-side rules."""
    cfg = _full_config()
    trade = {
        "asset": "MNQ",
        "direction": "SHORT",
        "entryPrice": 17000.0,
        "stopLoss": 17050.0,    # stop above entry (correct for SHORT)
        "takeProfit": 16900.0,  # target below entry (correct for SHORT)
        "contracts": 1,
    }
    if raw_dir is None:
        trade.pop("direction", None)
    else:
        trade["direction"] = raw_dir
    plan = {"trades": [trade]}
    validated, _ = validate_trade_plan(plan, cfg=cfg)
    assert len(validated["trades"]) == 1
    assert validated["trades"][0]["direction"] == expected


# ── Mixed plan ──────────────────────────────────────────────────────
def test_mixed_plan_keeps_valid_drops_invalid() -> None:
    cfg = _full_config()
    plan = {
        "logic": "mixed",
        "trades": [
            _valid_mnq_long(),                                  # valid
            _valid_mes_long(),                                  # valid
            {"asset": "MNQ", "noTrade": True, "noTradeReason": "CPI"},  # silent drop
            {"asset": "BTC", "direction": "LONG", "entryPrice": 60000.0,
             "stopLoss": 59000.0, "takeProfit": 65000.0, "contracts": 1},  # unknown asset
            {"asset": "MNQ", "direction": "LONG",
             "entryPrice": 17000.0, "stopLoss": 17050.0,        # wrong-side stop
             "takeProfit": 17100.0, "contracts": 1},            # will be inverted
        ],
    }
    validated, warnings = validate_trade_plan(plan, cfg=cfg)
    # Expect: 2 valid (MNQ + MES) + 1 inverted MNQ = 3 trades in output
    assert len(validated["trades"]) == 3
    assets = {t["asset"] for t in validated["trades"]}
    assert assets == {"MNQ", "MES"}
    # 2 warnings (BTC unknown, MNQ inverted)
    assert len(warnings) == 2


# ── Logging behaviour ───────────────────────────────────────────────
def test_log_warnings_true_writes_to_log(caplog) -> None:
    rules = ValidatorRules(
        max_price_decimals=2,
        drop_on_unknown_asset=True,
        log_warnings=True,
    )
    instruments = {
        "MNQ": InstrumentSpec(
            name="x", multiplier_dollar_per_pt=2.0,
            tick_size=0.25, tick_value_dollar=0.50,
        ),
    }
    phases = {
        "EVAL": AccountPhase(
            label="EVAL", description="e",
            default_risk_cap_per_trade_usd=100.0, daily_stop_usd=300.0,
            total_dd_buffer_usd=0.0, max_open_trades=3,
            min_reward_to_risk=1.5, block_reward_to_risk=1.0,
            allow_overnight=False,
        ),
    }
    cfg = RiskConfig(
        version="t", active_phase="EVAL", instruments=instruments,
        account_phases=phases, per_instrument_caps={}, validator_rules=rules,
    )
    plan = {"trades": [_valid_mnq_long({"stopLoss": 17050.0})]}

    with caplog.at_level(logging.WARNING, logger="scripts.libs_py.risk.narrative.validator"):
        validate_trade_plan(plan, cfg=cfg)

    assert any("[risk-validator]" in r.message for r in caplog.records)


# ── Config round-trip ───────────────────────────────────────────────
def test_get_risk_config_returns_frozen_valid_config() -> None:
    reset_cache()
    cfg = get_risk_config()
    # Schema sanity
    assert cfg.version
    assert cfg.active_phase in cfg.account_phases
    # Spot-check a few known values
    assert "MNQ" in cfg.instruments
    assert cfg.instruments["MNQ"].multiplier_dollar_per_pt == 2.0
    assert "MES" in cfg.instruments
    assert cfg.instruments["MES"].multiplier_dollar_per_pt == 5.0
    # Per-instrument cap helper
    assert cfg.get_risk_cap("MNQ") == 100.0
    assert cfg.get_risk_cap("MES") == 150.0
    # Phase helper
    phase = cfg.get_phase()
    assert phase.label == cfg.active_phase
    # Frozen
    with pytest.raises((AttributeError, TypeError)):
        cfg.active_phase = "FUNDED"  # type: ignore[misc]


def test_reset_cache_invalidates() -> None:
    cfg1 = get_risk_config()
    reset_cache()
    cfg2 = get_risk_config()
    assert cfg1 is not cfg2  # cache was cleared


# ── Defaults end-to-end ─────────────────────────────────────────────
def test_default_config_validates_known_good_plan() -> None:
    """Smoke test: the production constants (without overrides) accept
    a realistic MNQ+MES plan with no warnings."""
    reset_cache()
    plan = {
        "logic": "smoke",
        "trades": [_valid_mnq_long(), _valid_mes_long()],
    }
    validated, warnings = validate_trade_plan(plan)
    assert len(validated["trades"]) == 2
    assert warnings == []
