import asyncio
import os
from pathlib import Path
from datetime import datetime, timezone

os.environ['DATABASE_URL'] = f"file:{Path('web/prisma/dev.db').resolve().as_posix()}"
from prisma import Prisma

async def main():
    db = Prisma()
    await db.connect()
    try:
        yesterday_start = datetime(2026, 7, 10, tzinfo=timezone.utc)
        yesterday_end = datetime(2026, 7, 11, tzinfo=timezone.utc)
        rows = await db.gexsnapshot.find_many(
            where={'tradingDate': {'gte': yesterday_start, 'lt': yesterday_end}},
            order={'timestamp': 'desc'},
            take=10,
        )
        for r in rows:
            print("{} {} spot={:8.2f} totalGex={:14.0f} callWall={:8.2f} putWall={:8.2f} zg={:8.2f} future={:4} mode={}".format(
                r.timestamp.strftime("%H:%M:%S"), r.ticker, r.spotPrice, r.totalGex,
                r.callWall or 0, r.putWall or 0, r.zeroGamma or 0,
                r.futuresSymbol or '-', r.futuresTranslationMode or '-'))
    finally:
        await db.disconnect()

asyncio.run(main())
