"""
ML Timing vs Filtered Profiler Comparison
==========================================
Compare ML timing predictions against the profiler's filtered HOD/LOD distributions.

Fair comparison: Filter historical data by the same pre-market conditions
that the ML model uses, then compare prediction accuracy.

Question: Does ML add value over just filtering historical data?
"""

import pandas as pd
import numpy as np
import json
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import accuracy_score
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Config
DATA_DIR = Path(__file__).parent.parent.parent.parent / "data"
OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

TICKER = "NQ1"

# Data splits
TRAIN_END = "2022-12-31"
OOS_START = "2024-07-01"


def load_profiler_data():
    """Load profiler sessions with all features."""
    file_path = DATA_DIR / f"{TICKER}_profiler.json"
    
    with open(file_path) as f:
        data = json.load(f)
    
    # Group by date
    by_date = defaultdict(dict)
    for record in data:
        by_date[record['date']][record['session']] = record
    
    return by_date


def load_daily_hod_lod():
    """Load daily HOD/LOD timing data."""
    file_path = DATA_DIR / f"{TICKER}_daily_hod_lod.json"
    
    with open(file_path) as f:
        data = json.load(f)
    
    return data


def time_to_minutes(time_str: str) -> int:
    """Convert HH:MM to minutes from midnight."""
    if not time_str:
        return -1
    parts = time_str.split(':')
    return int(parts[0]) * 60 + int(parts[1])


def get_timing_bucket(minutes: int, session: str = 'NY_AM') -> str:
    """Classify timing into 15-minute buckets."""
    if session == 'NY_AM':
        # NY AM: 9:30 (570) - 12:00 (720) = 150 min = 10 buckets
        if minutes < 570:
            return 'pre_9:30'
        elif minutes < 585:
            return '9:30-9:45'
        elif minutes < 600:
            return '9:45-10:00'
        elif minutes < 615:
            return '10:00-10:15'
        elif minutes < 630:
            return '10:15-10:30'
        elif minutes < 645:
            return '10:30-10:45'
        elif minutes < 660:
            return '10:45-11:00'
        elif minutes < 675:
            return '11:00-11:15'
        elif minutes < 690:
            return '11:15-11:30'
        elif minutes < 705:
            return '11:30-11:45'
        elif minutes < 720:
            return '11:45-12:00'
        else:
            return 'post_12:00'
    else:
        # NY PM: 12:00 (720) - 16:00 (960) = 240 min = 16 buckets
        if minutes < 720:
            return 'pre_12:00'
        bucket_num = (minutes - 720) // 15
        start_hour = 12 + bucket_num // 4
        start_min = (bucket_num % 4) * 15
        end_min = start_min + 15
        if end_min == 60:
            end_hour = start_hour + 1
            end_min = 0
        else:
            end_hour = start_hour
        if minutes >= 960:
            return 'post_16:00'
        return f'{start_hour}:{start_min:02d}-{end_hour}:{end_min:02d}'


def build_dataset(profiler_data: dict, hod_lod_data: dict):
    """Build combined dataset with features and HOD/LOD timing."""
    rows = []
    
    for date, sessions in profiler_data.items():
        asia = sessions.get('Asia', {})
        london = sessions.get('London', {})
        ny1 = sessions.get('NY1', {})
        
        hod_lod = hod_lod_data.get(date, {})
        
        if not hod_lod or not asia or not london:
            continue
        
        hod_time = hod_lod.get('hod_time', '')
        lod_time = hod_lod.get('lod_time', '')
        
        hod_mins = time_to_minutes(hod_time)
        lod_mins = time_to_minutes(lod_time)
        
        if hod_mins < 0 or lod_mins < 0:
            continue
        
        # Features
        asia_range = asia.get('range_high', 0) - asia.get('range_low', 0)
        london_range = london.get('range_high', 0) - london.get('range_low', 0)
        
        row = {
            'date': date,
            # Pre-market features
            'asia_broken': 1 if asia.get('broken', False) else 0,
            'london_broken': 1 if london.get('broken', False) else 0,
            'asia_long': 1 if 'Long' in asia.get('status', '') else 0,
            'asia_short': 1 if 'Short' in asia.get('status', '') else 0,
            'london_long': 1 if 'Long' in london.get('status', '') else 0,
            'london_short': 1 if 'Short' in london.get('status', '') else 0,
            'london_expansion': london_range / asia_range if asia_range > 0 else 1,
            # Timing targets
            'hod_mins': hod_mins,
            'lod_mins': lod_mins,
            'hod_bucket': get_timing_bucket(hod_mins, 'NY_AM'),
            'lod_bucket': get_timing_bucket(lod_mins, 'NY_AM'),
        }
        
        # Day of week
        try:
            dt = datetime.strptime(date, '%Y-%m-%d')
            row['day_of_week'] = dt.weekday()
        except:
            row['day_of_week'] = 0
        
        rows.append(row)
    
    return pd.DataFrame(rows)


def filtered_baseline_prediction(train_df: pd.DataFrame, test_row: pd.Series, target: str):
    """
    Filtered profiler baseline: Find historical days with similar conditions
    and predict based on majority vote.
    """
    # Filter by same pre-market conditions
    filtered = train_df[
        (train_df['asia_broken'] == test_row['asia_broken']) &
        (train_df['london_broken'] == test_row['london_broken']) &
        (train_df['london_long'] == test_row['london_long'])
    ]
    
    # If too few matches, relax filters
    if len(filtered) < 10:
        filtered = train_df[
            (train_df['london_long'] == test_row['london_long'])
        ]
    
    if len(filtered) < 5:
        filtered = train_df
    
    # Return majority bucket
    return filtered[target].mode().iloc[0] if len(filtered) > 0 else 'mid'


def train_ml_classifier(train_df: pd.DataFrame, target: str):
    """Train ML classifier."""
    feature_cols = ['asia_broken', 'london_broken', 'asia_long', 'london_long',
                    'london_expansion', 'day_of_week']
    
    X = train_df[feature_cols].values
    y = train_df[target].values
    
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    clf = GradientBoostingClassifier(n_estimators=100, max_depth=4, random_state=42)
    clf.fit(X_scaled, y)
    
    return clf, scaler, feature_cols


def run_comparison():
    """Run full comparison between ML and filtered profiler baseline."""
    print("="*70)
    print("ML TIMING vs FILTERED PROFILER COMPARISON")
    print("="*70)
    
    # Load data
    profiler_data = load_profiler_data()
    hod_lod_data = load_daily_hod_lod()
    
    print(f"Loaded {len(profiler_data)} profiler days")
    print(f"Loaded {len(hod_lod_data)} HOD/LOD records")
    
    # Build dataset
    df = build_dataset(profiler_data, hod_lod_data)
    print(f"Combined dataset: {len(df)} days")
    
    # Split
    train_df = df[df['date'] <= TRAIN_END].copy()
    test_df = df[df['date'] >= OOS_START].copy()
    
    print(f"\nTrain: {len(train_df)} (up to {TRAIN_END})")
    print(f"Test: {len(test_df)} (from {OOS_START})")
    
    # Test on HOD and LOD timing
    for target in ['hod_bucket', 'lod_bucket']:
        print(f"\n{'='*50}")
        print(f"TARGET: {target.upper()}")
        print(f"{'='*50}")
        
        # Train ML
        clf, scaler, feature_cols = train_ml_classifier(train_df, target)
        
        # Predict
        X_test = test_df[feature_cols].values
        X_test_scaled = scaler.transform(X_test)
        ml_preds = clf.predict(X_test_scaled)
        
        # Filtered baseline predictions
        baseline_preds = []
        for _, row in test_df.iterrows():
            pred = filtered_baseline_prediction(train_df, row, target)
            baseline_preds.append(pred)
        
        # Actual
        y_actual = test_df[target].values
        
        # Calculate accuracy
        ml_acc = accuracy_score(y_actual, ml_preds)
        baseline_acc = accuracy_score(y_actual, baseline_preds)
        
        # Random baseline (majority class from train)
        majority_class = train_df[target].mode().iloc[0]
        random_acc = (y_actual == majority_class).mean()
        
        print(f"\n--- Accuracy Comparison ---")
        print(f"  Random (majority): {random_acc:.1%}")
        print(f"  Filtered Profiler: {baseline_acc:.1%}")
        print(f"  ML Classifier:     {ml_acc:.1%}")
        
        improvement = (ml_acc - baseline_acc) / baseline_acc * 100 if baseline_acc > 0 else 0
        print(f"\n  ML vs Filtered: {improvement:+.1f}%")
        
        if ml_acc > baseline_acc:
            print(f"  [+] ML adds value over filtered profiler")
        else:
            print(f"  [-] ML does NOT beat filtered profiler")
        
        # Breakdown by condition
        print(f"\n--- Accuracy by Pre-Market Condition ---")
        
        for london_long in [0, 1]:
            mask = test_df['london_long'] == london_long
            condition = "London Long" if london_long else "London Short"
            
            if mask.sum() < 5:
                continue
            
            ml_cond_acc = accuracy_score(y_actual[mask], ml_preds[mask])
            baseline_cond_acc = accuracy_score(y_actual[mask], np.array(baseline_preds)[mask])
            
            print(f"  {condition}: ML={ml_cond_acc:.1%}, Filtered={baseline_cond_acc:.1%}")
    
    # Summary visualization
    create_comparison_chart(df, train_df, test_df)
    
    print("\n" + "="*70)
    print("COMPARISON COMPLETE")
    print("="*70)


def create_comparison_chart(df: pd.DataFrame, train_df: pd.DataFrame, test_df: pd.DataFrame):
    """Create visual comparison of timing distributions."""
    fig = make_subplots(rows=2, cols=2, 
                        subplot_titles=['HOD Timing - London Long', 'HOD Timing - London Short',
                                       'LOD Timing - London Long', 'LOD Timing - London Short'])
    
    # Get buckets dynamically from data
    all_buckets = sorted(df['hod_bucket'].unique().tolist())
    
    for i, target in enumerate(['hod_bucket', 'lod_bucket']):
        for j, london_long in enumerate([1, 0]):
            row = i + 1
            col = j + 1
            
            # Historical distribution
            hist_data = train_df[train_df['london_long'] == london_long][target].value_counts(normalize=True)
            
            # OOS actual distribution
            oos_data = test_df[test_df['london_long'] == london_long][target].value_counts(normalize=True)
            
            fig.add_trace(
                go.Bar(x=all_buckets, y=[hist_data.get(b, 0) for b in all_buckets],
                       name='Historical', marker_color='blue', opacity=0.6),
                row=row, col=col
            )
            fig.add_trace(
                go.Bar(x=all_buckets, y=[oos_data.get(b, 0) for b in all_buckets],
                       name='OOS Actual', marker_color='orange', opacity=0.6),
                row=row, col=col
            )
    
    fig.update_layout(
        title='Timing Distribution: Historical vs OOS by London Condition',
        template='plotly_dark',
        height=600,
        showlegend=False,
        barmode='group'
    )
    
    fig.write_html(OUTPUT_DIR / 'timing_comparison.html')
    print(f"\n[OK] Chart saved: {OUTPUT_DIR / 'timing_comparison.html'}")


if __name__ == "__main__":
    import sys
    from io import StringIO
    
    # Capture output to file
    old_stdout = sys.stdout
    sys.stdout = buffer = StringIO()
    
    try:
        run_comparison()
    finally:
        output = buffer.getvalue()
        sys.stdout = old_stdout
        
        # Print to console
        print(output)
        
        # Save to file
        with open(OUTPUT_DIR / 'comparison_results.txt', 'w') as f:
            f.write(output)
        
        print(f"\n[SAVED] Results written to {OUTPUT_DIR / 'comparison_results.txt'}")
