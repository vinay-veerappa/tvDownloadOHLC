import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from api.features.profiler.service import ProfilerService

def test_profiler_date_filtering():
    # 1. Fetch full stats to know which dates exist
    full_stats = ProfilerService.get_filtered_stats("NQ1", "NY1")
    assert "error" not in full_stats, "Failed to load base stats"
    
    matched_dates = full_stats["matched_dates"]
    assert len(matched_dates) > 0, "No dates returned in full range"
    
    # Sort them to get proper boundaries
    sorted_dates = sorted(matched_dates)
    
    # Choose start and end dates within the available set
    test_start = sorted_dates[len(sorted_dates) // 4]
    test_end = sorted_dates[3 * len(sorted_dates) // 4]
    
    print(f"Testing filter range: {test_start} to {test_end}")
    
    # 2. Query with date filters
    filtered = ProfilerService.get_filtered_stats("NQ1", "NY1", start_date=test_start, end_date=test_end)
    assert "error" not in filtered
    
    filtered_dates = filtered["matched_dates"]
    
    # 3. Verify all returned dates fall strictly within the start and end dates
    for d in filtered_dates:
        assert test_start <= d <= test_end, f"Date {d} is outside filter [{test_start}, {test_end}]"
        
    print("Verification passed! All dates are strictly within boundaries.")

def test_profiler_price_model_date_filtering():
    # Fetch price model with date range
    full_stats = ProfilerService.get_filtered_stats("NQ1", "NY1")
    sorted_dates = sorted(full_stats["matched_dates"])
    test_start = sorted_dates[len(sorted_dates) // 4]
    test_end = sorted_dates[3 * len(sorted_dates) // 4]
    
    price_model = ProfilerService.get_filtered_price_model(
        "NQ1", "NY1", start_date=test_start, end_date=test_end
    )
    assert "error" not in price_model
    assert "median" in price_model
    # Count of days matched should be equal to filtered stats count of target_session
    filtered_stats = ProfilerService.get_filtered_stats("NQ1", "NY1", start_date=test_start, end_date=test_end)
    expected_count = sum(1 for s in filtered_stats["sessions"] if s.get("session") == "NY1")
    assert price_model["count"] == expected_count
    
    print("Price model verification passed!")

def test_profiler_transition_filters():
    # Fetch stats with transition filters on previous sessions
    filters = {"Prev Asia": "Short True"}
    full_stats = ProfilerService.get_filtered_stats("NQ1", "NY1", filters=filters)
    assert "error" not in full_stats
    matched_dates = sorted(full_stats["matched_dates"])
    assert len(matched_dates) > 0, "No dates matched transition filter"
    
    # Take a date that matched
    target_date = matched_dates[0]
    
    # Query specifically with start_date=target_date and end_date=target_date
    filtered = ProfilerService.get_filtered_stats(
        "NQ1", "NY1", filters=filters, start_date=target_date, end_date=target_date
    )
    assert target_date in filtered["matched_dates"], f"Transition boundary bug: target_date {target_date} failed to match when start_date is set to it."
    
    print("Transition filters verification passed!")

if __name__ == "__main__":
    test_profiler_date_filtering()
    test_profiler_price_model_date_filtering()
    test_profiler_transition_filters()
