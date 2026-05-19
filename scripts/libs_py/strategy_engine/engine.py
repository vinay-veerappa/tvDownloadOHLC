import logging
import os
import yaml
from datetime import datetime, timedelta
import pytz

from scripts.libs_py.strategy_engine.strategies import (
    WheelStrategy,
    ZeroDtePcsStrategy,
    LongDteCreditStrategy,
    MeanReversionEmStrategy,
    WallBreakStrategy,
    IncomeCcStrategy,
    EarningsStrangleStrategy
)
from scripts.libs_py.strategy_engine.strategies.base import StrategyParams
from scripts.libs_py.strategy_engine.paper_exec import PaperExecutor

# Import all services
from scripts.libs_py.strategy_engine.services.broker_service import BrokerService
from scripts.libs_py.strategy_engine.services.regime_service import RegimeService
from scripts.libs_py.strategy_engine.services.em_service import ExpectedMoveService
from scripts.libs_py.strategy_engine.services.iv_service import IvService
from scripts.libs_py.strategy_engine.services.ict_service import IctService
from scripts.libs_py.strategy_engine.services.calendar_service import CalendarService
from scripts.libs_py.strategy_engine.services.earnings_service import EarningsService
from scripts.libs_py.strategy_engine.services.holding_service import HoldingService
from scripts.libs_py.strategy_engine.services.sizing_service import SizingService
from scripts.libs_py.strategy_engine.services.leg_quote_service import LegQuoteService

logger = logging.getLogger(__name__)

STRATEGY_CLASSES = {
    "WHEEL": WheelStrategy,
    "ZERO_DTE_PCS": ZeroDtePcsStrategy,
    "LONG_DTE_CREDIT": LongDteCreditStrategy,
    "MEAN_REVERSION_EM": MeanReversionEmStrategy,
    "WALL_BREAK": WallBreakStrategy,
    "INCOME_CC": IncomeCcStrategy,
    "EARNINGS_STRANGLE": EarningsStrangleStrategy
}

INDEX_TICKERS = {"SPY", "SPX", "QQQ", "IWM"}
STOCK_TICKERS = {"NVDA", "TSLA", "AAPL", "GOOGL", "MSFT", "AMZN", "RIVN"}
DAILY_STRATEGY_CODES = {"WHEEL", "EARNINGS_STRANGLE", "INCOME_CC","LONG_DTE_CREDIT"}

class Engine:
    """
    Main Strategy Engine.
    Coordinating tick scanning, real-time mark-to-market management, 
    service initializations, and order executions.
    """
    def __init__(self, prisma, config_path: str):
        self.db = prisma
        self.config_path = config_path
        self.config = {}
        self.services = {}
        self.active_strategies = {}
        self.executor = None
        self._staleness_cache = {}  # C1: per-tick staleness cache

    async def initialize(self):
        """Initializes all services and instantiates enabled strategy variants."""
        logger.info("Initializing Options Strategy Engine...")
        
        # 1. Load config
        with open(self.config_path, "r") as f:
            self.config = yaml.safe_load(f)

        # 2. Instantiate and wire Services
        # In a real environment, we'd pass active calculators/fetchers to the services.
        # Here we initialize them with the prisma client and standard parameters.
        broker = BrokerService() # internal mock/direct Schwab API
        regime = RegimeService(db=self.db)
        em = ExpectedMoveService(db=self.db)
        iv = IvService(db=self.db) # direct EOD fallbacks
        ict = IctService()
        calendar = CalendarService(prisma_client=self.db)
        earnings = EarningsService(prisma_client=self.db)
        holdings = HoldingService(prisma_client=self.db)
        sizing = SizingService(prisma_client=self.db)
        leg_quote = LegQuoteService(broker_service=broker)

        self.services = {
            "prisma": self.db,
            "broker": broker,
            "regime": regime,
            "em": em,
            "iv": iv,
            "ict": ict,
            "calendar": calendar,
            "earnings": earnings,
            "holdings": holdings,
            "sizing": sizing,
            "leg_quote": leg_quote,
            "config": self.config
        }

        self.executor = PaperExecutor(self.db, broker, holdings)

        # 3. Instantiate enabled Strategy combinations (silos)
        loaded = 0
        skipped_disabled = 0
        for strategy_code, strat_cfg in self.config.get("strategies", {}).items():
            tickers = strat_cfg.get("tickers", [])
            variants = strat_cfg.get("variants", {})

            for variant_name, variant_params in variants.items():
                variant_params = variant_params or {}

                # M10: Skip disabled variants — log WARNING so operator is aware
                is_enabled = variant_params.get("enabled", True)  # default True if not specified
                if not is_enabled:
                    logger.warning(
                        f"Engine: Variant '{strategy_code}/{variant_name}' is DISABLED in config.yaml. Skipping all {len(tickers)} ticker(s)."
                    )
                    skipped_disabled += len(tickers)
                    continue

                for ticker in tickers:
                    comb_name = f"{strategy_code}_{variant_name}_{ticker}"

                    # Look up ResearchStrategy to link its DB id
                    research_strat = await self.db.researchstrategy.find_unique(where={"name": comb_name})
                    if not research_strat:
                        logger.warning(f"Engine: Seed data missing for ResearchStrategy '{comb_name}'. Skipping.")
                        continue

                    # Instantiate Strategy class
                    strat_class = STRATEGY_CLASSES.get(strategy_code)
                    if not strat_class:
                        logger.error(f"Engine: Unknown strategy code '{strategy_code}'")
                        continue

                    # Look up Account to get account_id
                    account = await self.db.account.find_first(where={"name": comb_name})
                    account_id = account.id if account else "unknown"

                    params = StrategyParams(
                        research_strategy_id=research_strat.id,
                        name=comb_name,
                        category=strategy_code,
                        underlying=ticker,
                        account_id=account_id,
                        params=variant_params,   # M7: full variant dict (incl. exit rules) passed through
                        enabled=True             # already filtered above
                    )

                    strategy_instance = strat_class(
                        params=params,
                        services=self.services
                    )

                    self.active_strategies[comb_name] = strategy_instance
                    loaded += 1

        logger.info(
            f"Engine: Loaded {loaded} active strategy combinations "
            f"({skipped_disabled} skipped — disabled in config)."
        )

    async def run_scan_tick(self, now: datetime, cadence: str = "index"):
        """
        Entry scan tick. Cadence filters which strategies execute:
          "index"  — only strategies whose underlying is an index/ETF
          "stock"  — only strategies whose underlying is a stock
          "daily"  — only strategies in DAILY_STRATEGY_CODES (Wheel, Earnings)
        """
        logger.info(f"Engine: Starting scan tick [{cadence}] at {now}")

        for name, strategy in self.active_strategies.items():
            try:
                # Cadence routing
                strategy_code = strategy.params.category
                underlying = strategy.params.underlying

                if cadence == "index":
                    if underlying not in INDEX_TICKERS:
                        continue
                    if strategy_code in DAILY_STRATEGY_CODES:
                        continue  # Wheel/Earnings on indices run only at 10:00
                elif cadence == "stock":
                    if underlying not in STOCK_TICKERS:
                        continue
                    if strategy_code in DAILY_STRATEGY_CODES:
                        continue
                elif cadence == "daily":
                    if strategy_code not in DAILY_STRATEGY_CODES:
                        continue

                # Staleness check for indices
                if underlying in INDEX_TICKERS:
                    is_stale = await self._check_index_staleness(underlying, now)
                    if is_stale:
                        logger.warning(f"Engine: Skipping entry scan for index silo '{name}' — GEX data stale.")
                        continue

                signals = await strategy.scan(now)
                for signal in signals:
                    await self.executor.execute_signal(name, signal, now)

            except Exception as e:
                logger.error(f"Engine: Error during scan tick for strategy '{name}': {e}", exc_info=True)

    async def run_manage_tick(self, now: datetime, cadence: str = "index"):
        """
        Mark-to-market management tick. Only manages trades belonging to the
        strategies active in the given cadence to avoid redundant MTM work.
        """
        logger.info(f"Engine: Starting management tick [{cadence}] at {now}")

        # Fetch all open trades
        open_trades = await self.executor.list_open_trades()

        for trade in open_trades:
            try:
                # Find matching strategy instance by Account name
                account_name = trade.account.name
                strategy = self.active_strategies.get(account_name)
                if not strategy:
                    logger.warning(f"Engine: Open trade {trade.id} linked to account '{account_name}', but no strategy instance is loaded.")
                    continue

                # Cadence filter — only manage trades that belong to this tier
                underlying = strategy.params.underlying
                strategy_code = strategy.params.category
                if cadence == "index" and underlying not in INDEX_TICKERS:
                    continue
                if cadence == "stock" and underlying not in STOCK_TICKERS:
                    continue
                if cadence == "daily":
                    continue  # daily scan doesn't manage open trades

                # Get real-time MTM valuation
                current_mtm = await self.services["leg_quote"].get_trade_mtm(trade)
                if not current_mtm:
                    continue

                # Create MTM QuoteSnapshot record
                await self.db.quotesnapshot.create(
                    data={
                        "tradeId": trade.id,
                        "takenAt": now,
                        "underlyingPx": float(current_mtm["underlying_px"]),
                        "netValue": float(current_mtm["net_value"]),
                        "unrealizedPnl": float(current_mtm["unrealized_pnl"]),
                        "legPrices": current_mtm["leg_prices_json"]
                    }
                )

                # Evaluate strategy management exit conditions
                action = await strategy.manage(trade, current_mtm, now)
                if action.close:
                    logger.info(f"Engine: Exit triggered for trade {trade.id}. Reason: {action.reason or 'Management Rule'}")
                    # Close the trade
                    await self.executor.close_trade(
                        trade,
                        action,
                        current_mtm["net_value_per_contract"],
                        now
                    )

            except Exception as e:
                logger.error(f"Engine: Error managing trade {trade.id}: {e}", exc_info=True)

    @staticmethod
    def _is_rth(now: datetime) -> bool:
        """Return True if `now` falls within RTH (9:30–16:00 ET, Mon–Fri)."""
        from zoneinfo import ZoneInfo
        now_et = now.astimezone(ZoneInfo("America/New_York"))
        if now_et.weekday() >= 5:
            return False
        mkt_open  = now_et.replace(hour=9,  minute=30, second=0, microsecond=0)
        mkt_close = now_et.replace(hour=16, minute=0,  second=0, microsecond=0)
        return mkt_open <= now_et <= mkt_close

    async def _check_index_staleness(self, ticker: str, now: datetime) -> bool:
        """
        For indices (SPX, SPY, etc.), any GEX/EM snapshot older than 15 minutes
        during RTH indicates that the upstream streaming pipeline has stopped.
        In this scenario, entries must be blocked to prevent stale-data entries.

        Outside RTH the GEX writer does not run, so old data is expected — scans
        are silently skipped (DEBUG) without raising a WARNING.
        """
        # C1: check per-tick cache
        if ticker in self._staleness_cache:
            cache_val, cache_ts = self._staleness_cache[ticker]
            if cache_ts == now:
                return cache_val

        # Outside RTH the pipeline does not write GEX snapshots; data will always
        # appear stale.  Skip silently — this is not an actionable warning.
        if not self._is_rth(now):
            logger.debug(f"Engine: Staleness check skipped for {ticker} — outside RTH.")
            self._staleness_cache[ticker] = (True, now)
            return True

        try:
            # Query the latest GexSnapshot for this ticker — use timestamp, not createdAt (B7)
            latest_gex = await self.db.gexsnapshot.find_first(
                where={"ticker": ticker},
                order={"timestamp": "desc"}
            )
            if not latest_gex:
                logger.warning(f"Engine: No GexSnapshot found for {ticker} during RTH — pipeline may not have started.")
                self._staleness_cache[ticker] = (True, now)
                return True

            # Calculate time difference — convert (not relabel) to UTC (B7)
            gex_time = latest_gex.timestamp
            if gex_time.tzinfo is None:
                gex_time = pytz.utc.localize(gex_time)
            now_utc = now.astimezone(pytz.utc)
            diff_seconds = (now_utc - gex_time).total_seconds()

            if diff_seconds > 900.0:
                logger.warning(
                    f"Engine: Staleness alert! Latest GEX snapshot for {ticker} is "
                    f"{diff_seconds:.1f}s old during RTH — upstream pipeline may have stopped."
                )
                self._staleness_cache[ticker] = (True, now)
                return True

            self._staleness_cache[ticker] = (False, now)
            return False

        except Exception as e:
            logger.error(f"Engine: Error checking staleness for {ticker}: {e}")
            return True
