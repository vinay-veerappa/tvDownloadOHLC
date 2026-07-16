"""DEPRECATED shim — use ``scripts.libs_py.discord`` instead.

This module is a thin compatibility layer that delegates to
:mod:`scripts.libs_py.discord`. It exists only so the 8
analysis / maintenance / strategy-engine consumers that
historically imported from ``scripts.utils.discord_notify``
keep working without changes during the Tier-1+2 migration.

**New code must import directly from
``scripts.libs_py.discord``.** This shim will be removed in a
follow-up commit once the 8 consumers are migrated to direct
imports.

The mapping is:

  * ``get_webhook_url(channel_name, override_url=None)`` →
    :func:`scripts.libs_py.discord.load_webhook_url` (the
    ``override_url`` parameter is honoured here because
    consumers use it; the new API does not).

  * ``upload_file(webhook_url, file_path, message=None)`` →
    :func:`scripts.libs_py.discord.send_message` with the
    file attached.

  * ``send_message(webhook_url, message, files=None)`` →
    :func:`scripts.libs_py.discord.send_message`.

The 1900-char / multipart logic that previously lived in
this file is now in
:mod:`scripts.libs_py.discord.webhooks` (the public
:func:`send_message` entry point and the lower-level
:func:`send_payload` and :func:`send_with_files` primitives).
"""
from __future__ import annotations

import os
import warnings
from typing import Iterable, Optional, Union

from scripts.libs_py.discord import load_webhook_url, send_message as _send_message

# Re-export the public API so existing callers keep working.
__all__ = (
    "get_webhook_url",
    "send_message",
    "upload_file",
)

# Emitted once on first import.
_DEPRECATION_EMITTED = False


def _emit_deprecation() -> None:
    global _DEPRECATION_EMITTED
    if _DEPRECATION_EMITTED:
        return
    _DEPRECATION_EMITTED = True
    warnings.warn(
        "`scripts.utils.discord_notify` is deprecated; import from "
        "`scripts.libs_py.discord` instead. This shim will be removed "
        "in a follow-up commit.",
        DeprecationWarning,
        stacklevel=2,
    )


def _repo_root() -> "os.PathLike[str]":
    """Locate the repo root from this file's location.

    Mirrors the legacy resolution in the deleted
    ``discord_notify.py``: this file is at
    ``<repo>/scripts/utils/discord_notify.py``, so the
    repo root is two ``dirname`` calls up.
    """
    here = os.path.abspath(__file__)
    # <repo>/scripts/utils/discord_notify.py → <repo>
    return os.path.dirname(os.path.dirname(os.path.dirname(here)))


def get_webhook_url(
    channel_name: Optional[str] = None,
    override_url: Optional[str] = None,
) -> Optional[str]:
    """Look up the Discord webhook URL for ``channel_name``.

    Mirrors the legacy signature exactly so existing callers
    (e.g. ``scripts/analysis/daily_system_audit.py``,
    ``scripts/trader/run_daily_prep.py``) work without
    changes. The new code should call
    :func:`scripts.libs_py.discord.load_webhook_url`
    directly.
    """
    _emit_deprecation()
    if override_url:
        return override_url
    repo = _repo_root()
    return load_webhook_url(channel_name or "test_channel", repo_root=repo)


def send_message(
    webhook_url: str,
    message: Optional[str] = None,
    files: Optional[Iterable[Union[str, "os.PathLike[str]"]]] = None,
) -> bool:
    """Send ``message`` (and optionally ``files``) to Discord.

    Mirrors the legacy signature exactly. Backed by
    :func:`scripts.libs_py.discord.send_message` which now
    uses the shared chunking, retry, and backoff policy.
    """
    _emit_deprecation()
    return _send_message(webhook_url, message, file_paths=files)


def upload_file(
    webhook_url: str,
    file_path: Union[str, "os.PathLike[str]"],
    message: Optional[str] = None,
) -> bool:
    """Send a single file (with optional caption) to Discord.

    Mirrors the legacy signature. Backed by
    :func:`scripts.libs_py.discord.send_message`.
    """
    _emit_deprecation()
    return _send_message(webhook_url, message, file_paths=[file_path])
