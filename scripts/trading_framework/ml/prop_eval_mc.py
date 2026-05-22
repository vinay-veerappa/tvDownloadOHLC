"""
DEPRECATED (ADR-021) — Do not extend or import from new code.
==============================================================
The canonical prop firm simulation implementation has moved to:
  scripts/trading_framework/ml/prop_firm_simulator.py

This file is retained only as a backward-compatibility shim for
existing tests. The `run_prop_mc_simulation` function previously
consumed per-trade % returns as if they were daily P&L, which is
methodologically incorrect. See ADR-021 for the full decision record.

Monte Carlo Simulation for Prop Firm Evaluations (Legacy).
Predicts the probability of passing an evaluation given a strategy's
daily P&L distribution and risk parameters.
"""
import numpy as np
import pandas as pd
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

def run_prop_mc_simulation(
    daily_pnl: pd.Series, 
    profit_target: float = 3000.0,
    max_drawdown: float = 2000.0,
    starting_equity: float = 50000.0,
    max_days: int = 30,
    n_sims: int = 10000
) -> Dict[str, Any]:
    """
    Simulates N evaluation attempts by sampling from the daily P&L.
    
    Returns:
        Summary statistics (Pass Rate, Avg Days to Pass, etc.)
    """
    if daily_pnl.empty:
        return {"pass_rate": 0, "msg": "No P&L data to sample from"}

    pnl_samples = daily_pnl.values
    passes = 0
    fails_dd = 0
    fails_timeout = 0
    days_to_pass = []

    # Vectorized sampling for the whole simulation batch
    # Each row is a simulation path
    all_pnl = np.random.choice(pnl_samples, size=(n_sims, max_days))
    
    for i in range(n_sims):
        equity = starting_equity
        peak = starting_equity
        passed = False
        
        for day in range(max_days):
            equity += all_pnl[i, day]
            peak = max(peak, equity)
            
            # Simple Trailing DD check (relative to peak)
            if (peak - equity) > max_drawdown:
                fails_dd += 1
                break
                
            # Profit target check
            if (equity - starting_equity) >= profit_target:
                passes += 1
                days_to_pass.append(day + 1)
                passed = True
                break
        else:
            # Reached max days without passing or failing DD
            if not passed:
                fails_timeout += 1

    pass_rate = passes / n_sims
    avg_days = np.mean(days_to_pass) if days_to_pass else 0
    
    return {
        "pass_rate": pass_rate,
        "fails_drawdown_rate": fails_dd / n_sims,
        "fails_timeout_rate": fails_timeout / n_sims,
        "avg_days_to_pass": avg_days,
        "p50_days": np.percentile(days_to_pass, 50) if days_to_pass else 0,
        "n_sims": n_sims
    }

def format_mc_report(stats: Dict[str, Any]) -> str:
    """Format MC results as a table."""
    if "pass_rate" not in stats:
        return stats.get("msg", "Error in simulation")
        
    return f"""
### Prop Firm Evaluation Simulation
| Component | Metric |
| :--- | :--- |
| **Pass Rate** | {stats['pass_rate']*100:.1f}% |
| **DD Failure Rate** | {stats['fails_drawdown_rate']*100:.1f}% |
| **Timeout Failure Rate** | {stats['fails_timeout_rate']*100:.1f}% |
| **Avg Days to Pass** | {stats['avg_days_to_pass']:.1f} days |
| **P50 Pass Speed** | {stats['p50_days']:.1f} days |
| **Confidence (Sims)** | {stats['n_sims']:,} paths |
"""
