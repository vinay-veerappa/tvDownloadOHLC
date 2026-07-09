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

def run_rtd_worker_process(data_queue, stop_event, all_symbols):
    """Entry point for the multiprocessing worker."""
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
    worker.start(all_symbols)

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

    def start(self, all_symbols: list) -> None:
        """Start RTD worker — subscribes to all symbols and polls for updates."""
        try:
            if self.initialized:
                self.logger.info("Cleaning up previous instance...")
                self.cleanup()

            self._first_data_received = False
            self._init_com_with_retry()

            if not all_symbols:
                self.logger.warning("No symbols provided!")
                return

            # Build flat list of all subscriptions
            subscriptions = []
            for symbol in all_symbols:
                if symbol.startswith("."):
                    # Option symbols — subscribe to Greeks + OI + Volume + IV
                    for qt in [
                        QuoteType.GAMMA,
                        QuoteType.OPEN_INT,
                        QuoteType.VOLUME,
                        QuoteType.DELTA,
                        QuoteType.IMPL_VOL,
                        QuoteType.LAST,
                    ]:
                        subscriptions.append((qt, symbol))
                else:
                    # Base symbol — subscribe to LAST
                    if symbol.startswith("/") and ":" not in symbol:
                        exchange = OptionSymbolBuilder.FUTURES_EXCHANGES.get(
                            symbol, "XCBT"
                        )
                        subscriptions.append((QuoteType.LAST, f"{symbol}:{exchange}"))
                    else:
                        subscriptions.append((QuoteType.LAST, symbol))

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

            while not self.stop_event.is_set():
                pythoncom.PumpWaitingMessages()

                try:
                    updates = self.client.get_pending_updates()
                    if updates:
                        self.data_queue.put(updates)

                        if not self._first_data_received:
                            self._first_data_received = True
                            self.logger.info("First data received — switching to normal poll rate")

                except Exception as e:
                    self.logger.error("Data processing error: %s", e)

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