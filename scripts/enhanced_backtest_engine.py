"""
Enhanced Backtest Engine with Partial Position Management

Extends the base BacktestEngine to support:
- Multiple take profit levels with partial exits
- Breakeven management
- Trailing stops
- Position scaling
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from backtest_engine import BacktestEngine
import pandas as pd
from typing import Dict, List, Optional


class EnhancedBacktestEngine(BacktestEngine):
    """Enhanced backtesting engine with partial position management"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Track partial positions
        self.position_tiers: List[Dict] = []
        self.breakeven_moved: bool = False
        self.trailing_active: bool = False
    
    def enter_position_with_tiers(
        self,
        bar: pd.Series,
        direction: str,
        entry_price: float,
        stop_loss: float,
        tp_levels: List[float],
        position_sizes: List[float],
        context: Dict
    ):
        """
        Enter position with multiple take profit tiers
        
        Args:
            bar: Current bar
            direction: 'LONG' or 'SHORT'
            entry_price: Entry price
            stop_loss: Initial stop loss
            tp_levels: List of take profit prices
            position_sizes: List of position sizes (as % of total, should sum to 1.0)
            context: Trade context data
        """
        # Apply slippage
        tick_value = self.tick_values.get(self.ticker, 5.0)
        slippage = self.slippage_ticks * (tick_value / 5.0)
        
        if direction == 'LONG':
            entry_price += slippage
        else:
            entry_price -= slippage
        
        # Create position tiers
        self.position_tiers = []
        for i, (tp_price, size) in enumerate(zip(tp_levels, position_sizes)):
            tier = {
                'tier_num': i + 1,
                'size': size,
                'tp_price': tp_price,
                'active': True
            }
            self.position_tiers.append(tier)
        
        # Create main position
        self.position = {
            'entry_time': bar.name,
            'entry_price': entry_price,
            'direction': direction,
            'stop_loss': stop_loss,
            'initial_stop': stop_loss,
            'highest_price': entry_price,
            'lowest_price': entry_price,
            'mae': 0.0,
            'mfe': 0.0,
            'context': context.copy(),
            'tiers_hit': [],
            'remaining_size': 1.0
        }
        
        self.breakeven_moved = False
        self.trailing_active = False
    
    def update_position_with_tiers(self, bar: pd.Series):
        """Update position with tier management"""
        if self.position is None:
            return
        
        high = bar['high']
        low = bar['low']
        entry_price = self.position['entry_price']
        direction = self.position['direction']
        
        # Update highest/lowest
        self.position['highest_price'] = max(self.position['highest_price'], high)
        self.position['lowest_price'] = min(self.position['lowest_price'], low)
        
        # Calculate MAE and MFE
        if direction == 'LONG':
            adverse_move = ((self.position['lowest_price'] - entry_price) / entry_price) * 100
            self.position['mae'] = min(self.position['mae'], adverse_move)
            
            favorable_move = ((self.position['highest_price'] - entry_price) / entry_price) * 100
            self.position['mfe'] = max(self.position['mfe'], favorable_move)
        else:
            adverse_move = ((entry_price - self.position['highest_price']) / entry_price) * 100
            self.position['mae'] = min(self.position['mae'], adverse_move)
            
            favorable_move = ((entry_price - self.position['lowest_price']) / entry_price) * 100
            self.position['mfe'] = max(self.position['mfe'], favorable_move)
        
        # Check for tier exits
        for tier in self.position_tiers:
            if not tier['active']:
                continue
            
            tier_hit = False
            if direction == 'LONG' and high >= tier['tp_price']:
                tier_hit = True
            elif direction == 'SHORT' and low <= tier['tp_price']:
                tier_hit = True
            
            if tier_hit:
                # Record tier hit
                tier['active'] = False
                self.position['tiers_hit'].append({
                    'tier_num': tier['tier_num'],
                    'time': bar.name,
                    'price': tier['tp_price'],
                    'size': tier['size']
                })
                self.position['remaining_size'] -= tier['size']
                
                # Breakeven management
                if tier['tier_num'] == 1 and not self.breakeven_moved:
                    # Move stop to breakeven after first TP
                    self.position['stop_loss'] = entry_price
                    self.breakeven_moved = True
                
                elif tier['tier_num'] == 2 and not self.trailing_active:
                    # Start trailing after second TP
                    # Move stop to first TP level
                    if len(self.position['tiers_hit']) >= 1:
                        first_tp = self.position['tiers_hit'][0]['price']
                        self.position['stop_loss'] = first_tp
                        self.trailing_active = True
        
        # Check for stop loss
        if direction == 'LONG' and low <= self.position['stop_loss']:
            self.exit_position_with_tiers(bar, self.position['stop_loss'], 'SL')
            return
        elif direction == 'SHORT' and high >= self.position['stop_loss']:
            self.exit_position_with_tiers(bar, self.position['stop_loss'], 'SL')
            return
        
        # Time-based exits
        current_time = bar.name.time()
        
        # USER REQUEST: Exit at 12:00 PM EST if still open
        if current_time >= pd.Timestamp('12:00').time() and current_time < pd.Timestamp('12:05').time():
            self.exit_position_with_tiers(bar, bar['close'], 'TARGET_12PM')
            return
            
        # Exit at 3:30 PM ET
        if current_time >= pd.Timestamp('15:30').time():
            self.exit_position_with_tiers(bar, bar['close'], 'TIME_330PM')
            return
        
        # Hard exit at 4:00 PM ET
        if current_time >= pd.Timestamp('16:00').time():
            self.exit_position_with_tiers(bar, bar['close'], 'EOD')
            return
    
    def exit_position_with_tiers(self, bar: pd.Series, exit_price: float, exit_reason: str):
        """Exit remaining position"""
        if self.position is None:
            return
        
        # Apply slippage
        tick_value = self.tick_values.get(self.ticker, 5.0)
        slippage = self.slippage_ticks * (tick_value / 5.0)
        
        if self.position['direction'] == 'LONG':
            exit_price -= slippage
        else:
            exit_price += slippage
        
        # Calculate weighted average P&L
        total_pnl_pct = 0.0
        
        # Add P&L from tiers that hit
        for tier_hit in self.position['tiers_hit']:
            if self.position['direction'] == 'LONG':
                tier_pnl = ((tier_hit['price'] - self.position['entry_price']) / self.position['entry_price']) * 100
            else:
                tier_pnl = ((self.position['entry_price'] - tier_hit['price']) / self.position['entry_price']) * 100
            
            total_pnl_pct += tier_pnl * tier_hit['size']
        
        # Add P&L from remaining position
        if self.position['remaining_size'] > 0:
            if self.position['direction'] == 'LONG':
                remaining_pnl = ((exit_price - self.position['entry_price']) / self.position['entry_price']) * 100
            else:
                remaining_pnl = ((self.position['entry_price'] - exit_price) / self.position['entry_price']) * 100
            
            total_pnl_pct += remaining_pnl * self.position['remaining_size']
        
        # Determine result
        if total_pnl_pct > 0.01:
            result = 'WIN'
        elif total_pnl_pct < -0.01:
            result = 'LOSS'
        else:
            result = 'BREAKEVEN'
        
        # Calculate hold duration
        hold_duration = (bar.name - self.position['entry_time']).total_seconds() / 60
        
        # Record trade
        trade = {
            'entry_time': self.position['entry_time'],
            'entry_price': self.position['entry_price'],
            'exit_time': bar.name,
            'exit_price': exit_price,
            'direction': self.position['direction'],
            'pnl_pct': total_pnl_pct,
            'mae_pct': self.position['mae'],
            'mfe_pct': self.position['mfe'],
            'initial_stop': self.position['initial_stop'],
            'exit_reason': exit_reason,
            'result': result,
            'hold_duration_min': hold_duration,
            'tiers_hit': len(self.position['tiers_hit']),
            'breakeven_moved': self.breakeven_moved,
            'trailing_active': self.trailing_active,
            **self.position['context']
        }
        
        self.trades.append(trade)
        
        # Update equity
        tick_value = self.tick_values.get(self.ticker, 5.0)
        pnl_dollars = (total_pnl_pct / 100) * self.position['entry_price'] * (tick_value / 0.25)
        pnl_dollars -= (2 * self.commission)
        
        self.current_equity += pnl_dollars
        self.equity_curve.append(self.current_equity)
        
        # Clear position
        self.position = None
        self.position_tiers = []
        self.breakeven_moved = False
        self.trailing_active = False
