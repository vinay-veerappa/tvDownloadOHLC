import sqlite3
import pandas as pd
from pathlib import Path

p = Path('web/prisma/dev.db')
if not p.exists():
    print(f"DB not found at {p}")
    # Try other locations
    for alt in ['web/dev.db', 'prisma/dev.db', 'data/dev.db']:
        if Path(alt).exists():
            p = Path(alt)
            print(f"Found at {p}")
            break
    else:
        print("No DB found. Searching...")
        import os
        for root, dirs, files in os.walk('.'):
            if 'dev.db' in files and 'prisma' in root.lower():
                p = Path(root) / 'dev.db'
                print(f"Found at {p}")
                break

if p.exists():
    conn = sqlite3.connect(str(p))
    # Get all tables
    tables = pd.read_sql_query("SELECT name FROM sqlite_master WHERE type='table'", conn)
    print("Tables:", tables['name'].tolist())
    
    # Check EconomicEvent
    if 'EconomicEvent' in tables['name'].tolist():
        count = pd.read_sql_query("SELECT COUNT(*) as n FROM EconomicEvent", conn)
        print(f"Total EconomicEvent rows: {count['n'][0]}")
        
        df = pd.read_sql_query(
            "SELECT datetime, name, impact, country FROM EconomicEvent WHERE impact IN ('HIGH','MEDIUM') ORDER BY datetime DESC LIMIT 20",
            conn
        )
        print("\nRecent HIGH/MEDIUM events:")
        print(df.to_string())
        
        # Check for 9:45 / 10:00 events specifically
        et_events = pd.read_sql_query(
            "SELECT datetime, name, impact FROM EconomicEvent WHERE impact IN ('HIGH','MEDIUM') AND name LIKE '%ISM%' OR name LIKE '%PMI%' OR name LIKE '%Consumer%' ORDER BY datetime DESC LIMIT 10",
            conn
        )
        print("\nISM/PMI/Consumer events:")
        print(et_events.to_string())
    conn.close()