
import pandas as pd
import numpy as np
import datetime
import pytz
import os

# Configuration
TRADE_FILE = 'ORB_V7G_-_Hybrid_CME_MINI_MNQ1!_2026-01-07_b8fb2.xlsx' # Run 6 (Verified)
OHLC_FILE = r'c:\Users\vinay\tvDownloadOHLC\data\NQ1_1m.parquet'
TIMEZONE_TRADES = 'US/Eastern'
POINT_VALUE = 2 # MNQ

def load_trades(filepath):
    print(f"Loading trades from {filepath}...")
    xl = pd.ExcelFile(filepath)
    df = pd.read_excel(xl, sheet_name='List of trades')
    
    if 'Trade #' in df.columns:
        trades = []
        grouped = df.groupby('Trade #')
        for trade_id, group in grouped:
            group = group.sort_values('Date and time')
            
            entry_row = group[group['Type'].str.contains('Entry', na=False, case=False)]
            exit_row = group[group['Type'].str.contains('Exit', na=False, case=False)]
            
            if len(entry_row) > 0 and len(exit_row) > 0:
                # Use raw string for time to avoid tz issues initially, then convert
                entry_time = pd.to_datetime(entry_row.iloc[0]['Date and time'])
                exit_time = pd.to_datetime(exit_row.iloc[-1]['Date and time'])
                
                # Exit Price (Last exit price often reflects the final close)
                exit_price = exit_row.iloc[-1]['Price USD']
                
                direction = 'Long' if 'Long' in entry_row.iloc[0]['Type'] else 'Short'
                realized_pnl = group['Net P&L USD'].sum()
                
                trades.append({
                    'Trade #': trade_id,
                    'Entry Time': entry_time,
                    'Exit Time': exit_time,
                    'Exit Price': exit_price,
                    'Direction': direction,
                    'Realized P&L': realized_pnl
                })
        return pd.DataFrame(trades)
    else:
        print("Error: 'Trade #' column not found.")
        return pd.DataFrame()

def load_ohlc(filepath):
    print(f"Loading OHLC data from {filepath}...")
    
    if filepath.endswith('.parquet'):
        df = pd.read_parquet(filepath)
        # Check if index is datetime
        if not isinstance(df.index, pd.DatetimeIndex):
            # Try to find time column
             if 'time' in df.columns:
                 df['datetime'] = pd.to_datetime(df['time'], unit='s', utc=True)
                 df = df.set_index('datetime')
             else:
                 print("Error: Parquet file has no DatetimeIndex and no 'time' column.")
                 exit()
        
        # Ensure timezone is ET
        if df.index.tz is None:
            # Naive. User confirmed Parquet is UTC.
            # Localize to UTC first.
            df.index = df.index.tz_localize('UTC')
            
        # Now convert to Target Timezone (ET)
        df.index = df.index.tz_convert(TIMEZONE_TRADES)
            
        df = df.sort_index()
        return df
        
    else:
        # CSV fallback
        df = pd.read_csv(filepath)
        df['datetime'] = pd.to_datetime(df['time'], unit='s', utc=True)
        df['datetime_et'] = df['datetime'].dt.tz_convert(TIMEZONE_TRADES)
        df = df.set_index('datetime_et').sort_index()
        return df

def calculate_mfe(trades, ohlc):
    print("Calculating Missed Post-Exit MFE...")
    results = []
    
    ohlc_tz = ohlc.index.tz
    
    for idx, trade in trades.iterrows():
        # Clean timezone
        exit_time = trade['Exit Time']
        if exit_time.tzinfo is None:
             exit_time = exit_time.tz_localize(TIMEZONE_TRADES)
        else:
             exit_time = exit_time.tz_convert(TIMEZONE_TRADES)
        
        # EOD Window: Until 16:55 ET (Session close)
        eod_time = exit_time.replace(hour=16, minute=55, second=0, microsecond=0)
        
        if exit_time >= eod_time:
            continue
            
        # Get Price Slice AFTER exit
        # We handle potential timezone mismatch if ohlc is different
        # But load_ohlc converts to TIMEZONE_TRADES (US/Eastern)
        # So comparison is safe.
        
        mask = (ohlc.index > exit_time) & (ohlc.index <= eod_time)
        slice_data = ohlc.loc[mask]
        
        if len(slice_data) == 0:
            continue
            
        exit_price = trade['Exit Price']
        direction = trade['Direction']
        
        missed_pts = 0
        
        if direction == 'Long':
            # Highest price reached after we sold
            max_high = slice_data['high'].max()
            missed_pts = max(0, max_high - exit_price)
        else:
            # Lowest price reached after we bought to cover
            min_low = slice_data['low'].min()
            missed_pts = max(0, exit_price - min_low)
            
        missed_usd_1con = missed_pts * POINT_VALUE
        
        results.append({
            'Trade #': trade['Trade #'],
            'Exit Time': exit_time,
            'Direction': direction,
            'Realized P&L': trade['Realized P&L'],
            'Missed Points': missed_pts,
            'Missed USD (1 Con)': missed_usd_1con
        })
        
    return pd.DataFrame(results)

if __name__ == "__main__":
    if not os.path.exists(TRADE_FILE):
        print(f"File not found: {TRADE_FILE}")
        exit()
        
    trades = load_trades(TRADE_FILE)
    if len(trades) == 0:
        print("No trades loaded.")
        exit()
        
    if not os.path.exists(OHLC_FILE):
        print(f"OHLC File not found: {OHLC_FILE}")
        exit()

    ohlc = load_ohlc(OHLC_FILE)
    mfe_df = calculate_mfe(trades, ohlc)
    
    # Generate Markdown Report
    report = []
    report.append("# Missed MFE Analysis (Run 6)")
    report.append(f"**Generated**: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
    report.append(f"**Trades Analyzed**: {len(mfe_df)}")
    
    avg_missed_usd = mfe_df['Missed USD (1 Con)'].mean()
    avg_missed_pts = mfe_df['Missed Points'].mean()
    total_missed_usd = mfe_df['Missed USD (1 Con)'].sum()
    
    report.append("")
    report.append("## 📊 Summary Statistics")
    report.append(f"- **Avg Points Left on Table**: {avg_missed_pts:.2f} pts")
    report.append(f"- **Avg Missed Profit (1 Contract)**: ${avg_missed_usd:.2f}")
    report.append(f"- **Total Missed Opportunity (If 1 runner held)**: ${total_missed_usd:,.0f}")
    
    # Buckets
    report.append("")
    report.append("## 📦 Distribution of Missed Points")
    buckets = [0, 10, 20, 50, 100, 9999]
    labels = ['0-10 pts', '10-20 pts', '20-50 pts', '50-100 pts', '100+ pts']
    mfe_df['Bucket'] = pd.cut(mfe_df['Missed Points'], bins=buckets, labels=labels, right=False)
    dist = mfe_df['Bucket'].value_counts().sort_index()
    
    report.append("| Range | Count | % of Trades |")
    report.append("|---|---|---|")
    for label, count in dist.items():
        pct = (count / len(mfe_df)) * 100
        report.append(f"| {label} | {count} | {pct:.1f}% |")
        
    # Top Opportunities
    report.append("")
    report.append("## 💎 Top 10 Missed Runners")
    report.append("| Trade # | Exit Time | Dir | Missed Pts | Missed USD (1 Con) |")
    report.append("|---|---|---|---|---|")
    
    top10 = mfe_df.sort_values('Missed Points', ascending=False).head(10)
    for _, row in top10.iterrows():
        report.append(f"| {row['Trade #']} | {row['Exit Time'].strftime('%H:%M')} | {row['Direction']} | {row['Missed Points']:.1f} | ${row['Missed USD (1 Con)']:.0f} |")
        
    with open('Missed_MFE_Analysis.md', 'w', encoding='utf-8') as f:
        f.write('\n'.join(report))
        
    print("Analysis complete. Saved to Missed_MFE_Analysis.md")
    print(mfe_df.head())
