import sqlite3
import time
import json
import os
import schwab
from datetime import datetime, timezone

def sync_to_tokens_db(token_data: dict):
    """
    Syncs token data to the 'schwabdev' table in tokens.db used by the schwabdev library.
    Preserves existing refresh_token and id_token if not returned in current payload.
    """
    db_path = "tokens.db"
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Read existing tokens if available
        existing_refresh_token = ""
        existing_id_token = ""
        try:
            cursor.execute("SELECT refresh_token, id_token FROM schwabdev LIMIT 1")
            row = cursor.fetchone()
            if row:
                existing_refresh_token = row[0] or ""
                existing_id_token = row[1] or ""
        except Exception:
            pass

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
        
        now = datetime.now(timezone.utc).isoformat()
        t = token_data.get("token", token_data)
        
        access_token = t.get("access_token") or ""
        refresh_token = t.get("refresh_token") or existing_refresh_token or access_token
        id_token = t.get("id_token") or existing_id_token or "none"
        expires_in = int(t.get("expires_in", 1800))
        token_type = t.get("token_type", "Bearer")
        scope = t.get("scope", "api")

        cursor.execute("""
            INSERT INTO schwabdev (
                access_token_issued, refresh_token_issued, access_token, 
                refresh_token, id_token, expires_in, token_type, scope
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            now, now, 
            access_token, 
            refresh_token, 
            id_token, 
            expires_in, 
            token_type, 
            scope
        ))
        
        conn.commit()
        conn.close()
        print("[OK] Synced tokens to 'tokens.db' (for schwabdev provider).")
    except Exception as e:
        print(f"[WARNING] Failed to sync to tokens.db: {e}")

import sys
from pathlib import Path

# Add project root to sys.path dynamically
_current_dir = Path(__file__).resolve().parent
while _current_dir.name and _current_dir.name != "scripts":
    _current_dir = _current_dir.parent
if _current_dir.name == "scripts":
    _root_dir = str(_current_dir.parent)
    if _root_dir not in sys.path:
        sys.path.insert(0, _root_dir)

import webbrowser

from scripts.streaming.credentials_manager import get_schwab_credentials, load_secrets
from scripts.streaming.windows_notifier import (
    notify_schwab_token_expired, 
    notify_schwab_token_refreshed, 
    notify_windows_toast
)


def authenticate():
    print("=== Schwab Authentication ===")
    
    app_key, app_secret, callback_url = get_schwab_credentials()
    
    if not app_key or not app_secret or "YOUR_" in app_key:
        print("[ERROR] Please update secrets.json or encrypted credentials with your actual App Key and Secret.")
        notify_schwab_token_expired()
        return

    print("[INFO] Starting Schwab OAuth flow...")
    notify_schwab_token_expired()
    
    try:
        # Generate OAuth Authorization URL
        auth_context = schwab.auth.get_auth_context(app_key, callback_url)
        auth_url = auth_context.authorization_url
        
        # Automatically open default web browser directly to login page
        print("[INFO] Opening default web browser directly to Schwab login page...")
        try:
            webbrowser.open(auth_url)
        except Exception as e:
            print(f"[WARNING] Could not auto-open browser: {e}")

        print("\n**************************************************************")
        print("1. Log in with your Schwab credentials in the opened browser window.")
        print("2. Click 'Allow' to grant access to your account.")
        print("3. Copy the ENTIRE redirected address bar URL, paste it below, and press Enter.")
        print("**************************************************************\n")

        received_url = input("Redirect URL> ").strip()

        token_write_func = schwab.auth.__make_update_token_func("token.json")
        client = schwab.auth.client_from_received_url(
            app_key, app_secret, auth_context, received_url, token_write_func,
            asyncio=False, enforce_enums=True
        )

        print("\n[SUCCESS] Authentication Successful!")
        print("Token saved to 'token.json' (for schwab-py provider).")
        notify_schwab_token_refreshed()
        
        # Read the newly created token to sync to DB
        with open("token.json", "r") as f:
            token_data = json.load(f)
        sync_to_tokens_db(token_data)
        
        # Test account fetch
        print("Testing Account Fetch...")
        resp = client.get_account_numbers()
        if resp.status_code == 200:
            print(f"Linked Accounts: {resp.json()}")
        else:
            print(f"Fetch Failed: {resp.status_code} - {resp.text}")
    except Exception as e:
        print(f"\n[ERROR] Authentication Failed: {e}")
        notify_schwab_token_expired()


if __name__ == "__main__":
    authenticate()
