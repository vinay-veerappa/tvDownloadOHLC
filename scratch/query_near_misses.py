import sqlite3
import os

db_path = "c:/Users/vinay/tvDownloadOHLC/web/prisma/dev.db"
if not os.path.exists(db_path):
    db_path = "web/prisma/dev.db"

if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if AMD is configured in the ResearchStrategy table
    print("--- AMD Configuration in ResearchStrategy ---")
    cursor.execute("SELECT id, name FROM ResearchStrategy WHERE name LIKE '%AMD%';")
    print(cursor.fetchall())
    
    # Query recent near-misses for AAPL and MSFT
    print("\n--- Recent Near Misses for AAPL & MSFT (Last 50) ---")
    cursor.execute("""
        SELECT ticker, failingFilter, filterValue, filterThreshold, datetime(evaluatedAt/1000, 'unixepoch') as time_str
        FROM SignalNearMiss
        WHERE ticker IN ('AAPL', 'MSFT', 'AMD')
        ORDER BY evaluatedAt DESC
        LIMIT 50;
    """)
    rows = cursor.fetchall()
    for row in rows:
        print(row)
        
    # Count totals by failing filter for each ticker
    print("\n--- Total Near Misses by Filter for AAPL ---")
    cursor.execute("""
        SELECT failingFilter, COUNT(*) 
        FROM SignalNearMiss 
        WHERE ticker = 'AAPL' 
        GROUP BY failingFilter;
    """)
    print(cursor.fetchall())

    print("\n--- Total Near Misses by Filter for MSFT ---")
    cursor.execute("""
        SELECT failingFilter, COUNT(*) 
        FROM SignalNearMiss 
        WHERE ticker = 'MSFT' 
        GROUP BY failingFilter;
    """)
    print(cursor.fetchall())
    
    conn.close()
else:
    print("Cannot find db file.")
