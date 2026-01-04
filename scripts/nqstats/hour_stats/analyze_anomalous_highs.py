
import pandas as pd
import numpy as np
import os
import argparse
from datetime import time, timedelta

# --- Configuration ---
DATA_DIR = 'data'
START_YEAR = 2015

def load_data(ticker):
    path = f"{DATA_DIR}/{ticker}_1m.parquet"
    if not os.path.exists(path): return None
    df = pd.read_parquet(path)
    if 'time' in df.columns:
        df['datetime'] = pd.to_datetime(df['time'], unit='s', utc=True)
        df.set_index('datetime', inplace=True)
    df = df.tz_convert('US/Eastern')
    return df[df.index.year >= START_YEAR]

def analyze_anomalous_highs(df):
    print("Resampling to 1H...")
    
    # 1. Resample to 1H
    h_df = df.resample('1h').agg({
        'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'
    })
    h_df.dropna(inplace=True)
    
    h_df['Color'] = np.where(h_df['close'] > h_df['open'], 'Green', 'Red')
    h_df['Prev_Color'] = h_df['Color'].shift(1)
    
    # Analyze detailed timing
    stats = []
    
    print("Analyzing High Timing...")
    
    for idx, row in h_df.iterrows():
        # Focus on RTH 09:00 - 16:00
        if idx.hour < 9 or idx.hour > 16: continue
        
        start_time = idx
        end_time = start_time + timedelta(hours=1)
        
        try:
            slice_df = df.loc[start_time:end_time - timedelta(minutes=1)]
        except: continue
        if slice_df.empty: continue
        
        # Quarter Calculation
        total_mins = len(slice_df)
        q_len = total_mins / 4.0
        t_high = slice_df['high'].idxmax()
        mins_to_high = (t_high - start_time).total_seconds() / 60
        high_quarter = int(mins_to_high // q_len)
        high_quarter = min(max(high_quarter, 0), 3)
        
        # ORB 5m Bias
        orb_end = start_time + timedelta(minutes=5)
        orb_slice = slice_df.loc[:orb_end - timedelta(minutes=1)]
        orb_bullish = False
        if not orb_slice.empty:
            if orb_slice.iloc[-1]['close'] > orb_slice.iloc[0]['open']: orb_bullish = True
            
        # Outcome Metric: Close Strength (How close to High did we close?)
        # 1.0 = Closed on High. 0.0 = Closed on Low.
        range_val = row['high'] - row['low']
        close_strength = 0.5
        if range_val > 0:
            close_strength = (row['close'] - row['low']) / range_val
            
        stats.append({
            'Hour': idx.hour,
            'High_Quarter': high_quarter,
            'Prev_Green': (row['Prev_Color'] == 'Green'),
            'ORB_Bullish': orb_bullish,
            'Close_Strength': close_strength,
            'Is_Green': (row['Color'] == 'Green')
        })
        
    stats_df = pd.DataFrame(stats)
    
    # Comparison: Baseline (Q1 High) vs Anomaly (Q2, Q3, Q4 High)
    
    # We want to know:
    # 1. If High is NOT Q1, is it likely a Strong Close? (Expansion)
    # 2. What characteristics precede a Non-Q1 High?
    
    print("\n--- Comparative Analysis: Q1 High vs Non-Q1 High ---")
    
    # Split
    q1_df = stats_df[stats_df['High_Quarter'] == 0]
    non_q1_df = stats_df[stats_df['High_Quarter'] > 0]
    
    summary = []
    
    # 1. Outcome Strength
    summary.append({
        'Metric': 'Average Close Strength (0-1)',
        'Q1_High (Standard)': q1_df['Close_Strength'].mean(),
        'Non-Q1_High (Expansion)': non_q1_df['Close_Strength'].mean()
    })
    
    # 2. Probability of Green Candle
    summary.append({
        'Metric': 'Prob of Green Candle',
        'Q1_High (Standard)': q1_df['Is_Green'].mean(),
        'Non-Q1_High (Expansion)': non_q1_df['Is_Green'].mean()
    })
    
    # 3. Precursors (Backwards Probability)
    # i.e. Given ORB Bullish, Prob of Non-Q1 High?
    
    print(pd.DataFrame(summary).round(3).to_string(index=False))
    
    print("\n--- Conditional Probabilities (What predicts Expansion?) ---")
    
    cond_summary = []
    
    # Impact of Previous Color
    # If Prev Green -> Prob High is Non-Q1?
    prev_green_df = stats_df[stats_df['Prev_Green'] == True]
    prev_red_df = stats_df[stats_df['Prev_Green'] == False]
    
    p_exp_given_prev_green = prev_green_df['High_Quarter'].apply(lambda x: x>0).mean() if not prev_green_df.empty else 0
    p_exp_given_prev_red = prev_red_df['High_Quarter'].apply(lambda x: x>0).mean() if not prev_red_df.empty else 0
    
    cond_summary.append({'Condition': 'Previous Hour GREEN', 'Prob of Expansion (Late High)': p_exp_given_prev_green})
    cond_summary.append({'Condition': 'Previous Hour RED', 'Prob of Expansion (Late High)': p_exp_given_prev_red})
    
    # Impact of ORB 5m
    orb_bull_df = stats_df[stats_df['ORB_Bullish'] == True]
    orb_bear_df = stats_df[stats_df['ORB_Bullish'] == False]
    
    p_exp_given_orb_bull = orb_bull_df['High_Quarter'].apply(lambda x: x>0).mean() if not orb_bull_df.empty else 0
    p_exp_given_orb_bear = orb_bear_df['High_Quarter'].apply(lambda x: x>0).mean() if not orb_bear_df.empty else 0
    
    cond_summary.append({'Condition': 'ORB 5m BULLISH', 'Prob of Expansion (Late High)': p_exp_given_orb_bull})
    cond_summary.append({'Condition': 'ORB 5m BEARISH', 'Prob of Expansion (Late High)': p_exp_given_orb_bear})

    print(pd.DataFrame(cond_summary).round(3).to_string(index=False))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('ticker', type=str, help='Ticker')
    args = parser.parse_args()
    
    df = load_data(args.ticker)
    if df is not None and not df.empty:
        analyze_anomalous_highs(df)
    else:
        print("No data found.")

if __name__ == "__main__":
    main()
