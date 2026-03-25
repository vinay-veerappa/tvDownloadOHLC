"""
Create annotated chart examples for winning and losing trades

Shows IB levels, Fibonacci retracements, entry/exit points
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from datetime import datetime, timedelta
import numpy as np

# Set style
plt.style.use('dark_background')

def create_trade_chart(trade_data, data_5m, title, filename):
    """Create annotated chart for a single trade"""
    
    # Parse trade data
    date = pd.to_datetime(trade_data['date'])
    entry_time = pd.to_datetime(trade_data['entry_time'])
    exit_time = pd.to_datetime(trade_data['exit_time'])
    direction = trade_data['direction']
    entry_price = trade_data['entry_price']
    pnl = trade_data['pnl_pct']
    mae = trade_data['mae_pct']
    mfe = trade_data['mfe_pct']
    ib_range_pct = trade_data['ib_range_pct']
    
    # Calculate IB levels (9:30-10:15 for 45min IB)
    ib_start = pd.Timestamp.combine(date.date(), pd.Timestamp('09:30').time())
    ib_end = ib_start + pd.Timedelta(minutes=45)
    
    # Get data for the day
    day_start = pd.Timestamp.combine(date.date(), pd.Timestamp('09:00').time())
    day_end = pd.Timestamp.combine(date.date(), pd.Timestamp('16:00').time())
    
    # Filter data (handle timezone)
    if data_5m.index.tz is not None:
        day_start = day_start.tz_localize(data_5m.index.tz)
        day_end = day_end.tz_localize(data_5m.index.tz)
        ib_start = ib_start.tz_localize(data_5m.index.tz)
        ib_end = ib_end.tz_localize(data_5m.index.tz)
    
    day_data = data_5m[(data_5m.index >= day_start) & (data_5m.index <= day_end)].copy()
    
    if len(day_data) == 0:
        print(f"No data for {date.date()}")
        return
    
    # Calculate IB high/low
    ib_data = day_data[(day_data.index >= ib_start) & (day_data.index < ib_end)]
    if len(ib_data) == 0:
        print(f"No IB data for {date.date()}")
        return
    
    ib_high = ib_data['high'].max()
    ib_low = ib_data['low'].min()
    ib_range = ib_high - ib_low
    
    # Calculate Fibonacci levels
    if direction == 'LONG':
        # For long, breakout was above IB high
        # Find the high after IB break
        post_ib = day_data[day_data.index >= ib_end]
        breakout_high = post_ib['high'].max()
        
        # Fibonacci retracements from breakout high back to IB high
        fib_382 = breakout_high - (breakout_high - ib_high) * 0.382
        fib_50 = breakout_high - (breakout_high - ib_high) * 0.50
        fib_618 = breakout_high - (breakout_high - ib_high) * 0.618
    else:
        # For short, breakout was below IB low
        post_ib = day_data[day_data.index >= ib_end]
        breakout_low = post_ib['low'].min()
        
        # Fibonacci retracements from breakout low back to IB low
        fib_382 = breakout_low + (ib_low - breakout_low) * 0.382
        fib_50 = breakout_low + (ib_low - breakout_low) * 0.50
        fib_618 = breakout_low + (ib_low - breakout_low) * 0.618
    
    # Create figure
    fig, ax = plt.subplots(figsize=(16, 10))
    
    # Plot candlesticks
    for idx, row in day_data.iterrows():
        color = 'lime' if row['close'] >= row['open'] else 'red'
        
        # Body
        body_height = abs(row['close'] - row['open'])
        body_bottom = min(row['open'], row['close'])
        rect = patches.Rectangle(
            (idx, body_bottom), timedelta(minutes=3), body_height,
            linewidth=0, facecolor=color, alpha=0.8
        )
        ax.add_patch(rect)
        
        # Wicks
        ax.plot([idx, idx], [row['low'], row['high']], color=color, linewidth=0.5, alpha=0.6)
    
    # IB box
    ib_box = patches.Rectangle(
        (ib_start, ib_low), ib_end - ib_start, ib_range,
        linewidth=2, edgecolor='cyan', facecolor='cyan', alpha=0.15, label='Initial Balance'
    )
    ax.add_patch(ib_box)
    
    # IB levels
    ax.axhline(ib_high, color='cyan', linestyle='--', linewidth=1.5, alpha=0.7, label='IB High')
    ax.axhline(ib_low, color='cyan', linestyle='--', linewidth=1.5, alpha=0.7, label='IB Low')
    
    # Fibonacci levels
    ax.axhline(fib_382, color='yellow', linestyle=':', linewidth=2, alpha=0.8, label='Fib 38.2%')
    ax.axhline(fib_50, color='orange', linestyle=':', linewidth=1.5, alpha=0.6, label='Fib 50%')
    ax.axhline(fib_618, color='magenta', linestyle=':', linewidth=1.5, alpha=0.6, label='Fib 61.8%')
    
    # Entry point
    entry_color = 'lime' if pnl > 0 else 'red'
    ax.scatter(entry_time, entry_price, s=300, marker='^' if direction == 'LONG' else 'v',
               color=entry_color, edgecolors='white', linewidths=2, zorder=10, label='Entry')
    
    # Exit point (approximate)
    if 'exit_price' in trade_data and not pd.isna(trade_data['exit_price']):
        exit_price = trade_data['exit_price']
        ax.scatter(exit_time, exit_price, s=300, marker='X',
                   color=entry_color, edgecolors='white', linewidths=2, zorder=10, label='Exit')
    
    # Annotations
    annotation_text = f"""
{direction} Trade - {date.strftime('%Y-%m-%d')}
Entry: {entry_time.strftime('%H:%M')} @ ${entry_price:,.2f}
Exit: {exit_time.strftime('%H:%M')}
PnL: {pnl:.2f}%  |  MAE: {mae:.2f}%  |  MFE: {mfe:.2f}%
IB Range: {ib_range_pct:.2f}%
Result: {'WIN ✓' if pnl > 0 else 'LOSS ✗'}
    """.strip()
    
    ax.text(0.02, 0.98, annotation_text, transform=ax.transAxes,
            fontsize=11, verticalalignment='top',
            bbox=dict(boxstyle='round', facecolor='black', alpha=0.8, edgecolor=entry_color, linewidth=2),
            color='white', family='monospace')
    
    # Formatting
    ax.set_xlabel('Time (ET)', fontsize=12, fontweight='bold')
    ax.set_ylabel('Price ($)', fontsize=12, fontweight='bold')
    ax.set_title(title, fontsize=16, fontweight='bold', pad=20)
    ax.legend(loc='upper right', fontsize=10, framealpha=0.9)
    ax.grid(True, alpha=0.2)
    
    # Format x-axis
    ax.xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter('%H:%M'))
    fig.autofmt_xdate()
    
    plt.tight_layout()
    plt.savefig(filename, dpi=150, bbox_inches='tight', facecolor='#0d1117')
    plt.close()
    print(f"✓ Created: {filename}")


# Load data
data_5m = pd.read_parquet('data/NQ1_5m.parquet')
if data_5m.index.tz is None:
    data_5m.index = data_5m.index.tz_localize('UTC').tz_convert('US/Eastern')
elif data_5m.index.tz != pd.DatetimeTZDtype(tz='US/Eastern'):
    data_5m.index = data_5m.index.tz_convert('US/Eastern')

# Load trade examples
winners = pd.read_csv('docs/strategies/initial_balance_break/winning_trade_examples.csv')
losers = pd.read_csv('docs/strategies/initial_balance_break/losing_trade_examples.csv')

print("="*80)
print("CREATING TRADE VISUALIZATION CHARTS")
print("="*80)

# Create charts for winners
for i, (idx, trade) in enumerate(winners.iterrows(), 1):
    title = f"Winning Trade #{i} - Fib 38.2% Pullback Entry"
    filename = f"docs/strategies/initial_balance_break/charts/winner_{i}_fib382.png"
    create_trade_chart(trade, data_5m, title, filename)

# Create charts for losers
for i, (idx, trade) in enumerate(losers.iterrows(), 1):
    title = f"Losing Trade #{i} - Fib 38.2% Pullback Entry"
    filename = f"docs/strategies/initial_balance_break/charts/loser_{i}_fib382.png"
    create_trade_chart(trade, data_5m, title, filename)

print("\n" + "="*80)
print("ALL CHARTS CREATED!")
print("="*80)
