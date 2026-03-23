import schwab
import json
import os
import datetime

def debug_futures():
    if not os.path.exists("secrets.json") or not os.path.exists("token.json"):
        print("Missing credentials")
        return

    with open("secrets.json", "r") as f:
        secrets = json.load(f)

    client = schwab.auth.client_from_token_file(
        token_path="token.json",
        api_key=secrets["app_key"],
        app_secret=secrets["app_secret"],
        enforce_enums=False
    )

    symbols = ["$DJI", "$RUT", "DIA", "IWM"]
    
    print(f"--- Testing Quote & Chain for: {symbols} ---")
    for s in symbols:
        try:
            print(f"\nRequesting Quote: {s}")
            resp = client.get_quote(s).json()
            # print(f"Quote Response: {json.dumps(resp, indent=2)}") # noisy
            print(f"Quote Status: {list(resp.keys()) if isinstance(resp, dict) else 'Error'}")

            print(f"Requesting Chain: {s}")
            chain = client.get_option_chain(s, strike_count=1).json()
            # Check if valid chain
            if "errors" in chain:
                print(f"Chain Error: {chain}")
            else:
                print(f"Chain Success! Underlying: {chain.get('symbol')} Status: {chain.get('status')}")
            
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    debug_futures()
