import sqlite3
import pandas as pd
from datetime import datetime, timedelta

def analyze_trades():
    db_path = r"c:\Users\vinay\tvDownloadOHLC\web\prisma\dev.db"
    conn = sqlite3.connect(db_path)
    
    # Let's get trades closed today or recently
    query = """
    SELECT t.id, t.ticker, t.direction, t.status, t.entryDate, t.exitDate, t.pnl, t.entryPrice, t.exitPrice, a.name as account_name
    FROM Trade t
    JOIN Account a ON t.accountId = a.id
    ORDER BY t.entryDate DESC
    LIMIT 100
    """
    
    df = pd.read_sql_query(query, conn)
    
    if df.empty:
        print("No trades found.")
        return
        
    df['entryDate'] = pd.to_datetime(df['entryDate'], unit='ms').dt.tz_localize('UTC').dt.tz_convert('America/New_York')
    # Filter for today or very recent
    now = pd.Timestamp.now(tz='America/New_York')
    today_str = now.strftime('%Y-%m-%d')
    
    print(f"Server Time (NY): {now}")
    print("\nRecent Trades:")
    print(df.head(20).to_string())
    
    # Let's also check if there are any ResearchRun updates
    run_query = """
    SELECT runId, ticker, grade, updatedAt, metricsJson 
    FROM ResearchRun 
    ORDER BY updatedAt DESC 
    LIMIT 10
    """
    df_runs = pd.read_sql_query(run_query, conn)
    print("\nRecent Research Runs:")
    if not df_runs.empty:
        print(df_runs.head(10).to_string())
    else:
        print("No ResearchRuns found.")
        
    conn.close()

if __name__ == "__main__":
    analyze_trades()
