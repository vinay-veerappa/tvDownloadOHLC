"""
Toxic Time Window Analysis
==========================
Analyze actual trades by 5-minute buckets to find windows to avoid.
Focus on news-related chop around 9:45, 10:00 etc.
"""

import pandas as pd
import numpy as np
from pathlib import Path

STRATEGY_DIR = Path(r"c:\Users\vinay\tvDownloadOHLC\docs\strategies\9_30_breakout\0930_AllDay")

def load_trades(excel_path):
    """Load trades from Excel backtest"""
    df = pd.read_excel(excel_path, sheet_name='List of trades')
    df['Date and time'] = pd.to_datetime(df['Date and time'])
    df['hour'] = df['Date and time'].dt.hour
    df['minute'] = df['Date and time'].dt.minute
    
    # Round to 5-minute bucket
    df['minute_bucket'] = (df['minute'] // 5) * 5
    df['time_bucket'] = df['hour'].astype(str).str.zfill(2) + ':' + df['minute_bucket'].astype(str).str.zfill(2)
    
    # Determine win/loss
    df['is_winner'] = df['Net P&L USD'] > 0
    df['is_loser'] = df['Net P&L USD'] < 0
    
    return df


def analyze_time_buckets(df):
    """Analyze performance by 5-minute time bucket"""
    
    # Group by time bucket
    results = []
    for bucket, group in df.groupby('time_bucket'):
        total = len(group)
        winners = group['is_winner'].sum()
        losers = group['is_loser'].sum()
        even = total - winners - losers
        
        win_rate = winners / total * 100 if total > 0 else 0
        total_pnl = group['Net P&L USD'].sum()
        avg_pnl = group['Net P&L USD'].mean()
        
        results.append({
            'time_bucket': bucket,
            'trades': total,
            'winners': int(winners),
            'losers': int(losers),
            'even': int(even),
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'avg_pnl': avg_pnl,
        })
    
    return pd.DataFrame(results).sort_values('time_bucket')


def find_toxic_windows(results_df, min_trades=20, max_winrate=25):
    """Identify toxic windows with low win rates"""
    
    # Filter to buckets with enough trades
    filtered = results_df[results_df['trades'] >= min_trades].copy()
    
    # Find below-average performers
    avg_wr = filtered['win_rate'].mean()
    toxic = filtered[filtered['win_rate'] < max_winrate].sort_values('win_rate')
    
    return toxic, avg_wr


def find_golden_windows(results_df, min_trades=20):
    """Identify best windows with high win rates"""
    
    filtered = results_df[results_df['trades'] >= min_trades].copy()
    avg_wr = filtered['win_rate'].mean()
    
    golden = filtered[filtered['win_rate'] > avg_wr + 5].sort_values('win_rate', ascending=False)
    
    return golden


def analyze_news_windows(df):
    """Specifically analyze windows around common news times"""
    
    # Common news times (ET)
    news_windows = ['09:40', '09:45', '09:55', '10:00', '10:25', '10:30']
    
    print("\n" + "="*70)
    print("NEWS WINDOW ANALYSIS")
    print("="*70)
    print("(Trades entering 5 min before/after common news times)")
    
    for news_time in news_windows:
        hour, minute = map(int, news_time.split(':'))
        
        # Get trades in this 5-min window and adjacent windows
        mask = (df['hour'] == hour) & (df['minute_bucket'] == minute)
        window_trades = df[mask]
        
        if len(window_trades) > 0:
            wr = window_trades['is_winner'].mean() * 100
            total_pnl = window_trades['Net P&L USD'].sum()
            print(f"\n{news_time} Window:")
            print(f"  Trades: {len(window_trades)}")
            print(f"  Win Rate: {wr:.1f}%")
            print(f"  Total P&L: ${total_pnl:.2f}")
            
            if wr < 25:
                print(f"  ⚠️ TOXIC - Consider skipping")
            elif wr > 35:
                print(f"  ✓ Good window")


if __name__ == "__main__":
    # Find latest MNQ Excel file
    excel_files = list(STRATEGY_DIR.glob("ORB_V3_Doji*MNQ*.xlsx"))
    if not excel_files:
        print("No MNQ Excel files found")
        exit(1)
    
    latest = sorted(excel_files)[-1]
    print(f"Analyzing: {latest.name}")
    
    # Load trades
    trades = load_trades(latest)
    print(f"Total trades: {len(trades)}")
    
    # Analyze all time buckets
    results = analyze_time_buckets(trades)
    
    print("\n" + "="*70)
    print("ALL 5-MINUTE BUCKETS (sorted by time)")
    print("="*70)
    print(f"{'Bucket':<8} {'Trades':>7} {'Win':>5} {'Loss':>5} {'WR%':>7} {'Avg P&L':>10}")
    print("-"*50)
    
    for _, row in results.iterrows():
        wr_flag = "⚠️" if row['win_rate'] < 22 else ("💎" if row['win_rate'] > 35 else "  ")
        print(f"{row['time_bucket']:<8} {row['trades']:>7} {row['winners']:>5} {row['losers']:>5} {row['win_rate']:>6.1f}% {row['avg_pnl']:>9.2f} {wr_flag}")
    
    # Find toxic windows
    print("\n" + "="*70)
    print("TOXIC WINDOWS (Win Rate < 25%, min 20 trades)")
    print("="*70)
    
    toxic, avg_wr = find_toxic_windows(results, min_trades=20, max_winrate=25)
    print(f"Average Win Rate: {avg_wr:.1f}%")
    print()
    
    if len(toxic) > 0:
        for _, row in toxic.iterrows():
            print(f"⚠️ {row['time_bucket']}: {row['win_rate']:.1f}% WR ({row['trades']} trades, ${row['total_pnl']:.0f} total)")
    else:
        print("No toxic windows found with current thresholds")
    
    # Find golden windows
    print("\n" + "="*70)
    print("GOLDEN WINDOWS (Above Average WR, min 20 trades)")
    print("="*70)
    
    golden = find_golden_windows(results, min_trades=20)
    if len(golden) > 0:
        for _, row in golden.head(10).iterrows():
            print(f"💎 {row['time_bucket']}: {row['win_rate']:.1f}% WR ({row['trades']} trades, ${row['total_pnl']:.0f} total)")
    
    # Analyze news windows specifically
    analyze_news_windows(trades)
    
    # Summary recommendation
    print("\n" + "="*70)
    print("RECOMMENDED SKIP WINDOWS")
    print("="*70)
    
    # Identify windows to skip based on consistent underperformance
    skip_candidates = results[(results['trades'] >= 20) & (results['win_rate'] < 22)]
    if len(skip_candidates) > 0:
        print("\nBased on analysis, consider skipping entries during:")
        for _, row in skip_candidates.sort_values('win_rate').iterrows():
            print(f"  • {row['time_bucket']} → {int(row['time_bucket'].split(':')[0]):02d}:{int(row['time_bucket'].split(':')[1])+4:02d}")
