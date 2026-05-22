import sqlite3
import os
from datetime import datetime

db_path = r"c:\Users\vinay\tvDownloadOHLC\web\prisma\dev.db"
if not os.path.exists(db_path):
    print(f"Error: Database not found at {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get open trades
print("--- OPEN TRADES IN DATABASE ---")
cursor.execute("""
    SELECT t.id, t.ticker, t.status, t.entryDate, t.direction, t.quantity, s.name 
    FROM Trade t
    LEFT JOIN Strategy s ON t.strategyId = s.id
    WHERE t.status = 'OPEN'
""")
open_trades = cursor.fetchall()
if not open_trades:
    print("No open trades in the database.")
else:
    for t in open_trades:
        print(f"Trade ID: {t[0]} | Ticker: {t[1]} | Status: {t[2]} | Entry: {t[3]} | Direction: {t[4]} | Qty: {t[5]} | Strategy: {t[6]}")
        # Fetch legs
        cursor.execute("SELECT id, symbol, optionType, side, strike, expiry, openPrice FROM TradeLeg WHERE tradeId = ?", (t[0],))
        legs = cursor.fetchall()
        for leg in legs:
            print(f"  Leg ID: {leg[0]} | Symbol: {leg[1]} | Type: {leg[2]} | Side: {leg[3]} | Strike: {leg[4]} | Expiry: {leg[5]} | Open Price: {leg[6]}")

print("\n--- OPEN LEGS EXPIRY SUMMARY ---")
cursor.execute("""
    SELECT tl.symbol, tl.expiry, t.entryDate, s.name, t.status
    FROM TradeLeg tl
    JOIN Trade t ON tl.tradeId = t.id
    LEFT JOIN Strategy s ON t.strategyId = s.id
    WHERE t.status = 'OPEN' AND tl.optionType != 'STOCK'
""")
open_legs = cursor.fetchall()
if not open_legs:
    print("No open option legs found.")
else:
    for leg in open_legs:
        print(f"Symbol: {leg[0]} | Expiry: {leg[1]} | Entry Date: {leg[2]} | Strategy: {leg[3]}")

conn.close()
