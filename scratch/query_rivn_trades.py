import sqlite3
import os

db_path = "c:/Users/vinay/tvDownloadOHLC/web/prisma/dev.db"
if not os.path.exists(db_path):
    db_path = "web/prisma/dev.db"

if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT t.id, t.ticker, datetime(t.entryDate/1000, 'unixepoch') as entry, datetime(t.exitDate/1000, 'unixepoch') as exit_dt, 
               t.entryPrice, t.exitPrice, t.quantity, t.pnl, t.status, t.notes
        FROM Trade t
        JOIN Account a ON t.accountId = a.id
        WHERE a.name = 'INCOME_CC_TIER_RIVN'
        ORDER BY t.entryDate ASC;
    """)
    rows = cursor.fetchall()
    print(f"Total trades: {len(rows)}")
    for idx, row in enumerate(rows):
        print(f"{idx+1}: {row}")
        
    conn.close()
else:
    print("Cannot find db file.")
