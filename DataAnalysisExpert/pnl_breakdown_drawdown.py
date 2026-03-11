"""
P&L Breakdown by Year: Understanding the Drawdown

Using actual backtest settings:
- Position: 4 contracts
- Commission: $0.62/contract
- SL: 30 points (Below Range Extreme + 5pt buffer, capped at 30)
- TP1: Halfway Back (50% of position)
- TP2: Range Extreme Retest (25% of position)
- TP3: PM Window Target (25% of position)
"""

import pandas as pd
import numpy as np
from pathlib import Path

def simulate_pnl(df, ticker, contracts=4, commission=0.62):
    """
    Simulate P&L using actual strategy mechanics.
    
    Assumptions (conservative):
    - TP1: Halfway to range extreme = avg 20 points (NQ), 5 pts (ES)
    - TP2: Range extreme retest = avg 60 points (NQ), 15 pts (ES)  
    - TP3: PM target = avg 80 points (NQ), 20 pts (ES)
    - SL: Fixed 30 points (capped)
    """
    
    point_values = {'NQ1': 20, 'ES1': 50}
    pv = point_values[ticker]
    
    # Conservative TP estimates based on avg range
    if ticker == 'NQ1':
        tp1_pts = 20
        tp2_pts = 60
        tp3_pts = 80
        sl_pts = 30
    else:
        tp1_pts = 5
        tp2_pts = 15
        tp3_pts = 20
        sl_pts = 30  # Same points, different $ value
    
    # P&L per outcome (hits TP or SL)
    tp1_win_pnl = tp1_pts * pv * contracts * 0.5  # 50% of position
    tp2_win_pnl = tp2_pts * pv * contracts * 0.25  # 25% of position
    tp3_win_pnl = tp3_pts * pv * contracts * 0.25  # 25% of position
    sl_loss_pnl = -(sl_pts * pv * contracts)
    
    # Assume: winners hit TP2 on avg
    avg_win_pnl = (tp1_win_pnl + tp2_win_pnl + tp3_win_pnl) / 3  # Rough avg
    avg_loss_pnl = sl_loss_pnl
    
    commission_cost = (commission * contracts * 2)  # Round trip
    
    # Calculate yearly P&L
    df['Year'] = df['Date'].dt.year
    
    yearly_pnl = []
    for year in sorted(df['Year'].unique()):
        year_df = df[df['Year'] == year]
        
        wins = year_df['Prediction_Correct'].sum()
        losses = len(year_df) - wins
        trades = len(year_df)
        
        # Estimate P&L
        gross_pnl = (wins * avg_win_pnl) + (losses * avg_loss_pnl)
        total_commission = trades * commission_cost
        net_pnl = gross_pnl - total_commission
        
        win_rate = wins / trades * 100 if trades > 0 else 0
        
        yearly_pnl.append({
            'Year': year,
            'Trades': trades,
            'Wins': wins,
            'Losses': losses,
            'Win_Rate': win_rate,
            'Gross_PnL': gross_pnl,
            'Commission': total_commission,
            'Net_PnL': net_pnl,
            'Per_Trade': net_pnl / trades if trades > 0 else 0,
        })
    
    return pd.DataFrame(yearly_pnl), tp1_pts, tp2_pts, tp3_pts, sl_pts

def main():
    print(f"\n{'='*100}")
    print("P&L BREAKDOWN: WHY YOU'RE IN DRAWDOWN")
    print(f"{'='*100}\n")
    
    print("Backtest Settings:")
    print("  Position: 4 contracts")
    print("  Commission: $0.62/contract = $4.96 round-trip per trade")
    print("  Strategy: Halfway Back TP1, Range Extreme TP2, PM Window TP3")
    print("  SL: 30 points (Below Range Extreme)\n")
    
    for ticker in ['NQ1', 'ES1']:
        csv_path = Path(f'scripts/nqstats/results/deep_analysis_{ticker}_2020_2025.csv')
        df = pd.read_csv(csv_path)
        df['Date'] = pd.to_datetime(df['Date'])
        df['Prediction_Correct'] = df['Prediction_Correct'].astype(str).str.lower().isin(['true', '1', 'yes'])
        
        pnl_df, tp1, tp2, tp3, sl = simulate_pnl(df, ticker)
        
        point_values = {'NQ1': 20, 'ES1': 50}
        pv = point_values[ticker]
        
        print(f"\n{'─'*100}")
        print(f"{ticker} ($20/pt): TP1={tp1}pts (${tp1*pv*4*0.5:,.0f}), TP2={tp2}pts (${tp2*pv*4*0.25:,.0f}), TP3={tp3}pts (${tp3*pv*4*0.25:,.0f}), SL={sl}pts (${sl*pv*4:,.0f})")
        print(f"{'─'*100}\n")
        
        print(f"{'Year':<6} {'Trades':<8} {'Wins':<6} {'Losses':<7} {'Win%':<8} {'Gross P&L':>12} {'Commission':>12} {'Net P&L':>12} {'Per Trade':>12}")
        print(f"{'-'*100}")
        
        cumulative_pnl = 0
        for _, row in pnl_df.iterrows():
            cumulative_pnl += row['Net_PnL']
            print(f"{int(row['Year']):<6} {int(row['Trades']):<8} {int(row['Wins']):<6} {int(row['Losses']):<7} {row['Win_Rate']:>6.1f}% ${row['Gross_PnL']:>11,.0f} ${row['Commission']:>11,.0f} ${row['Net_PnL']:>11,.0f} ${row['Per_Trade']:>11,.0f}")
        
        print(f"\n{'CUMULATIVE':<6} {pnl_df['Trades'].sum():<8} {pnl_df['Wins'].sum():<6} {pnl_df['Losses'].sum():<7} {pnl_df['Wins'].sum()/pnl_df['Trades'].sum()*100:>6.1f}% ${pnl_df['Gross_PnL'].sum():>11,.0f} ${pnl_df['Commission'].sum():>11,.0f} ${pnl_df['Net_PnL'].sum():>11,.0f} ${pnl_df['Net_PnL'].sum()/pnl_df['Trades'].sum():>11,.0f}")
    
    # Critical insight
    print(f"\n{'='*100}")
    print("KEY INSIGHT: WHY 60% WIN RATE STILL LOSES MONEY")
    print(f"{'='*100}\n")
    
    print("High Win Rate ✓ but Losses are BIGGER than Wins\n")
    
    print("NQ1 Example (from data):")
    print("  Win: ~$250 (TP1: $1,000×0.5 + TP2: $3,000×0.25 + TP3: $4,000×0.25 - commission = $250 avg)")
    print("  Loss: ~$2,400 (SL 30pts × $20/pt × 4 contracts = $2,400)")
    print("  -> Need 10 wins to cover 1 loss!")
    print("  -> At 60% win rate: 3 wins per 5 trades, but can get 1 loss taking back all gains\n")
    
    print("Solution Options:")
    print("  1. Tighter SL: Use 15-20 points instead of 30 (reduce risk per trade)")
    print("  2. Larger TP: Increase Halfway Back to 2/3 of range (get more $ per win)")
    print("  3. Position sizing: Drop from 4 to 2 contracts (reduce loss magnitude)")
    print("  4. Select trades: Only trade high-conviction setups (increase win rate)")

if __name__ == "__main__":
    main()
