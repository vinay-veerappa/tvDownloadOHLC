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

# Load env variables before importing engine/strategies
dotenv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../web/.env"))
load_dotenv(dotenv_path)

from scripts.libs_py.strategy_engine.engine import Engine, serialize_signal, deserialize_signal
from scripts.libs_py.strategy_engine.strategies.base import StrategyParams, Signal, LegSpec

# Setup logger
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("test_staged_pipeline")

class MockBrokerService:
    def __init__(self):
        self.spot = 500.0
        self.bid = 1.00
        self.ask = 1.10
        self.mark = 1.05
        self.option_quotes = {}

    async def get_stock_quote(self, ticker: str) -> dict:
        return {
            "symbol": ticker,
            "last": self.spot,
            "bid": self.spot,
            "ask": self.spot,
            "open": self.spot,
            "timestamp": datetime.now().timestamp()
        }

    async def get_option_quote(self, symbol: str) -> dict:
        quote = self.option_quotes.get(symbol, {"bid": self.bid, "ask": self.ask, "mark": self.mark})
        return {
            "symbol": symbol,
            "last": quote["mark"],
            "bid": quote["bid"],
            "ask": quote["ask"],
            "mark": quote["mark"],
            "iv": 0.15,
            "delta": -0.10 if "P" in symbol else 0.10,
            "gamma": 0.02,
            "theta": -0.05,
            "vega": 0.08,
            "timestamp": datetime.now().timestamp()
        }


class MockExecutor:
    def __init__(self):
        self.notifications = []
        self.trades = []

    def _notify_discord(self, msg: str):
        logger.info(f"DISCORD NOTIFICATION: {msg}")
        self.notifications.append(msg)

    async def execute_signal(self, strategy_name, signal, now, slippage_pct=0.02):
        logger.info(f"EXECUTING SIGNAL for strategy '{strategy_name}' at {now}")
        class MockTrade:
            def __init__(self):
                self.id = "mock-trade-123"
        trade = MockTrade()
        self.trades.append((strategy_name, signal, now, trade))
        return trade


async def main():
    logger.info("Initializing Prisma DB...")
    db = Prisma()
    await db.connect()

    try:
        # Create a mock research strategy in DB so the Engine does not skip it
        strategy_name = "ZERO_DTE_PCS_10D_5W_SPY"
        logger.info(f"Ensuring mock seed data for '{strategy_name}' exists in DB...")
        
        research_strat = await db.researchstrategy.upsert(
            where={"name": strategy_name},
            data={
                "create": {
                    "name": strategy_name,
                    "description": "Mock PCS strategy for pipeline test"
                },
                "update": {}
            }
        )
        
        account = await db.account.find_first(where={"name": strategy_name})
        if not account:
            account = await db.account.create(
                data={
                    "name": strategy_name,
                    "currentBalance": 25000.0,
                    "initialBalance": 25000.0,
                    "currency": "USD"
                }
            )

        logger.info("Initializing Engine with Mock Services...")
        config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../scripts/libs_py/strategy_engine/config.yaml"))
        engine = Engine(db, config_path)
        
        # We initialize first so all variables are populated
        await engine.initialize()
        
        # Override broker and executor with mock objects
        mock_broker = MockBrokerService()
        mock_executor = MockExecutor()
        engine.services["broker"] = mock_broker
        engine.executor = mock_executor
        
        async def mock_staleness(ticker, now, strategy_code=None):
            return False
        engine._check_index_staleness = mock_staleness
        
        # Get active strategy
        strategy = engine.active_strategies.get(strategy_name)
        if not strategy:
            logger.error(f"Strategy '{strategy_name}' not loaded in engine.")
            return

        # Prepare a mock Signal
        # SPY spot is at 500. Short Put strike is at 490, Long Put strike is at 485 (valid Bullish PCS)
        leg1 = LegSpec(
            option_type="PUT",
            side="SHORT",
            strike=490.0,
            expiry=date.today(),
            quantity=1,
            symbol="SPY260519P00490000",
            mid=1.05,
            bid=1.00,
            ask=1.10
        )
        leg2 = LegSpec(
            option_type="PUT",
            side="LONG",
            strike=485.0,
            expiry=date.today(),
            quantity=1,
            symbol="SPY260519P00485000",
            mid=0.35,
            bid=0.30,
            ask=0.40
        )
        
        mock_signal = Signal(
            research_strategy_id=research_strat.id,
            strategy_category="ZERO_DTE_PCS",
            underlying="SPY",
            legs=[leg1, leg2],
            max_risk_per_contract=430.0,
            max_capital_per_contract=500.0,
            profit_target_pct=0.50,
            stop_loss_mult=2.0,
            notes="Mock Pipeline Signal"
        )
        
        logger.info("STAGING SIGNAL TESTING...")
        tz_et = pytz.timezone("America/New_York")
        now = datetime.now(tz_et)
        
        # Inject our mock signal scan logic to strategy instance
        async def mock_scan(dt):
            return [mock_signal]
            
        strategy.scan = mock_scan
        
        # Clear any old staged signals for SPY to keep test isolated
        await db.stagedsignal.delete_many(where={"strategyName": strategy_name})
        
        # Run scan tick to stage signal
        await engine.run_scan_tick(now, cadence="index")
        
        # Query staged signal from DB
        staged_signals = await db.stagedsignal.find_many(where={"strategyName": strategy_name, "status": "PENDING"})
        assert len(staged_signals) == 1, "Failed to stage signal in DB."
        staged = staged_signals[0]
        logger.info(f"Staged signal successfully. ID: {staged.id}, Status: {staged.status}, ExecuteAfter: {staged.executeAfter}")
        
        # Check Discord staging card notification
        assert len(mock_executor.notifications) == 1, "Discord setup card not sent."
        assert "NEW SETUP STAGED" in mock_executor.notifications[0], "Discord message formatting incorrect."
        
        logger.info("TEST CASE 1: Validation passes -> Executes trade")
        # Tick the staged runner forward using execution timestamp
        # Ensure broker quote has no breaches
        mock_broker.spot = 500.0  # > short strike 490 (valid PCS)
        mock_broker.option_quotes = {
            "SPY260519P00490000": {"bid": 1.00, "ask": 1.10, "mark": 1.05},
            "SPY260519P00485000": {"bid": 0.30, "ask": 0.40, "mark": 0.35}
        }
        
        execute_time = staged.executeAfter + timedelta(seconds=1)
        await engine.run_staged_execution_tick(execute_time)
        
        staged_updated = await db.stagedsignal.find_unique(where={"id": staged.id})
        assert staged_updated.status == "EXECUTED", f"Staged signal should be EXECUTED, but is {staged_updated.status}."
        assert len(mock_executor.trades) == 1, "Failed to execute paper trade."
        logger.info("Test Case 1 passed: Valid staged signal executed successfully.")
        
        logger.info("TEST CASE 2: Underlying Strike Breach Guard -> Aborts and expires")
        # Reset staging
        await db.stagedsignal.delete_many(where={"strategyName": strategy_name})
        mock_executor.notifications.clear()
        mock_executor.trades.clear()
        
        # Stage again
        await engine.run_scan_tick(now, cadence="index")
        staged_signals = await db.stagedsignal.find_many(where={"strategyName": strategy_name, "status": "PENDING"})
        staged = staged_signals[0]
        
        # Simulate market crash below short strike (500 -> 488, short strike is 490)
        mock_broker.spot = 488.0
        
        execute_time = staged.executeAfter + timedelta(seconds=1)
        await engine.run_staged_execution_tick(execute_time)
        
        staged_updated = await db.stagedsignal.find_unique(where={"id": staged.id})
        assert staged_updated.status == "EXPIRED", f"Staged signal should be EXPIRED due to spot breach, but is {staged_updated.status}."
        assert len(mock_executor.trades) == 0, "Should not execute trade when underlying strike is breached."
        assert len(mock_executor.notifications) == 2, "Discord setup or cancel card not sent."
        assert "EXPIRED / CANCELLED" in mock_executor.notifications[1], "Discord cancellation card not sent."
        assert "breached short Put strike" in mock_executor.notifications[1], "Cancellation reason not logged in Discord card."
        logger.info("Test Case 2 passed: Underlying Strike Breach Guard triggered successfully.")

        logger.info("TEST CASE 3: Premium Deterioration Guard -> Aborts and expires")
        # Reset staging
        await db.stagedsignal.delete_many(where={"strategyName": strategy_name})
        mock_executor.notifications.clear()
        mock_executor.trades.clear()
        
        # Stage again
        await engine.run_scan_tick(now, cadence="index")
        staged_signals = await db.stagedsignal.find_many(where={"strategyName": strategy_name, "status": "PENDING"})
        staged = staged_signals[0]
        
        # Simulate premium collapse (mid price from 1.05 down to 0.50, which is >10% deterioration)
        mock_broker.spot = 500.0  # Spot fine
        mock_broker.option_quotes = {
            "SPY260519P00490000": {"bid": 0.45, "ask": 0.55, "mark": 0.50},
            "SPY260519P00485000": {"bid": 0.40, "ask": 0.44, "mark": 0.42}
        }
        
        execute_time = staged.executeAfter + timedelta(seconds=1)
        await engine.run_staged_execution_tick(execute_time)
        
        staged_updated = await db.stagedsignal.find_unique(where={"id": staged.id})
        assert staged_updated.status == "EXPIRED", f"Staged signal should be EXPIRED due to premium drop, but is {staged_updated.status}."
        assert len(mock_executor.trades) == 0, "Should not execute trade when premium deteriorated."
        assert "Credit deteriorated" in mock_executor.notifications[1], "Cancellation reason incorrect in Discord card."
        logger.info("Test Case 3 passed: Premium Deterioration Guard triggered successfully.")
        
        logger.info("ALL TEST CASES PASSED SUCCESSFULLY!")
        
    finally:
        await db.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
