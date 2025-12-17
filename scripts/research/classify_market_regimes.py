
import pandas as pd
import numpy as np
import os

def classify_regimes(ticker="NQ1", years=5):
    print(f"Classifying Market Regimes for {ticker} (Last {years} Years)...")
    
    data_path = f"data/{ticker}_1m.parquet"
    if not os.path.exists(data_path): return
    df = pd.read_parquet(data_path)
    
    if not isinstance(df.index, pd.DatetimeIndex):
        if 'time' in df.columns: df['datetime'] = pd.to_datetime(df['time'], unit='s' if df['time'].iloc[0] > 1e10 else 'ms')
        df = df.set_index('datetime')
    df = df.sort_index()
    if df.index.tz is not None: df = df.tz_convert('US/Eastern')
    
    # Aggregate to Daily
    daily = df['close'].resample('D').last().dropna().to_frame()
    
    # 200 SMA
    daily['SMA200'] = daily['close'].rolling(200).mean()
    # 50 SMA for Sideways detection
    daily['SMA50'] = daily['close'].rolling(50).mean()
    
    # ADR (Average Daily Range) for volatility
    daily_high = df['high'].resample('D').max().dropna()
    daily_low = df['low'].resample('D').min().dropna()
    daily['ADR_Pct'] = ((daily_high - daily_low) / daily['close']) * 100
    daily['ATR20'] = daily['ADR_Pct'].rolling(20).mean()

    def get_regime(row):
        if pd.isna(row['SMA200']): return 'Unknown'
        
        # Bull/Bear
        main_trend = 'BULL' if row['close'] > row['SMA200'] else 'BEAR'
        
        # Sideways Detection (Price range-bound between SMA50 and SMA200 OR low volatility)
        # Simple heuristic: If price is within 2% of SMA200 for 10 days
        # For simplicity in this backtest:
        return main_trend

    daily['Regime'] = daily.apply(get_regime, axis=1)
    
    # Report
    summary = daily.groupby('Regime').size()
    print("\nRegime Summary:")
    print(summary)
    
    # Save for backtest use
    daily.index.name = 'Date'
    daily[['Regime']].to_csv(f"reports/{ticker}_regimes.csv")
    print(f"Regimes saved to reports/{ticker}_regimes.csv")

if __name__ == "__main__":
    classify_regimes()
