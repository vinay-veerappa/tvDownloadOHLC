"""
Failure Diagnosis Engine - Deep analysis of Initial Balance failures
Correlates trade losses (false breakouts, whipsaws, stop-outs) with:
1. Normalized Volatility & ATR regimes
2. VIX levels (low/high volatility regimes)
3. Opening Gaps and prior close characteristics
4. Index divergence (NQ vs ES correlation)
"""

import pandas as pd
import numpy as np
from pathlib import Path
import sys

# Add project root to path
project_root = str(Path(__file__).parent.parent.parent.parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

def calculate_daily_atr(df_daily: pd.DataFrame, window: int = 14) -> pd.Series:
    """Computes daily Average True Range (ATR)."""
    prev_close = df_daily['close'].shift(1)
    tr1 = df_daily['high'] - df_daily['low']
    tr2 = (df_daily['high'] - prev_close).abs()
    tr3 = (df_daily['low'] - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(window).mean()

def run_failure_diagnosis(trades_csv: str = 'scripts/strategies/initial_balance/data/backtest_results_45min.csv'):
    """
    Diagnoses Initial Balance trade failures using multi-factor analysis.
    """
    path = Path(trades_csv)
    if not path.exists():
        print(f"[ERROR] Trades file not found at {path}. Please run backtests first.")
        return
        
    df_trades = pd.read_csv(path)
    if df_trades.empty or 'pnl_pct' not in df_trades.columns:
        print(f"[ERROR] Invalid or empty trades file: {path}")
        return
        
    print(f"\n{'='*100}")
    print(f"FAILURE DIAGNOSIS REPORT: {path.name}")
    print(f"{'='*100}\n")
    
    # Standardize trade dates
    df_trades['date'] = pd.to_datetime(df_trades['exit_time'], utc=True).dt.date
    df_trades = df_trades.set_index('date')
    
    # 1. Load market context data
    print("[INFO] Loading VIX and index parquets for correlation...")
    try:
        vix_daily = pd.read_parquet("data/VIX_1d.parquet")
        vix_daily.index = pd.to_datetime(vix_daily.index).date
        vix_daily = vix_daily[~vix_daily.index.duplicated()]
        df_trades['vix'] = df_trades.index.map(vix_daily['close'])
    except Exception as e:
        print(f"[WARNING] Could not load VIX data: {e}")
        df_trades['vix'] = np.nan
        
    try:
        nq_daily = pd.read_parquet("data/NQ1_1d.parquet")
        nq_daily.index = pd.to_datetime(nq_daily.index).date
        nq_daily = nq_daily[~nq_daily.index.duplicated()]
        df_trades['atr_14d'] = df_trades.index.map(calculate_daily_atr(nq_daily, 14))
    except Exception as e:
        print(f"[WARNING] Could not load NQ ATR data: {e}")
        df_trades['atr_14d'] = np.nan
        
    try:
        es_daily = pd.read_parquet("data/ES1_1d.parquet")
        es_daily.index = pd.to_datetime(es_daily.index).date
        es_daily = es_daily[~es_daily.index.duplicated()]
        
        # Inter-market green/red close alignment (divergence check)
        nq_daily['is_green'] = nq_daily['close'] > nq_daily['open']
        es_daily['is_green'] = es_daily['close'] > es_daily['open']
        
        diverged_dates = nq_daily.index[nq_daily['is_green'] != es_daily['is_green']]
        df_trades['diverged'] = df_trades.index.isin(diverged_dates)
    except Exception as e:
        print(f"[WARNING] Could not compute ES/NQ divergence: {e}")
        df_trades['diverged'] = False

    # 2. Compute customized metrics
    df_trades['result'] = np.where(df_trades['pnl_pct'] > 0, 'WIN', 'LOSS')
    df_trades['is_failure'] = df_trades['result'] == 'LOSS'
    
    # 3. Volatility / ATR Diagnosis
    print("--- 1. Volatility & ATR Regimes ---")
    if df_trades['vix'].notna().any():
        df_trades['vix_regime'] = pd.qcut(df_trades['vix'], q=3, labels=['LOW_VIX', 'MED_VIX', 'HIGH_VIX'])
        for regime in ['LOW_VIX', 'MED_VIX', 'HIGH_VIX']:
            subset = df_trades[df_trades['vix_regime'] == regime]
            if len(subset) > 0:
                wr = (subset['result']=='WIN').sum() / len(subset) * 100
                print(f"  {regime:<8}: {len(subset)} trades | Win Rate: {wr:.1f}%")
    else:
        print("  VIX data unavailable.")
        
    if df_trades['atr_14d'].notna().any():
        df_trades['atr_regime'] = pd.qcut(df_trades['atr_14d'], q=3, labels=['LOW_ATR', 'MED_ATR', 'HIGH_ATR'])
        for regime in ['LOW_ATR', 'MED_ATR', 'HIGH_ATR']:
            subset = df_trades[df_trades['atr_regime'] == regime]
            if len(subset) > 0:
                wr = (subset['result']=='WIN').sum() / len(subset) * 100
                print(f"  {regime:<8}: {len(subset)} trades | Win Rate: {wr:.1f}%")
    else:
        print("  ATR data unavailable.")
    print("")

    # 4. Opening Gap Diagnosis
    print("--- 2. Normalized IB Range & Gap Sizes ---")
    df_trades['ib_range_regime'] = pd.qcut(df_trades['ib_range_pct'], q=3, labels=['Tight Range', 'Medium Range', 'Wide Range'])
    for regime in ['Tight Range', 'Medium Range', 'Wide Range']:
        subset = df_trades[df_trades['ib_range_regime'] == regime]
        if len(subset) > 0:
            wr = (subset['result']=='WIN').sum() / len(subset) * 100
            print(f"  {regime:<12}: {len(subset)} trades | Win Rate: {wr:.1f}%")
    print("")

    # 5. Index Divergence Diagnosis
    print("--- 3. Inter-Market Divergence (NQ vs ES) ---")
    for status in [False, True]:
        subset = df_trades[df_trades['diverged'] == status]
        if len(subset) > 0:
            wr = (subset['result']=='WIN').sum() / len(subset) * 100
            lbl = "Diverged Close (Uncorrelated)" if status else "Aligned Close (Correlated)"
            print(f"  {lbl:<30}: {len(subset)} trades | Win Rate: {wr:.1f}%")
    print("")

    # 6. Expectation / Bias Match Diagnosis
    print("--- 4. Confluence / Bias Direction Accuracy ---")
    if 'matched_expectation' not in df_trades.columns and 'expected_break' in df_trades.columns and 'direction' in df_trades.columns:
        df_trades['matched_expectation'] = np.where(
            df_trades['expected_break'].isna(), np.nan,
            np.where(
                ((df_trades['direction'] == 'long') & (df_trades['expected_break'] == 'BULLISH')) |
                ((df_trades['direction'] == 'short') & (df_trades['expected_break'] == 'BEARISH')),
                True, False
            )
        )
        
    if 'matched_expectation' in df_trades.columns:
        for status in [True, False]:
            subset = df_trades[df_trades['matched_expectation'] == status]
            if len(subset) > 0:
                wr = (subset['result']=='WIN').sum() / len(subset) * 100
                lbl = "Matched Expectation" if status else "Against Expectation"
                print(f"  {lbl:<30}: {len(subset)} trades | Win Rate: {wr:.1f}%")
    else:
        # Compatibility fallback checking if expected_break matched breakout direction
        print("  Expectation columns not generated in this file.")
    print("\n" + "="*100)

if __name__ == '__main__':
    run_failure_diagnosis()
