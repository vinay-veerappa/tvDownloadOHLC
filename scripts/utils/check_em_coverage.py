import asyncio
from prisma import Prisma
import pandas as pd
import os

# Load Environment
try:
    env_path = os.path.join(os.getcwd(), 'web', '.env')
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                if '=' in line and not line.startswith('#'):
                    k, v = line.strip().split('=', 1)
                    os.environ[k] = v.strip('"').strip("'")
    else:
        # Fallback to current dir .env
        if os.path.exists('.env'):
             with open('.env', 'r') as f:
                for line in f:
                    if '=' in line and not line.startswith('#'):
                        k, v = line.strip().split('=', 1)
                        os.environ[k] = v.strip('"').strip("'")
except Exception as e:
    print(f"Warning: Could not load .env: {e}")

async def main():
    db = Prisma()
    await db.connect()
    
    # Get all unique tickers and their date ranges
    recs = await db.expectedmovehistory.find_many(
        order={'date': 'asc'}
    )
    
    if not recs:
        print("No historical EM data found.")
        await db.disconnect()
        return
        
    df = pd.DataFrame([
        {
            'ticker': r.ticker,
            'date': r.date,
            'has_straddle': r.straddlePrice is not None,
            'has_em365': r.em365 is not None
        } for r in recs
    ])
    
    summary = df.groupby('ticker').agg({
        'date': ['min', 'max', 'count'],
        'has_straddle': 'sum',
        'has_em365': 'sum'
    })
    
    print("\n=== Expected Move History Summary ===")
    print(summary)
    
    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
