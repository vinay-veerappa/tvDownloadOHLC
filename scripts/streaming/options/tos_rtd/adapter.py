"""
TOSRTDAdapter — bridges TOS RTD real-time data into our options pipeline.

Consumes RTD quotes from the worker thread and provides:
  - get_snapshot(): Latest {symbol: {GAMMA, OPEN_INT, VOLUME, LAST, ...}}
  - get_futures_price(symbol): Latest futures LAST price
  - build_chain_snapshot(): Converts RTD quotes to a chain-like structure
    compatible with gex_calculator.py expectations

Usage::

    adapter = TOSRTDAdapter()
    adapter.start(symbols=["/ES", "/NQ"], expiry=date(2026, 7, 17))
    time.sleep(3)  # Wait for first data
    price = adapter.get_futures_price("/ES")
    snapshot = adapter.get_snapshot()
    adapter.stop()
"""
from __future__ import annotations

import logging
import threading
import time
import multiprocessing as mp
from dataclasses import dataclass, field
from datetime import date
from queue import Empty
from typing import Any, Optional

from .quote_types import QuoteType
from .settings import SETTINGS
from .symbol_builder import OptionSymbolBuilder, parse_rtd_option_symbol, OptionContract

log = logging.getLogger(__name__)


@dataclass
class RTDConfig:
    """Configuration for TOSRTDAdapter."""

    strike_range: int = 20          # ± strikes from ATM (fallback)
    strike_spacing: float = 1.0     # Spacing between strikes (fallback)
    poll_timeout: float = 0.1       # Queue get timeout
    wait_for_first_data: float = 5.0  # Seconds to wait for first data on start
    # Per-symbol overrides: {"/NQ": {"strike_range": 500, "strike_spacing": 25.0}, ...}
    symbol_configs: dict[str, dict] | None = None


@dataclass
class ChainSnapshot:
    """
    Normalized option chain snapshot from RTD data.

    This is a lightweight structure that can be fed into gex_calculator
    or used standalone for quick GEX estimates.
    """

    symbol: str                     # Base futures symbol, e.g. "/ES"
    futures_price: float            # Latest underlying LAST price
    expiry: date                     # Primary expiration date (nearest)
    timestamp: float                 # Unix timestamp of snapshot
    contracts: list[OptionContract] = field(default_factory=list)
    # Per-contract Greeks: {rtd_symbol: {GAMMA: ..., OPEN_INT: ..., VOLUME: ..., LAST: ...}}
    greeks: dict[str, dict[str, float | int | None]] = field(default_factory=dict)
    # Per-symbol expiry mapping: {rtd_symbol: expiry_date}
    # Used by build_chain_from_rtd to assign correct expiry per contract
    expiry_map: dict[str, date] = field(default_factory=dict)

    @property
    def call_strikes(self) -> list[float]:
        """Sorted list of call strikes with data."""
        strikes = sorted({
            c.strike for c in self.contracts if c.option_type == "C"
            and c.rtd_symbol in self.greeks
        })
        return strikes

    @property
    def put_strikes(self) -> list[float]:
        """Sorted list of put strikes with data."""
        strikes = sorted({
            c.strike for c in self.contracts if c.option_type == "P"
            and c.rtd_symbol in self.greeks
        })
        return strikes


class TOSRTDAdapter:
    """
    Adapter that manages the RTD worker lifecycle and provides
    normalized data access for our options pipeline.
    """

    def __init__(self, config: Optional[RTDConfig] = None):
        self.config = config or RTDConfig()
        self._data_queue = mp.Queue()
        self._stop_event = mp.Event()
        self._process: Optional[mp.Process] = None
        self._latest_data: dict[str, Any] = {}
        self._latest_lock = threading.Lock()
        self._running = False
        self._option_symbols: list[str] = []
        self._base_symbols: list[str] = []
        self._expiry: Optional[date] = None
        self._drain_thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(
        self,
        symbols: list[str],
        expiry: date,
        current_price: Optional[float] = None,
        expiries: list[date] | None = None,
    ) -> None:
        """
        Start RTD streaming for the given futures symbols.

        Args:
            symbols: Futures symbols to monitor, e.g. ["/ES", "/NQ"]
            expiry: Primary option expiration date (for backward compat)
            current_price: Optional dict {symbol: price} for initial strike
                          generation. If None, will subscribe to LAST first
                          and build option symbols after price arrives.
            expiries: Optional list of expiration dates. If provided, option
                     symbols are built for ALL expiries (not just primary).
        """
        if self._running:
            log.warning("Adapter already running — stopping first")
            self.stop()

        self._expiry = expiry
        self._expiries = expiries or [expiry]
        self._base_symbols = list(symbols)
        self._stop_event.clear()

        # Build option symbols if we have prices
        all_symbols: list[str] = []
        prices = current_price if isinstance(current_price, dict) else {}
        sym_configs = self.config.symbol_configs or {}

        for sym in symbols:
            if sym in prices and prices[sym] > 0:
                sc = sym_configs.get(sym, {})
                sr = sc.get("strike_range", self.config.strike_range)
                ss = sc.get("strike_spacing", self.config.strike_spacing)
                tiers = sc.get("strike_tiers")  # tiered spacing: [(max_dist, spacing), ...]
                for exp in self._expiries:
                    option_syms = OptionSymbolBuilder.build_symbols(
                        sym, exp, prices[sym], sr, ss,
                        strike_tiers=tiers,
                    )
                    self._option_symbols.extend(option_syms)
                    all_symbols.extend(option_syms)
            all_symbols.append(sym)

        log.info(
            "TOSRTDAdapter: %d base symbols + %d option symbols across %d expiries",
            len(symbols), len(self._option_symbols), len(self._expiries),
        )

        from _rtd_worker_entry import run_rtd_worker_process

        self._process = mp.Process(
            target=run_rtd_worker_process,
            args=(self._data_queue, self._stop_event, all_symbols),
            daemon=True,
            name="TOSRTDWorker",
        )
        self._process.start()
        self._running = True

        # Start background drain thread
        self._drain_thread = threading.Thread(
            target=self._drain_loop,
            daemon=True,
            name="RTDDrainThread"
        )
        self._drain_thread.start()

        log.info("TOSRTDAdapter started for %s, expiry=%s", symbols, expiry)

    def stop(self) -> None:
        """Stop RTD streaming and clean up."""
        if not self._running:
            return

        self._stop_event.set()
        if self._drain_thread:
            self._drain_thread.join(timeout=2.0)
            self._drain_thread = None

        if self._process:
            self._process.join(timeout=5.0)
            if self._process.is_alive():
                self._process.terminate()
            self._process = None
        self._running = False
        self._option_symbols = []
        self._base_symbols = []
        log.info("TOSRTDAdapter stopped")

    def is_running(self) -> bool:
        """Check if the adapter is actively streaming."""
        return self._running and self._process is not None and self._process.is_alive()

    # ------------------------------------------------------------------
    # Data access
    # ------------------------------------------------------------------

    def _drain_loop(self) -> None:
        """Background thread that continuously drains the queue to prevent memory leaks in the child process."""
        from queue import Empty
        while self._running:
            try:
                data = self._data_queue.get(timeout=0.1)
                if "debug" in data:
                    log.debug("[RTD child] %s", data["debug"])
                    continue
                if "error" in data:
                    log.error("RTD worker error: %s", data["error"])
                    continue
                with self._latest_lock:
                    self._latest_data.update(data)
            except Empty:
                continue
            except EOFError:
                break
            except Exception as e:
                if self._running:
                    log.error("Error draining RTD queue: %s", e)
                break

    def get_snapshot(self) -> dict[str, Any]:
        """
        Get the latest RTD data snapshot.

        Returns:
            Dict mapping "symbol:quote_type" → value, e.g.:
            {"./NQH25C21000:XCME:GAMMA": 0.001, "/ES:XCME:LAST": 5500.25}
        """
        with self._latest_lock:
            return dict(self._latest_data)

    def get_futures_price(self, symbol: str) -> Optional[float]:
        """
        Get the latest LAST price for a futures symbol.

        Args:
            symbol: Futures symbol, e.g. "/ES" or "/ES:XCME"

        Returns:
            Latest price as float, or None if no data yet.
        """
        snapshot = self.get_snapshot()

        # Try with exchange suffix
        exchange = OptionSymbolBuilder.FUTURES_EXCHANGES.get(symbol, "XCBT")
        key = f"{symbol}:{exchange}:LAST"
        price = snapshot.get(key)

        if price is None:
            # Try without exchange
            key = f"{symbol}:LAST"
            price = snapshot.get(key)

        return float(price) if price is not None else None

    def get_option_greeks(self, rtd_symbol: str) -> dict[str, float | int | None]:
        """
        Get the latest Greeks for a specific option symbol.

        Args:
            rtd_symbol: RTD option symbol, e.g. "./NQH25C21000:XCME"

        Returns:
            Dict with keys: GAMMA, DELTA, OPEN_INT, VOLUME, LAST, IMPL_VOL
            (values may be None if not yet received)
        """
        snapshot = self.get_snapshot()
        return {
            "GAMMA": snapshot.get(f"{rtd_symbol}:GAMMA"),
            "DELTA": snapshot.get(f"{rtd_symbol}:DELTA"),
            "OPEN_INT": snapshot.get(f"{rtd_symbol}:OPEN_INT"),
            "VOLUME": snapshot.get(f"{rtd_symbol}:VOLUME"),
            "LAST": snapshot.get(f"{rtd_symbol}:LAST"),
            "IMPL_VOL": snapshot.get(f"{rtd_symbol}:IMPL_VOL"),
        }

    def build_chain_snapshot(self, symbol: str) -> Optional[ChainSnapshot]:
        """
        Build a normalized chain snapshot from RTD data for a futures symbol.

        This converts the flat RTD key-value data into a structured
        ChainSnapshot that can be used by gex_calculator or for
        quick GEX estimation.

        Args:
            symbol: Base futures symbol, e.g. "/ES"

        Returns:
            ChainSnapshot or None if no data available.
        """
        if not self._expiry:
            log.warning("No expiry set — call start() first")
            return None

        price = self.get_futures_price(symbol)
        if price is None:
            log.debug("No futures price yet for %s", symbol)
            return None

        snapshot = self.get_snapshot()

        # If we haven't built option symbols yet, do it now with the live price
        if not self._option_symbols:
            option_syms = OptionSymbolBuilder.build_symbols(
                symbol, self._expiry, price,
                self.config.strike_range, self.config.strike_spacing,
            )
            self._option_symbols = option_syms
            # Note: We can't subscribe mid-stream in this version.
            # The caller should restart with known prices for full coverage.
            log.warning(
                "Option symbols built after price arrival — "
                "restart adapter with prices for full subscription coverage"
            )

        contracts: list[OptionContract] = []
        greeks: dict[str, dict] = {}
        expiry_map: dict[str, date] = {}

        # Build a reverse lookup: rtd_symbol → expiry
        # by re-running build_symbols for each expiry and matching
        sym_configs = self.config.symbol_configs or {}
        sc = sym_configs.get(symbol, {})
        sr = sc.get("strike_range", self.config.strike_range)
        ss = sc.get("strike_spacing", self.config.strike_spacing)
        tiers = sc.get("strike_tiers")
        _symbol_to_expiry: dict[str, date] = {}
        if price and price > 0:
            for exp in self._expiries:
                syms_for_exp = OptionSymbolBuilder.build_symbols(
                    symbol, exp, price, sr, ss, strike_tiers=tiers,
                )
                for s in syms_for_exp:
                    _symbol_to_expiry[s] = exp

        for rtd_sym in self._option_symbols:
            parsed = parse_rtd_option_symbol(rtd_sym)
            if parsed and parsed.base_symbol == symbol:
                # Assign the correct expiry for this symbol
                exp = _symbol_to_expiry.get(rtd_sym, self._expiry)
                parsed.expiry = exp
                contracts.append(parsed)
                expiry_map[rtd_sym] = exp
                greeks[rtd_sym] = {
                    "GAMMA": snapshot.get(f"{rtd_sym}:GAMMA"),
                    "DELTA": snapshot.get(f"{rtd_sym}:DELTA"),
                    "OPEN_INT": snapshot.get(f"{rtd_sym}:OPEN_INT"),
                    "VOLUME": snapshot.get(f"{rtd_sym}:VOLUME"),
                    "LAST": snapshot.get(f"{rtd_sym}:LAST"),
                    "IMPL_VOL": snapshot.get(f"{rtd_sym}:IMPL_VOL"),
                    "VEGA": snapshot.get(f"{rtd_sym}:VEGA"),
                    "THETA": snapshot.get(f"{rtd_sym}:THETA"),
                }

        return ChainSnapshot(
            symbol=symbol,
            futures_price=price,
            expiry=self._expiry,
            timestamp=time.time(),
            contracts=contracts,
            greeks=greeks,
            expiry_map=expiry_map,
        )

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def get_status(self) -> dict[str, Any]:
        """Get adapter health status."""
        return {
            "running": self.is_running(),
            "base_symbols": self._base_symbols,
            "option_symbol_count": len(self._option_symbols),
            "expiry": self._expiry.isoformat() if self._expiry else None,
            "has_data": len(self._latest_data) > 0,
            "data_keys": len(self._latest_data),
        }

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> "TOSRTDAdapter":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop()