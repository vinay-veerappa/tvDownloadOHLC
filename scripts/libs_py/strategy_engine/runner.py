"""
Strategy Engine Runner — Three-tier scheduler
============================================
Cadences per spec §1.5:
  Tier 1 — 60s   : index/ETF strategies (SPY, SPX, QQQ, IWM)
  Tier 2 — 5 min : stock strategies (NVDA, TSLA, AAPL, GOOGL, MSFT, AMZN)
  Tier 3 — daily : daily-only strategies (Wheel CSP scan, Earnings scan) at 10:00 ET

Maintenance jobs per spec §11.6:
  Daily 03:00 ET  : prune QuoteSnapshot >90d, SignalNearMiss >30d (M4)
  Sunday 17:00 ET : weekly analytics rollup (M5 — moved from Friday)
  Sunday 18:00 ET : earnings calendar refresh for all tickers (M3)
  Mon-Fri 16:30 ET: EOD daily analytics rollup
"""

import asyncio
import logging
import os
import signal
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

from datetime import datetime, timedelta, timezone
from typing import Set

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
from prisma import Prisma

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("strategy_engine.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("strategy_engine.runner")

# Load env variables before Prisma import
dotenv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../web/.env"))
load_dotenv(dotenv_path)

from scripts.libs_py.strategy_engine.engine import Engine
from scripts.libs_py.strategy_engine.analytics import AnalyticsService

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.yaml")
TZ_ET = pytz.timezone("America/New_York")

# Ticker classification for cadence routing
INDEX_TICKERS: Set[str] = {"SPY", "SPX", "QQQ", "IWM"}
STOCK_TICKERS: Set[str] = {"NVDA", "TSLA", "AAPL", "GOOGL", "MSFT", "AMZN", "RIVN"}

# Daily-only strategy codes that should only run once per day at 10:00 ET
DAILY_STRATEGY_CODES: Set[str] = {"WHEEL", "EARNINGS_STRANGLE", "INCOME_CC","LONG_DTE_CREDIT"}


class Runner:
    """
    Continuous Scheduler for the Options Strategy Engine.
    Implements three-tier cadence + maintenance jobs per spec §1.5, §11.6.
    """

    def __init__(self):
        self.db = Prisma()
        self.engine: Engine = None
        self.analytics: AnalyticsService = None
        self.scheduler = AsyncIOScheduler(timezone=TZ_ET)
        self._running = True

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self):
        """Starts the scheduler and runs the main loop."""
        logger.info("Starting Strategy Engine Scheduler...")
        await self.db.connect()

        self.engine = Engine(self.db, CONFIG_PATH)
        await self.engine.initialize()

        self.analytics = AnalyticsService(self.db, CONFIG_PATH)

        # Check and seed earnings calendar if empty (M8)
        try:
            count = await self.db.earningscalendar.count()
            if count == 0:
                logger.info("Earnings calendar is empty on startup. Triggering initial fetch...")
                earnings_svc = self.engine.services.get("earnings")
                if earnings_svc:
                    all_tickers = list(INDEX_TICKERS | STOCK_TICKERS)
                    await earnings_svc.fetch_upcoming_all(all_tickers)
                    logger.info("Initial earnings calendar seeding completed.")
                else:
                    logger.warning("EarningsService not available during startup seeding.")
        except Exception as e:
            logger.error(f"Failed to seed earnings on startup: {e}")

        self._register_jobs()
        self.scheduler.start()
        logger.info("Scheduler started. All jobs registered.")

        # Windows-friendly signal handling
        try:
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, lambda: asyncio.create_task(self.stop()))
        except (NotImplementedError, RuntimeError):
            pass

        while self._running:
            await asyncio.sleep(1)

    async def stop(self):
        """Gracefully stops the scheduler and database connection."""
        logger.info("Stopping Strategy Engine Scheduler...")
        self._running = False
        self.scheduler.shutdown(wait=False)
        if self.db.is_connected():
            await self.db.disconnect()
        logger.info("Strategy Engine Scheduler stopped.")

    # ------------------------------------------------------------------
    # Job registration
    # ------------------------------------------------------------------

    def _register_jobs(self):
        # Tier 1 — 60s index tick
        self.scheduler.add_job(
            self.tick_index_job,
            trigger="interval",
            seconds=60,
            id="tick_index",
            name="Tier-1 Index Scan & Manage (60s)",
            max_instances=1,
            coalesce=True,
        )

        # Deferred Staged Execution — 10s tick
        self.scheduler.add_job(
            self.tick_staged_execution_job,
            trigger="interval",
            seconds=10,
            id="tick_staged_execution",
            name="Staged Signal Deferred Execution (10s)",
            max_instances=1,
            coalesce=True,
        )

        # Tier 2 — 5 min stock tick
        self.scheduler.add_job(
            self.tick_stock_job,
            trigger="interval",
            minutes=5,
            id="tick_stock",
            name="Tier-2 Stock Scan & Manage (5min)",
            max_instances=1,
            coalesce=True,
        )

        # Tier 3 — Daily strategies at 10:00 ET Mon-Fri
        self.scheduler.add_job(
            self.tick_daily_job,
            trigger="cron",
            day_of_week="mon-fri",
            hour=10,
            minute=0,
            id="tick_daily",
            name="Tier-3 Daily Strategy Scan (10:00 ET)",
            max_instances=1,
        )

        # EOD analytics — 16:30 ET Mon-Fri (spec §6.2 says 16:30, was 16:05)
        self.scheduler.add_job(
            self.eod_analytics_job,
            trigger="cron",
            day_of_week="mon-fri",
            hour=16,
            minute=30,
            id="eod_analytics",
            name="EOD Daily Analytics Rollup (16:30 ET)",
            max_instances=1,
        )

        # Daily system audit report — 16:35 ET Mon-Fri (after market close and EOD analytics)
        self.scheduler.add_job(
            self.daily_system_audit_job,
            trigger="cron",
            day_of_week="mon-fri",
            hour=16,
            minute=35,
            id="daily_system_audit",
            name="Daily System Audit Report (16:35 ET)",
            max_instances=1,
        )

        # Weekly analytics — Sunday 17:00 ET (M5: moved from Friday)
        self.scheduler.add_job(
            self.weekly_analytics_job,
            trigger="cron",
            day_of_week="sun",
            hour=17,
            minute=0,
            id="weekly_analytics",
            name="Weekly Analytics Rollup (Sunday 17:00 ET)",
            max_instances=1,
        )

        # Earnings calendar refresh — Sunday 18:00 ET (M3)
        self.scheduler.add_job(
            self.earnings_refresh_job,
            trigger="cron",
            day_of_week="sun",
            hour=18,
            minute=0,
            id="earnings_refresh",
            name="Earnings Calendar Refresh (Sunday 18:00 ET)",
            max_instances=1,
        )

        # DB maintenance pruning — daily 03:00 ET (M4)
        self.scheduler.add_job(
            self.maintenance_job,
            trigger="cron",
            hour=3,
            minute=0,
            id="db_maintenance",
            name="DB Maintenance Prune (03:00 ET)",
            max_instances=1,
        )

        logger.info(
            "Jobs registered: tick_index(60s), tick_staged_execution(10s), tick_stock(5m), tick_daily(10:00), "
            "eod_analytics(16:30), daily_system_audit(16:35), weekly_analytics(Sun 17:00), "
            "earnings_refresh(Sun 18:00), db_maintenance(03:00)"
        )

    # ------------------------------------------------------------------
    # Market hours guard
    # ------------------------------------------------------------------

    def _is_market_hours(self) -> tuple[bool, datetime]:
        """Returns (is_open, now_et)."""
        now_et = datetime.now(TZ_ET)
        if now_et.weekday() >= 5:
            return False, now_et
        market_open = now_et.replace(hour=9, minute=30, second=0, microsecond=0)
        market_close = now_et.replace(hour=16, minute=0, second=0, microsecond=0)
        return market_open <= now_et <= market_close, now_et

    # ------------------------------------------------------------------
    # Tick jobs
    # ------------------------------------------------------------------

    async def tick_index_job(self):
        """Tier-1: manage + scan for index strategies every 60 seconds."""
        is_open, now_et = self._is_market_hours()
        if not is_open:
            logger.debug("tick_index: outside market hours, skipping.")
            return

        logger.info(f"tick_index @ {now_et.strftime('%H:%M:%S %Z')}")
        await self.engine.run_manage_tick(now_et, cadence="index")
        await self.engine.run_scan_tick(now_et, cadence="index")

    async def tick_staged_execution_job(self):
        """High-frequency deferred staged execution runner (every 10s)."""
        is_open, now_et = self._is_market_hours()
        if not is_open:
            logger.debug("tick_staged_execution: outside market hours, skipping.")
            return

        logger.debug(f"tick_staged_execution @ {now_et.strftime('%H:%M:%S %Z')}")
        await self.engine.run_staged_execution_tick(now_et)

    async def tick_stock_job(self):
        """Tier-2: manage + scan for stock strategies every 5 minutes."""
        is_open, now_et = self._is_market_hours()
        if not is_open:
            logger.debug("tick_stock: outside market hours, skipping.")
            return

        logger.info(f"tick_stock @ {now_et.strftime('%H:%M:%S %Z')}")
        await self.engine.run_manage_tick(now_et, cadence="stock")
        await self.engine.run_scan_tick(now_et, cadence="stock")

    async def tick_daily_job(self):
        """Tier-3: daily scan for Wheel, Earnings Strangle once at 10:00 ET."""
        now_et = datetime.now(TZ_ET)
        if now_et.weekday() >= 5:
            return

        logger.info(f"tick_daily @ {now_et.strftime('%H:%M:%S %Z')} — running daily strategy scans")
        await self.engine.run_scan_tick(now_et, cadence="daily")

    # ------------------------------------------------------------------
    # Analytics jobs
    # ------------------------------------------------------------------

    async def eod_analytics_job(self):
        """EOD daily rollup at 16:30 ET Mon-Fri."""
        now_et = datetime.now(TZ_ET)
        logger.info(f"EOD analytics @ {now_et}")
        await self.analytics.run_daily_rollup(now_et)

    async def daily_system_audit_job(self):
        """Daily system audit report at 16:35 ET Mon-Fri."""
        now_et = datetime.now(TZ_ET)
        logger.info(f"Daily system audit @ {now_et}")
        try:
            from scripts.analysis.daily_system_audit import run_audit
            date_str = now_et.strftime("%Y-%m-%d")
            await run_audit(date_str, send_to_discord=True)
            logger.info("Daily system audit report successfully generated and sent to Discord.")
        except Exception as e:
            logger.error(f"daily_system_audit_job: Failed to run daily audit: {e}", exc_info=True)

    async def weekly_analytics_job(self):
        """Weekly rollup on Sunday 17:00 ET (M5)."""
        now_et = datetime.now(TZ_ET)
        logger.info(f"Weekly analytics @ {now_et}")
        await self.analytics.run_weekly_rollup(now_et)

    # ------------------------------------------------------------------
    # Maintenance jobs
    # ------------------------------------------------------------------

    async def earnings_refresh_job(self):
        """Sunday 18:00 ET — refresh earnings calendar for all tracked tickers (M3)."""
        now_et = datetime.now(TZ_ET)
        logger.info(f"Earnings calendar refresh @ {now_et}")
        earnings_svc = self.engine.services.get("earnings")
        if not earnings_svc:
            logger.error("earnings_refresh_job: EarningsService not available.")
            return

        all_tickers = list(INDEX_TICKERS | STOCK_TICKERS)
        try:
            await earnings_svc.fetch_upcoming_all(all_tickers)
            logger.info(f"Earnings calendar refreshed for {len(all_tickers)} tickers.")
        except Exception as e:
            logger.error(f"earnings_refresh_job: Failed: {e}", exc_info=True)

    async def maintenance_job(self):
        """
        Daily 03:00 ET — prune stale rows (M4):
          - QuoteSnapshot older than 90 days
          - SignalNearMiss older than 30 days
        """
        now_utc = datetime.now(timezone.utc)
        cutoff_snapshots = now_utc - timedelta(days=90)
        cutoff_nearmiss = now_utc - timedelta(days=30)

        logger.info(f"DB maintenance prune @ {datetime.now(TZ_ET)}")

        try:
            deleted_qs = await self.db.quotesnapshot.delete_many(
                where={"takenAt": {"lt": cutoff_snapshots}}
            )
            logger.info(f"Pruned {deleted_qs} QuoteSnapshot rows older than 90 days.")
        except Exception as e:
            logger.error(f"maintenance_job: Failed to prune QuoteSnapshot: {e}")

        try:
            deleted_nm = await self.db.signalnearmiss.delete_many(
                where={"evaluatedAt": {"lt": cutoff_nearmiss}}
            )
            logger.info(f"Pruned {deleted_nm} SignalNearMiss rows older than 30 days.")
        except Exception as e:
            logger.error(f"maintenance_job: Failed to prune SignalNearMiss: {e}")


if __name__ == "__main__":
    runner = Runner()
    try:
        asyncio.run(runner.start())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Received interrupt, shutting down.")
