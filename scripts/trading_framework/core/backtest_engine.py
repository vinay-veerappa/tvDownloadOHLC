import pandas as pd
import numpy as np
import uuid
from typing import Dict, Any, List, Optional, Union
from scripts.trading_framework.core.base import BaseBacktester

class VectorizedBacktester(BaseBacktester):
    """
    High-performance Vectorized / Semi-Vectorized Backtesting Engine.
    Layer 5 of the Statistical Trading Framework.
    """
    
    def __init__(self, commission: float = 2.05, slippage_pct: float = 0.0001, account_size: float = 50000.0):
        self.commission = commission
        self.slippage_pct = slippage_pct
        self.account_size = account_size
        
        # Standard Institutional Multipliers
        self.tick_multipliers = {
            'NQ1': 20.0,
            'NQ': 20.0,
            'MNQ': 2.0,
            'ES1': 50.0,
            'ES': 50.0,
            'MES': 5.0,
            'CL': 1000.0,
            'GC': 100.0
        }

    @staticmethod
    def _standard_signal_columns() -> List[str]:
        return ['signal_time', 'direction', 'entry_price', 'stop_price', 'target1_price']

    def _normalize_standardized_signals(self, signals: pd.DataFrame) -> pd.DataFrame:
        """Defensive normalization for standardized signal frames.

        Ensures missing/invalid no-signal outputs never crash the engine and
        returns an empty canonical-schema DataFrame when input is unusable.
        """
        cols = self._standard_signal_columns()
        if signals is None or not isinstance(signals, pd.DataFrame):
            return pd.DataFrame(columns=cols)

        if signals.empty:
            if not all(c in signals.columns for c in cols):
                return pd.DataFrame(columns=cols)
            return signals[cols].copy()

        if not all(c in signals.columns for c in cols):
            return pd.DataFrame(columns=cols)

        out = signals[cols].copy()
        out['signal_time'] = pd.to_datetime(out['signal_time'], errors='coerce')
        out['direction'] = out['direction'].astype(str).str.lower()

        for c in ['entry_price', 'stop_price', 'target1_price']:
            out[c] = pd.to_numeric(out[c], errors='coerce')

        out = out[
            out['signal_time'].notna()
            & out['direction'].isin(['long', 'short'])
            & out['entry_price'].notna()
            & out['stop_price'].notna()
            & out['target1_price'].notna()
        ]
        return out
        
    def run(self, signals: Union[pd.Series, pd.DataFrame], data: pd.DataFrame, risk_params: Dict[str, Any]) -> Dict[str, Any]:
        if isinstance(signals, pd.Series):
            return self._run_raw_vectorized(signals, data, risk_params)
        elif isinstance(signals, pd.DataFrame):
            return self._run_standardized_matches(signals, data, risk_params)
        else:
            raise ValueError("Unsupported signal format. Use pd.Series or pd.DataFrame.")

    def _run_raw_vectorized(self, signals: pd.Series, data: pd.DataFrame, risk_params: Dict[str, Any]) -> Dict[str, Any]:
        execution_signals = signals.shift(1).fillna(0)
        strategy_returns = execution_signals * data['returns']
        trades = execution_signals.diff().abs()
        costs = trades * self.slippage_pct
        net_returns = strategy_returns - costs
        cum_returns = (1 + net_returns).cumprod()
        
        return {
            'total_return_%': (cum_returns.iloc[-1] - 1) * 100,
            'sharpe_ratio': self._calculate_sharpe(net_returns),
            'max_drawdown_%': self._calculate_max_drawdown(cum_returns) * 100,
            'num_trades': int(trades.sum()),
            'equity_curve': cum_returns,
            'trade_returns_pct': net_returns[execution_signals != 0]
        }

    def _run_standardized_matches(self, signals: pd.DataFrame, data: pd.DataFrame, risk_params: Dict[str, Any]) -> Dict[str, Any]:
        signals = self._normalize_standardized_signals(signals)
        if signals.empty:
            return self._null_metrics(data)

        # 1. Alignment and Pre-check
        entry_indices = data.index.get_indexer(signals['signal_time'], method='bfill')
        valid_mask = entry_indices != -1
        signals = signals[valid_mask].copy()
        entry_indices = entry_indices[valid_mask]

        if signals.empty:
            return self._null_metrics(data)

        # 2. Performance Matrix Search (Layer 5 - ADR-008)
        MAX_SEARCH = 1440 
        n_sigs = len(signals)
        n_bars = len(data)
        CHUNK_SIZE = 25000

        high_vals = data['high'].values.astype(np.float32)
        low_vals = data['low'].values.astype(np.float32)
        close_vals = data['close'].values.astype(np.float32)

        all_hit_occurred = []
        all_hit_bars = []
        all_is_sl = []
        all_mae = []
        all_mfe = []
        all_exit_closes = []

        ticker = risk_params.get('ticker', 'NQ1')

        for i in range(0, n_sigs, CHUNK_SIZE):
            c_indices = entry_indices[i : i + CHUNK_SIZE]
            c_targets = signals['target1_price'].values[i : i + CHUNK_SIZE, None].astype(np.float32)
            c_stops = signals['stop_price'].values[i : i + CHUNK_SIZE, None].astype(np.float32)
            c_is_long = (signals['direction'] == 'long').values[i : i + CHUNK_SIZE, None]
            c_entries = signals['entry_price'].values[i : i + CHUNK_SIZE, None].astype(np.float32)

            offsets = np.arange(MAX_SEARCH)
            f_indices = np.clip(c_indices[:, None] + offsets, 0, n_bars - 1)

            c_highs = high_vals[f_indices]
            c_lows = low_vals[f_indices]
            c_closes = close_vals[f_indices]

            tp_hits = np.where(c_is_long, c_highs >= c_targets, c_lows <= c_targets)
            sl_hits = np.where(c_is_long, c_lows <= c_stops, c_highs >= c_stops)

            any_hit = tp_hits | sl_hits
            c_hit_occurred = np.any(any_hit, axis=1)
            c_hit_bars = np.where(c_hit_occurred, np.argmax(any_hit, axis=1), MAX_SEARCH - 1)
            
            mask = offsets[None, :] <= c_hit_bars[:, None]
            
            if c_is_long.flatten()[0] if len(c_is_long) > 0 else True: 
                 c_max_adv = np.min(np.where(mask, c_lows, 1e9), axis=1)
                 c_max_fav = np.max(np.where(mask, c_highs, -1e9), axis=1)
                 c_mae = ((c_max_adv - c_entries.flatten()) / c_entries.flatten()) * 100
                 c_mfe = ((c_max_fav - c_entries.flatten()) / c_entries.flatten()) * 100
            else:
                 c_max_adv = np.max(np.where(mask, c_highs, -1e9), axis=1)
                 c_max_fav = np.min(np.where(mask, c_lows, 1e9), axis=1)
                 c_mae = ((c_entries.flatten() - c_max_adv) / c_entries.flatten()) * 100
                 c_mfe = ((c_entries.flatten() - c_max_fav) / c_entries.flatten()) * 100

            c_is_sl = sl_hits[np.arange(len(c_indices)), c_hit_bars]

            all_hit_occurred.append(c_hit_occurred)
            all_hit_bars.append(c_hit_bars)
            all_is_sl.append(c_is_sl)
            all_mae.append(c_mae)
            all_mfe.append(c_mfe)
            all_exit_closes.append(c_closes[np.arange(len(c_indices)), MAX_SEARCH - 1])

        if not all_hit_occurred:
            return self._null_metrics(data)

        # 3. Outcomes Concat
        hit_occurred = np.concatenate(all_hit_occurred)
        hit_bars = np.concatenate(all_hit_bars)
        is_sl = np.concatenate(all_is_sl)
        mae_vec = np.concatenate(all_mae)
        mfe_vec = np.concatenate(all_mfe)
        exit_closes = np.concatenate(all_exit_closes)

        # 4. Returns Synthesis
        entry_prices = signals['entry_price'].values
        exit_prices = np.where(is_sl, signals['stop_price'].values, signals['target1_price'].values)
        exit_prices[~hit_occurred] = exit_closes[~hit_occurred]
        
        direction_vec = np.where(signals['direction'] == 'long', 1, -1)
        trade_returns = ((exit_prices - entry_prices) / entry_prices) * direction_vec
        
        # Apply Institutional Multipliers and Costs
        multiplier = self.tick_multipliers.get(ticker, 1.0)
        trade_returns -= self.slippage_pct 

        # 5. Equity Curve Mapping
        exit_times = data.index[entry_indices + hit_bars]
        equity_returns = pd.Series(0.0, index=data.index)
        equity_returns.loc[exit_times] += trade_returns
        cum_returns = (1 + equity_returns).cumprod()

        return {
            'total_return_%': (cum_returns.iloc[-1] - 1) * 100,
            'sharpe_ratio': self._calculate_sharpe(equity_returns),
            'max_drawdown_%': self._calculate_max_drawdown(cum_returns) * 100,
            'win_rate_%': (len(trade_returns[trade_returns > 0]) / len(trade_returns)) * 100 if len(trade_returns) > 0 else 0.0,
            'avg_mae_%': mae_vec.mean() if len(mae_vec) > 0 else 0.0,
            'num_trades': n_sigs,
            'equity_curve': cum_returns,
            'trade_returns_pct': pd.Series(trade_returns, index=signals.index),
            'trades_detailed': pd.DataFrame({
                'pnl_pct': trade_returns * 100,
                'mae_pct': mae_vec,
                'mfe_pct': mfe_vec,
                'exit_time': exit_times
            }, index=signals.index)
        }

    def _null_metrics(self, data: pd.DataFrame) -> Dict[str, Any]:
        return {
            'total_return_%': 0.0, 'sharpe_ratio': 0.0, 'max_drawdown_%': 0.0,
            'num_trades': 0, 'equity_curve': pd.Series(1.0, index=data.index),
            'trade_returns_pct': pd.Series([], dtype=float),
            'trades_detailed': pd.DataFrame()
        }

    def _calculate_sharpe(self, returns: pd.Series, periods: int = 252 * 6.5 * 60) -> float:
        if returns.std() == 0: return 0.0
        return np.sqrt(periods) * returns.mean() / returns.std()
        
    def _calculate_max_drawdown(self, cum_returns: pd.Series) -> float:
        rolling_max = cum_returns.cummax()
        drawdown = (cum_returns - rolling_max) / rolling_max
        return drawdown.min()
