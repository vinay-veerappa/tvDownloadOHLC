import requests
import json

def test_metadata():
    try:
        response = requests.get("http://127.0.0.1:8000/api/candle-science/metadata")
        print(f"Metadata Status: {response.status_code}")
        print(f"Metadata Content: {response.text[:200]}...")
    except Exception as e:
        print(f"Metadata Error: {e}")

def test_calculate():
    payload = {
        "ticker": "NQ1",
        "timeframe": "1m",
        "filters": {}
    }
    try:
        response = requests.post("http://127.0.0.1:8000/api/candle-science/calculate", json=payload)
        print(f"Calculate Status: {response.status_code}")
        print(f"Calculate Content: {response.text[:500]}...")
    except Exception as e:
        print(f"Calculate Error: {e}")

if __name__ == "__main__":
    test_metadata()
    test_calculate()
