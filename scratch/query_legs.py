import sqlite3
import os

db_path = "c:/Users/vinay/tvDownloadOHLC/web/prisma/dev.db"
if not os.path.exists(db_path):
    db_path = "web/prisma/dev.db"

if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    trade_ids = ['cmpe49qko00203a9nmn6kkba6', 'cmpe4b6gq003b3a9nzsryipg8', 'cmpe5cfgz00hf3a9ncmsn1qyw']
    
    for tid in trade_ids:
        print(f"\n--- Trade ID: {tid} ---")
        cursor.execute("""
            SELECT id, ticker, entryPrice, exitPrice, pnl, notes FROM Trade WHERE id = ?
        """, (tid,))
        print("Trade:", cursor.fetchone())
        
        cursor.execute("""
            SELECT id, symbol, side, optionType, strike, openPrice, closePrice, legPnl, quantity
            FROM TradeLeg
            WHERE tradeId = ?
            ORDER BY legIndex ASC;
        """, (tid,))
        legs = cursor.fetchall()
        for leg in legs:
            print("  Leg:", leg)
            
    conn.close()
else:
    print("Cannot find db file.")
