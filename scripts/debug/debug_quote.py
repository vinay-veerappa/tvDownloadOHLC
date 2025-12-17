import schwab
import json
import os
import sys

def get_client():
    if not os.path.exists("secrets.json") or not os.path.exists("token.json"):
        print("Missing credentials")
        return None

    with open("secrets.json", "r") as f:
        secrets = json.load(f)
        
    try:
        return schwab.auth.client_from_token_file(
            token_path="token.json",
            api_key=secrets["app_key"],
            app_secret=secrets["app_secret"],
            enforce_enums=False
        )
    except Exception as e:
        print(f"Auth failed: {e}")
        return None

if __name__ == "__main__":
    client = get_client()
    if not client: sys.exit(1)

    test_tickers = ['//ES', './ES', 'ES']
    
    print(f"----- DEBUGGING CHAIN ERRORS -----")
    for t in test_tickers:
        print(f"\n[Testing: {t}]")
        try:
             chain = client.get_option_chain(t).json()
             
             if 'errors' in chain:
                 print(f"    Failed with Errors: {chain['errors']}")
             elif 'underlying' in chain:
                 print(f"    Success! Underlying: {chain['underlying'].get('description')} Last: {chain['underlying'].get('last')}")
                 # Check first strike to verify asset class
                 call_map = chain.get('callExpDateMap', {})
                 if call_map:
                     first = list(call_map.keys())[0]
                     strikes = list(call_map[first].keys())[:3]
                     print(f"    Strikes: {strikes}")
             else:
                 print(f"    Unknown Response: {list(chain.keys())}")
                 
        except Exception as e:
            print(f"Error: {e}")
