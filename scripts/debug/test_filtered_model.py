import requests
import json

url = "http://localhost:8000/stats/filtered-price-model"
payload = {
    "ticker": "NQ1",
    "session": "NY2",
    "outcome": 1,
    "bucket_minutes": 5
}

try:
    res = requests.post(url, json=payload, timeout=10)
    print(f"Status: {res.status_code}")
    if res.status_code == 200:
        data = res.json()
        print("Keys:", data.keys())
        if "median" in data:
            print("Median is:", type(data["median"]))
            if isinstance(data["median"], dict):
                print("Median Keys:", data["median"].keys())
            else:
                print("Median Value:", data["median"])
except Exception as e:
    print(f"Error: {e}")
