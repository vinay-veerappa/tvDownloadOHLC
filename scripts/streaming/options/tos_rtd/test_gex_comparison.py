"""
Live RTD GEX comparison test — computes futures GEX from RTD and compares
against Schwab-translated levels.

Prerequisites:
  - Windows OS + TOS desktop running
  - Schwab API credentials configured (for translated levels)

Usage::

    python -m scripts.streaming.options.tos_rtd.test_gex_comparison --symbol /ES
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import date, timedelta

from .adapter import TOSRTDAdapter, RTDConfig
from .rtd_gex_calculator import calculate_futures_gex, format_comparison_table
from .symbol_builder import OptionSymbolBuilder

log = logging.getLogger(__name__)


def _nearest_friday(d: date) -> date:
    days_ahead = 4 - d.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return d + timedelta(days=days_ahead)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s %(message)s",
        datefmt="%H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    parser = argparse.ArgumentParser(description="RTD GEX comparison test")
    parser.add_argument("--symbol", default="/ES", help="Futures symbol (default: /ES)")
    parser.add_argument("--strike-range", type=int, default=20, help="± strikes from ATM")
    parser.add_argument("--strike-spacing", type=float, default=1.0, help="Strike spacing")
    parser.add_argument("--wait", type=int, default=5, help="Seconds to wait for RTD data")
    args = parser.parse_args()

    symbol = args.symbol
    expiry = _nearest_friday(date.today())
    print(f"\n=== RTD GEX Comparison Test ===")
    print(f"Symbol: {symbol}  Expiry: {expiry}")
    print(f"Strike range: ±{args.strike_range}  Spacing: {args.strike_spacing}")

    # Phase 1: Get futures price from RTD
    config = RTDConfig(strike_range=args.strike_range, strike_spacing=args.strike_spacing)
    adapter = TOSRTDAdapter(config)

    try:
        adapter.start(symbols=[symbol], expiry=expiry)
        time.sleep(3)
        price = adapter.get_futures_price(symbol)

        if not price:
            print("No RTD price data — is TOS desktop running?")
            return

        print(f"\n{symbol} RTD price: {price}")

        # Phase 2: Restart with option symbols
        adapter.stop()
        time.sleep(1)
        adapter.start(symbols=[symbol], expiry=expiry, current_price={symbol: price})
        print(f"Waiting {args.wait}s for option Greeks to stream...")
        time.sleep(args.wait)

        # Phase 3: Calculate GEX from RTD data
        print(f"\n--- Calculating GEX from RTD futures options ---")
        result = calculate_futures_gex(adapter, symbol)

        if result is None:
            print("No GEX result — check RTD data above")
            return

        dl = result.dealer_levels
        print(f"\nRTD GEX Results for {symbol}:")
        print(f"  Total GEX:      {dl.total_gex:,.2f}")
        print(f"  Regime:         {dl.gex_regime}")
        print(f"  Call Wall:      {dl.call_wall:,.2f}" if dl.call_wall else "  Call Wall:      N/A")
        print(f"  Put Wall:       {dl.put_wall:,.2f}" if dl.put_wall else "  Put Wall:       N/A")
        print(f"  Zero Gamma:     {dl.zero_gamma:,.2f}" if dl.zero_gamma else "  Zero Gamma:     N/A")
        print(f"  Zero Gamma DA:  {dl.zero_gamma_delta_adj:,.2f}" if dl.zero_gamma_delta_adj else "  Zero Gamma DA:  N/A")
        print(f"  Gamma Magnet:   {dl.gamma_magnet:,.2f}" if dl.gamma_magnet else "  Gamma Magnet:   N/A")
        print(f"  Contracts:      {result.contract_count}")
        print(f"  Spot:           {result.futures_price:,.2f}")

        # Show raw RTD snapshot for debugging
        snapshot = adapter.get_snapshot()
        option_keys = [k for k in snapshot if k.startswith(".")]
        gamma_keys = [k for k in snapshot if k.endswith(":GAMMA") and snapshot[k] is not None and snapshot[k] != 0]
        oi_keys = [k for k in snapshot if k.endswith(":OPEN_INT") and snapshot[k] is not None and snapshot[k] != 0]
        print(f"\n  RTD snapshot: {len(snapshot)} total keys, {len(option_keys)} option keys")
        print(f"  Non-zero gamma: {len(gamma_keys)}, Non-zero OI: {len(oi_keys)}")

        # Show sample Greeks
        if gamma_keys:
            print(f"\n  Sample Greeks (first 5 with non-zero gamma):")
            shown = 0
            for key in sorted(gamma_keys)[:5]:
                sym_part = key.replace(":GAMMA", "")
                g = snapshot.get(key)
                oi = snapshot.get(f"{sym_part}:OPEN_INT")
                vol = snapshot.get(f"{sym_part}:VOLUME")
                print(f"    {sym_part}: gamma={g:.6f} OI={oi} VOL={vol}")
                shown += 1

        # Phase 4: Try to get Schwab translated levels for comparison
        print(f"\n--- Attempting Schwab comparison ---")
        try:
            from ..config import ACTIVE_TICKERS, INDEX_TO_FUTURES
            from ..options_fetcher import create_client, fetch_option_chain_data, fetch_futures_quote
            from ..config import SECRETS_PATH, TOKEN_PATH
            from ..gex_calculator import calculate_dealer_levels
            from ..futures_translator import translate_to_futures

            # Map futures symbol to ETF proxy for reliable Schwab Greeks
            cash_ticker = None
            if symbol == "/ES":
                cash_ticker = "SPY"
            elif symbol == "/NQ":
                cash_ticker = "QQQ"
            else:
                for ct, fs in INDEX_TO_FUTURES.items():
                    if fs == symbol:
                        cash_ticker = ct
                        break

            if not cash_ticker:
                print(f"No cash ticker mapping for {symbol} — skipping comparison")
                return

            print(f"Fetching Schwab chain for {cash_ticker} (proxy for {symbol})...")
            client = create_client(SECRETS_PATH, TOKEN_PATH)
            # Use front-week targets (e.g. 7 DTE)
            schwab_chain = fetch_option_chain_data(client, cash_ticker, [7])

            # Filter to near-term
            from datetime import datetime
            from zoneinfo import ZoneInfo
            today = datetime.now(ZoneInfo("America/New_York")).date()
            near_calls = [c for c in schwab_chain.calls if (c.expiry - today).days <= 14]
            near_puts = [c for c in schwab_chain.puts if (c.expiry - today).days <= 14]
            from dataclasses import replace
            intraday_chain = replace(schwab_chain, contracts=near_calls + near_puts)

            print(f"Schwab chain: {len(near_calls)} calls, {len(near_puts)} puts")

            schwab_levels = calculate_dealer_levels(
                intraday_chain, cash_ticker,
                min_oi_floor=50,
                wall_scope="FRONT_WEEK_WEIGHTED",
                wall_dte_range=(0, 14),
            )

            fut = fetch_futures_quote(symbol)
            if fut and fut.price:
                translated = translate_to_futures(schwab_levels, fut)
                print(f"\nSchwab translated levels for {symbol}:")
                print(f"  Call Wall:     {translated.call_wall:,.2f}" if translated.call_wall else "  Call Wall:     N/A")
                print(f"  Put Wall:      {translated.put_wall:,.2f}" if translated.put_wall else "  Put Wall:      N/A")
                print(f"  Zero Gamma:    {translated.zero_gamma:,.2f}" if translated.zero_gamma else "  Zero Gamma:    N/A")
                print(f"  Zero Gamma DA: {translated.zero_gamma_delta_adj:,.2f}" if translated.zero_gamma_delta_adj else "  Zero Gamma DA: N/A")
                print(f"  Total GEX:     {translated.total_gex:,.2f}")

                # Compare
                from .rtd_gex_calculator import compare_gex_sources
                result = compare_gex_sources(result, translated)

                # Add Zero Gamma DA comparison
                rtd_da = dl.zero_gamma_delta_adj
                trans_da = translated.zero_gamma_delta_adj
                rtd_da_str = f"{rtd_da:,.2f}" if rtd_da is not None else "N/A"
                trans_da_str = f"{trans_da:,.2f}" if trans_da is not None else "N/A"
                diff_da_str = f"{rtd_da - trans_da:,.2f}" if (rtd_da is not None and trans_da is not None) else "N/A"
                print(f"  Zero Gamma DA: RTD={rtd_da_str}  Translated={trans_da_str}  diff={diff_da_str}")
                print(f"\n{format_comparison_table(result)}")
            else:
                print(f"No Schwab futures quote for {symbol}")

        except Exception as e:
            print(f"Schwab comparison failed: {e}")
            log.debug("Schwab comparison error", exc_info=True)

    except KeyboardInterrupt:
        print("\nInterrupted")
    finally:
        adapter.stop()
        print("\nDone.")


if __name__ == "__main__":
    main()