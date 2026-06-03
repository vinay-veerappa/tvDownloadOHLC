import asyncio
import os
import sys
from datetime import datetime
import pytz
from dotenv import load_dotenv

# Configure environment path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

dotenv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../web/.env"))
load_dotenv(dotenv_path)

from prisma import Prisma
from scripts.libs_py.strategy_engine.analytics import AnalyticsService

async def main():
    db = Prisma()
    await db.connect()
    
    config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../scripts/libs_py/strategy_engine/config.yaml"))
    analytics = AnalyticsService(db, config_path)
    
    tz_et = pytz.timezone("America/New_York")
    now_et = datetime.now(tz_et)
    
    print(f"Triggering EOD Daily Rollup for {now_et}...")
    await analytics.run_daily_rollup(now_et)
    
    print(f"\nTriggering Weekly Performance Rollup for {now_et}...")
    await analytics.run_weekly_rollup(now_et)
    
    print("\nRollups successfully executed!")
    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
