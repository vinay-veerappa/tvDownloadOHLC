"""
RTDClient — COM client for ThinkorSwim RTD server.

Ported from: 2187Nick/tos-streamlit-dashboard (futures branch)
Source: src/rtd/client.py

Provides synchronous subscribe/unsubscribe/refresh to real-time
market data via the TOS RTD COM server. Runs in a dedicated thread
with pythoncom message pumping.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple, Type, TypeVar, Union

import pythoncom
from comtypes import COMObject, GUID
from comtypes.automation import VARIANT, VARIANT_BOOL
from comtypes.client import CreateObject

from . import cleanup, topic
from .error_handler import (
    RTDClientError,
    RTDConnectionError,
    RTDConnectionState,
    RTDHeartbeatError,
    RTDServerError,
    RTDUpdateError,
    handle_com_error,
    log_method_call,
    validate_connection_state,
)
from .interfaces import IRTDUpdateEvent, IRtdServer
from .quote import Quote
from .quote_types import QuoteType
from .settings import SETTINGS

log = logging.getLogger(__name__)


class RTDClient(COMObject):
    """
    Real-Time Data Client for ThinkorSwim RTD Server.

    Provides a synchronous interface to the TOS RTD COM server for
    real-time market data subscriptions and updates.

    Attributes:
        _state: Current connection state
        server: COM server instance (IRtdServer)
        topics: Active topic subscriptions {topic_id: (symbol, quote_type)}
        heartbeat_interval: Server heartbeat interval in milliseconds
    """

    _com_interfaces_ = [IRTDUpdateEvent]

    def __init__(
        self,
        heartbeat_ms: Optional[int] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        super().__init__()

        self.logger = logger or log

        # COM server and state
        self.server: Optional[IRtdServer] = None
        self._state = RTDConnectionState.DISCONNECTED
        self._lock = Lock()

        # Topic management
        self.topics: Dict[int, Tuple[str, str]] = {}
        self._topic_lock = Lock()
        self._latest_values: Dict[Tuple[str, str], Quote] = {}
        self._value_lock = Lock()

        # Pending updates for incremental delta updates
        self._pending_updates: Dict[str, Any] = {}
        self._pending_lock = Lock()

        # Heartbeat
        self._heartbeat_interval = heartbeat_ms or SETTINGS.initial_heartbeat

        # Update tracking
        self._update_notify_count = 0
        self._last_refresh_time: Optional[float] = None

        self.logger.info("RTD Client instance created")

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> "RTDClient":
        self.initialize()
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> None:
        try:
            if exc_type is not None:
                self.logger.error("Context exit due to error: %s", exc_val)
            self.Disconnect()
        except Exception as e:
            self.logger.error("Error during context exit: %s", e)
            if exc_type is None:
                raise

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_connected(self) -> bool:
        return self._state == RTDConnectionState.CONNECTED

    @property
    def heartbeat_interval(self) -> int:
        return self._heartbeat_interval

    @heartbeat_interval.setter
    def heartbeat_interval(self, interval: int) -> None:
        if interval <= 0:
            raise ValueError("Heartbeat interval must be positive")
        self._heartbeat_interval = interval
        self.logger.info("Heartbeat interval set to %dms", interval)

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    @handle_com_error(RTDServerError)
    @log_method_call()
    def initialize(self) -> None:
        """Initialize COM and start the RTD server connection."""
        if self._state != RTDConnectionState.DISCONNECTED:
            raise RTDConnectionError(
                f"Initialization attempted in invalid state: {self._state}"
            )

        self._state = RTDConnectionState.CONNECTING
        self.logger.info("Starting RTD server initialization")

        try:
            pythoncom.CoInitialize()

            self.server = CreateObject(
                SETTINGS.progid,
                interface=IRtdServer,
            )
            self.logger.debug("COM server instance created")

            result = self.server.ServerStart(self)

            if result == 1:
                self._state = RTDConnectionState.CONNECTED
                self.logger.info("Server started successfully")

                current_interval = self.heartbeat_interval
                self.heartbeat_interval = SETTINGS.default_heartbeat
                self.logger.info(
                    "Heartbeat interval updated: %dms -> %dms",
                    current_interval,
                    self.heartbeat_interval,
                )
            else:
                raise RTDServerError(f"ServerStart failed with result: {result}")

        except Exception as e:
            self._state = RTDConnectionState.DISCONNECTED
            self.logger.error("Server initialization failed: %s", e)
            cleanup.cleanup_com()
            raise

    @handle_com_error(RTDServerError)
    @log_method_call()
    @validate_connection_state(
        [RTDConnectionState.CONNECTED, RTDConnectionState.CONNECTING]
    )
    def Disconnect(self) -> None:
        """Disconnect from RTD server and cleanup all resources."""
        with self._lock:
            if self._state == RTDConnectionState.DISCONNECTED:
                self.logger.info("Already disconnected")
                return
            if self._state == RTDConnectionState.DISCONNECTING:
                self.logger.info("Disconnect already in progress")
                return

            self._state = RTDConnectionState.DISCONNECTING
            self.logger.info("Starting disconnect sequence")

            try:
                subscriptions = [(qt, sym) for sym, qt in self.topics.values()]
                if subscriptions:
                    self.batch_unsubscribe(subscriptions)

                cleanup.cleanup_topics(self.topics)

                if self.server is not None:
                    try:
                        self.server.ServerTerminate()
                        self.logger.info("Server terminated")
                    except Exception as e:
                        self.logger.error("Error terminating server: %s", e)
                    finally:
                        self.server = None

                cleanup.cleanup_com()
                self._state = RTDConnectionState.DISCONNECTED
                self.logger.info("Disconnect completed")

            except Exception as e:
                self.logger.error("Error during disconnect: %s", e)
                raise

    # ------------------------------------------------------------------
    # Subscription management
    # ------------------------------------------------------------------

    @handle_com_error(RTDClientError)
    @log_method_call()
    @validate_connection_state([RTDConnectionState.CONNECTED])
    def subscribe(
        self, quote_type: Union[str, QuoteType], symbol: str
    ) -> Optional[int]:
        """Subscribe to a quote type for a symbol. Returns topic_id or None."""
        with self._topic_lock:
            quote_type_str = topic.validate_quote_type(quote_type)
            topic_id = topic.generate_topic_id(quote_type_str, symbol)

            if topic_id in self.topics:
                self.logger.debug("Already subscribed to %s %s", symbol, quote_type_str)
                return topic_id

            strings = (VARIANT * 2)()
            strings[0].value = quote_type_str
            strings[1].value = symbol
            get_new_values = VARIANT_BOOL(True)

            try:
                self.logger.debug("Subscribing to %s %s", symbol, quote_type_str)
                result = self.server.ConnectData(topic_id, strings, get_new_values)
                self.logger.debug("Subscription raw result for %s: %s", symbol, result)

                if isinstance(result, list) and len(result) >= 1 and result[0]:
                    self.topics[topic_id] = (symbol, quote_type_str)
                    self.logger.debug(
                        "Subscribed to %s %s with ID %d",
                        symbol,
                        quote_type_str,
                        topic_id,
                    )
                    return topic_id
                else:
                    self.logger.warning(
                        "Subscription failed for %s %s - Invalid result: %s",
                        symbol,
                        quote_type_str,
                        result,
                    )
                    return None

            except Exception as e:
                self.logger.error("Error subscribing to %s %s: %s", symbol, quote_type_str, e)
                raise RTDClientError(f"Subscription failed for {symbol}") from e

    @handle_com_error(RTDClientError)
    @log_method_call()
    @validate_connection_state(
        [RTDConnectionState.CONNECTED, RTDConnectionState.DISCONNECTING]
    )
    def unsubscribe(self, quote_type: Union[str, QuoteType], symbol: str) -> bool:
        """Unsubscribe from a quote type for a symbol."""
        with self._topic_lock:
            quote_type_str = topic.validate_quote_type(quote_type)
            topic_id = topic.find_topic_id(self.topics, symbol, quote_type_str)
            if topic_id is None:
                self.logger.warning("Not subscribed to %s %s", symbol, quote_type_str)
                return False

            try:
                result = self.server.DisconnectData(topic_id)
                self.logger.debug("Unsub raw result %s", result)

                if result == 0:
                    del self.topics[topic_id]
                    self.logger.debug("Unsubscribed from %s %s", symbol, quote_type_str)
                    return True
                else:
                    self.logger.warning("Unsubscription failed for %s %s", symbol, quote_type_str)
                    return False

            except Exception as e:
                self.logger.error("Error unsubscribing from %s %s: %s", symbol, quote_type_str, e)
                return False

    # ------------------------------------------------------------------
    # Data refresh
    # ------------------------------------------------------------------

    @handle_com_error(RTDUpdateError)
    @log_method_call()
    @validate_connection_state([RTDConnectionState.CONNECTED])
    def UpdateNotify(self) -> bool:
        """COM callback — called when the RTD server has new data."""
        self._update_notify_count += 1
        self.logger.debug("UpdateNotify called (count: %d)", self._update_notify_count)
        return self.refresh_topics()

    @handle_com_error(RTDClientError)
    @log_method_call()
    @validate_connection_state([RTDConnectionState.CONNECTED])
    def refresh_topics(self) -> bool:
        """Refresh all subscribed topics and process updates."""
        try:
            result = self.server.RefreshData()
            self.logger.debug("RefreshData raw result %s", result)
            self._last_refresh_time = time.time()

            if not result or not isinstance(result, list) or len(result) != 2:
                self.logger.warning("Unexpected RefreshData result: %s", result)
                return False

            topic_count, data = result
            if topic_count == 0 or not data:
                self.logger.debug("No new data in this update")
                return True

            self.logger.debug("Received refresh data for %d topics", topic_count)

            if isinstance(data, tuple) and len(data) == 2:
                topic_ids, raw_values = data
                for tid, raw_value in zip(topic_ids, raw_values):
                    if tid in self.topics:
                        symbol, quote_type = self.topics[tid]
                        quote_obj = Quote(quote_type, symbol, raw_value)
                        self._handle_quote_update(tid, symbol, quote_type, quote_obj)
                return True
            else:
                self.logger.warning("Unexpected data format: %s", data)
                return False

        except Exception as e:
            self.logger.error("Error in refresh: %s", e, exc_info=True)
            return False

    def _handle_quote_update(
        self, id: int, symbol: str, quote_type: str, quote: Quote
    ) -> None:
        """Process a single quote update and store in latest_values."""
        try:
            if quote.value is None:
                self.logger.debug("Null value for %s %s", symbol, quote_type)
                return

            with self._value_lock:
                key = (symbol, quote_type)
                # For futures with exchange suffix, store under both keys
                if ":" in symbol:
                    base_symbol = symbol.split(":")[0]
                    base_key = (base_symbol, quote_type)
                    self._latest_values[key] = quote
                    self._latest_values[base_key] = quote
                else:
                    self._latest_values[key] = quote

            with self._pending_lock:
                key_str = f"{symbol}:{quote_type}"
                self._pending_updates[key_str] = quote.value
                if ":" in symbol:
                    base_symbol = symbol.split(":")[0]
                    self._pending_updates[f"{base_symbol}:{quote_type}"] = quote.value

        except Exception as e:
            self.logger.error("Error handling quote update: %s", e)

    def get_pending_updates(self) -> Dict[str, Any]:
        """Get and clear all pending quote updates since last call."""
        with self._pending_lock:
            updates = self._pending_updates
            self._pending_updates = {}
            return updates

    # ------------------------------------------------------------------
    # Heartbeat
    # ------------------------------------------------------------------

    @handle_com_error(RTDHeartbeatError)
    @log_method_call()
    @validate_connection_state(
        [RTDConnectionState.CONNECTED, RTDConnectionState.DISCONNECTED]
    )
    def check_heartbeat(self) -> bool:
        """Check server heartbeat health."""
        if self._state == RTDConnectionState.DISCONNECTED:
            self.logger.debug("Heartbeat check skipped - disconnected")
            return False

        try:
            result = self.server.Heartbeat()
            is_healthy = result == 1
            if not is_healthy:
                self.logger.warning("Unhealthy heartbeat response: %s", result)
            return is_healthy
        except Exception as e:
            self.logger.error("Heartbeat check failed: %s", e)
            raise RTDHeartbeatError("Heartbeat operation failed") from e

    # ------------------------------------------------------------------
    # Batch operations
    # ------------------------------------------------------------------

    def batch_subscribe(
        self, subscriptions: List[Tuple[Union[str, QuoteType], str]]
    ) -> Dict[Tuple[str, str], bool]:
        """Subscribe to multiple quote types and symbols at once."""
        results = {}
        for quote_type, symbol in subscriptions:
            try:
                topic_id = self.subscribe(quote_type, symbol)
                results[(str(quote_type), symbol)] = topic_id is not None
            except Exception as e:
                self.logger.error("Batch subscribe error for %s %s: %s", symbol, quote_type, e)
                results[(str(quote_type), symbol)] = False

        successful = sum(1 for r in results.values() if r)
        self.logger.info("Batch subscribe: %d/%d successful", successful, len(subscriptions))
        return results

    def batch_unsubscribe(
        self, subscriptions: List[Tuple[Union[str, QuoteType], str]]
    ) -> Dict[Tuple[str, str], bool]:
        """Unsubscribe from multiple quote types and symbols at once."""
        results = {}
        for quote_type, symbol in subscriptions:
            try:
                success = self.unsubscribe(quote_type, symbol)
                results[(str(quote_type), symbol)] = success
            except Exception as e:
                self.logger.error("Batch unsubscribe error for %s %s: %s", symbol, quote_type, e)
                results[(str(quote_type), symbol)] = False

        successful = sum(1 for r in results.values() if r)
        self.logger.info("Batch unsubscribe: %d/%d successful", successful, len(subscriptions))
        return results

    # ------------------------------------------------------------------
    # Latest values access
    # ------------------------------------------------------------------

    def get_latest_values(self) -> Dict[Tuple[str, str], Quote]:
        """Get a snapshot of all latest quote values (thread-safe)."""
        with self._value_lock:
            return dict(self._latest_values)

    def get_value(self, symbol: str, quote_type: Union[str, QuoteType]) -> Optional[Quote]:
        """Get the latest Quote for a specific symbol + quote_type."""
        qt_str = topic.validate_quote_type(quote_type)
        with self._value_lock:
            return self._latest_values.get((symbol, qt_str))

    # ------------------------------------------------------------------
    # String representation
    # ------------------------------------------------------------------

    def __str__(self) -> str:
        status = "Connected" if self.is_connected else "Disconnected"
        return f"RTDClient: {status}, Topics: {len(self.topics)}, Updates: {self._update_notify_count}"

    def __repr__(self) -> str:
        return (
            f"RTDClient(state={self._state.name}, "
            f"topics={len(self.topics)}, "
            f"heartbeat={self._heartbeat_interval}ms, "
            f"updates={self._update_notify_count})"
        )