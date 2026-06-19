import json
import os
from schwabdev import Client, Stream

def main():
    secrets_path = "secrets.json"
    if not os.path.exists(secrets_path):
        return
    with open(secrets_path, 'r') as f:
        secrets = json.load(f)
    client = Client(
        secrets["app_key"], 
        secrets["app_secret"], 
        secrets["callback_url"],
        tokens_db="tokens.db"
    )
    stream = Stream(client)
    print("Stream attributes and methods:")
    for attr in dir(stream):
        if not attr.startswith("_"):
            print(f"  {attr}")
            
    print("\nUnderlying websocket or thread attributes:")
    if hasattr(stream, "active"):
        print(f"  active: {stream.active}")
    if hasattr(stream, "thread"):
        print(f"  thread: {stream.thread}")
    if hasattr(stream, "ws"):
        print(f"  ws: {stream.ws}")

if __name__ == "__main__":
    main()
