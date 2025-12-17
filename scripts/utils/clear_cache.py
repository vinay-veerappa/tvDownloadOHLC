import requests
try:
    requests.post("http://localhost:8000/stats/clear-cache")
    print("Cache cleared")
except Exception as e:
    print(f"Failed: {e}")
