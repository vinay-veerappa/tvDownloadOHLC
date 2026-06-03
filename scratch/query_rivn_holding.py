import sqlite3
import os

db_path = "c:/Users/vinay/tvDownloadOHLC/web/prisma/dev.db"
if not os.path.exists(db_path):
    db_path = "web/prisma/dev.db"

if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT ticker, shares, costBasis, datetime(acquiredAt/1000, 'unixepoch') as acq
        FROM Holding
        WHERE ticker = 'RIVN';
    """)
    row = cursor.fetchone()
    print("RIVN Holding:", row)
    
    conn.close()
else:
    print("Cannot find db file.")
