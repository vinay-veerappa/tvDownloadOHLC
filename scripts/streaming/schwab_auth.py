import sqlite3
import time
import json
import os
import schwab
from datetime import datetime, timezone

def sync_to_tokens_db(token_data: dict):
    """
    Syncs token data to the 'schwabdev' table in tokens.db used by the schwabdev library.
    """
    db_path = "tokens.db"
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Ensure table exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schwabdev (
                access_token_issued TEXT,
                refresh_token_issued TEXT,
                access_token TEXT,
                refresh_token TEXT,
                id_token TEXT,
                expires_in INTEGER,
                token_type TEXT,
                scope TEXT
            )
        """)
        
        # Clear old tokens
        cursor.execute("DELETE FROM schwabdev")
        
        now = datetime.now(timezone.utc).isoformat() if hasattr(datetime, 'now') else time.strftime('%Y-%m-%dT%H:%M:%S+00:00', time.gmtime())
        # Handle different token structures
        t = token_data.get("token", token_data)
        
        cursor.execute("""
            INSERT INTO schwabdev (
                access_token_issued, refresh_token_issued, access_token, 
                refresh_token, id_token, expires_in, token_type, scope
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            now, now, 
            t.get("access_token"), 
            t.get("refresh_token"), 
            t.get("id_token"), 
            t.get("expires_in", 1800), 
            t.get("token_type", "Bearer"), 
            t.get("scope", "api")
        ))
        
        conn.commit()
        conn.close()
        print("✅ Synced tokens to 'tokens.db' (for schwabdev provider).")
    except Exception as e:
        print(f"⚠️ Failed to sync to tokens.db: {e}")

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
        print("Token saved to 'token.json' (for schwab-py provider).")
        
        # Read the newly created token to sync to DB
        with open("token.json", "r") as f:
            token_data = json.load(f)
        sync_to_tokens_db(token_data)
        
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
