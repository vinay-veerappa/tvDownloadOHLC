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

log = logging.getLogger(__name__)

# Max embeds Discord accepts per webhook call.
_DISCORD_MAX_EMBEDS = 10


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


def _regime_line(regime: str) -> str:
    emoji = "🟢" if regime == "POSITIVE" else "🔴"
    return f"{emoji} **{regime} GEX**"


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
    embeds = [_build_embed(tl, run_label) for tl in translated_levels]

    # Discord allows up to _DISCORD_MAX_EMBEDS per POST, so batch if needed.
    for batch_start in range(0, len(embeds), _DISCORD_MAX_EMBEDS):
        batch = embeds[batch_start : batch_start + _DISCORD_MAX_EMBEDS]
        _post_payload(url, {"embeds": batch})
