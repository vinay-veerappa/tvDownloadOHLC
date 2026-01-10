"""
Displacement & FVG Analysis - OPTIMIZED
========================================
Uses pre-indexed date lookup for speed
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime

ROOT = Path(r"c:\Users\vinay\tvDownloadOHLC")
DATA_DIR = ROOT / "data"
STRATEGY_DIR = ROOT / "docs" / "strategies" / "9_30_breakout" / "0930_AllDay"

def load_1m_indexed(ticker):
    """Load and pre-index 1m data by date for fast lookup"""
    path = DATA_DIR / f"{ticker}_1m.parquet"
    df = pd.read_parquet(path).reset_index()
    
    time_col = 'time' if 'time' in df.columns else df.columns[0]
    if pd.api.types.is_numeric_dtype(df[time_col]):
        df['datetime'] = pd.to_datetime(df[time_col], unit='s', utc=True)
    else:
        df['datetime'] = pd.to_datetime(df[time_col])
    
    if df['datetime'].dt.tz is None:
        df['datetime'] = df['datetime'].dt.tz_localize('UTC')
    df['datetime'] = df['datetime'].dt.tz_convert('America/New_York')
    
    df['date'] = df['datetime'].dt.date
    df['hour'] = df['datetime'].dt.hour
    df['minute'] = df['datetime'].dt.minute
    df = df.sort_values('datetime').reset_index(drop=True)
    
    # Build date index
    date_index = {}
    for date_val, group in df.groupby('date'):
        date_index[date_val] = group
    
    return df, date_index


def analyze_fast(excel_path, date_index):
    """Fast analysis using pre-indexed data"""
    trades = pd.read_excel(excel_path, sheet_name='List of trades')
    trades['Date and time'] = pd.to_datetime(trades['Date and time'])
    trades['date'] = trades['Date and time'].dt.date
    trades['hour'] = trades['Date and time'].dt.hour
    trades['minute'] = trades['Date and time'].dt.minute
    trades['is_winner'] = trades['Net P&L USD'] > 0
    
    # Post-10AM only
    trades = trades[trades['hour'] >= 10].copy()
    print(f"Post-10AM trades: {len(trades)}")
    
    results = []
    processed = 0
    
    for _, trade in trades.iterrows():
        day_date = trade['date']
        hour = trade['hour']
        minute = trade['minute']
        
        if day_date not in date_index:
            continue
        
        day_data = date_index[day_date]
        
        # Get OR
        or_data = day_data[(day_data['hour'] == 9) & (day_data['minute'] >= 30) & (day_data['minute'] <= 34)]
        if len(or_data) == 0:
            continue
        
        or_high = or_data['high'].max()
        or_low = or_data['low'].min()
        or_height = or_high - or_low
        if or_height == 0:
            continue
        
        # Get entry candle
        candle = day_data[(day_data['hour'] == hour) & (day_data['minute'] == minute)]
        if len(candle) == 0:
            continue
        candle = candle.iloc[0]
        
        # Direction
        signal = str(trade.get('Signal', ''))
        direction = 'long' if signal.startswith('L') else 'short'
        
        # Body ratio
        body = abs(candle['close'] - candle['open'])
        total = candle['high'] - candle['low']
        body_ratio = body / total if total > 0 else 0
        
        # Displacement %
        entry = candle['close']
        if direction == 'long':
            disp_pct = (entry - or_high) / or_height * 100
        else:
            disp_pct = (or_low - entry) / or_height * 100
        
        # Simple FVG check - look at prev 3 candles
        has_fvg = False
        idx = candle.name
        day_list = day_data.index.tolist()
        if idx in day_list:
            pos = day_list.index(idx)
            if pos >= 3:
                for i in range(max(0, pos-5), pos-2):
                    c0 = day_data.loc[day_list[i+2]]
                    c2 = day_data.loc[day_list[i]]
                    if direction == 'long' and c0['low'] > c2['high']:
                        has_fvg = True
                        break
                    elif direction == 'short' and c0['high'] < c2['low']:
                        has_fvg = True
                        break
        
        results.append({
            'date': day_date,
            'is_winner': trade['is_winner'],
            'body_ratio': body_ratio,
            'disp_pct': disp_pct,
            'has_fvg': has_fvg,
        })
        
        processed += 1
        if processed % 500 == 0:
            print(f"  Processed {processed}...")
    
    return pd.DataFrame(results)


def report(df):
    losers = df[~df['is_winner']]
    winners = df[df['is_winner']]
    
    print(f"\n{'='*70}")
    print(f"RESULTS: {len(winners)} winners, {len(losers)} losers")
    print(f"{'='*70}")
    
    # Body ratio
    print(f"\n1. BODY RATIO")
    print(f"   Loser Mean:  {losers['body_ratio'].mean():.3f}")
    print(f"   Winner Mean: {winners['body_ratio'].mean():.3f}")
    print(f"   Delta:       {winners['body_ratio'].mean() - losers['body_ratio'].mean():+.3f}")
    
    for t in [0.3, 0.4, 0.5]:
        la = (losers['body_ratio'] < t).sum() / len(losers) * 100 if len(losers) > 0 else 0
        wa = (winners['body_ratio'] < t).sum() / len(winners) * 100 if len(winners) > 0 else 0
        print(f"   < {t:.0%}: Avoid {la:.1f}% losers | Miss {wa:.1f}% winners | Net: {la-wa:+.1f}%")
    
    # Displacement %
    print(f"\n2. DISPLACEMENT % FROM OR")
    print(f"   Loser Mean:  {losers['disp_pct'].mean():.2f}%")
    print(f"   Winner Mean: {winners['disp_pct'].mean():.2f}%")
    
    for t in [5, 10, 15, 20]:
        la = (losers['disp_pct'] < t).sum() / len(losers) * 100 if len(losers) > 0 else 0
        wa = (winners['disp_pct'] < t).sum() / len(winners) * 100 if len(winners) > 0 else 0
        print(f"   < {t}%: Avoid {la:.1f}% losers | Miss {wa:.1f}% winners | Net: {la-wa:+.1f}%")
    
    # FVG
    print(f"\n3. FVG PRESENCE")
    wr_fvg = df[df['has_fvg']]['is_winner'].mean() * 100 if df['has_fvg'].sum() > 0 else 0
    wr_no = df[~df['has_fvg']]['is_winner'].mean() * 100 if (~df['has_fvg']).sum() > 0 else 0
    print(f"   With FVG: {wr_fvg:.1f}% WR ({df['has_fvg'].sum()} trades)")
    print(f"   Without:  {wr_no:.1f}% WR ({(~df['has_fvg']).sum()} trades)")
    print(f"   Delta:    {wr_fvg - wr_no:+.1f}%")


if __name__ == "__main__":
    print("Loading NQ1 data with indexing...")
    _, date_index = load_1m_indexed("NQ1")
    print(f"Indexed {len(date_index)} trading days")
    
    excel = sorted(STRATEGY_DIR.glob("*MNQ*467b7*.xlsx"))[-1]
    print(f"Using: {excel.name}")
    
    results = analyze_fast(excel, date_index)
    
    if len(results) > 0:
        report(results)
