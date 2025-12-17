import schwab
import json
import os

def authenticate():
    print("=== Schwab Authentication ===")
    
    # Load secrets
    if not os.path.exists("secrets.json"):
        print("Error: secrets.json not found.")
        print("Please create secrets.json with your app_key, app_secret, and callback_url.")
        return

    with open("secrets.json", "r") as f:
        secrets = json.load(f)
        
    app_key = secrets.get("app_key")
    app_secret = secrets.get("app_secret")
    callback_url = secrets.get("callback_url")
    
    if not app_key or not app_secret or "YOUR_" in app_key:
        print("Error: Please update secrets.json with your actual App Key and Secret.")
        return

    print("Starting OAuth flow...")
    print("A browser window should open to log in to Schwab.")
    
    try:
        # this will create/update 'token.json' in the current directory
        client = schwab.auth.client_from_manual_flow(
            app_key, 
            app_secret, 
            callback_url, 
            token_path="token.json"
        )
        print("\n✅ Authentication Successful!")
        print("Token saved to 'token.json'.")
        
        # Test a simple call
        print("Testing Account Fetch...")
        resp = client.get_account_numbers()
        if resp.status_code == 200:
            print(f"Linked Accounts: {resp.json()}")
        else:
            print(f"Fetch Failed: {resp.status_code} - {resp.text}")
        
    except Exception as e:
        print(f"\n❌ Authentication Failed: {e}")

if __name__ == "__main__":
    authenticate()
