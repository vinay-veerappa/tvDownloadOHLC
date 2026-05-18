import asyncio
import logging
import os
import signal
import sys
from datetime import datetime
import pytz
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("strategy_engine.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("strategy_engine.runner")

# 1. Load env variables before starting Prisma
dotenv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../web/.env"))
load_dotenv(dotenv_path)

from prisma import Prisma
from scripts.libs_py.strategy_engine.engine import Engine
from scripts.libs_py.strategy_engine.analytics import AnalyticsService

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.yaml")

# Timezones
TZ_ET = pytz.timezone("America/New_York")

class Runner:
    """
    Continuous Scheduler for the Options Strategy Engine.
    Ticks every 60 seconds between 9:30 AM and 4:00 PM Eastern Time.
    Triggers EOD and Weekly analytics.
    """
    def __init__(self):
        self.db = Prisma()
        self.engine = None
        self.analytics = None
        self.scheduler = AsyncIOScheduler(timezone=TZ_ET)
        self._running = True

    async def start(self):
        """Starts the scheduler and runs the main loop."""
        logger.info("Starting Strategy Engine Scheduler...")
        await self.db.connect()

        # Initialize the Core Coordinator Engine
        self.engine = Engine(self.db, CONFIG_PATH)
        await self.engine.initialize()

        # Initialize the Analytics Service
        self.analytics = AnalyticsService(self.db, CONFIG_PATH)

        # Schedule the Main Intraday Tick Loop (runs every 60 seconds)
        self.scheduler.add_job(
            self.tick_job,
            trigger="interval",
            seconds=60,
            id="main_tick",
            name="Intraday Scan & Manage Loop",
            max_instances=1
        )

        # Schedule the Daily EOD Analytics (runs at 4:05 PM EST, Mon-Fri)
        self.scheduler.add_job(
            self.daily_analytics_job,
            trigger="cron",
            day_of_week="mon-fri",
            hour=16,
            minute=5,
            id="daily_analytics",
            name="EOD Analytics Rollup",
            max_instances=1
        )

        # Register signal handlers for clean shutdown
        try:
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, lambda: asyncio.create_task(self.stop()))
        except (NotImplementedError, RuntimeError):
            # Fallback for Windows Proactor event loops or environments without signal support
            pass

        # Start the scheduler
        self.scheduler.start()
        logger.info("Scheduler started successfully. Jobs scheduled.")

        # Keep running
        while self._running:
            await asyncio.sleep(1)

    async def stop(self):
        """Gracefully stops the scheduler and database connection."""
        logger.info("Stopping Strategy Engine Scheduler...")
        self._running = False
        self.scheduler.shutdown()
        if self.db.is_connected():
            await self.db.disconnect()
        logger.info("Strategy Engine Scheduler stopped.")

    async def tick_job(self):
        """Intraday tick job executed every 60 seconds."""
        now_et = datetime.now(TZ_ET)
        
        # Check active market hours: 9:30 AM to 4:00 PM EST, Monday to Friday
        if now_et.weekday() >= 5: # Saturday = 5, Sunday = 6
            logger.debug("Weekend - skipping tick.")
            return

        market_open = now_et.replace(hour=9, minute=30, second=0, microsecond=0)
        market_close = now_et.replace(hour=16, minute=0, second=0, microsecond=0)

        if not (market_open <= now_et <= market_close):
            logger.debug("Outside active market hours - skipping tick.")
            return

        logger.info(f"Tick triggered: {now_et.strftime('%Y-%m-%d %H:%M:%S %Z')}")

        # Execute Management Tick first to handle exits before new entries
        await self.engine.run_manage_tick(now_et)

        # Execute Entry Scanning Tick
        await self.engine.run_scan_tick(now_et)

    async def daily_analytics_job(self):
        """EOD Analytics job executed at 4:05 PM EST on weekdays."""
        now_et = datetime.now(TZ_ET)
        logger.info(f"EOD Analytics job triggered at {now_et}")

        # Run EOD Daily rollup
        await self.analytics.run_daily_rollup(now_et)

        # If it is Friday, also run the Weekly rollup
        if now_et.weekday() == 4: # Friday = 4
            logger.info("Friday detected. Running weekly rollup and rundown report.")
            await self.analytics.run_weekly_rollup(now_et)


if __name__ == "__main__":
    runner = Runner()
    try:
        asyncio.run(runner.start())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Received interrupt, shutting down.")
