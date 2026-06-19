import pandas as pd
from pathlib import Path
import sys

# Fix console encoding
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

def audit_gaps():
    print('================================================')
    print('             FULL DATA GAP AUDIT                ')
    print('================================================')
    
    files_to_check = []
    # Live storage
    files_to_check.extend(Path('data/live').glob('live_storage_*.parquet'))
    # Daily
    files_to_check.extend(Path('data').glob('*_1d.parquet'))
    # Weekly
    files_to_check.extend(Path('data').glob('*_1W.parquet'))
    
    for f in sorted(files_to_check):
        print(f'\nChecking {f}...')
        try:
            df = pd.read_parquet(f)
            if len(df) == 0:
                print('  ❌ Empty file.')
                continue
                
            if 'live_storage' in f.name:
                if 'time' in df.columns:
                    df = df.set_index(pd.to_datetime(df['time'], unit='ms'))
                else:
                    print('  ❌ live_storage file missing time column')
                    continue
            
            if '1W' in f.name:
                max_gap = 14 * 24 # 14 days (2 weeks gap is missing data)
            elif '1d' in f.name:
                max_gap = 4.5 * 24 # 4.5 days (4-day weekend max)
            else:
                max_gap = 3.5 * 24 # 3.5 days (weekend + 1 holiday)
                
            df = df.sort_index()
            diffs = df.index.to_series().diff().dt.total_seconds() / 3600.0
            gaps = diffs[diffs > max_gap]
            
            if len(gaps) > 0:
                print(f'  ⚠️ Found {len(gaps)} gaps > {max_gap} hours:')
                for end_time, delta in gaps.items():
                    start_time = end_time - pd.Timedelta(hours=delta)
                    print(f'      Gap: {start_time} -> {end_time} ({delta:.1f} hours)')
            else:
                print('  ✅ No significant gaps found.')
                
        except Exception as e:
            print(f'  ❌ Error: {e}')

if __name__ == '__main__':
    audit_gaps()
