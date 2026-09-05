import pandas as pd
import numpy as np
from datetime import time
from typing import Dict, List, Optional, Any

class NineThirtyStrategy:
    """
    Unified 9:30 Breakout Hunter (Vectorized).
    Implements Versions V0 (Raw), V1 (Baseline), and V2 (Optimized).
    
    Adheres to STRATEGY_WORKFLOW.md section 2 (the hunt() contract).
    """
    
    def __init__(self, variant: str = 'v2', ticker: str = "NQ1"):
        self.variant = variant
        self.ticker = ticker
        
    def hunt(self, data: pd.DataFrame, params: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
        """
        Main signal hunting method.
        
        Args:
            data: Standard OHLC DataFrame.
            params: Dictionary of overrides for optimization (Optuna).
            
        Returns:
            Signal DataFrame compliant with the Design Standard.
        """
        p = params or {}
        
        # 1. Pre-calculate 9:30 IB (30m IB equivalent to 9:30 candle)
        # For simplicity in 9:30 breakout, we use the 9:30 bar itself as the range
        df_930 = data.between_time('09:30', '09:30').copy()
        
        if df_930.empty:
            return pd.DataFrame()
            
        # 2. Vectorized Metric Calculation
        df_930['ib_high'] = df_930['high']
        df_930['ib_low'] = df_930['low']
        df_930['ib_range'] = df_930['ib_high'] - df_930['ib_low']
        
        # 3. Dynamic Thresholds (V2 Optimization)
        if self.variant == 'v2' or p.get('use_extreme_filter', False):
            df_930['range_pct'] = df_930['ib_range'] / df_930['open']
            df_930['extreme_thresh'] = df_930['range_pct'].rolling(20).quantile(p.get('extreme_q', 0.75))
        
        # 4. Filter for Valid Dates (e.g., Tuesday avoidance)
        valid_dates = df_930.index.normalize()
        if p.get('avoid_tue', False) or self.variant == 'v2':
            valid_dates = valid_dates[valid_dates.dayofweek != 1] # Skip Tuesday
            
        # 5. Signal Detection Window (9:31 to 9:35)
        # We find the FIRST 1m bar that breaks the 9:30 range
        entry_window = data.between_time('09:31', '09:35').copy()
        entry_window['date'] = entry_window.index.normalize()
        
        # Join with 9:30 levels
        entry_window = entry_window.join(df_930[['ib_high', 'ib_low', 'extreme_thresh']], on='date', rsuffix='_ref')
        
        # Filter for entry signals
        long_sigs = entry_window[entry_window['high'] > entry_window['ib_high']]
        short_sigs = entry_window[entry_window['low'] < entry_window['ib_low']]
        
        # Filter for Extreme (V2)
        if self.variant == 'v2' or p.get('use_extreme_filter', False):
           # To stay vectorized, we apply the filter to the potential signal bars
           long_sigs = long_sigs[ (long_sigs['ib_high']-long_sigs['ib_low'])/long_sigs['open'] <= long_sigs['extreme_thresh'] ]
           short_sigs = short_sigs[ (short_sigs['ib_high']-short_sigs['ib_low'])/short_sigs['open'] <= short_sigs['extreme_thresh'] ]

        # Deduplicate signals: only the FIRST break per day
        long_sigs = long_sigs.groupby('date').head(1)
        short_sigs = short_sigs.groupby('date').head(1)
        
        # 6. Schema Synthesis
        signals = []
        
        # Long Synthesis
        for _, sig in long_sigs.iterrows():
            entry_price = sig['ib_high']
            direction = 'long'
            
            # SL/TP Logic (V0/V1/V2)
            if self.variant == 'v0' or p.get('sl_mode') == 'STRUCT':
                stop_loss = sig['ib_low']
            else: # HYBRID V2
                stop_loss = max(sig['ib_low'], entry_price * (1 - p.get('sl_pct', 0.0020)))
                
            if self.variant == 'v0' or p.get('tp_mode') == 'NONE':
                target = 999999.0
            elif self.variant == 'v1' or p.get('tp_mode') == 'FIXED':
                target = entry_price * (1 + p.get('tp_pct', 0.0015))
            else: # DYNAMIC V2
                target = entry_price + (sig['ib_high'] - sig['ib_low']) * p.get('tp_mult', 0.8)
                
            signals.append({
                'signal_time': sig.name,
                'direction': direction,
                'entry_price': entry_price,
                'stop_price': stop_loss,
                'target1_price': target
            })
            
        # Short Synthesis
        for _, sig in short_sigs.iterrows():
            entry_price = sig['ib_low']
            direction = 'short'
            
            if self.variant == 'v0' or p.get('sl_mode') == 'STRUCT':
                stop_loss = sig['ib_high']
            else: # HYBRID V2
                stop_loss = min(sig['ib_high'], entry_price * (1 + p.get('sl_pct', 0.0020)))
                
            if self.variant == 'v0' or p.get('tp_mode') == 'NONE':
                target = 0.0
            elif self.variant == 'v1' or p.get('tp_mode') == 'FIXED':
                target = entry_price * (1 - p.get('tp_pct', 0.0015))
            else: # DYNAMIC V2
                target = entry_price - (sig['ib_high'] - sig['ib_low']) * p.get('tp_mult', 0.8)

            signals.append({
                'signal_time': sig.name,
                'direction': direction,
                'entry_price': entry_price,
                'stop_price': stop_loss,
                'target1_price': target
            })
            
        return pd.DataFrame(signals).sort_values('signal_time') if signals else pd.DataFrame()
