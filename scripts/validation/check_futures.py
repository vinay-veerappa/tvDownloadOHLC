import schwab
import json
import os

def check_futures():
    symbols = ["/ES", "/NQ", "ES", "NQ", "/ESH25", "/NQH25"] # Guesses
    
    if not os.path.exists("secrets.json") or not os.path.exists("token.json"):
        print("Error: secrets.json or token.json missing.")
        return

    with open("secrets.json", "r") as f:
        secrets = json.load(f)
        
    try:
        client = schwab.auth.client_from_token_file(
            token_path="token.json",
            api_key=secrets["app_key"], # Correct key name now
            app_secret=secrets["app_secret"],
            enforce_enums=False
        )
    except Exception as e:
        print(f"Auth Error: {e}")
        return

    print("Checking Futures Symbols...")
    for sym in symbols:
        try:
            print(f"--- {sym} ---")
            # Try getting quote
            resp = client.get_quote(sym).json()
            if sym in resp or (len(resp) > 0 and 'quote' in list(resp.values())[0]):
                print(f"  ✅ Quote Found: {resp}")
                
                # Try getting chain
                chain = client.get_option_chain(
                    sym,
                    strike_count=2,
                    strategy='ANALYTICAL'
                ).json()
                
                if chain.get('status') == 'FAILED':
                   print(f"  ❌ Option Chain Failed.")
                else:
                   print(f"  ✅ Option Chain Found ({len(chain.get('callExpDateMap',{}))} expirations)")
            else:
                print(f"  ❌ Quote Not Found.")
                
        except Exception as e:
            print(f"Error ({sym}): {e}")

if __name__ == "__main__":
    check_futures()
