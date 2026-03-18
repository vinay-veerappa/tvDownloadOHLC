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
from .formatting import (
    build_coaches_note,
    build_plan,
    copy_ready_line,
    fmt,
    fmt_copy,
    futures_tag,
    traffic_light,
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


def _regime_line(regime: str) -> str:
    emoji = "🟢" if regime == "POSITIVE" else "🔴"
    return f"{emoji} **{regime} GEX**"


def _plan_lines(tl: TranslatedLevels) -> str:
    """Compact trade-plan narrative for Discord embeds."""
    tag = futures_tag(tl.futures_symbol)
    lines = build_plan(tag, tl, extended=False)
    return "\n".join(lines)


def _copy_block_payload(
    translated_levels: list[TranslatedLevels],
    run_label: str,
    cash_levels: list[DealerLevels] | None = None,
) -> dict[str, Any]:
    lines = [copy_ready_line(futures_tag(tl.futures_symbol), tl) for tl in translated_levels]
    if cash_levels:
        lines.extend(copy_ready_line(levels.ticker, levels) for levels in cash_levels)
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
    tag = futures_tag(tl.futures_symbol)

    # Regime + traffic light
    regime_emoji = {"PINNED": "📌", "TRENDING": "🚀", "COILED": "🔄", "BATTLE_ZONE": "⚔️"}.get(tl.regime_label, "⚪")
    pin_pct = f"{tl.pin_odds:.0%}" if tl.pin_odds else "N/A"
    light_color, _light_reason = traffic_light(tl)
    light_emoji = {"GREEN": "🟢", "YELLOW": "🟡", "RED": "🔴"}[light_color]

    fields: list[dict[str, Any]] = [
        {
            "name": "Regime",
            "value": f"{light_emoji} {light_color}  |  {_regime_line(tl.gex_regime)}  {regime_emoji} **{tl.regime_label}**",
            "inline": False,
        },
        # ── Prices ──────────────────────────────────────────────
        {"name": f"Cash Index ({tl.cash_ticker})", "value": fmt(tl.cash_spot),      "inline": True},
        {"name": f"{tag} Futures Price",            "value": fmt(tl.futures_price), "inline": True},
        {"name": "Basis" if tl.translation_mode == "additive" else "Scale Ratio",
         "value": f"{tl.basis_spread:+.2f}" if tl.translation_mode == "additive" else f"{tl.basis_ratio:.2f}×",
         "inline": True},
        # ── Spacer ───────────────────────────────────────────────
        {"name": "\u200b", "value": "\u200b", "inline": False},
        # ── Market Structure ─────────────────────────────────────
        {"name": "🧲 Gamma Magnet",  "value": fmt(tl.gamma_magnet), "inline": True},
        {"name": f"📌 Pin Strike ({pin_pct})", "value": fmt(tl.pin_strike), "inline": True},
        {"name": "↔️ Wall Separation",         "value": f"{fmt(tl.wall_separation)} pts", "inline": True},
        # ── Spacer ───────────────────────────────────────────────
        {"name": "\u200b", "value": "\u200b", "inline": False},
        # ── Key levels (futures-translated) ─────────────────────
        {"name": f"📈 Call Wall ({tag})",    "value": fmt(tl.call_wall),   "inline": True},
        {"name": f"📉 Put Wall ({tag})",     "value": fmt(tl.put_wall),    "inline": True},
        {"name": f"⚡ Zero Gamma ({tag})",   "value": fmt(tl.zero_gamma),  "inline": True},
        # ── Spacer ───────────────────────────────────────────────
        {"name": "\u200b", "value": "\u200b", "inline": False},
        # ── Expected move ────────────────────────────────────────
        {"name": f"🔼 EM Upper ({tag})",     "value": fmt(tl.em_upper),    "inline": True},
        {"name": f"🔽 EM Lower ({tag})",     "value": fmt(tl.em_lower),    "inline": True},
        {"name": "ATM Straddle (cash)",      "value": fmt(tl.atm_straddle), "inline": True},
        # ── Compact execution plan ──────────────────────────────
        {"name": "🧠 Execution Plan",          "value": _plan_lines(tl), "inline": False},
    ]

    return {
        "title": f"{tl.cash_ticker} → {tag} Dealer Levels  |  {run_label}",
        "color": color,
        "fields": fields,
        "footer": {
            "text": (
                f"Total GEX: {tl.total_gex:,.0f}  "
                f"•  EM ±{fmt(tl.em_value)}  "
                f"•  {'Basis: ' + f'{tl.basis_spread:+.2f}' if tl.translation_mode == 'additive' else 'Ratio: ' + f'{tl.basis_ratio:.2f}×'}  "
                f"•  Vanna: {tl.net_vanna_exposure:,.0f}"
            )
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _build_coaches_note_payloads(
    translated_levels: list[TranslatedLevels],
    run_label: str,
) -> list[dict[str, Any]]:
    """
    Build one Discord message per instrument with the full Coach's Note.

    Each instrument gets its own message so nothing is truncated — a typical
    single-instrument note runs 800–1200 characters, well within the 2000
    character Discord content limit.
    """
    payloads: list[dict[str, Any]] = []

    for tl in translated_levels:
        tag = futures_tag(tl.futures_symbol)
        note = build_coaches_note(tag, tl)
        content = f"**🏋️ Coach's Briefing — {tag}  |  {run_label}**\n\n{note}"

        if len(content) > _DISCORD_MAX_CONTENT:
            content = content[:_DISCORD_MAX_CONTENT - 20] + "\n\n*(truncated)*"

        payloads.append({"content": content})

    return payloads


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

    # Coach's briefing — plain-English game plan as a separate message
    if translated_levels:
        for payload in _build_coaches_note_payloads(translated_levels, run_label):
            _post_payload(url, payload)


def send_regime_change_alert(
    alert_text: str,
    webhook_url: str | None = None,
) -> None:
    """
    Post a regime-change alert to Discord.

    Parameters
    ----------
    alert_text  : Pre-formatted alert string from state_tracker.format_change_alert().
    webhook_url : Override URL; uses discord_webhooks.json default when None.
    """
    if not alert_text:
        return

    url = webhook_url or _load_webhook_url()

    content = alert_text
    if len(content) > _DISCORD_MAX_CONTENT:
        content = content[:_DISCORD_MAX_CONTENT - 20] + "\n\n*(truncated)*"

    _post_payload(url, {"content": content})