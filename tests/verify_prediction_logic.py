import sys
import os
import json

# Add project root to path
sys.path.append(os.getcwd())

from api.services.profiler_service import ProfilerService

def test_asia_prediction():
    print("Testing Asia Prediction...")
    # Test case from known data (e.g. Long False|Long False from my view_file earlier)
    # Actually I saw "Long False|Long True" in the file view
    
    # Let's try a distinct one: prev_ny1="Long False", prev_ny2="Long True"
    result = ProfilerService.get_asia_prediction(prev_ny1="Long False", prev_ny2="Long True")
    
    if "error" in result:
        print(f"FAILED: {result['error']}")
        return
        
    print("SUCCESS: Got Asia Prediction")
    print(json.dumps(result, indent=2))
    
    # Verify structure
    if "probabilities" not in result or "price_stats" not in result:
        print("FAILED: Missing keys in response")

def test_london_prediction():
    print("\nTesting London Prediction...")
    # Test case: prev_ny2="Long False", asia_status="Short True"
    # (Randomly picking, hoping it exists, or I will see error)
    
    result = ProfilerService.get_london_prediction(prev_ny2="Long False", curr_asia="Short True")
    
    if "error" in result:
        print(f"FAILED: {result['error']}")
        # It might be valid that it doesn't exist, but I want to verify positive case.
        # Let's try one I saw in file view: "Long False|Short True" (lines 2-38 of London json)
        # That means NY2=Long False, Asia=Short True
    else:
        print("SUCCESS: Got London Prediction")
        print(json.dumps(result, indent=2))

if __name__ == "__main__":
    try:
        test_asia_prediction()
        test_london_prediction()
    except Exception as e:
        print(f"CRASHED: {e}")
        import traceback
        traceback.print_exc()
