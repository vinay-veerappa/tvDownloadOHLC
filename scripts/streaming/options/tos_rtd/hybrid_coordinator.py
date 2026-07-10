"""
Hybrid Coordinator — coordinates Schwab API + TOS RTD data sources.

Phase 2: Provides a unified interface that uses:
  - TOS RTD for real-time futures LAST price (sub-second, no rate limits)
  - TOS RTD for real-time Greeks validation (native gamma vs our BSM)
  - Schwab API for full option chain snapshots (primary source for GEX)

The coordinator is opt-in (config.ENABLE_TOS_RTD) and Windows-only.
When RTD is unavailable, it transparently falls back to Schwab-only mode.
"""
from __future__ import annotations

import logging
import sys
import time
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Optional

from ..config import (
    ENABLE_TOS_RTD,
    TOS_RTD_HEARTBEAT_MS,
    TOS_RTD_STRIKE_RANGE,
    TOS_RTD_STRIKE_SPACING,
    TOS_RTD_SYMBOLS,
    TOS_RTD_SYMBOL_CONFIG,
    _is_tos_running,
)

log = logging.getLogger(__name__)

# Guard: only import RTD on Windows
_RTD_AVAILABLE = False
if sys.platform == "win32":
    try:
        from .adapter import TOSRTDAdapter, RTDConfig, ChainSnapshot
        from .symbol_builder import OptionSymbolBuilder, parse_rtd_option_symbol
        from .rtd_gex_calculator import calculate_futures_gex, FuturesGEXResult, compare_gex_sources, format_comparison_table
        _RTD_AVAILABLE = True
    except ImportError:
        log.warning("tos_rtd package import failed — RTD disabled")


@dataclass
class HybridFuturesQuote:
    """Futures quote that may come from RTD (real-time) or Schwab (polling)."""

    symbol: str
    price: float
    source: str  # "tos_rtd" or "schwab"
    open_price: Optional[float] = None
    timestamp: float = field(default_factory=time.time)


@dataclass
class GreeksValidationResult:
    """Result of comparing TOS native Greeks vs our BSM-computed Greeks."""

    rtd_symbol: str
    strike: float
    option_type: str
    rtd_gamma: Optional[float]
    bsm_gamma: Optional[float]
    gamma_drift_pct: Optional[float]  # |rtd - bsm| / rtd * 100
    rtd_open_int: Optional[int]
    schwab_open_int: Optional[int]
    oi_match: bool


class HybridCoordinator:
    """
    Coordinates TOS RTD and Schwab API data sources.

    Usage::

        coord = HybridCoordinator()
        coord.start()  # Starts RTD if enabled

        # In pipeline loop:
        price = coord.get_futures_price("/ES")  # RTD first, Schwab fallback
        coord.validate_greeks(dealer_levels, "/ES")  # Compare RTD vs BSM

        coord.stop()
    """

    def __init__(
        self,
        symbols: list[str] | None = None,
        expiry: Optional[date] = None,
    ):
        self._enabled = ENABLE_TOS_RTD and _RTD_AVAILABLE
        self._symbols = symbols or TOS_RTD_SYMBOLS
        self._expiry = expiry
        self._adapter: Optional[Any] = None  # TOSRTDAdapter if enabled
        self._schwab_prices: dict[str, float] = {}  # Fallback cache
        self._validation_results: list[GreeksValidationResult] = []

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self, current_prices: dict[str, float] | None = None) -> None:
        """Start the RTD adapter if enabled and TOS desktop is running.

        If current_prices is not provided, performs a two-phase start:
        Phase 1: Subscribe to futures LAST only to get current price.
        Phase 2: Restart with option symbols built from the live price.
        """
        if not self._enabled:
            log.info("TOS RTD disabled — running in Schwab-only mode")
            return

        # Double-check TOS is actually running before attempting COM connection
        if not _is_tos_running():
            log.warning(
                "TOS RTD enabled but ThinkorSwim desktop is not running — "
                "falling back to Schwab-only mode"
            )
            self._enabled = False
            return

        if not self._expiry:
            # Default to nearest Friday
            from datetime import timedelta
            today = date.today()
            days_ahead = 4 - today.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            self._expiry = today + timedelta(days=days_ahead)

        # Build a proper expiry ladder using Schwab-discovered expiries when
        # available, falling back to a theoretical ladder otherwise.
        #
        # Schwab discovery: do a lightweight API call to get the actual
        # available expiries for each futures symbol.  This avoids wasting
        # COM subscriptions on non-existent option symbols (previously ~77%
        # of /ES and ~96% of /NQ subscriptions returned no data).
        from datetime import timedelta as _td

        def _third_friday(y: int, m: int) -> date:
            """Return the 3rd Friday of the given year/month."""
            d = date(y, m, 15)
            while d.weekday() != 4:
                d += _td(days=1)
            return d

        # Determine the max number of expiries across all symbols we monitor.
        max_expiries = max(
            (sc.get("num_expiries", 4) for sc in TOS_RTD_SYMBOL_CONFIG.values()),
            default=4,
        )

        # ── Attempt Schwab expiry discovery ──
        # Query the Hub for the futures option chain to get actual available
        # expiries.  This is a lightweight call (just needs the expiry dates,
        # not full chain data).  If it fails, fall back to theoretical ladder.
        schwab_expiries: dict[str, list[date]] = {}
        try:
            from ..options_fetcher import fetch_futures_option_chain_data, _hub_request
            from ..config import PIPELINE_DTE_TARGETS
            for sym in self._symbols:
                try:
                    # Use a small DTE target set for discovery — we just need
                    # the available expiries, not the full year's chain.
                    discovery_dte = list(range(0, 45))  # 0-44 DTE covers 0DTE through ~6 weeks
                    chain = fetch_futures_option_chain_data(sym, discovery_dte)
                    if chain and chain.contracts:
                        # Extract unique expiry dates from the contracts
                        expiry_dates = sorted({
                            c.expiry for c in chain.contracts
                            if isinstance(c.expiry, date) and c.expiry >= date.today()
                        })
                        if expiry_dates:
                            schwab_expiries[sym] = expiry_dates
                            log.info(
                                "Schwab discovery for %s: %d actual expiries found (%s)",
                                sym, len(expiry_dates),
                                ", ".join(e.isoformat() for e in expiry_dates[:max_expiries]),
                            )
                except Exception as exc:
                    log.debug("Schwab expiry discovery failed for %s: %s", sym, exc)
        except ImportError:
            log.debug("Schwab fetcher not available for expiry discovery — using theoretical ladder")

        # Build the expiry list
        if schwab_expiries:
            # Use Schwab-discovered expiries — merge across all symbols, trim to max
            all_discovered: set[date] = set()
            for exp_list in schwab_expiries.values():
                all_discovered.update(exp_list)
            expiries = sorted(all_discovered)[:max_expiries]
            if not expiries:
                # Fallback if discovery returned empty
                expiries = [self._expiry]
            log.info(
                "RTD expiry ladder (Schwab-discovered): %d expiries (%s)",
                len(expiries),
                ", ".join(e.isoformat() for e in expiries),
            )
        else:
            # Fallback: theoretical ladder (0DTE + weekly Fridays + monthly)
            today = date.today()
            expiries_set: set[date] = set()

            # Add today as a 0DTE expiry if it's a weekday
            if today.weekday() < 5:
                expiries_set.add(today)

            # Add the nearest Friday
            expiries_set.add(self._expiry)

            # Add weekly Fridays up to ~6 weeks out
            next_fri = self._expiry
            for _ in range(6):
                next_fri = next_fri + _td(days=7)
                expiries_set.add(next_fri)

            # Add monthly (3rd Friday) expiries for the next N months
            for months_ahead in range(0, max_expiries + 2):
                m = today.month + months_ahead
                y = today.year + (m - 1) // 12
                m = ((m - 1) % 12) + 1
                monthly = _third_friday(y, m)
                if monthly >= today:
                    expiries_set.add(monthly)

            expiries = sorted(expiries_set)[:max_expiries]
            log.info(
                "RTD expiry ladder (theoretical fallback): %d expiries (%s)",
                len(expiries),
                ", ".join(e.isoformat() for e in expiries),
            )

        config = RTDConfig(
            strike_range=TOS_RTD_STRIKE_RANGE,
            strike_spacing=TOS_RTD_STRIKE_SPACING,
            symbol_configs=TOS_RTD_SYMBOL_CONFIG,
        )
        self._adapter = TOSRTDAdapter(config)

        if current_prices:
            # Prices provided — single-phase start with option symbols
            self._start_with_prices(current_prices, expiries)
        else:
            # Two-phase start: get price first, then restart with options
            self._start_two_phase(expiries)

    def _start_with_prices(self, current_prices: dict[str, float], expiries: list[date] | None = None) -> None:
        """Start RTD with known prices — subscribes to futures + options immediately."""
        try:
            self._adapter.start(
                symbols=self._symbols,
                expiry=self._expiry,
                current_price=current_prices,
                expiries=expiries,
            )
            log.info("HybridCoordinator started with RTD for %s (prices provided)", self._symbols)
        except Exception as e:
            log.error("RTD start failed — falling back to Schwab-only: %s", e)
            self._enabled = False
            self._adapter = None

    def _start_two_phase(self, expiries: list[date] | None = None) -> None:
        """Two-phase start: get futures price from RTD, then restart with option symbols."""
        import time
        try:
            # Phase 1: Subscribe to futures LAST only
            self._adapter.start(symbols=self._symbols, expiry=self._expiry)
            log.info("RTD Phase 1: Waiting for futures LAST price...")

            prices = {}
            for i in range(10):
                time.sleep(1)
                
                if self._adapter._process and not self._adapter._process.is_alive():
                    log.error(f"RTD Phase 1: Child process died unexpectedly! Exit code: {self._adapter._process.exitcode}")
                    break

                for sym in self._symbols:
                    p = self._adapter.get_futures_price(sym)
                    if p and p > 0:
                        prices[sym] = p
                if all(s in prices for s in self._symbols):
                    break

            if not prices:
                log.warning("RTD Phase 1: No futures price received after 10s — falling back")
                self._adapter.stop()
                self._enabled = False
                return

            log.info("RTD Phase 1 complete: %s", prices)

            # Phase 2: Restart with option symbols
            self._adapter.stop()
            time.sleep(1)
            self._adapter.start(
                symbols=self._symbols,
                expiry=self._expiry,
                current_price=prices,
                expiries=expiries,
            )
            log.info("RTD Phase 2: Restarted with option symbols for %s", list(prices.keys()))

        except Exception as e:
            log.error("RTD two-phase start failed — falling back to Schwab-only: %s", e)
            self._enabled = False
            self._adapter = None

    def stop(self) -> None:
        """Stop the RTD adapter."""
        if self._adapter:
            self._adapter.stop()
            self._adapter = None
        log.info("HybridCoordinator stopped")

    @property
    def is_rtd_active(self) -> bool:
        """Check if RTD is enabled and running."""
        return self._enabled and self._adapter is not None and self._adapter.is_running()

    # ------------------------------------------------------------------
    # Futures price — RTD first, Schwab fallback
    # ------------------------------------------------------------------

    def get_futures_price(self, symbol: str, schwab_price: float | None = None) -> HybridFuturesQuote | None:
        """
        Get the latest futures price, preferring RTD over Schwab.

        Args:
            symbol: Futures symbol, e.g. "/ES"
            schwab_price: Price from Schwab API (if already fetched)

        Returns:
            HybridFuturesQuote with source tag, or None if no data.
        """
        # Cache Schwab price as fallback
        if schwab_price is not None:
            self._schwab_prices[symbol] = schwab_price

        # Try RTD first
        if self.is_rtd_active:
            rtd_price = self._adapter.get_futures_price(symbol)
            if rtd_price is not None and rtd_price > 0:
                return HybridFuturesQuote(
                    symbol=symbol,
                    price=rtd_price,
                    source="tos_rtd",
                )

        # Fallback to Schwab
        cached = self._schwab_prices.get(symbol)
        if cached is not None and cached > 0:
            return HybridFuturesQuote(
                symbol=symbol,
                price=cached,
                source="schwab",
            )

        return None

    # ------------------------------------------------------------------
    # Greeks validation — compare RTD native vs BSM computed
    # ------------------------------------------------------------------

    def validate_greeks(
        self,
        dealer_levels: Any,
        symbol: str,
        bsm_greeks: dict[float, dict[str, float]] | None = None,
    ) -> list[GreeksValidationResult]:
        """
        Compare TOS RTD native Greeks against our BSM-computed Greeks.

        Args:
            dealer_levels: DealerLevels from gex_calculator (has .gex_by_strike)
            symbol: Base futures symbol, e.g. "/ES"
            bsm_greeks: Optional dict {strike: {GAMMA: ..., DELTA: ...}}
                       from our BSM model. If None, extracts from dealer_levels.

        Returns:
            List of GreeksValidationResult for contracts with both RTD + BSM data.
        """
        if not self.is_rtd_active:
            return []

        results: list[GreeksValidationResult] = []

        # Get RTD chain snapshot
        chain_snap = self._adapter.build_chain_snapshot(symbol)
        if chain_snap is None:
            return []

        # Build BSM gamma lookup from dealer_levels if not provided
        bsm_gamma_lookup: dict[float, float] = {}
        if bsm_greeks:
            for strike, greeks in bsm_greeks.items():
                bsm_gamma_lookup[strike] = greeks.get("GAMMA", 0.0)
        elif hasattr(dealer_levels, "strike_gex"):
            # Extract from DealerLevels.strike_gex (list of StrikeGEX).
            # StrikeGEX stores per-strike call/put GEX, not raw gamma.
            # We reconstruct an approximate per-strike gamma by normalising
            # the net_gex by OI * multiplier * spot.  This is an approximation
            # but sufficient for drift comparison.
            from ..config import CONTRACT_MULTIPLIER
            spot = getattr(dealer_levels, "spot", 0.0) or 1.0
            for sg in dealer_levels.strike_gex:
                total_oi = (sg.call_oi + sg.put_oi)
                if total_oi > 0 and spot > 0:
                    # gamma ~ net_gex / (oi * multiplier * spot)
                    bsm_gamma_lookup[sg.strike] = abs(sg.net_gex) / (total_oi * CONTRACT_MULTIPLIER * spot)
                else:
                    bsm_gamma_lookup[sg.strike] = 0.0

        for rtd_sym, greeks in chain_snap.greeks.items():
            rtd_gamma = greeks.get("GAMMA")
            rtd_oi = greeks.get("OPEN_INT")

            # Find matching contract
            from .symbol_builder import parse_rtd_option_symbol
            parsed = parse_rtd_option_symbol(rtd_sym)
            if not parsed or parsed.base_symbol != symbol:
                continue

            bsm_gamma = bsm_gamma_lookup.get(parsed.strike)

            # Compute drift
            drift_pct = None
            if rtd_gamma is not None and bsm_gamma is not None and rtd_gamma != 0:
                drift_pct = abs(rtd_gamma - bsm_gamma) / abs(rtd_gamma) * 100.0

            result = GreeksValidationResult(
                rtd_symbol=rtd_sym,
                strike=parsed.strike,
                option_type=parsed.option_type,
                rtd_gamma=rtd_gamma,
                bsm_gamma=bsm_gamma,
                gamma_drift_pct=drift_pct,
                rtd_open_int=rtd_oi,
                schwab_open_int=None,  # Would need Schwab chain matching
                oi_match=False,
            )
            results.append(result)

        self._validation_results = results
        return results

    def get_drift_summary(self) -> dict[str, Any]:
        """Get summary of Greeks drift validation."""
        if not self._validation_results:
            return {"active": False, "count": 0}

        drifts = [r.gamma_drift_pct for r in self._validation_results if r.gamma_drift_pct is not None]
        if not drifts:
            return {"active": True, "count": len(self._validation_results), "avg_drift": None}

        avg_drift = sum(drifts) / len(drifts)
        max_drift = max(drifts)
        high_drift_count = sum(1 for d in drifts if d > 5.0)

        return {
            "active": True,
            "count": len(self._validation_results),
            "avg_drift_pct": round(avg_drift, 4),
            "max_drift_pct": round(max_drift, 4),
            "high_drift_count": high_drift_count,  # drift > 5%
            "threshold_pct": 5.0,
        }

    # ------------------------------------------------------------------
    # RTD GEX calculation — compute dealer levels directly from futures options
    # ------------------------------------------------------------------

    def calculate_rtd_gex(self, symbol: str, min_oi_floor: int | None = None) -> Optional[Any]:
        """
        Calculate dealer levels directly from RTD futures options data.

        This produces "true futures GEX" — levels computed from actual
        futures options book, not translated from cash/ETF space.

        Args:
            symbol: Futures symbol, e.g. "/ES"
            min_oi_floor: Minimum OI for wall detection.  If None, looks up
                         per-symbol default from TOS_RTD_SYMBOL_CONFIG.

        Returns:
            FuturesGEXResult or None if RTD not active or no data.
        """
        if not self.is_rtd_active or not _RTD_AVAILABLE:
            return None

        # Resolve per-symbol OI floor from config if not explicitly provided
        if min_oi_floor is None:
            sym_config = TOS_RTD_SYMBOL_CONFIG.get(symbol, {})
            min_oi_floor = sym_config.get("min_oi_floor", 25)

        # Wait a moment for option Greeks to arrive if just started
        import time
        time.sleep(2)

        return calculate_futures_gex(self._adapter, symbol, min_oi_floor=min_oi_floor)

    def compare_gex(self, rtd_result: Any, translated_levels: Any) -> str:
        """
        Compare RTD-computed futures GEX against Schwab-translated levels.

        Args:
            rtd_result: FuturesGEXResult from calculate_rtd_gex()
            translated_levels: TranslatedLevels from the Schwab pipeline

        Returns:
            Formatted comparison table string.
        """
        if not rtd_result or not translated_levels:
            return "Comparison skipped — missing data"

        compare_gex_sources(rtd_result, translated_levels)
        return format_comparison_table(rtd_result)

    # ------------------------------------------------------------------
    # RTD snapshot access
    # ------------------------------------------------------------------

    def get_rtd_snapshot(self) -> dict[str, Any]:
        """Get the raw RTD data snapshot (if RTD is active)."""
        if not self.is_rtd_active:
            return {}
        return self._adapter.get_snapshot()

    def get_status(self) -> dict[str, Any]:
        """Get coordinator status for health monitoring."""
        if not self._enabled:
            return {"mode": "schwab_only", "rtd_active": False}

        if not self.is_rtd_active:
            return {"mode": "schwab_only", "rtd_active": False, "rtd_enabled": True}

        adapter_status = self._adapter.get_status()
        drift = self.get_drift_summary()

        # Check if RTD GEX is primary
        try:
            from ..config import TOS_RTD_GEX_AS_PRIMARY
            gex_mode = "primary" if TOS_RTD_GEX_AS_PRIMARY else "supplementary"
        except ImportError:
            gex_mode = "supplementary"

        return {
            "mode": "hybrid",
            "rtd_active": True,
            "rtd_enabled": True,
            "rtd_gex_mode": gex_mode,
            "adapter": adapter_status,
            "greeks_validation": drift,
        }