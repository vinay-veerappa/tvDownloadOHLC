# filepath: scripts/libs_py/discord/sender.py
"""Discord webhook delivery.

This module owns:
  - Loading the webhook URL for a given key from
    `discord_webhooks.json` (path resolved via `config.py`).
  - Chunking the message body via `chunk_markdown()`.
  - POSTing each chunk to the webhook with the standard
    `{"content": <chunk>}` payload shape.

The narrative chain (daily / trader / weekly narratives) previously
implemented this verbatim in three files (audit §3.5). The new public
API surface is:

  from scripts.libs_py.discord import send_summary

  send_summary(summary, webhook_key="macro-alerts", repo_root=REPO_ROOT)

A `requests` mock is injected for tests via the optional `poster`
keyword argument (defaulting to `requests.post`). All other behaviour
matches the previous in-line code, including:
  - Single WARNING when the webhook key is missing.
  - INFO log per delivered chunk.
  - WARNING per failed chunk (does not raise — Discord is
    best-effort, mirroring the previous semantics).
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Callable, Optional

from .chunking import chunk_markdown
from .config import (
    DEFAULT_WEBHOOK_KEY,
    DISCORD_MAX_CHARS,
    HTTP_TIMEOUT_SECONDS,
    INTER_CHUNK_WAIT_SECONDS,
    resolve_webhooks_path,
)
from .telemetry import RateLimitTelemetry

log = logging.getLogger(__name__)


def _load_webhook_url(
    webhooks_path: Path,
    webhook_key: str,
) -> Optional[str]:
    """Read the webhook URL for `webhook_key` from `webhooks_path`.

    Returns `None` if the file is missing or the key is not present.
    Never raises — Discord delivery is best-effort and the previous
    in-line code was equally tolerant.
    """
    if not webhooks_path.exists():
        return None
    try:
        with open(webhooks_path, "r", encoding="utf-8") as f:
            webhooks = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    url = webhooks.get(webhook_key)
    if not url:
        return None
    return str(url)


def send_summary(
    summary: str,
    webhook_key: str = DEFAULT_WEBHOOK_KEY,
    repo_root: Optional[Path] = None,
    *,
    webhooks_path: Optional[Path] = None,
    poster: Optional[Callable[..., object]] = None,
    max_chars: int = DISCORD_MAX_CHARS,
    wait: bool = False,
    sleep_fn: Callable[[float], None] = time.sleep,
    thread_id: Optional[str] = None,
    thread_name: Optional[str] = None,
    telemetry: Optional[RateLimitTelemetry] = None,
) -> int:
    """Send `summary` to Discord via the configured webhook.

    Args:
        summary: The full markdown body to deliver.
        webhook_key: Lookup key in `discord_webhooks.json`
            (e.g. `"macro-alerts"`, `"alerts"`, `"option-levels"`).
        repo_root: Filesystem root used to locate the webhooks
            JSON file. Required unless `webhooks_path` is given
            explicitly (the latter is the test-friendly path).
        webhooks_path: Direct override for the webhooks file path.
            Takes precedence over `repo_root`.
        poster: The HTTP POST function. Defaults to
            `requests.post`. Tests pass a mock that records the
            calls instead of actually firing HTTP requests.
        max_chars: Chunk-size cap. Defaults to the Discord
            constant in `config.py`.
        wait: If ``True``, insert a small
            :data:`INTER_CHUNK_WAIT_SECONDS` sleep between
            successful chunks. Use this when sending >5
            chunks to stay under Discord's per-webhook
            rate limit (~5 messages / 2 s).
        thread_id: Optional Discord thread id to route each
            chunk to (Tier 3). Mutates the POST payload;
            ignored if no chunk is sent.
        thread_name: Optional Discord thread name; when
            set, the first chunk creates a new thread
            (forum-channel only) under this name.
        telemetry: Optional :class:`RateLimitTelemetry` to
            receive per-chunk and per-retry events. Defaults
            to ``None`` (no overhead). When supplied, only
            the success/failure outcomes are recorded; the
            ``send_summary`` direct POST path does not retry,
            so retry/backoff counters are N/A.

    Returns:
        The number of chunks successfully delivered. A return of 0
        is expected when (a) the webhook key is missing or
        (b) every chunk POST raised. The caller can use the
        return value to gate follow-up steps if it cares; the
        previous in-line code did not, so existing callers
        continue to treat the function as fire-and-forget.

    Side effects:
        Logs INFO on success per chunk, WARNING on missing
        webhook and on per-chunk POST failure. Never raises.
    """
    # Resolve the webhooks file path. Test paths and operator
    # overrides win over the `repo_root` derivation.
    if webhooks_path is None:
        if repo_root is None:
            log.warning(
                "Discord sender: neither webhooks_path nor repo_root "
                "given — skipping delivery."
            )
            return 0
        webhooks_path = resolve_webhooks_path(repo_root)

    webhook_url = _load_webhook_url(webhooks_path, webhook_key)
    if not webhook_url:
        log.warning(
            "No Discord webhook found for key '%s' — skipping Discord.",
            webhook_key,
        )
        return 0

    chunks = chunk_markdown(summary, max_chars=max_chars)

    # Lazily resolve the HTTP poster. The default import is
    # deferred to keep module import cheap and to allow tests
    # to inject a mock without monkeypatching `requests`.
    if poster is None:
        try:
            import requests  # type: ignore[import-untyped]
        except ImportError:  # pragma: no cover
            log.warning("`requests` not installed — skipping Discord delivery.")
            return 0
        poster = requests.post

    delivered = 0
    for i, chunk in enumerate(chunks, start=1):
        # Build the per-chunk payload (Tier 3 supports
        # thread routing here).
        payload: dict[str, object] = {"content": chunk}
        if thread_id is not None:
            payload["thread_id"] = str(thread_id)
        if thread_name is not None:
            payload["thread_name"] = str(thread_name)
        try:
            poster(
                webhook_url,
                json=payload,
                timeout=HTTP_TIMEOUT_SECONDS,
            )
            log.info(
                "  Discord chunk %d/%d sent to %s",
                i,
                len(chunks),
                webhook_key,
            )
            delivered += 1
            if telemetry is not None:
                telemetry.on_attempt(webhook_url, 200, i)
                telemetry.on_success(webhook_url, i)
            if wait and i < len(chunks):
                # Don't sleep after the final chunk.
                sleep_fn(INTER_CHUNK_WAIT_SECONDS)
        except Exception as exc:  # noqa: BLE001 — best-effort
            log.warning(
                "  Discord delivery failed for chunk %d: %s",
                i,
                exc,
            )
            if telemetry is not None:
                telemetry.on_attempt(webhook_url, None, i)
                telemetry.on_failure(webhook_url, None, i, "network")
    return delivered
