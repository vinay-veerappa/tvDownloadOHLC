# filepath: scripts/libs_py/discord/config.py
"""Constants and config loader for the Discord notifier sub-package.

The values here were previously duplicated across three files
(`daily_narrative.py`, `trader_narrative.py`, `weekly_narrative.py`).
A single source of truth means:
  - Changing the chunk-size limit (e.g. if Discord relaxes its 2000 char
    cap to 4000) is a one-line edit here.
  - Tests can override the webhook path and chunk size via monkeypatch
    on the public symbols in this module.

KEEP IN SYNC with:
  - `discord_webhooks.json` at the repo root (the file the webhooks
    loader reads from).
  - `scripts/trader/config/narrative_stats.yaml` if a future config
    refactor moves these knobs into YAML.
"""
from __future__ import annotations

from pathlib import Path

# Discord's hard character limit per message. We send 1900 (not 2000)
# to leave a safety margin for any code-point expansion that happens
# during JSON serialization of the `content` field.
DISCORD_MAX_CHARS: int = 1900

# Path to the JSON file containing webhook URL lookups, relative to
# the repo root. The previous duplicated code hard-coded the same
# string three times; it's now a single constant.
DISCORD_WEBHOOKS_FILENAME: str = "discord_webhooks.json"

# Default webhook key used by the narrative chain (open/EOD/weekly).
# Operators can override per-call via the `webhook_key` argument.
DEFAULT_WEBHOOK_KEY: str = "macro-alerts"

# HTTP timeout (seconds) for a single chunk POST. Same value as the
# previous in-line code.
HTTP_TIMEOUT_SECONDS: int = 15

# Header marker the chunker splits on. Markdown sections start with
# `## ` (two hashes + space). The chunker splits on the literal
# newline-prefixed form (`\n## `) so the first section keeps its
# leading content.
SECTION_HEADER_PREFIX: str = "\n## "

# ---------------------------------------------------------------------------
# Embed payload limits (Discord hard caps).
# ---------------------------------------------------------------------------
# Discord rejects webhook calls with more than 10 embeds.
DISCORD_MAX_EMBEDS: int = 10

# Discord's hard cap on the `content` field length (per message). The
# narrative chain uses 1900 to leave a safety margin; the embed consumer
# historically used the full 2000, and we keep that here for the embed
# path since the embed path already enforces a separate batch-level
# character budget. Tests can override via the function-level parameter.
DISCORD_MAX_CONTENT: int = 2000

# Conservative per-batch char budget. Discord's true per-message limit
# is 6000 total chars across all embeds, but in practice the options
# pipeline has hit 400-rejection territory above 5600. We keep that
# number as a stable public constant.
DISCORD_SAFE_EMBED_BATCH_CHARS: int = 5600

# Discord's documented per-field limits — used by the embed compactor
# to safely trim an embed to its tightest allowable shape.
EMBED_TITLE_MAX: int = 256
EMBED_DESCRIPTION_MAX: int = 4096
EMBED_FOOTER_MAX: int = 2048
EMBED_AUTHOR_MAX: int = 256
EMBED_FIELD_NAME_MAX: int = 256
EMBED_FIELD_VALUE_MAX: int = 1024

# HTTP timeout for embed/multipart webhook calls. Slightly higher than
# the narrative chain (15s) because attachments can be slow on the
# uploads leg.
EMBED_HTTP_TIMEOUT_SECONDS: int = 20

# Multipart upload timeout (larger payloads including images).
EMBED_MULTIPART_TIMEOUT_SECONDS: int = 20


# ---------------------------------------------------------------------------
# Retry / rate-limit / wait policy (Tier-2 hardening).
# ---------------------------------------------------------------------------
# Discord enforces two kinds of rate limits on webhooks:
#
#   1. Per-webhook: ~5 messages / 2 seconds.
#   2. Per-route: 429 with ``Retry-After`` (seconds) and
#      ``X-RateLimit-Reset-After`` headers.
#
# On a 429 we honour the server-supplied delay (capped by
# :data:`DISCORD_RETRY_AFTER_MAX_SECONDS` to avoid 24-hour holds).
# On a 5xx we use exponential backoff starting at
# :data:`DISCORD_BACKOFF_BASE_SECONDS` and growing by
# :data:`DISCORD_BACKOFF_MULTIPLIER` up to
# :data:`DISCORD_BACKOFF_MAX_SECONDS`.
#
# Operators can disable retries globally by passing
# ``max_retries=0`` to :func:`send_payload`.

DISCORD_MAX_RETRIES: int = 3
DISCORD_RETRY_AFTER_MAX_SECONDS: float = 60.0
DISCORD_BACKOFF_BASE_SECONDS: float = 1.0
DISCORD_BACKOFF_MULTIPLIER: float = 3.0
DISCORD_BACKOFF_MAX_SECONDS: float = 30.0

# Multi-message / multi-batch pacing. Discord's per-webhook
# rate limit is ~5 messages / 2 seconds. :data:`INTER_CHUNK_WAIT_SECONDS`
# is the small sleep inserted between successive
# ``send_summary`` / ``send_embeds`` POSTs when the caller opts
# in via ``wait=True``. :data:`WAIT_AFTER_BATCH_SECONDS` is the
# longer sleep inserted after each *batch* (used by ``send_embeds``
# which can fire 10-embed batches back to back).
INTER_CHUNK_WAIT_SECONDS: float = 0.5
WAIT_AFTER_BATCH_SECONDS: float = 1.0

# Discord HTTP status codes we treat as retryable. 429 is rate
# limited (special-cased with ``Retry-After``). 5xx is transient.
DISCORD_RETRYABLE_STATUS_CODES: tuple[int, ...] = (429, 500, 502, 503, 504)


def resolve_webhooks_path(repo_root: Path) -> Path:
    """Return the absolute path to the webhooks JSON file.

    Centralised so the sender doesn't have to know the repo-root
    contract — it just needs a `Path` to a JSON file with the
    `{"<key>": "<webhook_url>"}` shape.
    """
    return Path(repo_root) / DISCORD_WEBHOOKS_FILENAME
