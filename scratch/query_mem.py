import sqlite3
import json

DB_PATH = "mcp/memory.db"

def query_memories():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT category, topic, content FROM memories LIMIT 20")
        rows = cursor.fetchall()
        for row in rows:
            print(f"[{row[0]}] {row[1]}: {row[2][:100]}...")
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    query_memories()
