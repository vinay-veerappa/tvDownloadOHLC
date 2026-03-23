import asyncio
import json
import os
import logging
from schwab.auth import client_from_token_file
from schwab.streaming import StreamClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DiscoverL2")

async def discover():
    token_path = "token.json"
    client = client_from_token_file(token_path, "dummy", "dummy")
    stream_client = StreamClient(client)
    await stream_client.login()

    # (March 22, 2026 -> June M)
    symbols = ["./ESM26"]
    
    candidates = [
        "FUTURES_BOOK", "LEVELTWO_FUTURES", "L2_FUTURES", "BOOK_FUTURES", 
        "FUTURES_LEVEL_TWO", "FUTURES_LEVEL2", "FUTURES_L2",
        "CME_BOOK", "CBOT_BOOK", "NYMEX_BOOK", "COMEX_BOOK",
        "LEVEL_TWO_FUTURES", "FUTURES_MARKET_DEPTH", "MARKET_DEPTH_FUTURES",
        "FUTURES_ORDER_BOOK", "ORDER_BOOK_FUTURES",
        "FUTURES_BOOK_DATA", "FUTURES_DATA_BOOK"
    ]

    for svc in candidates:
        try:
            print(f"Testing: {svc} ...", end=" ", flush=True)
            # Use minimal parameters
            await stream_client._service_op(symbols, svc, "SUBS")
            print("✅ SUCCESS (or at least accepted)")
            
            # Wait a bit for data
            for _ in range(3):
                msg = await stream_client.handle_message()
                if msg:
                    print(f"  DATA from {svc}: {msg}")
            
        except Exception as e:
            msg = str(e)
            if "response code: 11" in msg:
                print("❌ Code 11 (Not Available)")
            elif "response code: 21" in msg:
                print("⚠️ Code 21 (Format Error - Service might exist!)")
            else:
                print(f"❌ Error: {msg}")
        
        await asyncio.sleep(1)

    await stream_client.logout()

if __name__ == "__main__":
    asyncio.run(discover())
