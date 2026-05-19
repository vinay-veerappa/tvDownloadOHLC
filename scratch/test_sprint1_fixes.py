import sys
import os
import asyncio
from datetime import datetime, timezone
sys.path.insert(0, r"c:\Users\vinay\tvDownloadOHLC")

from scripts.libs_py.strategy_engine.strategies.base import Strategy, StrategyParams, ManageAction
from scripts.libs_py.strategy_engine.services.leg_quote_service import TradeMtm
from dataclasses import dataclass
from typing import List

@dataclass
class MockTrade:
    direction: str
    entryPrice: float
    quantity: float

class MockStrategy(Strategy):
    async def scan(self, now): return []
    async def manage(self, trade, current_mtm, now): return ManageAction(close=False)

async def test_base_math():
    params = StrategyParams(research_strategy_id="1", name="test", category="test", underlying="SPY", account_id="1", params={})
    strat = MockStrategy(params, {})

    print("--- Testing base.py Profit Target and Stop Loss fixes ---")

    # Scenario 1: Credit Trade, Target = 50%, Entry = 1.00 ($100 per contract)
    # 2 contracts -> Quantity 2. Entry aggregate = 200.
    # Current MTM Unrealized PnL = $110. (This means cost to close is 0.45 per share, pnl = (1.00 - 0.45)*2*100 = 110)
    # per share PnL = 110 / 200 = 0.55
    # target = 50% of 1.00 = 0.50
    # Expected: Exit (0.55 >= 0.50)
    t1 = MockTrade(direction="CREDIT", entryPrice=1.00, quantity=2)
    mtm1 = TradeMtm(net_value=90.0, unrealized_pnl=110.0, leg_details={}, underlying_px=100.0)
    
    pt = await strat._check_profit_target(t1, mtm1, target_pct=0.50)
    print("Credit PT (110 PnL):", pt.reason if pt else "None", "Expected: TARGET")

    mtm2 = TradeMtm(net_value=120.0, unrealized_pnl=80.0, leg_details={}, underlying_px=100.0)
    pt = await strat._check_profit_target(t1, mtm2, target_pct=0.50)
    print("Credit PT (80 PnL):", pt.reason if pt else "None", "Expected: None")

    # Scenario 2: Credit Stop Loss, Stop = 2.0x
    # Entry = 1.00 ($100). If cost to close >= 2.00 ($200) -> STOP.
    # net_value = 400.0 for 2 contracts => 400 / 200 = 2.0 per share
    mtm3 = TradeMtm(net_value=400.0, unrealized_pnl=-200.0, leg_details={}, underlying_px=100.0)
    sl = await strat._check_stop_loss(t1, mtm3, stop_mult=2.0)
    print("Credit SL (400 Net):", sl.reason if sl else "None", "Expected: STOP")

    mtm4 = TradeMtm(net_value=300.0, unrealized_pnl=-100.0, leg_details={}, underlying_px=100.0)
    sl = await strat._check_stop_loss(t1, mtm4, stop_mult=2.0)
    print("Credit SL (300 Net):", sl.reason if sl else "None", "Expected: None")

    print("\n--- Testing Debit Trade math ---")
    # Debit trade Entry = 2.00 (Cost $200 per contract). Target = 50%.
    t2 = MockTrade(direction="DEBIT", entryPrice=2.00, quantity=3)
    # Target = 50% profit -> 1.00 profit per share.
    # PnL = 300 for 3 contracts -> 300 / 300 = 1.00 per share.
    mtm5 = TradeMtm(net_value=900.0, unrealized_pnl=300.0, leg_details={}, underlying_px=100.0)
    pt2 = await strat._check_profit_target(t2, mtm5, target_pct=0.50)
    print("Debit PT (300 PnL):", pt2.reason if pt2 else "None", "Expected: TARGET")
    
    # Stop loss for debit: stop_pct = 0.5 (lose 50% of debit paid -> net value per share drops to 1.00)
    # Net value = 300 for 3 contracts -> 1.00 per share.
    mtm6 = TradeMtm(net_value=300.0, unrealized_pnl=-300.0, leg_details={}, underlying_px=100.0)
    sl2 = await strat._check_stop_loss(t2, mtm6, stop_pct=0.5)
    print("Debit SL (300 Net):", sl2.reason if sl2 else "None", "Expected: STOP")

if __name__ == "__main__":
    asyncio.run(test_base_math())
