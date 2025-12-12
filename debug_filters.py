
from api.services.profiler_service import ProfilerService

def test_filters():
    ticker = "NQ1"
    
    print("\nTest 2: Filters=Any (Empty), Broken=No (All)")
    # Default filters = Any
    filters = {} 
    # Strict Broken = No (Held) for ALL
    broken_filters = {
        'Asia': 'No', 'London': 'No', 'NY1': 'No', 'NY2': 'No'
    }
    
    print(f"Testing for {ticker}...")
    stats = ProfilerService.analyze_profiler_stats(ticker, days=100)
    all_sessions = stats.get('sessions', [])
    print(f"Total Sessions: {len(all_sessions)}")
    
    matched_dates = ProfilerService.apply_filters(
        all_sessions, "NY1", filters, broken_filters, "Any"
    )
    
    print(f"Matched Dates (Held All): {len(matched_dates)}")
    print(matched_dates)

if __name__ == "__main__":
    test_filters()
