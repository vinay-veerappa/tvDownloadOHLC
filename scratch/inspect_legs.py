import sqlite3
import pandas as pd

def inspect_legs():
    db_path = r"c:\Users\vinay\tvDownloadOHLC\web\prisma\dev.db"
    conn = sqlite3.connect(db_path)
    
    # Query today's trades and their legs
    query_trades = """
    SELECT id, ticker, entryDate, exitDate, entryPrice, exitPrice, status, pnl, accountId
    FROM Trade
    WHERE entryDate >= 1779163200000
    """
    df_trades = pd.read_sql_query(query_trades, conn)
    
    print("Today's Trades:")
    print(df_trades)
    
    query_legs = """
    SELECT id, tradeId, symbol, side, optionType, openPrice, closePrice, openBid, openAsk, closeBid, closeAsk, legPnl
    FROM TradeLeg
    WHERE tradeId IN (SELECT id FROM Trade WHERE entryDate >= 1779163200000)
    """
    df_legs = pd.read_sql_query(query_legs, conn)
    
    print("\nToday's Trade Legs:")
    for _, trade in df_trades.iterrows():
        print("="*80)
        print(f"Trade {trade['id']} for {trade['ticker']} ({trade['accountId']}) | Status: {trade['status']} | PnL: {trade['pnl']}")
        print(f"  Entry Price: {trade['entryPrice']} | Exit Price: {trade['exitPrice']}")
        legs = df_legs[df_legs['tradeId'] == trade['id']]
        print("  Legs:")
        print(legs[['side', 'optionType', 'openPrice', 'closePrice', 'legPnl']].to_string(index=False))
        
    conn.close()

if __name__ == "__main__":
    inspect_legs()
