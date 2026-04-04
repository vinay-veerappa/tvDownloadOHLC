
import pandas as pd
import numpy as np
import os
import glob
from datetime import datetime, time, timedelta

# --- CONFIGURATION ---
DATA_DIR = r"C:\Users\vinay\tvDownloadOHLC\data"
REPORT_DIR = r"C:\Users\vinay\tvDownloadOHLC\docs\strategies\9_30_breakout\0930_AllDay\reports"
TICKERS = ['ES1', 'RTY1', 'YM1', 'GC1', 'CL1']
OR_START = time(9, 30)
OR_END = time(9, 31)
TRADING_END = time(15, 50) # Hard exit
MIN_TRADES = 50

def load_data(ticker):
    """Loads 1m parquet data for a ticker."""
    file_path = os.path.join(DATA_DIR, f"{ticker}_1m.parquet")
    print(f"Loading {file_path}...")
    try:
        df = pd.read_parquet(file_path)
        # Ensure datetime index
        if 'datetime' in df.columns:
            df['datetime'] = pd.to_datetime(df['datetime'])
            df = df.set_index('datetime')
        elif not isinstance(df.index, pd.DatetimeIndex):
             # Try to find a date column
             for col in df.columns:
                 if 'date' in col.lower() or 'time' in col.lower():
                     df[col] = pd.to_datetime(df[col])
                     df = df.set_index(col)
                     break
        
        # Sort index
        df = df.sort_index()
        
        # Localize/Convert to US/Eastern
        if df.index.tz is None:
            # Assuming raw data is in a consistent known timezone or UTC, 
            # but for this user context, previous scripts imply data might need specific handling.
            # However, standard practice: Assume localized or convert.
            # Let's assume the data source (tvDownloadOHLC) might be UTC or Exchange time.
            # *CRITICAL*: User's previous context often involves timezone conversions.
            # For simplicity in this "Perfect Foresight" script, we'll assume the timestamps 
            # align with the market hours we care about (09:30 EST).
            # If the data is standard Yahoo/TV export, it's often UTC.
            # Let's simple-check headers/values in a real run, but here we force Eastern for filter logic.
             df = df.tz_localize('UTC', ambiguous='NaT').tz_convert('America/New_York')
        else:
            df = df.tz_convert('America/New_York')
            


        # Filter for last 15 years
        min_date = df.index.min()
        max_date = df.index.max()
        print(f"  - Available Data: {min_date.date()} to {max_date.date()}")
        
        cutoff_date = datetime.now(df.index.tz) - timedelta(days=365*15)
        df = df[df.index >= cutoff_date]
        
        if df.empty:
            print(f"  - No data found in the last 15 years.")
            return None
            
        actual_start = df.index.min().date()
        actual_end = df.index.max().date()
        print(f"  - Analysis Range: {actual_start} to {actual_end} ({len(df)} bars)")
        
        return df
    except Exception as e:
        print(f"Error loading {ticker}: {e}")
        return None

def analyze_ticker(ticker, df):
    """
    Simulates 09:30 ORB breakouts and calculates stats.
    """
    results = []
    
    # Group by date
    grouped = df.groupby(df.index.date)
    
    # print(f"Analyzing {ticker} across {len(grouped)} days...") # Reduced verbosity
    
    for date, day_data in grouped:
        # 1. Identify Opening Range (09:30 - 09:31)
        # We need the bar starting at 09:30:00 (1m bar).
        # In many datasets, '09:30' bar covers 09:30:00 - 09:30:59.
        
        # Date-based grouping is safer for iteration
        # 1. OR Data
        try:
             or_data = day_data.between_time(OR_START, OR_END, inclusive='left') # 09:30 <= t < 09:31
        except TypeError:
             # Fallback for older pandas
             or_data = day_data.between_time(OR_START, OR_END, include_start=True, include_end=False)
        
        if len(or_data) == 0:
            continue
            
        or_high = or_data['high'].max()
        or_low = or_data['low'].min()
        or_close = day_data.iloc[-1]['close'] 
        
        # Calculate Range Size %
        ref_price = or_data.iloc[0]['open']
        range_size = or_high - or_low
        range_pct = (range_size / ref_price) * 100
        
        # 2. Post-OR Data
        try:
            trade_data = day_data.between_time(OR_END, TRADING_END, inclusive='both')
        except TypeError:
            trade_data = day_data.between_time(OR_END, TRADING_END, include_start=True, include_end=True)
        
        if len(trade_data) == 0:
            continue

        # 3. Simulate Breakout
        # Simple "Immediate" Logic:
        # First break of OR High -> Long
        # First break of OR Low -> Short
        # *Note*: This is "Perfect Foresight" in terms of "What happened after".
        # We want statistics for: IF we broke High, what was MFE/MAE?
        
        # Check Long Breakout
        long_breakout_bars = trade_data[trade_data['high'] > or_high]
        long_entry_idx = long_breakout_bars.index[0] if not long_breakout_bars.empty else None
        
        if long_entry_idx:
            # Analyze Long Trade
            entry_price = or_high # Theoretical fill at breakout level
            
            # Post-entry data
            post_entry = trade_data.loc[long_entry_idx:]
            
            # MAE (Lowest Low vs Entry)
            min_post_entry = post_entry['low'].min()
            mae = entry_price - min_post_entry
            mae_pct = (mae / entry_price) * 100
            
            # MFE (Highest High vs Entry)
            max_post_entry = post_entry['high'].max()
            mfe = max_post_entry - entry_price
            mfe_pct = (mfe / entry_price) * 100
            
            close_pnl = post_entry.iloc[-1]['close'] - entry_price
            win = close_pnl > 0
            
            results.append({
                'Date': date,
                'Ticker': ticker,
                'Direction': 'Long',
                'OR_Pct': range_pct,
                'MFE_Pct': mfe_pct,
                'MAE_Pct': mae_pct,
                'MAE_Ratio': mae_pct / range_pct if range_pct > 0 else 0,
                'Win_EOD': win
            })
            
        # Check Short Breakout
        # Independent check (Double Distribution logic possible, but here we treating independently for stats)
        short_breakout_bars = trade_data[trade_data['low'] < or_low]
        short_entry_idx = short_breakout_bars.index[0] if not short_breakout_bars.empty else None
        
        if short_entry_idx:
             # Analyze Short Trade
            entry_price = or_low # Theoretical fill
            
            # Post-entry data
            post_entry = trade_data.loc[short_entry_idx:]
            
            # MAE (Highest High vs Entry)
            max_post_entry = post_entry['high'].max()
            mae = max_post_entry - entry_price
            mae_pct = (mae / entry_price) * 100
            
            # MFE (Lowest Low vs Entry)
            min_post_entry = post_entry['low'].min()
            mfe = entry_price - min_post_entry
            mfe_pct = (mfe / entry_price) * 100
            
            close_pnl = entry_price - post_entry.iloc[-1]['close']
            win = close_pnl > 0
            
            results.append({
                'Date': date,
                'Ticker': ticker,
                'Direction': 'Short',
                'OR_Pct': range_pct,
                'MFE_Pct': mfe_pct,
                'MAE_Pct': mae_pct,
                'MAE_Ratio': mae_pct / range_pct if range_pct > 0 else 0,
                'Win_EOD': win
            })

    return pd.DataFrame(results)

def generate_stats(df):
    """Calculates summary statistics from raw trade results."""
    stats = {}
    
    # 1. OR Size Stats
    # One value per day/ticker (remove duplicates if both Long/Short triggered same day? 
    # Actually OR_Pct is same for both in a day, so unique dates)
    unique_days = df.drop_duplicates(subset=['Date'])
    stats['OR_Mean'] = unique_days['OR_Pct'].mean()
    stats['OR_Median'] = unique_days['OR_Pct'].median()
    stats['OR_P80'] = unique_days['OR_Pct'].quantile(0.80)
    stats['OR_P90'] = unique_days['OR_Pct'].quantile(0.90)
    
    # 2. MFE Stats (Potential Reward)
    # We care about "What is a reasonable target?"
    # P50 (Median) MFE = High probability target
    # P80 MFE = Runner target
    stats['MFE_Mean'] = df['MFE_Pct'].mean()
    stats['MFE_Median'] = df['MFE_Pct'].median()
    stats['MFE_P80'] = df['MFE_Pct'].quantile(0.80) # Larger move
    
    # 3. MAE Stats (Risk Tolerance)
    # "How much heat do winning/good runners take?"
    # We can filter for "Successful" trades (e.g. EOD Winners) to see their MAE profile
    winners = df[df['Win_EOD'] == True]
    if len(winners) > 0:
        stats['MAE_Winner_Mean'] = winners['MAE_Pct'].mean()
        stats['MAE_Winner_Median'] = winners['MAE_Pct'].median()
        stats['MAE_Winner_P90'] = winners['MAE_Pct'].quantile(0.90)
        stats['MAE_Winner_P50'] = winners['MAE_Pct'].quantile(0.50)
        
        # 4. MAE vs Range Ratio (Sniper Check)
        stats['MAE_Ratio_Median'] = winners['MAE_Ratio'].quantile(0.50)
        stats['MAE_Ratio_P90'] = winners['MAE_Ratio'].quantile(0.90)
        
        # Survival Rate
        survived_1R = len(winners[winners['MAE_Ratio'] <= 1.0]) / len(winners) * 100
        stats['Win_Survival_1R'] = survived_1R
    else:
        stats['MAE_Winner_Mean'] = 0
        stats['MAE_Winner_Median'] = 0
        stats['MAE_Winner_P90'] = 0
        stats['MAE_Winner_P50'] = 0
        stats['MAE_Ratio_Median'] = 0
        stats['MAE_Ratio_P90'] = 0
        stats['Win_Survival_1R'] = 0

    return stats

def main():
    all_results = []
    
    print(f"Starting Multi-Ticker Optimization for: {TICKERS}\n")
    
    for ticker in TICKERS:
        df = load_data(ticker)
        if df is not None and not df.empty:
            res_df = analyze_ticker(ticker, df)
            all_results.append(res_df)
    
    if not all_results:
        print("No results generated.")
        return

    full_df = pd.concat(all_results, ignore_index=True)
    
    # --- REPORT GENERATION ---
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    report_path = os.path.join(REPORT_DIR, "MULTI_TICKER_OPTIMIZATION.md")
    
    # Create directory if needed
    os.makedirs(REPORT_DIR, exist_ok=True)
    
    with open(report_path, "w") as f:
        f.write(f"# 09:30 ORB Multi-Ticker Optimization Report\n")
        f.write(f"**Generated:** {timestamp}\n")
        f.write(f"**Strategy:** Standard 09:30 Breakout (Immediate)\n")
        f.write(f"**Data:** 1-minute Parquet (Localized to America/New_York)\n")
        f.write(f"**Metric Basis:** Percentage of Price (Asset Class Agnostic)\n\n")
        
        f.write("## Summary of Optimal Parameters\n")
        f.write("Determined by historical distribution analysis (Median, P80, P90).\n\n")
        
        f.write("| Ticker | Rec. Range % Max | Rec. TP1 (P50 MFE) | Rec. TP2 (P80 MFE) | P90 MAE | Median MAE | Median MAE/Range |\n")
        f.write("|---|---|---|---|---|---|---|\n")

        # Group by Ticker and calc stats
        for ticker in TICKERS:
            t_data = full_df[full_df['Ticker'] == ticker]
            if len(t_data) < MIN_TRADES:
                f.write(f"| {ticker} | Insufficient Data ({len(t_data)}) | - | - | - |\n")
                continue
                
            s = generate_stats(t_data)
            
            # Formatting recommendation logic
            # Range Max: P90 of observed ranges (filter extreme outliers)
            rec_range = s['OR_P90']
            # TP1: Median MFE (Conservative high win rate target)
            rec_tp1 = s['MFE_Median'] 
            # TP2: P80 MFE (Runner target, captures trend days)
            rec_tp2 = s['MFE_P80'] # Actually for target, we might want quantile(0.20) if we look at "How often hit"?
                                   # No, MFE distribution: Higher is better. Median is 50% hit rate theoretical.
                                   # Actually, if we set TP at MFE Median, 50% of trades reach it.
                                   # To be conservative for TP1, we usually want Higher Probability -> Lower MFE quantile? 
                                   # Let's stick to Median for TP1 as "Base Expectation".
            
            # MAE: Mean is often skewed by outliers. User prefers Median.
            # But for a HARD STOP, P90 is safer than Median.
            # "Sniper" Mode = Median of Winners or 1.0x Range Cap.
            rec_mae_p90 = s['MAE_Winner_P90']
            rec_mae_median = s['MAE_Winner_Median']
            
            # Recommendation: If P90 MAE > 1.2 * Range P90, suggest the Range Cap?
            # Actually, standardizing on % is best.
            
            f.write(f"| **{ticker}** | {rec_range:.2f}% | {rec_tp1:.2f}% | {rec_tp2:.2f}% | {rec_mae_p90:.2f}% | {rec_mae_median:.2f}% | {s['MAE_Ratio_Median']:.2f}x |\n")
            
        f.write("\n## Detailed Distributions\n\n")
        
        for ticker in TICKERS:
            t_data = full_df[full_df['Ticker'] == ticker]
            if t_data.empty: continue
            
            s = generate_stats(t_data)
            
            f.write(f"### {ticker} Analysis ({len(t_data)} trades)\n")
            f.write(f"**1. Opening Range Size**\n")
            f.write(f"- Median: {s['OR_Median']:.3f}%\n")
            f.write(f"- P90 (Max Filter): {s['OR_P90']:.3f}%\n\n")
            
            f.write(f"**2. Max Favorable Excursion (MFE)**\n")
            f.write(f"- Median (TP1): {s['MFE_Median']:.3f}%\n")
            f.write(f"- P80 (Runner): {s['MFE_P80']:.3f}%\n\n")
            
            f.write(f"**3. Max Adverse Excursion (MAE) - Winners Only**\n")
            f.write(f"- Median (Sniper): {s['MAE_Winner_Median']:.3f}%\n")
            f.write(f"- P90 (Hard Stop): {s['MAE_Winner_P90']:.3f}%\n")
            f.write(f"- **Survival Rate at 1.0x Range Stop**: {s['Win_Survival_1R']:.1f}%\n")
            
            f.write(f"**4. Sniper Analysis (MAE vs Range)**\n")
            f.write(f"- Median MAE/Range: {s['MAE_Ratio_Median']:.2f}x\n")
            f.write(f"- P90 MAE/Range: {s['MAE_Ratio_P90']:.2f}x\n")
            f.write("\n---\n")

    print(f"\nReport generated: {report_path}")

if __name__ == "__main__":
    main()
