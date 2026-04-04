
import pandas as pd
import numpy as np
import os

def analyze_direction(ticker="NQ1"):
    print(f"--- Starting Bull/Bear & Risk Profile Analysis for {ticker} ---")
    
    # 1. Load Data
    base_dir = "c:/Users/vinay/tvDownloadOHLC/data"
    hourly_path = f"{base_dir}/sessions/{ticker}_hourly.parquet"
    class_path = f"{base_dir}/derived/{ticker}_daily_classification.parquet"
    
    if not os.path.exists(hourly_path) or not os.path.exists(class_path):
        print("Error: Missing data files.")
        return

    # Load Hourly Data
    print(f"Loading Hourly Data: {hourly_path}")
    df_h = pd.read_parquet(hourly_path, columns=['start_time', 'open', 'high', 'low', 'close'])
    # Fix column name & Timezone
    df_h['time'] = pd.to_datetime(df_h['start_time'], utc=True).dt.tz_convert('US/Eastern')
    df_h = df_h.sort_values('time')
    df_h['date'] = df_h['time'].dt.date
    df_h['hour'] = df_h['time'].dt.hour
    
    # Calculate Hourly Volatility (Risk Profile) - RTH Only (9-16)
    df_h['range'] = df_h['high'] - df_h['low']
    df_h['year'] = df_h['time'].dt.year
    vol_by_year = df_h[df_h['hour'].between(9, 16)].groupby('year')['range'].mean().tail(5)
    
    # 2. Extract Consistent Day Open/Close from Hourly
    # Day Open: Open of the 9:00 bar (Best proxy for 9:30 open + pre-market noise, consistent units)
    # Day Close: Close of the 16:00 bar (Settlement)
    
    # Filter for Open
    df_open = df_h[df_h['hour'] == 9].groupby('date', as_index=False)['open'].first().rename(columns={'open': 'daily_open'})
    
    # Filter for Close (Hour 16 usually, but sometimes 15 if half day? taking last RTH bar)
    # Better method: Take last bar between 9 and 16 for each date.
    df_rth = df_h[df_h['hour'].between(9, 16)]
    daily_close = df_rth.groupby('date', as_index=False)['close'].last()
    
    # Merge Open and Close
    daily_ohlc = df_open.merge(daily_close, on='date', how='inner')
    
    # 3. Load Classification
    df_class = pd.read_parquet(class_path, columns=['date', 'type'])
    df_class['date'] = pd.to_datetime(df_class['date'])
    
    # 4. Merge All
    # Note: daily_ohlc['date'] is object (date), df_class['date'] is timestamp
    daily_ohlc['date'] = pd.to_datetime(daily_ohlc['date'])
    
    df = df_class.merge(daily_ohlc, on='date', how='inner')
    
    # 5. Directional Calc
    df['is_green'] = df['close'] > df['daily_open']
    df['prev_close'] = df['close'].shift(1)
    
    # Gap Calculation
    df['gap'] = df['daily_open'] - df['prev_close']
    
    # Gap Thresholds
    # Using 0.25% of price might be better? But price varies 1300 to 18000.
    # Let's use ATR-based or fixed points based on era? 
    # For reporting, let's use a simple > 0 logic for "Green/Red Gap" first.
    # Then bucket by size if needed.
    # Simple: Gap Up > 0, Gap Down < 0.
    df['gap_type'] = np.where(df['gap'] > 5, 'Gap Up', 
                     np.where(df['gap'] < -5, 'Gap Down', 'Flat'))

    # DEBUG: Inspect Data
    print("\n[DEBUG] Data Inspection (Consistent Units):")
    print(df[['date', 'daily_open', 'close', 'prev_close', 'gap', 'gap_type', 'is_green']].head(10))
    
    # 6. Output Analysis
    
    print("\n## Part 1: Risk Profile (Hourly Volatility)")
    print("Average Hourly Range (Points) - Last 5 Years:")
    print(vol_by_year)
    recent_risk = vol_by_year.iloc[-1]
    print(f"> Insight: The average hourly bar is ~{recent_risk:.0f} points.")
    print(f"> Recommendation: A 'Tight Stop' should be at least {recent_risk*0.5:.0f} pts (50% of hourly vol) to avoid noise.")

    print("\n## Part 2: Predicting Direction")
    
    # Gap Stats
    print("\n### 1. Gap Analysis (Fade vs Follow)")
    gap_stats = df.groupby('gap_type')['is_green'].agg(['mean', 'count'])
    gap_stats['mean'] = gap_stats['mean'] * 100
    print(gap_stats.rename(columns={'mean': 'Green Day %'}))
    
    # Sequential Stats
    df['prev_type'] = df['type'].shift(1)
    print("\n### 2. Sequential Context (Yesterday -> Today)")
    seq_stats = df.groupby('prev_type')['is_green'].agg(['mean', 'count'])
    seq_stats['mean'] = seq_stats['mean'] * 100
    print(seq_stats.rename(columns={'mean': 'Green Day %'}))

if __name__ == "__main__":
    analyze_direction("NQ1")
