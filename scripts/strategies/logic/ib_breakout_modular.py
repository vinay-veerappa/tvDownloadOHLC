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

from scripts.trading_framework.core.modular_signal import ModularSignalGenerator
from scripts.trading_framework.strategy_lib.filters import KillZoneFilter
from scripts.trading_framework.library.adapters.nqstats_adapter import NQStatsAdapter

class IBBreakoutModular(ModularSignalGenerator):
    """
    Initial Balance (IB) Breakout Strategy (Modular Vectorized).
    Layer 4: Logic implementation following ADR-017.
    """
    
    def __init__(self):
        super().__init__(strategy_name="Initial Balance Breakout")
        # 1. Plug in Standard ICT Kill Zone (Morning RTH Window)
        self.add_filter(KillZoneFilter(9, 30, 11, 0)) # 9:30 AM - 11:00 AM ET

    def get_raw_trigger(self, data: pd.DataFrame, config: Dict[str, Any]) -> pd.Series:
        """
        Detect 1m closes crossing the IB High/Low.
        """
        # 1. Load IB levels from NQStats Adapter
        # Note: In a production environment, this would be pre-calculated in Layer 2.
        # But here we fetch it on-the-fly for flexibility.
        adapter = NQStatsAdapter()
        stats = adapter.get_box_features(data)
        
        # 2. Extract Data Standard (Institutional standard is 1m)
        close = data['close']
        
        # 3. Handle IB Calculation (Vectorized across daily groups)
        # Assuming RTH starts at 09:30 ET
        # We need ib_high and ib_low series aligned to 1m
        # For simplicity, we can use the 'feat_ny1_mid_dist' if NY1 is our IB definition
        # But for 'Pure IB', we'll calculate it if it's not in the adapter.
        
        # Logic: If close crosses the 1h high of the session
        # We'll use the 'feat_ny1_status' which internally tracks the box.
        # But let's be explicit for "IB Breakout":
        ib_duration = config.get('ib_duration', 60) # Default 60m
        
        # Create Daily Groups for IB calculation
        days = data.index.normalize()
        
        # Vectorized Highs for the first N minutes of each day
        def _get_ib_levels(df):
            # 09:30 - 09:30+duration
            rth_start = df.index[0].replace(hour=9, minute=30, second=0)
            ib_end = rth_start + pd.Timedelta(minutes=ib_duration)
            ib_mask = (df.index >= rth_start) & (df.index < ib_end)
            if not ib_mask.any(): return pd.Series({'h': np.nan, 'l': np.nan})
            return pd.Series({'h': df.loc[ib_mask, 'high'].max(), 'l': df.loc[ib_mask, 'low'].min()})

        # Calculate IB levels per day and broadcast back to 1m timeline
        daily_ib = data.groupby(days).apply(_get_ib_levels)
        ib_high = daily_ib['h'].reindex(days).values
        ib_low = daily_ib['l'].reindex(days).values
        
        raw_signals = pd.Series(0, index=data.index)
        
        # Trigger Condition: Close crosses above/below IB
        # BULLISH (1): Cross ABOVE IB High
        raw_signals[(close > ib_high) & (close.shift(1) <= ib_high)] = 1
        # BEARISH (-1): Cross BELOW IB Low
        raw_signals[(close < ib_low) & (close.shift(1) >= ib_low)] = -1
        
        return raw_signals

    def calculate_risk_levels(self, data: pd.DataFrame, signals: pd.Series, config: Dict[str, Any]) -> pd.DataFrame:
        """
        Layer 4c: High-fidelity stop and target mapping.
        """
        entry_price = data['close']
        rr = config.get('target_rr', 2.0)
        
        # Risk Strategy: Stop at IB Opposite or Fixed Points
        # Let's use technical stops (IB Opposite)
        # But we need IB low for long and IB high for short.
        # Repeating the IB calculation here (or we could cache it)
        days = data.index.normalize()
        ib_duration = config.get('ib_duration', 60)
        
        def _get_ib_levels(df):
            rth_start = df.index[0].replace(hour=9, minute=30, second=0)
            ib_end = rth_start + pd.Timedelta(minutes=ib_duration)
            ib_mask = (df.index >= rth_start) & (df.index < ib_end)
            if not ib_mask.any(): return pd.Series({'h': np.nan, 'l': np.nan})
            return pd.Series({'h': df.loc[ib_mask, 'high'].max(), 'l': df.loc[ib_mask, 'low'].min()})

        daily_ib = data.groupby(days).apply(_get_ib_levels)
        ib_high = daily_ib['h'].reindex(days).values
        ib_low = daily_ib['l'].reindex(days).values
        
        # LONG signals (1) -> Stop at ib_low
        # SHORT signals (-1) -> Stop at ib_high
        stop_price = pd.Series(np.nan, index=data.index)
        stop_price[signals == 1] = ib_low[signals == 1]
        stop_price[signals == -1] = ib_high[signals == -1]
        
        # Calculate Target based on RR
        risk_dist = (entry_price - stop_price).abs()
        target_price = pd.Series(np.nan, index=data.index)
        target_price[signals == 1] = entry_price + (risk_dist * rr)
        target_price[signals == -1] = entry_price - (risk_dist * rr)
        
        return pd.DataFrame({
            'entry_price': entry_price,
            'stop_price': stop_price,
            'target1_price': target_price
        })

    def get_param_grid(self) -> Dict[str, Any]:
        """DNA Definition for the Research Hub."""
        return {
            'ib_duration': [15, 30, 45, 60],
            'target_rr': [1.5, 2.0, 2.5, 3.0],
            'filter_news': [True, False],
            'filter_regime': [True, False]
        }
