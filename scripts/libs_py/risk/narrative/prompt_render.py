# filepath: scripts/libs_py/risk/narrative/prompt_render.py
"""Render prompt-level risk-parameter blocks for the narrative chain.

This module is the SINGLE SOURCE for the `{{INSERT_RISK_PARAMS}}`
block that gets injected into the daily-open / daily-EOD / trader
morning / trader intraday / trader close prompts. It reads the
typed risk config (constants.py → config.py) and produces the
markdown the LLM sees.

Why a dedicated module
----------------------
The risk numbers (MES $150/trade, MNQ $100/trade, daily stop
$450/$300, $2k trailing DD, max 3 trades/day, min R:R 1:2) used
to be hardcoded into 5+ prompt files (audit issue §1.7). Any time
the trader moved from 50K to 100K or tweaked the daily stop, every
prompt had to be edited by hand. That is error-prone and creates
silent drift between prompts.

This module exists to:
  1. Read the typed risk config (which the validator also uses, so
     there is exactly one source of truth for the numbers).
  2. Render the markdown block on demand.
  3. Inject it into the prompt template via a `{{INSERT_RISK_PARAMS}}`
     placeholder.

The placeholder is replaced by `daily_narrative.py` and
`trader_narrative.py` *before* the prompt is sent to Ollama.

Format produced
---------------
A markdown block ready to drop into a prompt section. Example for
phase=EVAL, instruments=[MNQ, MES]:

    ## Risk Parameters (active phase: EVAL)
    - Account size: $50,000 (50K evaluation, prop firm)
    - Trailing-DD buffer remaining: $2,000
    - Max open trades / day: 3
    - Min R:R (warn below this): 1.5:1
    - Block R:R (drop trade below this): 1.0:1
    - Allow overnight holds: No

    | Instrument | Contract  | $/pt | Risk/trade | Daily stop | Proxy |
    |------------|-----------|------|------------|------------|-------|
    | MNQ        | Micro NQ  | $2   | $100       | $450       | QQQ   |
    | MES        | Micro ES  | $5   | $150       | $450       | SPY   |
    | ES (full)  | E-mini ES | $50  | $250       | $450       | SPY   |
    | NQ (full)  | E-mini NQ | $20  | $200       | $450       | QQQ   |

    - Same-direction combined risk cap: $200
    - Same-direction combined-risk cap rationale: the $150 MES
      cap and the $100 MNQ cap can both fit when paired; never
      exceed the per-account max open trades above.

The combined-risk line is intentionally a soft check (LLM-visible
guidance), not a hard validator rule. The validator already
enforces per-instrument caps; this line just prevents the LLM
from proposing two MES longs that together would consume $300
on a $300 day-stop account.
"""
from __future__ import annotations

from typing import Final

from . import constants as C
from .config import get_risk_config


# Default order for the per-instrument table when callers do not
# pass an explicit order. Keeps the rendered block stable across
# runs (otherwise dict-iteration order could shuffle the table).
DEFAULT_INSTRUMENT_ORDER: Final[tuple[str, ...]] = (
    "MNQ", "MES", "MYM", "M2K", "NQ", "ES",
)


# Sentinel returned by the renderer when nothing in the config
# matches the requested instruments. Helps tests detect
# "configuration drift" without coupling to a specific exception.
EMPTY_BLOCK: Final[str] = (
    "## Risk Parameters\n"
    "- (no instruments configured for the active phase)\n"
)


def _format_usd(amount: float | int) -> str:
    """Render a USD amount with comma thousands separator and no decimals.

    Examples:
        >>> _format_usd(2000)
        '$2,000'
        >>> _format_usd(150.0)
        '$150'
    """
    return f"${int(round(amount)):,}"


def _format_combined_risk_line(instruments: list[str]) -> str:
    """Compute the per-account same-direction combined-risk cap.

    This is the cap when the trader takes the same direction on
    BOTH MNQ and MES (e.g. a long-MNQ + long-MES setup). We sum
    the per-instrument risk caps for the requested instruments
    that appear in PER_INSTRUMENT_CAPS.

    Returns a string like:
        'Same-direction combined risk cap: $250 (MES $150 + MNQ $100)'
    or just:
        'Same-direction combined risk cap: N/A'
    if no per-instrument caps are configured.
    """
    caps: list[tuple[str, float]] = []
    for inst in instruments:
        per = C.PER_INSTRUMENT_CAPS.get(inst)
        if per and "risk_cap_per_trade_usd" in per:
            caps.append((inst, per["risk_cap_per_trade_usd"]))
    if not caps:
        return "- Same-direction combined risk cap: N/A"
    total = sum(v for _, v in caps)
    breakdown = " + ".join(f"{inst} ${int(cap)}" for inst, cap in caps)
    return f"- Same-direction combined risk cap: { _format_usd(total)} ({breakdown})"


def format_risk_params_block(
    instruments: list[str] | None = None,
    phase: str | None = None,
) -> str:
    """Render the risk-params markdown block for the prompt.

    Args:
        instruments: list of micro-instrument symbols to include in
            the table (e.g. ['MNQ', 'MES']). Order is preserved
            after de-duplication. If None or empty, uses
            DEFAULT_INSTRUMENT_ORDER filtered to instruments that
            exist in INSTRUMENT_SPECS.
        phase: account phase label ('EVAL' / 'FUNDED'). If None,
            reads C.ACTIVE_PHASE.

    Returns:
        A markdown string ready to drop into a prompt. Returns
        EMPTY_BLOCK if no instruments are configured for the
        active phase.
    """
    cfg = get_risk_config()
    phase = phase or C.ACTIVE_PHASE
    acct = cfg.account_phases.get(phase)
    if acct is None:
        return EMPTY_BLOCK

    # De-duplicate the instrument list while preserving order.
    if instruments is None:
        instruments = [
            inst for inst in DEFAULT_INSTRUMENT_ORDER
            if inst in C.INSTRUMENT_SPECS
        ]
    seen: set[str] = set()
    ordered: list[str] = []
    for inst in instruments:
        if inst not in seen and inst in C.INSTRUMENT_SPECS:
            ordered.append(inst)
            seen.add(inst)
    if not ordered:
        return EMPTY_BLOCK

    # ── Account-level lines ──────────────────────────────────────
    account_size = C.ACCOUNT_SIZE_USD.get(phase, 0)
    account_size_str = (
        _format_usd(account_size) if account_size else "N/A"
    )
    dd_buffer_str = _format_usd(acct.total_dd_buffer_usd)
    daily_stop_str = _format_usd(acct.daily_stop_usd)
    max_open = acct.max_open_trades
    min_rr = acct.min_reward_to_risk
    block_rr = acct.block_reward_to_risk
    allow_overnight = "Yes" if acct.allow_overnight else "No"

    # Trailing-DD buffer line is phase-specific. EVAL accounts use a
    # fixed daily stop (no trailing-DD) so showing $0 looks wrong; we
    # label it as "not applicable" for EVAL and show the buffer for
    # FUNDED. Future phases can override via the same field.
    if acct.total_dd_buffer_usd > 0:
        dd_line = f"- Trailing-DD buffer remaining: {dd_buffer_str}"
    else:
        dd_line = "- Trailing-DD buffer: not applicable (fixed daily-stop account)"

    lines: list[str] = [
        f"## Risk Parameters (active phase: {phase})",
        f"- Account size: {account_size_str} ({phase.lower()} account)",
        dd_line,
        f"- Daily stop: {daily_stop_str} (cumulative realized loss for the day → stop trading)",
        f"- Max open trades / day: {max_open}",
        f"- Min R:R (warn below this): {min_rr}:1",
        f"- Block R:R (drop trade below this): {block_rr}:1",
        f"- Allow overnight holds: {allow_overnight}",
        "",
        "| Instrument | Contract  | $/pt | Risk/trade | Daily stop | Proxy |",
        "|------------|-----------|------|------------|------------|-------|",
    ]

    # ── Per-instrument table ─────────────────────────────────────
    for inst in ordered:
        spec = C.INSTRUMENT_SPECS[inst]
        cap = C.PER_INSTRUMENT_CAPS.get(inst, {}).get("risk_cap_per_trade_usd")
        risk_str = _format_usd(cap) if cap is not None else "(account default)"
        proxy = C.PROXY_SYMBOLS.get(inst, "—")
        contract_label = spec["name"]
        # Trim the verbose "E-mini" / "Micro E-mini" prefix for the
        # contract column to keep the table compact. The full name
        # is still recoverable from the spec dict.
        short = (
            contract_label
            .replace("E-mini ", "")
            .replace("Micro E-mini ", "Micro ")
        )
        lines.append(
            f"| {inst:<10} | {short:<9} "
            f"| ${int(spec['multiplier_dollar_per_pt']):<2} "
            f"| {risk_str:<10} "
            f"| {daily_stop_str:<10} "
            f"| {proxy:<5} |"
        )

    lines.append("")  # blank line before the combined-risk line
    lines.append(_format_combined_risk_line(ordered))

    return "\n".join(lines)


def insert_risk_params(prompt: str, instruments: list[str] | None = None) -> str:
    """Replace the `{{INSERT_RISK_PARAMS}}` placeholder in a prompt.

    The prompt must contain `{{INSERT_RISK_PARAMS}}` literally. If
    the placeholder is missing, the prompt is returned unchanged
    (a warning is logged, but the call does not raise — the user
    may have a custom prompt that does not need the block).

    Args:
        prompt: the full prompt string (after other placeholder
            substitutions have been made).
        instruments: list of micro-instrument symbols to include
            in the per-instrument table. Forwarded to
            `format_risk_params_block`.

    Returns:
        The prompt with `{{INSERT_RISK_PARAMS}}` replaced by the
        rendered markdown block. If the placeholder is missing,
        the prompt is returned unchanged.
    """
    placeholder = "{{INSERT_RISK_PARAMS}}"
    if placeholder not in prompt:
        return prompt
    block = format_risk_params_block(instruments=instruments)
    return prompt.replace(placeholder, block)
