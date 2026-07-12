"""
_rtd_worker_entry.py
--------------------
Minimal subprocess entry point for the TOS RTD worker.

This module is the *only* thing the child process imports. It deliberately
avoids importing anything from the broader pipeline (Prisma, Schwab client,
GEX calculator, etc.) so that Windows multiprocessing spawn overhead stays
under ~2 seconds instead of ~28 seconds.

Do NOT add pipeline imports here.
"""
from __future__ import annotations

# Set this FIRST — before any other imports — so that when multiprocessing
# spawn re-imports run_options_levels.py as __main__, the _IS_RTD_CHILD guard
# in that module fires and skips all heavy pipeline imports (Prisma etc.).
import os as _os
_os.environ["_RTD_WORKER_CHILD"] = "1"

import gc
import logging
import signal
import sys
import time

import pythoncom


def run_rtd_worker_process(data_queue, stop_event, subscriptions):
    """Entry point called by mp.Process in the child process.

    Args:
        data_queue: multiprocessing.Queue for outgoing RTD updates.
        stop_event: multiprocessing.Event that signals shutdown.
        subscriptions: list of (QuoteType, symbol) tuples to subscribe to.
    """

    # Immediately confirm the child is alive and the queue works
    try:
        data_queue.put({"debug": "Child process started."})
    except Exception as exc:
        print(f"[RTD child] queue put failed: {exc}", file=sys.stderr)

    # Ignore Ctrl-C — parent handles shutdown via stop_event
    try:
        signal.signal(signal.SIGINT, signal.SIG_IGN)
    except Exception:
        pass

    # Route child logs back to the parent via the queue
    class _QueueHandler(logging.Handler):
        def emit(self, record):
            try:
                data_queue.put({"debug": self.format(record)})
            except Exception:
                pass

    logger = logging.getLogger("RTDWorker")
    logger.setLevel(logging.DEBUG)
    _qh = _QueueHandler()
    _qh.setFormatter(logging.Formatter("[CHILD] %(levelname)s: %(message)s"))
    logger.addHandler(_qh)

    # Heavy imports happen here — inside the child only
    from scripts.streaming.options.tos_rtd.worker import RTDWorker  # noqa: PLC0415

    worker = RTDWorker(data_queue, stop_event)
    worker.logger = logger
    worker.start(subscriptions)
