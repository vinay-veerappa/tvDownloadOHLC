import argparse
import pandas as pd
import sys
import time
from pathlib import Path
from .config import INSTRUMENTS, MACRO_RECORDS_PATH, FVG_DETAIL_PATH, DERIVED_DATA_DIR
from .data_loader import load_bars_duckdb
from .macro_extractor import extract_macros_for_instrument
from .magnet_enricher import MagnetEnricher
from .context_enricher import enrich_context
from .news_enricher import enrich_news
from .daily_joins import join_daily_data
from .fvg_detector import detect_fvgs
from .fvg_tracker import track_fvg_outcomes
from .post_macro import compute_post_macro_outcomes
from .sequencer import compute_sequences
from .calendar_generator import generate_calendar
from .lib.context_join import join_daily_context
from .lib.range_core import add_extension_columns, add_macro_pd_fields

def main():
    parser = argparse.ArgumentParser(description="Macro Research Pipeline - Sprint 2 (Full Context)")
    parser.add_argument("--instruments", type=str, help="Comma-separated instruments (e.g. NQ1,ES1)")
    parser.add_argument("--start", type=str, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, help="End date (YYYY-MM-DD)")
    parser.add_argument("--append", action="store_true", help="Append to existing records instead of overwrite")
    
    args = parser.parse_args()
    
    target_list = args.instruments.split(",") if args.instruments else list(INSTRUMENTS.keys())
    
    print(f"=== Macro Research Pipeline: Sprint 2 ===")
    print(f"Targets: {target_list}")
    print(f"Dates:   {args.start or 'Full History'} to {args.end or 'Present'}")
    
    all_results = []
    all_fvgs = []
    enricher = MagnetEnricher()
    
    start_run = time.time()
    
    for inst in target_list:
        print(f"\nProcessing {inst}...")
        try:
            # Load 1m bars once for all modules to reuse
            bars_1m = load_bars_duckdb(inst, args.start, args.end)
            if bars_1m.empty:
                print(f"  -> No data found for {inst}.")
                continue

            # 1. Base Extraction (Sprint 1)
            # Pass bars directly to avoid redundant reload
            df_inst = extract_macros_for_instrument(inst, args.start, args.end, bars_in=bars_1m)
            if df_inst.empty:
                print(f"  -> No macros extracted for {inst}.")
                continue
            
            df_inst['instrument'] = inst

            # 2. Magnet Enrichment
            print(f"  -> Enriching with magnet context...")
            df_inst = enricher.enrich(df_inst, bars_1m)

            # 3. Context & Daily Joins (Sprint 2)
            print(f"  -> Enriching with session context and daily joins...")
            df_inst = enrich_context(df_inst, bars_1m)
            df_inst = join_daily_data(df_inst, inst)
            
            # 3.5 News Enrichment
            print(f"  -> Enriching with economic news...")
            df_inst = enrich_news(df_inst)

            # 4. Outcomes & Sequencing
            # Crucial: compute_post_macro_outcomes generates 'lookforward_end' used by FVG tracker
            print(f"  -> Computing post-macro outcomes and sequences...")
            df_inst = compute_post_macro_outcomes(df_inst, bars_1m)
            df_inst = compute_sequences(df_inst)
            
            # 4.5 Calendar Enrichment (OpEx Week, triple_witching, etc.)
            print(f"  -> Adding calendar context (OpEx)...")
            # Set a broad range for calendar to ensure coverage
            cal_start = args.start or "2006-01-01"
            cal_end = args.end or "2026-12-31"
            calendar_df = generate_calendar(cal_start, cal_end)
            
            # Ensure dtypes match for join (generated calendar uses datetime64[ns])
            df_inst = df_inst.merge(calendar_df, on='trading_date', how='left')

            # 4.6 Phase 2 — daily_context join + macro-level enrichment
            print(f"  -> Joining daily context (gap, ATR, session outcome, streaks)...")
            df_inst = join_daily_context(df_inst, inst)

            # Opening-candle continuation overlay field (macro-level).
            if {"first_hour_direction", "real_direction"}.issubset(df_inst.columns):
                df_inst["macro_aligned_with_first_hour"] = (
                    ((df_inst["first_hour_direction"] == "GREEN") & (df_inst["real_direction"] == "up"))
                    | ((df_inst["first_hour_direction"] == "RED") & (df_inst["real_direction"] == "down"))
                )
            else:
                df_inst["macro_aligned_with_first_hour"] = False

            print(f"  -> Adding extension levels and PD interaction fields...")
            if {"post_h", "post_l", "high", "low"}.issubset(df_inst.columns):
                df_inst = add_extension_columns(df_inst)
            if {"high", "low", "pdh", "pdl"}.issubset(df_inst.columns):
                df_inst = add_macro_pd_fields(df_inst)

            # 5. FVG Detection & Tracking
            print(f"  -> Detecting and tracking FVGs...")
            fvgs = detect_fvgs(df_inst, bars_1m)
            if not fvgs.empty:
                # Optimized: Pass macro_df to use precomputed lookforward_end
                fvgs = track_fvg_outcomes(fvgs, bars_1m, macro_df=df_inst)
                
                # Summarize FVGs for macro_records
                fvg_counts = fvgs.groupby('macro_id').size().rename('fvg_count')
                
                # FVG Direction Pattern (e.g., "Bull-Bull-Bear")
                fvg_patterns = fvgs.sort_values(['macro_id', 'sequence_in_macro']).groupby('macro_id')['fvg_type'].apply(
                    lambda x: "-".join([s[:4].capitalize() for s in x])
                ).rename('fvg_direction_pattern')
                
                df_inst = df_inst.merge(fvg_counts, on='macro_id', how='left')
                df_inst = df_inst.merge(fvg_patterns, on='macro_id', how='left')
                
                df_inst['fvg_count'] = df_inst['fvg_count'].fillna(0).astype(int)
                df_inst['has_fvg'] = df_inst['fvg_count'] > 0
                all_fvgs.append(fvgs)

            print(f"  -> Completed processing {len(df_inst)} records for {inst}.")
            all_results.append(df_inst)

        except Exception as e:
            print(f"  !! Error processing {inst}: {e}")
            import traceback
            traceback.print_exc()
            
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
        final_df = final_df.drop_duplicates(subset=["macro_id"], keep="last", inplace=False)
    
    print(f"\nSaving {len(final_df)} total records to {MACRO_RECORDS_PATH}...")
    final_df.to_parquet(MACRO_RECORDS_PATH, index=False)
    
    if all_fvgs:
        final_fvgs = pd.concat(all_fvgs, ignore_index=True)
        print(f"Saving {len(final_fvgs)} FVG details to {FVG_DETAIL_PATH}...")
        final_fvgs.to_parquet(FVG_DETAIL_PATH, index=False)
    
    duration = time.time() - start_run
    print(f"\nPipeline completed in {duration:.2f} seconds.")

if __name__ == "__main__":
    main()