
from pathlib import Path

CSV_PATH = Path("data/NinjaTrader/24Dec2025/ES Thursday 857.csv")

print(f"File Size: {CSV_PATH.stat().st_size / (1024*1024):.2f} MB")

with open(CSV_PATH, 'rb') as f:
    try:
        f.seek(-200, 2) # Go to end
        tail = f.read().decode('utf-8', errors='ignore')
        print("--- TAIL ---")
        print(tail)
    except Exception as e:
        print(f"Error reading tail: {e}")

# Check around line 139579
print("\n--- AROUND ERROR ---")
with open(CSV_PATH, 'r', encoding='utf-8', errors='replace') as f:
    for i in range(139575):
        next(f)
    for i in range(10):
        print(f"Line {139575+i}: {f.readline().strip()}")
