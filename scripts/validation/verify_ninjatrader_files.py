
import pandas as pd
from pathlib import Path

def verify_file(file_path):
    print(f"\n--- Verifying {file_path} ---")
    p = Path(file_path)
    if not p.exists():
        print("❌ File not found.")
        return

    try:
        with open(p, 'r') as f:
            lines = [f.readline().strip() for _ in range(5)]
        
        print(f"Header: {lines[0]}")
        print(f"Row 1: {lines[1]}")
        print(f"Row 2: {lines[2]}")
        
        delimiter = ',' if ',' in lines[0] else ';'
        print(f"Detected Delimiter: '{delimiter}'")
        
        # Determine format
        if "Time" in lines[0] or "Close" in lines[0]:
            print("Format: Header detected.")
        else:
            print("Format: No Header (Assumed: Date;Time;O;H;L;C;V)")
            
    except Exception as e:
        print(f"❌ Error reading file: {e}")

if __name__ == "__main__":
    verify_file("data/NinjaTrader/GC Monday 189.csv")
    verify_file("data/NinjaTrader/CL Monday 1815.csv")
