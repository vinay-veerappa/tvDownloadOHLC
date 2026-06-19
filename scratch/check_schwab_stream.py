import asyncio
import json
import os
import time
from schwabdev import Client, Stream

def receiver(message):
    print(f"Direct Stream Message: {message[:300]}")

async def main():
    secrets_path = "secrets.json"
    if not os.path.exists(secrets_path):
        print("secrets.json not found")
        return
        
    with open(secrets_path, 'r') as f:
        secrets = json.load(f)
        
    try:
        print("Initializing client...")
        client = Client(
            secrets["app_key"], 
            secrets["app_secret"], 
            secrets["callback_url"],
            tokens_db="tokens.db",
            timeout=30
        )
        print("Initializing stream...")
        stream = Stream(client)
        
        print("Starting stream...")
        stream.start(receiver=receiver)
        
        await asyncio.sleep(3)
        
        print("Subscribing to level one futures for /NQ...")
        # Resolve active futures first:
        resp = client.quotes(["/NQ"])
        data = resp.json()
        active_nq = list(data.keys())[0]
        print(f"Active contract: {active_nq}")
        
        stream.send(stream.level_one_futures([active_nq], "0,1,2,3,4,5,6"))
        
        print("Listening for 10 seconds...")
        await asyncio.sleep(10)
        
        print("Stopping stream...")
        stream.stop()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
