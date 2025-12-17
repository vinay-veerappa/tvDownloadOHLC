import sys
import pandas as pd
import json
import os

def read_parquet_to_json(file_path, max_rows=None, offset=0):
    """
    Read parquet file and return JSON data with pagination support.
    
    Args:
        file_path: Path to parquet file
        max_rows: Maximum number of rows to return (None = all)
        offset: Number of rows to skip from the END (for loading older data)
               offset=0 returns most recent data
               offset=50000 skips last 50000 rows and returns older data
    
    Returns JSON with:
        - data: OHLC data
        - totalRows: Total rows in file
        - startIdx: First row index returned
        - endIdx: Last row index returned
    """
    try:
        if not os.path.exists(file_path):
            print(json.dumps({"error": f"File not found: {file_path}"}))
            return

        df = pd.read_parquet(file_path)
        total_rows = len(df)
        
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
        df = df.reset_index(drop=True)
        
        # Calculate slice indices for pagination
        # offset is from the END, so we work backwards
        if max_rows:
            end_idx = total_rows - offset
            start_idx = max(0, end_idx - max_rows)
            df = df.iloc[start_idx:end_idx]
        else:
            start_idx = 0
            end_idx = total_rows
            
        # Select only OHLCV data
        result_data = df[['time', 'open', 'high', 'low', 'close']].to_dict(orient='records')
        
        print(json.dumps({
            "success": True, 
            "data": result_data, 
            "totalRows": total_rows,
            "startIdx": start_idx,
            "endIdx": end_idx
        }))

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
        file_path = sys.argv[1]
        max_rows = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2] else None
        offset = int(sys.argv[3]) if len(sys.argv) > 3 else 0
        read_parquet_to_json(file_path, max_rows, offset)


