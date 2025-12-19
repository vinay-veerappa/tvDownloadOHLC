import pandas as pd

CSV_PATH = 'data/options/options/doltdump/option_chain.csv'
TARGETS = ['SPY', 'AAPL']

def audit_dates():
    print(f"Auditing date ranges in {CSV_PATH} for {TARGETS}...")
    stats = {}
    
    try:
        reader = pd.read_csv(CSV_PATH, usecols=['date', 'act_symbol'], chunksize=1000000)
        for i, chunk in enumerate(reader):
            for sym in TARGETS:
                s_df = chunk[chunk['act_symbol'] == sym]
                if not s_df.empty:
                    if sym not in stats:
                        stats[sym] = {'min': s_df['date'].min(), 'max': s_df['date'].max(), 'count': len(s_df)}
                    else:
                        stats[sym]['min'] = min(stats[sym]['min'], s_df['date'].min())
                        stats[sym]['max'] = max(stats[sym]['max'], s_df['date'].max())
                        stats[sym]['count'] += len(s_df)
            
            if i % 5 == 0:
                print(f"Processed {i+1}M rows...")
                for sym, data in stats.items():
                    print(f"  {sym}: {data['min']} to {data['max']} (Count: {data['count']})")
                    
        print("\n=== Final Audit Results ===")
        for sym, data in stats.items():
            print(f"{sym}: {data['min']} to {data['max']} (Rows: {data['count']})")
            
    except Exception as e:
        print(f"Audit failed: {e}")

if __name__ == "__main__":
    audit_dates()
