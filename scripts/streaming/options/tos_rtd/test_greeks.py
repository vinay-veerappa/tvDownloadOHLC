"""Quick test: RTD option Greeks streaming from TOS."""
import logging
import time
from datetime import date, timedelta

from scripts.streaming.options.tos_rtd.adapter import TOSRTDAdapter, RTDConfig
from scripts.streaming.options.tos_rtd.symbol_builder import OptionSymbolBuilder

def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(name)s %(message)s", datefmt="%H:%M:%S")

    expiry = date.today() + timedelta(days=(4 - date.today().weekday()) % 7 or 7)
    print(f"Expiry: {expiry}")

    config = RTDConfig(strike_range=5, strike_spacing=1.0)
    adapter = TOSRTDAdapter(config)

    # Phase 1: Get /ES price
    adapter.start(symbols=["/ES"], expiry=expiry)
    time.sleep(3)
    price = adapter.get_futures_price("/ES")
    print(f"/ES price: {price}")

    if price:
        syms = OptionSymbolBuilder.build_symbols("/ES", expiry, price, 5, 1.0)
        print(f"Built {len(syms)} option symbols")
        print(f"First 6: {syms[:6]}")

        adapter.stop()
        time.sleep(1)

        # Phase 2: Restart with option symbols
        adapter.start(symbols=["/ES"], expiry=expiry, current_price={"/ES": price})
        time.sleep(5)

        snapshot = adapter.get_snapshot()
        print(f"\nSnapshot: {len(snapshot)} keys")

        print("\n--- Option Greeks ---")
        for sym in syms[:10]:
            greeks = adapter.get_option_greeks(sym)
            if any(v is not None for v in greeks.values()):
                print(f"  {sym}: GAMMA={greeks['GAMMA']}, OI={greeks['OPEN_INT']}, VOL={greeks['VOLUME']}")

        print(f"\n--- All keys ({len(snapshot)}) ---")
        for k in sorted(snapshot.keys())[:30]:
            print(f"  {k} = {snapshot[k]}")

    adapter.stop()
    print("\nDone")

if __name__ == "__main__":
    main()