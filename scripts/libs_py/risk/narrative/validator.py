# filepath: scripts/libs_py/risk/narrative/validator.py
"""LLM-output trade-plan validator.

The LLM that produces daily narratives (`scripts.trader.daily_narrative`)
also returns a JSON trade plan inside `<plan_json>...</plan_json>`. The
plan is meant to be saved to the Prisma DB and shown in Discord. Before
it reaches either, we run it through `validate_trade_plan()` to:

  1. Drop trades with invalid geometry (zero entry, wrong-side stop,
     wrong-side target, non-numeric prices, unknown instrument).
  2. Cap oversized contract counts to the per-instrument risk cap.
  3. Compute the missing risk fields (stopDistancePts, dollarRisk,
     rewardToRisk) deterministically in Python — the LLM is not
     trusted to do this math.
  4. Optionally block trades whose R:R is below the phase's hard
     threshold (block_reward_to_risk).

All decisions are made in Python. The LLM does not see the warnings and
the Discord summary never carries them — the operator sees them in the
scheduler console only.

This module is pure-functional (no DB, no I/O, no logging side-effects
beyond what `log.warning` does). It is easy to unit-test.
"""
from __future__ import annotations

import logging
from typing import Final

from .config import AccountPhase, InstrumentSpec, RiskConfig, get_risk_config

log = logging.getLogger(__name__)


# ── Public types ────────────────────────────────────────────────────
# The dict shape returned by `validate_trade_plan` is intentionally a
# plain `dict` to keep the LLM/Prisma boundary simple, but we expose
# string constants for the keys that downstream code reads.
KEY_ASSET: Final[str] = "asset"
KEY_DIRECTION: Final[str] = "direction"
KEY_ENTRY: Final[str] = "entryPrice"
KEY_STOP: Final[str] = "stopLoss"
KEY_TARGET: Final[str] = "takeProfit"
KEY_CONTRACTS: Final[str] = "contracts"
KEY_STOP_DIST: Final[str] = "stopDistancePts"
KEY_DOLLAR_RISK: Final[str] = "dollarRisk"
KEY_RR: Final[str] = "rewardToRisk"
KEY_REGIME: Final[str] = "regime"
KEY_NOTRADE: Final[str] = "noTrade"
KEY_NOTRADE_REASON: Final[str] = "noTradeReason"
KEY_LOGIC: Final[str] = "logic"
KEY_TRADES: Final[str] = "trades"

DIR_LONG: Final[str] = "LONG"
DIR_SHORT: Final[str] = "SHORT"
_VALID_DIRECTIONS: Final[frozenset[str]] = frozenset({DIR_LONG, DIR_SHORT})


# ── Helpers ─────────────────────────────────────────────────────────
def _coerce_trade_fields(trade: dict, cfg: RiskConfig) -> tuple[dict | None, str | None]:
    """Coerce LLM-returned trade fields to canonical types.

    Args:
        trade: raw trade dict from the LLM.
        cfg: typed risk config.

    Returns:
        (coerced, None) on success.
        (None, error_msg) if the trade must be dropped.
    """
    asset_raw = trade.get(KEY_ASSET, "")
    asset = str(asset_raw).upper().strip() if asset_raw is not None else ""
    if not asset:
        return None, "missing asset"

    if asset not in cfg.instruments:
        if cfg.validator_rules.drop_on_unknown_asset:
            return None, f"unknown asset '{asset_raw}'"
        # If the operator has chosen to keep unknown assets, we still
        # can't compute risk — so drop the trade with a clear reason.
        return None, f"unknown asset '{asset_raw}' (cannot compute risk)"

    direction_raw = trade.get(KEY_DIRECTION, DIR_LONG)
    direction = str(direction_raw).upper().strip() if direction_raw is not None else DIR_LONG
    # Common synonyms → canonical form. Anything else falls back to LONG.
    _DIRECTION_SYNONYMS: dict[str, str] = {
        "BUY": DIR_LONG,
        "LONG": DIR_LONG,
        "SELL": DIR_SHORT,
        "SHORT": DIR_SHORT,
    }
    direction = _DIRECTION_SYNONYMS.get(direction, DIR_LONG)

    try:
        entry = float(trade.get(KEY_ENTRY, 0))
        stop = float(trade.get(KEY_STOP, 0))
        target = float(trade.get(KEY_TARGET, 0))
    except (TypeError, ValueError):
        return None, (
            f"non-numeric price (entry={trade.get(KEY_ENTRY)!r}, "
            f"stop={trade.get(KEY_STOP)!r}, target={trade.get(KEY_TARGET)!r})"
        )

    try:
        contracts = int(float(trade.get(KEY_CONTRACTS, 0)))
    except (TypeError, ValueError):
        contracts = 0

    return {
        KEY_ASSET: asset,
        KEY_DIRECTION: direction,
        KEY_ENTRY: entry,
        KEY_STOP: stop,
        KEY_TARGET: target,
        KEY_CONTRACTS: contracts,
    }, None


def _round_prices(trade: dict, decimals: int) -> None:
    """Round the price/contracts fields in-place to the configured precision."""
    for key in (KEY_ENTRY, KEY_STOP, KEY_TARGET, KEY_STOP_DIST, KEY_DOLLAR_RISK, KEY_RR):
        if key in trade and isinstance(trade[key], (int, float)):
            trade[key] = round(float(trade[key]), decimals)


# ── Public API ──────────────────────────────────────────────────────
def validate_trade_plan(
    plan_data: dict,
    cfg: RiskConfig | None = None,
) -> tuple[dict, list[str]]:
    """Validate and correct an LLM-generated trade plan.

    Args:
        plan_data: raw parsed plan (from the `<plan_json>` block).
        cfg: optional pre-built RiskConfig (defaults to the cached one).

    Returns:
        (validated_plan, warnings)
            validated_plan: {"logic": str, "trades": [corrected_trades]}
            warnings: list of human-readable warning strings, suitable
                for `log.warning` but NOT for Discord output.

    Behaviour summary (in order):
        1. `noTrade=True` entries are dropped silently and NOT counted
           as warnings (caller is expected to log them separately).
        2. Missing asset / unknown instrument / non-numeric prices →
           drop with a warning.
        3. `entryPrice <= 0` → drop.
        4. Stop on the wrong side of entry → invert (LONG: stop must
           be < entry; SHORT: stop must be > entry).
        5. Target on the wrong side of entry → drop (cannot be
           corrected safely).
        6. `contracts > max_for_risk_cap` → cap and warn.
        7. `contracts < 1` after cap → drop.
        8. Compute stopDistancePts / dollarRisk / rewardToRisk from
           Python truth (the LLM's values, if present, are used as a
           fallback only).
        9. R:R < block_reward_to_risk → drop with warning.
        10. R:R < min_reward_to_risk → keep with warning.
    """
    cfg = cfg or get_risk_config()
    phase = cfg.get_phase()
    decimals = cfg.validator_rules.max_price_decimals
    log_warnings = cfg.validator_rules.log_warnings

    warnings: list[str] = []
    out_trades: list[dict] = []

    for raw in plan_data.get(KEY_TRADES, []):
        asset_label = str(raw.get(KEY_ASSET, "?")).upper() or "?"

        # Rule 1: drop noTrade=True silently (caller logs separately)
        if raw.get(KEY_NOTRADE, False):
            continue

        # Rules 2-3: coerce and basic validity
        coerced, err = _coerce_trade_fields(raw, cfg)
        if err is not None:
            warnings.append(f"{asset_label}: dropped ({err})")
            continue

        asset = coerced[KEY_ASSET]
        direction = coerced[KEY_DIRECTION]
        entry = coerced[KEY_ENTRY]
        stop = coerced[KEY_STOP]
        target = coerced[KEY_TARGET]
        contracts = coerced[KEY_CONTRACTS]

        spec: InstrumentSpec = cfg.instruments[asset]
        risk_cap = cfg.get_risk_cap(asset)

        # Rule 3 (zero entry)
        if entry <= 0:
            warnings.append(f"{asset}: dropped (entry={entry}, must be > 0)")
            continue

        # Rule 4: stop on wrong side of entry → invert
        if direction == DIR_LONG and stop >= entry:
            new_stop = round(entry - abs(stop - entry), decimals)
            warnings.append(f"{asset} LONG: stop {stop} >= entry {entry}, inverted to {new_stop}")
            stop = new_stop
        elif direction == DIR_SHORT and stop <= entry:
            new_stop = round(entry + abs(stop - entry), decimals)
            warnings.append(f"{asset} SHORT: stop {stop} <= entry {entry}, inverted to {new_stop}")
            stop = new_stop

        # Rule 5: target on wrong side of entry → drop
        if direction == DIR_LONG and target <= entry:
            warnings.append(f"{asset} LONG: dropped (target {target} <= entry {entry})")
            continue
        if direction == DIR_SHORT and target >= entry:
            warnings.append(f"{asset} SHORT: dropped (target {target} >= entry {entry})")
            continue

        # Rule 6: cap contracts to risk_cap / (stop_pts * point_value)
        stop_pts = abs(entry - stop)
        if stop_pts > 0 and spec.multiplier_dollar_per_pt > 0:
            max_contracts = int(risk_cap / (stop_pts * spec.multiplier_dollar_per_pt))
        else:
            max_contracts = 0

        if contracts > max_contracts:
            warnings.append(
                f"{asset}: contracts {contracts} -> {max_contracts} (cap by ${risk_cap:.0f})"
            )
            contracts = max_contracts

        # Rule 7: drop if no contracts after cap
        if contracts < 1:
            warnings.append(f"{asset}: dropped (contracts={contracts} after cap)")
            continue

        # Rule 8: compute missing risk fields (Python truth)
        target_pts = abs(target - entry)
        stop_distance_pts = raw.get(KEY_STOP_DIST) or round(stop_pts, decimals)
        dollar_risk = (
            raw.get(KEY_DOLLAR_RISK)
            or round(contracts * stop_pts * spec.multiplier_dollar_per_pt, decimals)
        )
        rr_value = raw.get(KEY_RR)
        if rr_value is None or rr_value == 0:
            rr_value = round(target_pts / stop_pts, 2) if stop_pts > 0 else 0.0
        else:
            try:
                rr_value = float(rr_value)
            except (TypeError, ValueError):
                rr_value = round(target_pts / stop_pts, 2) if stop_pts > 0 else 0.0

        # Rule 9: block below hard R:R threshold
        if rr_value < phase.block_reward_to_risk:
            warnings.append(
                f"{asset}: dropped (R:R 1:{rr_value} < block threshold 1:{phase.block_reward_to_risk})"
            )
            continue

        # Rule 10: warn (keep) below soft R:R threshold
        if rr_value < phase.min_reward_to_risk:
            warnings.append(
                f"{asset}: R:R 1:{rr_value} below min 1:{phase.min_reward_to_risk} (kept)"
            )

        corrected = {
            **raw,  # preserve regime, noTradeReason, etc.
            KEY_ASSET: asset,
            KEY_DIRECTION: direction,
            KEY_ENTRY: round(entry, decimals),
            KEY_STOP: round(stop, decimals),
            KEY_TARGET: round(target, decimals),
            KEY_CONTRACTS: contracts,
            KEY_STOP_DIST: stop_distance_pts,
            KEY_DOLLAR_RISK: dollar_risk,
            KEY_RR: rr_value,
        }
        _round_prices(corrected, decimals)
        out_trades.append(corrected)

    if log_warnings and warnings:
        for w in warnings:
            log.warning("[risk-validator] %s", w)

    return (
        {KEY_LOGIC: plan_data.get(KEY_LOGIC, ""), KEY_TRADES: out_trades},
        warnings,
    )


__all__: Final[tuple[str, ...]] = (
    "validate_trade_plan",
    "KEY_ASSET",
    "KEY_DIRECTION",
    "KEY_ENTRY",
    "KEY_STOP",
    "KEY_TARGET",
    "KEY_CONTRACTS",
    "KEY_STOP_DIST",
    "KEY_DOLLAR_RISK",
    "KEY_RR",
    "KEY_REGIME",
    "KEY_NOTRADE",
    "KEY_NOTRADE_REASON",
    "KEY_LOGIC",
    "KEY_TRADES",
    "DIR_LONG",
    "DIR_SHORT",
)
