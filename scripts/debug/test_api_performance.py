import requests
import time
import json
import statistics

BASE_URL = "http://127.0.0.1:8000"
TICKER = "NQ1"

def test_endpoint(name, method, url, payload=None):
    print(f"\n--- Testing {name} ---")
    
    start_time = time.time()
    # Use stream=True to measure raw bytes before decompression
    if method == "POST":
        response = requests.post(url, json=payload, stream=True)
    else:
        response = requests.get(url, stream=True)
        
    # Read content to force transfer
    content = response.content
    duration = (time.time() - start_time) * 1000  # ms
    
    status = response.status_code
    
    # Check headers for Gzip
    encoding = response.headers.get("Content-Encoding", "None")
    
    # Size calculation
    # content is decompressed by requests automatically when accessing .content
    # raw_size = len(response.raw.read()) # Can't read raw after content access easily without hook
    # But usually 'Content-Length' header tells us transfer size if present
    content_len = response.headers.get("Content-Length")
    
    decompressed_size_kb = len(content) / 1024
    
    print(f"Status: {status}")
    print(f"Time: {duration:.2f} ms")
    print(f"Encoding: {encoding}")
    if content_len:
         print(f"Transfer Size: {int(content_len)/1024:.2f} KB")
    else:
         print(f"Transfer Size: Unknown (Chunked?)")
    print(f"Decompressed Size: {decompressed_size_kb:.2f} KB")
    
    if status != 200:
        print(f"Error: {response.text[:200]}")
        return None, duration
        
    try:
        data = response.json()
        if "count" in data:
            print(f"Count: {data['count']}")
        if "median" in data:
            print(f"Points: {len(data['median'])}")
        return data, duration
    except:
        return None, duration

import concurrent.futures

def benchmark_concurrent(clear_cache=True):
    print("\n--- Testing Concurrent Load (Simulating App Startup) ---")
    if clear_cache:
        requests.post(f"{BASE_URL}/stats/clear-cache/{TICKER}")
    else:
        print("Skipping cache clear (Warm Run)")
    
    # Define requests matching Profiler View load
    reqs = [
        ("Filtered Stats", "POST", f"{BASE_URL}/stats/filtered-stats", {
            "ticker": TICKER, "target_session": "NY1", "filters": {}, "intra_state": "Any"
        }),
        ("Price Model (Daily)", "POST", f"{BASE_URL}/stats/filtered-price-model", {
             "ticker": TICKER, "target_session": "Daily", "filters": {}, "intra_state": "Any", "bucket_minutes": 5
        }),
        ("Price Model (Outcome)", "POST", f"{BASE_URL}/stats/filtered-price-model", {
             "ticker": TICKER, "target_session": "NY1", "filters": {"NY1": "Long True"}, "intra_state": "Any", "bucket_minutes": 5
        }),
         ("Hod Lod", "GET", f"{BASE_URL}/stats/daily-hod-lod/{TICKER}", None),
         ("Level Touches", "GET", f"{BASE_URL}/stats/level-touches/{TICKER}", None),
    ]
    
    start_all = time.time()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(test_endpoint, r[0], r[1], r[2], r[3]): r[0] for r in reqs}
        
        for future in concurrent.futures.as_completed(futures):
            name = futures[future]
            try:
                _, duration = future.result()
                print(f"{name} finished in {duration:.2f} ms")
            except Exception as e:
                print(f"{name} failed: {e}")
                
    total_time = (time.time() - start_all) * 1000
    print(f"Total Concurrent Time: {total_time:.2f} ms")

def main():
    # benchmark_concurrent() instead of sequential
    print("\n=== RUN 1: Concurrent Cold (Cache Loading) ===")
    benchmark_concurrent()
    
    print("\n=== RUN 2: Concurrent Warm (Should be faster) ===")
    benchmark_concurrent(clear_cache=False)

if __name__ == "__main__":
    main()
