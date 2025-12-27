"""
Initial Balance Pullback Strategy

Implements pullback entries using:
- Multi-timeframe Fair Value Gaps (5m, 15m, 1h)
- Fibonacci retracement levels (38.2%, 50%, 61.8%)
- Order Block confluence
- Multiple take profit tiers with breakeven management

Based on MAE/MFE analysis showing only 12.5% of breakout trades reach 1R.
Pullback entries expected to improve this to 40-50%.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

import pandas as pd
import numpy as np
from datetime import time, timedelta
from typing import Dict, List, Optional, Tuple
from enhanced_backtest_engine import EnhancedBacktestEngine
from fibonacci_calculator import FibonacciCalculator


class IBPullbackStrategy:
    """IB Break strategy with pullback entries"""
    
    def __init__(
        self,
        engine: EnhancedBacktestEngine,
        ib_duration_minutes: int = 45,
        pullback_mechanisms: List[str] = ['fvg', 'fibonacci'],
        fvg_timeframes: List[str] = ['5m', '15m'],
        fib_entry_type: str = 'standard',  # 'aggressive', 'standard', 'conservative'
        min_confluence_score: int = 2,
        tp_r_multiples: List[float] = [0.5, 1.0],
        position_tiers: List[float] = [0.5, 0.5],
        use_optimized_stop: bool = True,
        entry_window_end: time = time(11, 0)
    ):
        """
        Initialize IB Pullback Strategy
        
        Args:
            engine: Enhanced backtest engine
            ib_duration_minutes: IB duration (15, 30, 45, 60)
            pullback_mechanisms: List of mechanisms to use
            fvg_timeframes: Timeframes for FVG detection
            fib_entry_type: Fibonacci entry aggressiveness
            min_confluence_score: Minimum score to enter (1-3)
            tp_r_multiples: Take profit R-multiples
            position_tiers: Position sizes for each TP
            use_optimized_stop: Use MAE-optimized stop (-0.253%)
            entry_window_end: Latest time to enter
        """
        self.engine = engine
        self.ib_duration_minutes = ib_duration_minutes
        self.pullback_mechanisms = pullback_mechanisms
        self.fvg_timeframes = fvg_timeframes
        self.fib_entry_type = fib_entry_type
        self.min_confluence_score = min_confluence_score
        self.tp_r_multiples = tp_r_multiples
        self.position_tiers = position_tiers
        self.use_optimized_stop = use_optimized_stop
        self.entry_window_end = entry_window_end
        
        # Optimized stop from MAE analysis
        self.optimized_stop_pct = 0.253
        
        # Track IB data per day
        self.current_ib: Optional[Dict] = None
        self.ib_broken: bool = False
        self.break_time: Optional[pd.Timestamp] = None
        self.break_side: Optional[str] = None
        self.breakout_extreme: Optional[float] = None
        
        # FIXED: Track trades per day
        self.current_date: Optional[pd.Timestamp] = None
        self.entered_today: bool = False
        self.can_trigger_pullback: bool = False
        
        # Fibonacci data
        self.fib_data: Optional[Dict] = None
        
        # FVGs by timeframe
        self.fvgs_5m: List[Dict] = []
        self.fvgs_15m: List[Dict] = []
        self.fvgs_1h: List[Dict] = []
        
        # Order Blocks
        self.order_blocks: List[Dict] = []
        
        # Higher timeframe data
        self.data_15m: Optional[pd.DataFrame] = None
        self.data_1h: Optional[pd.DataFrame] = None
    
    def load_higher_timeframe_data(self):
        """Load 15m and 1h data for multi-timeframe FVG detection"""
        if '15m' in self.fvg_timeframes:
            try:
                file_15m = self.engine.data_dir / f"{self.engine.ticker}_15m.parquet"
                if file_15m.exists():
                    self.data_15m = pd.read_parquet(file_15m)
                    if self.data_15m.index.tz is None:
                        self.data_15m.index = self.data_15m.index.tz_localize('UTC').tz_convert(self.engine.tz_et)
                    elif self.data_15m.index.tz != self.engine.tz_et:
                        self.data_15m.index = self.data_15m.index.tz_convert(self.engine.tz_et)
                    print(f"✓ Loaded 15m data: {len(self.data_15m)} bars")
            except Exception as e:
                print(f"⚠ Could not load 15m data: {e}")
        
        if '1h' in self.fvg_timeframes:
            try:
                file_1h = self.engine.data_dir / f"{self.engine.ticker}_1h.parquet"
                if file_1h.exists():
                    self.data_1h = pd.read_parquet(file_1h)
                    if self.data_1h.index.tz is None:
                        self.data_1h.index = self.data_1h.index.tz_localize('UTC').tz_convert(self.engine.tz_et)
                    elif self.data_1h.index.tz != self.engine.tz_et:
                        self.data_1h.index = self.data_1h.index.tz_convert(self.engine.tz_et)
                    print(f"✓ Loaded 1h data: {len(self.data_1h)} bars")
            except Exception as e:
                print(f"⚠ Could not load 1h data: {e}")
    
    def detect_fvg(self, bars: pd.DataFrame, index: int) -> Optional[Dict]:
        """Detect Fair Value Gap"""
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
    
    def check_fvg_fill(self, price: float, fvgs: List[Dict], direction: str) -> Optional[Dict]:
        """Check if price has filled any FVG"""
        for fvg in fvgs:
            if fvg['filled']:
                continue
            
            # Check if price is in FVG zone
            if direction == 'LONG' and fvg['type'] == 'BULLISH':
                if fvg['bottom'] <= price <= fvg['top']:
                    fvg['filled'] = True
                    return fvg
            elif direction == 'SHORT' and fvg['type'] == 'BEARISH':
                if fvg['bottom'] <= price <= fvg['top']:
                    fvg['filled'] = True
                    return fvg
        
        return None
    
    def calculate_confluence_score(
        self,
        price: float,
        direction: str
    ) -> Tuple[int, List[str]]:
        """
        Calculate confluence score for entry
        
        Returns:
            (score, reasons)
        """
        score = 0
        reasons = []
        
        ib_low = self.current_ib['ib_low']
        ib_high = self.current_ib['ib_high']
        
        # Check FVG confluence
        if 'fvg' in self.pullback_mechanisms:
            # 5m FVG
            if self.check_fvg_fill(price, self.fvgs_5m, direction):
                if ib_low <= price <= ib_high:
                    score += 1
                    reasons.append('5m_FVG')
            
            # 15m FVG (higher weight)
            if self.data_15m is not None and self.check_fvg_fill(price, self.fvgs_15m, direction):
                if ib_low <= price <= ib_high:
                    score += 2
                    reasons.append('15m_FVG')
        
        # Check Fibonacci confluence
        if 'fibonacci' in self.pullback_mechanisms and self.fib_data is not None:
            fib_levels = self.fib_data['retracements'][direction]
            is_at_fib, fib_name = FibonacciCalculator.is_price_at_fib_level(
                price, fib_levels, tolerance_pct=0.15
            )
            if is_at_fib:
                score += 2
                reasons.append(f'Fib_{fib_name}')
        
        return score, reasons
    
    def should_enter_pullback(self, bar: pd.Series) -> Optional[Dict]:
        """Check if should enter on internal IB pullback/retracement"""
        # IB must be formed (after 10:15 ET)
        if self.current_ib is None or self.fib_data is None:
            return None
        
        # Only one trade per day
        if self.entered_today:
            return None
        
        # Entry window: 10:16 AM - 12:00 PM EST (per USER REQUEST)
        current_time = bar.name.time()
        if current_time < time(10, 16) or current_time > time(12, 0):
            return None
            
        current_price = bar['close']
        
        # USER REQUEST: Bias based on High/Low sequence
        # High first, Low Last -> SHORT (BEARISH)
        # Low first, High Last -> LONG (BULLISH)
        direction = 'SHORT' if self.current_ib['ib_high_time'] < self.current_ib['ib_low_time'] else 'LONG'
        
        # Pullback must happen within the IB range
        ib_low = self.current_ib['ib_low']
        ib_high = self.current_ib['ib_high']
        if not (ib_low <= current_price <= ib_high):
            return None
            
        # Get Fibonacci entry zone
        fib_zone_low, fib_zone_high = FibonacciCalculator.get_entry_zone(
            {
                'retracements': self.fib_data['retracements'][direction],
                'range': self.fib_data['range'],
                'direction': direction
            }, 
            self.fib_entry_type
        )
        
        # USER REQUEST: "Touch-Based" Pullback Trigger
        # Price must have been on trend side (Below for Short, Above for Long)
        if not self.can_trigger_pullback:
            if direction == 'SHORT' and current_price < fib_zone_low:
                self.can_trigger_pullback = True
            elif direction == 'LONG' and current_price > fib_zone_high:
                self.can_trigger_pullback = True
                
        if not self.can_trigger_pullback:
            return None
            
        # Check for touch
        bar_high = bar['high']
        bar_low = bar['low']
        bar_touched_fib = not (bar_low > fib_zone_high or bar_high < fib_zone_low)
        
        # Calculate confluence score (FVG check)
        score, reasons = self.calculate_confluence_score(current_price, direction)
        
        if not bar_touched_fib and score < self.min_confluence_score:
            return None

        # Take entry
        entry_price = current_price
        stop_loss = ib_low if direction == 'LONG' else ib_high
            
        # Take profit levels
        risk = abs(entry_price - stop_loss)
        tp_levels = []
        for r_mult in self.tp_r_multiples:
            tp = entry_price + (risk * r_mult) if direction == 'LONG' else entry_price - (risk * r_mult)
            tp_levels.append(tp)
            
        return {
            'entry_price': entry_price,
            'direction': direction,
            'stop_loss': stop_loss,
            'tp_levels': tp_levels,
            'position_sizes': self.position_tiers,
            'entry_type': 'INTERNAL_IB_PULLBACK',
            'confluence_score': score,
            'confluence_reasons': ','.join(reasons),
            'fib_entry_zone': f"{fib_zone_low:.2f}-{fib_zone_high:.2f}",
            'matched_expectation': True
        }
    
    def on_bar(self, bar: pd.Series, bar_index: int):
        """Process each bar"""
        current_date = bar.name.date()
        current_time = bar.name.time()
        
        # Reset daily trade flag and pullback trigger state
        if self.current_date is None or self.current_date != current_date:
            self.current_date = current_date
            self.entered_today = False
            self.can_trigger_pullback = False
            self.current_ib = None
            self.fib_data = None
            self.fvgs_5m = []

        # Calculate IB if new day
        ib_start_dt = pd.Timestamp.combine(current_date, time(9, 30))
        ib_end_dt = ib_start_dt + pd.Timedelta(minutes=self.ib_duration_minutes)
        ib_end_time = ib_end_dt.time()
        
        if (self.current_ib is None or self.current_ib['date'] != current_date) and current_time >= ib_end_time:
            self.current_ib = self.engine.calculate_ib_range(bar.name, self.ib_duration_minutes)
            if self.current_ib is not None:
                if 0.1 <= self.current_ib['ib_range_pct'] <= 3.0:
                    self.fib_data = FibonacciCalculator.calculate_internal_ib_fibonacci(self.current_ib)
                else:
                    self.current_ib = None
        
        if self.current_ib is None:
            return

        # USER REQUEST: 12:00 PM Hard Exit
        if current_time >= time(12, 0) and self.engine.position is not None:
            self.engine.exit_position_with_tiers(bar, bar['close'], 'TARGET_EXIT_12PM')
            return

        # Update existing position
        if self.engine.position is not None:
            self.engine.update_position_with_tiers(bar)
            return
        
        # Detect FVGs on 5m
        if bar_index >= 1:
            fvg = self.detect_fvg(self.engine.data, bar_index)
            if fvg is not None:
                self.fvgs_5m.append(fvg)
        
        # Check for pullback entry
        entry_signal = self.should_enter_pullback(bar)
        
        if entry_signal is not None:
            self.entered_today = True
            
            # Build context
            context = {
                'date': current_date,
                'ib_duration_min': self.ib_duration_minutes,
                'ib_range_pct': self.current_ib['ib_range_pct'],
                'entry_type': entry_signal['entry_type'],
                'confluence_score': entry_signal['confluence_score'],
                'confluence_reasons': entry_signal['confluence_reasons'],
                'fib_entry_zone': entry_signal['fib_entry_zone'],
                'variant': 'pullback'
            }
            
            self.engine.enter_position_with_tiers(
                bar,
                entry_signal['direction'],
                entry_signal['entry_price'],
                entry_signal['stop_loss'],
                entry_signal['tp_levels'],
                entry_signal['position_sizes'],
                context
            )
            
    def run(self):
        """Run the backtest"""
        print(f"\n{'='*80}")
        print(f"Running IB Pullback Strategy Backtest")
        print(f"{'='*80}")
        print(f"Ticker: {self.engine.ticker}")
        print(f"Timeframe: {self.engine.timeframe}")
        print(f"Date Range: {self.engine.start_date} to {self.engine.end_date}")
        print(f"{'='*80}\n")
        
        self.engine.load_data()
        self.load_higher_timeframe_data()
        
        for i, (timestamp, bar) in enumerate(self.engine.data.iterrows()):
            self.on_bar(bar, i)
        
        if self.engine.position is not None:
            last_bar = self.engine.data.iloc[-1]
            self.engine.exit_position_with_tiers(last_bar, last_bar['close'], 'END_OF_DATA')
        
        return self.engine.get_performance_metrics()
