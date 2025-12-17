import schwab
try:
    # Print Field Enums to verify IDs
    print("\n--- Chart Equity Fields ---")
    for field in schwab.streaming.StreamClient.ChartEquityFields:
        print(f"{field.name}: {field.value}")
        
    print("\n--- Chart Futures Fields ---")
    for field in schwab.streaming.StreamClient.ChartFuturesFields:
        print(f"{field.name}: {field.value}")
        
except Exception as e:
    print(f"Error: {e}")
