
import sys
import os
import pandas as pd
sys.path.append(os.getcwd())

from api.services.profiler_service import ProfilerService

def test_filters():
    # Mock Sessions
    sessions = [
        {'date': '2023-01-01', 'session': 'London', 'status': 'Long True', 'broken': False},
        {'date': '2023-01-01', 'session': 'NY1', 'status': 'Short False', 'broken': True},
        
        {'date': '2023-01-02', 'session': 'London', 'status': 'Short True', 'broken': False},
        {'date': '2023-01-02', 'session': 'NY1', 'status': 'Long True', 'broken': False},
        
        {'date': '2023-01-03', 'session': 'London', 'status': 'Long False', 'broken': False},
        {'date': '2023-01-03', 'session': 'NY1', 'status': 'Short True', 'broken': False},
    ]
    
    # Test 1: Filter London Long
    filters = {'London': 'Long'}
    matched = ProfilerService.apply_filters(sessions, 'NY1', filters=filters)
    print(f"Filter 'London': 'Long' -> {matched}")
    expected = ['2023-01-01', '2023-01-03']
    if sorted(matched) == sorted(expected):
        print("PASS")
    else:
        print(f"FAIL. Expected {expected}")

    # Test 2: Filter London Short True
    filters = {'London': 'Short True'}
    matched = ProfilerService.apply_filters(sessions, 'NY1', filters=filters)
    print(f"Filter 'London': 'Short True' -> {matched}")
    expected = ['2023-01-02']
    if sorted(matched) == sorted(expected):
        print("PASS")
    else:
        print(f"FAIL. Expected {expected}")

if __name__ == "__main__":
    test_filters()
