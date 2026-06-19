import urllib.request
import json
import sys

def main():
    url = "http://127.0.0.1:8001/history?symbol=/NQ&limit=2"
    print(f"Sending GET request to {url}...")
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            status = response.getcode()
            body = response.read().decode('utf-8')
            print(f"Status: {status}")
            data = json.loads(body)
            print(f"Success! Keys in response: {list(data.keys())}")
            print(f"Candles count: {len(data.get('candles', []))}")
            if data.get('candles'):
                print(f"Latest candle: {data['candles'][-1]}")
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    main()
