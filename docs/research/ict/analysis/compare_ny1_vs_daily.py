import json
import pandas as pd
import numpy as np
import os
import sys

def compare_ny1_vs_daily():
    profiler_path = r"c:\Users\vinay\tvDownloadOHLC\data\NQ1_profiler.json"
    
    if not os.path.exists(profiler_path):
        print("Profiler JSON not found.")
        return

    print("1. Loading Profiler Data...")
    with open(profiler_path, 'r') as f:
        p_data = json.load(f)
    
    df_p = pd.DataFrame(p_data)
    df_p['date_str'] = pd.to_datetime(df_p['date']).dt.strftime('%Y-%m-%d')
    
    # 2. Derive DAILY outcome
    # We need Open of the Day (Asia Open usually) and Close of the Day (NY PM Close)
    # Or we can just use the sum of ranges, but direction matters.
    # The JSON has 'open' and 'close' (implied by range/close_pct) but let's be precise.
    # Actually, we can infer Daily Trend from the Net Move of sessions. 
    # Better: Use 'prior_close' of next session? No.
    # We have 'close_pct' relative to range.
    # Let's use the 'close_pct' of the LAST session (NY PM) to see where we ended relative to the day's range?
    # No, that's just session range.
    
    # Let's aggregate: Day Open = Asia Open. Day Close = NY PM Close (if avail) or NY AM Close.
    # We need to group by date.
    
    daily_records = {}
    
    for _, row in df_p.iterrows():
        d = row['date_str']
        s = row['session']
        if d not in daily_records: daily_records[d] = {}
        
        # Store Session Status
        prefix = ""
        if s == "Asia": 
            prefix = "Asia"
            daily_records[d]['Day_Open'] = row['open'] # Asia Open is Day Open (approx 18:00)
        elif s == "London": prefix = "London"
        elif s == "NY1": prefix = "NY1"
        elif s == "NY2": 
            prefix = "NY2"
            daily_records[d]['Day_Close'] = row['open'] # This is session open. We need session close.
            # Close = Low + (Range * ClosePct)? 
            # actually row['open'] is session open.
            # Let's estimate close: 
            # RangeLow + (RangeHigh-RangeLow)*ClosePct
            rng = row['range_high'] - row['range_low']
            cls = row['range_low'] + (rng * row['close_pct'])
            daily_records[d]['Day_Close'] = cls
            
        if prefix:
            daily_records[d][f"{prefix}_Status"] = row['status']

    df = pd.DataFrame.from_dict(daily_records, orient='index')
    df = df.dropna(subset=['Asia_Status', 'London_Status', 'NY1_Status', 'Day_Open', 'Day_Close'])
    
    # 3. Define Outcomes
    
    # NY1 Outcome (Trend vs Reversal vs Neutral relative to London)
    # Re-use logic from previous report
    def get_dir(status):
        if status in ['Long True', 'Short False']: return "UP"
        if status in ['Short True', 'Long False']: return "DOWN"
        return "NEUTRAL"
        
    df['Asia_Dir'] = df['Asia_Status'].apply(get_dir)
    df['Lon_Dir'] = df['London_Status'].apply(get_dir)
    df['NY1_Dir'] = df['NY1_Status'].apply(get_dir)
    
    # Daily Outcome
    df['Day_Dir'] = np.where(df['Day_Close'] > df['Day_Open'], "UP", "DOWN")
    
    # 4. Compare Models
    
    def evaluate_model(name, filter_condition, expected_ny1, expected_day, desc):
        subset = df[filter_condition].copy()
        if len(subset) == 0: return
        
        print(f"\n--- {name}: {desc} (n={len(subset)}) ---")
        
        # NY1 Success Rate
        ny1_hits = subset[subset['NY1_Dir'] == expected_ny1]
        ny1_rate = len(ny1_hits) / len(subset) * 100
        
        # Daily Success Rate
        # "Success" means Daily Direction matched the prediction
        # If model predicts London Reversal (e.g. Lon=UP -> Exp Rev=Down), does Day close Down?
        day_hits = subset[subset['Day_Dir'] == expected_day]
        day_rate = len(day_hits) / len(subset) * 100
        
        print(f"  NY1 Accuracy:   {ny1_rate:.1f}%")
        print(f"  Daily Accuracy: {day_rate:.1f}%")
        
        if ny1_rate > day_rate + 2:
            print("  >> CRITICAL: Model is BETTER for NY1 (Intraday Edge)")
        elif day_rate > ny1_rate + 2:
            print("  >> CRITICAL: Model is BETTER for DAILY (Swing Edge)")
        else:
            print("  >> Model performs similarly for both.")

    # Tree A: Expansion Reversal (Opposing Trends)
    # Asia UP / Lon DOWN -> Pred UP
    # Asia DOWN / Lon UP -> Pred DOWN
    
    # Case A1: Asia UP -> Lon DOWN (Expect UP)
    cond_a1 = (df['Asia_Dir'] == "UP") & (df['Lon_Dir'] == "DOWN")
    evaluate_model("Tree A (Bullish Reversal)", cond_a1, "UP", "UP", "Asia UP -> Lon DOWN")
    
    # Case A2: Asia DOWN -> Lon UP (Expect DOWN)
    cond_a2 = (df['Asia_Dir'] == "DOWN") & (df['Lon_Dir'] == "UP")
    evaluate_model("Tree A (Bearish Reversal)", cond_a2, "DOWN", "DOWN", "Asia DOWN -> Lon UP")
    
    # Tree B: Double Failure (Same Direction Failure) -> Reversal of Failure (Trend)
    # Asia LF (Fail Bull) / Lon LF (Fail Bull) -> Pred DOWN
    # Asia SF (Fail Bear) / Lon SF (Fail Bear) -> Pred UP
    
    cond_b1 = (df['Asia_Status'] == "Long False") & (df['London_Status'] == "Long False")
    evaluate_model("Tree B (Double Bul Trapped)", cond_b1, "DOWN", "DOWN", "Asia LF -> Lon LF")
    
    cond_b2 = (df['Asia_Status'] == "Short False") & (df['London_Status'] == "Short False")
    evaluate_model("Tree B (Double Bear Trapped)", cond_b2, "UP", "UP", "Asia SF -> Lon SF")

    # Tree C: Inside Trap
    # Asia Inside / Lon Breakout -> Pred FADE (Reversal of London)
    
    cond_c1 = (df['Asia_Status'].isin(['None','Inside'])) & (df['London_Status'] == "Short True")
    evaluate_model("Tree C (Bear Trap)", cond_c1, "UP", "UP", "Asia Inside -> Lon Short True")
    
    cond_c2 = (df['Asia_Status'].isin(['None','Inside'])) & (df['London_Status'] == "Long True")
    evaluate_model("Tree C (Bull Trap)", cond_c2, "DOWN", "DOWN", "Asia Inside -> Lon Long True")

if __name__ == "__main__":
    compare_ny1_vs_daily()
