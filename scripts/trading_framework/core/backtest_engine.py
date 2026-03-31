import pandas as pd
import numpy as np
import uuid
from typing import Dict, Any, List, Optional, Union
from scripts.trading_framework.core.base import BaseBacktester

class VectorizedBacktester(BaseBacktester):
    """
    High-performance Vectorized / Semi-Vectorized Backtesting Engine.
    Layer 5 of the Statistical Trading Framework.
    
    Compatible with:
    1. Raw pd.Series [-1, 0, 1] — Simple mode.
    2. pd.DataFrame [SIGNAL_SCHEMA] — Standardized Layer 4 mode.
    """
    
    def __init__(self, commission: float = 2.01, slippage_pct: float = 0.0001, account_size: float = 50000.0):
        self.commission = commission
        self.slippage_pct = slippage_pct
        self.account_size = account_size
        
    def run(self, signals: Union[pd.Series, pd.DataFrame], data: pd.DataFrame, risk_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main runner: delegates based on signal format.
        """
        if isinstance(signals, pd.Series):
            return self._run_raw_vectorized(signals, data, risk_params)
        elif isinstance(signals, pd.DataFrame):
            return self._run_standardized_matches(signals, data, risk_params)
        else:
            raise ValueError("Unsupported signal format. Use pd.Series or pd.DataFrame (schema-compliant).")

    def _run_raw_vectorized(self, signals: pd.Series, data: pd.DataFrame, risk_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Original simple vectorized mode (Series-based).
        """
        execution_signals = signals.shift(1).fillna(0)
        strategy_returns = execution_signals * data['returns']
        trades = execution_signals.diff().abs()
        
        # Costs and returns
        costs = trades * self.slippage_pct + (trades > 0) * (self.commission / (data['close'] * 100))
        net_returns = strategy_returns - costs
        cum_returns = (1 + net_returns).cumprod()
        
        # Metrics
        sharpe = self._calculate_sharpe(net_returns)
        max_drawdown = self._calculate_max_drawdown(cum_returns)
        
        # Trade logs
        trade_blocks = (execution_signals.diff() != 0).cumsum()
        active_returns = net_returns[execution_signals != 0]
        active_blocks = trade_blocks[execution_signals != 0]
        trade_returns_pct = active_returns.groupby(active_blocks).apply(lambda x: (1 + x).prod() - 1)
        
        return {
            'total_return_%': (cum_returns.iloc[-1] - 1) * 100,
            'sharpe_ratio': sharpe,
            'max_drawdown_%': max_drawdown * 100,
            'num_trades': int(trades.sum()),
            'equity_curve': cum_returns,
            'trade_returns_pct': trade_returns_pct
        }

    def _run_standardized_matches(self, signals: pd.DataFrame, data: pd.DataFrame, risk_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        High-Performance Logic: Vectorized Matrix Search for SL/TP Hits.
        Fulfills ADR-008 performance goals while maintaining 1m accuracy.
        """
        if signals.empty:
            return {
                'total_return_%': 0.0, 'sharpe_ratio': 0.0, 'max_drawdown_%': 0.0,
                'num_trades': 0, 'equity_curve': pd.Series([1.0], index=[data.index[0]]),
                'trade_returns_pct': pd.Series([], dtype=float)
            }

        # 1. Pre-align signal indices to data index (Vectorized Location)
        # Handle timezone naivety (Assuming Western)
        entry_indices = data.index.get_indexer(signals['signal_time'], method='bfill')
        valid_mask = entry_indices != -1
        signals = signals[valid_mask].copy()
        entry_indices = entry_indices[valid_mask]

        # 2. Extract price matrices (N_signals x MAX_WINDOW) 
        # Using a fixed 24-hour search window (1440 bars) to keep memory constant
        MAX_SEARCH = 1440 
        n_sigs = len(signals)
        n_bars = len(data)

        # Vectorized Index Map: Create a 2D matrix of indices representing future bars
        offsets = np.arange(MAX_SEARCH)
        future_indices = entry_indices[:, None] + offsets  # (N_sigs, 1440)
        future_indices = np.clip(future_indices, 0, n_bars - 1)

        # Sample Prices (Efficiently vectorized)
        highs = data['high'].values[future_indices]
        lows = data['low'].values[future_indices]
        closes = data['close'].values[future_indices]

        targets = signals['target1_price'].values[:, None]
        stops = signals['stop_price'].values[:, None]
        is_long = (signals['direction'] == 'long').values[:, None]

        # 3. Compute HIT MATRICES
        # Long Logic: High >= Target OR Low <= Stop
        # Short Logic: Low <= Target OR High >= Stop
        tp_hits = np.where(is_long, highs >= targets, lows <= targets)
        sl_hits = np.where(is_long, lows <= stops, highs >= stops)

        # 4. Resolve Outcomes (Strict Priority: Stop Loss wins if same bar)
        # Find first bar where ANY hit occurs
        any_hit = tp_hits | sl_hits
        
        # argmax returns the first index of Truth
        hit_occurred = np.any(any_hit, axis=1)
        hit_bars = np.argmax(any_hit, axis=1)
        
        # Outcome Logic:
        # If both hit in the same bar, SL wins (Conservative)
        is_sl = sl_hits[np.arange(n_sigs), hit_bars] # True if SL hit at the hit_bar
        
        # 5. Compute Returns
        entry_prices = signals['entry_price'].values
        exit_prices = np.where(is_sl, stops.flatten(), targets.flatten())
        
        # If no hit occurred in the 24h window, use final Close (Timeout)
        no_hit_indices = ~hit_occurred
        exit_prices[no_hit_indices] = closes[no_hit_indices, -1]
        
        direction_vec = np.where(is_long.flatten(), 1, -1)
        
        # Base trade returns
        trade_returns = ((exit_prices - entry_prices) / entry_prices) * direction_vec
        
        # Apply Slippage and Commissions (Vectorized)
        trade_returns -= (self.slippage_pct + (self.commission / (entry_prices * 100)))

        # 6. Map to Equity Curve
        trade_results = pd.DataFrame({
            'return_pct': trade_returns,
            'exit_time_idx': np.where(hit_occurred, hit_bars, MAX_SEARCH - 1)
        }, index=signals.index)
        
        # Resolve exit timestamps
        exit_times = data.index[entry_indices + trade_results['exit_time_idx']]
        trade_results['exit_time'] = exit_times

        # Synthesize Daily Performance
        equity_returns = pd.Series(0.0, index=data.index)
        # Note: In overlapping trades, we aggregate returns on the exit bar
        equity_returns.loc[trade_results['exit_time']] = trade_results['return_pct'].values
        
        cum_returns = (1 + equity_returns).cumprod()

        return {
            'total_return_%': (cum_returns.iloc[-1] - 1) * 100,
            'sharpe_ratio': self._calculate_sharpe(equity_returns),
            'max_drawdown_%': self._calculate_max_drawdown(cum_returns) * 100,
            'num_trades': n_sigs,
            'equity_curve': cum_returns,
            'trade_returns_pct': trade_results['return_pct']
        }

    def collect_ml_labels(self, signals: pd.DataFrame, data: pd.DataFrame) -> pd.DataFrame:
        """
        Special helper for training Layer 8 (Signal Classifier).
        Iterates signals, matches them to future prices, and returns a Label DataFrame.
        """
        if signals.empty: return pd.DataFrame()
        
        labels = []
        for _, sig in signals.iterrows():
            if sig['signal_time'] not in data.index: continue
            start_idx = data.index.get_loc(sig['signal_time'])
            
            # Look forward up to 1000 bars
            future = data.iloc[start_idx+1 : start_idx + 1000]
            if future.empty: continue
            
            target = sig['target1_price']
            stop = sig['stop_price']
            direction = 1 if sig['direction'] == 'long' else -1
            
            if direction == 1:
                tp_hit = future['high'] >= target
                sl_hit = future['low'] <= stop
            else:
                tp_hit = future['low'] <= target
                sl_hit = future['high'] >= stop
                
            hit_mask = tp_hit | sl_hit
            if not hit_mask.any():
                label = 0
            else:
                exit_idx = hit_mask.idxmax()
                label = 1 if tp_hit.loc[exit_idx] else 0
                
            labels.append({
                "signal_time": sig['signal_time'],
                "label": int(label)
            })
            
        return pd.DataFrame(labels).set_index("signal_time")

    def _calculate_sharpe(self, returns: pd.Series, periods: int = 252 * 6.5 * 60) -> float:
        if returns.std() == 0: return 0.0
        return np.sqrt(periods) * returns.mean() / returns.std()
        
    def _calculate_max_drawdown(self, cum_returns: pd.Series) -> float:
        rolling_max = cum_returns.cummax()
        drawdown = (cum_returns - rolling_max) / rolling_max
        return drawdown.min()
