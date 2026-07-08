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


class RTDWorker:
    """Background worker that manages COM lifecycle and data polling."""

    def __init__(self, data_queue: Queue, stop_event: threading.Event):
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

            success_count = 0
            subscription_errors: list[str] = []

            for symbol in all_symbols:
                retry_count = 0
                while retry_count < 3:
                    try:
                        if symbol.startswith("."):
                            # Option symbols — subscribe to Greeks + OI + Volume
                            if self.client.subscribe(QuoteType.GAMMA, symbol):
                                success_count += 1
                                self.logger.info("Subscribed to GAMMA for %s", symbol)
                            if self.client.subscribe(QuoteType.OPEN_INT, symbol):
                                success_count += 1
                                self.logger.info("Subscribed to OPEN_INT for %s", symbol)
                            if self.client.subscribe(QuoteType.VOLUME, symbol):
                                success_count += 1
                                self.logger.info("Subscribed to VOLUME for %s", symbol)
                        else:
                            # Base symbol — subscribe to LAST
                            if symbol.startswith("/") and ":" not in symbol:
                                exchange = OptionSymbolBuilder.FUTURES_EXCHANGES.get(
                                    symbol, "XCBT"
                                )
                                full_symbol = f"{symbol}:{exchange}"
                                self.logger.info(
                                    "Subscribing to LAST for futures: %s", full_symbol
                                )
                                if self.client.subscribe(QuoteType.LAST, full_symbol):
                                    success_count += 1
                                    self.logger.info("Subscribed to %s", full_symbol)
                            else:
                                self.logger.info("Subscribing to LAST for %s", symbol)
                                if self.client.subscribe(QuoteType.LAST, symbol):
                                    success_count += 1
                                    self.logger.info("Subscribed to %s", symbol)
                        break
                    except Exception as sub_error:
                        retry_count += 1
                        if retry_count == 3:
                            error_msg = f"Failed to subscribe to {symbol} after 3 attempts: {sub_error}"
                            subscription_errors.append(error_msg)
                            self.logger.error(error_msg)
                        time.sleep(0.1)

            if subscription_errors:
                self.data_queue.put({"error": "\n".join(subscription_errors)})
                return

            self.logger.info("Successfully subscribed to %d topics", success_count)
            time.sleep(0.3)

            last_data: dict = {}

            while not self.stop_event.is_set():
                pythoncom.PumpWaitingMessages()

                try:
                    with self.client._value_lock:
                        if self.client._latest_values:
                            current_data = {}
                            for topic_str, quote in self.client._latest_values.items():
                                symbol, quote_type = topic_str
                                key = f"{symbol}:{quote_type}"
                                current_data[key] = quote.value

                            if current_data != last_data:
                                # Clear old data from queue
                                while not self.data_queue.empty():
                                    try:
                                        self.data_queue.get_nowait()
                                    except Exception:
                                        break

                                self.data_queue.put(current_data)
                                last_data = current_data.copy()

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