import pandas as pd
import numpy as np
from typing import Dict, Any

import sys
from pathlib import Path

# Add project root to sys.path dynamically
_current_dir = Path(__file__).resolve().parent
while _current_dir.name and _current_dir.name != "scripts":
    _current_dir = _current_dir.parent
if _current_dir.name == "scripts":
    _root_dir = str(_current_dir.parent)
    if _root_dir not in sys.path:
        sys.path.insert(0, _root_dir)

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
        
        # 2. Extract necessary price columns for signal metadata
        close = data['close']
        
        raw_signals = pd.Series(0, index=data.index)
        
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
        
        # 6. Core Entry Logic
        # LONG: Short False (-1) + valid entry filters
        raw_signals[(ny1_status == -1) & valid_entry] = 1
        # SHORT: Long False (1) + valid entry filters
        raw_signals[(ny1_status == 1) & valid_entry] = -1
        
        # 7. Convert Series to Standardized Signal DataFrame (Layer 4 Schema)
        # This converts a flat Series into the Metadata-rich DF the engine expects
        entry_indices = raw_signals[raw_signals != 0].index
        if entry_indices.empty:
            return pd.DataFrame()
            
        signal_list = []
        for idx in entry_indices:
            direction = "long" if raw_signals.loc[idx] == 1 else "short"
            entry_price = close.loc[idx]
            m_dist = mid_dist.loc[idx]
            
            # Map parameters to relative targets
            # Target is the Mid point
            target = entry_price * (1 - m_dist) # Reverses the (mid-close)/close normalization
            
            # Stop is dist away
            stop = entry_price * (1 - (sl_dist * raw_signals.loc[idx]))
            
            signal_list.append({
                'signal_id': str(uuid.uuid4()) if 'uuid' in globals() else idx,
                'signal_time': idx,
                'direction': direction,
                'entry_price': entry_price,
                'stop_price': stop,
                'target1_price': target,
                'status': 'active'
            })
            
        return pd.DataFrame(signal_list)
