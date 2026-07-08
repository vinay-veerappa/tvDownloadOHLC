"""
Live RTD connection test for TOS desktop.

Prerequisites:
  - Windows OS
  - ThinkorSwim desktop running and logged in
  - comtypes installed: pip install comtypes

Usage::

    python -m scripts.streaming.options.tos_rtd.live_test

    # Or with specific symbols:
    python -m scripts.streaming.options.tos_rtd.live_test --symbol /ES --symbol /NQ
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import date, timedelta
from queue import Empty

from .adapter import TOSRTDAdapter, RTDConfig
from .symbol_builder import OptionSymbolBuilder, parse_rtd_option_symbol


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def _nearest_friday(d: date) -> date:
    """Get the nearest Friday (today if Friday, else next Friday)."""
    days_ahead = 4 - d.weekday()  # 4 = Friday
    if days_ahead <= 0:
        days_ahead += 7
    return d + timedelta(days=days_ahead)


def test_symbol_builder() -> None:
    """Test the symbol builder with known dates."""
    print("\n=== Symbol Builder Tests ===")

    # /ES quarterly (March 2026 3rd Friday = March 20)
    expiry = date(2026, 3, 20)
    syms = OptionSymbolBuilder.build_symbols("/ES", expiry, 5500.0, 10, 1.0)
    print(f"/ES quarterly {expiry}: {len(syms)} symbols")
    print(f"  First 4: {syms[:4]}")

    # /NQ weekly Friday
    expiry = date(2026, 7, 17)
    syms = OptionSymbolBuilder.build_symbols("/NQ", expiry, 21000.0, 10, 1.0)
    print(f"/NQ weekly Fri {expiry}: {len(syms)} symbols")
    print(f"  First 4: {syms[:4]}")

    # /CL standard
    expiry = date(2026, 8, 20)
    syms = OptionSymbolBuilder.build_symbols("/CL", expiry, 75.0, 5, 0.5)
    print(f"/CL {expiry}: {len(syms)} symbols")
    print(f"  First 4: {syms[:4]}")

    # Test reverse parser
    print("\n=== Parser Tests ===")
    test_cases = [
        "./NQH25C21000:XCME",
        "./EWH25P5950:XCME",
        "./CL1G25C7500:XNYM",
        "./GC1G25C2700:XCEC",
    ]
    for sym in test_cases:
        parsed = parse_rtd_option_symbol(sym)
        if parsed:
            print(f"  {sym} → product={parsed.product_code}, type={parsed.option_type}, "
                  f"strike={parsed.strike}, exchange={parsed.exchange}, base={parsed.base_symbol}")
        else:
            print(f"  {sym} → PARSE FAILED")


def test_live_rtd(symbols: list[str], duration: int) -> None:
    """Test live RTD connection with TOS desktop."""
    print(f"\n=== Live RTD Test ({duration}s) ===")
    print(f"Symbols: {symbols}")
    print("Make sure ThinkorSwim desktop is running and logged in.\n")

    expiry = _nearest_friday(date.today())
    print(f"Using expiry: {expiry}")

    config = RTDConfig(strike_range=10, strike_spacing=1.0)
    adapter = TOSRTDAdapter(config)

    try:
        # Phase 1: Subscribe to just the futures LAST to get current price
        print("\n--- Phase 1: Subscribing to futures LAST price ---")
        adapter.start(symbols=symbols, expiry=expiry)

        # Wait for first data
        print("Waiting for first data...")
        for i in range(10):
            time.sleep(1)
            snapshot = adapter.get_snapshot()
            if snapshot:
                print(f"  Got data after {i+1}s: {len(snapshot)} keys")
                break
        else:
            print("  No data received after 10s — check TOS is running")
            return

        # Print futures prices
        print("\n--- Futures Prices ---")
        for sym in symbols:
            price = adapter.get_futures_price(sym)
            if price is not None:
                print(f"  {sym}: {price}")
            else:
                print(f"  {sym}: no data yet")

        # Print raw snapshot keys
        print(f"\n--- Raw Snapshot ({len(snapshot)} keys) ---")
        for key, val in sorted(snapshot.items())[:20]:
            print(f"  {key} = {val}")
        if len(snapshot) > 20:
            print(f"  ... and {len(snapshot) - 20} more")

        # Continue streaming for the remaining duration
        remaining = duration - 10
        if remaining > 0:
            print(f"\n--- Streaming for {remaining}s more ---")
            for i in range(remaining):
                time.sleep(1)
                snapshot = adapter.get_snapshot()
                prices = []
                for sym in symbols:
                    p = adapter.get_futures_price(sym)
                    if p is not None:
                        prices.append(f"{sym}={p}")
                if prices:
                    print(f"  [{i+1}s] {' | '.join(prices)} | {len(snapshot)} keys")

        # Final status
        print("\n--- Final Status ---")
        status = adapter.get_status()
        for k, v in status.items():
            print(f"  {k}: {v}")

    except KeyboardInterrupt:
        print("\nInterrupted by user")
    finally:
        print("\nStopping adapter...")
        adapter.stop()
        print("Done.")


def main() -> None:
    _setup_logging()

    parser = argparse.ArgumentParser(description="TOS RTD live test")
    parser.add_argument(
        "--symbol", action="append", default=None,
        help="Futures symbol to test (e.g. /ES). Can repeat for multiple.",
    )
    parser.add_argument(
        "--duration", type=int, default=15,
        help="Test duration in seconds (default: 15)",
    )
    parser.add_argument(
        "--symbols-only", action="store_true",
        help="Only test the symbol builder, no live RTD connection",
    )
    args = parser.parse_args()

    # Always test symbol builder first
    test_symbol_builder()

    if args.symbols_only:
        return

    symbols = args.symbol or ["/ES", "/NQ"]
    test_live_rtd(symbols, args.duration)


if __name__ == "__main__":
    main()