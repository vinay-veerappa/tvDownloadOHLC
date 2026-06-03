import sqlite3
import os

db_path = "c:/Users/vinay/tvDownloadOHLC/web/prisma/dev.db"
if not os.path.exists(db_path):
    print(f"Database not found at {db_path}")
    # Try web/prisma/dev.db relative to workspace or check other places
    db_path = "web/prisma/dev.db"

if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    print("Tables:", tables)
    
    # Query accounts and trades for ZERO_DTE_PCS_10D_5W_SPY
    print("\n--- ZERO_DTE_PCS_10D_5W_SPY Trades ---")
    cursor.execute("""
        SELECT t.id, t.ticker, t.entryDate, t.exitDate, t.entryPrice, t.exitPrice, t.quantity, t.direction, t.pnl, t.status, t.notes
        FROM Trade t
        JOIN Account a ON t.accountId = a.id
        WHERE a.name = 'ZERO_DTE_PCS_10D_5W_SPY'
        ORDER BY t.entryDate DESC
        LIMIT 10;
    """)
    rows = cursor.fetchall()
    for row in rows:
        print(row)
        
    conn.close()
else:
    print("Cannot find db file.")
