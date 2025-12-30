"""
Extensible Trade Simulator Framework
=====================================
A modular, event-driven backtesting framework that supports multiple strategies.

ARCHITECTURE:
- BaseStrategy: Abstract class defining the strategy interface
- TradeSimulator: Engine that runs any BaseStrategy implementation
- ORB_V7_Strategy: Concrete implementation for 9:30 ORB breakout

USAGE:
    from simulate_trades import TradeSimulator, ORB_V7_Strategy
    
    strategy = ORB_V7_Strategy(config)
    simulator = TradeSimulator(strategy, data)
    results = simulator.run()

EXTENDING:
    Create a new strategy by inheriting from BaseStrategy and implementing:
    - should_enter(bar, state) -> (bool, direction, entry_price)
    - should_exit(bar, state) -> (bool, exit_reason, exit_price)
    - on_entry(bar, state) -> state
    - on_exit(bar, state) -> state
"""

import pandas as pd
import numpy as np
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple
from datetime import time
import json
import os

# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class TradeState:
    """Current state of a trade (passed to strategy methods)"""
    position: int = 0  # 1=Long, -1=Short, 0=Flat
    entry_price: float = 0.0
    entry_time: Optional[pd.Timestamp] = None
    sl_price: float = 0.0
    tp1_price: float = 0.0
    tp2_price: float = 0.0
    tp1_hit: bool = False
    quantity_remaining: float = 1.0  # 1.0 = full, 0.5 = partial
    trades_today: int = 0
    mae: float = 0.0  # Max Adverse Excursion
    mfe: float = 0.0  # Max Favorable Excursion
    breakout_bar: Optional[pd.Series] = None  # For engulfing detection
    custom: Dict = field(default_factory=dict)  # Strategy-specific state

@dataclass
class DayContext:
    """Context for a trading day (range, filters, etc.)"""
    date: pd.Timestamp
    range_high: float
    range_low: float
    range_open: float
    range_pct: float
    day_of_week: int
    vvix_open: Optional[float] = None
    regime_bull: bool = True
    custom: Dict = field(default_factory=dict)

@dataclass
class TradeRecord:
    """Record of a completed trade"""
    date: pd.Timestamp
    direction: str
    entry_price: float
    entry_time: pd.Timestamp
    exit_price: float
    exit_time: pd.Timestamp
    exit_reason: str
    pnl_pct: float
    mae_pct: float
    mfe_pct: float
    tp1_hit: bool
    quantity: float
    custom: Dict = field(default_factory=dict)

# ============================================================
# BASE STRATEGY (Abstract)
# ============================================================

class BaseStrategy(ABC):
    """Abstract base class for all strategies"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.name = config.get('name', 'Unnamed Strategy')
    
    @abstractmethod
    def should_trade_day(self, context: DayContext) -> bool:
        """Return True if this day passes filters"""
        pass
    
    @abstractmethod
    def should_enter(self, bar: pd.Series, state: TradeState, context: DayContext) -> Tuple[bool, int, float]:
        """
        Check if we should enter a trade.
        Returns: (should_enter, direction, entry_price)
        """
        pass
    
    @abstractmethod
    def should_exit(self, bar: pd.Series, state: TradeState, context: DayContext) -> Tuple[bool, str, float, float]:
        """
        Check if we should exit (fully or partially).
        Returns: (should_exit, reason, exit_price, quantity_to_exit)
        """
        pass
    
    def on_entry(self, bar: pd.Series, state: TradeState, context: DayContext) -> TradeState:
        """Called after entry - set up initial state"""
        return state
    
    def on_bar(self, bar: pd.Series, state: TradeState, context: DayContext) -> TradeState:
        """Called on each bar - update MAE/MFE, etc."""
        if state.position != 0:
            if state.position == 1:
                state.mae = max(state.mae, (state.entry_price - bar['low']) / state.entry_price * 100)
                state.mfe = max(state.mfe, (bar['high'] - state.entry_price) / state.entry_price * 100)
            else:
                state.mae = max(state.mae, (bar['high'] - state.entry_price) / state.entry_price * 100)
                state.mfe = max(state.mfe, (state.entry_price - bar['low']) / state.entry_price * 100)
        return state

# ============================================================
# ORB V7 STRATEGY IMPLEMENTATION
# ============================================================

class ORB_V7_Strategy(BaseStrategy):
    """
    9:30 Opening Range Breakout V7.1 Strategy
    
    Entry: Confirmed breakout (0.10% beyond range)
    Exit: CTQ (Cover the Queen) with time exit
    """
    
    def __init__(self, config: Dict = None):
        default_config = {
            'name': 'ORB_V7.1',
            'confirm_pct': 0.10,
            'tp1_pct': 0.05,
            'tp1_qty': 0.50,
            'max_sl_pct': 0.25,
            'hard_exit_time': time(11, 0),
            'entry_cutoff_time': time(10, 30),
            'use_engulfing_exit': False,
            'use_be_trail': False,
            'allow_reentry': False,
            'skip_tuesday': True,
            'skip_wednesday': True,
            'max_range_pct': 0.25,
            'vvix_threshold': 115,
        }
        if config:
            default_config.update(config)
        super().__init__(default_config)
    
    def should_trade_day(self, context: DayContext) -> bool:
        """Check if day passes filters"""
        if self.config['skip_tuesday'] and context.day_of_week == 1:
            return False
        if self.config['skip_wednesday'] and context.day_of_week == 2:
            return False
        if context.range_pct > self.config['max_range_pct']:
            return False
        if context.vvix_open and context.vvix_open > self.config['vvix_threshold']:
            return False
        return True
    
    def should_enter(self, bar: pd.Series, state: TradeState, context: DayContext) -> Tuple[bool, int, float]:
        """Check for confirmed breakout entry"""
        if state.position != 0:
            return False, 0, 0.0
        
        # Check entry cutoff
        bar_time = bar.name.time()
        if bar_time >= self.config['entry_cutoff_time']:
            return False, 0, 0.0
        
        # Check re-entry limit
        if not self.config['allow_reentry'] and state.trades_today > 0:
            return False, 0, 0.0
        
        # Confirmation levels
        confirm_long = context.range_high * (1 + self.config['confirm_pct'] / 100)
        confirm_short = context.range_low * (1 - self.config['confirm_pct'] / 100)
        
        if bar['close'] > confirm_long:
            return True, 1, bar['close']
        elif bar['close'] < confirm_short:
            return True, -1, bar['close']
        
        return False, 0, 0.0
    
    def should_exit(self, bar: pd.Series, state: TradeState, context: DayContext) -> Tuple[bool, str, float, float]:
        """Check exit conditions in priority order"""
        if state.position == 0:
            return False, '', 0.0, 0.0
        
        pos = state.position
        
        # 1. Engulfing candle exit (optional)
        if self.config['use_engulfing_exit'] and state.breakout_bar is not None:
            bb = state.breakout_bar
            if pos == 1:
                if bar['close'] < bb['open'] and bar['open'] > bb['close']:
                    return True, 'ENGULF', bar['close'], state.quantity_remaining
            else:
                if bar['close'] > bb['open'] and bar['open'] < bb['close']:
                    return True, 'ENGULF', bar['close'], state.quantity_remaining
        
        # 2. TP1 (Cover the Queen) - partial exit
        if not state.tp1_hit:
            if pos == 1 and bar['high'] >= state.tp1_price:
                return True, 'TP1', state.tp1_price, self.config['tp1_qty']
            elif pos == -1 and bar['low'] <= state.tp1_price:
                return True, 'TP1', state.tp1_price, self.config['tp1_qty']
        
        # 3. Stop Loss
        sl_price = state.sl_price
        if self.config['use_be_trail'] and state.tp1_hit:
            sl_price = state.entry_price  # BE trail
        
        if pos == 1 and bar['low'] <= sl_price:
            return True, 'SL', sl_price, state.quantity_remaining
        elif pos == -1 and bar['high'] >= sl_price:
            return True, 'SL', sl_price, state.quantity_remaining
        
        # 4. Time exit
        bar_time = bar.name.time()
        if bar_time >= self.config['hard_exit_time']:
            return True, 'TIME', bar['close'], state.quantity_remaining
        
        return False, '', 0.0, 0.0
    
    def on_entry(self, bar: pd.Series, state: TradeState, context: DayContext) -> TradeState:
        """Set up SL and TP levels after entry"""
        if state.position == 1:
            state.sl_price = context.range_low
            state.tp1_price = state.entry_price * (1 + self.config['tp1_pct'] / 100)
        else:
            state.sl_price = context.range_high
            state.tp1_price = state.entry_price * (1 - self.config['tp1_pct'] / 100)
        
        state.breakout_bar = bar
        state.trades_today += 1
        return state

# ============================================================
# TRADE SIMULATOR ENGINE
# ============================================================

class TradeSimulator:
    """
    Event-driven trade simulator that runs any BaseStrategy
    """
    
    def __init__(self, strategy: BaseStrategy):
        self.strategy = strategy
        self.trades: List[TradeRecord] = []
    
    def load_data(self, ticker: str, years: int = 10):
        """Load OHLC data and opening range"""
        # Load opening range
        or_path = f"data/{ticker}_opening_range.json"
        with open(or_path, 'r') as f:
            or_data = json.load(f)
        self.or_df = pd.DataFrame(or_data)
        self.or_df['date'] = pd.to_datetime(self.or_df['date'])
        self.or_df = self.or_df.set_index('date')
        
        # Load 1m data
        self.df_1m = pd.read_parquet(f"data/{ticker}_1m.parquet")
        if 'time' in self.df_1m.columns:
            self.df_1m['datetime'] = pd.to_datetime(self.df_1m['time'], unit='s')
            self.df_1m = self.df_1m.set_index('datetime')
        if self.df_1m.index.tz is None:
            self.df_1m = self.df_1m.tz_localize('UTC')
        self.df_1m = self.df_1m.tz_convert('US/Eastern').sort_index()
        
        # Load VVIX
        self.vvix = None
        if os.path.exists('data/VVIX_1d.parquet'):
            vvix_raw = pd.read_parquet('data/VVIX_1d.parquet')
            if 'time' in vvix_raw.columns:
                vvix_raw['date'] = pd.to_datetime(vvix_raw['time'], unit='s').dt.date
                self.vvix = vvix_raw.set_index('date')
        
        # Filter to period
        end_date = self.or_df.index.max()
        start_date = end_date - pd.Timedelta(days=years*365)
        self.or_df = self.or_df[self.or_df.index >= start_date]
    
    def run(self) -> pd.DataFrame:
        """Run simulation over all days"""
        self.trades = []
        
        for d, row in self.or_df.iterrows():
            # Build day context
            context = DayContext(
                date=d,
                range_high=row['high'],
                range_low=row['low'],
                range_open=row['open'],
                range_pct=row.get('range_pct', (row['high'] - row['low']) / row['open']),
                day_of_week=d.dayofweek,
            )
            
            # Get VVIX
            if self.vvix is not None:
                try:
                    vv = self.vvix.loc[d.date()]['open']
                    context.vvix_open = vv.iloc[0] if isinstance(vv, pd.Series) else vv
                except:
                    pass
            
            # Check day filter
            if not self.strategy.should_trade_day(context):
                continue
            
            # Get intraday bars
            d_loc = pd.Timestamp(d).tz_localize('US/Eastern')
            t_start = d_loc + pd.Timedelta(hours=9, minutes=31)
            t_end = d_loc + pd.Timedelta(hours=11, minutes=30)
            
            bars = self.df_1m.loc[t_start:t_end]
            if len(bars) < 5:
                continue
            
            # Initialize state for the day
            state = TradeState()
            
            # Bar-by-bar simulation
            for bar_time, bar in bars.iterrows():
                # Update MAE/MFE
                state = self.strategy.on_bar(bar, state, context)
                
                # Check entry
                if state.position == 0:
                    should_enter, direction, entry_price = self.strategy.should_enter(bar, state, context)
                    if should_enter:
                        state.position = direction
                        state.entry_price = entry_price
                        state.entry_time = bar_time
                        state.quantity_remaining = 1.0
                        state.mae = 0.0
                        state.mfe = 0.0
                        state = self.strategy.on_entry(bar, state, context)
                
                # Check exit
                if state.position != 0:
                    should_exit, reason, exit_price, exit_qty = self.strategy.should_exit(bar, state, context)
                    if should_exit:
                        # Calculate PnL
                        if state.position == 1:
                            pnl = (exit_price - state.entry_price) / state.entry_price * 100
                        else:
                            pnl = (state.entry_price - exit_price) / state.entry_price * 100
                        
                        # Record trade
                        trade = TradeRecord(
                            date=d,
                            direction='LONG' if state.position == 1 else 'SHORT',
                            entry_price=state.entry_price,
                            entry_time=state.entry_time,
                            exit_price=exit_price,
                            exit_time=bar_time,
                            exit_reason=reason,
                            pnl_pct=pnl * exit_qty,
                            mae_pct=state.mae,
                            mfe_pct=state.mfe,
                            tp1_hit=state.tp1_hit or reason == 'TP1',
                            quantity=exit_qty,
                        )
                        self.trades.append(trade)
                        
                        # Update state
                        if reason == 'TP1':
                            state.tp1_hit = True
                            state.quantity_remaining -= exit_qty
                            if state.quantity_remaining <= 0:
                                state.position = 0
                        else:
                            state.position = 0
        
        return self._to_dataframe()
    
    def _to_dataframe(self) -> pd.DataFrame:
        """Convert trades to DataFrame"""
        if not self.trades:
            return pd.DataFrame()
        return pd.DataFrame([vars(t) for t in self.trades])
    
    def summary(self) -> Dict:
        """Calculate summary statistics"""
        if not self.trades:
            return {'trades': 0}
        
        df = self._to_dataframe()
        winners = df[df['pnl_pct'] > 0]
        
        return {
            'strategy': self.strategy.name,
            'trades': len(df),
            'win_rate': len(winners) / len(df),
            'gross_pnl': df['pnl_pct'].sum(),
            'avg_pnl': df['pnl_pct'].mean(),
            'avg_mae': df['mae_pct'].mean(),
            'avg_mfe': df['mfe_pct'].mean(),
            'profit_factor': winners['pnl_pct'].sum() / abs(df[df['pnl_pct'] < 0]['pnl_pct'].sum()) if (df['pnl_pct'] < 0).any() else float('inf'),
        }

# ============================================================
# MAIN
# ============================================================

if __name__ == '__main__':
    print("=== ORB V7.1 Trade Simulation ===\n")
    
    # Create strategy with default config
    strategy = ORB_V7_Strategy()
    
    # Create simulator
    sim = TradeSimulator(strategy)
    sim.load_data('NQ1', years=10)
    
    # Run simulation
    print("Running bar-by-bar simulation...")
    trades_df = sim.run()
    
    # Show results
    summary = sim.summary()
    print(f"\n=== RESULTS: {summary['strategy']} ===")
    print(f"Total Trades: {summary['trades']}")
    print(f"Win Rate: {summary['win_rate']:.1%}")
    print(f"Gross PnL: {summary['gross_pnl']:.2f}%")
    print(f"Avg PnL: {summary['avg_pnl']:.4f}%")
    print(f"Profit Factor: {summary['profit_factor']:.2f}")
    print(f"Avg MAE: {summary['avg_mae']:.4f}%")
    print(f"Avg MFE: {summary['mfe_pct']:.4f}%" if 'mfe_pct' in summary else "")
    
    # Exit reason breakdown
    print("\n=== EXIT REASONS ===")
    for reason in trades_df['exit_reason'].unique():
        count = (trades_df['exit_reason'] == reason).sum()
        pnl = trades_df[trades_df['exit_reason'] == reason]['pnl_pct'].sum()
        print(f"  {reason}: {count} trades, PnL: {pnl:.2f}%")
    
    # Save results
    trades_df.to_csv('scripts/backtest/9_30_breakout/results/v7_simulation_trades.csv', index=False)
    print("\nSaved: v7_simulation_trades.csv")
