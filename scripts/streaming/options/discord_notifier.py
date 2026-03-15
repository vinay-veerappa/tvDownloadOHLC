"""
discord_notifier.py
===================
Formats dealer-positioning summaries into Discord embeds and delivers them
via webhook.  All Discord-specific logic lives in this module.

Public API
----------
send_discord_update(translated_levels, run_label, webhook_url) → None
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

import requests

from .config import (
    DISCORD_WEBHOOKS_PATH,
    DISCORD_TARGET_KEY,
    DISCORD_COLOR_POSITIVE,
    DISCORD_COLOR_NEGATIVE,
)
from .futures_translator import TranslatedLevels
from .gex_calculator import DealerLevels

log = logging.getLogger(__name__)

# Max embeds Discord accepts per webhook call.
_DISCORD_MAX_EMBEDS = 10
_DISCORD_MAX_CONTENT = 2000


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_webhook_url() -> str:
    """Read the webhook URL for DISCORD_TARGET_KEY from discord_webhooks.json."""
    try:
        data: dict[str, str] = json.loads(DISCORD_WEBHOOKS_PATH.read_text())
    except FileNotFoundError:
        raise FileNotFoundError(
            f"discord_webhooks.json not found at {DISCORD_WEBHOOKS_PATH}"
        )
    url = data.get(DISCORD_TARGET_KEY)
    if not url:
        raise KeyError(
            f"Webhook key '{DISCORD_TARGET_KEY}' not found in {DISCORD_WEBHOOKS_PATH}. "
            f"Available keys: {list(data.keys())}"
        )
    return url


def _fmt(value: float | None, decimals: int = 2) -> str:
    """Format a float for display, returning 'N/A' for None."""
    if value is None:
        return "N/A"
    return f"{value:,.{decimals}f}"


def _fmt_copy(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:.2f}"


def _first_level(*values: float | None) -> float | None:
    for value in values:
        if value is not None:
            return value
    return None


def _nearest_below(reference: float | None, *values: float | None) -> float | None:
    if reference is None:
        return _first_level(*values)
    candidates = [value for value in values if value is not None and value < reference]
    if not candidates:
        return _first_level(*values)
    return max(candidates)


def _nearest_above(reference: float | None, *values: float | None) -> float | None:
    if reference is None:
        return _first_level(*values)
    candidates = [value for value in values if value is not None and value > reference]
    if not candidates:
        return _first_level(*values)
    return min(candidates)


def _regime_line(regime: str) -> str:
    emoji = "🟢" if regime == "POSITIVE" else "🔴"
    return f"{emoji} **{regime} GEX**"


def _copy_ready_line(tl: TranslatedLevels) -> str:
    tag = tl.futures_symbol.lstrip("/")
    ordered = [
        (_fmt_copy(tl.em_upper), "Upper EM"),
        (_fmt_copy(tl.call_wall), "Absolute Call Wall"),
        (_fmt_copy(tl.local_call_node), "Local Call Node"),
        (_fmt_copy(tl.call_wall_0dte), "0DTE Call Wall"),
        (_fmt_copy(tl.dex_call_node), "DEX Call Node"),
        (_fmt_copy(tl.gamma_flip_upper), "Gamma Flip Upper"),
        (_fmt_copy(tl.gamma_cliff_up), "Gamma Cliff Up"),
        (_fmt_copy(tl.zero_gamma), "Zero Gamma"),
        (_fmt_copy(tl.gamma_cliff_down), "Gamma Cliff Down"),
        (_fmt_copy(tl.gamma_flip_lower), "Gamma Flip Lower"),
        (_fmt_copy(tl.max_pain), "Max Pain"),
        (_fmt_copy(tl.put_wall_0dte), "0DTE Put Wall"),
        (_fmt_copy(tl.local_put_node), "Local Put Node"),
        (_fmt_copy(tl.dex_put_node), "DEX Put Node"),
        (_fmt_copy(tl.hedge_wall), "Hedge Wall"),
        (_fmt_copy(tl.em_lower), "Lower EM"),
    ]
    return f"{tag}: " + ", ".join(f"{price}:{label}" for price, label in ordered)


def _copy_ready_cash_line(levels: DealerLevels) -> str:
    ordered = [
        (_fmt_copy(levels.em_upper), "Upper EM"),
        (_fmt_copy(levels.call_wall), "Absolute Call Wall"),
        (_fmt_copy(levels.local_call_node), "Local Call Node"),
        (_fmt_copy(levels.call_wall_0dte), "0DTE Call Wall"),
        (_fmt_copy(levels.dex_call_node), "DEX Call Node"),
        (_fmt_copy(levels.gamma_flip_upper), "Gamma Flip Upper"),
        (_fmt_copy(levels.gamma_cliff_up), "Gamma Cliff Up"),
        (_fmt_copy(levels.zero_gamma), "Zero Gamma"),
        (_fmt_copy(levels.gamma_cliff_down), "Gamma Cliff Down"),
        (_fmt_copy(levels.gamma_flip_lower), "Gamma Flip Lower"),
        (_fmt_copy(levels.max_pain), "Max Pain"),
        (_fmt_copy(levels.put_wall_0dte), "0DTE Put Wall"),
        (_fmt_copy(levels.local_put_node), "Local Put Node"),
        (_fmt_copy(levels.dex_put_node), "DEX Put Node"),
        (_fmt_copy(levels.hedge_wall), "Hedge Wall"),
        (_fmt_copy(levels.em_lower), "Lower EM"),
    ]
    return f"{levels.ticker}: " + ", ".join(f"{price}:{label}" for price, label in ordered)


def _plan_lines(tl: TranslatedLevels) -> str:
    tag = tl.futures_symbol.lstrip("/")
    short_trigger = _first_level(tl.zero_gamma, tl.gamma_flip_lower, tl.call_wall)
    short_target = _nearest_below(short_trigger, tl.put_wall_0dte, tl.local_put_node, tl.hedge_wall, tl.em_lower)
    short_invalid = _nearest_above(short_trigger, tl.gamma_flip_upper, tl.call_wall, tl.em_upper)

    long_trigger = _first_level(tl.call_wall, tl.gamma_flip_upper, tl.zero_gamma)
    long_target = _nearest_above(long_trigger, tl.max_pain, tl.em_upper)
    long_invalid = _nearest_below(long_trigger, tl.zero_gamma, tl.gamma_flip_lower, tl.put_wall_0dte)

    regime_tone = "sellers have structural control" if tl.gex_regime == "NEGATIVE" else "buyers have structural control"

    return (
        f"Context: {tag} is in a {tl.gex_regime} GEX regime ({tl.total_gex:,.0f}); {regime_tone}.\n"
        f"Watch first: Zero Gamma {_fmt_copy(tl.zero_gamma)}, gamma flip {_fmt_copy(tl.gamma_flip_lower)}↔{_fmt_copy(tl.gamma_flip_upper)}, DEX {_fmt_copy(tl.dex_put_node)}/{_fmt_copy(tl.dex_call_node)}.\n"
        f"Base case: Below {_fmt_copy(short_trigger)}, look for rotation into {_fmt_copy(short_target)}. Use Gamma Cliff Down {_fmt_copy(tl.gamma_cliff_down)} and DEX {_fmt_copy(tl.dex_put_node)} as reaction zones; invalidation is reclaim/hold above {_fmt_copy(short_invalid)}.\n"
        f"Alternate: Above {_fmt_copy(long_trigger)}, look for continuation into {_fmt_copy(long_target)}. Use Gamma Cliff Up {_fmt_copy(tl.gamma_cliff_up)} and DEX {_fmt_copy(tl.dex_call_node)} as decision zones; invalidation is loss of {_fmt_copy(long_invalid)} after breakout.\n"
        f"Risk map: EM {_fmt_copy(tl.em_lower)}↔{_fmt_copy(tl.em_upper)}."
    )


def _copy_block_payload(
    translated_levels: list[TranslatedLevels],
    run_label: str,
    cash_levels: list[DealerLevels] | None = None,
) -> dict[str, Any]:
    lines = [_copy_ready_line(tl) for tl in translated_levels]
    if cash_levels:
        lines.extend(_copy_ready_cash_line(levels) for levels in cash_levels)
    header = f"**Dealer Levels — {run_label}**\nCopy directly into TradingView indicator input:\n"
    content = header + "```\n" + "\n".join(lines) + "\n```"

    if len(content) <= _DISCORD_MAX_CONTENT:
        return {"content": content}

    trimmed: list[str] = []
    current_len = len(header) + len("```\n\n```")
    for line in lines:
        add_len = len(line) + 1
        if current_len + add_len > _DISCORD_MAX_CONTENT:
            break
        trimmed.append(line)
        current_len += add_len

    return {
        "content": header + "```\n" + "\n".join(trimmed) + "\n```",
    }


def _build_embed(tl: TranslatedLevels, run_label: str) -> dict[str, Any]:
    """Construct a single Discord embed dict for one TranslatedLevels entry."""
    color = DISCORD_COLOR_POSITIVE if tl.gex_regime == "POSITIVE" else DISCORD_COLOR_NEGATIVE
    tag = tl.futures_symbol.lstrip("/")   # "ES" or "NQ"

    fields: list[dict[str, Any]] = [
        {
            "name": "Regime",
            "value": _regime_line(tl.gex_regime),
            "inline": False,
        },
        # ── Prices ──────────────────────────────────────────────
        {"name": f"Cash Index ({tl.cash_ticker})", "value": _fmt(tl.cash_spot),      "inline": True},
        {"name": f"{tag} Futures Price",            "value": _fmt(tl.futures_price), "inline": True},
        {"name": "Basis Spread",                    "value": f"{tl.basis_spread:+.2f}", "inline": True},
        # ── Spacer ───────────────────────────────────────────────
        {"name": "\u200b", "value": "\u200b", "inline": False},
        # ── Key levels (futures-translated) ─────────────────────
        {"name": f"📈 Call Wall ({tag})",    "value": _fmt(tl.call_wall),   "inline": True},
        {"name": f"📉 Put Wall ({tag})",     "value": _fmt(tl.put_wall),    "inline": True},
        {"name": f"⚡ Zero Gamma ({tag})",   "value": _fmt(tl.zero_gamma),  "inline": True},
        # ── Spacer ───────────────────────────────────────────────
        {"name": "\u200b", "value": "\u200b", "inline": False},
        # ── Expected move ────────────────────────────────────────
        {"name": f"🔼 EM Upper ({tag})",     "value": _fmt(tl.em_upper),    "inline": True},
        {"name": f"🔽 EM Lower ({tag})",     "value": _fmt(tl.em_lower),    "inline": True},
        {"name": "ATM Straddle (cash)",      "value": _fmt(tl.atm_straddle), "inline": True},
        # ── Narrative & copy line ───────────────────────────────
        {"name": "🧠 Pre-Open Plan",          "value": _plan_lines(tl), "inline": False},
    ]

    return {
        "title": f"{tl.cash_ticker} → {tag} Dealer Levels  |  {run_label}",
        "color": color,
        "fields": fields,
        "footer": {
            "text": (
                f"Total GEX: {tl.total_gex:,.0f}  "
                f"•  EM ±{_fmt(tl.em_value)}  "
                f"•  Basis: {tl.basis_spread:+.2f}"
            )
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _post_payload(url: str, payload: dict[str, Any]) -> None:
    """POST a single Discord webhook payload with error handling."""
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code in (200, 204):
            log.info(
                "Discord update sent (%d embed(s)).",
                len(payload.get("embeds", [])),
            )
        else:
            log.warning(
                "Discord webhook returned HTTP %s: %s",
                resp.status_code,
                resp.text[:300],
            )
    except requests.exceptions.Timeout:
        log.error("Discord webhook timed out.")
    except requests.exceptions.RequestException as exc:
        log.error("Discord webhook request failed: %s", exc)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def send_discord_update(
    translated_levels: list[TranslatedLevels],
    run_label: str = "",
    cash_levels: list[DealerLevels] | None = None,
    webhook_url: str | None = None,
) -> None:
    """
    Post one Discord embed per TranslatedLevels entry via webhook.

    Parameters
    ----------
    translated_levels : List of futures-translated dealer levels.
    run_label         : Human-readable label, e.g. "08:30 Pre-Market".
                        Defaults to current HH:MM ET wall-clock time.
    webhook_url       : Override URL; uses discord_webhooks.json default when None.
    """
    if not run_label:
        run_label = datetime.now().strftime("%H:%M ET")

    url = webhook_url or _load_webhook_url()

    if translated_levels:
        _post_payload(url, _copy_block_payload(translated_levels, run_label, cash_levels=cash_levels))

    embeds = [_build_embed(tl, run_label) for tl in translated_levels]

    # Discord allows up to _DISCORD_MAX_EMBEDS per POST, so batch if needed.
    for batch_start in range(0, len(embeds), _DISCORD_MAX_EMBEDS):
        batch = embeds[batch_start : batch_start + _DISCORD_MAX_EMBEDS]
        _post_payload(url, {"embeds": batch})
