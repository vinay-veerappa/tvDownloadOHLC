import pandas as pd
import numpy as np
from typing import Dict, Any
from scripts.trading_framework.core.base import SignalGenerator
from scripts.trading_framework.library.adapters.nqstats_adapter import NQStatsAdapter

class BoxMeanReversionSignal(SignalGenerator):
    """
    Box Mean Reversion Strategy (Using NQStats Adapter).
    Layer 4: Logic implementation.
    
    Strategy:
    1. Identify 'False Breakout' states from NQStats (LF/SF).
    2. Enter Reversion: 
       - If Long False (LF), price broke High then broke Low -> Signal SHORT (Target Mid).
       - If Short False (SF), price broke Low then broke High -> Signal LONG (Target Mid).
    3. Exit: When price touches the Session Mid-point (borrowed from Adapter).
    """
    
    def generate_signals(self, data: pd.DataFrame, config: Dict[str, Any]) -> pd.Series:
        """
        Generate signals based on institutional Box Statuses.
        """
        # 1. Borrow normalized features from the NQStats Adapter
        adapter = NQStatsAdapter()
        features = adapter.get_box_features(data)
        
        signals = pd.Series(0, index=data.index)
        
        # 2. Extract mapped statuses (LF = 1, SF = -1)
        # We look at NY1 (AM session) status as our primary driver
        # Fallback to zero if feature is not present in initial hours
        ny1_status = features.get('feat_ny1_status', pd.Series(0, index=data.index))
        
        # 3. Entry Logic
        # Signal LONG if SF (Short False - Low broken then High)
        signals[ny1_status == -1] = 1
        
        # Signal SHORT if LF (Long False - High broken then Low)
        signals[ny1_status == 1] = -1
        
        # 4. Exit Logic (Close at Mid-point touch)
        # Using the normalized % distance to mid from the adapter
        # Fallback to 1 (far from mid) if feature is missing
        mid_dist = features.get('feat_ny1_mid_dist', pd.Series(1, index=data.index))
        
        # If we are LONG and price reaches Mid (dist close to 0), flatten
        # We use a 5-tick buffer for 'real-world' touch
        buffer = 0.0001 
        signals[(signals == 1) & (mid_dist.abs() < buffer)] = 0
        signals[(signals == -1) & (mid_dist.abs() < buffer)] = 0
        
        # 5. Regime Filtering (Optional - from Layer 3)
        # If the market is in High Volatility (Regime 2), we might want to skip mean reversion.
        if config.get('filter_high_vol', False) and 'regime' in data.columns:
            signals[data['regime'] == 2] = 0
            
        return signals
