import asyncio
from datetime import datetime, timezone
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from scripts.streaming.providers.schwab_dev_provider import SchwabDevProvider
from config.symbols import ALL_SYMBOLS

async def test_schwab_daily():
    provider = SchwabDevProvider()
    await provider.initialize()
    
    start_dt = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end_dt = datetime.now(timezone.utc)
    
    print(f"Testing Schwab API for daily data from {start_dt.date()} to {end_dt.date()}...")
    
    df = await provider.get_historical_data("/NQ", "1D", start_dt, end_dt)
    
    if df.empty:
        print("Failed: No data returned.")
    else:
        print(f"Success! Returned {len(df)} daily candles.")
        print(f"First date: {df.index.min()}")
        print(f"Last date:  {df.index.max()}")
        print(df.head(2))

if __name__ == "__main__":
    asyncio.run(test_schwab_daily())
