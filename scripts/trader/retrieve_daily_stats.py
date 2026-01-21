import pandas as pd
import sys
import os
import argparse

def load_data(ticker):
    base_dir = "c:/Users/vinay/tvDownloadOHLC/docs/DailyClassification"
    
    # 1. Overnight Matrix
    on_path = f"{base_dir}/{ticker}_overnight_probability_matrix.csv"
    if os.path.exists(on_path):
        df_on = pd.read_csv(on_path, index_col=0)
    else:
        df_on = None
        
    # 2. Sequence Matrix
    seq_path = f"{base_dir}/{ticker}_sequential_probabilities.csv"
    if os.path.exists(seq_path):
        df_seq = pd.read_csv(seq_path, index_col=0)
    else:
        df_seq = None
        
    return df_on, df_seq

def print_plan(ticker, df_on, df_seq, prev_day=None, overnight=None, streak=None):
    print(f"\n===== 📊 STATISTICAL TRADE PLAN: {ticker} =====\n")
    
    # --- 1. CONTEXT: PREVIOUS DAY ---
    if prev_day and df_seq is not None:
        if prev_day in df_seq.index:
            row = df_seq.loc[prev_day]
            print(f"🔹 Context: Yesterday was {prev_day}")
            print(f"   --> Probability for TODAY:")
            print(f"       R1:  {row.get('R1%', 0)}%")
            print(f"       R2:  {row.get('R2%', 0)}%")
            print(f"       DWP: {row.get('DWP%', 0)}%")
            print(f"       DNP: {row.get('DNP%', 0)}%")
            
            # Highlight
            best = row[['R1%', 'R2%', 'DWP%', 'DNP%']].idxmax().replace('%', '')
            print(f"   🎯 Edge: Leans towards **{best}**")
        else:
            print(f"⚠️  Context: Yesterday '{prev_day}' not found in sequence stats.")
    
    # --- 2. CONTEXT: OVERNIGHT ---
    if overnight and df_on is not None:
        # Search for key containing the overnight string (e.g. "Bullish | Bullish")
        # User input might be "Bullish" or simple.
        # Let's match partial if specific key provided, or generic "Bullish/Bearish" scenario logic if I had that map.
        # For now, let's assume user inputs exact key OR we list options.
        
        matches = [idx for idx in df_on.index if overnight.lower() in str(idx).lower()]
        
        if matches:
            print(f"\n🔹 Context: Overnight '{overnight}' matches {len(matches)} setups.")
            # If exact match or single match
            if len(matches) == 1:
                row = df_on.loc[matches[0]]
                print(f"   --> Setup: {matches[0]} (n={row['n']})")
                print(f"   --> Probability for TODAY:")
                print(f"       R1:  {row['R1%']}%")
                print(f"       R2:  {row['R2%']}%")
                print(f"       DWP: {row['DWP%']}%")
                print(f"       DNP: {row['DNP%']}%")
                
                most_likely = row['most_likely']
                print(f"   🎯 Edge: **{most_likely}**")
            else:
                print("   Multiple matches found. Be more specific (e.g. 'Bullish | Bullish'):")
                for m in matches[:5]:
                    print(f"   - {m}")
        else:
             print(f"\n⚠️  Context: Overnight '{overnight}' not found in matrix.")

    print("\n==============================================")
    print("🧠 TRADER REMINDER:")
    print("   - R1: Reversal Day (Fade edges)")
    print("   - R2: Expansion Day (Follow trend)")
    print("   - DWP: Deep Pullback Trend (Wait for pullback)")
    print("   - DNP: Clean Trend (Go with momentum)")
    print("==============================================\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Get Daily Probability Stats")
    parser.add_argument("ticker", help="Ticker symbol (e.g. NQ1)")
    parser.add_argument("--prev", help="Previous Day Type (R1, R2, DWP, DNP)", required=False)
    parser.add_argument("--overnight", help="Overnight Context (e.g. 'Bullish', 'Bearish', 'long true')", required=False)
    
    args = parser.parse_args()
    
    df_on, df_seq = load_data(args.ticker)
    
    if df_on is None and df_seq is None:
        print(f"Error: No data found for {args.ticker}. Run 'Market Analysis Suite' first.")
    else:
        print_plan(args.ticker, df_on, df_seq, prev_day=args.prev, overnight=args.overnight)
