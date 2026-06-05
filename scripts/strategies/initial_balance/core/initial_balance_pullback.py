import pandas as pd
import numpy as np
from datetime import time, datetime, timedelta
from typing import Dict, List, Optional, Any
from scripts.utils.vectorized_indicators import VectorizedIndicators

class IBPullbackStrategy:
    """
    Unified IB Pullback Strategy (Vectorized & ADR-017 Compliant).
    Supports RTH, Globex, and Tokyo session windows with duration variants (30m, 45m, 60m).
    Offers both Pre-Break and Post-Break entry variants, multiple stop losses,
    and secondary bias confirmation via 5m FVG and Inversion FVGs.
    """
    
    def __init__(
        self,
        ticker: str = "NQ1",
        session_preset: str = "RTH",
        ib_duration_min: int = 45,
        entry_variant: str = "post_break",
        pullback_level: str = "fib_382",
        stop_loss_type: str = "ib_opposite",
        bias_source: str = "ib_close",
        tp_r_mult: float = 1.0,
        fvg_start_time: Optional[time] = None,
        fvg_end_time: Optional[time] = None
    ):
        self.ticker = ticker
        self.session_preset = session_preset
        self.ib_duration_min = ib_duration_min
        self.entry_variant = entry_variant
        self.pullback_level = pullback_level
        self.stop_loss_type = stop_loss_type
        self.bias_source = bias_source
        self.tp_r_mult = tp_r_mult
        self.fvg_start_time_override = fvg_start_time
        self.fvg_end_time_override = fvg_end_time
        
        self.output_cols = ['signal_time', 'direction', 'entry_price', 'stop_price', 'target1_price']

    def hunt(self, data: pd.DataFrame, params: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
        """
        Main signal hunting method (Zero-Loop Vectorized).
        """
        p = params or {}
        session = p.get('session_preset', self.session_preset)
        ib_dur = int(p.get('ib_duration_min', self.ib_duration_min))
        entry_var = p.get('entry_variant', self.entry_variant)
        pullback_lvl = p.get('pullback_level', self.pullback_level)
        sl_type = p.get('stop_loss_type', self.stop_loss_type)
        bias_src = p.get('bias_source', self.bias_source)
        tp_mult = float(p.get('tp_r_mult', self.tp_r_mult))
        
        df = data.copy()
        
        # 1. Resolve Session Windows & Dynamic Trade Exit Times
        if session == 'RTH':
            ib_start = time(9, 30)
            fvg_start = time(10, 0)
            fvg_end = time(11, 0)
            entry_end = time(15, 30) # RTH ends before 16:00 close
        elif session == 'Globex':
            ib_start = time(18, 0)
            fvg_start = time(19, 0)
            fvg_end = time(20, 0)
            entry_end = time(6, 0)   # Globex trading ends at 6:00 AM next morning
        elif session == 'Tokyo':
            ib_start = time(19, 0)
            fvg_start = time(20, 0)
            fvg_end = time(21, 0)
            entry_end = time(2, 0)   # Tokyo session ends at 2:00 AM next morning
        else:
            raise ValueError(f"Unknown session preset: {session}")
            
        # Optional custom FVG overrides
        if self.fvg_start_time_override is not None:
            fvg_start = self.fvg_start_time_override
        if self.fvg_end_time_override is not None:
            fvg_end = self.fvg_end_time_override
            
        ib_end_dt = datetime.combine(datetime.min, ib_start) + timedelta(minutes=ib_dur)
        ib_end = ib_end_dt.time()
        
        # 2. Date/Trading Day Normalization (Handles overnight sessions crossing midnight)
        if ib_start > ib_end: # crosses midnight
            df['trading_date'] = np.where(
                df.index.time >= ib_start,
                df.index.normalize() + pd.Timedelta(days=1),
                df.index.normalize()
            )
        else:
            # For Globex/Tokyo, even if IB start is 18:00/19:00 and ends 18:45/19:45, it still crosses midnight for the full session trading day
            if session in ['Globex', 'Tokyo']:
                df['trading_date'] = np.where(
                    df.index.time >= ib_start,
                    df.index.normalize() + pd.Timedelta(days=1),
                    df.index.normalize()
                )
            else:
                df['trading_date'] = df.index.normalize()
            
        # 3. Calculate IB range high/low for each trading day
        # For Globex/Tokyo, the IB range window is within the same calendar day, but we group by 'trading_date'
        ib_mask = (df.index.time >= ib_start) & (df.index.time <= ib_end)
            
        ib_data = df[ib_mask]
        if ib_data.empty:
            return pd.DataFrame(columns=self.output_cols)
            
        daily_ib_high = ib_data.groupby('trading_date')['high'].max()
        daily_ib_low = ib_data.groupby('trading_date')['low'].min()
        daily_ib_close = ib_data.groupby('trading_date')['close'].last()
        
        # Map back to main dataframe
        df['ib_high'] = df['trading_date'].map(daily_ib_high)
        df['ib_low'] = df['trading_date'].map(daily_ib_low)
        df['ib_close'] = df['trading_date'].map(daily_ib_close)
        
        df['ib_range'] = df['ib_high'] - df['ib_low']
        
        # 4. Determine Primary IB Bias
        df['ib_pos'] = (df['ib_close'] - df['ib_low']) / df['ib_range']
        df['ib_bias'] = np.where(df['ib_pos'] >= 0.50, 'long', 'short')
        
        # Calculate High-Low Sequence Bias (formed last logic)
        df['bar_idx'] = np.arange(len(df))
        df['ib_high_match_idx'] = np.where(ib_mask & (df['high'] == df['ib_high']), df['bar_idx'], -1)
        df['ib_low_match_idx'] = np.where(ib_mask & (df['low'] == df['ib_low']), df['bar_idx'], -1)
        
        daily_high_idx = df.groupby('trading_date')['ib_high_match_idx'].max()
        daily_low_idx = df.groupby('trading_date')['ib_low_match_idx'].max()
        
        df['ib_high_idx'] = df['trading_date'].map(daily_high_idx)
        df['ib_low_idx'] = df['trading_date'].map(daily_low_idx)
        
        df['sequence_bias'] = np.where(
            df['ib_high_idx'] > df['ib_low_idx'], 'long',
            np.where(df['ib_high_idx'] < df['ib_low_idx'], 'short', 'neutral')
        )
        
        # 5. Determine Secondary 10-11 AM FVG/Inversion Bias
        # Standard FVG calculation (vectorized)
        fvg_df = VectorizedIndicators.find_fvgs(df)
        df = pd.concat([df, fvg_df], axis=1)
        
        # Filter for the FVG window
        fvg_window_mask = (df.index.time >= fvg_start) & (df.index.time <= fvg_end)
            
        fvg_window_data = df[fvg_window_mask]
        
        # Get FVG direction: 1 = bullish, -1 = bearish
        daily_fvg_type = fvg_window_data.groupby('trading_date')['fvg_type'].first()
        df['daily_fvg_type'] = df['trading_date'].map(daily_fvg_type).fillna(0)
        
        # Assign FVG bias
        df['fvg_bias'] = np.where(df['daily_fvg_type'] == 1, 'long', 
                                  np.where(df['daily_fvg_type'] == -1, 'short', 'neutral'))
                                  
        # FVG Inversion check (vectorized)
        # Check for inversion
        daily_fvg_top = fvg_window_data[fvg_window_data['fvg_type'] != 0].groupby('trading_date')['fvg_top'].first()
        daily_fvg_bottom = fvg_window_data[fvg_window_data['fvg_type'] != 0].groupby('trading_date')['fvg_bottom'].first()
        
        df['daily_fvg_top'] = df['trading_date'].map(daily_fvg_top)
        df['daily_fvg_bottom'] = df['trading_date'].map(daily_fvg_bottom)
        
        df['is_bull_inverted'] = (df['close'] < df['daily_fvg_bottom']) & (df['daily_fvg_type'] == 1)
        df['is_bear_inverted'] = (df['close'] > df['daily_fvg_top']) & (df['daily_fvg_type'] == -1)
        
        # Cumulative max of inversion per day
        df['has_inverted_bull'] = df['is_bull_inverted'].groupby(df['trading_date']).cummax()
        df['has_inverted_bear'] = df['is_bear_inverted'].groupby(df['trading_date']).cummax()
        
        # FVG Inversion Bias: if standard FVG is inverted, flip bias
        df['fvg_inversion_bias'] = df['fvg_bias']
        df.loc[df['has_inverted_bull'] == 1, 'fvg_inversion_bias'] = 'short'
        df.loc[df['has_inverted_bear'] == 1, 'fvg_inversion_bias'] = 'long'
        
        # 6. Synthesize Unified Bias
        if bias_src == 'ib_close':
            df['bias'] = df['ib_bias']
        elif bias_src == 'sequence':
            df['bias'] = df['sequence_bias']
        elif bias_src == 'fvg':
            df['bias'] = df['fvg_bias']
        elif bias_src == 'fvg_inversion':
            df['bias'] = df['fvg_inversion_bias']
        elif bias_src == 'confluence':
            df['bias'] = np.where(df['ib_bias'] == df['fvg_bias'], df['ib_bias'], 'neutral')
        else:
            df['bias'] = df['ib_bias']
            
        # 7. Pullback Entry Levels
        if pullback_lvl == 'fib_382':
            df['entry_long'] = df['ib_high'] - (0.382 * df['ib_range'])
            df['entry_short'] = df['ib_low'] + (0.382 * df['ib_range'])
        elif pullback_lvl == 'fib_50':
            df['entry_long'] = df['ib_high'] - (0.50 * df['ib_range'])
            df['entry_short'] = df['ib_low'] + (0.50 * df['ib_range'])
        elif pullback_lvl == 'fib_618':
            df['entry_long'] = df['ib_high'] - (0.618 * df['ib_range'])
            df['entry_short'] = df['ib_low'] + (0.618 * df['ib_range'])
        elif pullback_lvl == 'q_25':
            df['entry_long'] = df['ib_high'] - (0.25 * df['ib_range'])
            df['entry_short'] = df['ib_low'] + (0.25 * df['ib_range'])
        elif pullback_lvl == 'q_75':
            df['entry_long'] = df['ib_high'] - (0.75 * df['ib_range'])
            df['entry_short'] = df['ib_low'] + (0.75 * df['ib_range'])
        elif pullback_lvl == 'ib_edge':
            df['entry_long'] = df['ib_high']
            df['entry_short'] = df['ib_low']
        else:
            raise ValueError(f"Unknown pullback level: {pullback_lvl}")
            
        # 8. Entry Windows & Session Filters (Supports overnight cross-midnight windows)
        if ib_end > entry_end:
            # Over midnight: e.g. starts at 18:30 (ib_end) and goes until 6:00 (entry_end)
            entry_window = (df.index.time > ib_end) | (df.index.time <= entry_end)
        else:
            # RTH: starts at 10:15 and goes until 15:30
            entry_window = (df.index.time > ib_end) & (df.index.time <= entry_end)
            
        # 9. Entry Variant Signal Triggers
        # Breakout status
        df['has_broken_high'] = (df['high'] > df['ib_high']).groupby(df['trading_date']).cummax()
        df['has_broken_low'] = (df['low'] < df['ib_low']).groupby(df['trading_date']).cummax()
        
        if entry_var == 'pre_break':
            long_trigger = (~df['has_broken_high']) & (df['low'] <= df['entry_long'])
            short_trigger = (~df['has_broken_low']) & (df['high'] >= df['entry_short'])
        elif entry_var == 'post_break':
            long_trigger = df['has_broken_high'] & (df['low'] <= df['entry_long'])
            short_trigger = df['has_broken_low'] & (df['high'] >= df['entry_short'])
        else:
            raise ValueError(f"Unknown entry variant: {entry_var}")
            
        # Construct Signal DF
        df['direction'] = np.nan
        df['direction'] = df['direction'].astype(object)
        df.loc[long_trigger & entry_window & (df['bias'] == 'long'), 'direction'] = 'long'
        df.loc[short_trigger & entry_window & (df['bias'] == 'short'), 'direction'] = 'short'
        
        signals = df[df['direction'].notnull()].copy()
        if signals.empty:
            return pd.DataFrame(columns=self.output_cols)
            
        # Select first signal per trading day
        signals = signals.groupby('trading_date').head(1).copy()
        
        # 10. Synthesize Entries, Stops & Take Profits
        signals['signal_time'] = signals.index
        signals['entry_price'] = np.where(signals['direction'] == 'long', signals['entry_long'], signals['entry_short'])
        
        # Stop Loss
        if sl_type == 'ib_opposite':
            signals['stop_price'] = np.where(signals['direction'] == 'long', signals['ib_low'], signals['ib_high'])
        elif sl_type == 'ib_edge':
            signals['stop_price'] = np.where(
                signals['direction'] == 'long',
                signals['entry_price'] - (0.05 * signals['ib_range']),
                signals['entry_price'] + (0.05 * signals['ib_range'])
            )
        elif sl_type == 'fixed_pct':
            signals['stop_price'] = np.where(
                signals['direction'] == 'long',
                signals['entry_price'] * 0.9975,
                signals['entry_price'] * 1.0025
            )
        else:
            signals['stop_price'] = np.where(signals['direction'] == 'long', signals['ib_low'], signals['ib_high'])
            
        # Risk & Take Profit (0.5R + 1.0R TPs, trailing)
        risk = (signals['entry_price'] - signals['stop_price']).abs()
        signals['target1_price'] = np.where(
            signals['direction'] == 'long',
            signals['entry_price'] + (risk * tp_mult),
            signals['entry_price'] - (risk * tp_mult)
        )
        
        return signals[self.output_cols].reset_index(drop=True)

    @staticmethod
    def get_param_grid() -> Dict[str, Any]:
        """Optuna Hyperparameter Grid compliance (ADR-017)"""
        return {
            'session_preset': ('categorical', ['RTH', 'Globex', 'Tokyo']),
            'ib_duration_min': ('categorical', [30, 45, 60]),
            'entry_variant': ('categorical', ['pre_break', 'post_break']),
            'pullback_level': ('categorical', ['fib_382', 'fib_50', 'fib_618', 'q_25', 'q_75', 'ib_edge']),
            'stop_loss_type': ('categorical', ['ib_opposite', 'ib_edge', 'fixed_pct']),
            'bias_source': ('categorical', ['ib_close', 'fvg', 'fvg_inversion', 'confluence']),
            'tp_r_mult': ('float', 0.5, 3.0)
        }
