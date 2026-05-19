import asyncio
import logging
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[1]
sys.path.append(str(project_root))

from scripts.streaming.options.options_fetcher import fetch_option_chain_data

logging.basicConfig(level=logging.INFO)

async def test_chain():
    for sym in ["SPX", "VIX"]:
        try:
            print(f"\n--- Testing fetch_option_chain_data for {sym} ---")
            # dte_targets = [30]
            chain = fetch_option_chain_data(None, sym, [30])
            print(f"Success for {sym}!")
            print(f"Spot: {chain.spot}, Spot Open: {chain.spot_open}")
            print(f"Contracts count: {len(chain.contracts)}")
            if chain.contracts:
                print(f"First contract: {chain.contracts[0].symbol} strike {chain.contracts[0].strike}")
        except Exception as e:
            print(f"Error fetching chain for {sym}: {e}")

if __name__ == "__main__":
    asyncio.run(test_chain())
