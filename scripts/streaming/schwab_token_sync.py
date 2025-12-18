import sqlite3
import json
import os
import time
from datetime import datetime

# Paths
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(ROOT_DIR, "web", "prisma", "dev.db")
TOKEN_PATH = os.path.join(ROOT_DIR, "token.json")

def sync_token_to_db():
    """
    Reads token.json and saves it to the SQLite SchwabToken table.
    """
    if not os.path.exists(TOKEN_PATH):
        print(f"⚠️ {TOKEN_PATH} not found. Skipping sync to DB.")
        return

    try:
        with open(TOKEN_PATH, "r") as f:
            full_data = json.load(f)
        
        # schwab-py saves token under 'token' key
        token_data = full_data.get("token")
        if not token_data:
            print("⚠️ 'token' key not found in token.json. Checking for flat structure...")
            token_data = full_data
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check if table exists (Prisma migration should have created it)
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='SchwabToken'")
        if not cursor.fetchone():
            print("❌ SchwabToken table does not exist in DB.")
            conn.close()
            return

        now_iso = datetime.now().isoformat()
        
        # id is "schwab-primary"
        sql = """
        INSERT INTO SchwabToken (id, accessToken, refreshToken, expiresAt, idToken, tokenType, scope, createdAt, updatedAt)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            accessToken = excluded.accessToken,
            refreshToken = excluded.refreshToken,
            expiresAt = excluded.expiresAt,
            idToken = excluded.idToken,
            tokenType = excluded.tokenType,
            scope = excluded.scope,
            updatedAt = excluded.updatedAt
        """
        
        params = (
            "schwab-primary",
            token_data.get("access_token"),
            token_data.get("refresh_token"),
            token_data.get("expires_at", 0),
            token_data.get("id_token"),
            token_data.get("token_type", "Bearer"),
            token_data.get("scope"),
            now_iso,
            now_iso
        )
        
        if not params[1]: # access_token is required
            print(f"❌ access_token is missing in token_data: {token_data.keys()}")
            conn.close()
            return

        cursor.execute(sql, params)
        conn.commit()
        conn.close()
        print(f"✅ Synced {TOKEN_PATH} to SQLite.")
        
    except Exception as e:
        print(f"❌ Token sync to DB failed: {e}")

def restore_token_from_db():
    """
    Reads token from SQLite and writes it to token.json if file is missing.
    """
    if not os.path.exists(DB_PATH):
        print(f"⚠️ DB not found at {DB_PATH}")
        return

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT accessToken, refreshToken, expiresAt, idToken, tokenType, scope FROM SchwabToken WHERE id = 'schwab-primary'")
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            print("⚠️ No token found in DB.")
            return

        token_data = {
            "access_token": row[0],
            "refresh_token": row[1],
            "expires_at": row[2],
            "id_token": row[3],
            "token_type": row[4],
            "scope": row[5]
        }
        
        # Wrap in schwab-py format
        full_data = {
            "creation_timestamp": int(time.time()),
            "token": token_data
        }
        
        if not os.path.exists(TOKEN_PATH):
            with open(TOKEN_PATH, "w") as f:
                json.dump(full_data, f, indent=2)
            print(f"✅ Restored {TOKEN_PATH} from SQLite.")
        else:
            print(f"ℹ️ {TOKEN_PATH} already exists. Skipping restore.")
            
    except Exception as e:
        print(f"❌ Token restore from DB failed: {e}")

if __name__ == "__main__":
    # If run directly, sync to DB
    sync_token_to_db()
