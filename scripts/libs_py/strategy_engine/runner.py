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
import json
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

from datetime import datetime, timedelta, timezone, time
from typing import Set, Optional

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
from prisma import Prisma

from logging.handlers import RotatingFileHandler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        RotatingFileHandler("strategy_engine.log", maxBytes=10*1024*1024, backupCount=5, encoding="utf-8"),
    ],
)

# Suppress chatty third-party loggers
for noisy in ("httpx", "httpcore", "urllib3", "apscheduler", "prisma"):
    logging.getLogger(noisy).setLevel(logging.WARNING)

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



def map_ticker_for_yfinance(ticker: str) -> str:
    if ticker.upper() == "SPX":
        return "^SPX"
    if ticker.upper() == "NDX":
        return "^NDX"
    if ticker.upper() == "RUT":
        return "^RUT"
    if ticker.upper() == "VIX":
        return "^VIX"
    return ticker.upper()


def get_last_scheduled_earnings_refresh(now_et: datetime) -> datetime:
    # Sunday 18:00
    days_back = (now_et.weekday() - 6) % 7
    target = now_et - timedelta(days=days_back)
    target = target.replace(hour=18, minute=0, second=0, microsecond=0)
    if target > now_et:
        target -= timedelta(days=7)
    return target


def get_last_scheduled_tick_daily(now_et: datetime) -> datetime:
    # Mon-Fri 10:00
    for i in range(10):
        candidate = now_et - timedelta(days=i)
        if candidate.weekday() < 5:  # Mon-Fri
            target = candidate.replace(hour=10, minute=0, second=0, microsecond=0)
            if target <= now_et:
                return target
    return now_et - timedelta(days=7)


def get_last_scheduled_eod_analytics(now_et: datetime) -> datetime:
    # Mon-Fri 16:30
    for i in range(10):
        candidate = now_et - timedelta(days=i)
        if candidate.weekday() < 5:  # Mon-Fri
            target = candidate.replace(hour=16, minute=30, second=0, microsecond=0)
            if target <= now_et:
                return target
    return now_et - timedelta(days=7)


def get_last_scheduled_economic_refresh(now_et: datetime) -> datetime:
    # Daily 16:30 ET
    target = now_et.replace(hour=16, minute=30, second=0, microsecond=0)
    if target > now_et:
        target -= timedelta(days=1)
    return target


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

        # Reconcile expired trades and missed jobs on boot
        try:
            await self.reconcile_expired_trades()
        except Exception as e:
            logger.error(f"Error during expired trades reconciliation: {e}", exc_info=True)

        try:
            await self.reconcile_missed_jobs()
        except Exception as e:
            logger.error(f"Error during missed jobs reconciliation: {e}", exc_info=True)

        try:
            await self.reconcile_dolt_database()
        except Exception as e:
            logger.error(f"Error during Dolt database reconciliation: {e}", exc_info=True)

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
    # State Persistence and Reconciliation
    # ------------------------------------------------------------------

    def _load_scheduler_state(self) -> dict:
        state_path = os.path.join(os.path.dirname(__file__), "scheduler_state.json")
        if os.path.exists(state_path):
            try:
                with open(state_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load scheduler_state.json: {e}")
        return {}

    def _save_scheduler_state(self, state: dict):
        state_path = os.path.join(os.path.dirname(__file__), "scheduler_state.json")
        try:
            with open(state_path, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to save scheduler_state.json: {e}")

    async def reconcile_missed_jobs(self):
        """Checks scheduler_state.json and runs missed cron jobs retroactively."""
        logger.info("Reconciling missed cron jobs...")
        now_et = datetime.now(TZ_ET)
        state = self._load_scheduler_state()

        def parse_iso(dt_str):
            if not dt_str:
                return None
            try:
                return datetime.fromisoformat(dt_str)
            except Exception:
                return None

        last_daily_scan_str = state.get("last_daily_scan")
        last_earnings_refresh_str = state.get("last_earnings_refresh")
        last_eod_analytics_str = state.get("last_eod_analytics")

        last_daily_scan = parse_iso(last_daily_scan_str)
        last_earnings_refresh = parse_iso(last_earnings_refresh_str)
        last_eod_analytics = parse_iso(last_eod_analytics_str)
        last_econ_refresh_str = state.get("last_econ_refresh")
        last_econ_refresh = parse_iso(last_econ_refresh_str)

        # 0. Economic Calendar Refresh (Daily 03:05 ET)
        target_econ = get_last_scheduled_economic_refresh(now_et)
        if not last_econ_refresh or last_econ_refresh < target_econ:
            logger.info(f"Missed economic calendar refresh (last run: {last_econ_refresh}, target: {target_econ}). Running retroactively...")
            await self.economic_calendar_refresh_job()
            state = self._load_scheduler_state()
            state["last_econ_refresh"] = target_econ.isoformat()
            self._save_scheduler_state(state)

        # 1. Earnings Refresh (Sunday 18:00 ET)
        target_earnings = get_last_scheduled_earnings_refresh(now_et)
        if not last_earnings_refresh or last_earnings_refresh < target_earnings:
            logger.info(f"Missed earnings refresh (last run: {last_earnings_refresh}, target: {target_earnings}). Running retroactively...")
            await self.earnings_refresh_job()
            state = self._load_scheduler_state()
            state["last_earnings_refresh"] = target_earnings.isoformat()
            self._save_scheduler_state(state)

        # 2. Daily Strategy Scan (Mon-Fri 10:00 ET)
        target_daily = get_last_scheduled_tick_daily(now_et)
        if not last_daily_scan or last_daily_scan < target_daily:
            if target_daily.date() == now_et.date() and now_et.hour >= 16:
                logger.warning(f"Missed daily strategy scan for today {target_daily.date()} but engine restarted after 16:00 ET close. Skipping retroactive run to avoid risky late entries.")
                state = self._load_scheduler_state()
                state["last_daily_scan"] = target_daily.isoformat()
                self._save_scheduler_state(state)
            else:
                logger.info(f"Missed daily strategy scan (last run: {last_daily_scan}, target: {target_daily}). Running retroactively...")
                await self.tick_daily_job()
                state = self._load_scheduler_state()
                state["last_daily_scan"] = target_daily.isoformat()
                self._save_scheduler_state(state)

        # 3. EOD Analytics Rollup (Mon-Fri 16:30 ET)
        target_eod = get_last_scheduled_eod_analytics(now_et)
        if not last_eod_analytics or last_eod_analytics < target_eod:
            logger.info(f"Missed EOD analytics rollup (last run: {last_eod_analytics}, target: {target_eod}). Running retroactively...")
            await self.eod_analytics_job()
            state = self._load_scheduler_state()
            state["last_eod_analytics"] = target_eod.isoformat()
            self._save_scheduler_state(state)

        logger.info("Missed cron job reconciliation complete.")

    async def reconcile_dolt_database(self):
        """Asynchronously pulls latest option database commits from DoltHub on startup."""
        logger.info("Reconciling Dolt options database on startup...")
        dolt_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../data/options/options"))
        if not os.path.exists(dolt_dir):
            logger.warning(f"Dolt database directory not found at: {dolt_dir}. Skipping synchronization.")
            return

        def run_pull():
            import subprocess
            logger.info("Running 'dolt pull' to synchronize options database...")
            res = subprocess.run(["dolt", "pull"], cwd=dolt_dir, capture_output=True, text=True)
            return res

        try:
            res = await asyncio.to_thread(run_pull)
            if res.returncode == 0:
                logger.info("Dolt options database pulled successfully. Local database is fully synchronized.")
                if res.stdout:
                    logger.info(f"Dolt pull output:\n{res.stdout.strip()}")
            else:
                logger.warning(f"Dolt pull failed with return code {res.returncode}. Output:\n{res.stderr.strip()}")
        except Exception as e:
            logger.error(f"Failed to pull from DoltHub during startup reconciliation: {e}", exc_info=True)

    async def get_historical_close_price(self, ticker: str, expiry_date) -> Optional[float]:
        """Fetches historical closing price of the underlying ticker using a tiered fallback hierarchy."""
        from datetime import date as dt_date
        target_date = expiry_date.date() if isinstance(expiry_date, datetime) else expiry_date
        
        logger.info(f"Resolving historical spot price for {ticker} on {target_date} using tiered fallback...")
        
        # Tier 1: Local Parquet lookup (accurate, offline)
        try:
            from scripts.streaming.options.dolt_fallback import fetch_historical_spot_local
            spot_val = await asyncio.to_thread(fetch_historical_spot_local, ticker, target_date)
            if spot_val is not None:
                logger.info(f"Tier 1 [Parquet] resolved {ticker} spot price on {target_date}: {spot_val}")
                return spot_val
        except Exception as e:
            logger.warning(f"Tier 1 [Parquet] lookup failed: {e}")

        # Tier 2: yfinance lookup (accurate, online)
        try:
            from scripts.streaming.options.dolt_fallback import fetch_historical_spot_yfinance
            spot_val = await asyncio.to_thread(fetch_historical_spot_yfinance, ticker, target_date)
            if spot_val is not None:
                logger.info(f"Tier 2 [yfinance] resolved {ticker} spot price on {target_date}: {spot_val}")
                return spot_val
        except Exception as e:
            logger.warning(f"Tier 2 [yfinance] lookup failed: {e}")

        # Tier 3: Dolt Put-Call Parity (estimated, offline fallback-of-fallback)
        try:
            from scripts.streaming.options.dolt_fallback import fetch_from_dolt
            logger.info(f"Attempting Tier 3 [Dolt Put-Call Parity] fallback for {ticker} on {target_date}...")
            # fetch_from_dolt returns OptionChainData, which resolves spot using Put-Call parity internally
            chain = await asyncio.to_thread(fetch_from_dolt, ticker, target_date.strftime("%Y-%m-%d"))
            if chain and chain.spot_price > 0:
                logger.info(f"Tier 3 [Dolt Put-Call Parity] resolved {ticker} estimated spot price on {target_date}: {chain.spot_price:.2f}")
                return chain.spot_price
        except Exception as e:
            logger.warning(f"Tier 3 [Dolt Put-Call Parity] estimation failed: {e}")

        logger.error(f"Failed to resolve historical close price for {ticker} on {target_date} using all fallback tiers.")
        return None

    async def reconcile_expired_trades(self):
        """Audits all OPEN trades immediately on startup and resolves expired options."""
        logger.info("Auditing open trades for expired options on startup...")
        now_et = datetime.now(TZ_ET)
        
        try:
            open_trades = await self.db.trade.find_many(
                where={"status": "OPEN"},
                include={"legs": True, "account": True}
            )
        except Exception as e:
            logger.error(f"Failed to fetch open trades: {e}")
            return

        reconciled_count = 0
        for trade in open_trades:
            is_options_trade = any(l.optionType in ["CALL", "PUT"] for l in trade.legs)
            if not is_options_trade:
                continue

            has_expired_legs = False
            expiry_date = None
            for leg in trade.legs:
                if leg.optionType in ["CALL", "PUT"] and leg.expiry:
                    leg_expiry_date = leg.expiry.date() if isinstance(leg.expiry, datetime) else leg.expiry
                    if leg_expiry_date < now_et.date() or (leg_expiry_date == now_et.date() and now_et.hour >= 16):
                        has_expired_legs = True
                        expiry_date = leg_expiry_date
                        break

            if not has_expired_legs:
                continue

            logger.info(f"Reconciling expired trade {trade.id} ({trade.ticker}) with expiry {expiry_date}")
            
            underlying_close = await self.get_historical_close_price(trade.ticker, expiry_date)
            if underlying_close is None:
                logger.warning(f"Failed to fetch historical close price for {trade.ticker} on {expiry_date}. Defaulting legs to OTM/worthless.")

            trade_pnl = 0.0
            stock_gain = 0.0
            is_assignment = False
            qty = trade.quantity

            short_assigned_legs = []
            for leg in trade.legs:
                if leg.optionType in ["CALL", "PUT"] and leg.side == "SHORT":
                    if underlying_close is not None:
                        if leg.optionType == "PUT" and underlying_close <= leg.strike:
                            short_assigned_legs.append(leg)
                        elif leg.optionType == "CALL" and underlying_close >= leg.strike:
                            short_assigned_legs.append(leg)

            if len(short_assigned_legs) > 0:
                is_assignment = True

            if is_assignment:
                for leg in short_assigned_legs:
                    strike = leg.strike
                    shares = int(qty * 100)
                    if leg.optionType == "PUT":
                        logger.info(f"Reconciliation: CSP assignment. Buying {shares} shares of {trade.ticker} at ${strike:.2f}")
                        holdings_svc = self.engine.services.get("holdings")
                        if holdings_svc:
                            await holdings_svc.add_shares(trade.ticker, shares, strike, datetime.now(timezone.utc))
                        else:
                            logger.error("HoldingService not available for CSP assignment.")
                    elif leg.optionType == "CALL":
                        logger.info(f"Reconciliation: CC assignment. Selling {shares} shares of {trade.ticker} at ${strike:.2f}")
                        holdings_svc = self.engine.services.get("holdings")
                        if holdings_svc:
                            holding = await holdings_svc.get_holding(trade.ticker)
                            stock_cost_basis = holding["cost_basis"] if holding else strike
                            await holdings_svc.remove_shares(trade.ticker, shares)
                            stock_gain += (strike - stock_cost_basis) * shares
                            logger.info(f"Reconciliation: CC Realized stock gain: ${stock_gain:+,.2f} (Cost Basis: ${stock_cost_basis:.2f})")
                        else:
                            logger.error("HoldingService not available for CC assignment.")

            leg_exit_slippages = []
            for leg in trade.legs:
                multiplier = 100.0 if leg.optionType in ["CALL", "PUT"] else 1.0
                leg_assigned = leg in short_assigned_legs
                
                close_val = 0.0
                expired_otm = True
                if leg.optionType in ["CALL", "PUT"]:
                    if underlying_close is not None:
                        if leg.side == "LONG":
                            if leg.optionType == "CALL" and underlying_close > leg.strike:
                                close_val = underlying_close - leg.strike
                                expired_otm = False
                            elif leg.optionType == "PUT" and underlying_close < leg.strike:
                                close_val = leg.strike - underlying_close
                                expired_otm = False
                        else:
                            if leg_assigned:
                                expired_otm = False
                            else:
                                expired_otm = True
                    else:
                        close_val = 0.0
                        expired_otm = True
                
                leg_pnl = 0.0
                if leg.side == "SHORT":
                    leg_pnl = (leg.openPrice - close_val) * leg.quantity * multiplier
                else:
                    leg_pnl = (close_val - leg.openPrice) * leg.quantity * multiplier

                trade_pnl += leg_pnl
                leg_exit_slippages.append(0.0)

                try:
                    await self.db.tradeleg.update(
                        where={"id": leg.id},
                        data={
                            "closePrice": close_val,
                            "closeBid": 0.0,
                            "closeAsk": 0.0,
                            "legPnl": leg_pnl,
                            "assigned": leg_assigned,
                            "expiredOtm": expired_otm
                        }
                    )
                except Exception as le:
                    logger.error(f"Failed to update leg {leg.id} in DB: {le}")

            trade_pnl += stock_gain
            cash_effect = trade_pnl

            status_label = "ASSIGNED" if is_assignment else "CLOSED"
            try:
                meta = json.loads(trade.metadata) if trade.metadata else {}
            except Exception:
                meta = {}
            meta["exit_slippages"] = leg_exit_slippages
            meta["reconciled_at_startup"] = True
            if underlying_close is not None:
                meta["expiry_underlying_close"] = underlying_close

            try:
                await self.db.trade.update(
                    where={"id": trade.id},
                    data={
                        "exitDate": datetime.now(timezone.utc),
                        "exitPrice": 0.0,
                        "pnl": trade_pnl,
                        "status": status_label,
                        "notes": (trade.notes or "") + f" | Reconciled at startup: option expired. Underlying close on {expiry_date}: {f'${underlying_close:.2f}' if underlying_close else 'N/A'}",
                        "metadata": json.dumps(meta)
                    }
                )
            except Exception as te:
                logger.error(f"Failed to update trade {trade.id} in DB: {te}")

            # Fetch fresh account balance from DB to prevent stale state updates in loops
            try:
                fresh_acc = await self.db.account.find_unique(where={"id": trade.account.id})
                current_bal = fresh_acc.currentBalance if fresh_acc else trade.account.currentBalance
                account = fresh_acc if fresh_acc else trade.account
            except Exception as ae:
                logger.warning(f"Failed to fetch fresh account balance for {trade.account.name}: {ae}")
                current_bal = trade.account.currentBalance
                account = trade.account

            new_balance = current_bal + cash_effect
            try:
                await self.db.account.update(
                    where={"id": trade.account.id},
                    data={"currentBalance": new_balance}
                )
            except Exception as ae:
                logger.error(f"Failed to update account balance for {trade.account.name}: {ae}")

            logger.info(f"Reconciliation: Closed trade {trade.id} ({status_label}). P&L: ${trade_pnl:+,.2f}. Cash impact: ${cash_effect:+,.2f}. New Balance: ${new_balance:,.2f}")

            try:
                pnl_indicator = "🏆 **WIN**" if trade_pnl >= 0.0 else "⚠️ **LOSS**"
                outcome_str = f"{pnl_indicator}"
                if is_assignment:
                    outcome_str = "📦 **ASSIGNED**"
                
                legs_str = ""
                for leg in trade.legs:
                    strike_str = f" ${leg.strike}" if leg.strike else ""
                    open_px = leg.openPrice if leg.openPrice is not None else 0.0
                    close_px = 0.0
                    if leg.optionType in ["CALL", "PUT"] and leg.side == "LONG" and underlying_close is not None:
                        if leg.optionType == "CALL" and underlying_close > leg.strike:
                            close_px = underlying_close - leg.strike
                        elif leg.optionType == "PUT" and underlying_close < leg.strike:
                            close_px = leg.strike - underlying_close
                    legs_str += f"• **{leg.side}** {leg.optionType}{strike_str} (Open: ${open_px:.2f} | Expiry Close: ${close_px:.2f})\n"
                
                underlying_info = f"${underlying_close:.2f}" if underlying_close is not None else "N/A"
                exit_msg = (
                    f"📤 **STRATEGY ENGINE: RECONCILIATION POSITION CLOSED**\n\n"
                    f"* **Silo:** `{account.name}`\n"
                    f"* **Underlying:** `{trade.ticker}` (Close on expiry: {underlying_info})\n"
                    f"* **Outcome:** {outcome_str}\n"
                    f"* **Realized P&L:** `${trade_pnl:+,.2f}`\n"
                    f"* **New Account Balance:** `${new_balance:,.2f}`\n"
                    f"* **Legs Details:**\n{legs_str}"
                    f"* **Reconciliation Date:** `{expiry_date}`"
                )
                
                if self.engine and self.engine.executor:
                    self.engine.executor._notify_discord(exit_msg)
            except Exception as de:
                logger.warning(f"Reconciliation: Failed to send Discord notification: {de}")

            reconciled_count += 1

        logger.info(f"Reconciled {reconciled_count} expired options trades.")


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

        # Economic calendar refresh — daily 16:30 ET
        self.scheduler.add_job(
            self.economic_calendar_refresh_job,
            trigger="cron",
            hour=16,
            minute=30,
            id="economic_calendar_refresh",
            name="Economic Calendar Refresh (16:30 ET)",
            max_instances=1,
        )

        # Daily earnings calendar sync and Discord briefing (Sunday-Thursday 19:00 ET)
        self.scheduler.add_job(
            self.daily_earnings_briefing_job,
            trigger="cron",
            day_of_week="mon-thu,sun",
            hour=19,
            minute=0,
            id="daily_earnings_briefing",
            name="Daily Earnings Sync & Discord Briefing (19:00 ET)",
            max_instances=1,
        )

        # Weekly earnings calendar Discord briefing (Sunday 18:30 ET)
        self.scheduler.add_job(
            self.weekly_earnings_briefing_job,
            trigger="cron",
            day_of_week="sun",
            hour=18,
            minute=30,
            id="weekly_earnings_briefing",
            name="Weekly Earnings Discord Briefing (Sunday 18:30 ET)",
            max_instances=1,
        )

        logger.info(
            "Jobs registered: tick_index(60s), tick_staged_execution(10s), tick_stock(5m), tick_daily(10:00), "
            "eod_analytics(16:30), daily_system_audit(16:35), weekly_analytics(Sun 17:00), "
            "earnings_refresh(Sun 18:00), db_maintenance(03:00), "
            "daily_earnings_briefing(Sun-Thu 19:00), weekly_earnings_briefing(Sun 18:30)"
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

        state = self._load_scheduler_state()
        state["last_daily_scan"] = now_et.isoformat()
        self._save_scheduler_state(state)

    # ------------------------------------------------------------------
    # Analytics jobs
    # ------------------------------------------------------------------

    async def eod_analytics_job(self):
        """EOD daily rollup at 16:30 ET Mon-Fri."""
        now_et = datetime.now(TZ_ET)
        logger.info(f"EOD analytics @ {now_et}")
        await self.analytics.run_daily_rollup(now_et)

        state = self._load_scheduler_state()
        state["last_eod_analytics"] = now_et.isoformat()
        self._save_scheduler_state(state)

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

            state = self._load_scheduler_state()
            state["last_earnings_refresh"] = now_et.isoformat()
            self._save_scheduler_state(state)
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

    async def economic_calendar_refresh_job(self):
        """Daily 03:05 ET — refresh economic events calendar for next 14 days."""
        now_et = datetime.now(TZ_ET)
        logger.info(f"Economic calendar refresh @ {now_et}")
        try:
            from scripts.market_data.fetch_economic_calendar import main as run_fetch_econ
            await asyncio.to_thread(run_fetch_econ)
            logger.info("Economic calendar refreshed.")
        except Exception as e:
            logger.error(f"economic_calendar_refresh_job: Failed: {e}", exc_info=True)

    async def daily_earnings_briefing_job(self):
        """Syncs the upcoming earnings calendar and delivers the EOD briefing for the next day's session."""
        now_et = datetime.now(TZ_ET)
        logger.info(f"Starting daily earnings calendar sync and briefing @ {now_et}")
        try:
            # 1. Sync upcoming earnings calendar for next 8 days (min market cap 5B)
            from scripts.market_data.sync_earnings_calendar import run_sync
            await run_sync(days=8, min_market_cap=5e9)
            logger.info("Daily earnings calendar database sync completed.")

            # 2. Run the EOD briefing for tomorrow
            from scripts.market_data.discord_earnings_notifier import run_notify
            await asyncio.to_thread(run_notify, mode="EOD", channel_key="option-levels")
            logger.info("Daily earnings Discord briefing posted successfully.")
        except Exception as e:
            logger.error(f"daily_earnings_briefing_job failed: {e}", exc_info=True)

    async def weekly_earnings_briefing_job(self):
        """Delivers the EOW weekly roadmap briefing on Sunday evening."""
        now_et = datetime.now(TZ_ET)
        logger.info(f"Starting weekly earnings calendar briefing @ {now_et}")
        try:
            # Run the EOW weekly briefing
            from scripts.market_data.discord_earnings_notifier import run_notify
            await asyncio.to_thread(run_notify, mode="EOW", channel_key="option-levels")
            logger.info("Weekly earnings Discord briefing posted successfully.")
        except Exception as e:
            logger.error(f"weekly_earnings_briefing_job failed: {e}", exc_info=True)


if __name__ == "__main__":
    runner = Runner()
    try:
        asyncio.run(runner.start())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Received interrupt, shutting down.")
