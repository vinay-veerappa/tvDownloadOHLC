# filepath: scripts/libs_py/discord/embeds.py
"""Discord embed construction, sizing, and batching.

The embed contract for the repo has two large consumers:

  - ``scripts/streaming/options/discord_notifier.py`` — produces one
    embed per dealer-levels entry, then batches them by both the
    10-embed and 5600-character limits before POSTing.

  - ``scripts/market_data/discord_earnings_notifier.py`` — produces
    a single embed per mode (EOD / EOW / RECAP) and POSTs it
    directly.

Both call sites historically had their own copy of the embed
helpers (``_compact_embed``, ``_embed_batches``, ``_embed_char_count``,
``_truncate_text``, ``_embed_to_content``). This module centralises
all of those so the embed semantics — particularly the
HTTP 400 → plain-text fallback that the options pipeline relies
on — live in exactly one place.

Every function here is pure (no I/O) and side-effect-free. That
keeps the batch / fallback decisions testable without mocking
``requests``.
"""
from __future__ import annotations

import logging
from typing import Any

from .config import (
    DISCORD_MAX_CONTENT,
    DISCORD_MAX_EMBEDS,
    DISCORD_SAFE_EMBED_BATCH_CHARS,
    EMBED_AUTHOR_MAX,
    EMBED_DESCRIPTION_MAX,
    EMBED_FIELD_NAME_MAX,
    EMBED_FIELD_VALUE_MAX,
    EMBED_FOOTER_MAX,
    EMBED_TITLE_MAX,
)

log = logging.getLogger(__name__)

__all__ = (
    "truncate_text",
    "embed_char_count",
    "compact_embed",
    "embed_to_content",
    "embed_batches",
)


def truncate_text(value: str, max_len: int) -> str:
    """Truncate ``value`` to ``max_len`` characters.

    Adds a ``...`` suffix when truncation occurs. If ``max_len`` is
    too small to fit the suffix, the function falls back to a hard
    cut. Mirrors the legacy behaviour used by the options notifier
    for fields, titles, and footer text.
    """
    if len(value) <= max_len:
        return value
    if max_len <= 3:
        return value[:max_len]
    return value[: max_len - 3] + "..."


def embed_char_count(embed: dict[str, Any]) -> int:
    """Return the per-embed character count under Discord's rules.

    Counts ``title`` + ``description`` + ``footer.text`` +
    ``author.name`` + every ``field.{name,value}``. Author and
    footer are tolerated if missing or non-dict (the options
    pipeline is permissive about that). The total is used to keep
    a batch of embeds under
    :data:`DISCORD_SAFE_EMBED_BATCH_CHARS` (default 5600).
    """
    total = 0
    total += len(str(embed.get("title", "")))
    total += len(str(embed.get("description", "")))

    footer = embed.get("footer") or {}
    if isinstance(footer, dict):
        total += len(str(footer.get("text", "")))

    author = embed.get("author") or {}
    if isinstance(author, dict):
        total += len(str(author.get("name", "")))

    for field in embed.get("fields", []) or []:
        if not isinstance(field, dict):
            continue
        total += len(str(field.get("name", "")))
        total += len(str(field.get("value", "")))
    return total


def compact_embed(
    embed: dict[str, Any],
    max_chars: int = DISCORD_SAFE_EMBED_BATCH_CHARS,
) -> dict[str, Any]:
    """Trim an embed down to Discord-safe limits while preserving context.

    Behaviour:

    1. Title, description, footer, fields, author are each truncated
       to their documented Discord caps.
    2. If the resulting embed still exceeds ``max_chars`` (the per-
       batch budget), the function pops the lowest-priority fields
       from the end. As a last resort it re-truncates the surviving
       first field to 512 and then 256 chars before giving up.

    Returns a *new* dict; the input is never mutated. This matches
    the legacy in-line behaviour used by
    ``scripts/streaming/options/discord_notifier.py``.
    """
    compact: dict[str, Any] = dict(embed)

    title = str(compact.get("title", ""))
    if title:
        compact["title"] = truncate_text(title, EMBED_TITLE_MAX)

    description = str(compact.get("description", ""))
    if description:
        compact["description"] = truncate_text(description, EMBED_DESCRIPTION_MAX)

    footer = compact.get("footer")
    if isinstance(footer, dict):
        footer = dict(footer)
        footer["text"] = truncate_text(str(footer.get("text", "")), EMBED_FOOTER_MAX)
        compact["footer"] = footer

    author = compact.get("author")
    if isinstance(author, dict):
        author = dict(author)
        author["name"] = truncate_text(str(author.get("name", "")), EMBED_AUTHOR_MAX)
        compact["author"] = author

    raw_fields = compact.get("fields") or []
    fields: list[dict[str, Any]] = []
    for field in raw_fields:
        if not isinstance(field, dict):
            continue
        fields.append(
            {
                "name": truncate_text(str(field.get("name", "\u200b")), EMBED_FIELD_NAME_MAX),
                "value": truncate_text(str(field.get("value", "\u200b")), EMBED_FIELD_VALUE_MAX),
                "inline": bool(field.get("inline", False)),
            }
        )
    compact["fields"] = fields

    # If we still exceed the batch budget, drop fields from the end
    # until we fit. The last-resort truncation ladder matches the
    # legacy code.
    while embed_char_count(compact) > max_chars and compact.get("fields"):
        fields = list(compact["fields"])
        if not fields:
            break
        if len(fields) > 1:
            fields.pop()
        else:
            fields[0]["value"] = truncate_text(str(fields[0].get("value", "")), 512)
            if embed_char_count(compact) > max_chars:
                fields[0]["value"] = truncate_text(str(fields[0].get("value", "")), 256)
                break
        compact["fields"] = fields

    return compact


def embed_to_content(embed: dict[str, Any], max_len: int = DISCORD_MAX_CONTENT) -> str:
    """Convert a rejected embed into a plain-text fallback payload.

    Used by :func:`scripts.libs_py.discord.webhooks.send_payload`
    when Discord returns HTTP 400 for an embed payload — the
    options pipeline's resilience contract is "if the rich embed
    is rejected, fall back to a text summary of the same data so
    the operator still sees the briefing".

    Spacer fields (``name == '\u200b'``) are flattened to their
    value line so the text reads cleanly.
    """
    parts: list[str] = []
    title = str(embed.get("title", "")).strip()
    if title:
        parts.append(f"**{title}**")

    for field in embed.get("fields", []) or []:
        if not isinstance(field, dict):
            continue
        name = str(field.get("name", "")).strip()
        value = str(field.get("value", "")).strip()
        if not name and not value:
            continue
        if name == "\u200b":
            parts.append(value)
        else:
            parts.append(f"**{name}:** {value}")

    content = "\n".join(parts)
    return truncate_text(content, max_len)


def embed_batches(
    embeds: list[dict[str, Any]],
    max_embeds: int = DISCORD_MAX_EMBEDS,
    max_batch_chars: int = DISCORD_SAFE_EMBED_BATCH_CHARS,
) -> list[list[dict[str, Any]]]:
    """Split ``embeds`` into batches that respect both Discord limits.

    Each batch is at most ``max_embeds`` embeds and at most
    ``max_batch_chars`` total characters (per
    :func:`embed_char_count`). Every embed is first compacted via
    :func:`compact_embed` so a single over-budget embed never
    blocks the whole batch.

    Returns an empty list when ``embeds`` is empty.
    """
    if not embeds:
        return []

    batches: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    current_chars = 0

    for raw_embed in embeds:
        embed = compact_embed(raw_embed, max_chars=max_batch_chars)
        embed_chars = embed_char_count(embed)

        should_flush = bool(current) and (
            len(current) >= max_embeds
            or current_chars + embed_chars > max_batch_chars
        )
        if should_flush:
            batches.append(current)
            current = []
            current_chars = 0

        current.append(embed)
        current_chars += embed_chars

    if current:
        batches.append(current)
    return batches
