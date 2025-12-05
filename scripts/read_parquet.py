import sys
import pandas as pd
import json
import os

def read_parquet_to_json(file_path):
    try:
        if not os.path.exists(file_path):
            print(json.dumps({"error": f"File not found: {file_path}"}))
            return

        df = pd.read_parquet(file_path)
        
        # Reset index to move time/date/datetime from index to column
        df.reset_index(inplace=True)
            
        # Rename columns if necessary (case insensitive)
        df.columns = [c.lower() for c in df.columns]
        
        # Map common time column names to 'time'
        if 'datetime' in df.columns:
            df.rename(columns={'datetime': 'time'}, inplace=True)
        elif 'date' in df.columns:
            df.rename(columns={'date': 'time'}, inplace=True)
            
        # Convert time to UNIX timestamp (seconds) for compatibility
        if pd.api.types.is_datetime64_any_dtype(df['time']):
            # Convert to seconds (int)
            df['time'] = (df['time'].astype('int64') // 10**9).astype(int)
            
        # Ensure data is sorted by time
        df.sort_values('time', inplace=True)
            
        # Select only OHLCV data
        result_data = df[['time', 'open', 'high', 'low', 'close']].to_dict(orient='records')
        
        print(json.dumps({"success": True, "data": result_data}))

    except Exception as e:
        # Include column info in error for debugging
        cols = "Unknown"
        try:
            df = pd.read_parquet(file_path)
            cols = f"Columns: {list(df.columns)}, Index: {df.index.names}"
        except:
            pass
        print(json.dumps({"error": f"{str(e)} | {cols}"}))

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"error": "No file path provided"}))
    else:
        read_parquet_to_json(sys.argv[1])
