import requests
import time

url = "http://localhost:8000/api/sessions/ES1?range_type=hourly"
print(f"Fetching {url}...")
start = time.time()
try:
    res = requests.get(url, timeout=10)
    elapsed = time.time() - start
    print(f"Status: {res.status_code}")
    print(f"Time: {elapsed:.2f}s")
    if res.status_code == 200:
        data = res.json()
        print(f"Data Items: {len(data)}")
        if len(data) > 0:
            print("First Item:", data[0])
    else:
        print("Error:", res.text)
except Exception as e:
    print(f"Failed: {e}")
