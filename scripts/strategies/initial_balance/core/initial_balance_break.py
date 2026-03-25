"""
Initial Balance Break Strategy with ICT Concepts

This strategy combines:
1. Initial Balance (IB) breakout logic with multiple timeframes (15/30/45/60 min)
2. ICT concepts for refined entry timing:
   - Fair Value Gaps (FVG) for pullback entries
   - Order Blocks for support/resistance
   - Liquidity sweeps before reversals
   - Kill Zones for optimal entry timing

ICT Integration:
- Use FVGs formed after IB break for pullback entries
- Identify Order Blocks within IB range for better stops
- Look for liquidity grabs (stop hunts) before true breakout
- Align entries with ICT Kill Zones (8:30-11:00, 13:30-16:00 ET)
"""

import pandas as pd
import numpy as np
from datetime import time
from typing import Dict, List, Optional
from backtest_engine import BacktestEngine


class IBBreakStrategy:
    """Initial Balance Break Strategy with ICT entry refinement"""
    
    def __init__(
        self,
        engine: BacktestEngine,
        ib_duration_minutes: int = 60,
        entry_variant: str = 'breakout',  # 'breakout', 'pullback', 'confirmation'
        use_ict_fvg: bool = True,
        use_ict_killzones: bool = True,
        min_ib_range_pct: float = 0.3,
        max_ib_range_pct: float = 2.0,
        stop_loss_type: str = 'ib_opposite',  # 'ib_opposite', 'fixed_pct', 'order_block'
        take_profit_r_multiple: float = 2.0,
        entry_window_end: time = time(14, 0)  # 2:00 PM ET
    ):
        """
        Initialize IB Break Strategy
        
        Args:
            engine: BacktestEngine instance
            ib_duration_minutes: IB duration (15, 30, 45, 60)
            entry_variant: Entry method ('breakout', 'pullback', 'confirmation')
            use_ict_fvg: Use Fair Value Gaps for pullback entries
            use_ict_killzones: Only enter during ICT kill zones
            min_ib_range_pct: Minimum IB range (% of open)
            max_ib_range_pct: Maximum IB range (% of open)
            stop_loss_type: Stop loss method
            take_profit_r_multiple: R-multiple for take profit
            entry_window_end: Latest time to enter trades
        """
        self.engine = engine
        self.ib_duration_minutes = ib_duration_minutes
        self.entry_variant = entry_variant
        self.use_ict_fvg = use_ict_fvg
        self.use_ict_killzones = use_ict_killzones
        self.min_ib_range_pct = min_ib_range_pct
        self.max_ib_range_pct = max_ib_range_pct
        self.stop_loss_type = stop_loss_type
        self.take_profit_r_multiple = take_profit_r_multiple
        self.entry_window_end = entry_window_end
        
        # ICT Kill Zones (ET)
        self.morning_killzone = (time(8, 30), time(11, 0))
        self.afternoon_killzone = (time(13, 30), time(16, 0))
        
        # Track IB data per day
        self.current_ib: Optional[Dict] = None
        self.ib_broken: bool = False
        self.break_time: Optional[pd.Timestamp] = None
        self.break_side: Optional[str] = None
        
        # ICT structures
        self.fvgs: List[Dict] = []  # Fair Value Gaps
        self.order_blocks: List[Dict] = []  # Order Blocks
    
    def is_in_killzone(self, current_time: time) -> bool:
        """Check if current time is within ICT kill zone"""
        if not self.use_ict_killzones:
            return True
        
        return (
            (self.morning_killzone[0] <= current_time <= self.morning_killzone[1]) or
            (self.afternoon_killzone[0] <= current_time <= self.afternoon_killzone[1])
        )
    
    def detect_fvg(self, bars: pd.DataFrame, index: int) -> Optional[Dict]:
        """
        Detect Fair Value Gap (FVG)
        
        FVG occurs when:
        - Bullish FVG: bar[i-1].low > bar[i+1].high (gap up)
        - Bearish FVG: bar[i-1].high < bar[i+1].low (gap down)
        
        Returns FVG dict or None
        """
        if index < 1 or index >= len(bars) - 1:
            return None
        
        prev_bar = bars.iloc[index - 1]
        curr_bar = bars.iloc[index]
        next_bar = bars.iloc[index + 1]
        
        # Bullish FVG (gap up)
        if prev_bar['low'] > next_bar['high']:
            return {
                'type': 'BULLISH',
                'top': prev_bar['low'],
                'bottom': next_bar['high'],
                'time': curr_bar.name,
                'filled': False
            }
        
        # Bearish FVG (gap down)
        if prev_bar['high'] < next_bar['low']:
            return {
                'type': 'BEARISH',
                'top': next_bar['low'],
                'bottom': prev_bar['high'],
                'time': curr_bar.name,
                'filled': False
            }
        
        return None
    
    def detect_order_block(self, bars: pd.DataFrame, index: int) -> Optional[Dict]:
        """
        Detect Order Block (OB)
        
        OB is the last opposite-colored candle before a strong move:
        - Bullish OB: Last red candle before strong green move
        - Bearish OB: Last green candle before strong red move
        
        Returns OB dict or None
        """
        if index < 2:
            return None
        
        curr_bar = bars.iloc[index]
        prev_bar = bars.iloc[index - 1]
        prev_prev_bar = bars.iloc[index - 2]
        
        # Strong bullish move (current bar)
        if curr_bar['close'] > curr_bar['open']:
            body_size = curr_bar['close'] - curr_bar['open']
            prev_body_size = abs(prev_bar['close'] - prev_bar['open'])
            
            # Strong move (2x previous candle)
            if body_size > 2 * prev_body_size and prev_bar['close'] < prev_bar['open']:
                return {
                    'type': 'BULLISH',
                    'high': prev_bar['high'],
                    'low': prev_bar['low'],
                    'time': prev_bar.name
                }
        
        # Strong bearish move
        if curr_bar['close'] < curr_bar['open']:
            body_size = curr_bar['open'] - curr_bar['close']
            prev_body_size = abs(prev_bar['close'] - prev_bar['open'])
            
            if body_size > 2 * prev_body_size and prev_bar['close'] > prev_bar['open']:
                return {
                    'type': 'BEARISH',
                    'high': prev_bar['high'],
                    'low': prev_bar['low'],
                    'time': prev_bar.name
                }
        
        return None
    
    def check_fvg_fill(self, bar: pd.Series) -> Optional[Dict]:
        """Check if price has filled any open FVGs (pullback opportunity)"""
        for fvg in self.fvgs:
            if fvg['filled']:
                continue
            
            # Bullish FVG filled (price pulled back into gap)
            if fvg['type'] == 'BULLISH' and bar['low'] <= fvg['top']:
                fvg['filled'] = True
                return fvg
            
            # Bearish FVG filled
            if fvg['type'] == 'BEARISH' and bar['high'] >= fvg['bottom']:
                fvg['filled'] = True
                return fvg
        
        return None
    
    def calculate_stop_loss(self, entry_price: float, direction: str) -> float:
        """Calculate stop loss based on strategy settings"""
        if self.stop_loss_type == 'ib_opposite':
            # Stop at opposite side of IB
            if direction == 'LONG':
                return self.current_ib['ib_low']
            else:
                return self.current_ib['ib_high']
        
        elif self.stop_loss_type == 'fixed_pct':
            # Fixed 0.5% stop
            if direction == 'LONG':
                return entry_price * 0.995
            else:
                return entry_price * 1.005
        
        elif self.stop_loss_type == 'order_block':
            # Use nearest order block
            if len(self.order_blocks) > 0:
                ob = self.order_blocks[-1]
                if direction == 'LONG':
                    return ob['low']
                else:
                    return ob['high']
            else:
                # Fallback to IB opposite
                return self.calculate_stop_loss(entry_price, direction)
        
        return entry_price
    
    def calculate_take_profit(self, entry_price: float, stop_loss: float, direction: str) -> float:
        """Calculate take profit based on R-multiple"""
        risk = abs(entry_price - stop_loss)
        reward = risk * self.take_profit_r_multiple
        
        if direction == 'LONG':
            return entry_price + reward
        else:
            return entry_price - reward
    
    def should_enter_breakout(self, bar: pd.Series) -> Optional[Dict]:
        """Check if should enter on IB breakout (Variant 1)"""
        if self.ib_broken or self.current_ib is None:
            return None
        
        # Check if in entry window
        if bar.name.time() > self.entry_window_end:
            return None
        
        # Check if in kill zone
        if not self.is_in_killzone(bar.name.time()):
            return None
        
        # Check for breakout
        expected_break = self.current_ib['expected_break']
        
        # Long entry (high break expected)
        if expected_break == 'HIGH' and bar['high'] > self.current_ib['ib_high']:
            entry_price = self.current_ib['ib_high']
            direction = 'LONG'
            stop_loss = self.calculate_stop_loss(entry_price, direction)
            take_profit = self.calculate_take_profit(entry_price, stop_loss, direction)
            
            return {
                'entry_price': entry_price,
                'direction': direction,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'entry_type': 'BREAKOUT',
                'matched_expectation': True
            }
        
        # Short entry (low break expected)
        if expected_break == 'LOW' and bar['low'] < self.current_ib['ib_low']:
            entry_price = self.current_ib['ib_low']
            direction = 'SHORT'
            stop_loss = self.calculate_stop_loss(entry_price, direction)
            take_profit = self.calculate_take_profit(entry_price, stop_loss, direction)
            
            return {
                'entry_price': entry_price,
                'direction': direction,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'entry_type': 'BREAKOUT',
                'matched_expectation': True
            }
        
        return None
    
    def should_enter_pullback(self, bar: pd.Series) -> Optional[Dict]:
        """Check if should enter on pullback after break (Variant 2 with ICT FVG)"""
        if not self.ib_broken or self.current_ib is None:
            return None
        
        # Check if in entry window
        if bar.name.time() > self.entry_window_end:
            return None
        
        # Check if in kill zone
        if not self.is_in_killzone(bar.name.time()):
            return None
        
        # Check for FVG fill (pullback)
        if self.use_ict_fvg:
            filled_fvg = self.check_fvg_fill(bar)
            if filled_fvg is not None:
                # Enter in direction of break
                if self.break_side == 'HIGH':
                    entry_price = bar['close']
                    direction = 'LONG'
                    stop_loss = self.calculate_stop_loss(entry_price, direction)
                    take_profit = self.calculate_take_profit(entry_price, stop_loss, direction)
                    
                    return {
                        'entry_price': entry_price,
                        'direction': direction,
                        'stop_loss': stop_loss,
                        'take_profit': take_profit,
                        'entry_type': 'PULLBACK_FVG',
                        'matched_expectation': self.break_side == self.current_ib['expected_break']
                    }
                
                elif self.break_side == 'LOW':
                    entry_price = bar['close']
                    direction = 'SHORT'
                    stop_loss = self.calculate_stop_loss(entry_price, direction)
                    take_profit = self.calculate_take_profit(entry_price, stop_loss, direction)
                    
                    return {
                        'entry_price': entry_price,
                        'direction': direction,
                        'stop_loss': stop_loss,
                        'take_profit': take_profit,
                        'entry_type': 'PULLBACK_FVG',
                        'matched_expectation': self.break_side == self.current_ib['expected_break']
                    }
        
        return None
    
    def on_bar(self, bar: pd.Series, bar_index: int):
        """Process each bar"""
        current_date = bar.name.date()
        current_time = bar.name.time()
        
        # Calculate IB if it's a new day and after IB end time
        # IB starts at 9:30, so end time is 9:30 + duration
        ib_start_dt = pd.Timestamp.combine(current_date, time(9, 30))
        ib_end_dt = ib_start_dt + pd.Timedelta(minutes=self.ib_duration_minutes)
        ib_end_time = ib_end_dt.time()
        
        if (self.current_ib is None or self.current_ib['date'] != current_date) and current_time >= ib_end_time:
            self.current_ib = self.engine.calculate_ib_range(bar.name, self.ib_duration_minutes)
            self.ib_broken = False
            self.break_time = None
            self.break_side = None
            self.fvgs = []
            self.order_blocks = []
            
            # Validate IB range
            if self.current_ib is not None:
                if (self.current_ib['ib_range_pct'] < self.min_ib_range_pct or 
                    self.current_ib['ib_range_pct'] > self.max_ib_range_pct):
                    self.current_ib = None  # Skip this day
                    return
        
        if self.current_ib is None:
            return
        
        # Detect ICT structures
        if self.use_ict_fvg and bar_index >= 1:
            fvg = self.detect_fvg(self.engine.data, bar_index)
            if fvg is not None:
                self.fvgs.append(fvg)
        
        ob = self.detect_order_block(self.engine.data, bar_index)
        if ob is not None:
            self.order_blocks.append(ob)
        
        # Check for IB break
        if not self.ib_broken:
            break_side = self.engine.check_ib_break(
                self.current_ib, bar.name, bar['high'], bar['low']
            )
            if break_side is not None:
                self.ib_broken = True
                self.break_time = bar.name
                self.break_side = break_side
        
        # Update existing position
        if self.engine.position is not None:
            self.engine.update_position(bar)
            return
        
        # Entry logic based on variant
        entry_signal = None
        
        if self.entry_variant == 'breakout':
            entry_signal = self.should_enter_breakout(bar)
        elif self.entry_variant == 'pullback':
            entry_signal = self.should_enter_pullback(bar)
        
        # Enter position if signal generated
        if entry_signal is not None:
            # Mark IB as broken
            if not self.ib_broken:
                self.ib_broken = True
                self.break_time = bar.name
                self.break_side = entry_signal['direction'].replace('LONG', 'HIGH').replace('SHORT', 'LOW')
            
            # Build context
            context = {
                'date': current_date,
                'day_of_week': bar.name.strftime('%A'),
                'ib_duration_min': self.ib_duration_minutes,
                'ib_range_pct': self.current_ib['ib_range_pct'],
                'ib_close_position': self.current_ib['ib_close_position'],
                'expected_break': self.current_ib['expected_break'],
                'break_side': self.break_side,
                'break_time': self.break_time,
                'matched_expectation': entry_signal.get('matched_expectation', False),
                'entry_type': entry_signal.get('entry_type', 'UNKNOWN'),
                'variant': self.entry_variant
            }
            
            self.engine.enter_position(
                bar,
                entry_signal['direction'],
                entry_signal['entry_price'],
                entry_signal['stop_loss'],
                entry_signal['take_profit'],
                context
            )
    
    def run(self):
        """Run the backtest"""
        print(f"\n{'='*60}")
        print(f"Running IB Break Strategy Backtest")
        print(f"{'='*60}")
        print(f"Ticker: {self.engine.ticker}")
        print(f"Timeframe: {self.engine.timeframe}")
        print(f"IB Duration: {self.ib_duration_minutes} minutes")
        print(f"Entry Variant: {self.entry_variant}")
        print(f"Use ICT FVG: {self.use_ict_fvg}")
        print(f"Use ICT Kill Zones: {self.use_ict_killzones}")
        print(f"Date Range: {self.engine.start_date} to {self.engine.end_date}")
        print(f"{'='*60}\n")
        
        # Load data
        self.engine.load_data()
        
        # Iterate through bars
        for i, (timestamp, bar) in enumerate(self.engine.data.iterrows()):
            self.on_bar(bar, i)
        
        # Close any open position at end
        if self.engine.position is not None:
            last_bar = self.engine.data.iloc[-1]
            self.engine.exit_position(last_bar, last_bar['close'], 'END_OF_DATA')
        
        # Print results
        print(f"\n{'='*60}")
        print(f"Backtest Complete")
        print(f"{'='*60}")
        
        metrics = self.engine.get_performance_metrics()
        
        print(f"\nPerformance Metrics:")
        print(f"  Total Trades: {metrics.get('total_trades', 0)}")
        print(f"  Wins: {metrics.get('wins', 0)}")
        print(f"  Losses: {metrics.get('losses', 0)}")
        print(f"  Win Rate: {metrics.get('win_rate', 0):.2f}%")
        print(f"  Avg Win: {metrics.get('avg_win', 0):.2f}%")
        print(f"  Avg Loss: {metrics.get('avg_loss', 0):.2f}%")
        print(f"  Profit Factor: {metrics.get('profit_factor', 0):.2f}")
        print(f"  Total P&L: {metrics.get('total_pnl_pct', 0):.2f}%")
        print(f"  Avg MAE: {metrics.get('avg_mae', 0):.2f}%")
        print(f"  Avg MFE: {metrics.get('avg_mfe', 0):.2f}%")
        print(f"  Final Equity: ${metrics.get('final_equity', 0):,.2f}")
        print(f"  Total Return: {metrics.get('total_return_pct', 0):.2f}%")
        
        return metrics
