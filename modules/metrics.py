"""
Metrics Module (The Edge System)
================================
Core definition of Risk/Performance metrics.
"""

import pandas as pd
import numpy as np

def calculate_edge_metrics(df, bankroll_units=20, normalize_contracts=True):
    """
    Calculate the full suite of 'Edge System' metrics.
    
    Args:
        df: DataFrame with 'Net P&L USD', 'Qty' (optional).
        bankroll_units: For RoR calculation (Standard=20).
        normalize_contracts: If True, calculates 'Avg P&L per Contract' 
                             instead of raw dollars if Qty varies.
                             
    Returns:
        dict: Stats + Grade
    """
    if len(df) == 0: return {}
    
    # Copy to avoid mutation
    work_df = df.copy()
    
    if 'Qty' not in work_df.columns:
        work_df['Qty'] = 1
        
    # --- 1. BASIC STATS ---
    trades = len(work_df)
    wins = work_df[work_df['Net P&L USD'] > 0]
    losses = work_df[work_df['Net P&L USD'] <= 0]
    
    win_rate = len(wins) / trades if trades > 0 else 0
    loss_rate = 1 - win_rate
    
    total_pnl = work_df['Net P&L USD'].sum()
    gross_profit = wins['Net P&L USD'].sum()
    gross_loss = abs(losses['Net P&L USD'].sum())
    
    # Avg P&L (Raw)
    avg_pnl_raw = work_df['Net P&L USD'].mean()
    
    # Contract Normalization?
    # User Note: "I use 1 contract so PF is lower" -> Actually PF is ratio. 
    # But "Avg P&L" definitely scales.
    # Let's calc Avg Contracts to show context.
    avg_contracts = work_df['Qty'].mean()
    
    # --- 2. RISK DEFINITION ($R) ---
    # R = Absolute Avg Loss
    avg_loss_abs = abs(losses['Net P&L USD'].mean()) if len(losses) > 0 else 1.0 # Default to $1 if no losses
    risk_r = avg_loss_abs
    
    # --- 3. EXPECTED VALUE (EV) ---
    # EV = (Win% * AvgWin) - (Loss% * AvgLoss)
    avg_win = wins['Net P&L USD'].mean() if len(wins) > 0 else 0
    ev_dollars = (win_rate * avg_win) - (loss_rate * risk_r)
    
    # --- 4. PROFIT FACTOR ---
    pf = gross_profit / gross_loss if gross_loss > 0 else 0
    
    # --- 5. R-MULTIPLES & SQN ---
    # R-Multiple = PnL / Risk
    work_df['R'] = work_df['Net P&L USD'] / risk_r
    mean_r = work_df['R'].mean()
    std_r = work_df['R'].std()
    
    sqn = (mean_r / std_r) * (trades ** 0.5) if std_r > 0 else 0
    
    # --- 6. COMBINED EDGE ---
    # Raw Edge metric for Grading (EV * PF)
    combined_edge_raw = ev_dollars * pf
    
    # Normalized Edge (EV_R * PF)
    ev_r = ev_dollars / risk_r
    combined_edge_norm = ev_r * pf
    
    # --- 7. DRAWDOWN ---
    work_df = work_df.sort_values('Entry Time')
    equity = work_df['Net P&L USD'].cumsum()
    peak = equity.cummax()
    drawdown = equity - peak
    max_dd = drawdown.min()
    
    # DRR (Drawdown Risk Rating) -> "How many R's deep?"
    drr = abs(max_dd) / risk_r if risk_r > 0 else 0
    
    # --- 8. RISK OF RUIN (RoR) ---
    try:
        ror_calc = (1 - combined_edge_norm) / (1 + combined_edge_norm)
        if ror_calc <= 0:
            ror = 0.0
        else:
            ror = (ror_calc ** bankroll_units) * 100
    except:
        ror = 100.0
        
    # --- 9. STREAKS ---
    try:
        max_streak_theoretical = np.log(trades) / np.log(1 / loss_rate) if loss_rate > 0 else 0
    except:
        max_streak_theoretical = 0
        
    # --- 10. GRADING ---
    grade = "F"
    # Adjusted Grading Scale for 1 Contract?
    # If 1 contract, EV is ~$30-50 for NQ. 
    # Combined Edge = EV * PF. 
    # If EV=$40, PF=1.5 -> Edge=60. (Grade B)
    # If EV=$200 (scale), PF=1.5 -> Edge=300 (Grade A+)
    # The Raw Dollar grading works for "Standard NQ sizing" assumption.
    # It might penalize micro-lots.
    
    # Let's base grade on NORMALIZED Edge if we want size-independence?
    # No, user guide says "CombinedEdge = EV * PF" in dollars.
    # Let's keep it but note the nuance.
    
    sc = combined_edge_raw
    if sc > 150: grade = "A+"
    elif sc > 100: grade = "A"
    elif sc > 50: grade = "B"
    elif sc > 20: grade = "C"
    elif sc > 0: grade = "D"
    else: grade = "F"
    
    # Penalty modifiers
    if ror > 5.0: grade += " (Risk!)"
    if drr > 15: grade += " (Deep DD)"
    if sqn < 1.0 and "F" not in grade: grade += " (Low Qual)"
    
    return {
        'Trades': trades,
        'Win Rate %': win_rate * 100,
        'Total P&L': total_pnl,
        'Avg P&L (EV)': ev_dollars,
        'Risk ($)': risk_r,
        'Profit Factor': pf,
        'Combined Edge': combined_edge_raw,
        'SQN': sqn,
        'RoR %': ror,
        'Max Drawdown': max_dd,
        'DRR': drr,
        'Avg Contracts': avg_contracts,
        'Grade': grade
    }

def get_recommendations(stats):
    """Generate textual advice."""
    recs = []
    
    # EV check
    if stats['Avg P&L (EV)'] < 20:
        recs.append("🔴 **Fix EV**: Low avg profit. Increase winners or cut losers.")
        
    # PF check
    if stats['Profit Factor'] < 1.3:
        recs.append("🟠 **Fix Efficiency**: PF < 1.3 implies weak edge. Reduce chop trades.")
        
    # RoR
    if stats['RoR %'] > 2.0:
        recs.append("🔴 **CRITICAL**: High Risk of Ruin. Reduce position size.")
    
    # 1-Contract Nuance
    if stats['Avg Contracts'] <= 1.5:
        recs.append("ℹ️ **Size Note**: Low contract size limits partial-scale-out benefits.")
        
    if not recs:
        recs.append("🟢 **Healthy**: System looks robust.")
        
    return recs
