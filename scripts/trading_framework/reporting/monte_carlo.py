import numpy as np
import pandas as pd
from typing import Dict, Any

class MonteCarloSimulator:
    """
    Layer 8: Monte Carlo Resampling Engine
    Shuffles trade sequences to discover absolute worst-case drawdowns 
    and losing streak clusters that were masked by the actual historical timeline.
    """
    
    def __init__(self, iterations: int = 10000, account_size: float = 50000.0, risk_per_trade: float = 500.0):
        self.iterations = iterations
        self.account_size = account_size
        self.risk_per_trade = risk_per_trade
        self.risk_pct = risk_per_trade / account_size
        
    def simulate(self, trade_returns_pct: pd.Series) -> Dict[str, Any]:
        """
        Runs Monte Carlo simulation by shuffling the actual trade returns.
        We track:
        1. Max Drawdown (95% and 99% confidence intervals)
        2. Max Consecutive Losing Trades (95% and 99% confidence intervals)
        3. Worst DRR (Drawdown Risk Rating)
        """
        # Drop zero-return trades if any
        trades = trade_returns_pct[trade_returns_pct != 0].dropna().values
        n_trades = len(trades)
        
        if n_trades < 5:
            return {"Error": "Not enough trades for Monte Carlo simulation"}
            
        # Convert % returns to absolute dollar returns based on account size
        trades_dollars = trades * self.account_size
        
        # Output arrays
        max_drawdowns_pct = np.zeros(self.iterations)
        max_losing_streaks = np.zeros(self.iterations)
        
        for i in range(self.iterations):
            # Shuffle trades with replacement for bootstrapping
            simulated_trades = np.random.choice(trades_dollars, size=n_trades, replace=True)
            
            # Simulated equity curve
            equity = self.account_size + np.cumsum(simulated_trades)
            
            # Drawdown Calculation (avoiding negative running highs by using starting account)
            equity_with_start = np.insert(equity, 0, self.account_size)
            rolling_max = np.maximum.accumulate(equity_with_start)
            
            # Calculate drawdown from peak
            with np.errstate(divide='ignore', invalid='ignore'):
                drawdowns_pct = (rolling_max - equity_with_start) / rolling_max
                drawdowns_pct = np.nan_to_num(drawdowns_pct)
                
            max_drawdowns_pct[i] = np.max(drawdowns_pct)
            
            # Max Losing Streak Calculation
            is_loss = simulated_trades < 0
            pad = np.concatenate([[False], is_loss, [False]])
            edges = np.diff(pad.astype(int))
            starts = np.where(edges == 1)[0]
            ends = np.where(edges == -1)[0]
            if len(starts) > 0:
                max_streak = np.max(ends - starts)
            else:
                max_streak = 0
            max_losing_streaks[i] = max_streak

        mdd_95 = np.percentile(max_drawdowns_pct, 95)
        mdd_99 = np.percentile(max_drawdowns_pct, 99)
        
        drr_95 = (mdd_95 / self.risk_pct)
        drr_99 = (mdd_99 / self.risk_pct)

        return {
            "Iterations": self.iterations,
            "MDD_95%": f"{mdd_95*100:.2f}%",
            "MDD_99%": f"{mdd_99*100:.2f}%",
            "MaxStreak_95%": int(np.percentile(max_losing_streaks, 95)),
            "MaxStreak_99%": int(np.percentile(max_losing_streaks, 99)),
            "DRR_95%": f"{drr_95:.2f}",
            "DRR_99%": f"{drr_99:.2f}",
        }
    
    def print_report(self, metrics: Dict[str, Any], title: str = "Monte Carlo Simulation (Worst-Case)"):
        print(f"\n{'='*50}\n{title.upper().center(50)}\n{'='*50}")
        if "Error" in metrics:
            print(metrics["Error"])
        else:
            for k, v in metrics.items():
                print(f"{k.ljust(25)}: {v}")
        print("="*50 + "\n")
