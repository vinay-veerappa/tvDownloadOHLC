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

    async def initialize(self):
        """Initializes all services and instantiates enabled strategy variants."""
        logger.info("Initializing Options Strategy Engine...")
        
        # 1. Load config
        with open(self.config_path, "r") as f:
            self.config = yaml.safe_load(f)

        # 2. Instantiate and wire Services
        # In a real environment, we'd pass active calculators/fetchers to the services.
        # Here we initialize them with the prisma client and standard parameters.
        broker = BrokerService(options_fetcher=None) # internal mock/direct Schwab API
        regime = RegimeService(prisma_client=self.db)
        em = ExpectedMoveService(prisma_client=self.db)
        iv = IvService(prisma_client=self.db, dolt_adapter=None) # direct EOD fallbacks
        ict = IctService()
        calendar = CalendarService(prisma_client=self.db)
        earnings = EarningsService(prisma_client=self.db)
        holdings = HoldingService(prisma_client=self.db)
        sizing = SizingService(prisma_client=self.db)
        leg_quote = LegQuoteService(broker=broker)

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
            "leg_quote": leg_quote
        }

        self.executor = PaperExecutor(self.db, broker, holdings)

        # 3. Instantiate enabled Strategy combinations (silos)
        for strategy_code, strat_cfg in self.config.get("strategies", {}).items():
            tickers = strat_cfg.get("tickers", [])
            variants = strat_cfg.get("variants", {})

            for variant_name, variant_params in variants.items():
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

                    params = StrategyParams(
                        research_strategy_id=research_strat.id,
                        strategy_category=strategy_code,
                        underlying=ticker,
                        variant_name=variant_name,
                        parameters=variant_params or {}
                    )

                    strategy_instance = strat_class(
                        name=comb_name,
                        underlying=ticker,
                        params=params,
                        services=self.services
                    )

                    self.active_strategies[comb_name] = strategy_instance

        logger.info(f"Engine: Successfully loaded {len(self.active_strategies)} active strategy combinations.")

    async def run_scan_tick(self, now: datetime):
        """Intraday/Daily entry scan tick. Runs for all active strategy instances."""
        logger.info(f"Engine: Starting scan tick at {now}")

        for name, strategy in self.active_strategies.items():
            try:
                # Staleness check for indices
                if strategy.underlying in INDEX_TICKERS:
                    is_stale = await self._check_index_staleness(strategy.underlying, now)
                    if is_stale:
                        logger.warning(f"Engine: Skipping entry scan for index silo '{name}' due to GEX/EM data staleness.")
                        continue

                # Run scan
                signals = await strategy.scan(now)
                for signal in signals:
                    await self.executor.execute_signal(name, signal, now)

            except Exception as e:
                logger.error(f"Engine: Error during scan tick for strategy '{name}': {e}", exc_info=True)

    async def run_manage_tick(self, now: datetime):
        """Real-time mark-to-market management tick. Evaluates open paper trades."""
        logger.info(f"Engine: Starting management tick at {now}")

        # Fetch all open trades
        open_trades = await self.db.trade.find_many(
            where={"status": "OPEN"},
            include={"legs": True, "account": True}
        )

        for trade in open_trades:
            try:
                # Find matching strategy instance by Account name
                account_name = trade.account.name
                strategy = self.active_strategies.get(account_name)
                if not strategy:
                    logger.warning(f"Engine: Open trade {trade.id} linked to account '{account_name}', but no strategy instance is loaded.")
                    continue

                # Get real-time MTM valuation
                current_mtm = await self.services["leg_quote"].get_trade_mtm(trade)
                if not current_mtm:
                    continue

                # Create MTM QuoteSnapshot record
                await self.db.quotesnapshot.create(
                    data={
                        "tradeId": trade.id,
                        "takenAt": now,
                        "underlyingPx": float(current_mtm.underlying_px),
                        "netValue": float(current_mtm.net_value_per_contract),
                        "unrealizedPnl": float(current_mtm.unrealized_pnl),
                        "legPrices": current_mtm.leg_prices_json
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
                        current_mtm.net_value_per_contract,
                        now
                    )

            except Exception as e:
                logger.error(f"Engine: Error managing trade {trade.id}: {e}", exc_info=True)

    async def _check_index_staleness(self, ticker: str, now: datetime) -> bool:
        """
        For indices (SPX, SPY, etc.), any GEX/EM snapshot older than 5 minutes 
        indicates that the upstream streaming pipeline has stopped. 
        In this scenario, entries must be blocked to prevent outdated entries.
        """
        try:
            # Query the latest GexSnapshot for this ticker
            latest_gex = await self.db.gexsnapshot.find_first(
                where={"ticker": ticker},
                order={"createdAt": "desc"}
            )
            if not latest_gex:
                return True

            # Calculate time difference
            gex_time = latest_gex.createdAt.replace(tzinfo=pytz.utc)
            now_utc = now.replace(tzinfo=pytz.utc)
            diff_seconds = (now_utc - gex_time).total_seconds()

            if diff_seconds > 300.0:
                logger.warning(f"Engine: Staleness alert! Latest GEX snapshot for {ticker} is {diff_seconds:.1f} seconds old.")
                return True

            return False

        except Exception as e:
            logger.error(f"Engine: Error checking staleness for {ticker}: {e}")
            return True
