import unittest
import pandas as pd
import numpy as np
import datetime
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from scripts.trading_framework.config.config_loader import load_config
from scripts.libs.risk.session_manager import SessionRiskManager
from scripts.libs.risk.account_manager import AccountRiskManager
from scripts.libs.risk.risk_config import Signal, TradeDirection, TradeRecord, TradeStatus
from scripts.trading_framework.core.engine import BacktestEngine

class TestPhase1(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        # We need a basic config from the yaml
        cls.config = load_config("scripts/trading_framework/config/sessions.yaml")
        
    def test_config_loaded(self):
        self.assertIsNotNone(self.config)
        self.assertEqual(self.config.account_risk.starting_equity, 50000.0)
        self.assertEqual(self.config.execution.default_contracts, 1)

    def test_account_manager(self):
        am = AccountRiskManager(self.config.account_risk)
        
        # Test basic equity updates and EOD calculation
        self.assertTrue(am.can_trade_today())
        
        am.on_session_close(500.0)
        # Trailing DD is EOD
        self.assertEqual(am.state.equity, 50500.0)
        self.assertEqual(am.state.high_water_mark, 50500.0)
        
        # Take a loss
        am.on_session_close(-2200.0)
        self.assertEqual(am.state.equity, 48300.0)
        self.assertEqual(am.state.high_water_mark, 50500.0)
        
        # HWM - DD = 50500 - 2000 = 48500. Current is 48300. So we should be blown.
        self.assertTrue(am.state.is_blown)
        self.assertFalse(am.can_trade_today())

    def test_session_manager(self):
        sm = SessionRiskManager(self.config.session_risk, self.config.sessions)
        sm.on_session_open(datetime.date(2024, 1, 1))
        
        # Mock signals
        sig1 = Signal(timestamp=pd.Timestamp("2024-01-01 10:00:00", tz="US/Eastern"), symbol="MES", direction=TradeDirection.LONG, entry_price=5000, 
                      stop_price=4990, risk_points=10, risk_dollars=50, strategy_name="strat_a", context={})
        
        # Request should pass
        t_time = pd.Timestamp("2024-01-01 10:00:00", tz="US/Eastern")
        self.assertTrue(sm.request_entry(sig1, t_time))
        
        tr1 = TradeRecord(signal=sig1, status=TradeStatus.CLOSED, entry_time=t_time, entry_fill_price=5000, policy_name="test")
        sm.state.open_position = tr1
        
        # Next trade should fail (max concurrent is 1)
        sig2 = Signal(timestamp=pd.Timestamp("2024-01-01 10:01:00", tz="US/Eastern"), symbol="MES", direction=TradeDirection.LONG, entry_price=5005, 
                      stop_price=4990, risk_points=15, risk_dollars=75, strategy_name="strat_a", context={})
        self.assertFalse(sm.request_entry(sig2, pd.Timestamp("2024-01-01 10:01:00", tz="US/Eastern")))
        
        # Record trade result (profit)
        tr1.exit_time = pd.Timestamp("2024-01-01 10:30:00", tz="US/Eastern")
        tr1.realized_pnl = -500.0  # Daily max loss is 400.0! Result should halt session.
        sm.record_trade_result(tr1)
        
        # Check current state
        self.assertIsNone(sm.state.open_position)
        
        sig3 = Signal(timestamp=pd.Timestamp("2024-01-01 10:45:00", tz="US/Eastern"), symbol="MES", direction=TradeDirection.SHORT, entry_price=5000, 
                      stop_price=5010, risk_points=10, risk_dollars=50, strategy_name="strat_a", context={})
        self.assertFalse(sm.request_entry(sig3, pd.Timestamp("2024-01-01 10:45:00", tz="US/Eastern")))
        
    def test_engine_cover_the_queen(self):
        engine = BacktestEngine(self.config)
        
        # Create a simple trend day 1-minute dataframe moving straight up
        num_bars = 60
        dates = pd.date_range(start="2024-01-01 09:30:00", periods=num_bars, freq="1min", tz="US/Eastern")
        df = pd.DataFrame({
            "open": np.arange(100, 100 + num_bars),
            "high": np.arange(100, 100 + num_bars) + 0.5,
            "low": np.arange(100, 100 + num_bars) - 0.5,
            "close": np.arange(100, 100 + num_bars) + 0.25,
            "volume": [100] * num_bars
        }, index=dates)
        
        # Signal at first bar. Long at 100. Stop at 90. Risk is 10pts. CTQ policy normally targets 1R initially (110).
        sig = Signal(timestamp=dates[0], symbol="MES", direction=TradeDirection.LONG, entry_price=100.0, 
                     stop_price=90.0, risk_points=10.0, risk_dollars=50.0, strategy_name="test", context={})
        
        res = engine.run([sig], df)
        
        self.assertEqual(len(res.trades), 1)
        tr = res.trades[0]
        
        # Since it's cover the queen, we should have a partial exit at Target RR around +10 pts (price 110)
        self.assertTrue(tr.partial_exit_price is not None)
        # Entry will be 100 + slippage (0.25). Default tick size is 0.25, slippage 1 tick. Entry fill = 100.25.
        # Stop is 90. Risk is 10.25pts. Target 1 is 110.50.
        # Since the close keeps going up to ~160, we should hit target 1, and then trail out or close at EOD.
        self.assertTrue(tr.status in [TradeStatus.CLOSED, TradeStatus.PARTIAL])

if __name__ == '__main__':
    unittest.main()
