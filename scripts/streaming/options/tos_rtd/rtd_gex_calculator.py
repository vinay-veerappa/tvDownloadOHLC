"""
RTD GEX Calculator — compute dealer levels directly from TOS RTD futures options.

Instead of pulling SPY/SPX chains from Schwab and translating to futures space,
this module subscribes to /ES and /NQ futures options via RTD, gets native
GAMMA + OPEN_INT + VOLUME + IV from TOS, and feeds them directly into our
existing gex_calculator.calculate_dealer_levels().

This produces "true futures GEX" — levels computed from actual futures options
book, not translated from cash/ETF space.

The result can then be compared against the SPY/SPX→futures translated levels
to validate the translation accuracy.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import date, datetime, time as dtime
from typing import Any, Optional
from zoneinfo import ZoneInfo

from ..gex_calculator import DealerLevels, calculate_dealer_levels
from ..options_fetcher import OptionChainData, OptionContract
from .adapter import TOSRTDAdapter, RTDConfig, ChainSnapshot
from .symbol_builder import OptionSymbolBuilder, parse_rtd_option_symbol, OptionContract as RTDOptionContract

log = logging.getLogger(__name__)

# Quote types we need from RTD for full GEX calculation
RTD_GEX_QUOTE_TYPES = ["GAMMA", "OPEN_INT", "VOLUME", "LAST", "MARK", "IMPL_VOL", "DELTA"]


@dataclass
class FuturesGEXResult:
    """GEX levels computed directly from futures options via RTD."""

    symbol: str                    # "/ES" or "/NQ"
    futures_price: float           # RTD LAST price
    expiry: date
    dealer_levels: DealerLevels     # Full dealer levels from gex_calculator
    contract_count: int            # How many option contracts had data
    source: str = "tos_rtd"        # Data source tag
    timestamp: float = field(default_factory=time.time)

    # Comparison fields (filled by compare_with_translated)
    translated_levels: Optional[DealerLevels] = None
    call_wall_diff: Optional[float] = None      # RTD wall - translated wall
    put_wall_diff: Optional[float] = None
    zero_gamma_diff: Optional[float] = None
    total_gex_diff: Optional[float] = None


def build_chain_from_rtd(
    snapshot: ChainSnapshot,
    ticker: str = "",
) -> OptionChainData:
    """
    Convert an RTD ChainSnapshot into an OptionChainData compatible with
    gex_calculator.calculate_dealer_levels().

    The key insight: RTD gives us native GAMMA, OPEN_INT, VOLUME, IV, DELTA
    directly from the exchange. We don't need to compute Greeks via BSM —
    we just pass them through.

    Args:
        snapshot: ChainSnapshot from TOSRTDAdapter.build_chain_snapshot()
        ticker: Ticker label for the chain (e.g. "/ES" or "ES")

    Returns:
        OptionChainData ready for calculate_dealer_levels()
    """
    contracts: list[OptionContract] = []

    for rtd_sym, greeks in snapshot.greeks.items():
        parsed = parse_rtd_option_symbol(rtd_sym)
        if not parsed:
            continue

        # Extract Greeks from RTD data
        gamma = greeks.get("GAMMA")
        open_int = greeks.get("OPEN_INT") or 0
        volume = greeks.get("VOLUME") or 0
        last = greeks.get("LAST") or 0.0
        # IV and delta may not be subscribed — default to 0
        iv = greeks.get("IMPL_VOL") or 0.0
        delta = greeks.get("DELTA") or 0.0

        # Skip contracts with no OI (they don't contribute to GEX)
        if open_int == 0:
            continue

        contract = OptionContract(
            symbol=rtd_sym,
            strike=parsed.strike,
            contract_type="CALL" if parsed.option_type == "C" else "PUT",
            type="CALL" if parsed.option_type == "C" else "PUT",
            expiry=snapshot.expiry,
            last=float(last) if last else 0.0,
            bid=float(last) if last else 0.0,   # RTD has no bid/ask — use last as proxy
            ask=float(last) if last else 0.0,   # so _expected_move() guardrail passes
            mark=float(last) if last else 0.0,
            volume=int(volume) if volume else 0,
            open_interest=int(open_int) if open_int else 0,
            iv=float(iv) if iv else 0.0,
            delta=float(delta) if delta else 0.0,
            gamma=float(gamma) if gamma else 0.0,
            theta=0.0,  # Not subscribed via RTD by default
            vega=0.0,   # Not subscribed via RTD by default
            rho=0.0,    # Not subscribed via RTD by default
            dte=max(0, (snapshot.expiry - date.today()).days),
        )
        contracts.append(contract)

    chain = OptionChainData(
        ticker=ticker or snapshot.symbol,
        spot=snapshot.futures_price,
        spot_open=snapshot.futures_price,  # RTD doesn't give us open separately
        timestamp=datetime.now(ZoneInfo("America/New_York")),
        contracts=contracts,
        underlying_symbol=snapshot.symbol,
        spot_price=snapshot.futures_price,
    )

    log.info(
        "Built RTD chain for %s: %d contracts (%d calls, %d puts), spot=%.2f",
        snapshot.symbol,
        len(contracts),
        len(chain.calls),
        len(chain.puts),
        snapshot.futures_price,
    )

    return chain


def calculate_futures_gex(
    adapter: TOSRTDAdapter,
    symbol: str,
    min_oi_floor: int = 1,
) -> Optional[FuturesGEXResult]:
    """
    Calculate dealer levels directly from RTD futures options data.

    This is the main entry point — subscribes to RTD, builds a chain,
    and runs the full GEX calculation.

    Args:
        adapter: TOSRTDAdapter instance (must be started)
        symbol: Futures symbol, e.g. "/ES"
        min_oi_floor: Minimum OI threshold for wall detection

    Returns:
        FuturesGEXResult with dealer levels, or None if no data.
    """
    # Build chain snapshot from RTD
    chain_snap = adapter.build_chain_snapshot(symbol)
    if chain_snap is None:
        log.warning("No RTD data for %s — cannot calculate futures GEX", symbol)
        return None

    if not chain_snap.contracts:
        log.warning("No option contracts in RTD snapshot for %s", symbol)
        return None

    # Convert to OptionChainData
    chain = build_chain_from_rtd(chain_snap, ticker=symbol)

    if not chain.calls and not chain.puts:
        log.warning("No calls/puts in RTD chain for %s", symbol)
        return None

    # Run the full GEX calculation
    try:
        dealer_levels = calculate_dealer_levels(
            chain,
            symbol,
            min_oi_floor=min_oi_floor,
            wall_scope="FRONT_WEEK_WEIGHTED",
            wall_dte_range=(0, 14),
        )

        result = FuturesGEXResult(
            symbol=symbol,
            futures_price=chain_snap.futures_price,
            expiry=chain_snap.expiry,
            dealer_levels=dealer_levels,
            contract_count=len(chain.contracts),
        )

        log.info(
            "RTD GEX for %s: total_gex=%.2f, regime=%s, call_wall=%.2f, put_wall=%.2f, zero_gamma=%.2f",
            symbol,
            dealer_levels.total_gex,
            dealer_levels.gex_regime,
            dealer_levels.call_wall or 0,
            dealer_levels.put_wall or 0,
            dealer_levels.zero_gamma or 0,
        )

        return result

    except Exception as e:
        log.error("GEX calculation from RTD data failed for %s: %s", symbol, e, exc_info=True)
        return None


def compare_gex_sources(
    rtd_result: FuturesGEXResult,
    translated_levels: Any,  # TranslatedLevels from futures_translator
) -> FuturesGEXResult:
    """
    Compare RTD-computed futures GEX against SPY/SPX→futures translated levels.

    Args:
        rtd_result: FuturesGEXResult from calculate_futures_gex()
        translated_levels: TranslatedLevels from the Schwab pipeline

    Returns:
        The rtd_result with comparison fields filled in.
    """
    rtd_dl = rtd_result.dealer_levels
    rtd_result.translated_levels = getattr(translated_levels, "dealer_levels", translated_levels)

    # Compare key levels
    rtd_cw = rtd_dl.call_wall or 0
    tr_cw = getattr(translated_levels, "call_wall", 0) or 0
    rtd_result.call_wall_diff = round(rtd_cw - tr_cw, 2) if rtd_cw and tr_cw else None

    rtd_pw = rtd_dl.put_wall or 0
    tr_pw = getattr(translated_levels, "put_wall", 0) or 0
    rtd_result.put_wall_diff = round(rtd_pw - tr_pw, 2) if rtd_pw and tr_pw else None

    rtd_zg = rtd_dl.zero_gamma or 0
    tr_zg = getattr(translated_levels, "zero_gamma", 0) or 0
    rtd_result.zero_gamma_diff = round(rtd_zg - tr_zg, 2) if rtd_zg and tr_zg else None

    rtd_gex = rtd_dl.total_gex
    tr_gex = getattr(translated_levels, "total_gex", 0) or 0
    rtd_result.total_gex_diff = round(rtd_gex - tr_gex, 2) if rtd_gex and tr_gex else None

    log.info(
        "GEX comparison for %s:\n"
        "  Call Wall:  RTD=%.2f  Translated=%.2f  diff=%s\n"
        "  Put Wall:   RTD=%.2f  Translated=%.2f  diff=%s\n"
        "  Zero Gamma: RTD=%.2f  Translated=%.2f  diff=%s\n"
        "  Total GEX:  RTD=%.2f  Translated=%.2f  diff=%s",
        rtd_result.symbol,
        rtd_cw, tr_cw, rtd_result.call_wall_diff,
        rtd_pw, tr_pw, rtd_result.put_wall_diff,
        rtd_zg, tr_zg, rtd_result.zero_gamma_diff,
        rtd_gex, tr_gex, rtd_result.total_gex_diff,
    )

    return rtd_result


def format_comparison_table(rtd_result: FuturesGEXResult) -> str:
    """Format a comparison table for logging/Discord output."""
    rtd_dl = rtd_result.dealer_levels
    tr = rtd_result.translated_levels

    if tr is None:
        return f"No translated levels to compare for {rtd_result.symbol}"

    lines = [
        f"**{rtd_result.symbol} GEX Source Comparison** (RTD vs Schwab-translated)",
        f"",
        f"| Level | RTD (futures options) | Schwab (SPY/SPX->futures) | Difference |",
        f"|---|---|---|---|",
    ]

    def _row(label: str, rtd_val: float | None, tr_val: float | None, diff: float | None) -> str:
        r = f"{rtd_val:,.2f}" if rtd_val else "N/A"
        t = f"{tr_val:,.2f}" if tr_val else "N/A"
        d = f"{diff:+,.2f}" if diff is not None else "N/A"
        return f"| {label} | {r} | {t} | {d} |"

    lines.append(_row("Call Wall", rtd_dl.call_wall, getattr(tr, "call_wall", None), rtd_result.call_wall_diff))
    lines.append(_row("Put Wall", rtd_dl.put_wall, getattr(tr, "put_wall", None), rtd_result.put_wall_diff))
    lines.append(_row("Zero Gamma", rtd_dl.zero_gamma, getattr(tr, "zero_gamma", None), rtd_result.zero_gamma_diff))
    lines.append(_row("Total GEX", rtd_dl.total_gex, getattr(tr, "total_gex", None), rtd_result.total_gex_diff))
    lines.append(f"| Contracts | {rtd_result.contract_count} | (Schwab chain) | - |")
    lines.append(f"| Spot | {rtd_result.futures_price:,.2f} | {getattr(tr, 'futures_price', 'N/A')} | - |")

    return "\n".join(lines)