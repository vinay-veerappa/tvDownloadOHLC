
import requests
import json
import sys

BASE_URL = "http://127.0.0.1:8000"
TICKERS = ["GC1", "CL1", "RTY1", "YM1", "ES1", "NQ1"]

def test_endpoint(name, method, url, payload=None):
    print(f"Testing {name} [{method} {url}]...")
    try:
        if method == "GET":
            response = requests.get(f"{BASE_URL}{url}")
        else:
            response = requests.post(f"{BASE_URL}{url}", json=payload)
        
        status = response.status_code
        try:
            data = response.json()
            size = len(str(data))
            
            # Check for specific error keys even in 200 OK
            if isinstance(data, dict) and "error" in data:
                print(f"  ❌ Failed: {status} - Error in response: {data['error']}")
                return False
            
            # Check for empty data
            if isinstance(data, dict) and not data:
                 print(f"  ⚠️ Warning: {status} - Empty JSON Response")
            elif isinstance(data, list) and not data:
                 print(f"  ⚠️ Warning: {status} - Empty List Response")
            else:
                print(f"  ✅ Success: {status} - Size: {size} chars")
                return True
                
        except json.JSONDecodeError:
            print(f"  ❌ Failed: {status} - Invalid JSON")
            return False
            
    except Exception as e:
        print(f"  ❌ Connection Error: {e}")
        return False

def main():
    print("=== API Verification ===")
    
    success_count = 0
    total_count = 0
    
    for ticker in TICKERS:
        print(f"\n--- {ticker} ---")
        
        # 1. Daily HOD/LOD
        total_count += 1
        if test_endpoint("Daily HOD/LOD", "GET", f"/stats/daily-hod-lod/{ticker}"):
            success_count += 1
            
        # 2. Level Touches
        total_count += 1
        if test_endpoint("Level Touches", "GET", f"/stats/level-touches/{ticker}"):
            success_count += 1
            
        # 3. Filtered Stats (Default Daily)
        total_count += 1
        payload = {
            "ticker": ticker,
            "target_session": "NY1",
            "filters": {},
            "broken_filters": {},
            "intra_state": "Any"
        }
        if test_endpoint("Filtered Stats (NY1)", "POST", "/stats/filtered-stats", payload):
            success_count += 1
            
        # 4. Filtered Price Model (Default NY1)
        total_count += 1
        # Payload same as stats but logic differs
        if test_endpoint("Filtered Price Model (NY1)", "POST", "/stats/filtered-price-model", payload):
            success_count += 1

    print(f"\nTotal: {success_count}/{total_count} Passed")

if __name__ == "__main__":
    main()
