import pandas as pd
import json
import os
import math

def export_for_notebooklm(ticker="NQ1"):
    output_dir = "c:/Users/vinay/tvDownloadOHLC/docs/DailyClassification/data_exports"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Created output directory: {output_dir}")

    # --- 1. Export Daily Classification (Parquet -> CSV) ---
    class_path = f"c:/Users/vinay/tvDownloadOHLC/data/derived/{ticker}_daily_classification.parquet"
    if os.path.exists(class_path):
        print(f"Loading {class_path}...")
        df_class = pd.read_parquet(class_path)
        
        # Sort by date
        df_class = df_class.sort_values('date')
        
        # Determine split size (NotebookLM limit safe zone: ~500k rows/50MB)
        # 20 years of daily data is only ~5k rows. No split needed.
        csv_path = f"{output_dir}/{ticker}_daily_classification.csv"
        df_class.to_csv(csv_path, index=False)
        print(f"[SUCCESS] Exported: {csv_path} ({len(df_class)} rows)")
    else:
        print(f"[ERROR] Logic file not found: {class_path}")

    # --- 2. Export Profiler Data (JSON -> CSV) ---
    prof_path = f"c:/Users/vinay/tvDownloadOHLC/data/{ticker}_profiler.json"
    if os.path.exists(prof_path):
        print(f"Loading {prof_path}...")
        with open(prof_path, 'r') as f:
            data = json.load(f)
            
        df_prof = pd.DataFrame(data)
        
        # Sort by date and session start
        if 'start_ts' in df_prof.columns:
            df_prof = df_prof.sort_values('start_ts')
            
        # Check size for potential splitting
        # NotebookLM prefers smaller semantic chunks. 
        # Check size for potential splitting
        # NotebookLM prefers smaller semantic chunks. 
        # Approx word count for 20k rows is ~550k words, which is > 500k limit.
        # Split into chunks of 2,500 rows to be absolutely safe (approx 70k words per file).
        
        row_limit = 2500 
        total_rows = len(df_prof)
        
        if total_rows > row_limit:
            print(f"Large dataset ({total_rows} rows). Splitting...")
            num_chunks = math.ceil(total_rows / row_limit)
            
            for i in range(num_chunks):
                start_idx = i * row_limit
                end_idx = min((i + 1) * row_limit, total_rows)
                chunk = df_prof.iloc[start_idx:end_idx]
                
                chunk_path = f"{output_dir}/{ticker}_profiler_part{i+1}.csv"
                chunk.to_csv(chunk_path, index=False)
                print(f"[SUCCESS] Exported chunk: {chunk_path} ({len(chunk)} rows)")
        else:
            prof_csv_path = f"{output_dir}/{ticker}_profiler.csv"
            df_prof.to_csv(prof_csv_path, index=False)
            print(f"[SUCCESS] Exported: {prof_csv_path} ({total_rows} rows)")
            
    else:
        print(f"[ERROR] Profiler file not found: {prof_path}")

if __name__ == "__main__":
    export_for_notebooklm("NQ1")
