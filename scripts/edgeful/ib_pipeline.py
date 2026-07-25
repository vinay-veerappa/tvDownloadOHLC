import argparse
import pandas as pd
import numpy as np
import time
import os
from pathlib import Path
from typing import List


import sys
from pathlib import Path

# Add project root to sys.path dynamically
_current_dir = Path(__file__).resolve().parent
while _current_dir.name and _current_dir.name != "scripts":
    _current_dir = _current_dir.parent
if _current_dir.name == "scripts":
    _root_dir = str(_current_dir.parent)
    if _root_dir not in sys.path:
        sys.path.insert(0, _root_dir)

from scripts.edgeful.lib.data_loader import get_loader
from scripts.libs_py.nqstats.ib import calculate_ib_statistics_v5

# Configuration
INSTRUMENTS = ["NQ1", "ES1", "YM1", "RTY1", "CL1", "GC1"]
SESSIONS = ["Globex IB", "Tokyo IB", "London IB", "Midnight OR", "NY AM IB", "NY PM IB"]
ICT_DIR = Path("data/derived/ICT")
ALL_TABLES = {"facts", "ext", "play", "level_touch"}

def process_single_symbol(symbol, start_date, end_date, vix_series, force_regen=None, incremental=False):
    # Setup imports inside process for multiprocessing cleanliness on Windows
    import pandas as pd
    import numpy as np
    from pathlib import Path
    from scripts.edgeful.lib.data_loader import get_loader
    from scripts.libs_py.nqstats.ib import calculate_ib_statistics_v5
    from scripts.libs_py.nqstats.sessions import normalize_to_eastern, get_logical_trading_date, get_dst_flags
    from scripts.libs_py.nqstats.ib import detect_fvgs_v5
    
    loader = get_loader()
    print(f"\nProcessing {symbol}...")
    try:
        # Load 1m bars
        df_1m = loader.load_1m(symbol, start_date, end_date)
        if df_1m.empty:
            print(f"  -> No 1m data found for {symbol}.")
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
        
        # Drop unused volume column to save memory
        df_1m = df_1m.drop(columns=['volume'], errors='ignore')
        print(f"  -> Loaded {len(df_1m)} 1m bars for {symbol}.")
        
        # 1. Pre-calculate global timezone-naive America/New_York features
        print(f"  -> Pre-calculating timezone and dates for {symbol}...")
        df_1m_precalc = normalize_to_eastern(df_1m)
        df_1m_precalc = df_1m_precalc[~df_1m_precalc.index.isna()]
        df_1m_precalc['timestamp'] = df_1m_precalc.index
        df_1m_precalc['datetime'] = df_1m_precalc.index
        df_1m_precalc['logical_date'] = get_logical_trading_date(df_1m_precalc.index)
        df_1m_precalc['bar_idx'] = np.arange(len(df_1m_precalc))
        df_1m_precalc['minutes_from_midnight'] = df_1m_precalc.index.hour * 60 + df_1m_precalc.index.minute
        
        us_dst, uk_dst = get_dst_flags(df_1m_precalc.index)
        df_1m_precalc['us_dst'] = us_dst
        df_1m_precalc['uk_dst'] = uk_dst
        
        # Setup existing daily ATR if in incremental mode
        existing_atr = None
        last_date = None
        facts_path = Path("data/derived/ib_facts.parquet")
        if incremental and facts_path.exists() and (force_regen is None or "precalc" not in force_regen):
            try:
                df_facts = pd.read_parquet(facts_path)
                df_facts = df_facts[df_facts['symbol'] == symbol]
                if not df_facts.empty:
                    df_facts = df_facts[df_facts['range_atr'].notna() & (df_facts['range_atr'] > 0)]
                    if not df_facts.empty:
                        df_facts['daily_atr'] = df_facts['range_pts'] / df_facts['range_atr']
                        existing_atr = df_facts.groupby('trading_day')['daily_atr'].first()
                        last_date = existing_atr.index.max()
            except Exception as e:
                print(f"  -> [WARN] Failed to load existing ATR history: {e}")

        # 2. Pre-calculate Daily ATR (Wilder's 14)
        print(f"  -> Pre-calculating daily ATR for {symbol}...")
        daily_ohlc = df_1m_precalc.groupby('logical_date').agg(
            high=('high', 'max'),
            low=('low', 'min'),
            close=('close', 'last')
        )
        prev_close = daily_ohlc['close'].shift(1)
        tr = pd.concat([
            daily_ohlc['high'] - daily_ohlc['low'],
            (daily_ohlc['high'] - prev_close).abs(),
            (daily_ohlc['low'] - prev_close).abs()
        ], axis=1).max(axis=1)
        
        if existing_atr is not None and last_date in existing_atr:
            daily_atr_precalc = pd.Series(index=daily_ohlc.index, dtype=float)
            for d in daily_ohlc.index:
                if d in existing_atr:
                    daily_atr_precalc[d] = existing_atr[d]
            
            sorted_dates = sorted(daily_ohlc.index)
            try:
                last_idx = sorted_dates.index(last_date)
                curr_atr = existing_atr[last_date]
                for i in range(last_idx + 1, len(sorted_dates)):
                    d = sorted_dates[i]
                    d_tr = tr.loc[d]
                    if pd.notna(d_tr):
                        curr_atr = (curr_atr * 13.0 + d_tr) / 14.0
                        daily_atr_precalc[d] = curr_atr
            except ValueError:
                daily_atr_precalc = tr.ewm(com=14 - 1, adjust=False, min_periods=14).mean()
        else:
            daily_atr_precalc = tr.ewm(com=14 - 1, adjust=False, min_periods=14).mean()
        
        # 3. Load FVG database from data/derived/ICT/ (generated by fvg_database.py).
        #    Uses the 5m FVG database. Falls back to resample+detect if DB not found
        #    or --force-regen fvg was passed.
        fvg_db_path = ICT_DIR / f"{symbol}_fvg_5m.parquet"
        force_fvg = force_regen and "fvg" in force_regen
        if fvg_db_path.exists() and not force_fvg:
            print(f"  -> Loading FVG database from {fvg_db_path.name}...")
            fvg_all = pd.read_parquet(fvg_db_path)
            # Filter by bar_time (index) to exactly match the UTC date boundary
            # that load_1m(start_date, end_date) uses — avoids including overnight
            # bars from the prior calendar day that belong to the next logical_date.
            if start_date:
                fvg_all = fvg_all[fvg_all.index >= pd.to_datetime(start_date)]
            if end_date:
                fvg_all = fvg_all[fvg_all.index < pd.to_datetime(end_date) + pd.Timedelta(days=1)]
            fvg_df_precalc = fvg_all.drop(columns=["symbol", "timeframe"], errors="ignore")
        else:
            if not fvg_db_path.exists():
                print(f"  -> [WARN] FVG database not found. Run: python -m scripts.edgeful.fvg_database")
            print(f"  -> Resampling 1m->5m and detecting FVGs (fallback)...")
            df_5m = df_1m_precalc[["high", "low"]].resample("5min", origin="start_day").agg(
                {"high": "max", "low": "min"}
            ).dropna()
            fvg_df_precalc = detect_fvgs_v5(df_5m, "5min")
            fvg_df_precalc["logical_date"] = get_logical_trading_date(fvg_df_precalc.index)
        
        symbol_facts = []
        symbol_touches = []
        symbol_plays = []
        
        for sess in SESSIONS:
            time_bases = ["ET_fixed"]
            if sess in ["Tokyo IB", "London IB"]:
                time_bases = ["ET_fixed", "event_anchored"]
                
            for tb in time_bases:
                print(f"    - [{symbol}] Running {sess} ({tb})...")
                facts, touches, plays = calculate_ib_statistics_v5(
                    df_1m=df_1m,
                    symbol=symbol,
                    session_choice=sess,
                    time_basis=tb,
                    use_fvg=True,
                    vix_series=vix_series,
                    df_1m_precalc=df_1m_precalc,
                    fvg_df_precalc=fvg_df_precalc,
                    daily_atr_precalc=daily_atr_precalc
                )
                
                if not facts.empty:
                    symbol_facts.append(facts)
                if not touches.empty:
                    symbol_touches.append(touches)
                if not plays.empty:
                    symbol_plays.append(plays)
                    
        f_df = pd.concat(symbol_facts, ignore_index=True) if symbol_facts else pd.DataFrame()
        t_df = pd.concat(symbol_touches, ignore_index=True) if symbol_touches else pd.DataFrame()
        p_df = pd.concat(symbol_plays, ignore_index=True) if symbol_plays else pd.DataFrame()
        
        return f_df, t_df, p_df
    except Exception as e:
        print(f"  -> Error processing {symbol}: {e}")
        import traceback
        traceback.print_exc()
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

def main():
    parser = argparse.ArgumentParser(description="Multi-Session Initial Balance Statistics Pipeline v5")
    parser.add_argument("--instruments", type=str, help="Comma-separated instruments (default: all)")
    parser.add_argument("--start", type=str, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, help="End date (YYYY-MM-DD)")
    parser.add_argument("--outdir", type=str, default="data/derived", help="Output directory for Parquet files")
    parser.add_argument(
        "--force-regen", type=str, default="",
        help="Comma-separated list of layers to force-regenerate: fvg,precalc,all (e.g. --force-regen fvg)"
    )
    parser.add_argument(
        "--tables", type=str, default="",
        help="Comma-separated subset of tables to regenerate: facts,ext,play,level_touch (default: all)"
    )
    parser.add_argument(
        "--incremental", "-i", action="store_true",
        help="Incremental update mode: processes only new dates since last execution"
    )
    parser.add_argument(
        "--workers", "-w", type=int, default=0,
        help="Number of parallel workers to use (default: min of CPU count, target list, capped at 3 for memory safety)"
    )
    parser.add_argument(
        "--custom-ranges", type=str, default=None,
        help="Path to custom ranges YAML config (FR-11, BL-4). Custom ranges are registered into SESSION_CONFIGS_V5 and appended to the session list."
    )
    
    args = parser.parse_args()

    # BL-4: Load custom ranges if specified
    if args.custom_ranges:
        from scripts.edgeful.ib_session_config import load_custom_ranges
        registered = load_custom_ranges(args.custom_ranges)
        SESSIONS.extend(registered)
        print(f"Loaded {len(registered)} custom ranges: {registered}")
    
    target_list = args.instruments.split(",") if args.instruments else INSTRUMENTS
    out_dir = Path(args.outdir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ICT_DIR.mkdir(parents=True, exist_ok=True)

    # Parse selective flags
    force_regen = set(args.force_regen.lower().split(",")) if args.force_regen else set()
    if "all" in force_regen:
        force_regen = {"fvg", "precalc"}
    tables_requested = set(args.tables.lower().split(",")) if args.tables else ALL_TABLES
    tables_requested &= ALL_TABLES  # sanitize
    
    print(f"=== Multi-Session IB Statistics Pipeline ===")
    print(f"Targets:  {target_list}")
    print(f"Dates:    {args.start or 'Full History'} to {args.end or 'Present'}")
    print(f"Output:   {out_dir}")
    
    start_run = time.time()
    
    loader = get_loader()
    
    # Auto-detect incremental start dates per symbol
    symbol_starts = {}
    symbol_last_dates = {}
    incremental_mode = args.incremental
    facts_path = out_dir / "ib_facts.parquet"
    
    if incremental_mode and facts_path.exists():
        try:
            existing_facts = pd.read_parquet(facts_path)
            if not existing_facts.empty and "symbol" in existing_facts.columns and "trading_day" in existing_facts.columns:
                max_dates = existing_facts.groupby("symbol")["trading_day"].max()
                for symbol in target_list:
                    if symbol in max_dates:
                        last_date = max_dates[symbol]
                        symbol_last_dates[symbol] = last_date
                        # Back-date by 60 days for daily ATR warm-up and session/timezone safety
                        start_dt = pd.to_datetime(last_date) - pd.Timedelta(days=60)
                        symbol_starts[symbol] = start_dt.strftime("%Y-%m-%d")
                        print(f"  -> [{symbol}] Incremental mode: start date set to {symbol_starts[symbol]} (last date: {last_date})")
                    else:
                        symbol_starts[symbol] = args.start
                        print(f"  -> [{symbol}] Incremental mode: no existing facts found. Start date: {args.start or 'Full History'}")
            else:
                for symbol in target_list:
                    symbol_starts[symbol] = args.start
        except Exception as e:
            print(f"  -> [WARN] Failed to load existing facts for incremental check: {e}. Running from specified start date.")
            for symbol in target_list:
                symbol_starts[symbol] = args.start
    else:
        for symbol in target_list:
            symbol_starts[symbol] = args.start

    # Determine start date for VIX loading
    starts = [s for s in symbol_starts.values() if s is not None]
    vix_start = min(starts) if len(starts) == len(target_list) else args.start

    # Try loading VIX
    print("Loading VIX daily data...")
    try:
        vix_df = loader.load_vix(vix_start, args.end)
        if not vix_df.empty:
            vix_series = vix_df['close']
            print(f"  -> Loaded VIX data: {len(vix_series)} rows.")
        else:
            vix_series = None
            print("  -> VIX data is empty.")
    except Exception as e:
        vix_series = None
        print(f"  -> Failed to load VIX data: {e}. Proceeding without VIX.")
        
    facts_list = []
    level_touches_list = []
    from concurrent.futures import ProcessPoolExecutor
    
    if args.workers > 0:
        max_workers = args.workers
    else:
        max_workers = min(len(target_list), os.cpu_count() or 4, 3)

    results = []
    if max_workers <= 1:
        print("\nRunning symbol tasks sequentially in the main thread...")
        for symbol in target_list:
            try:
                facts, touches, plays = process_single_symbol(
                    symbol, symbol_starts[symbol], args.end, vix_series, force_regen, incremental_mode
                )
                results.append((symbol, facts, touches, plays))
            except Exception as exc:
                print(f"Symbol {symbol} generated an exception: {exc}")
    else:
        print(f"\nRunning symbol tasks in parallel with {max_workers} workers...")
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    process_single_symbol, symbol, symbol_starts[symbol], args.end, vix_series, force_regen, incremental_mode
                ): symbol
                for symbol in target_list
            }
            for future in futures:
                symbol = futures[future]
                try:
                    facts, touches, plays = future.result()
                    results.append((symbol, facts, touches, plays))
                except Exception as exc:
                    print(f"Symbol {symbol} generated an exception: {exc}")
                   # ── MATERIALIZE PARQUET FILES PER SYMBOL ─────────────────────────────────
    print(f"\nMaterializing Parquet files in {out_dir} per symbol...")
    import gc
    processed_count = 0
    
    # Sort keys for stable merge and comparison
    sort_keys = {
        "ib_facts": ["symbol", "trading_day", "session_slot", "time_basis"],
        "ib_ext_detail": ["symbol", "trading_day", "session_slot", "time_basis", "side", "level"],
        "ib_play_detail": ["symbol", "trading_day", "session_slot", "time_basis", "play", "target_lvl"],
        "ib_level_touch_detail": ["symbol", "trading_day", "session_slot", "time_basis", "level_pct", "phase"]
    }
    
    def save_symbol_table(new_df, base_name, symbol, keys, recompute_func=None):
        if new_df.empty:
            return None
            
        file_path = out_dir / f"{base_name}_{symbol}.parquet"
        new_df = new_df.drop_duplicates(subset=keys, keep="last")

        if incremental_mode and file_path.exists():
            try:
                existing_df = pd.read_parquet(file_path)
                combined = pd.concat([existing_df, new_df], ignore_index=True)
                combined = combined.drop_duplicates(subset=keys, keep="last")
                combined = combined.sort_values(by=keys).reset_index(drop=True)
                if recompute_func:
                    combined = recompute_func(combined)
                combined.to_parquet(file_path, index=False)
                return combined
            except Exception as e:
                print(f"  [WARN] Failed to incrementally update {file_path.name}: {e}. Overwriting with new data only.")
                new_df = new_df.sort_values(by=keys).reset_index(drop=True)
                if recompute_func:
                    new_df = recompute_func(new_df)
                new_df.to_parquet(file_path, index=False)
                return new_df
        else:
            new_df = new_df.sort_values(by=keys).reset_index(drop=True)
            if recompute_func:
                new_df = recompute_func(new_df)
            new_df.to_parquet(file_path, index=False)
            return new_df

    def recompute_historical_stats(df):
        if df.empty:
            return df
        # Sort values first to make sure rolling/expanding/shift are ordered correctly
        df = df.sort_values(by=["symbol", "session_slot", "time_basis", "trading_day"]).reset_index(drop=True)
        
        # Group by the session key
        grouped = df.groupby(["symbol", "session_slot", "time_basis"])
        
        dfs = []
        for keys, group in grouped:
            group = group.copy()
            
            # 1. Trailing quantiles for range
            group['range_pctile_20'] = group['range_pts'].rolling(20, min_periods=1).rank(pct=True) * 100
            group['range_pctile_60'] = group['range_pts'].rolling(60, min_periods=1).rank(pct=True) * 100
            
            # 2. Tercile buckets
            q1_3 = group['range_pct'].quantile(1/3)
            q2_3 = group['range_pct'].quantile(2/3)
            group['range_bucket_full'] = np.select(
                [group['range_pct'] <= q1_3, group['range_pct'] <= q2_3],
                ['Small', 'Medium'],
                default='Large'
            )
            
            q1_3_trailing = group['range_pct'].expanding(min_periods=20).quantile(1/3).shift(1)
            q2_3_trailing = group['range_pct'].expanding(min_periods=20).quantile(2/3).shift(1)
            first_q1 = q1_3_trailing.dropna().iloc[0] if not q1_3_trailing.dropna().empty else q1_3
            first_q2 = q2_3_trailing.dropna().iloc[0] if not q2_3_trailing.dropna().empty else q2_3
            group['range_bucket_trailing'] = np.select(
                [group['range_pct'] <= q1_3_trailing.fillna(first_q1), group['range_pct'] <= q2_3_trailing.fillna(first_q2)],
                ['Small', 'Medium'],
                default='Large'
            )
            
            # 3. VIX Buckets
            if 'vix_close' in group.columns:
                vix_non_nan = group['vix_close'].dropna()
                vix_q1 = vix_non_nan.quantile(1/3) if not vix_non_nan.empty else 15.0
                vix_q2 = vix_non_nan.quantile(2/3) if not vix_non_nan.empty else 20.0
                group['vix_bucket_full'] = np.select(
                    [group['vix_close'] <= vix_q1, group['vix_close'] <= vix_q2],
                    ['Low', 'Medium'],
                    default='High'
                )
                
                vix_q1_trailing = group['vix_close'].expanding(min_periods=20).quantile(1/3).shift(1)
                vix_q2_trailing = group['vix_close'].expanding(min_periods=20).quantile(2/3).shift(1)
                first_vix_q1 = vix_q1_trailing.dropna().iloc[0] if not vix_q1_trailing.dropna().empty else vix_q1
                first_vix_q2 = vix_q2_trailing.dropna().iloc[0] if not vix_q2_trailing.dropna().empty else vix_q2
                group['vix_bucket_trailing'] = np.select(
                    [group['vix_close'] <= vix_q1_trailing.fillna(first_vix_q1), group['vix_close'] <= vix_q2_trailing.fillna(first_vix_q2)],
                    ['Low', 'Medium'],
                    default='High'
                )
                
            # 4. Prior day Same-Slot result
            group['prior_day_result'] = np.sign(group['play1_result'].shift(1))
            
            dfs.append(group)
            
        return pd.concat(dfs, ignore_index=True).sort_values(by=["symbol", "trading_day", "session_slot", "time_basis"]).reset_index(drop=True)

    facts_list = []
    level_touches_list = []
    fvg_details_list = []
    play_details_list = []
    
    for symbol, facts, touches, plays in results:
        # Calculate bar index offset and adjust index columns in incremental mode
        if incremental_mode and symbol in symbol_last_dates and not facts.empty and 'existing_facts' in locals() and not existing_facts.empty:
            df_ext_sym = existing_facts[existing_facts["symbol"] == symbol]
            if not df_ext_sym.empty:
                common_days = set(df_ext_sym["trading_day"]).intersection(set(facts["trading_day"]))
                if common_days:
                    merged = pd.merge(
                        df_ext_sym[['trading_day', 'session_slot', 'time_basis', 'high_break_idx', 'low_break_idx']],
                        facts[['trading_day', 'session_slot', 'time_basis', 'high_break_idx', 'low_break_idx']],
                        on=['trading_day', 'session_slot', 'time_basis'],
                        suffixes=('_ext', '_new')
                    )
                    diffs = []
                    for col in ['high_break_idx', 'low_break_idx']:
                        diffs.extend(merged[col + '_ext'] - merged[col + '_new'])
                    valid_diffs = [d for d in diffs if d > 0]
                    if valid_diffs:
                        from collections import Counter
                        offset = Counter(valid_diffs).most_common(1)[0][0]
                        print(f"  -> [{symbol}] Bar index offset detected: {offset}. Adjusting index columns.")
                        for col in ['high_break_idx', 'low_break_idx', 'first_break_idx']:
                            if col in facts.columns:
                                facts[col] = facts[col] + offset
        
        # If in incremental mode, filter out rows on or before last_date for this symbol
        if incremental_mode and symbol in symbol_last_dates:
            last_date = symbol_last_dates[symbol]
            if not facts.empty: facts = facts[facts["trading_day"] > last_date]
            if not touches.empty: touches = touches[touches["trading_day"] > last_date]
            if not plays.empty: plays = plays[plays["trading_day"] > last_date]
        
        if facts.empty:
            continue
            
        print(f"  -> Reshaping and saving tables for {symbol}...")
        processed_count += 1
        
        # 1. ib_ext_detail (Vectorized)
        ext_dfs = []
        levels = [0.25, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]
        base_cols = ['symbol', 'trading_day', 'session_slot', 'time_basis']
        
        for lvl in levels:
            col_lvl = str(lvl).replace('.', '')
            # Up side
            col_hit_up = f'ext_up_{col_lvl}_hit'
            col_min_up = f'ext_up_{col_lvl}_minutes'
            df_up = facts[base_cols].copy()
            df_up['side'] = 'up'
            df_up['level'] = lvl
            df_up['hit'] = facts[col_hit_up].fillna(False).astype(bool) if col_hit_up in facts.columns else False
            df_up['minutes'] = facts[col_min_up].astype(float) if col_min_up in facts.columns else np.nan
            ext_dfs.append(df_up)
            
            # Down side
            col_hit_dn = f'ext_down_{col_lvl}_hit'
            col_min_dn = f'ext_down_{col_lvl}_minutes'
            df_dn = facts[base_cols].copy()
            df_dn['side'] = 'down'
            df_dn['level'] = lvl
            df_dn['hit'] = facts[col_hit_dn].fillna(False).astype(bool) if col_hit_dn in facts.columns else False
            df_dn['minutes'] = facts[col_min_dn].astype(float) if col_min_dn in facts.columns else np.nan
            ext_dfs.append(df_dn)
            
        symbol_ext = pd.concat(ext_dfs, ignore_index=True) if ext_dfs else pd.DataFrame(columns=base_cols + ['side', 'level', 'hit', 'minutes'])
        
        # 2. ib_play_detail
        symbol_play = plays
        
        # Clean temporary calculation columns from facts
        temp_cols = []
        for col in facts.columns:
            if ('ext_up_' in col) or ('ext_down_' in col) or ('either_side_' in col):
                temp_cols.append(col)
        facts = facts.drop(columns=temp_cols, errors='ignore')
        
        # Save individual tables
        final_facts = save_symbol_table(facts, "ib_facts", symbol, sort_keys["ib_facts"], recompute_func=recompute_historical_stats)
        if final_facts is not None: print(f"    - ib_facts_{symbol}:              {len(final_facts)} rows")
        
        final_ext = save_symbol_table(symbol_ext, "ib_ext_detail", symbol, sort_keys["ib_ext_detail"])
        if final_ext is not None: print(f"    - ib_ext_detail_{symbol}:         {len(final_ext)} rows")
        
        final_play = save_symbol_table(symbol_play, "ib_play_detail", symbol, sort_keys["ib_play_detail"])
        if final_play is not None: print(f"    - ib_play_detail_{symbol}:        {len(final_play)} rows")
        
        final_touches = save_symbol_table(touches, "ib_level_touch_detail", symbol, sort_keys["ib_level_touch_detail"])
        if final_touches is not None: print(f"    - ib_level_touch_detail_{symbol}: {len(final_touches)} rows")
        
        gc.collect()

    if processed_count == 0:
        print("\n[!] No records processed. Exiting.")
        return

    print("\nParquet Materialization Complete!")
    print(f"Total time elapsed: {time.time() - start_run:.2f} seconds.")

if __name__ == "__main__":
    main()
