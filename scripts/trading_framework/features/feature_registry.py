import pandas as pd
from typing import List, Dict, Callable, Any
from scripts.trading_framework.features.indicators import (
    compute_bollinger_bands,
    compute_keltner_channels,
    compute_squeeze
)
from scripts.trading_framework.features.microstructure import (
    compute_arrival_velocity,
    compute_momentum_features
)
from scripts.trading_framework.features.volume_features import (
    compute_volume_features
)

# Layer 2: Feature Registry — The Central Nervous System for Feature Engineering.
# Maps human-readable feature names to their implementation functions.
# This prevents code duplication and allows ML models to discover features programmatically.

class FeatureRegistry:
    """
    Centralized catalog and orchestration for all strategy indicators 
    and market microstructure features.
    """
    
    def __init__(self):
        # Register standard functions
        self._registry = {
            "bollinger": compute_bollinger_bands,
            "keltner": compute_keltner_channels,
            "squeeze": compute_squeeze,
            "microstructure": compute_momentum_features,
            "velocity": compute_arrival_velocity,
            "volume": compute_volume_features
        }
        
    def compute_all(self, df: pd.DataFrame, config: Dict[str, Any] = None) -> pd.DataFrame:
        """
        Orchestrates the computation of all registered features into a single DataFrame.
        """
        config = config or {}
        
        # 1. Base Indicators
        bb = self._registry["bollinger"](df, 
                                        period=config.get('bb_period', 20), 
                                        num_std=config.get('bb_std', 2.0))
        
        kc_params = config.get('keltner', {})
        kc = self._registry["keltner"](df, 
                                      period=kc_params.get('period', 20), 
                                      atr_period=kc_params.get('atr_period', 14), 
                                      atr_mult=kc_params.get('atr_mult', 2.0))
        
        # 2. Derived Cross-features
        sqz = self._registry["squeeze"](df, bb, kc)
        
        # 3. Microstructure & Volume Dynamics
        micro = self._registry["microstructure"](df)
        vel = self._registry["velocity"](df, lookback=config.get('velocity_lookback', 10))
        vol = self._registry["volume"](df, period=config.get('volume_period', 20))
        
        # Join results
        enriched_df = pd.concat([df, bb, kc, sqz, micro, vel.rename('arrival_velocity'), vol], axis=1)
        
        # 4. Handle session and time-based context from the loader logic
        # For now, we assume these are already in df (Layer 1 output)
        
        return enriched_df

    def get_feature_list(self) -> List[str]:
        """Returns list of all possible feature keys."""
        return list(self._registry.keys())
