import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
from datetime import time

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

from scripts.trading_framework.library.adapters.nqstats_adapter import NQStatsAdapter

class BoxReversionStrategy:
    """
    Box Reversion Strategy (Vectorized ADR-017).
    Identifies institutional 'False Breakout' states and targets session mid-points.
    
    Adheres to the STRATEGY_DESIGN_STANDARD.md (Zero-Loop).
    """
    
    def __init__(self, ticker: str = "NQ1"):
        self.ticker = ticker
        self.adapter = NQStatsAdapter()
        self.output_cols = ['signal_time', 'direction', 'entry_price', 'stop_price', 'target1_price']
        
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
        
        # 1. Borrow normalized features from the NQStats Adapter
        features = self.adapter.get_box_features(data)
        data = data.copy()
        
        # 2. Map necessary columns
        ny1_status = features.get('feat_ny1_status', pd.Series(0, index=data.index))
        mid_dist = features.get('feat_ny1_mid_dist', pd.Series(0, index=data.index))
        
        # 3. Dynamic Hyperparameters
        min_dist = p.get('min_dist', 0.0005)
        sl_dist = p.get('sl_dist', 0.0050)
        
        # 4. Entry Filters (Regime & Distance)
        valid_mask = pd.Series(True, index=data.index)
        
        # A. High Volatility Filter (Regime 2 = High Vol)
        if p.get('filter_high_vol', False) and 'regime' in data.columns:
            valid_mask &= (data['regime'] != 2)
            
        # B. Minimum Distance to Target Filter
        valid_mask &= (mid_dist.abs() >= min_dist)
        
        # 5. Core Entry Masks (Zero-Loop)
        # LONG: Short False (-1)
        long_mask = (ny1_status == -1) & valid_mask
        # SHORT: Long False (1)
        short_mask = (ny1_status == 1) & valid_mask
        
        # 6. Optimized Synthesis (Zero-Loop)
        data['direction'] = pd.Series(pd.NA, index=data.index, dtype='object')
        data.loc[long_mask, 'direction'] = 'long'
        data.loc[short_mask, 'direction'] = 'short'
        
        combined = data.dropna(subset=['direction']).copy()
        if combined.empty:
            return pd.DataFrame(columns=self.output_cols)
            
        # Select first signal per day
        combined['date'] = combined.index.normalize()
        first_sigs = combined.groupby('date').head(1).copy()
        
        # 7. Vectorized Price Calculation
        first_sigs['signal_time'] = first_sigs.index
        first_sigs['entry_price'] = first_sigs['close']
        
        # Target calculation (reverses mid_dist normalization)
        # mid_dist = (mid - close) / close  => mid = close * (1 + mid_dist)
        first_sigs['target1_price'] = first_sigs['close'] * (1 + mid_dist.loc[first_sigs.index])
        
        # Stop calculation
        first_sigs['stop_price'] = np.where(
            first_sigs['direction'] == 'long',
            first_sigs['entry_price'] * (1 - sl_dist),
            first_sigs['entry_price'] * (1 + sl_dist)
        )
        
        # Final Schema Formatting
        return first_sigs[self.output_cols].reset_index(drop=True)

    @staticmethod
    def get_param_grid() -> Dict[str, Any]:
        """
        Returns the standard optimization grid for Optuna.
        """
        return {
            'min_dist': ('float', 0.0001, 0.0010),
            'sl_dist': ('float', 0.0030, 0.0080),
            'filter_high_vol': ('categorical', [True, False])
        }
