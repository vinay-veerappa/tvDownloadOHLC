import pandas as pd

CSV_PATH = 'data/options/options/doltdump/option_chain.csv'
TARGETS = ['SPX', 'QQQ', 'SPY', 'NDX', 'VIX']

def audit_chain():
    print(f"Auditing {CSV_PATH} for {TARGETS}...")
    found = set()
    try:
        reader = pd.read_csv(CSV_PATH, usecols=['act_symbol'], chunksize=1000000)
        for i, chunk in enumerate(reader):
            symbols = chunk['act_symbol'].unique()
            matches = set(symbols).intersection(TARGETS)
            if matches:
                new_matches = matches - found
                if new_matches:
                    print(f"Chunk {i}: Found {new_matches}")
                    found.update(matches)
            
            if len(found) == len(TARGETS):
                break
                
        print(f"\nFinal Found Symbols: {found}")
        missing = set(TARGETS) - found
        if missing:
            print(f"Missing Symbols: {missing}")
            
    except Exception as e:
        print(f"Audit failed: {e}")

if __name__ == "__main__":
    audit_chain()
