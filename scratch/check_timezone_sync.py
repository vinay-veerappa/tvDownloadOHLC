import asyncio
import logging
import sys
import os
from datetime import datetime, timedelta, date, timezone
import pytz

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from prisma import Prisma
from dotenv import load_dotenv

# Load env variables
dotenv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../web/.env"))
load_dotenv(dotenv_path)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("check_timezone_sync")

async def test_timezone_queries():
    db = Prisma()
    await db.connect()
    
    try:
        logger.info("=" * 80)
        logger.info("TIMEZONE & DATABASE PERSISTENCE LAYER SYNCHRONIZATION TEST")
        logger.info("=" * 80)
        
        # 1. Establish timezones
        tz_et = pytz.timezone("America/New_York")
        tz_utc = pytz.utc
        
        now_et = datetime.now(tz_et)
        now_utc = now_et.astimezone(tz_utc)
        
        logger.info(f"Local time (EST/EDT): {now_et} (tzinfo: {now_et.tzinfo})")
        logger.info(f"Equivalent UTC time : {now_utc} (tzinfo: {now_utc.tzinfo})")
        
        # 2. Stage a mock signal with Eastern Time
        strategy_name = "TIMEZONE_TEST_PCS"
        logger.info(f"Creating a temporary staged signal record in DB under name '{strategy_name}'...")
        
        # Clear any existing timezone test records
        await db.stagedsignal.delete_many(where={"strategyName": strategy_name})
        
        buffer_seconds = 60
        execute_after_et = now_et + timedelta(seconds=buffer_seconds)
        execute_after_utc = now_utc + timedelta(seconds=buffer_seconds)
        
        staged = await db.stagedsignal.create(
            data={
                "strategyName": strategy_name,
                "strategyCode": "TZ_TEST",
                "variantName": "TEST",
                "ticker": "SPY",
                "stagedAt": now_et,          # Passing ET-aware datetime
                "executeAfter": execute_after_et, # Passing ET-aware datetime
                "status": "PENDING",
                "signalJson": "{}"
            }
        )
        
        logger.info(f"StagedSignal record created. ID: {staged.id}")
        logger.info(f"Returned from DB client (executeAfter): {staged.executeAfter} (tzinfo: {staged.executeAfter.tzinfo})")
        
        # 3. Read it back via direct query and verify timezone is UTC
        retrieved = await db.stagedsignal.find_unique(where={"id": staged.id})
        logger.info("Retrieved record back from DB:")
        logger.info(f"  • stagedAt     : {retrieved.stagedAt} (tzinfo: {retrieved.stagedAt.tzinfo})")
        logger.info(f"  • executeAfter : {retrieved.executeAfter} (tzinfo: {retrieved.executeAfter.tzinfo})")
        
        # Verify that both dates returned are UTC-aware datetime objects
        assert retrieved.stagedAt.tzinfo == timezone.utc, "stagedAt tzinfo is not UTC!"
        assert retrieved.executeAfter.tzinfo == timezone.utc, "executeAfter tzinfo is not UTC!"
        
        # Localize retrieved dates back to ET to make sure they match original values exactly
        staged_at_converted_et = retrieved.stagedAt.astimezone(tz_et)
        execute_after_converted_et = retrieved.executeAfter.astimezone(tz_et)
        logger.info("Localized back to Eastern Time:")
        logger.info(f"  • stagedAt (ET)     : {staged_at_converted_et}")
        logger.info(f"  • executeAfter (ET) : {execute_after_converted_et}")
        
        assert abs((staged_at_converted_et - now_et).total_seconds()) < 1.0, "stagedAt value mismatched!"
        assert abs((execute_after_converted_et - execute_after_et).total_seconds()) < 1.0, "executeAfter value mismatched!"
        logger.info("✅ Timezone roundtrip verification: PASSED! Values stored and read back match perfectly.")
        
        # 4. Test querying with localized Eastern Time filter
        logger.info("Querying database using Eastern Time-aware 'lte' filter...")
        query_time_et = execute_after_et + timedelta(seconds=1)
        pending_et = await db.stagedsignal.find_many(
            where={
                "strategyName": strategy_name,
                "status": "PENDING",
                "executeAfter": {"lte": query_time_et}
            }
        )
        logger.info(f"Query with ET filter '{query_time_et}' returned {len(pending_et)} record(s).")
        assert len(pending_et) == 1, "Failed to find record using ET-aware filter!"
        
        # 5. Test querying with UTC-aware filter
        logger.info("Querying database using UTC-aware 'lte' filter...")
        query_time_utc = execute_after_utc + timedelta(seconds=1)
        pending_utc = await db.stagedsignal.find_many(
            where={
                "strategyName": strategy_name,
                "status": "PENDING",
                "executeAfter": {"lte": query_time_utc}
            }
        )
        logger.info(f"Query with UTC filter '{query_time_utc}' returned {len(pending_utc)} record(s).")
        assert len(pending_utc) == 1, "Failed to find record using UTC-aware filter!"
        assert pending_et[0].id == pending_utc[0].id, "Returned records mismatched between ET and UTC filters!"
        
        logger.info("✅ Database query timezone synchronization: PASSED! Prisma + SQLite natively and correctly handles both ET-aware and UTC-aware queries.")
        
        # 6. Clean up
        await db.stagedsignal.delete_many(where={"strategyName": strategy_name})
        logger.info("Timezone sync verification temporary records cleaned up successfully.")
        
        logger.info("=" * 80)
        logger.info("ALL TIMING AND TIMEZONE PERSISTENCE INTEGRITY CHECKS PASSED!")
        logger.info("=" * 80)
        
    finally:
        await db.disconnect()

if __name__ == "__main__":
    asyncio.run(test_timezone_queries())
