import requests
import json

BASE_URL = "http://127.0.0.1:8000/api/candle-science"

def test_metadata():
    print("Testing /metadata...")
    response = requests.get(f"{BASE_URL}/metadata")
    print(f"Status: {response.status_code}")
    print(f"Data: {json.dumps(response.json(), indent=2)[:200]}...")

def test_filters():
    print("\nTesting /filters for NQ1 1d...")
    response = requests.get(f"{BASE_URL}/filters?ticker=NQ1&timeframe=1d")
    print(f"Status: {response.status_code}")
    print(f"Data: {json.dumps(response.json(), indent=2)}")

def test_calculate():
    print("\nTesting /calculate for NQ1 1d...")
    payload = {
        "ticker": "NQ1",
        "timeframe": "1d",
        "filters": {
            "years": ["2023", "2024"],
            "c1Direction": "bull"
        }
    }
    response = requests.post(f"{BASE_URL}/calculate", json=payload)
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"Sample Count: {data.get('sample_count')}")
        print("\n--- Debugging High Wicks Structure ---")
        import json
        print(json.dumps(data.get('high_wicks'), indent=2))
        
        c3_bull = data.get('direction', {}).get('c3', {}).get('bull')
        print(f"\nC3 Bull Prob: {c3_bull}%")
    else:
        print(f"Error: {response.text}")

if __name__ == "__main__":
    try:
        test_metadata()
        test_filters()
        test_calculate()
    except Exception as e:
        print(f"Connection failed: {e}. Make sure the FastAPI server is running.")
