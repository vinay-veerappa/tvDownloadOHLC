import asyncio
import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from prisma import Prisma
from dotenv import load_dotenv

# Load env variables
dotenv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../web/.env"))
load_dotenv(dotenv_path)

from scripts.libs_py.strategy_engine.services.broker_service import BrokerService

async def main():
    broker = BrokerService()
    # Let's see what keys are returned by get_option_quote for a dummy symbol or SPY symbol
    try:
        quote = await broker.get_option_quote("SPY   260520P00729000")
        print("Quote keys:", quote.keys())
        print("Quote values:", quote)
    except Exception as e:
        print("Failed to get quote:", e)

if __name__ == "__main__":
    asyncio.run(main())
