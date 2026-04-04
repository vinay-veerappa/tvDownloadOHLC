import pytest
import pandas as pd
import numpy as np
from scripts.trading_framework.ml.prop_eval_mc import run_prop_mc_simulation

def test_mc_guaranteed_pass():
    """Test with highly positive P&L distribution."""
    # Every day is +$500
    daily_pnl = pd.Series([500.0] * 30)
    
    # Target 3000, MaxDD 2000, Start 50000
    stats = run_prop_mc_simulation(
        daily_pnl, 
        profit_target=3000.0, 
        max_drawdown=2000.0, 
        max_days=30,
        n_sims=100
    )
    
    # Should pass in exactly 6 days (6 * 500 = 3000)
    assert stats["pass_rate"] == 1.0
    assert stats["avg_days_to_pass"] == 6.0
    assert stats["fails_drawdown_rate"] == 0.0

def test_mc_guaranteed_fail_drawdown():
    """Test with deeply negative P&L distribution."""
    # Every day is -$500
    daily_pnl = pd.Series([-500.0] * 30)
    
    stats = run_prop_mc_simulation(
        daily_pnl, 
        profit_target=3000.0, 
        max_drawdown=1000.0, # Fail in 2 days
        max_days=30,
        n_sims=100
    )
    
    assert stats["pass_rate"] == 0.0
    assert stats["fails_drawdown_rate"] == 1.0

def test_mc_timeout_failure():
    """Test with zero P&L (should never pass within max_days)."""
    daily_pnl = pd.Series([0.0] * 30)
    
    stats = run_prop_mc_simulation(
        daily_pnl, 
        profit_target=100.0, 
        max_drawdown=1000.0, 
        max_days=10,
        n_sims=100
    )
    
    assert stats["pass_rate"] == 0.0
    assert stats["fails_timeout_rate"] == 1.0

def test_mc_empty_pnl():
    """Test that engine handles empty series without crashing."""
    daily_pnl = pd.Series([])
    
    stats = run_prop_mc_simulation(daily_pnl)
    
    assert stats["pass_rate"] == 0
    assert "msg" in stats
