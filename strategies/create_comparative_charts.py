import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.dates as mdates
import sys
from pathlib import Path
from datetime import datetime
import pytz

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))
from fibonacci_calculator import FibonacciCalculator

def create_comparative_charts(examples_path, output_dir):
    df = pd.read_csv(examples_path)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Cache for data
    data_cache = {}
    
    for idx, row in df.iterrows():
        ticker = row.get('ticker', 'NQ1')
        if ticker not in data_cache:
            data_file = Path(f'data/{ticker}_5m.parquet')
            if not data_file.exists():
                print(f"Data not found for {ticker}")
                continue
            full_data = pd.read_parquet(data_file)
            if full_data.index.tz is None:
                full_data.index = full_data.index.tz_localize('UTC').tz_convert('US/Eastern')
            else:
                full_data.index = full_data.index.tz_convert('US/Eastern')
            data_cache[ticker] = full_data
            
        full_data = data_cache[ticker]
        
        entry_time = pd.to_datetime(row['entry_time'])
        if entry_time.tz is None:
            entry_time = entry_time.tz_localize('UTC').tz_convert('US/Eastern')
        else:
            entry_time = entry_time.tz_convert('US/Eastern')
            
        print(f"Generating chart for {ticker} ({row['config']}) - {row['result']} on {row['date']}")
        
        # Get data for the day
        day_data = full_data[full_data.index.date == entry_time.date()]
        if len(day_data) == 0:
            continue
            
        # Setup plot
        fig, ax = plt.subplots(figsize=(15, 8))
        
        # Plot candlesticks
        for bar_time, bar in day_data.iterrows():
            color = 'green' if bar['close'] >= bar['open'] else 'red'
            ax.plot([bar_time, bar_time], [bar['low'], bar['high']], color='black', linewidth=1)
            rect_width = pd.Timedelta(minutes=4)
            ax.add_patch(patches.Rectangle((bar_time - rect_width/2, min(bar['open'], bar['close'])), 
                                        rect_width, abs(bar['open'] - bar['close']),
                                        color=color, alpha=0.8, zorder=2))

        # IB Box
        ib_start = entry_time.replace(hour=9, minute=30, second=0)
        ib_end = ib_start + pd.Timedelta(minutes=row.get('ib_duration_min', 45))
        ib_data = day_data[ib_start:ib_end]
        if not ib_data.empty:
            ib_high = ib_data['high'].max()
            ib_low = ib_data['low'].min()
            rect = patches.Rectangle((ib_start, ib_low), ib_end - ib_start, ib_high - ib_low,
                                   linewidth=2, edgecolor='cyan', facecolor='cyan', alpha=0.1, label='Initial Balance')
            ax.add_patch(rect)
            
        # Entry line
        ax.axhline(row['entry_price'], color='yellow', linestyle='--', alpha=0.8, label=f"Entry ({row['entry_type']})")
        
        # Exit point
        exit_time = pd.to_datetime(row['exit_time'])
        if exit_time.tz is None:
            exit_time = exit_time.tz_localize('UTC').tz_convert('US/Eastern')
        else:
            exit_time = exit_time.tz_convert('US/Eastern')
            
        exit_color = 'blue' if row['result'] == 'WIN' else 'magenta'
        ax.scatter(exit_time, row['exit_price'], color=exit_color, s=150, zorder=10, label=f"Exit ({row['result']})")
        
        # Limit X-axis to trading hours
        tz_et = pytz.timezone('US/Eastern')
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M', tz=tz_et))
        plt.xlabel('Time (ET)')
        plt.xticks(rotation=45)
        
        # USER REQUEST: Noon marker (12:00 PM EST)
        noon_time = entry_time.replace(hour=12, minute=0, second=0)
        ax.axvline(noon_time, color='orange', linestyle=':', linewidth=2, alpha=0.8, label='12:00 PM Target Exit')
        
        # Annotations
        plt.title(f"{ticker} | {row['config']} | {row['result']} | {row['date']} | PnL: {row['pnl_pct']:.2f}%")
        plt.legend(loc='upper left', fontsize='small')
        plt.grid(True, alpha=0.3)
        
        ax.set_xlim(day_data.index[0], day_data.index[-1])
        
        # Save
        filename = f"{ticker}_{row['config']}_{row['result']}_{row['date']}.png".replace(' ', '_').replace('/', '_')
        plt.tight_layout()
        plt.savefig(output_path / filename)
        plt.close()

if __name__ == "__main__":
    create_comparative_charts('docs/strategies/initial_balance_break/comparative_trade_examples.csv', 
                             'docs/strategies/initial_balance_break/charts/omnibus')
