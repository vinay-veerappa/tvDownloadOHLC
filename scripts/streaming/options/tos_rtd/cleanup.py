"""
Cleanup utilities for COM resources.

Ported from: 2187Nick/tos-streamlit-dashboard (futures branch)
Source: src/utils/cleanup.py
"""
from __future__ import annotations

import logging
from typing import Dict, Tuple

import pythoncom

log = logging.getLogger(__name__)


def cleanup_com() -> None:
    """Uninitialize COM for the current thread."""
    try:
        pythoncom.CoUninitialize()
        log.debug("COM uninitialized")
    except Exception as e:
        log.error("Error uninitializing COM: %s", e)


def cleanup_topics(topics: Dict[int, Tuple[str, str]]) -> None:
    """Clear all topic subscriptions from tracking."""
    try:
        count = len(topics)
        topics.clear()
        log.info("Cleared %d topics from tracking", count)
    except Exception as e:
        log.error("Error clearing topics: %s", e)