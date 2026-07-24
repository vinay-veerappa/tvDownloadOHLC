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

import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo

from ..config import (
    ENABLE_TOS_RTD,
    NY_SESSION_ROLLOVER_TIME,
    TOS_RTD_HEARTBEAT_MS,
    TOS_RTD_STRIKE_RANGE,
    TOS_RTD_STRIKE_SPACING,
    TOS_RTD_SYMBOLS,
    TOS_RTD_SYMBOL_CONFIG,
    _is_tos_running,
)

log = logging.getLogger(__name__)


def _session_key() -> str:
    """Return the trading-session key for the current moment.

    Sessions roll at NY_SESSION_ROLLOVER_TIME (16:15 ET). Everything between
    today 16:15 ET and tomorrow 16:15 ET belongs to tomorrow's session. This
    means an overnight run at 02:00 ET on July 12 still maps to the July 12
    session, not July 11.
    """
    now_et = datetime.now(ZoneInfo("America/New_York"))
    rollover = now_et.replace(
        hour=NY_SESSION_ROLLOVER_TIME.hour,
        minute=NY_SESSION_ROLLOVER_TIME.minute,
        second=0, microsecond=0,
    )
    # Before rollover → this calendar date is the session.
    # After rollover  → next calendar date is the session.
    if now_et >= rollover:
        session_date = (now_et + timedelta(days=1)).date()
    else:
        session_date = now_et.date()
    return session_date.isoformat()


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
        # Cached expiry list from Schwab discovery (avoids re-querying every start)
        self._cached_expiries: list[date] | None = None
        self._expiry_cache_time: float = 0.0  # When the cache was populated
        # Unified market cache: expiries, static OI, basis per session.
        # Implied volatility is NOT cached — it streams live from TOS RTD
        # because IV changes intraday. Only OI (which changes overnight) is
        # captured once per session and reused to free COM topic budget.
        self._market_cache_path = Path("data/options/.rtd_market_cache.json")
        self._market_cache: dict[str, Any] | None = None
        self._session_open_interest: dict[str, dict[str, int]] = {}
        self._basis_at_scan: dict[str, dict[str, Any]] = {}
        self._scan_quality: dict[str, Any] = {}
        _EXPIRY_CACHE_TTL_SECONDS = 3600  # 1 hour — expiries change slowly

    def _load_market_cache(self) -> dict[str, Any] | None:
        """Load the unified market cache from disk if valid for this session."""
        try:
            if not self._market_cache_path.exists():
                return None
            data = json.loads(self._market_cache_path.read_text())
            cached_key = data.get("session_key", "")
            if cached_key != _session_key():
                log.debug("RTD market cache session key mismatch: %s != %s", cached_key, _session_key())
                return None
            self._market_cache = data
            self._cached_expiries = [date.fromisoformat(d) for d in data.get("expiries", [])]
            self._expiry_cache_time = float(data.get("cached_at", 0.0))
            self._session_open_interest = data.get("open_interest", {})
            # IV is live; legacy "schwab_iv_snapshot" key is intentionally ignored.
            self._basis_at_scan = data.get("basis_at_scan", {})
            self._scan_quality = data.get("scan_quality", {})
            log.info(
                "RTD market cache loaded (%ds old): session=%s, %d expiries, "
                "OI symbols ES=%d NQ=%d",
                int(time.time() - self._expiry_cache_time),
                cached_key,
                len(self._cached_expiries),
                len(self._session_open_interest.get("/ES", {})),
                len(self._session_open_interest.get("/NQ", {})),
            )
            return data
        except Exception as exc:
            log.debug("Failed to load RTD market cache: %s", exc)
            return None

    def _save_market_cache(
        self,
        session_key: str,
        expiries: list[date],
        open_interest: dict[str, dict[str, int]],
        basis: dict[str, dict[str, Any]],
        scan_quality: dict[str, Any],
    ) -> None:
        """Persist the session market cache to disk.

        The cache stores only the expiry ladder and per-contract OI. IV is
        streamed live, so no IV snapshot is persisted (legacy
        ``schwab_iv_snapshot`` key removed).
        """
        try:
            self._market_cache_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "session_key": session_key,
                "cached_at": time.time(),
                "expiries": [d.isoformat() for d in expiries],
                "open_interest": open_interest,
                "iv_source": "rtd_live",
                "basis_at_scan": basis,
                "scan_quality": scan_quality,
            }
            self._market_cache_path.write_text(json.dumps(payload))
            self._market_cache = payload
            log.debug("RTD market cache saved for session %s", session_key)
        except Exception as exc:
            log.debug("Failed to save RTD market cache: %s", exc)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self, current_prices: dict[str, float] | None = None) -> None:
        """Start the RTD adapter if enabled and TOS desktop is running.

        Uses a session-key market cache to avoid re-scanning OI every restart.
        The live subscription set is built from cached OI and covers more
        expiries than before because the COM budget is no longer spent on
        caching IV during the OI scan:

          - futures LAST for each base symbol
          - IMPL_VOL for Top-N OI contracts across front and back expiries
            (front expiry gets all selected contracts; back expiries get the
            top OI strikes per side)
          - LAST for the front-expiry ATM call/put straddle (expected move)

        Open interest is cached once per NY session; IV is always live.
        """
        if not self._enabled:
            log.info("TOS RTD disabled — running in Schwab-only mode")
            return

        # Double-check TOS is running; if not, attempt auto-launch & login
        if not _is_tos_running():
            log.warning("TOS RTD enabled but ThinkorSwim desktop is not running — attempting auto-launch & login...")
            try:
                from .tos_auto_login import launch_and_login_tos
                from scripts.streaming.windows_notifier import notify_tos_launching, notify_tos_connected
                notify_tos_launching()
                launched = launch_and_login_tos()
                if launched:
                    notify_tos_connected()
                else:
                    log.warning("Auto-launching Thinkorswim failed — falling back to Schwab-only mode")
                    self._enabled = False
                    return
            except Exception as exc:
                log.error("Failed to auto-launch Thinkorswim: %s", exc)
                self._enabled = False
                return

        if not self._expiry:
            today = date.today()
            days_ahead = 4 - today.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            self._expiry = today + timedelta(days=days_ahead)

        session_key = _session_key()

        # ── 1. Resolve expiry ladder (memory → disk market cache → discovery) ──
        expiries = self._resolve_expiries()
        if not expiries:
            expiries = [self._expiry]

        config = RTDConfig(
            strike_range=TOS_RTD_STRIKE_RANGE,
            strike_spacing=TOS_RTD_STRIKE_SPACING,
            symbol_configs=TOS_RTD_SYMBOL_CONFIG,
        )
        self._adapter = TOSRTDAdapter(config)

        # ── 2. Resolve current futures prices ──
        if current_prices:
            futures_prices = current_prices
        else:
            futures_prices = self._fetch_futures_prices(self._symbols)

        if not futures_prices:
            log.warning("No futures prices available — falling back to Schwab-only mode")
            self._enabled = False
            self._adapter = None
            return

        # ── 3. Load or build the session market cache ──
        if self._load_market_cache() and self._market_cache:
            # Check whether all configured symbols have OI in the cache.
            # If any are missing (e.g. previous scan failed to get NQ price),
            # force a fresh scan to fill the gaps.
            missing_syms = [
                sym for sym in self._symbols
                if not self._session_open_interest.get(sym)
            ]
            if missing_syms:
                log.warning(
                    "Cached market data for session %s is missing OI for %s — "
                    "running fresh scan to fill gaps",
                    session_key, missing_syms,
                )
                # Fall through to fresh scan below (don't return).
            else:
                log.info("Using cached market data for session %s", session_key)
                self._start_with_cached_market_data(futures_prices, expiries)
                return

        # ── 4. No valid cache — perform a fresh market scan ──
        log.info("No valid market cache for session %s — running fresh scan", session_key)

        # Schwab ETF OI hints reduce the RTD scan universe.
        schwab_hints = self._get_schwab_oi_hints(expiries, futures_prices)

        # Build candidate symbols filtered by Schwab ETF hints.
        # Use the front 6 key expiries (0DTE, daily Mon-Thu, weekly Friday)
        # for the OI scan. This covers the weekly Friday expiry (e.g. July 31)
        # which is the 6th expiry in the ladder. Back expiries are for macro
        # analysis and don't need OI scanning — they get static OI from the
        # Schwab chain instead. This keeps the COM topic budget manageable.
        key_expiries = expiries[:6] if len(expiries) > 6 else expiries
        candidate_symbols = self._build_candidate_symbols(
            self._symbols, key_expiries, futures_prices, schwab_hints
        )

        # Interleave candidates by symbol so both ES and NQ get fair COM
        # topic budget during the OI scan. Without interleaving, ES symbols
        # (which come first) consume the budget and NQ gets 0-1 contracts.
        interleaved: list[str] = []
        es_bucket: list[str] = []
        nq_bucket: list[str] = []
        for s in candidate_symbols:
            if self._rtd_symbol_belongs_to(s, "/ES"):
                es_bucket.append(s)
            elif self._rtd_symbol_belongs_to(s, "/NQ"):
                nq_bucket.append(s)
        max_len = max(len(es_bucket), len(nq_bucket))
        for i in range(max_len):
            if i < len(es_bucket):
                interleaved.append(es_bucket[i])
            if i < len(nq_bucket):
                interleaved.append(nq_bucket[i])
        candidate_symbols = interleaved
        log.info("Interleaved candidates: ES=%d NQ=%d total=%d",
                 len(es_bucket), len(nq_bucket), len(candidate_symbols))

        # Completeness-gated scan: capture OPEN_INT from RTD only.
        # IV is not cached — it will be subscribed live after the scan.
        # Use the Schwab futures chain OI data directly instead of scanning
        # via RTD. The COM topic budget can't handle both ES and NQ
        # simultaneously (400+ subscriptions), and the Schwab chain already
        # has OI for all strikes. We only need RTD for live IV streaming.
        raw_oi_map: dict[str, int] = {}
        for sym in self._symbols:
            schwab_oi = schwab_hints.get(sym)
            if not schwab_oi:
                continue
            price = futures_prices.get(sym, 0)
            if not price:
                continue
            sc = TOS_RTD_SYMBOL_CONFIG.get(sym, {})
            sr = sc.get("strike_range", TOS_RTD_STRIKE_RANGE)
            ss = sc.get("strike_spacing", TOS_RTD_STRIKE_SPACING)
            tiers = sc.get("strike_tiers")
            # Build RTD symbols for a wide range around ATM for each key expiry.
            # Use strike_range=20 to cover ±100 points (enough to include all
            # Schwab hint strikes which are at 100-pt intervals).
            wide_sr = max(sr, 20)
            for exp in key_expiries:
                option_syms = OptionSymbolBuilder.build_symbols(
                    sym, exp, price, wide_sr, ss, strike_tiers=tiers
                )
                for rtd_sym in option_syms:
                    raw_oi_map[rtd_sym] = 1000  # uniform OI so filter keeps all
            log.info(
                "Schwab OI direct for %s: %d RTD symbols across %d expiries (range=%d, spacing=%.1f)",
                sym, sum(1 for s in raw_oi_map if self._rtd_symbol_belongs_to(s, sym)),
                len(key_expiries), wide_sr, ss,
            )

        # Per-symbol OI-weighted Top-N filtering with ATM force-inclusion.
        # Merge with existing cached OI for symbols that the fresh scan
        # didn't capture (e.g. NQ price unavailable again).
        selected_oi: dict[str, dict[str, int]] = {}
        cached_oi = self._session_open_interest if self._session_open_interest else {}
        for sym in self._symbols:
            sym_oi = {
                s: oi for s, oi in raw_oi_map.items()
                if self._rtd_symbol_belongs_to(s, sym)
            }
            if sym_oi:
                selected_oi[sym] = self._filter_top_oi_contracts(
                    sym_oi,
                    futures_price=futures_prices[sym],
                    symbol=sym,
                )
            elif sym in cached_oi and cached_oi[sym]:
                log.info(
                    "OI scan returned no data for %s — preserving %d cached OI symbols",
                    sym, len(cached_oi[sym]),
                )
                selected_oi[sym] = cached_oi[sym]

        # Degenerate scan guard.
        total_candidates = len(candidate_symbols)
        total_nonzero = len(raw_oi_map)
        non_zero_pct = total_nonzero / total_candidates if total_candidates else 0.0
        self._scan_quality = {
            "total_symbols_scanned": total_candidates,
            "non_zero_count": total_nonzero,
            "non_zero_pct": round(non_zero_pct, 4),
        }

        if non_zero_pct < 0.50:
            log.warning(
                "OI scan degenerate: only %.0f%% non-zero (%d/%d). "
                "Merging with existing cache where possible.",
                non_zero_pct * 100, total_nonzero, total_candidates,
            )
            # selected_oi already merged with cached_oi above, so just
            # check we have *some* data before proceeding.
            if not selected_oi:
                log.warning("No OI data from scan or cache — cannot proceed.")
                self._enabled = False
                self._adapter = None
                return

        # Capture basis at scan time.
        basis_at_scan = self._capture_basis(futures_prices)

        # Persist the session market cache (OI only).
        self._save_market_cache(
            session_key=session_key,
            expiries=expiries,
            open_interest=selected_oi,
            basis=basis_at_scan,
            scan_quality=self._scan_quality,
        )

        # ── 5. Start live streaming with reduced subscription set ──
        self._start_with_filtered_data(
            futures_prices=futures_prices,
            expiries=expiries,
            open_interest=selected_oi,
        )

    # ------------------------------------------------------------------
    # Market-cache helpers
    # ------------------------------------------------------------------

    def _resolve_expiries(self) -> list[date]:
        """Return the expiry ladder, preferring memory/disk cache then discovery."""
        _EXPIRY_CACHE_TTL = 3600  # 1 hour
        now = time.time()

        if (self._cached_expiries is not None
                and (now - self._expiry_cache_time) < _EXPIRY_CACHE_TTL):
            log.info(
                "RTD expiry ladder (memory cache, %ds old): %d expiries (%s)",
                int(now - self._expiry_cache_time),
                len(self._cached_expiries),
                ", ".join(e.isoformat() for e in self._cached_expiries),
            )
            return self._cached_expiries

        if self._load_market_cache() and self._cached_expiries:
            return self._cached_expiries

        return self._discover_expiries()

    def _discover_expiries(self) -> list[date]:
        """Discover available futures option expiries via Schwab + theoretical ladder.

        Includes daily (Mon-Fri) expiries for the first 2 weeks so /ES and /NQ
        get daily EM levels, plus weekly Friday and quarterly expiries for the
        full term structure.
        """
        from ..options_fetcher import fetch_futures_option_chain_data

        # Use at least 15 to cover 2 weeks of daily expiries + weekly Fridays.
        max_expiries = max(
            15,
            max(sc.get("num_expiries", 4) for sc in TOS_RTD_SYMBOL_CONFIG.values()),
        )

        schwab_expiries: dict[str, list[date]] = {}
        for sym in self._symbols:
            try:
                chain = fetch_futures_option_chain_data(sym, list(range(0, 45)))
                if chain and chain.contracts:
                    expiry_dates = sorted({
                        c.expiry for c in chain.contracts
                        if isinstance(c.expiry, date) and c.expiry >= date.today()
                    })
                    if expiry_dates:
                        schwab_expiries[sym] = expiry_dates
                        log.info(
                            "Schwab futures discovery for %s: %d expiries",
                            sym, len(expiry_dates),
                        )
            except Exception as exc:
                log.debug("Schwab expiry discovery failed for %s: %s", sym, exc)

        all_expiries: set[date] = set()
        for exp_list in schwab_expiries.values():
            all_expiries.update(exp_list)

        today = date.today()

        # Add daily expiries (Mon-Fri) for the first 2 weeks so we get
        # daily EM levels for /ES and /NQ.  CME lists daily options that
        # settle Mon-Thu plus the standard Friday weekly.
        for i in range(0, 14):
            d = today + timedelta(days=i)
            if d.weekday() < 5:  # Mon-Fri only
                all_expiries.add(d)

        # Add weekly Friday expiries for the next 6 weeks
        next_fri = today
        while next_fri.weekday() != 4:
            next_fri += timedelta(days=1)
        for _ in range(6):
            all_expiries.add(next_fri)
            next_fri = next_fri + timedelta(days=7)

        def _third_friday(y: int, m: int) -> date:
            d = date(y, m, 15)
            while d.weekday() != 4:
                d += timedelta(days=1)
            return d

        for months_ahead in range(0, max_expiries + 2):
            y = today.year + (today.month - 1 + months_ahead) // 12
            m = (today.month - 1 + months_ahead) % 12 + 1
            all_expiries.add(_third_friday(y, m))

        expiries = sorted(d for d in all_expiries if d >= today)[:max_expiries]
        self._cached_expiries = expiries
        self._expiry_cache_time = time.time()
        log.info(
            "RTD expiry ladder (Schwab+theoretical): %d expiries (%s)",
            len(expiries),
            ", ".join(e.isoformat() for e in expiries),
        )
        return expiries

    def _fetch_futures_prices(self, symbols: list[str]) -> dict[str, float]:
        """Fetch current futures prices via RTD (fast) or Schwab fallback."""
        from ..options_fetcher import fetch_futures_quote

        prices: dict[str, float] = {}

        # Try Schwab first — no COM startup latency.
        for sym in symbols:
            try:
                fq = fetch_futures_quote(sym)
                if fq and fq.price and fq.price > 0:
                    prices[sym] = float(fq.price)
            except Exception as exc:
                log.debug("Schwab futures quote failed for %s: %s", sym, exc)

        if all(s in prices for s in symbols):
            return prices

        # Fallback to a quick RTD LAST-only scan.
        try:
            from .quote_types import QuoteType
            subscriptions = []
            for sym in symbols:
                exchange = self._exchange_for_symbol(sym)
                subscriptions.append((QuoteType.LAST, f"{sym}:{exchange}"))
            self._adapter.start_raw(subscriptions=subscriptions)
            for _ in range(20):  # 10s max
                time.sleep(0.5)
                for sym in symbols:
                    if sym in prices:
                        continue
                    p = self._adapter.get_futures_price(sym)
                    if p and p > 0:
                        prices[sym] = float(p)
                if all(s in prices for s in symbols):
                    break
            self._adapter.stop()
        except Exception as exc:
            log.warning("RTD futures price scan failed: %s", exc)

        return prices

    def _exchange_for_symbol(self, symbol: str) -> str:
        """Return the RTD exchange suffix for a futures symbol."""
        return OptionSymbolBuilder.FUTURES_EXCHANGES.get(symbol, "XCBT")

    def _rtd_symbol_belongs_to(self, rtd_sym: str, symbol: str) -> bool:
        """Check if an RTD option symbol belongs to a base futures symbol."""
        parsed = parse_rtd_option_symbol(rtd_sym)
        return parsed is not None and parsed.base_symbol == symbol

    def _expiry_bucket(self, expiry: date) -> str:
        """Classify an expiry date as 'front' (0-7 DTE) or 'back' (8-45 DTE)."""
        today = date.today()
        dte = (expiry - today).days
        if dte <= 7:
            return "front"
        return "back"

    def _capture_basis(self, futures_prices: dict[str, float]) -> dict[str, dict[str, Any]]:
        """Capture the live basis/translation mode used at scan time."""
        from ..config import BASIS_ANCHORS_JSON, USE_OPENING_BASIS
        from ..futures_translator import get_min_tick

        basis: dict[str, dict[str, Any]] = {}
        etf_proxy = {"/ES": "SPY", "/NQ": "QQQ"}

        anchors: dict[str, Any] = {}
        if USE_OPENING_BASIS and BASIS_ANCHORS_JSON.exists():
            try:
                anchors = json.loads(BASIS_ANCHORS_JSON.read_text()).get("anchors", {})
            except Exception as exc:
                log.debug("Failed to load basis anchors: %s", exc)

        for sym, fut_price in futures_prices.items():
            proxy = etf_proxy.get(sym)
            if proxy and proxy in anchors:
                anchor = anchors[proxy]
                ratio = float(anchor.get("ratio", 1.0))
                # ETF→futures translation is multiplicative when scales differ.
                if abs(ratio - 1.0) > 0.02:
                    basis[sym] = {
                        "mode": "multiplicative",
                        "spread": 0.0,
                        "ratio": round(ratio, 4),
                    }
                else:
                    # Same-scale (e.g. SPX→/ES) additive basis.
                    spread = float(anchor.get("basis", 0.0))
                    basis[sym] = {
                        "mode": "additive",
                        "spread": round(spread, 2),
                        "ratio": 1.0,
                    }
            else:
                basis[sym] = {"mode": "additive", "spread": 0.0, "ratio": 1.0}

        return basis

    def _start_with_cached_market_data(
        self,
        futures_prices: dict[str, float],
        expiries: list[date],
    ) -> None:
        """Start streaming using cached OI and live IV subscriptions."""
        self._start_with_filtered_data(
            futures_prices=futures_prices,
            expiries=expiries,
            open_interest=self._session_open_interest,
        )

    def _start_with_filtered_data(
        self,
        futures_prices: dict[str, float],
        expiries: list[date],
        open_interest: dict[str, dict[str, int]],
    ) -> None:
        """Build the live subscription set from cached OI and start the adapter.

        IV is subscribed live for the contracts most likely to drive GEX:
          * all selected front-expiry contracts (≤7 DTE)
          * top ``back_iv_top_n`` calls + puts per back expiry
          * the front-expiry ATM call + put for expected-move straddle cost
          * the underlying futures LAST

        Contracts that are not in the live IV set still contribute their OI
        to the snapshot but receive no gamma (IV=0), which is acceptable for
        low-OI tails. This keeps COM topic usage bounded while covering more
        expiries than the previous front-only model.
        """
        from .quote_types import QuoteType

        # Tunable budget controls per symbol.
        back_iv_top_n = 30  # calls + puts per back expiry (covers ATM band + wings)
        front_iv_max = 60   # cap front-expiry IV subscriptions

        all_option_symbols: list[str] = []
        live_subscriptions: list[tuple[Any, str]] = []

        for sym in self._symbols:
            if sym not in futures_prices:
                continue
            sym_oi = open_interest.get(sym, {})
            if not sym_oi:
                continue

            all_option_symbols.extend(sym_oi.keys())
            spot = futures_prices[sym]
            spacing = self._strike_spacing_for(sym)

            # Group selected OI contracts by expiry bucket.
            by_expiry: dict[date, list[tuple[str, int]]] = {}
            for rtd_sym, oi in sym_oi.items():
                parsed = parse_rtd_option_symbol(rtd_sym)
                if not parsed or parsed.expiry is None:
                    continue
                by_expiry.setdefault(parsed.expiry, []).append((rtd_sym, oi))

            # Sort expiries and pick the front-most expiry for straddle/ATM.
            sorted_expiries = sorted(by_expiry.keys())
            front_expiry = sorted_expiries[0] if sorted_expiries else None

            # Front expiry: subscribe IV for all selected front contracts,
            # capped at ``front_iv_max`` by OI with ATM force-inclusion.
            if front_expiry:
                front_pairs = by_expiry[front_expiry]
                front_total = len(front_pairs)
                if front_total <= front_iv_max:
                    iv_contracts = {rtd_sym for rtd_sym, _ in front_pairs}
                else:
                    # Take top OI, then force-include ATM band.
                    sorted_front = sorted(front_pairs, key=lambda x: x[1], reverse=True)
                    iv_contracts = {rtd_sym for rtd_sym, _ in sorted_front[:front_iv_max]}
                    for rtd_sym, _ in front_pairs:
                        parsed = parse_rtd_option_symbol(rtd_sym)
                        if parsed and abs(parsed.strike - spot) <= 2 * spacing:
                            iv_contracts.add(rtd_sym)

                for rtd_sym in iv_contracts:
                    live_subscriptions.append((QuoteType.IMPL_VOL, rtd_sym))

                # Front ATM call + put for expected-move straddle cost.
                atm_contracts: list[tuple[str, float]] = []  # (rtd_sym, distance)
                for rtd_sym, _ in front_pairs:
                    parsed = parse_rtd_option_symbol(rtd_sym)
                    if not parsed:
                        continue
                    atm_contracts.append((rtd_sym, abs(parsed.strike - spot)))
                # Pick closest call and closest put.
                call_atm = min(
                    [s for s, d in atm_contracts if parse_rtd_option_symbol(s).option_type == "C"],
                    key=lambda s: abs(parse_rtd_option_symbol(s).strike - spot),
                    default=None,
                )
                put_atm = min(
                    [s for s, d in atm_contracts if parse_rtd_option_symbol(s).option_type == "P"],
                    key=lambda s: abs(parse_rtd_option_symbol(s).strike - spot),
                    default=None,
                )
                if call_atm:
                    live_subscriptions.append((QuoteType.LAST, call_atm))
                if put_atm:
                    live_subscriptions.append((QuoteType.LAST, put_atm))

            # Back expiries: subscribe IV to the top OI calls + puts per expiry,
            # plus force-include the ATM band so we get straddle/EM data.
            for exp in sorted_expiries:
                if exp == front_expiry:
                    continue
                pairs = by_expiry[exp]
                calls = sorted(
                    [p for p in pairs if parse_rtd_option_symbol(p[0]).option_type == "C"],
                    key=lambda x: x[1],
                    reverse=True,
                )[:back_iv_top_n]
                puts = sorted(
                    [p for p in pairs if parse_rtd_option_symbol(p[0]).option_type == "P"],
                    key=lambda x: x[1],
                    reverse=True,
                )[:back_iv_top_n]
                iv_set = {s for s, _ in calls + puts}
                # Force-include ATM band for back expiries (same logic as front).
                for rtd_sym, _ in pairs:
                    parsed = parse_rtd_option_symbol(rtd_sym)
                    if parsed and abs(parsed.strike - spot) <= 2 * spacing:
                        iv_set.add(rtd_sym)
                for rtd_sym in iv_set:
                    live_subscriptions.append((QuoteType.IMPL_VOL, rtd_sym))

            # Base futures LAST.
            exchange = self._exchange_for_symbol(sym)
            live_subscriptions.append((QuoteType.LAST, f"{sym}:{exchange}"))

        if not live_subscriptions:
            log.warning("No live subscriptions generated — falling back to Schwab-only")
            self._enabled = False
            self._adapter = None
            return

        # Flatten cached OI across symbols; IV is live so static IV is empty.
        static_oi: dict[str, int] = {}
        for sym in self._symbols:
            static_oi.update(open_interest.get(sym, {}))

        try:
            self._adapter.start(
                symbols=self._symbols,
                expiry=self._expiry,
                current_price=futures_prices,
                expiries=expiries,
                option_symbols=all_option_symbols,
                live_subscriptions=live_subscriptions,
                static_oi=static_oi,
                static_iv={},
            )
            log.info(
                "HybridCoordinator started with %d live subscriptions across %d option symbols",
                len(live_subscriptions), len(all_option_symbols),
            )
        except Exception as e:
            log.error("RTD start failed — falling back to Schwab-only: %s", e)
            self._enabled = False
            self._adapter = None

    def _strike_spacing_for(self, symbol: str) -> float:
        """Return the base strike spacing for a symbol."""
        sym_configs = TOS_RTD_SYMBOL_CONFIG or {}
        sc = sym_configs.get(symbol, {})
        tiers = sc.get("strike_tiers")
        if tiers:
            return float(tiers[0][1])
        return float(sc.get("strike_spacing", TOS_RTD_STRIKE_SPACING))

    # ------------------------------------------------------------------
    # Schwab ETF OI pre-filter
    # ------------------------------------------------------------------

    def _get_schwab_oi_hints(
        self,
        expiries: list[date],
        futures_prices: dict[str, float],
        top_n_per_symbol: int = 40,
    ) -> dict[str, list[float]]:
        """Fetch futures options chains directly and extract top-OI strikes.

        Uses Schwab's futures options chain API (not ETF proxy) so the strikes
        are already in the correct futures strike grid — no translation ratio
        needed. This avoids the QQQ→NQ translation errors that caused NQ to
        have only 19 contracts vs ES's 154.

        Returns:
            hints: {futures_symbol: [candidate_strike, ...]}
        """
        from ..options_fetcher import fetch_futures_option_chain_data
        from ..futures_translator import get_min_tick, round_to_tick

        hints: dict[str, list[float]] = {}

        for sym, fut_price in futures_prices.items():
            if sym not in ("/ES", "/NQ"):
                continue

            min_tick = get_min_tick(sym)
            try:
                chain = fetch_futures_option_chain_data(sym, [0, 7, 14, 30, 45])
            except Exception as exc:
                log.debug("Schwab futures chain fetch failed for %s: %s", sym, exc)
                continue

            if not chain or not chain.contracts:
                log.debug("No contracts in Schwab futures chain for %s", sym)
                continue

            # Top-OI strikes from the direct futures options chain.
            sorted_contracts = sorted(
                chain.contracts,
                key=lambda c: c.open_interest or 0,
                reverse=True,
            )
            top_contracts = sorted_contracts[:top_n_per_symbol]
            candidate_strikes: set[float] = set()
            for c in top_contracts:
                if c.open_interest and c.open_interest > 0:
                    candidate_strikes.add(c.strike)

            # Round hints to the RTD strike grid so they actually match.
            # Schwab NQ strikes are at 100-pt intervals (28000, 28200, 28500...)
            # but RTD NQ uses 5-pt intervals (28460, 28465, 28470...).
            # Without rounding, the 7.5-pt tolerance in _build_candidate_symbols
            # misses every hint.
            spacing = self._strike_spacing_for(sym)
            if spacing > 0:
                rounded = set()
                for s in candidate_strikes:
                    rounded.add(round(s / spacing) * spacing)
                candidate_strikes = rounded

            hints[sym] = sorted(candidate_strikes)

            log.info(
                "Schwab futures OI hints for %s: %d candidate strikes from direct chain (%d contracts, rounded to %.1f-pt grid)",
                sym, len(candidate_strikes), len(chain.contracts), spacing,
            )

        return hints

    def _build_candidate_symbols(
        self,
        symbols: list[str],
        expiries: list[date],
        futures_prices: dict[str, float],
        hints: dict[str, list[float]],
        hint_tolerance_mult: float = 1.5,
    ) -> list[str]:
        """Build option RTD symbols, keeping only those near Schwab ETF hint strikes."""
        candidates: list[str] = []
        for sym in symbols:
            if sym not in futures_prices:
                continue
            price = futures_prices[sym]
            sc = TOS_RTD_SYMBOL_CONFIG.get(sym, {})
            sr = sc.get("strike_range", TOS_RTD_STRIKE_RANGE)
            ss = sc.get("strike_spacing", TOS_RTD_STRIKE_SPACING)
            tiers = sc.get("strike_tiers")

            sym_hints = set(hints.get(sym, []))
            tolerance = hint_tolerance_mult * self._strike_spacing_for(sym)

            for exp in expiries:
                option_syms = OptionSymbolBuilder.build_symbols(
                    sym, exp, price, sr, ss, strike_tiers=tiers
                )
                if sym_hints:
                    for rtd_sym in option_syms:
                        parsed = parse_rtd_option_symbol(rtd_sym)
                        if parsed and any(abs(parsed.strike - h) <= tolerance for h in sym_hints):
                            candidates.append(rtd_sym)
                else:
                    candidates.extend(option_syms)

        log.info("Candidate RTD symbols after Schwab ETF pre-filter: %d", len(candidates))
        return candidates

    # ------------------------------------------------------------------
    # Completeness-gated OI scan
    # ------------------------------------------------------------------

    def _run_oi_scan(
        self,
        option_symbols: list[str],
        timeout: float = 30.0,
        completeness_pct: float = 0.80,
    ) -> dict[str, int]:
        """Subscribe to OPEN_INT for all symbols and return the OI map.

        This is the once-per-session scan that seeds the RTD market cache.
        Open interest changes slowly, so it is captured once and reused to
        free COM topic budget. Implied volatility is NOT captured here — it is
        subscribed live during streaming because IV changes intraday.
        """
        from .quote_types import QuoteType

        if not option_symbols:
            return {}

        subscriptions = [(QuoteType.OPEN_INT, sym) for sym in option_symbols]
        self._adapter.start_raw(subscriptions=subscriptions)

        target_count = int(len(option_symbols) * completeness_pct)
        start = time.time()

        try:
            while time.time() - start < timeout:
                time.sleep(0.5)
                snapshot = self._adapter.get_snapshot()
                oi_keys = [
                    k for k in snapshot
                    if k.endswith(":OPEN_INT") and snapshot[k] is not None
                ]
                if len(oi_keys) >= target_count:
                    log.info(
                        "OI scan reached %.0f%% completeness (%d/%d) after %.1fs",
                        completeness_pct * 100, len(oi_keys), len(option_symbols),
                        time.time() - start,
                    )
                    break
            else:
                log.warning(
                    "OI scan timed out after %.1fs (target %d/%d)",
                    timeout, target_count, len(option_symbols),
                )
        finally:
            # Collect final values before stopping.
            snapshot = self._adapter.get_snapshot()
            self._adapter.stop()

        oi_map: dict[str, int] = {}
        for sym in option_symbols:
            oi_val = snapshot.get(f"{sym}:OPEN_INT")
            if oi_val is not None and int(oi_val) > 0:
                oi_map[sym] = int(oi_val)

        log.info(
            "OI scan complete: %d/%d contracts with non-zero OI",
            len(oi_map), len(option_symbols),
        )
        return oi_map

    # ------------------------------------------------------------------
    # OI-weighted Top-N filter with ATM force-inclusion
    # ------------------------------------------------------------------

    def _filter_top_oi_contracts(
        self,
        oi_map: dict[str, int],
        futures_price: float,
        symbol: str,
        coverage_pct: float = 0.90,
        atm_band_strikes: int = 5,
    ) -> dict[str, int]:
        """Keep contracts covering ≥coverage_pct of total OI, plus ±atm_band ATM strikes."""
        if not oi_map:
            return {}

        strike_spacing = self._strike_spacing_for(symbol)
        atm_band_width = atm_band_strikes * strike_spacing

        # 1. Force-include ATM band regardless of OI rank.
        atm_symbols = set()
        for sym, _ in oi_map.items():
            parsed = parse_rtd_option_symbol(sym)
            if parsed and abs(parsed.strike - futures_price) <= atm_band_width:
                atm_symbols.add(sym)

        # 2. Sort remaining by OI descending, accumulate until coverage_pct.
        total_oi = sum(oi_map.values())
        sorted_contracts = sorted(oi_map.items(), key=lambda x: x[1], reverse=True)

        cumulative = 0
        selected: dict[str, int] = {}
        for sym, oi in sorted_contracts:
            selected[sym] = oi
            cumulative += oi
            if cumulative >= total_oi * coverage_pct:
                break

        # 3. Merge ATM band (may already be in selected).
        for sym in atm_symbols:
            if sym not in selected:
                selected[sym] = oi_map[sym]

        log.info(
            "Top-N OI filter for %s: %d → %d contracts (%.0f%% OI coverage, +%d ATM forced)",
            symbol, len(oi_map), len(selected),
            (sum(selected.values()) / total_oi * 100) if total_oi else 0,
            len(atm_symbols - set(selected.keys())),
        )
        return selected

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

        # Adaptive wait for option Greeks to arrive.
        # Instead of a hardcoded sleep, check if the adapter already has
        # GAMMA/OPEN_INT data for this symbol.  If data is already fresh,
        # skip the wait entirely.  Otherwise poll with a short timeout.
        import time
        if self.is_rtd_active and self._adapter is not None:
            snapshot = self._adapter.get_snapshot()
            # Check if we already have option data for this symbol
            has_option_data = any(
                f":{symbol}" in key and (":GAMMA" in key or ":OPEN_INT" in key)
                for key in snapshot
            )
            if not has_option_data:
                # No data yet — poll for up to 3 seconds (1s increments)
                for _ in range(3):
                    time.sleep(1)
                    snapshot = self._adapter.get_snapshot()
                    has_option_data = any(
                        f":{symbol}" in key and (":GAMMA" in key or ":OPEN_INT" in key)
                        for key in snapshot
                    )
                    if has_option_data:
                        break
                if not has_option_data:
                    log.debug("No RTD option data for %s after 3s — proceeding with BSM fallback")

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