import pandas as pd
import mplfinance as mpf
import matplotlib.pyplot as plt
from pathlib import Path
from datetime import timedelta

# Constants
DATA_DIR = Path("data")
STATS_DIR = Path("docs/first_presented_stats")
OUTPUT_DIR = STATS_DIR / "charts"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def load_data(ticker="NQ1"):
    path = DATA_DIR / f"{ticker}_1m.parquet"
    print(f"Loading {path}...")
    df = pd.read_parquet(path)
    
    if 'time' in df.columns and not isinstance(df.index, pd.DatetimeIndex):
        df['datetime'] = pd.to_datetime(df['time'], unit='s' if df['time'].iloc[0] > 1e10 else 'ms')
        df = df.set_index('datetime')
    elif 'datetime' in df.columns:
        df = df.set_index('datetime')
        
    if df.index.tz is None:
        df.index = df.index.tz_localize('UTC').tz_convert('America/New_York')
    else:
        df.index = df.index.tz_convert('America/New_York')
        
    df = df.sort_index()
    return df

def generate_charts():
    # 1. Load Trades CSV
    csv_path = STATS_DIR / "NQ1_raw_trades.csv"
    if not csv_path.exists():
        print("Trades CSV not found.")
        return
        
    print("Loading trades...")
    trades = pd.read_csv(csv_path)
    trades['time'] = pd.to_datetime(trades['date']) # The 'date' col in CSV might just be date, wait.
    # The 'setup' dictionary had 'time'. In process_day: result['time'] wasn't strictly added? 
    # Let's check keys added: 'date', 'session_type', 'setup_category', and 'setup_type'
    # BUT 'trigger_time' IS in result. 'exit_time' IS in result.
    # We need the SETUP time to know where to start looking.
    # 'time' was in the setup dict but maybe lost if not explicitly copied to result?
    # Actually, process_day -> result = simulate_trade(setup...) -> result has 'trigger_time'
    
    # We can use 'trigger_time' to center the chart if setup time is missing.
    # 'trigger_time' is a timestamp string in CSV.
    
    trades['trigger_time'] = pd.to_datetime(trades['trigger_time'])
    
    # Filter for Wins (R > 2) and Triggered
    wins = trades[
        (trades['triggered'] == True) & 
        (trades['r_multiple'] > 2.0) &
        (trades['session_start'] != 9) & # Avoid 9am
        (trades['session_start'] != 8)   # Avoid 8am
    ]
    
    if wins.empty:
        print("No suitable winning trades found to chart.")
        return

    # Select Examples
    examples = []
    
    # Categories: Bullish FVG, Bearish FVG, Bullish OB, Bearish OB
    # Distinct hours if possible
    
    targets = [
        {'cat': 'FVG', 'type': 'Bullish FVG', 'h': 16}, # Close/Globex
        {'cat': 'FVG', 'type': 'Bearish FVG', 'h': 3},  # London
        {'cat': 'OB',  'type': 'Bullish OB',  'h': 20}, # Asia
        {'cat': 'OB',  'type': 'Bearish OB',  'h': 10}, # NY AM (Late)
        {'cat': 'OB',  'type': 'Bearish OB',  'h': 11}  # Alt NY AM
    ]
    
    selected_indices = set()
    
    for t in targets:
        # Try to find match
        candidates = wins[
            (wins['setup_category'] == t['cat']) & 
            (wins['setup_type'] == t['type']) & 
            (wins['session_start'] == t['h'])
        ]
        
        if candidates.empty:
            # Fallback to any hour
            candidates = wins[
                (wins['setup_category'] == t['cat']) & 
                (wins['setup_type'] == t['type'])
            ]
            
        if not candidates.empty:
            # Pick latest one
            ex = candidates.sort_values('trigger_time').iloc[-1]
            if ex.name not in selected_indices:
                examples.append(ex)
                selected_indices.add(ex.name)
            
    if not examples:
        print("No examples selected.")
        return

    # 2. Load OHLC Data
    df = load_data()
    
    # 3. Plot
    print(f"Generating {len(examples)} charts...")
    for ex in examples:
        # Window: Trigger - 60m to Exit + 60m
        # If exit_time is valid
        if pd.notna(ex['exit_time']):
            t_entry = ex['trigger_time']
            t_exit = pd.to_datetime(ex['exit_time'])
            
            start_plot = t_entry - timedelta(minutes=45)
            end_plot = t_exit + timedelta(minutes=45)
            
            # Ensure Min window size
            if (end_plot - start_plot) < timedelta(minutes=120):
                end_plot = start_plot + timedelta(minutes=120)
                
            chart_df = df[(df.index >= start_plot) & (df.index <= end_plot)]
            if len(chart_df) < 10: continue
            
            # Setup lines
            # Entry (The price we executed at)
            # Stop (The structural stop)
            # Zone Entry (The setup level)
            
            hlines_dict = dict(
                hlines=[ex['entry_price'], ex['zone_stop'], ex['zone_entry']],
                colors=['blue', 'red', 'gray'],
                linestyle=['-', '-', '--'],
                linewidths=[1.5, 1.5, 1.0],
                alpha=0.8
            )
            
            # Annotations?
            # Markers for trigger and exit
            # We need to construct a marker series matching chart_df index
            
            # Filename
            fname = f"{ex['setup_type'].replace(' ', '_')}_{ex['session_start']:02d}h_{t_entry.strftime('%Y%m%d')}.png"
            
            mc = mpf.make_marketcolors(up='#26a69a', down='#ef5350', wick='inherit', edge='inherit', volume='in')
            s  = mpf.make_mpf_style(marketcolors=mc, base_mpf_style='nightclouds', gridstyle=':')
            
            title = (f"{ex['setup_type']} @ {t_entry.strftime('%H:%M')}\n"
                     f"Entry: {ex['entry_price']:.2f} | Stop: {ex['zone_stop']:.2f} | R: {ex['r_at_exit']:.2f}")
            
            try:
                mpf.plot(
                    chart_df,
                    type='candle',
                    style=s,
                    volume=False,
                    hlines=hlines_dict,
                    title=title,
                    savefig=str(OUTPUT_DIR / fname)
                )
                print(f"Saved: {fname}")
            except Exception as e:
                print(f"Error plotting {fname}: {e}")

if __name__ == "__main__":
    generate_charts()
