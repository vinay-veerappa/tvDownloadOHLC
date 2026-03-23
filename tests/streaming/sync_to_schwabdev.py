import json
import sqlite3
import os
from datetime import datetime, timezone

def sync_tokens(token_json="token.json", tokens_db="tokens.db"):
    print(f"Syncing {token_json} to {tokens_db}...")
    
    if not os.path.exists(token_json):
        print(f"Error: {token_json} not found.")
        return False
        
    with open(token_json, "r") as f:
        tdata = json.load(f)
        
    token = tdata.get("token", {})
    access_token = token.get("access_token")
    refresh_token = token.get("refresh_token")
    id_token = token.get("id_token", "")
    expires_at = token.get("expires_at", 0)
    
    # schwabdev expects ISO strings
    # We'll estimate the 'issued' time based on expiration
    # access token usually lasts 30 min (1800s)
    at_issued = datetime.fromtimestamp(expires_at - 1800, tz=timezone.utc).isoformat()
    # refresh token usually lasts 7 days (604800s)
    rt_issued = datetime.fromtimestamp(expires_at - 1800, tz=timezone.utc).isoformat() 
    
    conn = sqlite3.connect(tokens_db)
    cur = conn.cursor()
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS schwabdev (
            access_token_issued TEXT NOT NULL,
            refresh_token_issued TEXT NOT NULL,
            access_token TEXT NOT NULL,
            refresh_token TEXT NOT NULL,
            id_token TEXT NOT NULL,
            expires_in INTEGER,
            token_type TEXT,
            scope TEXT
        );
    """)
    
    cur.execute("DELETE FROM schwabdev")
    cur.execute("""
        INSERT INTO schwabdev (
            access_token_issued,
            refresh_token_issued,
            access_token,
            refresh_token,
            id_token,
            expires_in,
            token_type,
            scope
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        at_issued,
        rt_issued,
        access_token,
        refresh_token,
        id_token,
        1800,
        "Bearer",
        "api"
    ))
    
    conn.commit()
    conn.close()
    print("✅ Sync complete.")
    return True

if __name__ == "__main__":
    sync_tokens()
