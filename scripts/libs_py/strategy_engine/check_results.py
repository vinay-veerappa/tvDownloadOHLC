import asyncio
import os
import sys
from dotenv import load_dotenv

# Configure environment path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

dotenv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../web/.env"))
load_dotenv(dotenv_path)

from prisma import Prisma

async def main():
    db = Prisma()
    await db.connect()
    
    print("\n==================================================")
    print("      OPTIONS STRATEGY ENGINE - STATUS CHECK      ")
    print("==================================================")
    
    # 1. Check Accounts
    accounts = await db.account.find_many(order={"currentBalance": "desc"})
    print(f"\nSilo Accounts Configured: {len(accounts)}")
    print(f"{'Account ID':<40} | {'Initial Bal':<12} | {'Current Bal':<12}")
    print("-" * 72)
    for acc in accounts[:10]: # Show top 10
        init_str = f"${acc.initialBalance:,.2f}"
        curr_str = f"${acc.currentBalance:,.2f}"
        print(f"{acc.id:<40} | {init_str:<12} | {curr_str:<12}")
    if len(accounts) > 10:
        print(f"... and {len(accounts) - 10} more accounts.")
        
    # 2. Check Trades
    trades = await db.trade.find_many(order={"entryDate": "desc"})
    open_trades = [t for t in trades if t.status.upper() == "OPEN"]
    closed_trades = [t for t in trades if t.status.upper() == "CLOSED"]
    
    print(f"\nTrades Summary:")
    print(f"  Total Trades:  {len(trades)}")
    print(f"  Open Trades:   {len(open_trades)}")
    print(f"  Closed Trades: {len(closed_trades)}")
    
    if open_trades:
        print("\nActive Open Trades:")
        print(f"{'Trade ID':<36} | {'Ticker':<6} | {'Direction':<10} | {'Entry Price':<12}")
        print("-" * 72)
        for t in open_trades[:5]:
            price_str = f"${t.entryPrice or 0.0:,.2f}"
            print(f"{t.id:<36} | {t.ticker:<6} | {t.direction:<10} | {price_str:<12}")
            
    # 3. Check Performance Runs
    runs = await db.researchrun.find_many(order={"createdAt": "desc"})
    print(f"\nEOD Performance Runs Logged: {len(runs)}")
    if runs:
        print(f"{'Date':<12} | {'Trades':<8} | {'Win Rate':<10} | {'Net Profit':<15}")
        print("-" * 52)
        import json
        for r in runs[:5]:
            metrics = json.loads(r.metricsJson) if r.metricsJson else {}
            win_rate = metrics.get("win_rate", 0.0) * 100
            win_str = f"{win_rate:,.1f}%"
            profit = metrics.get("total_pnl", 0.0)
            profit_str = f"${profit:,.2f}"
            total_t = metrics.get("total_trades", 0)
            print(f"{r.createdAt.strftime('%Y-%m-%d'):<12} | {total_t:<8} | {win_str:<10} | {profit_str:<15}")
            
    print("\n==================================================\n")
    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
