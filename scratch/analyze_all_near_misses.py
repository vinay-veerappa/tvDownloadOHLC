import sqlite3
import os

def analyze():
    db_path = "c:/Users/vinay/tvDownloadOHLC/web/prisma/dev.db"
    if not os.path.exists(db_path):
        db_path = "web/prisma/dev.db"

    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("==================================================")
    print("      STRATEGY BLOCKAGE & NEAR-MISS ANALYSIS      ")
    print("==================================================")

    # 1. Total Near Misses by Strategy
    print("\n[1] Near-Miss Counts by Strategy Variant:")
    cursor.execute("""
        SELECT rs.name, COUNT(nm.id) as count
        FROM SignalNearMiss nm
        JOIN ResearchStrategy rs ON nm.researchStrategyId = rs.id
        GROUP BY rs.name
        ORDER BY count DESC;
    """)
    rows = cursor.fetchall()
    for row in rows:
        print(f"  {row[0]:<40} : {row[1]} near-misses")

    # 2. Failing Filters Breakdown
    print("\n[2] Primary Reasons for Near-Misses (Failing Filters) across all Strategies:")
    cursor.execute("""
        SELECT failingFilter, COUNT(*) as count
        FROM SignalNearMiss
        GROUP BY failingFilter
        ORDER BY count DESC;
    """)
    rows = cursor.fetchall()
    for row in rows:
        print(f"  Filter '{row[0]}': {row[1]} times")

    # 3. Analyze Ticker Blockages
    print("\n[3] Filter Failures by Ticker:")
    cursor.execute("""
        SELECT ticker, failingFilter, COUNT(*) as count
        FROM SignalNearMiss
        GROUP BY ticker, failingFilter
        ORDER BY ticker, count DESC;
    """)
    rows = cursor.fetchall()
    current_ticker = None
    for row in rows:
        ticker, filter_name, count = row
        if ticker != current_ticker:
            current_ticker = ticker
            print(f"\n  Ticker: {ticker}")
        print(f"    - Filter '{filter_name}': {count} times")

    # 4. Check ResearchStrategy and Trade schema
    print("\n[4] ResearchStrategy & Trade Table Schema Info:")
    cursor.execute("PRAGMA table_info(ResearchStrategy);")
    rs_cols = [col[1] for col in cursor.fetchall()]
    print(f"  ResearchStrategy Columns: {rs_cols}")
    
    cursor.execute("PRAGMA table_info(Trade);")
    trade_cols = [col[1] for col in cursor.fetchall()]
    print(f"  Trade Columns: {trade_cols}")
    
    # Let's count total trades in dev db
    cursor.execute("SELECT COUNT(*) FROM Trade;")
    total_trades = cursor.fetchone()[0]
    print(f"\n  Total Trades in DB: {total_trades}")
    
    # If there is a column mapping back to strategies, let's group by it
    strategy_rel_col = None
    for col in trade_cols:
        if "strategy" in col.lower() or "silo" in col.lower() or "type" in col.lower() or "acct" in col.lower() or "account" in col.lower():
            # let's list some counts grouped by that
            pass
    
    cursor.execute("SELECT status, COUNT(*) FROM Trade GROUP BY status;")
    status_groups = cursor.fetchall()
    print("  Trades by status:")
    for status, count in status_groups:
        print(f"    - {status}: {count}")

    conn.close()

if __name__ == "__main__":
    analyze()
