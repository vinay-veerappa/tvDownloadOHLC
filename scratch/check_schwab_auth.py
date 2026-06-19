import json
import os
from schwabdev import Client

def main():
    secrets_path = "secrets.json"
    if not os.path.exists(secrets_path):
        print("secrets.json not found")
        return
        
    with open(secrets_path, 'r') as f:
        secrets = json.load(f)
        
    try:
        print("Initializing schwabdev Client with tokens.db...")
        client = Client(
            secrets["app_key"], 
            secrets["app_secret"], 
            secrets["callback_url"],
            tokens_db="tokens.db",
            timeout=30
        )
        print("Calling linked_accounts()...")
        resp = client.linked_accounts()
        print(f"Status Code: {resp.status_code}")
        print(f"Response: {resp.text}")
        
        print("\nCalling quotes() for /NQ...")
        resp_q = client.quotes(["/NQ"])
        print(f"Status Code: {resp_q.status_code}")
        print(f"Response: {resp_q.text[:400]}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
