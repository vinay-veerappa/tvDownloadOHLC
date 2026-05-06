import pandas as pd
import numpy as np
import uuid
from typing import Dict, Any

from scripts.trading_framework.core.base import SignalGenerator
from scripts.libs_py.features.feature_registry import FeatureRegistry
from scripts.trading_framework.signals.signal_schema import SIGNAL_SCHEMA

class MeanReversionSignal(SignalGenerator):
    """
    Standard Strategy: Tactical Mean Reversion (Bollinger + Keltner Channels).
    Conforms to Layer 4 (v2.0 Architecture).
    """

    def __init__(self):
        self.feature_registry = FeatureRegistry()

    def generate_signals(self, data: pd.DataFrame, config: Dict[str, Any]) -> pd.DataFrame:
        """
        Standardized Signal Generation:
        1. Enriches data with Indicators via Registry.
        2. Applies Logic (Bollinger Touch).
        3. Returns Signal Schema with Target Prices (Midline).
        """
        # 1. Layer 2: Feature Engineering
        df = self.feature_registry.compute_all(data, config)
        
        # 2. Layer 4: Signal Logic
        # LONG: close <= bb_lower
        long_mask = (df['close'] <= df['bb_lower'])
        # SHORT: close >= bb_upper
        short_mask = (df['close'] >= df['bb_upper'])
        
        # 3. Build Standardized Signal DataFrame (Vectorized)
        long_sigs = df[long_mask].copy()
        long_sigs['direction'] = 'long'
        
        short_sigs = df[short_mask].copy()
        short_sigs['direction'] = 'short'
        
        combined = pd.concat([long_sigs, short_sigs]).sort_index()
        
        if combined.empty:
            return pd.DataFrame(columns=SIGNAL_SCHEMA.keys())
            
        # Map to SCHEMA
        signal_df = pd.DataFrame(index=combined.index)
        signal_df['signal_id'] = [str(uuid.uuid4())[:8] for _ in range(len(combined))]
        signal_df['signal_time'] = combined.index
        signal_df['symbol'] = config.get('ticker', 'NQ1')
        signal_df['direction'] = combined['direction']
        signal_df['signal_type'] = 'bb_touch'
        signal_df['band_type'] = 'bollinger'
        signal_df['entry_price'] = combined['close']
        signal_df['target1_price'] = combined['bb_mid']
        signal_df['target2_price'] = combined['bb_upper'].where(combined['direction']=='long', combined['bb_lower'])
        
        # Approximate ATR for stop distance
        atr = combined['bb_mid'] * combined['bb_bandwidth'] / (2 * 2.0)
        signal_df['stop_price'] = combined['bb_lower'] - (1.5 * atr)
        signal_df.loc[combined['direction']=='short', 'stop_price'] = combined['bb_upper'] + (1.5 * atr)
        
        signal_df['entry_regime'] = combined['regime'].astype(str) if 'regime' in combined.columns else 'unknown'
        signal_df['entry_regime_confidence'] = 1.0
        signal_df['entry_session'] = 'NY' # placeholder
        signal_df['entry_vix_pctile'] = 0.5
        signal_df['entry_is_macro_window'] = False
        
        return signal_df.reset_index(drop=True)
