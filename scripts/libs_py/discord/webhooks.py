"""Low-level Discord webhook delivery (embed + multipart + retry).

This module is the I/O layer for the Discord consumers in the
repo (narrative summaries, options-pipeline embeds, earnings
embeds, strategy-engine cards, analysis/maintenance reports,
chart uploads). After the Tier-1+2 refactor it is the *only*
place that talks HTTP to Discord — every other module goes
through this one.

Public entry points:

  * :func:`send_payload` — single webhook POST (JSON or
    multipart) with built-in retry-on-429/5xx and
    embed-→-text fallback. Used by the earnings pipeline,
    the options macro/attachment path, and the analysis +
    strategy-engine consumers.

  * :func:`send_embeds` — batch-aware embed POST. Takes a
    list of embed dicts, runs them through
    :func:`embed_batches` from :mod:`scripts.libs_py.discord.
    embeds`, and POSTs each batch with the same retry policy
    and fallback behaviour. Used by the options levels and
    daily-curve pipelines.

  * :func:`send_with_files` — convenience wrapper for
    "one message + N file attachments" uploads. Used by the
    strategy-engine analytics + paper_exec traders and by
    the daily-prep chart upload path. Built on top of
    :func:`send_payload` so it inherits the same retry
    policy.

  * :func:`send_message` — high-level text-or-text+files
    helper that chunks long messages, optionally attaches
    files, and POSTs. Replaces
    ``scripts.utils.discord_notify.send_message``.

  * :func:`load_webhook_url` — look up a webhook URL by key
    in ``discord_webhooks.json``.

All functions accept a ``poster`` keyword argument so tests
can inject a mock without monkeypatching globals. All accept
a ``wait=True`` flag (where applicable) that inserts a small
sleep between successive POSTs to stay under Discord's
per-webhook ~5 msg / 2 s rate limit.
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Callable, Iterable, Optional, Union

from .chunking import chunk_markdown
from .config import (
    DEFAULT_WEBHOOK_KEY,
    DISCORD_BACKOFF_BASE_SECONDS,
    DISCORD_BACKOFF_MAX_SECONDS,
    DISCORD_BACKOFF_MULTIPLIER,
    DISCORD_MAX_CHARS,
    DISCORD_MAX_RETRIES,
    DISCORD_RETRY_AFTER_MAX_SECONDS,
    DISCORD_RETRYABLE_STATUS_CODES,
    EMBED_HTTP_TIMEOUT_SECONDS,
    EMBED_MULTIPART_TIMEOUT_SECONDS,
    INTER_CHUNK_WAIT_SECONDS,
    WAIT_AFTER_BATCH_SECONDS,
    resolve_webhooks_path,
)
from .embeds import embed_batches, embed_to_content
from .telemetry import RateLimitTelemetry

log = logging.getLogger(__name__)

__all__ = (
    "send_payload",
    "send_embeds",
    "send_with_files",
    "send_message",
    "load_webhook_url",
)


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------
Poster = Callable[..., Any]
FileInput = Union[str, Path, tuple[str, bytes, str]]


# ---------------------------------------------------------------------------
# Thread injection helper
# ---------------------------------------------------------------------------
def _apply_thread(
    payload: dict[str, Any],
    *,
    thread_id: Optional[str],
    thread_name: Optional[str],
) -> None:
    """Inject ``thread_id`` / ``thread_name`` into ``payload`` in place.

    Discord webhook payloads accept both:

    * ``thread_id`` — route the message to an existing thread
      (forum channel or text channel with active threads).
    * ``thread_name`` — auto-create a thread from the first
      message in a channel (forum-channel only).

    Tier 3 surfaces these on every public send function so the
    caller doesn't have to mutate the payload dict themselves.
    """
    if thread_id is not None:
        payload["thread_id"] = str(thread_id)
    if thread_name is not None:
        payload["thread_name"] = str(thread_name)


# ---------------------------------------------------------------------------
# Webhook lookup
# ---------------------------------------------------------------------------
def load_webhook_url(
    webhook_key: str,
    *,
    repo_root: Optional[Path] = None,
    webhooks_path: Optional[Path] = None,
) -> Optional[str]:
    """Look up the Discord webhook URL for ``webhook_key``.

    Returns ``None`` if the file is missing, the JSON is invalid,
    or the key is not present. Never raises — Discord delivery is
    best-effort and the previous in-line code in both pipelines
    was equally tolerant.

    Provide either ``repo_root`` (resolved via
    :func:`scripts.libs_py.discord.config.resolve_webhooks_path`)
    or a direct ``webhooks_path`` override (the test-friendly
    path).
    """
    if webhooks_path is None:
        if repo_root is None:
            return None
        webhooks_path = resolve_webhooks_path(repo_root)

    if not webhooks_path.exists():
        return None
    try:
        with open(webhooks_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None

    url = data.get(webhook_key)
    if not url:
        return None
    return str(url)


# ---------------------------------------------------------------------------
# Default poster
# ---------------------------------------------------------------------------
def _default_poster(
    url: str,
    *,
    json: Any = None,
    data: Any = None,
    files: Any = None,
    timeout: float = 10,
) -> Any:
    """Lazy import + invoke of ``requests.post``.

    We don't import ``requests`` at module load time so the rest
    of the sub-package is importable in environments that lack
    the dependency (e.g. lightweight test runners).
    """
    import requests  # type: ignore[import-untyped]  # local import

    if files is not None:
        return requests.post(url, data=data, files=files, timeout=timeout)
    return requests.post(url, json=json, timeout=timeout)


# ---------------------------------------------------------------------------
# Retry helpers
# ---------------------------------------------------------------------------
def _retry_after_seconds(resp: Any) -> Optional[float]:
    """Extract the ``Retry-After`` value from a Discord 429 response.

    Discord sends it as either a float (seconds) or an HTTP-date
    header. The ``X-RateLimit-Reset-After`` header is the more
    precise source for webhook rate limits; we prefer it.

    Returns ``None`` if no useful hint is present, or the value
    is unparseable.
    """
    headers = getattr(resp, "headers", None) or {}
    candidates = (
        headers.get("X-RateLimit-Reset-After"),
        headers.get("Retry-After"),
    )
    for raw in candidates:
        if raw is None:
            continue
        try:
            val = float(raw)
            if val >= 0:
                return val
        except (TypeError, ValueError):
            continue
    return None


def _sleep_fn(seconds: float) -> None:
    """Test seam: ``send_payload`` sleeps via this so tests can
    patch it to a no-op and assert the *number* of sleeps without
    actually waiting.
    """
    if seconds > 0:
        time.sleep(seconds)


def _post_once(
    url: str,
    payload: dict[str, Any],
    *,
    files: Any,
    poster: Poster,
    timeout: float,
) -> Any:
    """Single POST (no retry, no fallback). Returns the response."""
    if files:
        return poster(
            url,
            data={"payload_json": json.dumps(payload)},
            files=files,
            timeout=timeout,
        )
    return poster(url, json=payload, timeout=timeout)


def _post_payload_with_retry(
    url: str,
    payload: dict[str, Any],
    *,
    files: Any = None,
    poster: Optional[Poster] = None,
    max_retries: int = DISCORD_MAX_RETRIES,
    sleep_fn: Callable[[float], None] = _sleep_fn,
    telemetry: Optional[RateLimitTelemetry] = None,
) -> bool:
    """POST ``payload`` to ``url`` with retry-on-429/5xx.

    This is the I/O primitive used by the embed-→-text fallback
    in :func:`send_payload`. The fallback POSTs are not retried
    (a 400 means the payload shape is wrong, not a transient
    error) so this is also exposed for callers that want
    "retry-once-then-give-up" semantics.

    When ``telemetry`` is supplied, every attempt and every
    retry is reported to it. See :class:`RateLimitTelemetry`.
    """
    poster = poster or _default_poster
    timeout = EMBED_MULTIPART_TIMEOUT_SECONDS if files else EMBED_HTTP_TIMEOUT_SECONDS

    attempt = 0
    while True:
        try:
            resp = _post_once(
                url, payload, files=files, poster=poster, timeout=timeout
            )
        except Exception as exc:  # network errors, mock failures
            msg = str(exc).lower()
            if "timeout" in msg or "timed out" in msg:
                log.error("Discord webhook timed out.")
            else:
                log.error("Discord webhook request failed: %s", exc)
            if telemetry is not None:
                telemetry.on_attempt(url, None, attempt + 1)
            if attempt >= max_retries:
                if telemetry is not None:
                    telemetry.on_failure(url, None, attempt + 1, "network")
                return False
            backoff = min(
                DISCORD_BACKOFF_MAX_SECONDS,
                DISCORD_BACKOFF_BASE_SECONDS * (DISCORD_BACKOFF_MULTIPLIER ** attempt),
            )
            log.info(
                "Discord retrying after network error (attempt %d/%d, sleep %.1fs).",
                attempt + 1, max_retries, backoff,
            )
            if telemetry is not None:
                telemetry.on_retry_scheduled(
                    url, attempt + 1, backoff, "network"
                )
            sleep_fn(backoff)
            attempt += 1
            continue

        status = getattr(resp, "status_code", None)
        if status in (200, 204):
            if telemetry is not None:
                telemetry.on_attempt(url, status, attempt + 1)
                telemetry.on_success(url, attempt + 1)
            return True

        if telemetry is not None:
            telemetry.on_attempt(url, status, attempt + 1)

        if status in DISCORD_RETRYABLE_STATUS_CODES and attempt < max_retries:
            if status == 429:
                hint = _retry_after_seconds(resp)
                delay = (
                    min(hint, DISCORD_RETRY_AFTER_MAX_SECONDS)
                    if hint is not None
                    else min(
                        DISCORD_BACKOFF_MAX_SECONDS,
                        DISCORD_BACKOFF_BASE_SECONDS
                        * (DISCORD_BACKOFF_MULTIPLIER ** attempt),
                    )
                )
                reason = "429"
                log.warning(
                    "Discord 429 rate-limited (attempt %d/%d, sleep %.1fs).",
                    attempt + 1, max_retries, delay,
                )
            else:
                delay = min(
                    DISCORD_BACKOFF_MAX_SECONDS,
                    DISCORD_BACKOFF_BASE_SECONDS
                    * (DISCORD_BACKOFF_MULTIPLIER ** attempt),
                )
                reason = "5xx"
                log.warning(
                    "Discord HTTP %s (attempt %d/%d, sleep %.1fs).",
                    status, attempt + 1, max_retries, delay,
                )
            if telemetry is not None:
                telemetry.on_retry_scheduled(
                    url, attempt + 1, delay, reason
                )
            sleep_fn(delay)
            attempt += 1
            continue

        if telemetry is not None:
            telemetry.on_failure(
                url, status, attempt + 1, str(status) if status else "error"
            )
        return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def send_payload(
    url: str,
    payload: dict[str, Any],
    *,
    files: Any = None,
    poster: Optional[Poster] = None,
    allow_embed_fallback: bool = True,
    max_retries: int = DISCORD_MAX_RETRIES,
    sleep_fn: Callable[[float], None] = _sleep_fn,
    thread_id: Optional[str] = None,
    thread_name: Optional[str] = None,
    telemetry: Optional[RateLimitTelemetry] = None,
) -> bool:
    """POST ``payload`` (JSON or multipart) to a Discord webhook.

    Returns ``True`` on HTTP 200/204 (after any retries). Returns
    ``False`` on any other status, on a network exception, or
    after exhausting retries.

    When ``allow_embed_fallback`` is ``True`` and Discord returns
    HTTP 400 for a payload that contains ``embeds`` (and is *not*
    a multipart file upload), each embed is individually
    converted to plain text via
    :func:`scripts.libs_py.discord.embeds.embed_to_content` and
    re-POSTed. The overall result is ``True`` only if every
    fallback POST succeeds — mirroring the legacy
    ``_post_payload`` contract in the options notifier. Fallback
    POSTs are not retried (a 400 means the payload shape is
    wrong, not a transient error).

    The ``poster`` argument is the test seam; default is
    ``requests.post`` invoked with the appropriate kwarg for the
    payload kind. The ``sleep_fn`` argument is the test seam for
    the retry backoff (default :func:`time.sleep`).

    Tier 3 additions: ``thread_id`` and ``thread_name`` are
    injected into the JSON payload (Discord routes to / creates
    a thread accordingly). ``telemetry``, when supplied,
    receives per-attempt and per-retry events.
    """
    if not url:
        log.warning("send_payload called with empty URL; skipping.")
        return False

    # Thread routing (Tier 3) — inject into the payload so the
    # caller doesn't have to mutate the dict themselves.
    _apply_thread(payload, thread_id=thread_id, thread_name=thread_name)

    poster = poster or _default_poster
    timeout = EMBED_MULTIPART_TIMEOUT_SECONDS if files else EMBED_HTTP_TIMEOUT_SECONDS
    last_status: Optional[int] = None
    last_text: str = ""
    attempt = 0

    while True:
        try:
            resp = _post_once(
                url, payload, files=files, poster=poster, timeout=timeout
            )
        except Exception as exc:  # network errors
            msg = str(exc).lower()
            if "timeout" in msg or "timed out" in msg:
                log.error("Discord webhook timed out.")
            else:
                log.error("Discord webhook request failed: %s", exc)
            if telemetry is not None:
                telemetry.on_attempt(url, None, attempt + 1)
            if attempt >= max_retries:
                if telemetry is not None:
                    telemetry.on_failure(url, None, attempt + 1, "network")
                return False
            backoff = min(
                DISCORD_BACKOFF_MAX_SECONDS,
                DISCORD_BACKOFF_BASE_SECONDS * (DISCORD_BACKOFF_MULTIPLIER ** attempt),
            )
            log.info(
                "Discord retrying after network error (attempt %d/%d, sleep %.1fs).",
                attempt + 1, max_retries, backoff,
            )
            if telemetry is not None:
                telemetry.on_retry_scheduled(
                    url, attempt + 1, backoff, "network"
                )
            sleep_fn(backoff)
            attempt += 1
            continue

        status = getattr(resp, "status_code", None)
        if status in (200, 204):
            log.info(
                "Discord update sent (%d embed(s), %s).",
                len(payload.get("embeds", []) or []),
                "with file" if files else "no file",
            )
            if telemetry is not None:
                telemetry.on_attempt(url, status, attempt + 1)
                telemetry.on_success(url, attempt + 1)
            return True

        if telemetry is not None:
            telemetry.on_attempt(url, status, attempt + 1)

        if status in DISCORD_RETRYABLE_STATUS_CODES and attempt < max_retries:
            if status == 429:
                hint = _retry_after_seconds(resp)
                delay = (
                    min(hint, DISCORD_RETRY_AFTER_MAX_SECONDS)
                    if hint is not None
                    else min(
                        DISCORD_BACKOFF_MAX_SECONDS,
                        DISCORD_BACKOFF_BASE_SECONDS
                        * (DISCORD_BACKOFF_MULTIPLIER ** attempt),
                    )
                )
                reason = "429"
                log.warning(
                    "Discord 429 rate-limited (attempt %d/%d, sleep %.1fs).",
                    attempt + 1, max_retries, delay,
                )
            else:
                delay = min(
                    DISCORD_BACKOFF_MAX_SECONDS,
                    DISCORD_BACKOFF_BASE_SECONDS
                    * (DISCORD_BACKOFF_MULTIPLIER ** attempt),
                )
                reason = "5xx"
                log.warning(
                    "Discord HTTP %s (attempt %d/%d, sleep %.1fs).",
                    status, attempt + 1, max_retries, delay,
                )
            if telemetry is not None:
                telemetry.on_retry_scheduled(
                    url, attempt + 1, delay, reason
                )
            sleep_fn(delay)
            attempt += 1
            last_status = status
            last_text = (getattr(resp, "text", "") or "")[:300]
            continue

        # Non-retryable, or out of retries.
        last_status = status
        last_text = (getattr(resp, "text", "") or "")[:300]
        if telemetry is not None:
            telemetry.on_failure(
                url, status, attempt + 1,
                str(status) if status else "error",
            )
        break

    # ----------------------------------------------------------------
    # Embed-→-text fallback (HTTP 400, embeds, no multipart).
    # ----------------------------------------------------------------
    if allow_embed_fallback and last_status == 400 and payload.get("embeds") and not files:
        embeds = payload.get("embeds") or []
        log.warning(
            "Discord rejected embed payload (HTTP 400). "
            "Falling back to text summaries for %d embed(s).",
            len(embeds),
        )
        all_sent = True
        for embed in embeds:
            content = embed_to_content(embed)
            if not content:
                all_sent = False
                continue
            # Fallback POSTs are not retried — a 400 means the
            # payload is wrong, not transient.
            sent = _post_payload_with_retry(
                url,
                {"content": content},
                files=None,
                poster=poster,
                max_retries=0,
                sleep_fn=sleep_fn,
                telemetry=telemetry,
            )
            all_sent = all_sent and sent
        return all_sent

    log.warning(
        "Discord webhook returned HTTP %s: %s",
        last_status,
        last_text,
    )
    return False


def send_embeds(
    url: str,
    embeds: list[dict[str, Any]],
    *,
    content: Optional[str] = None,
    username: Optional[str] = None,
    files: Any = None,
    poster: Optional[Poster] = None,
    max_embeds: Optional[int] = None,
    max_batch_chars: Optional[int] = None,
    max_retries: int = DISCORD_MAX_RETRIES,
    wait: bool = False,
    sleep_fn: Callable[[float], None] = _sleep_fn,
    thread_id: Optional[str] = None,
    thread_name: Optional[str] = None,
    telemetry: Optional[RateLimitTelemetry] = None,
) -> int:
    """Batch ``embeds`` by Discord's limits and POST each batch.

    Splits the input with :func:`embed_batches` (default
    10 embeds per batch, max 5600 chars per batch by default),
    POSTs each batch via :func:`send_payload`, and returns the
    number of batches that POSTed successfully.

    A 0 return value means no batches were sent (empty
    ``embeds`` list, or every POST failed).

    The :class:`HTTPError` fallback-to-text behaviour from
    :func:`send_payload` is preserved per batch. The retry
    policy from :func:`send_payload` is also preserved per
    batch.

    When ``wait=True`` a :data:`WAIT_AFTER_BATCH_SECONDS` sleep
    is inserted between successful batches to stay under
    Discord's per-webhook rate limit.
    """
    if not embeds:
        return 0
    if not url:
        log.warning("send_embeds called with empty URL; skipping.")
        return 0

    batches = embed_batches(
        embeds,
        max_embeds=max_embeds if max_embeds is not None else 10,
        max_batch_chars=max_batch_chars if max_batch_chars is not None else 5600,
    )

    sent = 0
    for batch in batches:
        body: dict[str, Any] = {"embeds": batch}
        if content is not None:
            body["content"] = content
        if username is not None:
            body["username"] = username
        if send_payload(
            url,
            body,
            files=files,
            poster=poster,
            max_retries=max_retries,
            sleep_fn=sleep_fn,
            thread_id=thread_id,
            thread_name=thread_name,
            telemetry=telemetry,
        ):
            sent += 1
            if wait:
                sleep_fn(WAIT_AFTER_BATCH_SECONDS)
    return sent


# ---------------------------------------------------------------------------
# File-upload helper
# ---------------------------------------------------------------------------
def send_with_files(
    url: str,
    content: Optional[str],
    file_inputs: Iterable[FileInput],
    *,
    username: Optional[str] = None,
    poster: Optional[Poster] = None,
    max_retries: int = DISCORD_MAX_RETRIES,
    sleep_fn: Callable[[float], None] = _sleep_fn,
    thread_id: Optional[str] = None,
    thread_name: Optional[str] = None,
    telemetry: Optional[RateLimitTelemetry] = None,
) -> bool:
    """Send a single Discord message with one or more file attachments.

    Used by the strategy-engine analytics + paper_exec traders
    and by the daily-prep chart upload path. Splits ``content``
    via :func:`chunk_markdown` if needed; in that case the
    *last* chunk carries the files and earlier chunks are
    sent as plain text (mirrors the legacy
    ``scripts.utils.discord_notify.send_message`` behaviour).

    Returns ``True`` only if every chunk + the final file
    upload succeeded.

    Opened file handles are closed before the function returns.
    """
    if not url:
        log.warning("send_with_files called with empty URL; skipping.")
        return False
    if not content and not file_inputs:
        log.warning("send_with_files called with no content and no files; skipping.")
        return False

    opened: list[Any] = []
    try:
        files_dict: dict[str, Any] = {}
        for f in file_inputs:
            if isinstance(f, (str, Path)):
                p = Path(f)
                fh = open(p, "rb")
                opened.append(fh)
                files_dict[f"file_{p.stem}"] = (p.name, fh)
            else:
                # (filename, bytes, mimetype) tuple
                filename, data, mimetype = f
                files_dict[f"file_{Path(filename).stem}"] = (
                    filename, data, mimetype
                )

        if content is None or content == "":
            # Files only.
            payload: dict[str, Any] = {}
            if username is not None:
                payload["username"] = username
            return send_payload(
                url,
                payload,
                files=files_dict,
                poster=poster,
                max_retries=max_retries,
                sleep_fn=sleep_fn,
                thread_id=thread_id,
                thread_name=thread_name,
                telemetry=telemetry,
            )

        chunks = chunk_markdown(content, max_chars=DISCORD_MAX_CHARS)
        # All chunks except the last are plain text; the last
        # carries the files. If only one chunk, it carries the
        # files.
        if len(chunks) == 1:
            payload = {"content": chunks[0]}
            if username is not None:
                payload["username"] = username
            return send_payload(
                url, payload, files=files_dict, poster=poster,
                max_retries=max_retries, sleep_fn=sleep_fn,
                thread_id=thread_id, thread_name=thread_name,
                telemetry=telemetry,
            )

        # Multi-chunk: text-only for all but last, then file upload.
        all_sent = True
        for chunk in chunks[:-1]:
            body = {"content": chunk}
            if username is not None:
                body["username"] = username
            if not send_payload(
                url, body, files=None, poster=poster,
                max_retries=max_retries, sleep_fn=sleep_fn,
                thread_id=thread_id, thread_name=thread_name,
                telemetry=telemetry,
            ):
                all_sent = False
        # Last chunk + files.
        last_body: dict[str, Any] = {"content": chunks[-1]}
        if username is not None:
            last_body["username"] = username
        if not send_payload(
            url, last_body, files=files_dict, poster=poster,
            max_retries=max_retries, sleep_fn=sleep_fn,
            thread_id=thread_id, thread_name=thread_name,
            telemetry=telemetry,
        ):
            all_sent = False
        return all_sent
    finally:
        for fh in opened:
            try:
                fh.close()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# High-level: text + files (replaces scripts.utils.discord_notify.send_message)
# ---------------------------------------------------------------------------
def send_message(
    url: str,
    message: Optional[str] = None,
    file_paths: Optional[Iterable[Union[str, Path]]] = None,
    *,
    username: Optional[str] = None,
    poster: Optional[Poster] = None,
    max_retries: int = DISCORD_MAX_RETRIES,
    sleep_fn: Callable[[float], None] = _sleep_fn,
    thread_id: Optional[str] = None,
    thread_name: Optional[str] = None,
    telemetry: Optional[RateLimitTelemetry] = None,
) -> bool:
    """Send a Discord message, optionally with file attachments.

    Convenience wrapper around :func:`send_with_files` and
    :func:`send_payload`. Mirrors the legacy
    ``scripts.utils.discord_notify.send_message`` contract
    (chunk long text, attach files only to the last chunk,
    best-effort return bool).

    Returns ``True`` on full success, ``False`` otherwise.
    """
    files: list[FileInput] = []
    if file_paths:
        for fp in file_paths:
            if not Path(fp).exists():
                log.warning("send_message: file not found, skipping: %s", fp)
                continue
            files.append(fp)
    return send_with_files(
        url,
        message,
        files,
        username=username,
        poster=poster,
        max_retries=max_retries,
        sleep_fn=sleep_fn,
        thread_id=thread_id,
        thread_name=thread_name,
        telemetry=telemetry,
    )
