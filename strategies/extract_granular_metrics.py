import pandas as pd
import numpy as np
from pathlib import Path

def get_detailed_metrics(csv_path):
    try:
        df = pd.read_csv(csv_path)
    except:
        return None
        
    if len(df) == 0 or 'pnl_pct' not in df.columns:
        return None
    
    # Calculate risk_pct
    if 'initial_stop' in df.columns:
        # Preferred: Dynamic risk per trade
        df['risk_pct'] = abs(df['entry_price'] - df['initial_stop']) / df['entry_price'] * 100
    else:
        # Fallback to fixed if it's NQ mechanism eval (though we re-ran, so should be there)
        df['risk_pct'] = 0.253
        
    # Remove rows with zero risk to avoid division by zero
    df = df[df['risk_pct'] > 0]
    if len(df) == 0: return None
        
    # R_reach = MFE_pct / risk_pct
    df['mfe_r'] = df['mfe_pct'] / df['risk_pct']
    
    stats = {
        'trades': len(df),
        'win_rate': (df['result'] == 'WIN').mean() * 100,
        'profit_factor': df[df['result'] == 'WIN']['pnl_pct'].sum() / abs(df[df['result'] == 'LOSS']['pnl_pct'].sum()) if (df['result'] == 'LOSS').any() else np.inf,
        'avg_mae': df['mae_pct'].mean(),
        'avg_mfe': df['mfe_pct'].mean(),
        'reach_0.5r': (df['mfe_r'] >= 0.5).mean() * 100,
        'reach_1.0r': (df['mfe_r'] >= 1.0).mean() * 100,
        'reach_1.5r': (df['mfe_r'] >= 1.5).mean() * 100,
        'reach_2.0r': (df['mfe_r'] >= 2.0).mean() * 100,
    }
    return stats

results = []
folders = [
    Path('docs/strategies/initial_balance_break/mechanism_evaluation'),
    Path('docs/strategies/initial_balance_break/multi_asset_validation'),
]

for folder in folders:
    for csv_file in folder.glob('*.csv'):
        # Skip certain files
        if csv_file.name in ['comparison.csv', 'detailed_granular_results.csv', 'detailed_analysis.csv', 'VALIDATION_SUMMARY.csv']: 
            continue
            
        name = csv_file.stem
        metrics = get_detailed_metrics(csv_file)
        if metrics:
            metrics['config'] = f"{folder.name}/{name}"
            results.append(metrics)

if results:
    df_final = pd.DataFrame(results)
    cols = ['config', 'trades', 'win_rate', 'profit_factor', 'avg_mae', 'avg_mfe', 'reach_0.5r', 'reach_1.0r', 'reach_1.5r', 'reach_2.0r']
    df_final = df_final[cols]
    output_path = Path('docs/strategies/initial_balance_break/omnibus_granular_results.csv')
    df_final.to_csv(output_path, index=False)
    print(f"Omnibus granular results saved to {output_path}")
    print(df_final.to_string(index=False))
else:
    print("No results found. Are the backtests finished?")
