"""
Regime Analysis: Why the strategy broke 2023-2026

Compares strategy performance across periods to identify regime shifts
"""

import pandas as pd
import numpy as np
from pathlib import Path

def load_analysis_data(ticker):
    """Load the deep analysis CSV"""
    csv_path = Path(f'scripts/nqstats/results/deep_analysis_{ticker}_2020_2025.csv')
    df = pd.read_csv(csv_path)
    df['Date'] = pd.to_datetime(df['Date'])
    
    # Parse boolean columns
    df['Prediction_Correct'] = df['Prediction_Correct'].astype(str).str.lower().isin(['true', '1', 'yes'])
    
    return df

def analyze_by_period(df, ticker):
    """Break down accuracy by year"""
    
    df['Year'] = df['Date'].dt.year
    
    print(f"\n{'='*80}")
    print(f"{ticker}: ACCURACY BY YEAR")
    print(f"{'='*80}\n")
    
    yearly_stats = []
    for year in sorted(df['Year'].unique()):
        year_df = df[df['Year'] == year]
        trades = len(year_df)
        wins = year_df['Prediction_Correct'].sum()
        accuracy = (wins / trades * 100) if trades > 0 else 0
        
        print(f"{year}: {accuracy:5.1f}% ({wins:3d}/{trades:4d} trades)")
        yearly_stats.append({'Year': year, 'Accuracy': accuracy, 'Trades': trades})
    
    return pd.DataFrame(yearly_stats)

def analyze_by_period_ranges(df, ticker):
    """Check specific date ranges"""
    
    print(f"\n{'='*80}")
    print(f"{ticker}: ACCURACY BY PERIOD")
    print(f"{'='*80}\n")
    
    periods = [
        ('2020-2021', '2020-01-01', '2021-12-31'),
        ('2022', '2022-01-01', '2022-12-31'),
        ('2023-2024', '2023-01-01', '2024-12-31'),
        ('2025-Mar2026', '2025-01-01', '2026-03-31'),
    ]
    
    for label, start, end in periods:
        period_df = df[(df['Date'] >= start) & (df['Date'] <= end)]
        if len(period_df) == 0:
            print(f"{label:15s}: NO DATA")
            continue
        
        trades = len(period_df)
        wins = period_df['Prediction_Correct'].sum()
        accuracy = (wins / trades * 100) if trades > 0 else 0
        
        print(f"{label:15s}: {accuracy:5.1f}% ({wins:3d}/{trades:4d} trades) | Avg Range: {period_df['AM_Range'].mean():.1f} pts")

def analyze_market_conditions(df, ticker):
    """Check if market conditions changed"""
    
    print(f"\n{'='*80}")
    print(f"{ticker}: MARKET CONDITION CHANGES")
    print(f"{'='*80}\n")
    
    df['Year'] = df['Date'].dt.year
    
    for year in sorted(df['Year'].unique()):
        year_df = df[df['Year'] == year]
        
        avg_range = year_df['AM_Range'].mean()
        avg_gap = year_df['Time_Gap_Minutes'].mean()
        bull_trades = (year_df['Expected_Dir'] == 'BULL').sum()
        bear_trades = (year_df['Expected_Dir'] == 'BEAR').sum()
        bull_acc = year_df[year_df['Expected_Dir'] == 'BULL']['Prediction_Correct'].mean() * 100
        bear_acc = year_df[year_df['Expected_Dir'] == 'BEAR']['Prediction_Correct'].mean() * 100
        
        print(f"{year}:")
        print(f"  Avg AM Range: {avg_range:6.1f} pts")
        print(f"  Avg Time Gap: {avg_gap:6.1f} min")
        print(f"  BULL acc: {bull_acc:5.1f}% ({bull_trades} trades) | BEAR acc: {bear_acc:5.1f}% ({bear_trades} trades)")
        print()

def main():
    """Run regime analysis"""
    
    for ticker in ['NQ1', 'ES1']:
        df = load_analysis_data(ticker)
        
        yearly = analyze_by_period(df, ticker)
        analyze_by_period_ranges(df, ticker)
        analyze_market_conditions(df, ticker)
        
        # Key question: when did it break?
        print(f"\n{ticker}: WHEN DID EDGE DISAPPEAR?")
        print(f"{'='*80}")
        df['Year'] = df['Date'].dt.year
        for year in sorted(df['Year'].unique()):
            year_df = df[df['Year'] == year]
            acc = year_df['Prediction_Correct'].mean() * 100
            if acc < 55:
                print(f"  {year}: {acc:.1f}% - BELOW BREAKEVEN ⚠️")
            else:
                print(f"  {year}: {acc:.1f}% - OK")

if __name__ == "__main__":
    main()
