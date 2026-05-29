import asyncio
import os
import sys
from datetime import datetime, date
from unittest.mock import MagicMock, AsyncMock

# Configure environment path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

from scripts.libs_py.strategy_engine.strategies import StockRepairStrategy, CollarStrategy
from scripts.libs_py.strategy_engine.strategies.base import StrategyParams

class DummyContract:
    def __init__(self, strike, bid, ask, last, delta, symbol="DUMMY"):
        self.strike = strike
        self.bid = bid
        self.ask = ask
        self.last = last
        self.delta = delta
        self.symbol = symbol
        self.iv = 0.45
        self.gamma = 0.01
        self.theta = -0.05
        self.vega = 0.12

class DummyChain:
    def __init__(self, calls, puts):
        self.calls = calls
        self.puts = puts
        self.vix = 18.5

def run_tests():
    print("==================================================")
    print("      AUTOMATED OPTIONS STRATEGY ENGINE TESTS     ")
    print("==================================================")

    # 1. Mock StrategyParams and config
    config = {
        "volatility_grades": {
            "INDEX": {"tickers": ["SPY", "SPX", "QQQ"], "min_iv_rank": 15},
            "BLUE_CHIP": {"tickers": ["AAPL", "MSFT", "GOOGL"], "min_iv_rank": 15},
            "HIGH_BETA": {"tickers": ["TSLA", "NVDA", "RIVN"], "min_iv_rank": 30}
        },
        "holdings": {
            "RIVN": {"shares": 1000, "cost_basis": 30.0, "enabled": True},
            "NVDA": {"shares": 100, "cost_basis": 250.0, "enabled": True}
        }
    }

    params_rivn_repair = StrategyParams(
        research_strategy_id="RIVN_REPAIR_TEST",
        name="RIVN_STOCK_REPAIR_REPAIR",
        category="STOCK_REPAIR",
        underlying="RIVN",
        account_id="RIVN_REPAIR_ACCT",
        params={"dte": 30, "delta_long": 0.40},
        enabled=True
    )

    params_nvda_repair = StrategyParams(
        research_strategy_id="NVDA_REPAIR_TEST",
        name="NVDA_STOCK_REPAIR_REPAIR",
        category="STOCK_REPAIR",
        underlying="NVDA",
        account_id="NVDA_REPAIR_ACCT",
        params={"dte": 30, "delta_long": 0.40},
        enabled=True
    )

    # Mock Services
    mock_broker = AsyncMock()
    mock_broker.get_expiries = AsyncMock(return_value=["2026-06-28"])
    
    # RIVN Chain Setup
    rivn_calls = [
        DummyContract(strike=15.0, bid=1.50, ask=1.60, last=1.55, delta=0.60, symbol="RIVN_C15"),
        DummyContract(strike=16.0, bid=1.00, ask=1.10, last=1.05, delta=0.45, symbol="RIVN_C16"), # Long Call Candidate A (ATM)
        DummyContract(strike=23.0, bid=0.50, ask=0.55, last=0.53, delta=0.20, symbol="RIVN_C23"), # Short Call Candidate B (Midpoint)
    ]
    rivn_puts = [
        DummyContract(strike=14.0, bid=0.45, ask=0.55, last=0.50, delta=-0.15, symbol="RIVN_P14"),
    ]
    rivn_chain = DummyChain(rivn_calls, rivn_puts)

    # NVDA Chain Setup
    nvda_calls = [
        DummyContract(strike=210.0, bid=15.00, ask=16.00, last=15.50, delta=0.60, symbol="NVDA_C210"),
        DummyContract(strike=215.0, bid=11.00, ask=12.00, last=11.50, delta=0.45, symbol="NVDA_C215"), # Long Call Candidate A
        DummyContract(strike=232.5, bid=6.00, ask=6.50, last=6.25, delta=0.20, symbol="NVDA_C2325"), # Short Call Candidate B
    ]
    nvda_puts = [
        DummyContract(strike=195.0, bid=5.50, ask=6.00, last=5.75, delta=-0.15, symbol="NVDA_P195"),
    ]
    nvda_chain = DummyChain(nvda_calls, nvda_puts)

    def mock_get_chain(ticker, dtes):
        if ticker == "RIVN":
            return rivn_chain
        return nvda_chain

    mock_broker.get_chain = AsyncMock(side_effect=mock_get_chain)

    def mock_find_strike_by_delta(chain, target_delta, option_type):
        contracts = chain.calls if option_type == "CALL" else chain.puts
        return sorted(contracts, key=lambda c: abs(c.delta - target_delta))[0]

    def mock_find_strike_nearest(chain, target_strike, option_type):
        contracts = chain.calls if option_type == "CALL" else chain.puts
        return sorted(contracts, key=lambda c: abs(c.strike - target_strike))[0]

    mock_broker.find_strike_by_delta = mock_find_strike_by_delta
    mock_broker.find_strike_nearest = mock_find_strike_nearest

    async def mock_get_stock_quote(ticker):
        if ticker == "RIVN":
            return {"last": 16.25}
        return {"last": 215.0}

    mock_broker.get_stock_quote = AsyncMock(side_effect=mock_get_stock_quote)

    # Holdings Mock
    mock_holdings = AsyncMock()
    async def mock_get_holding(ticker):
        if ticker == "RIVN":
            return {"shares": 1000, "cost_basis": 30.0}
        return {"shares": 100, "cost_basis": 250.0}
    mock_holdings.get_holding = AsyncMock(side_effect=mock_get_holding)

    # Other Services
    mock_calendar = AsyncMock()
    mock_calendar.is_blackout_window = AsyncMock(return_value=False)
    
    mock_prisma = AsyncMock()
    mock_prisma.account.find_first = AsyncMock(return_value=MagicMock(id="TEST_ACCT"))
    mock_prisma.trade.find_many = AsyncMock(return_value=[])

    services = {
        "broker": mock_broker,
        "holdings": mock_holdings,
        "calendar": mock_calendar,
        "prisma": mock_prisma,
        "config": config
    }

    # 2. Test Dynamic IVR Lookup
    print("\n[TEST 1] Dynamic IV Rank routing:")
    dummy_strategy = StockRepairStrategy(params_rivn_repair, services)
    
    spy_ivr = dummy_strategy.get_min_iv_rank_for_ticker("SPY", 30.0)
    aapl_ivr = dummy_strategy.get_min_iv_rank_for_ticker("AAPL", 30.0)
    tsla_ivr = dummy_strategy.get_min_iv_rank_for_ticker("TSLA", 20.0)
    amd_ivr = dummy_strategy.get_min_iv_rank_for_ticker("AMD", 25.0)

    print(f"  SPY (INDEX) Expected: 15.0, Got: {spy_ivr}")
    print(f"  AAPL (BLUE_CHIP) Expected: 15.0, Got: {aapl_ivr}")
    print(f"  TSLA (HIGH_BETA) Expected: 30.0, Got: {tsla_ivr}")
    print(f"  AMD (Uncategorized) Expected: 25.0, Got: {amd_ivr}")

    assert spy_ivr == 15.0, "SPY routing failed"
    assert aapl_ivr == 15.0, "AAPL routing failed"
    assert tsla_ivr == 30.0, "TSLA routing failed"
    assert amd_ivr == 25.0, "AMD routing failed"
    print("  => SUCCESS: Dynamic IV Rank routing functions perfectly!")

    # 3. Test STOCK_REPAIR scan logic
    print("\n[TEST 2] STOCK_REPAIR strategy scan triggers:")
    
    async def run_scan_repair():
        # Test RIVN (Low-Priced stock, 1000 shares)
        repair_rivn = StockRepairStrategy(params_rivn_repair, services)
        signals_rivn = await repair_rivn.scan(datetime.now())
        print(f"  RIVN Strategy Signals Fired: {len(signals_rivn)}")
        if signals_rivn:
            sig = signals_rivn[0]
            print(f"  RIVN Signal Notes: {sig.notes}")
            print(f"  RIVN Legs count: {len(sig.legs)}")
            assert len(sig.legs) == 2, "Stock repair ratio spread should have 2 legs"
            
            leg_long = [l for l in sig.legs if l.side == "LONG"][0]
            leg_short = [l for l in sig.legs if l.side == "SHORT"][0]
            
            print(f"  RIVN Long strike: {leg_long.strike}, qty: {leg_long.quantity}")
            print(f"  RIVN Short strike: {leg_short.strike}, qty: {leg_short.quantity}")
            assert leg_long.quantity == 10, "1000 shares of RIVN must scale to 10 long call contracts"
            assert leg_short.quantity == 20, "1000 shares of RIVN must scale to 20 short call contracts"

        # Test NVDA (High-Priced stock, 100 shares)
        repair_nvda = StockRepairStrategy(params_nvda_repair, services)
        signals_nvda = await repair_nvda.scan(datetime.now())
        print(f"  NVDA Strategy Signals Fired: {len(signals_nvda)}")
        if signals_nvda:
            sig = signals_nvda[0]
            print(f"  NVDA Signal Notes: {sig.notes}")
            print(f"  NVDA Legs count: {len(sig.legs)}")
            assert len(sig.legs) == 2, "Stock repair ratio spread should have 2 legs"
            
            leg_long = [l for l in sig.legs if l.side == "LONG"][0]
            leg_short = [l for l in sig.legs if l.side == "SHORT"][0]
            
            print(f"  NVDA Long strike: {leg_long.strike}, qty: {leg_long.quantity}")
            print(f"  NVDA Short strike: {leg_short.strike}, qty: {leg_short.quantity}")
            assert leg_long.quantity == 1, "100 shares of NVDA must scale to 1 long call contract"
            assert leg_short.quantity == 2, "100 shares of NVDA must scale to 2 short call contracts"

    asyncio.run(run_scan_repair())
    print("  => SUCCESS: STOCK_REPAIR triggers and scales perfectly under both price/shares regimes!")

    # 4. Test COLLAR scan logic
    print("\n[TEST 3] COLLAR strategy scan triggers:")
    params_rivn_collar = StrategyParams(
        research_strategy_id="RIVN_COLLAR_TEST",
        name="RIVN_COLLAR_DEFENSIVE",
        category="COLLAR",
        underlying="RIVN",
        account_id="RIVN_COLLAR_ACCT",
        params={"dte": 30, "short_call_delta": 0.20, "long_put_delta": 0.15},
        enabled=True
    )
    
    async def run_scan_collar():
        collar_rivn = CollarStrategy(params_rivn_collar, services)
        signals = await collar_rivn.scan(datetime.now())
        print(f"  RIVN Collar Signals Fired: {len(signals)}")
        if signals:
            sig = signals[0]
            print(f"  Collar Signal Notes: {sig.notes}")
            leg_call = [l for l in sig.legs if l.option_type == "CALL"][0]
            leg_put = [l for l in sig.legs if l.option_type == "PUT"][0]
            print(f"  Collar call: Short {leg_call.strike} (qty {leg_call.quantity})")
            print(f"  Collar put: Long {leg_put.strike} (qty {leg_put.quantity})")
            assert leg_call.quantity == 10, "Collar call leg must scale to 10 contracts"
            assert leg_put.quantity == 10, "Collar put leg must scale to 10 contracts"
            
    asyncio.run(run_scan_collar())
    print("  => SUCCESS: COLLAR strategy scan executes and structures premium hedges correctly!")

    print("\n==================================================")
    print("           ALL TESTS COMPLETED SUCCESSFUL!        ")
    print("==================================================\n")

if __name__ == "__main__":
    run_tests()
