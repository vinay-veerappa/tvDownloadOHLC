import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
from datetime import time

from scripts.trading_framework.reporting.decision_log import GateRecorder

class MeanReversionStrategy:
    """
    Tactical Mean Reversion Strategy (Vectorized ADR-017).
    Uses Bollinger Bands to identify overextended conditions.
    
    Adheres to STRATEGY_WORKFLOW.md section 2 (the hunt() contract, Zero-Loop).
    """
    
    def __init__(self, ticker: str = "NQ1"):
        self.ticker = ticker
        self.output_cols = ['signal_time', 'direction', 'entry_price', 'stop_price', 'target1_price']
        # Set by hunt(). The reporting layer picks this up if present, so
        # instrumenting a hunter does not change the hunt() signature -- see
        # STRATEGY_WORKFLOW.md section 5.1. None means "not instrumented",
        # which the report states rather than treating as "no rejections".
        self.last_decisions: Optional[pd.DataFrame] = None
        
    def hunt(self, data: pd.DataFrame, params: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
        """
        Main signal hunting method (Zero-Loop).
        
        Args:
            data: Standard OHLC DataFrame.
            params: Dictionary of overrides for optimization (Optuna).
            
        Returns:
            Signal DataFrame compliant with the Design Standard.
        """
        p = params or {}
        
        # 1. Hyperparameters
        period = p.get('bb_period', 20)
        std_dev = p.get('bb_std', 2.0)
        atr_period = p.get('atr_period', 14)
        sl_atr_mult = p.get('sl_atr_mult', 1.5)
        
        # 2. Vectorized Indicators (Layer 2)
        data = data.copy()
        
        # Bollinger Bands
        data['bb_mid'] = data['close'].rolling(window=period).mean()
        data['bb_std'] = data['close'].rolling(window=period).std()
        data['bb_upper'] = data['bb_mid'] + (data['bb_std'] * std_dev)
        data['bb_lower'] = data['bb_mid'] - (data['bb_std'] * std_dev)
        
        # ATR for Stop Loss
        high_low = data['high'] - data['low']
        high_close = (data['high'] - data['close'].shift()).abs()
        low_close = (data['low'] - data['close'].shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        data['atr'] = tr.rolling(window=atr_period).mean()
        
        # 3. Core Entry Logic (Zero-Loop)
        # LONG: close <= bb_lower
        long_mask = (data['close'] <= data['bb_lower'])
        # SHORT: close >= bb_upper
        short_mask = (data['close'] >= data['bb_upper'])
        
        # 4. Optimized Synthesis (Zero-Loop)
        data['direction'] = pd.Series(pd.NA, index=data.index, dtype='object')
        data.loc[long_mask, 'direction'] = 'long'
        data.loc[short_mask, 'direction'] = 'short'
        
        combined = data.dropna(subset=['direction']).copy()
        if combined.empty:
            return pd.DataFrame(columns=self.output_cols)
            
        # Select first signal per day
        combined['date'] = combined.index.normalize()
        first_sigs = combined.groupby('date').head(1).copy()

        # 4b. Decision log (section 5.1). This strategy has ONE gate, and saying
        # so is the point: the C# bot paired with it (BBMRReversionBot) gates on
        # RSI, ADX, squeeze, IB compression, lunch, MACD and Kaufman ER, so the
        # two rosters do not overlap and a trade-set recall between them is not
        # interpretable. That is visible in one diff and invisible in a metrics
        # table.
        #
        # `first_signal_of_day` is ALSO the real trade cap: `head(1)` is 1/day,
        # while sessions.yaml says 3 and the bot allows 99. Three answers.
        is_first = pd.Series(False, index=data.index)
        is_first.loc[first_sigs.index] = True
        band = np.where(long_mask, data['bb_lower'], data['bb_upper'])
        self.last_decisions = (
            GateRecorder(data.index, run_id="", strategy="mean_reversion")
            .trigger(long_mask, "long")
            .trigger(short_mask, "short")
            # A magnitude, not a criterion: on a bar that triggered because the
            # close is outside the band, "the close is outside the band" cannot
            # fail. Recorded with measure() so it stays out of the roster and
            # still reaches the winner/loser comparison.
            .measure("band_excursion_atr",
                     (data['close'] - band).abs() / data['atr'])
            .gate("first_signal_of_day", is_first)
            .to_frame(signal_prefix="mr_")
        )
        
        # 5. Vectorized Price Calculation
        first_sigs['signal_time'] = first_sigs.index
        first_sigs['entry_price'] = first_sigs['close']
        first_sigs['target1_price'] = first_sigs['bb_mid']
        
        # Stop calculation based on ATR-normalized distance
        first_sigs['stop_price'] = np.where(
            first_sigs['direction'] == 'long',
            first_sigs['bb_lower'] - (first_sigs['atr'] * sl_atr_mult),
            first_sigs['bb_upper'] + (first_sigs['atr'] * sl_atr_mult)
        )
        
        # Final Schema Formatting
        return first_sigs[self.output_cols].reset_index(drop=True)

    @staticmethod
    def get_param_grid() -> Dict[str, Any]:
        """
        Returns the standard optimization grid for Optuna.
        """
        return {
            'bb_period': ('int', 10, 50),
            'bb_std': ('float', 1.5, 3.0),
            'sl_atr_mult': ('float', 1.0, 3.0)
        }
