"""Simple 15-min timing comparison test."""
import pandas as pd
import numpy as np
import json
from pathlib import Path
from collections import defaultdict
from datetime import datetime
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import accuracy_score

DATA_DIR = Path("data")
TICKER = "NQ1"
TRAIN_END = "2022-12-31"
OOS_START = "2024-07-01"

def time_to_minutes(time_str):
    if not time_str:
        return -1
    parts = time_str.split(':')
    return int(parts[0]) * 60 + int(parts[1])

def get_15m_bucket(minutes):
    """15-minute buckets for NY AM session."""
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

# Load data
print("Loading data...")
with open(DATA_DIR / f"{TICKER}_profiler.json") as f:
    profiler_raw = json.load(f)

with open(DATA_DIR / f"{TICKER}_daily_hod_lod.json") as f:
    hod_lod = json.load(f)

# Build profiler by date
profiler = defaultdict(dict)
for r in profiler_raw:
    profiler[r['date']][r['session']] = r

# Build dataset
rows = []
for date, sessions in profiler.items():
    asia = sessions.get('Asia', {})
    london = sessions.get('London', {})
    hl = hod_lod.get(date, {})
    
    if not hl or not asia or not london:
        continue
    
    hod_mins = time_to_minutes(hl.get('hod_time', ''))
    lod_mins = time_to_minutes(hl.get('lod_time', ''))
    
    if hod_mins < 0 or lod_mins < 0:
        continue
    
    rows.append({
        'date': date,
        'asia_broken': 1 if asia.get('broken', False) else 0,
        'london_broken': 1 if london.get('broken', False) else 0,
        'london_long': 1 if 'Long' in london.get('status', '') else 0,
        'hod_bucket': get_15m_bucket(hod_mins),
        'lod_bucket': get_15m_bucket(lod_mins),
    })

df = pd.DataFrame(rows)
print(f"Total days: {len(df)}")

# Show bucket distribution
print("\n--- HOD Bucket Distribution (12 buckets at 15min) ---")
print(df['hod_bucket'].value_counts().sort_index())

print("\n--- LOD Bucket Distribution ---")
print(df['lod_bucket'].value_counts().sort_index())

# Split
train = df[df['date'] <= TRAIN_END]
test = df[df['date'] >= OOS_START]
print(f"\nTrain: {len(train)}, Test: {len(test)}")

# Test ML vs Filtered for each target
for target in ['hod_bucket', 'lod_bucket']:
    print(f"\n{'='*50}")
    print(f"TARGET: {target}")
    print(f"{'='*50}")
    
    # Features
    X_train = train[['asia_broken', 'london_broken', 'london_long']].values
    y_train = train[target].values
    X_test = test[['asia_broken', 'london_broken', 'london_long']].values
    y_test = test[target].values
    
    # ML
    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s = scaler.transform(X_test)
    
    clf = GradientBoostingClassifier(n_estimators=50, max_depth=3, random_state=42)
    clf.fit(X_train_s, y_train)
    ml_preds = clf.predict(X_test_s)
    ml_acc = accuracy_score(y_test, ml_preds)
    
    # Filtered baseline: majority by london_long
    filtered_preds = []
    for _, row in test.iterrows():
        subset = train[train['london_long'] == row['london_long']]
        if len(subset) > 0:
            filtered_preds.append(subset[target].mode().iloc[0])
        else:
            filtered_preds.append(train[target].mode().iloc[0])
    
    filtered_acc = accuracy_score(y_test, filtered_preds)
    
    # Random (majority class)
    majority = train[target].mode().iloc[0]
    random_acc = (y_test == majority).mean()
    
    print(f"Random (majority '{majority}'): {random_acc:.1%}")
    print(f"Filtered Profiler:              {filtered_acc:.1%}")
    print(f"ML Classifier:                  {ml_acc:.1%}")
    
    if ml_acc > filtered_acc:
        print("[+] ML beats filtered profiler")
    else:
        print("[-] ML does NOT beat filtered profiler")

print("\nDone!")
