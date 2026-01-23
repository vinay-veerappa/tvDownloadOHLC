import sqlite3
import pandas as pd
import os
import pytz

DB_PATH = "c:/Users/vinay/tvDownloadOHLC/web/prisma/dev.db"

def inspect_events():
    if not os.path.exists(DB_PATH):
        print(f"Error: Database not found at {DB_PATH}")
        return
    
    conn = sqlite3.connect(DB_PATH)
    
    # Let's see the column names and some samples to understand the date format better
    print("Columns in EconomicEvent:")
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(EconomicEvent)")
    columns = cursor.fetchall()
    for col in columns:
        print(f" - {col[1]} ({col[2]})")
    
    # Query for HIGH impact events
    query = """
    SELECT name, datetime, impact 
    FROM EconomicEvent 
    WHERE impact = 'HIGH'
    LIMIT 10
    """
    df = pd.read_sql_query(query, conn)
    print("\nSample HIGH Impact Events:")
    print(df)
    
    # Try to find 8:30 events
    print("\nImpact Counts:")
    cursor.execute("SELECT impact, count(*) FROM EconomicEvent GROUP BY impact")
    print(cursor.fetchall())

    # Load ALL High Impact Events
    query_all = "SELECT datetime, name FROM EconomicEvent WHERE impact='HIGH'"
    df_all = pd.read_sql_query(query_all, conn)
    local_tz = pytz.timezone('US/Eastern')
    
    EXCLUDE_KEYWORDS = [
        "German", "French", "Spanish", "Italian", "Eurozone", 
        "UK ", "JPY", "AUD", "CAD", "CNY", "Swiss", "ECB President", 
        "EU ", "Australian", "British", "Canadian", "Japanese", "Chinese"
    ]
    
    times = []
    us_830_events = []
    
    for _, row in df_all.iterrows():
        dt_raw = row['datetime']
        name = row['name']
        
        # Filter for non-US
        if any(kw in name for kw in EXCLUDE_KEYWORDS):
            continue
            
        if isinstance(dt_raw, str):
            dt_utc = pd.to_datetime(dt_raw).tz_localize('UTC')
        else:
            dt_utc = pd.to_datetime(dt_raw, unit='ms').tz_localize('UTC')
        dt_local = dt_utc.astimezone(local_tz)
        
        t_str = dt_local.strftime("%H:%M")
        times.append(t_str)
        
        if dt_local.hour == 8 and dt_local.minute == 30:
            us_830_events.append((dt_local, name))
    
    from collections import Counter
    time_counts = Counter(times)
    print("\nTop US Event Times (US/Eastern):")
    for t, count in time_counts.most_common(10):
        print(f" - {t}: {count}")

    print("\nSample US Events at 11:30 (US/Eastern):")
    events_1130 = []
    for _, row in df_all.iterrows():
        dt_raw = row['datetime']
        name = row['name']
        if any(kw in name for kw in EXCLUDE_KEYWORDS): continue
        if isinstance(dt_raw, str): dt_utc = pd.to_datetime(dt_raw).tz_localize('UTC')
        else: dt_utc = pd.to_datetime(dt_raw, unit='ms').tz_localize('UTC')
        dt_local = dt_utc.astimezone(local_tz)
        if dt_local.hour == 11 and dt_local.minute == 30:
            events_1130.append(name)
    
    unique_1130 = Counter(events_1130)
    for name, count in unique_1130.most_common(10):
        print(f" - {name}: {count}")

    print("\nSample US Events at 08:30 (US/Eastern):")
    events_0830 = []
    for _, row in df_all.iterrows():
        dt_raw = row['datetime']
        name = row['name']
        if any(kw in name for kw in EXCLUDE_KEYWORDS): continue
        if isinstance(dt_raw, str): dt_utc = pd.to_datetime(dt_raw).tz_localize('UTC')
        else: dt_utc = pd.to_datetime(dt_raw, unit='ms').tz_localize('UTC')
        dt_local = dt_utc.astimezone(local_tz)
        if dt_local.hour == 8 and dt_local.minute == 30:
            events_0830.append(name)
    
    unique_0830 = Counter(events_0830)
    for name, count in unique_0830.most_common(10):
        print(f" - {name}: {count}")
    
    conn.close()

if __name__ == "__main__":
    inspect_events()
