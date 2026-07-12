# ⚠️ MIXED AUTH PATH
# The streaming section below uses schwabdev.Client + Stream directly because
# the Schwab Hub does not expose a streaming WebSocket. The Greeks section
# routes through fetch_futures_option_chain_data(), which uses the internal
# Schwab Hub proxy. If the direct-streaming portion prompts for a token,
# refresh tokens.db separately.
import json
import os
import pprint
import time
import threading
import sys
from pathlib import Path
from schwabdev import Client, Stream

# Ensure we can import from the main project
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
from scripts.streaming.options.options_fetcher import fetch_futures_option_chain_data
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

    print("\n--- Testing Greeks Data via Hub Proxy ---")
    try:
        print("Fetching futures option chain data for /ES (this uses the hub proxy)...")
        # NOTE: Testing performed on 2026-07-06 during live market hours confirmed that 
        # Schwab's REST 'quotes' API endpoint does NOT return Greeks (Delta, Gamma, Theta, Vega) 
        # or Implied Volatility (IV) for futures options. While Bid/Ask/Last stream correctly, 
        # Greek fields structurally return 0.0. 
        # To get Greeks for futures options, a local Black-Scholes pricing model must be integrated.
        chain_data = fetch_futures_option_chain_data("/ES", [10])
        print(f"\nSuccessfully fetched {len(chain_data.contracts)} contracts!")
        print("Searching for strike 7580 contracts to verify greeks/quotes:\n")
        
        print("Available strikes returned by the API:\n")
        
        strikes = sorted(list(set(c.strike for c in chain_data.contracts)))
        print(f"Strikes found: {strikes}")
        
        # Still try to print 7575 if it exists
        found_7575 = False
        for contract in chain_data.contracts:
            if contract.strike == 7575.0:
                found_7575 = True
                print(f"\nSymbol: {contract.symbol}")
                print(f"  Bid:    {contract.bid}")
                print(f"  Ask:    {contract.ask}")
                print(f"  Last:   {contract.last}")
                print(f"  IV:     {contract.iv}")
                print(f"  Delta:  {contract.delta}")
                print(f"  Gamma:  {contract.gamma}")
                print(f"  Theta:  {contract.theta}")
                print(f"  Vega:   {contract.vega}")
                
        if not found_7575:
            print("\nStrike 7575 still not found.")

    except Exception as e:
        print(f"Hub Proxy Greeks Error: {e}")

if __name__ == "__main__":
    test_futures_options()
