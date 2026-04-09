import argparse
import pandas as pd
import sys
import time
from pathlib import Path
from .config import INSTRUMENTS, MACRO_RECORDS_PATH, DERIVED_DATA_DIR
from .macro_extractor import extract_macros_for_instrument
from .magnet_enricher import MagnetEnricher

def main():
    parser = argparse.ArgumentParser(description="Macro Research Pipeline - Sprint 1 (Extraction)")
    parser.add_argument("--instruments", type=str, help="Comma-separated instruments (e.g. NQ1,ES1)")
    parser.add_argument("--start", type=str, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, help="End date (YYYY-MM-DD)")
    parser.add_argument("--append", action="store_true", help="Append to existing records instead of overwrite")
    
    args = parser.parse_args()
    
    target_list = args.instruments.split(",") if args.instruments else list(INSTRUMENTS.keys())
    
    print(f"=== Macro Research Pipeline: Sprint 1 ===")
    print(f"Targets: {target_list}")
    print(f"Dates:   {args.start or 'Full History'} to {args.end or 'Present'}")
    
    all_results = []
    enricher = MagnetEnricher()
    
    start_run = time.time()
    
    for inst in target_list:
        print(f"\nProcessing {inst}...")
        try:
            df_inst = extract_macros_for_instrument(inst, args.start, args.end)
            if not df_inst.empty:
                df_inst['instrument'] = inst
                print(f"  -> Enriching with magnet context...")
                df_inst = enricher.enrich(df_inst, inst)
            print(f"  -> Extracted and enriched {len(df_inst)} macro records.")
            all_results.append(df_inst)
        except Exception as e:
            print(f"  !! Error processing {inst}: {e}")
            
    if not all_results:
        print("\nNo records extracted. Exiting.")
        return
        
    final_df = pd.concat(all_results, ignore_index=True)
    
    # Ensure output dir exists
    DERIVED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    if args.append and MACRO_RECORDS_PATH.exists():
        existing_df = pd.read_parquet(MACRO_RECORDS_PATH)
        final_df = pd.concat([existing_df, final_df], ignore_index=True)
        # Drop duplicates if any by macro_id
        final_df.drop_duplicates(subset=["macro_id"], keep="last", inplace=True)
    
    print(f"\nSaving {len(final_df)} total records to {MACRO_RECORDS_PATH}...")
    final_df.to_parquet(MACRO_RECORDS_PATH, index=False)
    
    duration = time.time() - start_run
    print(f"\nPipeline completed in {duration:.2f} seconds.")

if __name__ == "__main__":
    main()
