import os
import json
import glob

DATA_DIR = r"c:\Users\vinay\tvDownloadOHLC\web\public\data"

def repair_ticker(ticker, timeframe="1m"):
    dir_path = os.path.join(DATA_DIR, f"{ticker}_{timeframe}")
    print(f"--- Repairing {ticker} {timeframe} ---")
    
    files = glob.glob(os.path.join(dir_path, "chunk_*.json"))
    repaired_count = 0
    
    for file_path in files:
        file_name = os.path.basename(file_path)
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            if not data:
                continue

            # Check for dupes/unsorted
            needs_repair = False
            prev_time = -1
            seen_times = set()
            
            # Simple check first to avoid rewriting good files
            for bar in data:
                t = bar.get('time')
                if t is None: continue
                if t <= prev_time or t in seen_times:
                    needs_repair = True
                    break
                prev_time = t
                seen_times.add(t)
            
            if needs_repair:
                print(f"   Reparing {file_name}...")
                
                # Deduplicate based on time
                unique_data = {}
                for bar in data:
                    t = bar.get('time')
                    if t is not None:
                        unique_data[t] = bar # overwrites duplicates, keeping last
                
                # Sort
                sorted_data = sorted(unique_data.values(), key=lambda x: x['time'])
                
                # Save back
                with open(file_path, 'w') as f:
                    json.dump(sorted_data, f)
                
                repaired_count += 1
                
        except Exception as e:
            print(f"   Error processing {file_name}: {e}")

    print(f"Repair Complete. Fixed {repaired_count} chunks.")

if __name__ == "__main__":
    repair_ticker("NQ1")
