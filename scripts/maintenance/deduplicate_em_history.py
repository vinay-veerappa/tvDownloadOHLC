
import asyncio
from prisma import Prisma
import datetime
import os

# Load Environment
try:
    with open('web/.env', 'r') as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                k, v = line.strip().split('=', 1)
                os.environ[k] = v.strip('"').strip("'")
except Exception as e:
    print(f"Warning: Could not load .env: {e}")

async def deduplicate():
    db = Prisma()
    await db.connect()
    
    print("Fetching all ExpectedMoveHistory records...")
    # Fetch all records, ordered by date
    # We might have thousands, so this might be heavy. 
    # Better to group by ticker/date if possible, but Prisma doesn't do GROUP BY easily with raw queries?
    # We can try raw query or just fetch strictly ordered and iterate.
    
    records = await db.expectedmovehistory.find_many(
        order=[
            {'ticker': 'asc'},
            {'date': 'asc'},
            {'id': 'asc'} # Deterministic tie breaker
        ]
    )
    
    print(f"Found {len(records)} records. Checking for duplicates...")
    
    duplicates_found = 0
    deleted_count = 0
    
    # Store visited (ticker, date_str) -> id
    visited = {}
    ids_to_delete = []
    
    for r in records:
        # Normalize date to YYYY-MM-DD
        d_str = r.date.strftime('%Y-%m-%d')
        key = (r.ticker, d_str)
        
        if key in visited:
            duplicates_found += 1
            # We found a duplicate. 
            # Strategy: Keep the FIRST one seen? Or checking which is "better"?
            # Since we sorted by ID asc, we keep the older ID? 
            # Or maybe we want the newer one if it was an update?
            # User said "clean that up". Usually newer data is better.
            # But upsert should have handled it. Duplicate implies distinct IDs.
            # Let's verify if they are truly identical or different.
            
            existing_id = visited[key]
            # print(f"Duplicate for {key}: Keep {existing_id}, Delete {r.id}")
            ids_to_delete.append(r.id)
        else:
            visited[key] = r.id
            
    print(f" identified {duplicates_found} duplicates to delete.")
    
    if ids_to_delete:
        # Delete in batches if needed
        count = await db.expectedmovehistory.delete_many(
            where={
                'id': {'in': ids_to_delete}
            }
        )
        print(f"Successfully deleted {count} duplicate records.")
    else:
        print("No duplicates found.")

    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(deduplicate())
