"""
IB Break Strategy with Pine Script and Confluence Alignment
Supports multi-session setups, advanced bias confluence, and three plays.
Vectorized and ADR-017 compliant.
"""

import pandas as pd
import numpy as np
from datetime import time, datetime, timedelta
from typing import Dict, List, Optional, Any
from scripts.libs_py.nqstats.ib import calculate_ib_statistics, get_time_mask

class IBBreakStrategy:
    """Initial Balance Break Strategy - Unified Python/Pine Version"""
    
    def __init__(
        self,
        ticker: str = "NQ1",
        session_choice: str = "NY AM IB",
        ib_duration_minutes: int = 60,
        entry_variant: str = 'play1',  # 'play1' (Breakout), 'play2' (Retest), 'play3' (Fade)
        breakout_confirmation_type: str = 'touch',  # 'touch', '1m_close', '5m_close'
        min_ib_range_pct: float = 0.3,
        max_ib_range_pct: float = 2.0,
        stop_loss_type: str = 'ib_opposite',
        take_profit_r_multiple: float = 2.0,
        p1TgtExt: float = 1.0,
        p2TgtExt: float = 0.5,
        p3OvershootExt: float = 0.25,
        p3StopExt: float = 0.5
    ):
        self.ticker = ticker
        self.session_choice = session_choice
        self.ib_duration_minutes = ib_duration_minutes
        self.entry_variant = entry_variant
        self.breakout_confirmation_type = breakout_confirmation_type
        self.min_ib_range_pct = min_ib_range_pct
        self.max_ib_range_pct = max_ib_range_pct
        self.stop_loss_type = stop_loss_type
        self.take_profit_r_multiple = take_profit_r_multiple
        self.p1TgtExt = p1TgtExt
        self.p2TgtExt = p2TgtExt
        self.p3OvershootExt = p3OvershootExt
        self.p3StopExt = p3StopExt
        
        self.output_cols = [
            'signal_time', 'direction', 'entry_price', 'stop_price', 
            'target1_price', 'ib_range_pct', 'expected_break', 'entry_type'
        ]

    def hunt(self, data: pd.DataFrame, params: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
        """Vectorized signal hunting following ADR-017 (Zero Loops)."""
        p = params or {}
        session = p.get('session_choice', self.session_choice)
        entry_var = p.get('entry_variant', self.entry_variant)
        confirm_type = p.get('breakout_confirmation_type', self.breakout_confirmation_type)
        min_range = p.get('min_ib_range_pct', self.min_ib_range_pct)
        max_range = p.get('max_ib_range_pct', self.max_ib_range_pct)
        tp_r = p.get('take_profit_r_multiple', self.take_profit_r_multiple)
        
        # 1. Compute IB stats & advanced biases via ib.py
        df = calculate_ib_statistics(data, session_choice=session)
        
        # Retrieve session parameters
        from scripts.libs_py.nqstats.ib import SESSION_CONFIGS
        cfg = SESSION_CONFIGS[session]
        ib_end, out_end = cfg["ib_end"], cfg["out_end"]
        
        # 2. Setup Gating Masks
        bar_times = df.index.time
        in_out = get_time_mask(bar_times, ib_end, out_end)
        
        df['ib_range_pct'] = (df['ib_range'] / df['ib_low']) * 100
        valid_range_mask = (df['ib_range_pct'] >= min_range) & (df['ib_range_pct'] <= max_range)
        
        # 3. Entry Signal Logic
        df['is_breakout_long'] = False
        df['is_breakout_short'] = False
        
        # Determine breakout conditions based on confirmation type
        if confirm_type == 'touch':
            df['is_breakout_long'] = df['high'] > df['ib_high']
            df['is_breakout_short'] = df['low'] < df['ib_low']
            df['entry_price_raw'] = np.where(df['is_breakout_long'], df['ib_high'], df['ib_low'])
        elif confirm_type == '1m_close':
            df['is_breakout_long'] = df['close'] > df['ib_high']
            df['is_breakout_short'] = df['close'] < df['ib_low']
            df['entry_price_raw'] = df['close']
        elif confirm_type == '5m_close':
            is_5m_close = (df.index.minute % 5 == 4)
            df['is_breakout_long'] = is_5m_close & (df['close'] > df['ib_high'])
            df['is_breakout_short'] = is_5m_close & (df['close'] < df['ib_low'])
            df['entry_price_raw'] = df['close']
            
        # Cumulative breakout status running through the outcome window
        df['has_broken_long'] = (df['is_breakout_long'] & in_out).groupby(df['logical_date']).cummax()
        df['has_broken_short'] = (df['is_breakout_short'] & in_out).groupby(df['logical_date']).cummax()
        
        # Find the exact timestamp of the first breakout per day
        df['breakout_long_time'] = np.where(df['is_breakout_long'] & in_out, df['bar_idx'], 999999)
        df['breakout_short_time'] = np.where(df['is_breakout_short'] & in_out, df['bar_idx'], 999999)
        
        daily_first_long_idx = df.groupby('logical_date')['breakout_long_time'].min()
        daily_first_short_idx = df.groupby('logical_date')['breakout_short_time'].min()
        
        df = df.join(daily_first_long_idx, on='logical_date', rsuffix='_first_long')
        df = df.join(daily_first_short_idx, on='logical_date', rsuffix='_first_short')
        
        # 4. Generate Signal Triggers
        df['is_trigger'] = False
        df['sig_direction'] = np.nan
        df['sig_direction'] = df['sig_direction'].astype(object)
        df['sig_entry'] = np.nan
        df['sig_stop'] = np.nan
        df['sig_target'] = np.nan
        
        if entry_var == 'play1':
            # Play 1: Breakout in bias direction
            # If dominant bias is BULLISH, trigger long on first high break.
            # If dominant bias is BEARISH, trigger short on first low break.
            long_trigger = (df['bar_idx'] == df['breakout_long_time_first_long']) & (df['dominant_bias'] == 'BULLISH')
            short_trigger = (df['bar_idx'] == df['breakout_short_time_first_short']) & (df['dominant_bias'] == 'BEARISH')
            
            df.loc[long_trigger & in_out & valid_range_mask, 'is_trigger'] = True
            df.loc[long_trigger & in_out & valid_range_mask, 'sig_direction'] = 'long'
            df.loc[long_trigger & in_out & valid_range_mask, 'sig_entry'] = df['entry_price_raw']
            
            df.loc[short_trigger & in_out & valid_range_mask, 'is_trigger'] = True
            df.loc[short_trigger & in_out & valid_range_mask, 'sig_direction'] = 'short'
            df.loc[short_trigger & in_out & valid_range_mask, 'sig_entry'] = df['entry_price_raw']
            
            # Stop is opposite boundary
            df['sig_stop'] = np.where(df['sig_direction'] == 'long', df['ib_low'], df['ib_high'])
            
            # Target is p1TgtExt range beyond entry
            risk = (df['sig_entry'] - df['sig_stop']).abs()
            df['sig_target'] = np.where(df['sig_direction'] == 'long', df['sig_entry'] + (risk * self.p1TgtExt), df['sig_entry'] - (risk * self.p1TgtExt))
            entry_type = 'PLAY1_BREAKOUT'
            
        elif entry_var == 'play2':
            # Play 2: Retest-continuation
            # Triggered on first touch of midpoint AFTER a breakout has occurred on that side.
            df['retest_long_eligible'] = (df['bar_idx'] > df['breakout_long_time_first_long']) & (df['low'] <= df['ib_mid'])
            df['retest_short_eligible'] = (df['bar_idx'] > df['breakout_short_time_first_short']) & (df['high'] >= df['ib_mid'])
            
            df['retest_long_time'] = np.where(df['retest_long_eligible'] & in_out, df['bar_idx'], 999999)
            df['retest_short_time'] = np.where(df['retest_short_eligible'] & in_out, df['bar_idx'], 999999)
            
            daily_first_retest_long = df.groupby('logical_date')['retest_long_time'].min()
            daily_first_retest_short = df.groupby('logical_date')['retest_short_time'].min()
            
            df = df.join(daily_first_retest_long, on='logical_date', rsuffix='_first_retest_long')
            df = df.join(daily_first_retest_short, on='logical_date', rsuffix='_first_retest_short')
            
            long_trigger = (df['bar_idx'] == df['retest_long_time_first_retest_long']) & (df['dominant_bias'] == 'BULLISH')
            short_trigger = (df['bar_idx'] == df['retest_short_time_first_retest_short']) & (df['dominant_bias'] == 'BEARISH')
            
            df.loc[long_trigger & in_out & valid_range_mask, 'is_trigger'] = True
            df.loc[long_trigger & in_out & valid_range_mask, 'sig_direction'] = 'long'
            df.loc[long_trigger & in_out & valid_range_mask, 'sig_entry'] = df['ib_mid']
            
            df.loc[short_trigger & in_out & valid_range_mask, 'is_trigger'] = True
            df.loc[short_trigger & in_out & valid_range_mask, 'sig_direction'] = 'short'
            df.loc[short_trigger & in_out & valid_range_mask, 'sig_entry'] = df['ib_mid']
            
            # Stop is opposite boundary
            df['sig_stop'] = np.where(df['sig_direction'] == 'long', df['ib_low'], df['ib_high'])
            
            # Target is p2TgtExt range beyond the high/low breakout point
            df['sig_target'] = np.where(
                df['sig_direction'] == 'long',
                df['ib_high'] + (df['ib_range'] * self.p2TgtExt),
                df['ib_low'] - (df['ib_range'] * self.p2TgtExt)
            )
            entry_type = 'PLAY2_RETEST'
            
        elif entry_var == 'play3':
            # Play 3: Fade-to-mid
            # Enter fade at boundary after price overshoots boundary by p3OvershootExt
            df['os_long_val'] = df['ib_high'] + (df['ib_range'] * self.p3OvershootExt)
            df['os_short_val'] = df['ib_low'] - (df['ib_range'] * self.p3OvershootExt)
            
            df['os_long_eligible'] = (df['high'] >= df['os_long_val'])
            df['os_short_eligible'] = (df['low'] <= df['os_short_val'])
            
            df['os_long_time'] = np.where(df['os_long_eligible'] & in_out, df['bar_idx'], 999999)
            df['os_short_time'] = np.where(df['os_short_eligible'] & in_out, df['bar_idx'], 999999)
            
            daily_first_os_long = df.groupby('logical_date')['os_long_time'].min()
            daily_first_os_short = df.groupby('logical_date')['os_short_time'].min()
            
            df = df.join(daily_first_os_long, on='logical_date', rsuffix='_first_os_long')
            df = df.join(daily_first_os_short, on='logical_date', rsuffix='_first_os_short')
            
            # Fade direction is opposite: if overshoot is High, we sell short. If overshoot is Low, we buy long.
            long_trigger = (df['bar_idx'] == df['os_short_time_first_os_short'])
            short_trigger = (df['bar_idx'] == df['os_long_time_first_os_long'])
            
            df.loc[long_trigger & in_out & valid_range_mask, 'is_trigger'] = True
            df.loc[long_trigger & in_out & valid_range_mask, 'sig_direction'] = 'long'
            df.loc[long_trigger & in_out & valid_range_mask, 'sig_entry'] = df['ib_low']
            
            df.loc[short_trigger & in_out & valid_range_mask, 'is_trigger'] = True
            df.loc[short_trigger & in_out & valid_range_mask, 'sig_direction'] = 'short'
            df.loc[short_trigger & in_out & valid_range_mask, 'sig_entry'] = df['ib_high']
            
            # Target is the midpoint
            df['sig_target'] = df['ib_mid']
            
            # Stop is the configured stop extension (further out)
            df['sig_stop'] = np.where(
                df['sig_direction'] == 'long',
                df['ib_low'] - (df['ib_range'] * self.p3StopExt),
                df['ib_high'] + (df['ib_range'] * self.p3StopExt)
            )
            entry_type = 'PLAY3_FADE'
            
        else:
            raise ValueError(f"Unknown entry variant: {entry_var}")
            
        signals = df[df['is_trigger']].copy()
        if signals.empty:
            return pd.DataFrame(columns=self.output_cols)
            
        signals['signal_time'] = signals.index
        signals['direction'] = signals['sig_direction']
        signals['entry_price'] = signals['sig_entry']
        signals['stop_price'] = signals['sig_stop']
        signals['target1_price'] = signals['sig_target']
        signals['expected_break'] = signals['dominant_bias']
        signals['entry_type'] = entry_type
        
        # Canonical schema return
        return signals[self.output_cols].reset_index(drop=True)
