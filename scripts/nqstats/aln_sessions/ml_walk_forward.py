"""
Multi-Period Out-of-Sample Validation
=======================================
Tests the binary classifier on multiple out-of-sample periods.

Walk-Forward Approach:
- Train on all data before test period
- Test on each year separately: 2020, 2021, 2022, 2023, 2024

This gives a more robust view of model stability across market regimes.
"""

import json
import pandas as pd
import numpy as np
from collections import defaultdict
from pathlib import Path
from datetime import datetime
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score

# --- CONFIG ---
DATA_DIR = Path(__file__).parent.parent.parent.parent / "data"
TICKERS = ['NQ1', 'ES1', 'YM1', 'RTY1']

# Test periods (each year is a separate out-of-sample test)
TEST_PERIODS = [
    {'name': '2020', 'start': '2020-01-01', 'end': '2021-01-01'},
    {'name': '2021', 'start': '2021-01-01', 'end': '2022-01-01'},
    {'name': '2022', 'start': '2022-01-01', 'end': '2023-01-01'},
    {'name': '2023', 'start': '2023-01-01', 'end': '2024-01-01'},
    {'name': '2024-25', 'start': '2024-01-01', 'end': '2026-01-01'},
]


def load_profiler_data(ticker: str):
    """Load profiler and HOD/LOD data."""
    profiler_file = DATA_DIR / f"{ticker}_profiler.json"
    hod_lod_file = DATA_DIR / f"{ticker}_daily_hod_lod.json"
    
    with open(profiler_file) as f:
        profiler_data = json.load(f)
    
    hod_lod_data = {}
    if hod_lod_file.exists():
        with open(hod_lod_file) as f:
            hod_lod_data = json.load(f)
    
    daily = defaultdict(dict)
    for record in profiler_data:
        date = record['date']
        session = record['session']
        daily[date][session] = record
    
    for date, hod_lod in hod_lod_data.items():
        if date in daily:
            daily[date]['hod_lod'] = hod_lod
    
    return daily


def classify_aln(asia: dict, london: dict) -> str:
    if not asia or not london:
        return 'Unknown'
    
    asia_h, asia_l = asia.get('range_high'), asia.get('range_low')
    london_h, london_l = london.get('range_high'), london.get('range_low')
    
    if None in (asia_h, asia_l, london_h, london_l):
        return 'Unknown'
    
    if london_h > asia_h and london_l < asia_l:
        return 'LEA'
    if london_h > asia_h and london_l >= asia_l:
        return 'LPEU'
    if london_l < asia_l and london_h <= asia_h:
        return 'LPED'
    return 'AEL'


def create_features(daily: dict) -> pd.DataFrame:
    """Create feature matrix."""
    rows = []
    dates = sorted(daily.keys())
    
    for i, date in enumerate(dates):
        sessions = daily[date]
        asia = sessions.get('Asia')
        london = sessions.get('London')
        ny1 = sessions.get('NY1')
        hod_lod = sessions.get('hod_lod')
        
        if not all([asia, london, ny1]):
            continue
        
        prev_date = dates[i-1] if i > 0 else None
        prev_sessions = daily.get(prev_date, {}) if prev_date else {}
        prev_ny2 = prev_sessions.get('NY2', {})
        prev_hod_lod = prev_sessions.get('hod_lod', {})
        
        row = {'date': date}
        row['aln'] = classify_aln(asia, london)
        row['asia_broken'] = 1 if asia.get('broken', False) else 0
        row['london_broken'] = 1 if london.get('broken', False) else 0
        
        asia_status = asia.get('status', 'None')
        london_status = london.get('status', 'None')
        row['asia_long'] = 1 if 'Long' in asia_status else 0
        row['asia_short'] = 1 if 'Short' in asia_status else 0
        row['london_long'] = 1 if 'Long' in london_status else 0
        row['london_short'] = 1 if 'Short' in london_status else 0
        
        if prev_ny2 and london:
            prev_close = prev_ny2.get('range_low', prev_ny2.get('range_high', None))
            london_open = london.get('open')
            row['gap_pts'] = (london_open - prev_close) if prev_close and london_open else 0
        else:
            row['gap_pts'] = 0
        
        row['gap_up'] = 1 if row['gap_pts'] > 10 else 0
        row['gap_down'] = 1 if row['gap_pts'] < -10 else 0
        
        if prev_hod_lod:
            try:
                prev_hod = prev_hod_lod.get('hod_time', '')
                prev_lod = prev_hod_lod.get('lod_time', '')
                hod_h = int(prev_hod.split(':')[0]) if prev_hod else 12
                lod_h = int(prev_lod.split(':')[0]) if prev_lod else 12
                row['prev_classic_buy'] = 1 if (lod_h < 12 and hod_h >= 12) else 0
                row['prev_classic_sell'] = 1 if (hod_h < 12 and lod_h >= 12) else 0
            except:
                row['prev_classic_buy'] = 0
                row['prev_classic_sell'] = 0
        else:
            row['prev_classic_buy'] = 0
            row['prev_classic_sell'] = 0
        
        row['or_vs_asia'] = 1 if london.get('open', 0) > (asia.get('range_high', 0) + asia.get('range_low', 0)) / 2 else -1
        
        try:
            dt = datetime.strptime(date, '%Y-%m-%d')
            row['day_of_week'] = dt.weekday()
        except:
            row['day_of_week'] = -1
        
        asia_range = asia.get('range_high', 0) - asia.get('range_low', 0)
        london_range = london.get('range_high', 0) - london.get('range_low', 0)
        row['london_expansion'] = london_range / asia_range if asia_range > 0 else 1
        
        if prev_hod_lod:
            prev_high = prev_hod_lod.get('daily_high', prev_hod_lod.get('hod_price', 0))
            prev_low = prev_hod_lod.get('daily_low', prev_hod_lod.get('lod_price', 0))
            row['prev_day_range'] = (prev_high - prev_low) if prev_high and prev_low else 0
        else:
            row['prev_day_range'] = 0
        
        # Target
        ny1_status = ny1.get('status', 'None')
        if ny1_status == 'Long True':
            row['target'] = 'LONG'
        elif ny1_status == 'Short True':
            row['target'] = 'SHORT'
        else:
            row['target'] = 'NEUTRAL'
        
        rows.append(row)
    
    return pd.DataFrame(rows)


def train_and_test(df_train: pd.DataFrame, df_test: pd.DataFrame):
    """Train model and evaluate on test set."""
    # Filter NEUTRAL
    df_train = df_train[df_train['target'] != 'NEUTRAL'].copy()
    df_test = df_test[df_test['target'] != 'NEUTRAL'].copy()
    
    if len(df_train) < 50 or len(df_test) < 10:
        return None
    
    # Encode
    le_aln = LabelEncoder()
    all_aln = pd.concat([df_train['aln'], df_test['aln']])
    le_aln.fit(all_aln)
    df_train['aln_encoded'] = le_aln.transform(df_train['aln'])
    df_test['aln_encoded'] = le_aln.transform(df_test['aln'])
    
    feature_cols = [
        'aln_encoded', 'asia_broken', 'london_broken',
        'asia_long', 'asia_short', 'london_long', 'london_short',
        'gap_pts', 'gap_up', 'gap_down',
        'prev_classic_buy', 'prev_classic_sell',
        'or_vs_asia', 'day_of_week',
        'prev_day_range', 'london_expansion',
    ]
    
    X_train = df_train[feature_cols].values
    y_train = df_train['target'].values
    X_test = df_test[feature_cols].values
    y_test = df_test['target'].values
    
    # Scale
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # Train with class balancing
    class_counts = pd.Series(y_train).value_counts()
    total = len(y_train)
    weights = [total / (2 * class_counts[y]) for y in y_train]
    
    model = GradientBoostingClassifier(n_estimators=100, max_depth=5, random_state=42)
    model.fit(X_train_scaled, y_train, sample_weight=weights)
    
    # Predict
    y_pred = model.predict(X_test_scaled)
    
    return {
        'train_samples': len(df_train),
        'test_samples': len(df_test),
        'accuracy': accuracy_score(y_test, y_pred),
        'long_precision': precision_score(y_test, y_pred, pos_label='LONG', zero_division=0),
        'short_precision': precision_score(y_test, y_pred, pos_label='SHORT', zero_division=0),
        'predictions': list(y_pred),
        'actuals': list(y_test),
    }


def run_walk_forward(ticker: str, df: pd.DataFrame):
    """Run walk-forward validation across all test periods."""
    print(f"\n{'='*70}")
    print(f"WALK-FORWARD VALIDATION: {ticker}")
    print(f"{'='*70}")
    
    results = []
    
    for period in TEST_PERIODS:
        # Split data
        df_train = df[df['date'] < period['start']].copy()
        df_test = df[(df['date'] >= period['start']) & (df['date'] < period['end'])].copy()
        
        if len(df_train) < 50:
            print(f"  {period['name']}: ⚠️ Insufficient training data")
            continue
        
        if len(df_test) < 10:
            print(f"  {period['name']}: ⚠️ Insufficient test data")
            continue
        
        result = train_and_test(df_train, df_test)
        
        if result:
            result['period'] = period['name']
            results.append(result)
            
            print(f"  {period['name']}: Train={result['train_samples']:>4}, Test={result['test_samples']:>3}, "
                  f"Acc={result['accuracy']:.1%}, LongP={result['long_precision']:.1%}, ShortP={result['short_precision']:.1%}")
    
    return results


if __name__ == "__main__":
    print("="*70)
    print("MULTI-PERIOD OUT-OF-SAMPLE VALIDATION")
    print("="*70)
    print("\nTest Periods:")
    for p in TEST_PERIODS:
        print(f"  - {p['name']}: {p['start']} to {p['end']}")
    
    all_results = {}
    
    for ticker in TICKERS:
        print(f"\nLoading {ticker}...")
        daily = load_profiler_data(ticker)
        df = create_features(daily)
        print(f"  Total samples: {len(df)}")
        
        results = run_walk_forward(ticker, df)
        all_results[ticker] = results
    
    # Summary table
    print("\n" + "="*70)
    print("SUMMARY BY TICKER AND PERIOD")
    print("="*70)
    
    print("\n{:<8}".format("Period"), end="")
    for ticker in TICKERS:
        print(f"{ticker:>10}", end="")
    print("")
    print("-"*50)
    
    for period in TEST_PERIODS:
        print(f"{period['name']:<8}", end="")
        for ticker in TICKERS:
            ticker_results = all_results.get(ticker, [])
            period_result = next((r for r in ticker_results if r['period'] == period['name']), None)
            if period_result:
                print(f"{period_result['accuracy']:>9.1%}", end="")
            else:
                print(f"{'N/A':>10}", end="")
        print("")
    
    # Average
    print("-"*50)
    print(f"{'Average':<8}", end="")
    for ticker in TICKERS:
        ticker_results = all_results.get(ticker, [])
        if ticker_results:
            avg = np.mean([r['accuracy'] for r in ticker_results])
            print(f"{avg:>9.1%}", end="")
        else:
            print(f"{'N/A':>10}", end="")
    print("")
    
    # Overall stats
    print("\n" + "="*70)
    print("OVERALL STATISTICS")
    print("="*70)
    
    for ticker in TICKERS:
        ticker_results = all_results.get(ticker, [])
        if ticker_results:
            accuracies = [r['accuracy'] for r in ticker_results]
            print(f"\n{ticker}:")
            print(f"  Mean: {np.mean(accuracies):.1%}")
            print(f"  Std:  {np.std(accuracies):.1%}")
            print(f"  Min:  {np.min(accuracies):.1%}")
            print(f"  Max:  {np.max(accuracies):.1%}")
