
import talib

print("TA-Lib Version:", talib.__version__)

print("\n--- Available Function Groups ---")
groups = talib.get_function_groups()
for group, functions in groups.items():
    print(f"\n[{group}]")
    for func in functions:
        print(f"  - {func}")

print("\n--- Search for 'Supertrend' ---")
all_functions = talib.get_functions()
found = [f for f in all_functions if 'super' in f.lower() or 'trend' in f.lower()]
if found:
    print("Found potential matches:", found)
else:
    print("No direct function found matching 'super' or 'trend' (Supertrend likely needs custom calculation using ATR).")
