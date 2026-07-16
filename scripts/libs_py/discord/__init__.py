# filepath: scripts/libs_py/discord/__init__.py
"""Discord delivery for the entire repo.

This sub-package is the single home for Discord webhook handling
in ``tvDownloadOHLC`` (audit §3.5). It started as a dedup of the
narrative chain's chunk-and-POST loop and was extended to also
own the embed/attachment contracts used by the options and
earnings pipelines.

Three families of delivery live here:

  1. **Narrative summaries** — ``send_summary`` chunks a long
     markdown body on ``\\n## `` headers and POSTs each chunk as
     a ``{"content": <chunk>}`` payload. Used by
     ``scripts/trader/{daily,trader,weekly}_narrative.py``.

  2. **Embed batches** — ``send_embeds`` accepts a list of embed
     dicts, batches them by both the 10-embed and 5600-char
     limits (with the embed-→-text fallback on HTTP 400), and
     POSTs each batch. Used by
     ``scripts/streaming/options/discord_notifier.py``.

  3. **Single payloads** — ``send_payload`` is a thin wrapper
     that accepts any pre-built ``payload`` (with optional
     multipart ``files``) and POSTs it once. Used by
     ``scripts/market_data/discord_earnings_notifier.py`` and by
     the options pipeline's macro / attachment path.

All callers that previously had their own ``_load_webhook_url``
or ``_post_payload`` now import the equivalents from this
package: ``load_webhook_url`` and ``send_payload``.

Public API:
    from scripts.libs_py.discord import (
        # High-level delivery
        send_summary,
        send_embeds,
        send_payload,
        send_with_files,
        send_message,
        # Low-level
        chunk_markdown,
        compact_embed,
        embed_batches,
        embed_char_count,
        embed_to_content,
        truncate_text,
        load_webhook_url,
        # Tier 3 — observability
        RateLimitTelemetry,
        RecordingTelemetry,
        # Constants
        DEFAULT_WEBHOOK_KEY,
        DISCORD_MAX_CHARS,
        DISCORD_MAX_EMBEDS,
        DISCORD_SAFE_EMBED_BATCH_CHARS,
    )

All ``send_*`` functions accept ``thread_id`` and
``thread_name`` keyword arguments to route the message into a
Discord thread, and ``telemetry=RateLimitTelemetry(...)`` to
emit observability events. See ``docs/architecture/DISCORD_LIBRARY.md``
for the full API contract.

See README.md in this directory for usage examples and the
chunking / batching contract.
"""
from __future__ import annotations

from typing import Final

from .chunking import chunk_markdown
from .config import (
    DEFAULT_WEBHOOK_KEY,
    DISCORD_BACKOFF_BASE_SECONDS,
    DISCORD_BACKOFF_MAX_SECONDS,
    DISCORD_BACKOFF_MULTIPLIER,
    DISCORD_MAX_CHARS,
    DISCORD_MAX_CONTENT,
    DISCORD_MAX_EMBEDS,
    DISCORD_MAX_RETRIES,
    DISCORD_RETRY_AFTER_MAX_SECONDS,
    DISCORD_RETRYABLE_STATUS_CODES,
    DISCORD_SAFE_EMBED_BATCH_CHARS,
    DISCORD_WEBHOOKS_FILENAME,
    EMBED_AUTHOR_MAX,
    EMBED_DESCRIPTION_MAX,
    EMBED_FIELD_NAME_MAX,
    EMBED_FIELD_VALUE_MAX,
    EMBED_FOOTER_MAX,
    EMBED_HTTP_TIMEOUT_SECONDS,
    EMBED_MULTIPART_TIMEOUT_SECONDS,
    EMBED_TITLE_MAX,
    HTTP_TIMEOUT_SECONDS,
    INTER_CHUNK_WAIT_SECONDS,
    SECTION_HEADER_PREFIX,
    WAIT_AFTER_BATCH_SECONDS,
    resolve_webhooks_path,
)
from .embeds import (
    compact_embed,
    embed_batches,
    embed_char_count,
    embed_to_content,
    truncate_text,
)
from .sender import send_summary
from .telemetry import (
    RateLimitTelemetry,
    RecordingTelemetry,
    TelemetryEvent,
    default_sink,
)
from .webhooks import (
    load_webhook_url,
    send_embeds,
    send_message,
    send_payload,
    send_with_files,
)

__all__: Final[tuple[str, ...]] = (
    # Main API
    "send_summary",
    "send_embeds",
    "send_payload",
    "send_with_files",
    "send_message",
    # Narrative chunking
    "chunk_markdown",
    # Embed helpers
    "compact_embed",
    "embed_batches",
    "embed_char_count",
    "embed_to_content",
    "truncate_text",
    # Webhook lookup
    "load_webhook_url",
    # Telemetry (Tier 3)
    "RateLimitTelemetry",
    "RecordingTelemetry",
    "TelemetryEvent",
    "default_sink",
    # Constants (re-exported for tests and operator-facing scripts)
    "DEFAULT_WEBHOOK_KEY",
    "DISCORD_BACKOFF_BASE_SECONDS",
    "DISCORD_BACKOFF_MAX_SECONDS",
    "DISCORD_BACKOFF_MULTIPLIER",
    "DISCORD_MAX_CHARS",
    "DISCORD_MAX_CONTENT",
    "DISCORD_MAX_EMBEDS",
    "DISCORD_MAX_RETRIES",
    "DISCORD_RETRY_AFTER_MAX_SECONDS",
    "DISCORD_RETRYABLE_STATUS_CODES",
    "DISCORD_SAFE_EMBED_BATCH_CHARS",
    "DISCORD_WEBHOOKS_FILENAME",
    "EMBED_AUTHOR_MAX",
    "EMBED_DESCRIPTION_MAX",
    "EMBED_FIELD_NAME_MAX",
    "EMBED_FIELD_VALUE_MAX",
    "EMBED_FOOTER_MAX",
    "EMBED_HTTP_TIMEOUT_SECONDS",
    "EMBED_MULTIPART_TIMEOUT_SECONDS",
    "EMBED_TITLE_MAX",
    "HTTP_TIMEOUT_SECONDS",
    "INTER_CHUNK_WAIT_SECONDS",
    "SECTION_HEADER_PREFIX",
    "WAIT_AFTER_BATCH_SECONDS",
    "resolve_webhooks_path",
)
