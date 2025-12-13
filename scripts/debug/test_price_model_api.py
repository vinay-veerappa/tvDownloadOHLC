
import requests
import json
import sys

def main():
    ticker = "NQ1"
    url = "http://localhost:8000/stats/filtered-price-model"
    payload = {
        "ticker": ticker,
        "target_session": "Daily",
        "filters": {},
        "broken_filters": {},
        "intra_state": "Any",
        "bucket_minutes": 5
    }

    print(f"--- Testing API Endpoint: {url} ---")
    print(f"Payload: {payload}")

    try:
        response = requests.post(url, json=payload)
        
        if response.status_code != 200:
            print(f"Error: {response.status_code} - {response.text}")
            return
        
        data = response.json()
        
        avg_data = data.get("average", [])
        print(f"\nAPI Response Count: {len(avg_data)}")
        
        if avg_data:
            print("First 5 API points:", avg_data[:5])
            print("Last 5 API points:", avg_data[-5:])
        
        # Save for comparison
        with open("api_price_model_response.json", "w") as f:
            json.dump(data, f, indent=2)
        print("\nResponse saved to api_price_model_response.json")

    except Exception as e:
        print(f"Exception: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
