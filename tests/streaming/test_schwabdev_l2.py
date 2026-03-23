import json
import os
import time
from schwabdev import Client

def test_schwabdev():
    # 1. Load secrets
    if not os.path.exists("secrets.json"):
        print("secrets.json not found")
        return
    with open("secrets.json", "r") as f:
        secrets = json.load(f)
    
    # 2. Initialize Client
    # Schwabdev 3.x wants app_key, app_secret, callback_url
    client = Client(
        secrets["app_key"], 
        secrets["app_secret"], 
        secrets["callback_url"]
    )
    
    # 3. Use internal tokens if available (bypass manual flow if possible)
    # Schwabdev stores tokens in its own format. Let's try to manually push our token.
    if os.path.exists("token.json"):
        with open("token.json", "r") as f:
            tdata = json.load(f)
            # Schwabdev Token object structure: 
            # client.tokens.access_token, client.tokens.refresh_token, etc.
            client.tokens.access_token = tdata["token"]["access_token"]
            client.tokens.refresh_token = tdata["token"]["refresh_token"]
            # Set a far future expiration
            client.tokens.access_token_expires_at = time.time() + 1800
    
    # 4. Define callback
    def handle_msg(msg):
        print(f"SCHWABDEV DATA: {msg}")

    # 5. Start Stream
    print("Starting Schwabdev Stream...")
    client.stream.start(receiver=handle_msg)
    
    # Wait for login
    time.sleep(5)
    
    # 6. Try subscriptions
    month = "M"
    year = "26"
    futures_symbols = [f"./ES{month}{year}", f"./NQ{month}{year}"]
    
    print(f"\n--- Testing Level 1 Futures for {futures_symbols} ---")
    # level_one_futures(keys, fields, command="ADD")
    client.stream.send(client.stream.level_one_futures(futures_symbols, "0,1,2,3,4,5,6,7,8"))
    
    time.sleep(5)
    
    print(f"\n--- Testing NASDAQ_BOOK for ['SPY'] ---")
    # nasdaq_book(keys, fields, command="ADD")
    client.stream.send(client.stream.nasdaq_book(["SPY"], "0,1,2,3"))
    
    time.sleep(10)
    
    print("\nStopping Schwabdev Stream...")
    client.stream.stop()

if __name__ == "__main__":
    test_schwabdev()
