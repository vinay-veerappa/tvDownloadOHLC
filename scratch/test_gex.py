import asyncio
import os
import dotenv
from prisma import Prisma

dotenv.load_dotenv("web/.env")

async def main():
    db = Prisma()
    await db.connect()
    
    print("GEX Snapshots Count:", await db.gexsnapshot.count())
    print("Macro Snapshots Count:", await db.macrosnapshot.count())
    print("Expected Move Count:", await db.expectedmove.count())
    print("Expected Move History Count:", await db.expectedmovehistory.count())
    print("RTH Expected Move Count:", await db.rthexpectedmove.count())
    print("Historical Volatility Count:", await db.historicalvolatility.count())
    
    print("\nSample GEX Snapshot (non-None IV):")
    sample_gex = await db.gexsnapshot.find_first(
        where={
            "OR": [
                {"put25dIv": {"not": None}},
                {"call25dIv": {"not": None}}
            ]
        }
    )
    print(sample_gex)
    
    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
