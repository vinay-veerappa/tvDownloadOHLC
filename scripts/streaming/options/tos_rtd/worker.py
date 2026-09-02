"""
RTDWorker — background thread that pumps COM messages and emits quotes.

Ported from: 2187Nick/tos-streamlit-dashboard (futures branch)
Source: src/rtd/rtd_worker.py

Runs in a dedicated thread with pythoncom message pumping. Subscribes
to GAMMA, OPEN_INT, and VOLUME for option symbols, and LAST for base
futures symbols. Emits data updates to a Queue.
"""
from __future__ import annotations

import gc
import logging
import threading
import time
from queue import Queue

import pythoncom

from .client import RTDClient
from .quote_types import QuoteType
from .settings import SETTINGS
from .symbol_builder import OptionSymbolBuilder

log = logging.getLogger(__name__)

MAX_INIT_RETRIES = SETTINGS.max_init_retries
INIT_RETRY_DELAYS = SETTINGS.init_retry_delays

def run_rtd_worker_process(data_queue, stop_event, subscriptions, command_queue=None):
    """Entry point for the multiprocessing worker.

    Args:
        data_queue: multiprocessing.Queue for outgoing RTD updates.
        stop_event: multiprocessing.Event that signals shutdown.
        subscriptions: list of (QuoteType, symbol) tuples to subscribe to.
        command_queue: optional multiprocessing.Queue for incremental
            subscribe/unsubscribe commands so a single COM connection can be
            reused across many topic batches (avoids per-batch COM churn).
    """
    import signal
    import sys

    # Try to send a debug message through the queue immediately
    try:
        data_queue.put({"debug": "Child process successfully started and queue is accessible!"})
    except Exception as e:
        print(f"Failed to put to queue: {e}", file=sys.stderr)

    try:
        signal.signal(signal.SIGINT, signal.SIG_IGN)
    except Exception:
        pass

    import logging
    class QueueHandler(logging.Handler):
        def emit(self, record):
            try:
                data_queue.put({"debug": self.format(record)})
            except:
                pass

    logger = logging.getLogger("RTDWorker")
    logger.setLevel(logging.DEBUG)
    qh = QueueHandler()
    qh.setFormatter(logging.Formatter('[CHILD] %(levelname)s: %(message)s'))
    logger.addHandler(qh)

    worker = RTDWorker(data_queue, stop_event)
    worker.logger = logger
    worker.start(subscriptions, command_queue=command_queue)

class RTDWorker:
    """Background worker that manages COM lifecycle and data polling."""

    def __init__(self, data_queue, stop_event):
        self.data_queue = data_queue
        self.stop_event = stop_event
        self.client: RTDClient | None = None
        self.initialized = False
        self._first_data_received = False
        self.logger = logging.getLogger("RTDWorker")

    def _init_com_with_retry(self) -> None:
        """Initialize COM and RTD server with retry on failure."""
        for attempt in range(MAX_INIT_RETRIES):
            try:
                pythoncom.CoInitialize()
                time.sleep(0.1)

                self.client = RTDClient(
                    heartbeat_ms=SETTINGS.initial_heartbeat,
                    logger=self.logger,
                )
                self.client.initialize()
                self.initialized = True
                return

            except Exception as e:
                self.logger.warning(
                    "COM init attempt %d/%d failed: %s", attempt + 1, MAX_INIT_RETRIES, e
                )
                if self.client:
                    try:
                        self.client.Disconnect()
                    except Exception:
                        pass
                    self.client = None
                try:
                    pythoncom.CoUninitialize()
                except Exception:
                    pass
                gc.collect()

                if attempt < MAX_INIT_RETRIES - 1:
                    delay = INIT_RETRY_DELAYS[attempt]
                    self.logger.info("Retrying COM init in %ss...", delay)
                    time.sleep(delay)
                else:
                    raise

    def start(self, subscriptions: list[tuple[QuoteType, str]], command_queue=None) -> None:
        """Start RTD worker — subscribes to the provided quote tuples and polls for updates.

        The caller is responsible for assembling the exact (QuoteType, symbol)
        subscriptions. This lets the coordinator differentiate live streaming
        subscriptions (front-expiry IV/LAST) from cached/static back-expiry
        contracts, dramatically reducing COM topic usage.

        If ``command_queue`` is provided, the worker keeps running and accepts
        {"cmd": "subscribe"|"unsubscribe", "subscriptions": [...]} messages so
        a single COM connection can be reused across many topic batches.
        """
        try:
            if self.initialized:
                self.logger.info("Cleaning up previous instance...")
                self.cleanup()

            self._first_data_received = False
            self._init_com_with_retry()

            if not subscriptions:
                self.logger.warning("No subscriptions provided!")
                return

            self.logger.info("Subscribing to %d topics...", len(subscriptions))
            results = self.client.batch_subscribe(subscriptions)
            
            # Retry failed subscriptions (up to 2 attempts)
            failed_subs = [(qt, sym) for (qt_str, sym), success in results.items() for qt in [QuoteType[qt_str] if qt_str in QuoteType.__members__ else qt_str] if not success]
            # Simple list comprehension check to reconstruct original QuoteType/str
            failed_subs = []
            for (qt_str, sym), success in results.items():
                if not success:
                    # Resolve to QuoteType enum if possible
                    qt_resolved = qt_str
                    for qt_enum in QuoteType:
                        if qt_enum.value == qt_str:
                            qt_resolved = qt_enum
                            break
                    failed_subs.append((qt_resolved, sym))

            if failed_subs:
                self.logger.warning("Retrying %d failed subscriptions...", len(failed_subs))
                for attempt in range(2):
                    time.sleep(0.1)
                    retry_results = self.client.batch_subscribe(failed_subs)
                    failed_subs = []
                    for (qt_str, sym), success in retry_results.items():
                        if not success:
                            qt_resolved = qt_str
                            for qt_enum in QuoteType:
                                if qt_enum.value == qt_str:
                                    qt_resolved = qt_enum
                                    break
                            failed_subs.append((qt_resolved, sym))
                    if not failed_subs:
                        break

            success_count = len(subscriptions) - len(failed_subs)
            if failed_subs:
                self.logger.error("%d subscriptions failed: %s", len(failed_subs), failed_subs)
                # Still proceed if some succeeded
                if success_count == 0:
                    self.data_queue.put({"error": f"All {len(subscriptions)} subscriptions failed"})
                    return
            else:
                self.logger.info("Successfully subscribed to all %d topics", success_count)

            time.sleep(0.3)

            # Heartbeat monitoring: the RTD server can silently stop pushing
            # updates for subscribed topics (COM throttle, TOS hiccup, data
            # subscription lapse). Poll the server heartbeat periodically —
            # a failed heartbeat is pushed through the queue as an error so
            # the parent's health monitor sees it and can restart.
            HEARTBEAT_CHECK_EVERY = 30.0  # seconds between heartbeat probes
            last_heartbeat_check = time.time()
            consecutive_hb_failures = 0

            while not self.stop_event.is_set():
                pythoncom.PumpWaitingMessages()

                # Process incremental subscribe/unsubscribe commands (reuses
                # the same COM connection — no per-batch teardown).
                if command_queue is not None:
                    try:
                        while True:
                            cmd = command_queue.get_nowait()
                            self._handle_command(cmd)
                    except Exception:
                        pass  # queue.Empty or transient

                try:
                    updates = self.client.get_pending_updates()
                    if updates:
                        self.data_queue.put(updates)

                        if not self._first_data_received:
                            self._first_data_received = True
                            self.logger.info("First data received — switching to normal poll rate")

                except Exception as e:
                    self.logger.error("Data processing error: %s", e)

                # Periodic heartbeat probe — detects a silent RTD server.
                now_hb = time.time()
                if now_hb - last_heartbeat_check >= HEARTBEAT_CHECK_EVERY:
                    last_heartbeat_check = now_hb
                    try:
                        if self.client.check_heartbeat():
                            if consecutive_hb_failures > 0:
                                self.logger.info("RTD heartbeat recovered after %d failures", consecutive_hb_failures)
                            consecutive_hb_failures = 0
                        else:
                            consecutive_hb_failures += 1
                            self.logger.warning(
                                "RTD heartbeat unhealthy (%d consecutive)", consecutive_hb_failures
                            )
                            if consecutive_hb_failures >= 3:
                                self.data_queue.put({
                                    "error": f"RTD heartbeat failed {consecutive_hb_failures} consecutive checks"
                                })
                    except Exception as hb_err:
                        consecutive_hb_failures += 1
                        self.logger.warning("Heartbeat probe failed: %s (%d consecutive)", hb_err, consecutive_hb_failures)
                        if consecutive_hb_failures >= 3:
                            self.data_queue.put({"error": f"RTD heartbeat unreachable: {hb_err}"})

                # Poll fast until first data, then slow down
                if self._first_data_received:
                    time.sleep(SETTINGS.normal_poll_interval)
                else:
                    time.sleep(SETTINGS.fast_poll_interval)

        except Exception as e:
            error_msg = f"RTD Error: {e}"
            self.logger.error(error_msg)
            self.data_queue.put({"error": error_msg})
        finally:
            self.cleanup()
            self.logger.info("RTDWorker cleanup complete")

    def _handle_command(self, cmd) -> None:
        """Handle an incremental subscribe/unsubscribe command on a live worker."""
        if not isinstance(cmd, dict):
            return
        op = cmd.get("cmd")
        subs = cmd.get("subscriptions") or []
        if not subs:
            return
        try:
            if op == "subscribe":
                self.client.batch_subscribe(subs)
            elif op == "unsubscribe":
                self.client.batch_unsubscribe(subs)
        except Exception as e:
            self.logger.error("Command %s failed: %s", op, e)

    def cleanup(self) -> None:
        """Disconnect RTD client and uninitialize COM."""
        if self.client:
            try:
                self.logger.info("Disconnecting RTDClient...")
                self.client.Disconnect()
            except Exception as e:
                self.logger.error("Error during disconnect: %s", e)
            finally:
                self.client = None
        try:
            pythoncom.CoUninitialize()
        except Exception as e:
            self.logger.error("Error during CoUninitialize: %s", e)
        self.initialized = False
        self._first_data_received = False
        gc.collect()