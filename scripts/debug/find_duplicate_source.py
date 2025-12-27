
import json
import os
import glob

def find_timestamp(ticker, timeframe, target_timestamp):
    base_dir = f"web/public/data/{ticker}_{timeframe}"
    print(f"Searching for {target_timestamp} in {base_dir}...")
    
    # Check meta first? No, let's just scan chunks.
    chunk_files = glob.glob(os.path.join(base_dir, "chunk_*.json"))
    chunk_files.sort(key=lambda x: int(os.path.basename(x).split('_')[1].split('.')[0]))
    
    found_locations = []
    
    for cf in chunk_files:
        try:
            with open(cf, 'r') as f:
                data = json.load(f)
                
            count = 0
            indices = []
            for i, bar in enumerate(data):
                if bar['time'] == target_timestamp:
                    count += 1
                    indices.append(i)
            
            if count > 0:
                print(f"FOUND in {os.path.basename(cf)}: {count} times at indices {indices}")
                found_locations.append((cf, count, indices))
                
                # Check neighbors for context
                for idx in indices:
                    prev = data[idx-1] if idx > 0 else None
                    curr = data[idx]
                    next_bar = data[idx+1] if idx < len(data)-1 else None
                    
                    print(f"  Context around index {idx}:")
                    if prev: print(f"    Prev: {prev['time']} ({prev.get('date', '')})")
                    print(f"    Curr: {curr['time']} ({curr.get('date', '')}) <--- MATCH")
                    if next_bar: print(f"    Next: {next_bar['time']} ({next_bar.get('date', '')})")

        except Exception as e:
            print(f"Error reading {cf}: {e}")

    return found_locations

if __name__ == "__main__":
    # Timestamp from user log: 1764126000
    find_timestamp("ES1", "1m", 1764126000)
