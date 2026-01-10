"""
Cross-reference Toxic Windows with Economic Calendar
=====================================================
Query Prisma DB for economic events and see if they correlate with toxic time windows
"""

import sqlite3
import pandas as pd
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# Prisma uses SQLite by default in dev
DB_PATH = Path(r"c:\Users\vinay\tvDownloadOHLC\web\prisma\dev.db")

def load_economic_events():
    """Load economic events from Prisma SQLite DB"""
    conn = sqlite3.connect(DB_PATH)
    
    query = """
    SELECT datetime, name, impact 
    FROM EconomicEvent 
    ORDER BY datetime
    """
    
    df = pd.read_sql(query, conn)
    
    # Convert milliseconds to datetime and localize to ET
    df['datetime'] = pd.to_datetime(df['datetime'], unit='ms', utc=True)
    df['datetime'] = df['datetime'].dt.tz_convert('America/New_York')
    
    # Extract time components
    df['hour'] = df['datetime'].dt.hour
    df['minute'] = df['datetime'].dt.minute
    df['minute_bucket'] = (df['minute'] // 5) * 5
    df['time_str'] = df['hour'].astype(str).str.zfill(2) + ':' + df['minute_bucket'].astype(str).str.zfill(2)
    
    conn.close()
    return df


def analyze_news_times(df):
    """Analyze which time buckets have the most news events"""
    
    # Count by time bucket
    time_counts = df.groupby('time_str').agg({
        'name': 'count',
        'impact': lambda x: (x == 'HIGH').sum()
    }).rename(columns={'name': 'total_events', 'impact': 'high_impact'})
    
    time_counts = time_counts.sort_values('total_events', ascending=False)
    
    return time_counts


def get_common_news_by_time():
    """Get most common news events for each time bucket"""
    df = load_economic_events()
    
    print(f"Total events in DB: {len(df)}")
    print(f"Date range: {df['datetime'].min()} to {df['datetime'].max()}")
    
    print("\n" + "="*70)
    print("ECONOMIC NEWS BY TIME BUCKET (sorted by frequency)")
    print("="*70)
    
    time_counts = analyze_news_times(df)
    
    print(f"\n{'Time':<8} {'Total':>8} {'High Impact':>12}")
    print("-"*35)
    
    for time_str, row in time_counts.head(20).iterrows():
        hi_flag = "🔴" if row['high_impact'] > 10 else ""
        print(f"{time_str:<8} {row['total_events']:>8} {row['high_impact']:>12} {hi_flag}")
    
    # Cross-reference with toxic windows
    toxic_windows = ['09:55', '10:00', '10:10', '10:30', '11:10', '11:20', '13:00']
    
    print("\n" + "="*70)
    print("TOXIC WINDOWS VS NEWS EVENTS")
    print("="*70)
    
    for window in toxic_windows:
        if window in time_counts.index:
            events = time_counts.loc[window]
            print(f"\n⚠️ {window}: {events['total_events']} events ({events['high_impact']} high impact)")
            
            # Get sample events for this time
            samples = df[df['time_str'] == window]['name'].value_counts().head(5)
            for name, count in samples.items():
                print(f"    - {name}: {count}x")
        else:
            print(f"\n{window}: No economic events")
    
    # Show what news happens at 10:00
    print("\n" + "="*70)
    print("COMMON 10:00 AM NEWS EVENTS")
    print("="*70)
    
    ten_am = df[df['time_str'] == '10:00']['name'].value_counts().head(15)
    for name, count in ten_am.items():
        print(f"  {name}: {count}x")
    
    # Show what news happens at 10:30
    print("\n" + "="*70)
    print("COMMON 10:30 AM NEWS EVENTS")
    print("="*70)
    
    ten_30 = df[df['time_str'] == '10:30']['name'].value_counts().head(15)
    for name, count in ten_30.items():
        print(f"  {name}: {count}x")


if __name__ == "__main__":
    if not DB_PATH.exists():
        print(f"DB not found at {DB_PATH}")
        exit(1)
    
    get_common_news_by_time()
