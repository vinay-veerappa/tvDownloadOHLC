"""
NY AM Session High/Low Timing Prediction
==========================================
Predict when the SESSION high and SESSION low occur WITHIN the NY AM session (9:30-12:00).

This is actionable for day trading because:
- We're predicting session extremes, not daily extremes
- The high/low WILL occur during this session by definition
- 15-minute buckets: 10 buckets covering 150 minutes

Comparison:
1. Random (majority class)
2. Filtered Profiler (filter by London condition, use majority)
3. ML Classifier
"""

import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import accuracy_score, classification_report
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Config
OUTPUT_DIR = Path(__file__).parent / "output"
TICKER = "NQ1"

TRAIN_END = "2022-12-31"
OOS_START = "2024-07-01"

# 15-minute buckets for 150-minute session
BUCKETS = [
    '0-15',    # 9:30-9:45
    '15-30',   # 9:45-10:00
    '30-45',   # 10:00-10:15
    '45-60',   # 10:15-10:30
    '60-75',   # 10:30-10:45
    '75-90',   # 10:45-11:00
    '90-105',  # 11:00-11:15
    '105-120', # 11:15-11:30
    '120-135', # 11:30-11:45
    '135-150', # 11:45-12:00
]

def get_15m_bucket(minutes):
    """Convert session minutes (0-150) to 15-min bucket."""
    bucket_idx = min(int(minutes // 15), 9)
    return BUCKETS[bucket_idx]


def load_session_metrics():
    """Load pre-extracted NY AM session metrics."""
    metrics_path = OUTPUT_DIR / f"{TICKER}_NY_AM_metrics.csv"
    df = pd.read_csv(metrics_path)
    return df


def main():
    print("="*70)
    print("NY AM SESSION HIGH/LOW TIMING PREDICTION")
    print("="*70)
    print("(Predicting when HIGH/LOW occurs WITHIN the 9:30-12:00 session)")
    
    # Load data
    df = load_session_metrics()
    print(f"\nLoaded {len(df)} NY AM sessions")
    
    # Create 15-min buckets for high_time and low_time
    df['high_bucket'] = df['high_time'].apply(get_15m_bucket)
    df['low_bucket'] = df['low_time'].apply(get_15m_bucket)
    
    # Show distribution
    print("\n--- Session High Timing Distribution (15-min buckets) ---")
    high_dist = df['high_bucket'].value_counts().reindex(BUCKETS, fill_value=0)
    for bucket, count in high_dist.items():
        pct = count / len(df) * 100
        print(f"  {bucket:>8}: {count:>4} ({pct:>5.1f}%)")
    
    print("\n--- Session Low Timing Distribution ---")
    low_dist = df['low_bucket'].value_counts().reindex(BUCKETS, fill_value=0)
    for bucket, count in low_dist.items():
        pct = count / len(df) * 100
        print(f"  {bucket:>8}: {count:>4} ({pct:>5.1f}%)")
    
    # Split by date
    train = df[df['date'] <= TRAIN_END].copy()
    test = df[df['date'] >= OOS_START].copy()
    
    print(f"\nTrain: {len(train)} sessions (up to {TRAIN_END})")
    print(f"Test: {len(test)} sessions (from {OOS_START})")
    
    # Features
    feature_cols = ['asia_broken', 'london_broken', 'asia_long', 'london_long']
    
    results = {}
    
    for target in ['high_bucket', 'low_bucket']:
        print(f"\n{'='*60}")
        print(f"TARGET: Session {target.replace('_bucket', '').upper()} Timing")
        print(f"{'='*60}")
        
        X_train = train[feature_cols].values
        y_train = train[target].values
        X_test = test[feature_cols].values
        y_test = test[target].values
        
        # ML Classifier
        scaler = StandardScaler()
        X_train_s = scaler.fit_transform(X_train)
        X_test_s = scaler.transform(X_test)
        
        clf = GradientBoostingClassifier(n_estimators=100, max_depth=4, random_state=42)
        clf.fit(X_train_s, y_train)
        ml_preds = clf.predict(X_test_s)
        ml_acc = accuracy_score(y_test, ml_preds)
        
        # Filtered Profiler: majority by london_long
        filtered_preds = []
        for _, row in test.iterrows():
            subset = train[train['london_long'] == row['london_long']]
            if len(subset) > 0:
                filtered_preds.append(subset[target].mode().iloc[0])
            else:
                filtered_preds.append(train[target].mode().iloc[0])
        filtered_acc = accuracy_score(y_test, filtered_preds)
        
        # Filtered by more conditions
        filtered2_preds = []
        for _, row in test.iterrows():
            subset = train[
                (train['london_long'] == row['london_long']) &
                (train['asia_broken'] == row['asia_broken'])
            ]
            if len(subset) < 10:
                subset = train[train['london_long'] == row['london_long']]
            if len(subset) > 0:
                filtered2_preds.append(subset[target].mode().iloc[0])
            else:
                filtered2_preds.append(train[target].mode().iloc[0])
        filtered2_acc = accuracy_score(y_test, filtered2_preds)
        
        # Random baseline
        majority = train[target].mode().iloc[0]
        random_acc = (y_test == majority).mean()
        n_classes = len(train[target].unique())
        
        print(f"\n--- Accuracy Comparison (Random baseline: {1/n_classes:.1%}) ---")
        print(f"  Majority ('{majority}'):         {random_acc:.1%}")
        print(f"  Filtered (London only):          {filtered_acc:.1%}")
        print(f"  Filtered (London+Asia):          {filtered2_acc:.1%}")
        print(f"  ML Classifier:                   {ml_acc:.1%}")
        
        best = max(ml_acc, filtered_acc, filtered2_acc)
        if ml_acc == best:
            print(f"\n  [+] ML is best or tied")
        elif filtered2_acc == best:
            print(f"\n  [=] Filtered (London+Asia) is best")
        else:
            print(f"\n  [=] Filtered (London only) is best")
        
        # Feature importance
        print(f"\n--- Feature Importance ---")
        for feat, imp in sorted(zip(feature_cols, clf.feature_importances_), key=lambda x: -x[1]):
            print(f"  {feat}: {imp:.3f}")
        
        results[target] = {
            'random': random_acc,
            'filtered': filtered_acc,
            'filtered2': filtered2_acc,
            'ml': ml_acc,
        }
    
    # Create comparison chart
    print("\n" + "="*60)
    print("CREATING VISUALIZATION")
    print("="*60)
    
    fig = make_subplots(rows=1, cols=2, subplot_titles=['Session HIGH Timing', 'Session LOW Timing'])
    
    for i, target in enumerate(['high_bucket', 'low_bucket']):
        col = i + 1
        
        # Historical distribution
        hist_data = train[target].value_counts().reindex(BUCKETS, fill_value=0)
        hist_data = hist_data / hist_data.sum()
        
        # OOS distribution
        oos_data = test[target].value_counts().reindex(BUCKETS, fill_value=0)
        oos_data = oos_data / oos_data.sum()
        
        fig.add_trace(
            go.Bar(x=BUCKETS, y=hist_data.values, name='Historical', marker_color='blue', opacity=0.7),
            row=1, col=col
        )
        fig.add_trace(
            go.Bar(x=BUCKETS, y=oos_data.values, name='OOS Actual', marker_color='orange', opacity=0.7),
            row=1, col=col
        )
    
    fig.update_layout(
        title='NY AM Session High/Low Timing Distribution (Historical vs OOS)',
        template='plotly_dark',
        height=500,
        barmode='group'
    )
    
    fig.write_html(OUTPUT_DIR / 'ny_am_session_timing.html')
    print(f"[OK] Chart saved: {OUTPUT_DIR / 'ny_am_session_timing.html'}")
    
    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    
    print("\n                    | HIGH Timing | LOW Timing |")
    print("--------------------|-------------|------------|")
    print(f"Random (majority)   | {results['high_bucket']['random']:>10.1%} | {results['low_bucket']['random']:>9.1%} |")
    print(f"Filtered (London)   | {results['high_bucket']['filtered']:>10.1%} | {results['low_bucket']['filtered']:>9.1%} |")
    print(f"Filtered (Lon+Asia) | {results['high_bucket']['filtered2']:>10.1%} | {results['low_bucket']['filtered2']:>9.1%} |")
    print(f"ML Classifier       | {results['high_bucket']['ml']:>10.1%} | {results['low_bucket']['ml']:>9.1%} |")
    
    print("\n[OK] Done!")


if __name__ == "__main__":
    main()
