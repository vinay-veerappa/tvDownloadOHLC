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
from typing import Dict, List, Optional, Any
from scripts.trading_framework.core.backtest_engine import VectorizedBacktester


class IBBreakStrategy:
    """Initial Balance Break Strategy with ICT entry refinement"""
    
    def hunt(self, data: pd.DataFrame, params: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
        """
        Standardized hunter interface for the reporting framework.
        Runs the iterative logic and returns signals as a DataFrame.
        """
        # 1. Initialize logic
        self.data = data
        self.params = params or {}
        self.signals = []
        self.position = None
        
        # Ensure parameters are set
        self.ib_duration_minutes = int(self.params.get('ib_duration_minutes', 60))
        self.entry_variant = self.params.get('entry_variant', 'breakout')
        
        # 2. Run iterative loop (Layer 4/5 Hybrid)
        self.current_ib = None
        total_bars = len(data)
        for i, (ts, bar) in enumerate(data.iterrows()):
            """if i % 10000 == 0:
                print(f"[HUNTING] Processed {i}/{total_bars} bars...")
            """
            self.on_bar(bar, i)
            # Reset position mock after each day or signal to allow hunting multiple signals
            if self.position is not None:
                self.position = None 
                
        # 5. Return signal frame
        if not self.signals:
            return pd.DataFrame(columns=['signal_time', 'direction', 'entry_price', 'stop_price', 'target1_price'])
            
        return pd.DataFrame(self.signals)
    
    def __init__(
        self,
        ticker: str = "NQ1",
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
        """
        self.ticker = ticker
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

    def _calculate_ib_range(self, data: pd.DataFrame, timestamp: pd.Timestamp, duration: int) -> Optional[Dict]:
        """Calculates the IB range for the day containing the timestamp."""
        day_start = pd.Timestamp.combine(timestamp.date(), time(9, 30))
        if timestamp.tzinfo is not None:
            day_start = day_start.tz_localize(timestamp.tzinfo)
        day_end = day_start + pd.Timedelta(minutes=duration)
        
        ib_slice = data.loc[day_start:day_end]
        if ib_slice.empty:
            return None
            
        ib_high = ib_slice['high'].max()
        ib_low = ib_slice['low'].min()
        ib_close = ib_slice['close'].iloc[-1]
        
        ib_range = ib_high - ib_low
        ib_range_pct = (ib_range / ib_low) * 100 if ib_low > 0 else 0
        
        # Simple expectation: if close is in top third, expect high break
        pos = (ib_close - ib_low) / ib_range if ib_range > 0 else 0.5
        expected = "HIGH" if pos > 0.66 else ("LOW" if pos < 0.33 else "CHOP")
        
        return {
            'date': timestamp.date(),
            'ib_high': ib_high,
            'ib_low': ib_low,
            'ib_range_pct': ib_range_pct,
            'ib_close_position': pos,
            'expected_break': expected
        }

    def _check_ib_break(self, ib: Dict, timestamp: pd.Timestamp, high: float, low: float) -> Optional[str]:
        """Checks if a bar has broken the IB range."""
        if high > ib['ib_high']:
            return "HIGH"
        if low < ib['ib_low']:
            return "LOW"
        return None
    
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
        """
        if index < 2:
            return None
        
        curr_bar = bars.iloc[index]
        prev_bar = bars.iloc[index - 1]
        
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
            if direction == 'LONG':
                return self.current_ib['ib_low']
            else:
                return self.current_ib['ib_high']
        
        elif self.stop_loss_type == 'fixed_pct':
            if direction == 'LONG':
                return entry_price * 0.995
            else:
                return entry_price * 1.005
        
        elif self.stop_loss_type == 'order_block':
            if len(self.order_blocks) > 0:
                ob = self.order_blocks[-1]
                if direction == 'LONG':
                    return ob['low']
                else:
                    return ob['high']
            else:
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
        
        if bar.name.time() > self.entry_window_end:
            return None
        
        if not self.is_in_killzone(bar.name.time()):
            return None
        
        expected_break = self.current_ib['expected_break']
        
        if expected_break == 'HIGH' and bar['high'] > self.current_ib['ib_high']:
            entry_price = self.current_ib['ib_high']
            direction = 'LONG'
            stop_loss = self.calculate_stop_loss(entry_price, direction)
            take_profit = self.calculate_take_profit(entry_price, stop_loss, direction)
            return {
                'entry_price': entry_price, 'direction': direction,
                'stop_loss': stop_loss, 'take_profit': take_profit,
                'entry_type': 'BREAKOUT', 'matched_expectation': True
            }
        
        if expected_break == 'LOW' and bar['low'] < self.current_ib['ib_low']:
            entry_price = self.current_ib['ib_low']
            direction = 'SHORT'
            stop_loss = self.calculate_stop_loss(entry_price, direction)
            take_profit = self.calculate_take_profit(entry_price, stop_loss, direction)
            return {
                'entry_price': entry_price, 'direction': direction,
                'stop_loss': stop_loss, 'take_profit': take_profit,
                'entry_type': 'BREAKOUT', 'matched_expectation': True
            }
        
        return None
    
    def should_enter_pullback(self, bar: pd.Series) -> Optional[Dict]:
        """Check if should enter on pullback after break (Variant 2 with ICT FVG)"""
        if not self.ib_broken or self.current_ib is None:
            return None
        
        if bar.name.time() > self.entry_window_end:
            return None
        
        if not self.is_in_killzone(bar.name.time()):
            return None
        
        if self.use_ict_fvg:
            filled_fvg = self.check_fvg_fill(bar)
            if filled_fvg is not None:
                if self.break_side == 'HIGH':
                    entry_price = bar['close']
                    direction = 'LONG'
                    stop_loss = self.calculate_stop_loss(entry_price, direction)
                    take_profit = self.calculate_take_profit(entry_price, stop_loss, direction)
                    return {
                        'entry_price': entry_price, 'direction': direction,
                        'stop_loss': stop_loss, 'take_profit': take_profit,
                        'entry_type': 'PULLBACK_FVG',
                        'matched_expectation': self.break_side == self.current_ib['expected_break']
                    }
                elif self.break_side == 'LOW':
                    entry_price = bar['close']
                    direction = 'SHORT'
                    stop_loss = self.calculate_stop_loss(entry_price, direction)
                    take_profit = self.calculate_take_profit(entry_price, stop_loss, direction)
                    return {
                        'entry_price': entry_price, 'direction': direction,
                        'stop_loss': stop_loss, 'take_profit': take_profit,
                        'entry_type': 'PULLBACK_FVG',
                        'matched_expectation': self.break_side == self.current_ib['expected_break']
                    }
        return None

    def on_bar(self, bar: pd.Series, bar_index: int):
        """Process each bar"""
        current_date = bar.name.date()
        current_time = bar.name.time()
        
        ib_start_dt = pd.Timestamp.combine(current_date, time(9, 30))
        if bar.name.tzinfo is not None:
            ib_start_dt = ib_start_dt.tz_localize(bar.name.tzinfo)
        ib_end_dt = ib_start_dt + pd.Timedelta(minutes=self.ib_duration_minutes)
        ib_end_time = ib_end_dt.time()
        
        if (self.current_ib is None or self.current_ib['date'] != current_date) and current_time >= ib_end_time:
            self.current_ib = self._calculate_ib_range(self.data, bar.name, self.ib_duration_minutes)
            self.ib_broken = False
            self.break_time = None
            self.break_side = None
            self.fvgs = []
            self.order_blocks = []
            
            if self.current_ib is not None:
                if (self.current_ib['ib_range_pct'] < self.min_ib_range_pct or 
                    self.current_ib['ib_range_pct'] > self.max_ib_range_pct):
                    self.current_ib = None
                    return
        
        if self.current_ib is None:
            return
        
        if self.use_ict_fvg and bar_index >= 1:
            fvg = self.detect_fvg(self.data, bar_index)
            if fvg is not None:
                self.fvgs.append(fvg)
        
        ob = self.detect_order_block(self.data, bar_index)
        if ob is not None:
            self.order_blocks.append(ob)
        
        if not self.ib_broken:
            break_side = self._check_ib_break(self.current_ib, bar.name, bar['high'], bar['low'])
            if break_side is not None:
                self.ib_broken = True
                self.break_time = bar.name
                self.break_side = break_side
        
        entry_signal = None
        if self.entry_variant == 'breakout':
            entry_signal = self.should_enter_breakout(bar)
        elif self.entry_variant == 'pullback':
            entry_signal = self.should_enter_pullback(bar)
        
        if entry_signal is not None:
            # Layer 1: Chop Filter
            if self.params.get("chop_filter", False):
                from scripts.libs.indicators.market_regime import compute_chop_score
                results = compute_chop_score(self.data.iloc[:bar_index+1], lookback=14)
                curr_chop = results['chop_score'].iloc[-1]
                prev_chop = results['chop_score'].iloc[-2] if len(results) > 1 else curr_chop
                if curr_chop < 2.0 and prev_chop < 2.0:
                    return

            context = {
                'date': current_date,
                'ib_range_pct': self.current_ib['ib_range_pct'],
                'expected_break': self.current_ib['expected_break'],
                'break_side': self.break_side,
                'entry_type': entry_signal.get('entry_type', 'UNKNOWN')
            }
            
            self.signals.append({
                'signal_time': bar.name,
                'direction': entry_signal['direction'].lower(),
                'entry_price': entry_signal['entry_price'],
                'stop_price': entry_signal['stop_loss'],
                'target1_price': entry_signal['take_profit'],
                **context
            })
            self.position = "OPEN"
