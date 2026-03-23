import schwabdev
import inspect
import json

def inspect_schwabdev():
    print("--- Checking schwabdev module ---")
    client = schwabdev.Client("dummy_key", "dummy_secret", "https://127.0.0.1")
    
    # Check Stream method
    if hasattr(client, 'stream'):
        print("\nFound client.stream object.")
        streamer = client.stream
        methods = [m for m in dir(streamer) if not m.startswith('_')]
        print(f"Stream methods: {methods}")
        
        # Look for subscription patterns
        for m_name in methods:
            method = getattr(streamer, m_name)
            if callable(method):
                try:
                    sig = inspect.signature(method)
                    print(f"- {m_name}{sig}")
                except:
                    print(f"- {m_name} (no signature)")
    else:
        print("\nNo 'stream' attribute found in client.")
        print("Dir(client):", dir(client))

if __name__ == "__main__":
    try:
        inspect_schwabdev()
    except Exception as e:
        print(f"Error: {e}")
