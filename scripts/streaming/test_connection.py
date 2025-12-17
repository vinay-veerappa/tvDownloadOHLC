
import schwab
import json
import os

def test_schwab_connection():
    if not os.path.exists("secrets.json") or not os.path.exists("token.json"):
        print("Missing secrets.json or token.json")
        return

    with open("secrets.json", "r") as f:
        secrets = json.load(f)

    try:
        client = schwab.auth.client_from_token_file(
            token_path="token.json",
            api_key=secrets["app_key"],
            app_secret=secrets["app_secret"],
            enforce_enums=False
        )
        
        print("--- Testing get_account_numbers ---")
        resp = client.get_account_numbers()
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            print(f"Success! {resp.json()}")
        else:
            print(f"Failed: {resp.text}")
        
        print("\n--- Testing get_accounts ---")
        resp2 = client.get_accounts()
        print(f"Status: {resp2.status_code}")
        if resp2.status_code == 200:
            print(f"Success! Accounts: {resp2.json()}")
        else:
            print(f"Failed: {resp2.text}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_schwab_connection()
