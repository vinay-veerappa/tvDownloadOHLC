
import pandas as pd
import numpy as np

def analyze_insights():
    print("Analyzing 9:30 Backtest Data for Optimization Insights...")
    
    csv_path = "reports/930_backtest_all_trades.csv"
    try:
        df = pd.read_csv(csv_path)
    except FileNotFoundError:
        print("CSV not found. Please run compare_930_variants.py first.")
        return

    # Filter for the relevant strategies to analyze (Original seems best baseline, or OptB for FVG)
    # Let's analyze "Original" and "OptB_Market" separately if possible, or aggregate trend?
    # User asked how to improve "this", implying the FVG work we just did. 
    # But Original is the baseline. Let's look at ALL trades to find general NQ behavior insights.
    
    # 1. ENTRY TIMING ANALYSIS
    print("\n--- 1. ENTRY TIMING (Seconds from Open) ---")
    bins = [0, 60, 180, 300, 9999]
    labels = ['< 1 min', '1-3 mins', '3-5 mins', '> 5 mins']
    df['Delay_Bucket'] = pd.cut(df['Entry_Delay_Sec'], bins=bins, labels=labels)
    
    timing = df.groupby('Delay_Bucket', observed=True).agg({
        'Result': lambda x: (x == 'WIN').mean() * 100,
        'PnL_Pct': 'mean',
        'MAE_Pct': 'mean',
        'Variant': 'count' # Trade Count
    }).rename(columns={'Variant': 'Count'})
    print(timing.to_string())
    
    # 2. RANGE SIZE ANALYSIS
    print("\n--- 2. RANGE SIZE (Tight vs Wide) ---")
    # Quartiles
    q33 = df['Range_Pct'].quantile(0.33)
    q66 = df['Range_Pct'].quantile(0.66)
    
    def get_size_bucket(x):
        if x < q33: return 'Tight (< {:.2f}%)'.format(q33)
        elif x > q66: return 'Wide (> {:.2f}%)'.format(q66)
        else: return 'Normal'
        
    df['Size_Bucket'] = df['Range_Pct'].apply(get_size_bucket)
    
    sizing = df.groupby('Size_Bucket').agg({
        'Result': lambda x: (x == 'WIN').mean() * 100,
        'PnL_Pct': 'mean',
        'Variant': 'count'
    }).rename(columns={'Variant': 'Count'})
    print(sizing.to_string())

    # 3. MAE ANALYSIS (Cutting Losses)
    print("\n--- 3. MAE ANALYSIS (Optimal Stop Loss?) ---")
    # Logic: If we tightened stop to X%, how many WINNERS would trigger it (False Positive)?
    # And how much PnL would we save on LOSERS?
    
    winners = df[df['Result'] == 'WIN']
    losers = df[df['Result'] == 'LOSS']
    
    print(f"Total Winners: {len(winners)}")
    print(f"Total Losers: {len(losers)}")
    
    # Test MAE thresholds
    thresholds = [0.05, 0.10, 0.15, 0.20, 0.25]
    
    full_pnl = df['PnL_Pct'].sum()
    print(f"Baseline Total PnL: {full_pnl:.3f}%")
    
    print(f"\n{'Threshold':<10} | {'Wins Killed':<12} | {'Loss Saved':<12} | {'New Net PnL':<12}")
    
    for thresh in thresholds:
        # How many winners violated this thresh?
        wins_killed = winners[winners['MAE_Pct'] > thresh]
        killed_count = len(wins_killed)
        
        # PnL lost from killing winners (Assume they become -thresh loss)
        # Actually, they become -thresh.
        pnl_lost_from_wins = wins_killed['PnL_Pct'].sum() - (killed_count * -thresh)
        # Wait, current PnL is Sum(Wins). New PnL is Sum(Wins kept) + (Killed * -thresh).
        # Difference is simpler: subtract deviation.
        
        # Losers Saved:
        # Losers that exceeded thresh would now be capped at -thresh.
        # Check losers where MAE > thresh (meaning we could have stopped earlier)
        # Note: Some losers might be small (MAE < thresh), so they stay same.
        relevant_losers = losers[losers['MAE_Pct'] > thresh]
        saved_pnl = relevant_losers['PnL_Pct'].sum() # Negative Number (e.g. -100)
        new_loss_pnl = len(relevant_losers) * -thresh # (e.g. -50)
        pnl_gain_from_losers = new_loss_pnl - saved_pnl # (-50) - (-100) = +50 gain
        
        # Calculate Exact New Total PnL
        # 1. Winners kept (MAE <= thresh)
        w_kept = winners[winners['MAE_Pct'] <= thresh]['PnL_Pct'].sum()
        # 2. Winners killed (MAE > thresh -> Stopped out at -thresh)
        w_killed = len(wins_killed) * -thresh
        
        # 3. Losers kept (MAE <= thresh -> Full loss taken? Or is MAE limit implied?)
        # If loser MAE <= thresh, it means it never hit stop. It closed at EOD or Time.
        l_kept = losers[losers['MAE_Pct'] <= thresh]['PnL_Pct'].sum()
        # 4. Losers cut (MAE > thresh -> Stopped at -thresh)
        l_cut = len(relevant_losers) * -thresh
        
        new_total = w_kept + w_killed + l_kept + l_cut
        
        print(f"{thresh:.2f}%     | {killed_count:<12} | {len(relevant_losers):<12} | {new_total:.3f}%")

if __name__ == "__main__":
    analyze_insights()
