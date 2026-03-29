import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional
from scripts.trading_framework.core.base import BaseBacktester

class VectorizedBacktester(BaseBacktester):
    """
    High-performance Vectorized Backtesting Engine.
    Layer 5 of the Statistical Trading Framework.
    
    This engine assumes fixed entry at 'next open' and exit at 'next close' 
    or specific time-based triggers. For complex intra-bar logic (SL/TP),
    refer to the Event-driven engine.
    """
    
    def __init__(self, commission: float = 2.01, slippage_pct: float = 0.0001):
        self.commission = commission
        self.slippage_pct = slippage_pct
        
    def run(self, signals: pd.Series, data: pd.DataFrame, risk_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute vectorized returns calculation.
        
        Args:
            signals: pd.Series of [-1, 0, 1] aligned with data index.
            data: OHLCV DataFrame (must contain 'returns' from Layer 1 loader).
            risk_params: Dictionary containing 'leverage', 'fixed_size', etc.
            
        Returns:
            Dict containing performance metrics.
        """
        # Ensure signals are shifted by 1 to avoid lookahead bias (trade next bar)
        # Entry is open of bar T+1, exit is close of bar T+1
        execution_signals = signals.shift(1).fillna(0)
        
        # Calculate raw returns (borrowed returns from loader.py)
        strategy_returns = execution_signals * data['returns']
        
        # Apply costs (commission + slippage) only on signal changes (trades)
        trades = execution_signals.diff().abs()
        # For simplicity in vectorized mode, we estimate impact per trade
        costs = trades * self.slippage_pct + (trades > 0) * (self.commission / (data['close'] * 100)) # Simple cost proxy
        
        net_returns = strategy_returns - costs
        
        # Cumulative performance
        cum_returns = (1 + net_returns).cumprod()
        
        # Performance Metrics (ADR-002 %-based)
        sharpe = self._calculate_sharpe(net_returns)
        max_drawdown = self._calculate_max_drawdown(cum_returns)
        
        return {
            'total_return_%': (cum_returns.iloc[-1] - 1) * 100,
            'sharpe_ratio': sharpe,
            'max_drawdown_%': max_drawdown * 100,
            'num_trades': int(trades.sum()),
            'equity_curve': cum_returns
        }
        
    def _calculate_sharpe(self, returns: pd.Series, periods: int = 252 * 6.5 * 60) -> float:
        """Annualized Sharpe Ratio (assuming 1m data during RTH)."""
        if returns.std() == 0:
            return 0.0
        return np.sqrt(periods) * returns.mean() / returns.std()
        
    def _calculate_max_drawdown(self, cum_returns: pd.Series) -> float:
        """Max Drawdown calculation from cumulative returns."""
        rolling_max = cum_returns.cummax()
        drawdown = (cum_returns - rolling_max) / rolling_max
        return drawdown.min()
