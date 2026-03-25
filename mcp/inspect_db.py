import sqlite3
import os

db_path = r"C:\Users\vinay\.cache\codebase-memory-mcp\c-Users-vinay-tvDownloadOHLC.db"

if not os.path.exists(db_path):
    print(f"DB not found: {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("--- Node Labels ---")
cursor.execute("SELECT label, COUNT(*) FROM nodes GROUP BY label")
for row in cursor.fetchall():
    print(row)

print("\n--- Nodes Table Schema ---")
cursor.execute("PRAGMA table_info(nodes)")
for row in cursor.fetchall():
    print(row)

print("\n--- Sample Node ---")
cursor.execute("SELECT * FROM nodes LIMIT 2")
for row in cursor.fetchall():
    print(row)

print("\n--- Project Node Details ---")
cursor.execute("SELECT * FROM nodes WHERE label='Project'")
for row in cursor.fetchall():
    print(row)

print("\n--- Project Table Details ---")
cursor.execute("SELECT * FROM projects")
for row in cursor.fetchall():
    print(row)

conn.close()
