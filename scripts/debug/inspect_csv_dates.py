
import pandas as pd
import csv

def inspect_csv(file_path):
    print(f"Inspecting {file_path}...")
    min_date = None
    max_date = None
    
    has_target = False
    
    try:
        # Read header
        with open(file_path, 'r') as f:
            header = f.readline()
            print(f"Header: {header.strip()}")
            
            # Read first data line
            first = f.readline()
            print(f"First Line: {first.strip()}")
            parts = first.split(',')
            min_date = parts[0] + " " + parts[1]
            
            # Scan for 11/25
            # This is slow for 300MB in python line by line without optimization, 
            # but regex search failed so let's try a quick seek check or pandas chunk?
            pass

    except Exception as e:
        print(f"Error reading first lines: {e}")

    # Use Pandas for efficient tail reading and chunk checking
    try:
        # Read first chunk
        chunk_iter = pd.read_csv(file_path, chunksize=10000, names=['date','time','open','high','low','close','vol','up','down','x'])
        
        for i, chunk in enumerate(chunk_iter):
            # Check for target date string in 'date' column
            # Search for 11/25/2025 and 11/26/2025
            
            mask_25 = (chunk['date'] == '11/25/2025') & (chunk['time'].str.startswith('22:00'))
            mask_26 = (chunk['date'] == '11/26/2025') & (chunk['time'].str.startswith('03:00'))
            
            if mask_25.any():
                print("FOUND 11/25/2025 22:00 data!")
                print(chunk[mask_25].head())
                
            if mask_26.any():
                print("FOUND 11/26/2025 03:00 data!")
                print(chunk[mask_26].head())
            
            if i % 1000 == 0:
                print(f"Scanned {i*10000} rows...")
                
        # To get the very last date, we'd need to consume all. 
        # But we mostly care if 11/25 exists.
        
    except Exception as e:
        print(f"Pandas error: {e}")

if __name__ == "__main__":
    inspect_csv("data/NinjaTrader/15Dec2025/ES Monday 1719.csv")
