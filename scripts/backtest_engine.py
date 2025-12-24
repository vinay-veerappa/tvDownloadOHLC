"""
Backtesting Engine - Core backtesting framework with multi-timeframe support

This module provides the main backtesting engine that:
- Loads OHLCV data from Parquet files
- Manages positions and calculates P&L, MAE, MFE
- Supports multiple IB timeframes (15min, 30min, 45min, 60min)
- Tracks detailed statistics for each trade
- Integrates ICT concepts for entry refinement
"""

import pandas as pd
import numpy as np
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import pytz


class BacktestEngine:
    """Main backtesting engine for strategy execution"""
    
    def __init__(
        self,
        ticker: str,
        timeframe: str = "5m",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        data_dir: str = "data",
        initial_capital: float = 100000.0,
        commission: float = 2.50,  # Per contract per side
        slippage_ticks: int = 1
    ):
        """
        Initialize backtesting engine
        
        Args:
            ticker: Ticker symbol (e.g., 'NQ1', 'ES1')
            timeframe: Data timeframe (e.g., '5m', '15m')
            start_date: Start date for backtest (YYYY-MM-DD)
            end_date: End date for backtest (YYYY-MM-DD)
            data_dir: Directory containing Parquet files
            initial_capital: Starting account balance
            commission: Commission per contract per side
            slippage_ticks: Slippage in ticks
        """
        self.ticker = ticker
        self.timeframe = timeframe
        self.start_date = start_date
        self.end_date = end_date
        self.data_dir = Path(data_dir)
        self.initial_capital = initial_capital
        self.commission = commission
        self.slippage_ticks = slippage_ticks
        
        # Timezone handling
        self.tz_et = pytz.timezone('US/Eastern')
        self.tz_utc = pytz.UTC
        
        # Data
        self.data: Optional[pd.DataFrame] = None
        self.current_bar_index: int = 0
        
        # Position tracking
        self.position: Optional[Dict] = None
        self.trades: List[Dict] = []
        self.equity_curve: List[float] = []
        self.current_equity: float = initial_capital
        
        # Tick values for common futures
        self.tick_values = {
            'NQ1': 5.0,   # $5 per tick
            'ES1': 12.5,  # $12.50 per tick
            'YM1': 5.0,   # $5 per tick
            'RTY1': 5.0,  # $5 per tick
            'CL1': 10.0,  # $10 per tick
            'GC1': 10.0   # $10 per tick
        }
        
    def load_data(self) -> pd.DataFrame:
        """Load data from Parquet file"""
        parquet_file = self.data_dir / f"{self.ticker}_{self.timeframe}.parquet"
        
        if not parquet_file.exists():
            raise FileNotFoundError(f"Data file not found: {parquet_file}")
        
        print(f"Loading data from {parquet_file}...")
        df = pd.read_parquet(parquet_file)
        
        # Ensure datetime index
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)
        
        # Convert to ET timezone if not already
        if df.index.tz is None:
            df.index = df.index.tz_localize('UTC').tz_convert(self.tz_et)
        elif df.index.tz != self.tz_et:
            df.index = df.index.tz_convert(self.tz_et)
        
        # Filter by date range
        if self.start_date:
            df = df[df.index >= self.start_date]
        if self.end_date:
            df = df[df.index <= self.end_date]
        
        print(f"Loaded {len(df)} bars from {df.index[0]} to {df.index[-1]}")
        self.data = df
        return df
    
    def calculate_ib_range(
        self,
        date: pd.Timestamp,
        ib_duration_minutes: int = 60
    ) -> Optional[Dict]:
        """
        Calculate Initial Balance for a given date and duration
        
        Args:
            date: Trading date
            ib_duration_minutes: IB duration (15, 30, 45, 60 minutes)
            
        Returns:
            Dictionary with IB metrics or None if insufficient data
        """
        # Define IB window (9:30 - 9:30+duration)
        ib_start = pd.Timestamp.combine(date.date(), time(9, 30)).tz_localize(self.tz_et)
        ib_end = ib_start + timedelta(minutes=ib_duration_minutes)
        
        # Get bars within IB window
        ib_bars = self.data[(self.data.index >= ib_start) & (self.data.index < ib_end)]
        
        if len(ib_bars) == 0:
            return None
        
        # Calculate IB metrics
        ib_high = ib_bars['high'].max()
        ib_low = ib_bars['low'].min()
        ib_range = ib_high - ib_low
        ib_open = ib_bars.iloc[0]['open']
        ib_close = ib_bars.iloc[-1]['close']
        ib_midpoint = (ib_high + ib_low) / 2
        
        # Calculate where IB closed within the range (0-100%)
        if ib_range > 0:
            ib_close_position = ((ib_close - ib_low) / ib_range) * 100
        else:
            ib_close_position = 50.0
        
        # Determine expected break direction
        expected_break = 'HIGH' if ib_close_position > 50 else 'LOW'
        
        # Find when high and low were set
        ib_high_time = ib_bars[ib_bars['high'] == ib_high].index[0]
        ib_low_time = ib_bars[ib_bars['low'] == ib_low].index[0]
        
        return {
            'date': date.date(),
            'ib_duration_min': ib_duration_minutes,
            'ib_start': ib_start,
            'ib_end': ib_end,
            'ib_high': ib_high,
            'ib_low': ib_low,
            'ib_range': ib_range,
            'ib_range_pct': (ib_range / ib_open) * 100,
            'ib_open': ib_open,
            'ib_close': ib_close,
            'ib_midpoint': ib_midpoint,
            'ib_close_position': ib_close_position,
            'expected_break': expected_break,
            'ib_high_time': ib_high_time,
            'ib_low_time': ib_low_time,
            'ib_bias': 'BEARISH' if ib_high_time < ib_low_time else 'BULLISH'
        }
    
    def check_ib_break(
        self,
        ib_data: Dict,
        current_time: pd.Timestamp,
        current_high: float,
        current_low: float
    ) -> Optional[str]:
        """
        Check if IB has been broken
        
        Returns:
            'HIGH' if high broken, 'LOW' if low broken, None if no break
        """
        if current_time <= ib_data['ib_end']:
            return None
        
        if current_high > ib_data['ib_high']:
            return 'HIGH'
        elif current_low < ib_data['ib_low']:
            return 'LOW'
        
        return None
    
    def enter_position(
        self,
        bar: pd.Series,
        direction: str,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        context: Dict
    ):
        """Enter a new position"""
        # Apply slippage
        tick_value = self.tick_values.get(self.ticker, 5.0)
        slippage = self.slippage_ticks * (tick_value / 5.0)  # Adjust for tick size
        
        if direction == 'LONG':
            entry_price += slippage
        else:
            entry_price -= slippage
        
        self.position = {
            'entry_time': bar.name,
            'entry_price': entry_price,
            'direction': direction,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'highest_price': entry_price,
            'lowest_price': entry_price,
            'mae': 0.0,  # Maximum Adverse Excursion
            'mfe': 0.0,  # Maximum Favorable Excursion
            'context': context.copy()
        }
    
    def update_position(self, bar: pd.Series):
        """Update position MAE/MFE and check for exit"""
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
            # MAE: worst drawdown from entry
            adverse_move = ((self.position['lowest_price'] - entry_price) / entry_price) * 100
            self.position['mae'] = min(self.position['mae'], adverse_move)
            
            # MFE: best profit from entry
            favorable_move = ((self.position['highest_price'] - entry_price) / entry_price) * 100
            self.position['mfe'] = max(self.position['mfe'], favorable_move)
        else:  # SHORT
            # MAE: worst drawdown from entry
            adverse_move = ((entry_price - self.position['highest_price']) / entry_price) * 100
            self.position['mae'] = min(self.position['mae'], adverse_move)
            
            # MFE: best profit from entry
            favorable_move = ((entry_price - self.position['lowest_price']) / entry_price) * 100
            self.position['mfe'] = max(self.position['mfe'], favorable_move)
        
        # Check for exit conditions
        exit_price = None
        exit_reason = None
        
        # Stop loss hit
        if direction == 'LONG' and low <= self.position['stop_loss']:
            exit_price = self.position['stop_loss']
            exit_reason = 'SL'
        elif direction == 'SHORT' and high >= self.position['stop_loss']:
            exit_price = self.position['stop_loss']
            exit_reason = 'SL'
        
        # Take profit hit
        if direction == 'LONG' and high >= self.position['take_profit']:
            exit_price = self.position['take_profit']
            exit_reason = 'TP'
        elif direction == 'SHORT' and low <= self.position['take_profit']:
            exit_price = self.position['take_profit']
            exit_reason = 'TP'
        
        # Time-based exits
        current_time = bar.name.time()
        
        # Exit at 3:30 PM ET
        if current_time >= time(15, 30) and exit_price is None:
            exit_price = bar['close']
            exit_reason = 'TIME_330PM'
        
        # Hard exit at 4:00 PM ET
        if current_time >= time(16, 0) and exit_price is None:
            exit_price = bar['close']
            exit_reason = 'EOD'
        
        # Execute exit if triggered
        if exit_price is not None:
            self.exit_position(bar, exit_price, exit_reason)
    
    def exit_position(self, bar: pd.Series, exit_price: float, exit_reason: str):
        """Exit current position and record trade"""
        if self.position is None:
            return
        
        # Apply slippage
        tick_value = self.tick_values.get(self.ticker, 5.0)
        slippage = self.slippage_ticks * (tick_value / 5.0)
        
        if self.position['direction'] == 'LONG':
            exit_price -= slippage
        else:
            exit_price += slippage
        
        # Calculate P&L
        if self.position['direction'] == 'LONG':
            pnl_pct = ((exit_price - self.position['entry_price']) / self.position['entry_price']) * 100
        else:
            pnl_pct = ((self.position['entry_price'] - exit_price) / self.position['entry_price']) * 100
        
        # Determine result
        if pnl_pct > 0.01:
            result = 'WIN'
        elif pnl_pct < -0.01:
            result = 'LOSS'
        else:
            result = 'BREAKEVEN'
        
        # Calculate hold duration
        hold_duration = (bar.name - self.position['entry_time']).total_seconds() / 60  # minutes
        
        # Record trade
        trade = {
            'entry_time': self.position['entry_time'],
            'entry_price': self.position['entry_price'],
            'exit_time': bar.name,
            'exit_price': exit_price,
            'direction': self.position['direction'],
            'pnl_pct': pnl_pct,
            'mae_pct': self.position['mae'],
            'mfe_pct': self.position['mfe'],
            'exit_reason': exit_reason,
            'result': result,
            'hold_duration_min': hold_duration,
            **self.position['context']
        }
        
        self.trades.append(trade)
        
        # Update equity
        # For simplicity, assume 1 contract and use tick value
        tick_value = self.tick_values.get(self.ticker, 5.0)
        pnl_dollars = (pnl_pct / 100) * self.position['entry_price'] * (tick_value / 0.25)
        pnl_dollars -= (2 * self.commission)  # Entry + Exit
        
        self.current_equity += pnl_dollars
        self.equity_curve.append(self.current_equity)
        
        # Clear position
        self.position = None
    
    def get_performance_metrics(self) -> Dict:
        """Calculate overall performance metrics"""
        if len(self.trades) == 0:
            return {}
        
        df_trades = pd.DataFrame(self.trades)
        
        total_trades = len(df_trades)
        wins = len(df_trades[df_trades['result'] == 'WIN'])
        losses = len(df_trades[df_trades['result'] == 'LOSS'])
        
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
        
        avg_win = df_trades[df_trades['result'] == 'WIN']['pnl_pct'].mean() if wins > 0 else 0
        avg_loss = df_trades[df_trades['result'] == 'LOSS']['pnl_pct'].mean() if losses > 0 else 0
        
        total_pnl = df_trades['pnl_pct'].sum()
        
        # Profit factor
        gross_profit = df_trades[df_trades['pnl_pct'] > 0]['pnl_pct'].sum()
        gross_loss = abs(df_trades[df_trades['pnl_pct'] < 0]['pnl_pct'].sum())
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 0
        
        # Average MAE/MFE
        avg_mae = df_trades['mae_pct'].mean()
        avg_mfe = df_trades['mfe_pct'].mean()
        
        return {
            'total_trades': total_trades,
            'wins': wins,
            'losses': losses,
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'total_pnl_pct': total_pnl,
            'profit_factor': profit_factor,
            'avg_mae': avg_mae,
            'avg_mfe': avg_mfe,
            'final_equity': self.current_equity,
            'total_return_pct': ((self.current_equity - self.initial_capital) / self.initial_capital) * 100
        }
    
    def export_trades_to_csv(self, output_path: str):
        """Export trades to CSV following BACKTEST_STANDARDS.md format"""
        if len(self.trades) == 0:
            print("No trades to export")
            return
        
        df = pd.DataFrame(self.trades)
        
        # Reorder columns to match standards
        column_order = [
            'date', 'day_of_week', 'ib_duration_min', 'ib_range_pct', 'ib_close_position',
            'expected_break', 'entry_time', 'entry_price', 'direction',
            'result', 'pnl_pct', 'mae_pct', 'mfe_pct', 'exit_reason',
            'exit_time', 'exit_price', 'hold_duration_min'
        ]
        
        # Add any columns that exist in df
        for col in df.columns:
            if col not in column_order:
                column_order.append(col)
        
        # Reorder
        df = df[[col for col in column_order if col in df.columns]]
        
        # Export
        df.to_csv(output_path, index=False)
        print(f"Exported {len(df)} trades to {output_path}")
