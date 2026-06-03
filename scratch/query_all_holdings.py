import sqlite3
import os
import asyncio
from dotenv import load_dotenv

import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

dotenv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../web/.env"))
load_dotenv(dotenv_path)

from scripts.libs_py.strategy_engine.services.broker_service import BrokerService

async def main():
    db_path = "c:/Users/vinay/tvDownloadOHLC/web/prisma/dev.db"
    if not os.path.exists(db_path):
        db_path = "web/prisma/dev.db"
        
    if not os.path.exists(db_path):
        print("Cannot find db file.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT ticker, shares, costBasis FROM Holding;
    """)
    holdings = cursor.fetchall()
    conn.close()
    
    print("\n================ ACTIVE STOCK HOLDINGS ================")
    broker = BrokerService()
    for ticker, shares, cost_basis in holdings:
        try:
            quote = await broker.get_stock_quote(ticker)
            spot = quote["last"]
            diff = spot - cost_basis
            diff_pct = (diff / cost_basis) * 100.0 if cost_basis > 0 else 0.0
            status = "UNDERWATER" if diff < 0 else "IN PROFIT"
            print(f"{ticker:<6} | Shares: {shares:<5} | Cost Basis: ${cost_basis:<6.2f} | Spot: ${spot:<6.2f} | PnL: ${diff:+.2f} ({diff_pct:+.1f}%) | {status}")
        except Exception as e:
            print(f"{ticker:<6} | Shares: {shares:<5} | Cost Basis: ${cost_basis:<6.2f} | Spot: N/A | Error: {e}")
    print("=======================================================\n")

if __name__ == "__main__":
    asyncio.run(main())
