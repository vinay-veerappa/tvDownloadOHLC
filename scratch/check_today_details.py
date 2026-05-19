import sqlite3
import json
import pandas as pd
from datetime import datetime

def inspect_today_trades():
    db_path = r"c:\Users\vinay\tvDownloadOHLC\web\prisma\dev.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get table columns
    cursor.execute("PRAGMA table_info(Trade)")
    columns = [col[1] for col in cursor.fetchall()]
    print("Trade Columns:", columns)
    
    # Get today's trades (since midnight UTC or Eastern, let's just query everything from today in ms)
    # Today is May 19, 2026.
    # Midnight Eastern on May 19, 2026 is May 19, 2026 04:00:00 UTC = 1779163200000 ms.
    cursor.execute("SELECT * FROM Trade WHERE entryDate >= 1779163200000")
    rows = cursor.fetchall()
    
    print(f"\nFound {len(rows)} trades for today (since May 19, 2026 00:00 Eastern):")
    
    for row in rows:
        trade_dict = dict(zip(columns, row))
        print("="*60)
        print(f"ID: {trade_dict['id']} | Ticker: {trade_dict['ticker']} | Account: {trade_dict['accountId']}")
        print(f"Status: {trade_dict['status']} | PnL: {trade_dict['pnl']}")
        print(f"Entry Date: {pd.to_datetime(trade_dict['entryDate'], unit='ms')} UTC")
        print(f"Exit Date: {pd.to_datetime(trade_dict['exitDate'], unit='ms') if trade_dict['exitDate'] else 'N/A'} UTC")
        print(f"Entry Price: {trade_dict['entryPrice']} | Exit Price: {trade_dict['exitPrice']}")
        
        # Parse metadata
        meta_str = trade_dict.get('metadata', None)
        if meta_str:
            try:
                meta = json.loads(meta_str)
                print(f"Metadata: {json.dumps(meta, indent=2)}")
            except Exception as e:
                print(f"Raw Metadata (failed to parse): {meta_str}")
        else:
            print("Metadata: None")
            
    # Also inspect any OptionLegs or LegRealizations if they exist
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [t[0] for t in cursor.fetchall()]
    print("\nTables in DB:", tables)
    
    if 'OptionLeg' in tables:
        cursor.execute("PRAGMA table_info(OptionLeg)")
        leg_cols = [col[1] for col in cursor.fetchall()]
        cursor.execute("SELECT * FROM OptionLeg WHERE tradeId IN (SELECT id FROM Trade WHERE entryDate >= 1779163200000)")
        legs = cursor.fetchall()
        print(f"\nFound {len(legs)} option legs for today's trades:")
        for leg in legs:
            leg_dict = dict(zip(leg_cols, leg))
            print("-"*40)
            print(f"Leg ID: {leg_dict['id']} | TradeId: {leg_dict['tradeId']} | Symbol: {leg_dict['symbol']}")
            print(f"Strike: {leg_dict.get('strike')} | Type: {leg_dict.get('type') or leg_dict.get('optionType')}")
            print(f"Entry Price: {leg_dict.get('entryPrice')} | Exit Price: {leg_dict.get('exitPrice')}")
            
    conn.close()

if __name__ == "__main__":
    inspect_today_trades()
