"""
Enhanced Bias Prediction with Machine Learning
================================================
Uses all available derived data to predict NY AM/PM bias.

Features:
- ALN Pattern (LPEU, LPED, LEA, AEL)
- Broken Status (Asia/London held or broken)
- Profiler Status (Asia/London Long/Short)
- Prior Day Close vs Open (Gap)
- Midnight position
- 7:30 Open position
- Previous HOD/LOD timing
- Day of week

Target: NY1 Status (Long True / Short True / False)
"""

import json
import pandas as pd
import numpy as np
from collections import defaultdict
from pathlib import Path
from datetime import datetime
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, accuracy_score, confusion_matrix

# --- CONFIG ---
DATA_DIR = Path(__file__).parent.parent.parent.parent / "data"
TICKERS = ['NQ1']  # Start with NQ1, can expand


def load_all_data(ticker: str):
    """Load all relevant data sources for a ticker."""
    profiler_file = DATA_DIR / f"{ticker}_profiler.json"
    hod_lod_file = DATA_DIR / f"{ticker}_daily_hod_lod.json"
    opening_range_file = DATA_DIR / f"{ticker}_opening_range.json"
    
    with open(profiler_file) as f:
        profiler_data = json.load(f)
    
    with open(hod_lod_file) as f:
        hod_lod_data = json.load(f)
    
    # Opening range is a list
    with open(opening_range_file) as f:
        or_data = json.load(f)
    or_by_date = {r['date']: r for r in or_data}
    
    # Group profiler by date
    daily = defaultdict(dict)
    for record in profiler_data:
        date = record['date']
        session = record['session']
        daily[date][session] = record
    
    # Merge HOD/LOD data
    for date, hod_lod in hod_lod_data.items():
        if date in daily:
            daily[date]['hod_lod'] = hod_lod
    
    # Merge Opening Range
    for date, orec in or_by_date.items():
        if date in daily:
            daily[date]['opening_range'] = orec
    
    return daily


def parse_time(time_str):
    """Parse time string to hour decimal."""
    if not time_str:
        return None
    try:
        parts = time_str.split(':')
        return int(parts[0]) + int(parts[1]) / 60
    except:
        return None


def classify_aln(asia: dict, london: dict) -> str:
    """Classify ALN pattern."""
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


def create_feature_matrix(daily: dict) -> pd.DataFrame:
    """Create feature matrix from daily data."""
    rows = []
    dates = sorted(daily.keys())
    
    for i, date in enumerate(dates):
        sessions = daily[date]
        asia = sessions.get('Asia')
        london = sessions.get('London')
        ny1 = sessions.get('NY1')
        hod_lod = sessions.get('hod_lod')
        opening_range = sessions.get('opening_range')
        
        if not all([asia, london, ny1]):
            continue
        
        # Previous day data
        prev_date = dates[i-1] if i > 0 else None
        prev_sessions = daily.get(prev_date, {}) if prev_date else {}
        prev_ny2 = prev_sessions.get('NY2', {})
        prev_hod_lod = prev_sessions.get('hod_lod', {})
        
        # === FEATURES ===
        row = {'date': date}
        
        # 1. ALN Pattern
        row['aln'] = classify_aln(asia, london)
        
        # 2. Broken Status
        row['asia_broken'] = 1 if asia.get('broken', False) else 0
        row['london_broken'] = 1 if london.get('broken', False) else 0
        
        # 3. Session Status (Long/Short)
        asia_status = asia.get('status', 'None')
        london_status = london.get('status', 'None')
        row['asia_long'] = 1 if 'Long' in asia_status else 0
        row['asia_short'] = 1 if 'Short' in asia_status else 0
        row['london_long'] = 1 if 'Long' in london_status else 0
        row['london_short'] = 1 if 'Short' in london_status else 0
        
        # 4. Gap (London Open vs Prior Day Close)
        if prev_ny2 and london:
            prev_close = prev_ny2.get('range_low', prev_ny2.get('range_high', None))  # Approx close
            london_open = london.get('open')
            if prev_close and london_open:
                row['gap_pts'] = london_open - prev_close
                row['gap_up'] = 1 if row['gap_pts'] > 10 else 0
                row['gap_down'] = 1 if row['gap_pts'] < -10 else 0
            else:
                row['gap_pts'] = 0
                row['gap_up'] = 0
                row['gap_down'] = 0
        else:
            row['gap_pts'] = 0
            row['gap_up'] = 0
            row['gap_down'] = 0
        
        # 5. Prior Day ICT Profile
        if prev_hod_lod:
            prev_hod = parse_time(prev_hod_lod.get('hod_time'))
            prev_lod = parse_time(prev_hod_lod.get('lod_time'))
            if prev_hod and prev_lod:
                row['prev_classic_buy'] = 1 if (prev_lod < 12 and prev_hod >= 12) else 0
                row['prev_classic_sell'] = 1 if (prev_hod < 12 and prev_lod >= 12) else 0
            else:
                row['prev_classic_buy'] = 0
                row['prev_classic_sell'] = 0
        else:
            row['prev_classic_buy'] = 0
            row['prev_classic_sell'] = 0
        
        # 6. Opening Range Position
        if opening_range:
            or_mid = (opening_range.get('high', 0) + opening_range.get('low', 0)) / 2
            asia_mid = (asia.get('range_high', 0) + asia.get('range_low', 0)) / 2
            if or_mid and asia_mid:
                row['or_vs_asia'] = 1 if or_mid > asia_mid else -1
            else:
                row['or_vs_asia'] = 0
        else:
            row['or_vs_asia'] = 0
        
        # 7. London Range vs Asia Range (expansion/contraction)
        asia_range = asia.get('range_high', 0) - asia.get('range_low', 0)
        london_range = london.get('range_high', 0) - london.get('range_low', 0)
        row['london_expansion'] = 1 if london_range > asia_range * 1.2 else 0
        
        # 8. Day of Week
        try:
            dt = datetime.strptime(date, '%Y-%m-%d')
            row['day_of_week'] = dt.weekday()  # 0=Mon, 4=Fri
        except:
            row['day_of_week'] = -1
        
        # === TARGET ===
        ny1_status = ny1.get('status', 'None')
        if ny1_status == 'Long True':
            row['target'] = 'LONG'
        elif ny1_status == 'Short True':
            row['target'] = 'SHORT'
        else:
            row['target'] = 'NEUTRAL'
        
        rows.append(row)
    
    return pd.DataFrame(rows)


def train_and_evaluate(df: pd.DataFrame):
    """Train ML models and evaluate."""
    print(f"\n{'='*60}")
    print("FEATURE MATRIX CREATED")
    print(f"{'='*60}")
    print(f"Total samples: {len(df)}")
    print(f"Target distribution:\n{df['target'].value_counts()}")
    
    # Encode categorical features
    le_aln = LabelEncoder()
    df['aln_encoded'] = le_aln.fit_transform(df['aln'])
    
    # Features
    feature_cols = [
        'aln_encoded', 'asia_broken', 'london_broken',
        'asia_long', 'asia_short', 'london_long', 'london_short',
        'gap_pts', 'gap_up', 'gap_down',
        'prev_classic_buy', 'prev_classic_sell',
        'or_vs_asia', 'london_expansion', 'day_of_week'
    ]
    
    X = df[feature_cols].values
    y = df['target'].values
    
    # Split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    print(f"\nTrain samples: {len(X_train)}")
    print(f"Test samples: {len(X_test)}")
    
    # Models to try
    models = {
        'Logistic Regression': LogisticRegression(max_iter=1000),
        'Random Forest': RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42),
        'Gradient Boosting': GradientBoostingClassifier(n_estimators=100, max_depth=5, random_state=42),
    }
    
    results = {}
    
    for name, model in models.items():
        print(f"\n{'='*60}")
        print(f"MODEL: {name}")
        print(f"{'='*60}")
        
        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)
        
        acc = accuracy_score(y_test, y_pred)
        results[name] = acc
        
        print(f"Accuracy: {acc:.2%}")
        print("\nClassification Report:")
        print(classification_report(y_test, y_pred))
        
        # Feature importance for tree models
        if hasattr(model, 'feature_importances_'):
            print("\nTop 5 Feature Importances:")
            importances = list(zip(feature_cols, model.feature_importances_))
            importances.sort(key=lambda x: x[1], reverse=True)
            for feat, imp in importances[:5]:
                print(f"  {feat}: {imp:.3f}")
    
    return results, df


if __name__ == "__main__":
    print("Loading all data for NQ1...")
    daily = load_all_data('NQ1')
    print(f"Loaded {len(daily)} trading days.")
    
    print("\nCreating feature matrix...")
    df = create_feature_matrix(daily)
    
    print("\nTraining ML models...")
    results, df = train_and_evaluate(df)
    
    # Save feature matrix for later analysis
    df.to_csv(DATA_DIR / 'ml_feature_matrix.csv', index=False)
    print(f"\n✅ Feature matrix saved to: {DATA_DIR / 'ml_feature_matrix.csv'}")
