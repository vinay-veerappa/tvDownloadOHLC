import asyncio
import json
import os
import logging
from schwab.auth import client_from_token_file
from schwab.streaming import StreamClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestL2")

async def test_l2():
    # 1. Load client
    token_path = "token.json"
    if not os.path.exists(token_path):
        print(f"Error: Token file {token_path} not found.")
        return

    print("Loading secrets...")
    with open("secrets.json", "r") as f:
        secrets = json.load(f)
    app_key = secrets["app_key"]
    app_secret = secrets["app_secret"]

    print("Loading client from token...")
    client = client_from_token_file(token_path, app_key, app_secret)
    
    # 2. Setup StreamClient
    print("Initializing StreamClient...")
    stream_client = StreamClient(client)
    
    print("Attempting login()...")
    await stream_client.login()
    print("Login successful!")
    def on_message(msg):
        print(f"STREAM DATA: {json.dumps(msg)}")

    # 3. Test symbols and services
    plans = [
        ("LEVELONE_EQUITIES", ["AAPL"]),
        ("LEVELONE_FUTURES", ["/ES"]),
        ("NASDAQ_BOOK", ["AAPL"]),
        ("LEVELTWO_FUTURES", ["/ES"]),
    ]
    
    # Try subscriptions
    for svc, syms in plans:
        try:
            print(f"\n--- Testing Service: {svc} for {syms} ---")
            if "BOOK" in svc:
                await stream_client._service_op(syms, svc, "SUBS", stream_client.BookFields, fields=stream_client.BookFields.all_fields())
            elif svc == "LEVELTWO_FUTURES":
                await stream_client._service_op(syms, svc, "SUBS", stream_client.BookFields, fields=stream_client.BookFields.all_fields())
            elif "FUTURES" in svc:
                await stream_client._service_op(syms, svc, "SUBS", stream_client.LevelOneFuturesFields, fields=stream_client.LevelOneFuturesFields.all_fields())
            else:
                # Corrected: LevelOneEquityFields (singular in schwab-py? Let's check)
                # It is LevelOneEquityFields in some versions, LevelOneEquitiesFields in others.
                f_type = getattr(stream_client, "LevelOneEquityFields", getattr(stream_client, "LevelOneEquitiesFields", None))
                await stream_client._service_op(syms, svc, "SUBS", f_type, fields=f_type.all_fields())
            
            print(f"OK: Subscription request sent for {svc}!")
            
            # Wait for data
            print("Waiting 10s for ANY message...")
            for _ in range(15):
                try:
                    raw_msg = await asyncio.wait_for(stream_client._socket.recv(), timeout=2.0)
                    print(f"RAW MSG: {raw_msg}")
                    if svc in str(raw_msg):
                        print(f"MATCH: Found {svc} in message")
                        # If we get a response indicating success or data, we can move to next plan
                        if "response" in str(raw_msg) or "data" in str(raw_msg):
                            break
                except asyncio.TimeoutError:
                    pass
                
        except Exception as e:
            print(f"ERROR for {svc}: {e}")

    await stream_client.logout()

if __name__ == "__main__":
    asyncio.run(test_l2())
