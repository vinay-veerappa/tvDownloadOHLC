import json
import os
import pprint
import time
import threading
from schwabdev import Client, Stream

def test_futures_options():
    # Load secrets
    secrets_path = "secrets.json"
    if not os.path.exists(secrets_path):
        print(f"Error: {secrets_path} not found.")
        return

    with open(secrets_path, "r") as f:
        secrets = json.load(f)

    # Initialize Client
    client = Client(
        app_key=secrets["app_key"],
        app_secret=secrets["app_secret"],
        callback_url=secrets["callback_url"],
        tokens_db="tokens.db"
    )

    print("\n--- Testing Expiration Chain for /ES ---")
    try:
        resp = client.option_expiration_chain(symbol="/ES")
        if resp.status_code == 200:
            print("Successfully fetched /ES expiration chain!")
            pprint.pprint(resp.json())
        else:
            print(f"Failed /ES expiration chain: {resp.status_code} - {resp.text}")
    except Exception as e:
        print(f"Error: {e}")

    print("\n--- Testing Streaming for Futures Options ---")
    
    def on_message(message):
        print(f"\n[STREAM MESSAGE] {message}\n")

    try:
        stream = Stream(client)
        # Start stream in background
        t = threading.Thread(target=stream.start, args=(on_message,))
        t.daemon = True
        t.start()
        
        time.sleep(3) # Wait for login/connect
        
        # Try to subscribe to /ES for futures options data
        # 'LEVELONE_FUTURES_OPTIONS' is the service name from docs
        print("Sending subscription for /ES futures options...")
        stream.send(stream.level_one_futures_options(["/ES"], "0,1,2,3,4,5"))
        
        print("Waiting 10 seconds for messages...")
        time.sleep(10)
        stream.stop()
    except Exception as e:
        print(f"Streaming Error: {e}")

if __name__ == "__main__":
    test_futures_options()
