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
        
        # 3. Dynamic Hyperparameters
        min_dist = config.get('min_dist', 0.0005)    # Min distance required to enter
        tp_buffer = config.get('tp_buffer', 0.0001)  # Take Profit (distance inside mid)
        sl_dist = config.get('sl_dist', 0.0050)      # Stop Loss (distance outside mid)
        
        # 4. Entry Filters (Regime & Distance)
        valid_entry = pd.Series(True, index=data.index)
        
        # A. High Volatility Filter
        if config.get('filter_high_vol', False) and 'regime' in data.columns:
            valid_entry &= (data['regime'] != 2)
            
        # B. Trend Sequence Filter (Skip if overnight was pure trend)
        if config.get('filter_trend_sequence', False):
            trend_up = (features['feat_asia_status'] == 2) & (features['feat_london_status'] == 2)
            trend_down = (features['feat_asia_status'] == -2) & (features['feat_london_status'] == -2)
            valid_entry &= ~(trend_up | trend_down)
            
        # C. Minimum Distance to Target Filter (Avoid tiny EV trades)
        mid_dist = features.get('feat_ny1_mid_dist', pd.Series(1, index=data.index))
        valid_entry &= (mid_dist.abs() >= min_dist)
        
        # D. London Breakout Requirement
        if config.get('require_london_breakout', False):
            valid_entry &= (features['feat_london_broken'] == 1)

        # E. Institutional News Filter (ADR-007)
        if 'sec_to_news' in data.columns:
            # 1. Block Entry if News is Imminent (60 min window)
            valid_entry &= (data['sec_to_news'] > 3600)
            
            # 2. Forced Exit for Existing Positions (15 min safety window)
            # We flatten signals if we are too close to the news bar
            imminent_news = (data['sec_to_news'] <= 900)
            # Note: We apply this after initial signal generation below
        
        # 5. Core Entry Logic
        ny1_status = features.get('feat_ny1_status', pd.Series(0, index=data.index))
        # LONG: Short False (-1) + valid entry filters
        signals[(ny1_status == -1) & valid_entry] = 1
        # SHORT: Long False (1) + valid entry filters
        signals[(ny1_status == 1) & valid_entry] = -1
        
        # 6. Core Exit Logic (SL, TP, & News)
        # Flatten if price touches Mid (Take Profit)
        signals[(signals != 0) & (mid_dist.abs() <= tp_buffer)] = 0
        
        # Flatten if price blasts away from Mid uncontrollably (Stop Loss)
        signals[(signals != 0) & (mid_dist.abs() >= sl_dist)] = 0
        
        # Flatten for Imminent High Impact News (Institutional Safety)
        if 'sec_to_news' in data.columns:
            signals[(signals != 0) & (data['sec_to_news'] <= 900)] = 0

        # Note: In a fully continuous live market, we block re-entry by session ID
        # but for vectorized approximation this strictly trims exposure distributions
        return signals
