import json
import math

def debug_frontend():
    # Load Data
    with open('data/NQ1_level_touches.json', 'r') as f:
        touches = json.load(f)
    
    # Mock filtered dates (all dates in file)
    filtered_dates = list(touches.keys())
    # Or just last 50 days
    filtered_dates = sorted(filtered_dates)[-50:]
    
    # Run tests for different sessions
    test_session(touches, filtered_dates, 'daily_open', 'Daily', {'start': '18:00', 'end': '17:00'})
    test_session(touches, filtered_dates, 'asia_mid', 'AsiaMid', {'start': '02:00', 'end': '17:00'})
    test_session(touches, filtered_dates, 'pdh', 'Asia', {'start': '18:00', 'end': '02:00'}) # Crossing midnight

def test_session(touches, filtered_dates, level_key, target_session, session_range):
    print(f"\nAnalyzing {level_key} for {target_session} ({session_range})")
    
    touched_count = 0
    total_count = 0
    
    for date in filtered_dates:
        if date not in touches: continue
        day_data = touches[date]
        if level_key not in day_data: continue
        
        level_data = day_data[level_key]
        total_count += 1
        
        if level_data.get('touched') and level_data.get('touch_times'):
            # Filter hits
            valid_hits = [t for t in level_data['touch_times'] if is_in_range(t, session_range)]
            
            if valid_hits:
                touched_count += 1
                valid_hits.sort()
                first_hit = valid_hits[0]
                # print(f"  {date}: Hit at {first_hit}")
    
    print(f"Total: {total_count}")
    print(f"Touched: {touched_count}")
    print(f"Hit Rate: {touched_count/total_count*100:.2f}%")

def is_in_range(time_str, range_def):
    if range_def['start'] == '00:00' and range_def['end'] == '23:59':
        return True
        
    t = int(time_str.replace(':', ''))
    start = int(range_def['start'].replace(':', ''))
    end = int(range_def['end'].replace(':', ''))
    
    if start < end:
        return t >= start and t < end
    else:
        return t >= start or t < end

if __name__ == "__main__":
    debug_frontend()
