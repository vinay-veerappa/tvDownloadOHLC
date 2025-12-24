
import asyncio
from prisma import Prisma
import os

# Load Environment
try:
    with open('web/.env', 'r') as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                k, v = line.strip().split('=', 1)
                os.environ[k] = v.strip('"').strip("'")
except Exception as e:
    print(f"Warning: Could not load .env: {e}")

async def main():
    db = Prisma()
    await db.connect()
    
    print("Fetching Watchlist Items...")
    items = await db.watchlistitem.find_many()
    
    tickers = sorted(list(set(item.symbol for item in items)))
    
    print(f"\nFound {len(tickers)} unique tickers in Watchlists:")
    print(", ".join(f"'{t}'" for t in tickers))
    
    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
