
import pandas as pd
import numpy as np
import os
from datetime import timedelta

# Config
TRADE_FILE = 'ORB_V7G_-_Hybrid_CME_MINI_MNQ1!_2026-01-07_f3994.xlsx' # Run 5 file
CALENDAR_FILE = r'c:\Users\vinay\tvDownloadOHLC\docs\JournalRequirements\us_complete_economic_calendar_2000_2025.csv'
VVIX_FILE = r'c:\Users\vinay\tvDownloadOHLC\data\TV_OHLC\VIX\CBOE_DLY_VVIX, 1D_beb10.csv'

def load_trades(filepath):
    print(f"Loading trades from {filepath}...")
    if not os.path.exists(filepath):
        print("Trade file not found.")
        return pd.DataFrame()
        
    xl = pd.ExcelFile(filepath)
    df = pd.read_excel(xl, sheet_name='List of trades')
    
    # Process trades
    trades = []
    if 'Trade #' in df.columns:
        grouped = df.groupby('Trade #')
        for trade_id, group in grouped:
            group = group.sort_values('Date and time')
            entry_row = group[group['Type'].str.contains('Entry', na=False, case=False)]
            exit_row = group[group['Type'].str.contains('Exit', na=False, case=False)]
            
            if len(entry_row) > 0:
                entry_time = pd.to_datetime(entry_row.iloc[0]['Date and time'])
                # Localize if naive (TradingView Excel dates are usually local exchange time, so ET)
                if entry_time.tzinfo is None:
                    entry_time = entry_time.tz_localize('US/Eastern')
                
                pnl = group['Net P&L USD'].sum()
                trades.append({
                    'Trade #': trade_id,
                    'Entry Time': entry_time,
                    'Net P&L': pnl,
                    'Result': 'Win' if pnl > 0 else 'Loss'
                })
    return pd.DataFrame(trades)

def load_calendar(filepath):
    print(f"Loading calendar from {filepath}...")
    df = pd.read_csv(filepath)
    # Strip ' ET' from time
    df['time'] = df['time'].str.replace(' ET', '').str.strip()
    # Combine and parse with coerce
    df['datetime'] = pd.to_datetime(df['date'] + ' ' + df['time'], errors='coerce')
    # Drop rows with invalid dates
    df = df.dropna(subset=['datetime'])
    # Localize to ET
    df['datetime'] = df['datetime'].dt.tz_localize('US/Eastern')
    return df

def load_vvix(filepath):
    print(f"Loading VVIX from {filepath}...")
    df = pd.read_csv(filepath)
    # Standard TV export: time (unix), open, high, low, close
    df['date'] = pd.to_datetime(df['time'], unit='s', utc=True).dt.tz_convert('US/Eastern').dt.date
    return df.set_index('date')

def analyze_news(trades, calendar):
    print("\n=== News Impact Analysis ===")
    # Filter for High impact
    high_impact = calendar[calendar['importance'] == 'High']
    
    # Label trades
    trades['News Event'] = None
    trades['News Dist (min)'] = 999
    
    # Slow loop but fine for ~3000 trades
    for idx, trade in trades.iterrows():
        entry = trade['Entry Time']
        day_news = high_impact[high_impact['datetime'].dt.date == entry.date()]
        
        if len(day_news) > 0:
            # Find closest news
            day_news = day_news.copy() # Avoid SettingWithCopyWarning
            day_news.loc[:, 'delta_min'] = (day_news['datetime'] - entry).dt.total_seconds() / 60
            closest = day_news.iloc[day_news['delta_min'].abs().argmin()]
            
            if abs(closest['delta_min']) < 60: # Within 60 mins
                trades.at[idx, 'News Event'] = closest['indicator']
                trades.at[idx, 'News Dist (min)'] = closest['delta_min']
                
    # Stats
    news_trades = trades[trades['News Event'].notnull()]
    clean_trades = trades[trades['News Event'].isnull()]
    
    print(f"Trades within 60min of High Impact News: {len(news_trades)}")
    print(f"Win Rate during News: {len(news_trades[news_trades['Net P&L']>0]) / len(news_trades) * 100:.1f}%")
    print(f"Win Rate Clean: {len(clean_trades[clean_trades['Net P&L']>0]) / len(clean_trades) * 100:.1f}%")
    
    print("\nTop News Losers:")
    print(news_trades[news_trades['Net P&L'] < 0].sort_values('Net P&L').head(5)[['Entry Time', 'News Event', 'News Dist (min)', 'Net P&L']].to_string())

def analyze_vvix(trades, vvix):
    print("\n=== VVIX Regime Analysis ===")
    # Join VVIX
    trades['Date'] = trades['Entry Time'].dt.date
    trades['VVIX'] = trades['Date'].map(vvix['close'])
    
    # Buckets
    bins = [0, 80, 90, 100, 110, 120, 150, 200]
    labels = ['<80', '80-90', '90-100', '100-110', '110-120', '120-150', '>150']
    trades['VVIX Bucket'] = pd.cut(trades['VVIX'], bins=bins, labels=labels)
    
    # Group stats
    stats = trades.groupby('VVIX Bucket').agg({
        'Net P&L': ['count', 'sum', 'mean'],
        'Result': lambda x: (x == 'Win').mean() * 100
    })
    stats.columns = ['Count', 'Total P&L', 'Avg P&L', 'Win Rate %']
    print(stats)

if __name__ == "__main__":
    trades = load_trades(TRADE_FILE)
    if len(trades) > 0:
        if os.path.exists(CALENDAR_FILE):
            calendar = load_calendar(CALENDAR_FILE)
            analyze_news(trades, calendar)
        else:
            print("Calendar file missing.")
            
        if os.path.exists(VVIX_FILE):
            vvix = load_vvix(VVIX_FILE)
            analyze_vvix(trades, vvix)
        else:
            print("VVIX file missing.")
