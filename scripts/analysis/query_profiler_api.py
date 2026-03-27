import argparse
import json
import requests
import sys

def main():
    parser = argparse.ArgumentParser(description="Query Profiler API for conditional probabilities")
    parser.add_argument("--ticker", type=str, default="NQ1", help="Ticker (default: NQ1)")
    parser.add_argument("--target", type=str, default="London", help="Target session (London, NY1, NY2)")
    parser.add_argument("--asia", type=str, help="Filter: Asia status (e.g. 'Long True')")
    parser.add_argument("--london", type=str, help="Filter: London status")
    parser.add_argument("--ny1", type=str, help="Filter: NY1 status")
    parser.add_argument("--url", type=str, default="http://127.0.0.1:8000/stats/filtered-stats", help="API URL")
    
    args = parser.parse_args()
    
    filters = {}
    if args.asia: filters["Asia"] = args.asia
    if args.london: filters["London"] = args.london
    if args.ny1: filters["NY1"] = args.ny1
    
    payload = {
        "ticker": args.ticker,
        "target_session": args.target,
        "filters": filters,
        "broken_filters": {},
        "intra_state": "Any"
    }
    
    print(f"📡 Querying Profiler API for {args.ticker} {args.target}...")
    if filters:
        print(f"   Filters: {filters}")
    
    try:
        response = requests.post(args.url, json=payload, timeout=10)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.ConnectionError:
        print("❌ Error: Could not connect to API server at " + args.url)
        print("   Make sure the FastAPI server is running (python api/main.py)")
        sys.exit(1)
    except Exception as e:
        print(f"❌ API Error: {e}")
        sys.exit(1)
        
    count = data.get("count", 0)
    distribution = data.get("distribution", {})
    
    print(f"\n==================================================")
    print(f"📊 CONDITIONAL PROBABILITIES: {args.ticker}")
    print(f"Context: {filters if filters else 'None'}")
    print(f"Sample Size: {count} days")
    print(f"==================================================\n")
    
    if count == 0:
        print("⚠️ No historical matches found for this combination.")
        return

    # Sort distribution by alphabetical key for consistency
    sorted_dist = sorted(distribution.items())
    
    print(f"[ {args.target} OUTCOME DISTRIBUTION ]")
    for status, hits in sorted_dist:
        prob = (hits / count) * 100
        bar = "█" * int(prob / 5)
        print(f"{status:12}: {prob:5.1f}% ({hits:3} hits) {bar}")
        
    range_stats = data.get("range_stats", {})
    if range_stats:
        print(f"\n[ RANGE EXPECTANCY (MEDIANS) ]")
        h_med = range_stats.get("high_pct", {}).get("median")
        l_med = range_stats.get("low_pct", {}).get("median")
        print(f"High % Median: {h_med:+6.2f}%")
        print(f"Low  % Median: {l_med:+6.2f}%")
        
    print("\n" + "="*50)

if __name__ == "__main__":
    main()
