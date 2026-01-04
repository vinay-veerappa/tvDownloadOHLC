"""
Binary LONG/SHORT Classifier with Class Balancing
===================================================
Removes NEUTRAL class and trains binary classifier with proper validation.

Data Split:
- Training: All data before 2025
- In-Sample Test: 2025 data (from Profiler)
- Out-of-Sample Test: December 2025 TradingView data

Class Balancing:
- Use class_weight='balanced' 
- Compare with SMOTE oversampling
"""

import json
import pandas as pd
import numpy as np
from collections import defaultdict
from pathlib import Path
from datetime import datetime
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, accuracy_score, confusion_matrix, precision_score, recall_score
import joblib

# --- CONFIG ---
DATA_DIR = Path(__file__).parent.parent.parent.parent / "data"
TV_DIR = DATA_DIR / "TV_OHLC"
MODEL_DIR = DATA_DIR / "ml_models"
MODEL_DIR.mkdir(exist_ok=True)

TICKERS = ['NQ1', 'ES1', 'YM1', 'RTY1']

# Split date
IN_SAMPLE_START = '2024-01-01'  # Use 2024 for in-sample test
OUT_OF_SAMPLE_START = '2025-12-01'  # December 2025 is out-of-sample


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
    """Create feature matrix from daily data."""
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
        
        # ALN Pattern
        row['aln'] = classify_aln(asia, london)
        
        # Broken Status
        row['asia_broken'] = 1 if asia.get('broken', False) else 0
        row['london_broken'] = 1 if london.get('broken', False) else 0
        
        # Session Status
        asia_status = asia.get('status', 'None')
        london_status = london.get('status', 'None')
        row['asia_long'] = 1 if 'Long' in asia_status else 0
        row['asia_short'] = 1 if 'Short' in asia_status else 0
        row['london_long'] = 1 if 'Long' in london_status else 0
        row['london_short'] = 1 if 'Short' in london_status else 0
        
        # Gap
        if prev_ny2 and london:
            prev_close = prev_ny2.get('range_low', prev_ny2.get('range_high', None))
            london_open = london.get('open')
            if prev_close and london_open:
                row['gap_pts'] = london_open - prev_close
            else:
                row['gap_pts'] = 0
        else:
            row['gap_pts'] = 0
        
        row['gap_up'] = 1 if row['gap_pts'] > 10 else 0
        row['gap_down'] = 1 if row['gap_pts'] < -10 else 0
        
        # Prior ICT Profile
        if prev_hod_lod:
            prev_hod = prev_hod_lod.get('hod_time', '')
            prev_lod = prev_hod_lod.get('lod_time', '')
            try:
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
        
        # London expansion
        asia_range = asia.get('range_high', 0) - asia.get('range_low', 0)
        london_range = london.get('range_high', 0) - london.get('range_low', 0)
        row['london_expansion'] = london_range / asia_range if asia_range > 0 else 1
        
        # Prior day range
        if prev_hod_lod:
            prev_high = prev_hod_lod.get('daily_high', prev_hod_lod.get('hod_price', 0))
            prev_low = prev_hod_lod.get('daily_low', prev_hod_lod.get('lod_price', 0))
            row['prev_day_range'] = (prev_high - prev_low) if prev_high and prev_low else 0
        else:
            row['prev_day_range'] = 0
        
        row['vix_level'] = 20
        row['vix_high'] = 0
        row['vix_low'] = 0
        
        # Target (LONG or SHORT only)
        ny1_status = ny1.get('status', 'None')
        if ny1_status == 'Long True':
            row['target'] = 'LONG'
        elif ny1_status == 'Short True':
            row['target'] = 'SHORT'
        else:
            row['target'] = 'NEUTRAL'  # Will be filtered out
        
        rows.append(row)
    
    return pd.DataFrame(rows)


def train_binary_model(ticker: str):
    """Train binary LONG/SHORT classifier with time-based split."""
    print(f"\n{'='*70}")
    print(f"TRAINING BINARY MODEL FOR: {ticker}")
    print(f"{'='*70}")
    
    # Load data
    daily = load_profiler_data(ticker)
    df = create_features(daily)
    
    # Filter out NEUTRAL
    df_binary = df[df['target'] != 'NEUTRAL'].copy()
    
    print(f"Total samples: {len(df)}")
    print(f"Binary samples (LONG/SHORT only): {len(df_binary)}")
    print(f"Target distribution: {df_binary['target'].value_counts().to_dict()}")
    
    # Time-based split
    df_train = df_binary[df_binary['date'] < IN_SAMPLE_START].copy()
    df_test_in = df_binary[(df_binary['date'] >= IN_SAMPLE_START) & (df_binary['date'] < OUT_OF_SAMPLE_START)].copy()
    
    print(f"\nTraining set: {len(df_train)} samples (before {IN_SAMPLE_START})")
    print(f"In-sample test: {len(df_test_in)} samples ({IN_SAMPLE_START} to {OUT_OF_SAMPLE_START})")
    
    if len(df_train) < 100 or len(df_test_in) < 20:
        print("⚠️ Insufficient data for proper split")
        return None
    
    # Encode ALN
    le_aln = LabelEncoder()
    all_aln = pd.concat([df_train['aln'], df_test_in['aln']])
    le_aln.fit(all_aln)
    df_train['aln_encoded'] = le_aln.transform(df_train['aln'])
    df_test_in['aln_encoded'] = le_aln.transform(df_test_in['aln'])
    
    # Features
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
    X_test = df_test_in[feature_cols].values
    y_test = df_test_in['target'].values
    
    # Scale
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # Train with class_weight='balanced'
    model = GradientBoostingClassifier(
        n_estimators=100, 
        max_depth=5, 
        random_state=42
    )
    
    # Sample weights for class balancing
    class_counts = pd.Series(y_train).value_counts()
    total = len(y_train)
    weights = [total / (2 * class_counts[y]) for y in y_train]
    
    model.fit(X_train_scaled, y_train, sample_weight=weights)
    
    # Evaluate on in-sample test
    y_pred = model.predict(X_test_scaled)
    accuracy = accuracy_score(y_test, y_pred)
    precision = precision_score(y_test, y_pred, pos_label='LONG')
    recall = recall_score(y_test, y_pred, pos_label='LONG')
    
    print(f"\n--- IN-SAMPLE TEST RESULTS ({IN_SAMPLE_START} - {OUT_OF_SAMPLE_START}) ---")
    print(f"Accuracy: {accuracy:.1%}")
    print(f"Long Precision: {precision:.1%}")
    print(f"Long Recall: {recall:.1%}")
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred))
    
    print("\nConfusion Matrix:")
    print(pd.crosstab(pd.Series(y_pred, name='Predicted'), pd.Series(y_test, name='Actual')))
    
    # Feature importance
    print("\nTop 5 Features:")
    importances = list(zip(feature_cols, model.feature_importances_))
    importances.sort(key=lambda x: x[1], reverse=True)
    for feat, imp in importances[:5]:
        print(f"  {feat}: {imp:.3f}")
    
    # Save model
    model_path = MODEL_DIR / f"{ticker}_binary_model.pkl"
    joblib.dump({
        'model': model, 
        'scaler': scaler, 
        'features': feature_cols, 
        'le_aln': le_aln,
        'train_dates': df_train['date'].tolist(),
    }, model_path)
    print(f"\n✅ Model saved: {model_path}")
    
    return {
        'ticker': ticker,
        'train_samples': len(df_train),
        'test_samples': len(df_test_in),
        'accuracy': accuracy,
        'precision': precision,
        'recall': recall,
    }


def test_on_tradingview(ticker: str):
    """Test binary model on TradingView December data."""
    import pytz
    
    ET = pytz.timezone('America/New_York')
    
    # Load TV data
    file_map = {
        'NQ1': 'CME_MINI_NQ1!, 1_23f45.csv',
        'ES1': 'CME_MINI_ES1!, 1_2e5eb.csv',
        'RTY1': 'CME_MINI_RTY1!, 1_c377c.csv',
        'YM1': 'CBOT_MINI_YM1!, 1_7893b.csv',
    }
    
    filename = file_map.get(ticker)
    if not filename:
        return None
    
    file_path = TV_DIR / filename
    if not file_path.exists():
        return None
    
    df_tv = pd.read_csv(file_path)
    df_tv['datetime_utc'] = pd.to_datetime(df_tv['time'], unit='s', utc=True)
    df_tv['datetime_et'] = df_tv['datetime_utc'].dt.tz_convert(ET)
    df_tv = df_tv.set_index('datetime_et')
    df_tv['date'] = df_tv.index.date
    df_tv['hour'] = df_tv.index.hour
    
    # Extract sessions
    dates = df_tv['date'].unique()
    sessions_by_date = {}
    
    for date in dates:
        day_data = df_tv[df_tv['date'] == date]
        sessions_by_date[str(date)] = {}
        
        # Asia (18:00 - 02:00)
        asia_data = day_data[(day_data['hour'] >= 18) | (day_data['hour'] < 2)]
        if len(asia_data) > 0:
            sessions_by_date[str(date)]['Asia'] = {
                'range_high': asia_data['high'].max(),
                'range_low': asia_data['low'].min(),
                'open': asia_data['open'].iloc[0],
                'close': asia_data['close'].iloc[-1],
            }
        
        # London (03:00 - 08:00)
        london_data = day_data[(day_data['hour'] >= 3) & (day_data['hour'] < 8)]
        if len(london_data) > 0:
            sessions_by_date[str(date)]['London'] = {
                'range_high': london_data['high'].max(),
                'range_low': london_data['low'].min(),
                'open': london_data['open'].iloc[0],
                'close': london_data['close'].iloc[-1],
            }
        
        # NY1 (09:00 - 12:00)
        ny1_data = day_data[(day_data['hour'] >= 9) & (day_data['hour'] < 12)]
        if len(ny1_data) > 0:
            sessions_by_date[str(date)]['NY1'] = {
                'range_high': ny1_data['high'].max(),
                'range_low': ny1_data['low'].min(),
                'open': ny1_data['open'].iloc[0],
                'close': ny1_data['close'].iloc[-1],
            }
    
    # Create features
    rows = []
    sorted_dates = sorted(sessions_by_date.keys())
    
    for i, date in enumerate(sorted_dates):
        sessions = sessions_by_date[date]
        asia = sessions.get('Asia')
        london = sessions.get('London')
        ny1 = sessions.get('NY1')
        
        if not asia or not london or not ny1:
            continue
        
        prev_date = sorted_dates[i-1] if i > 0 else None
        prev_sessions = sessions_by_date.get(prev_date, {}) if prev_date else {}
        
        row = {'date': date}
        row['aln'] = classify_aln(asia, london)
        row['asia_broken'] = 1 if (london['range_high'] > asia['range_high'] or london['range_low'] < asia['range_low']) else 0
        row['london_broken'] = 0
        row['asia_long'] = 1 if asia['close'] > asia['open'] else 0
        row['asia_short'] = 1 if asia['close'] < asia['open'] else 0
        row['london_long'] = 1 if london['close'] > london['open'] else 0
        row['london_short'] = 1 if london['close'] < london['open'] else 0
        
        prev_ny1 = prev_sessions.get('NY1', {})
        if prev_ny1 and prev_ny1.get('close'):
            row['gap_pts'] = london['open'] - prev_ny1['close']
        else:
            row['gap_pts'] = 0
        
        row['gap_up'] = 1 if row['gap_pts'] > 10 else 0
        row['gap_down'] = 1 if row['gap_pts'] < -10 else 0
        row['prev_classic_buy'] = 0
        row['prev_classic_sell'] = 0
        row['or_vs_asia'] = 1 if london['open'] > (asia['range_high'] + asia['range_low']) / 2 else -1
        
        try:
            dt = datetime.strptime(date, '%Y-%m-%d')
            row['day_of_week'] = dt.weekday()
        except:
            row['day_of_week'] = -1
        
        asia_range = asia['range_high'] - asia['range_low']
        london_range = london['range_high'] - london['range_low']
        row['london_expansion'] = london_range / asia_range if asia_range > 0 else 1
        row['prev_day_range'] = 0
        
        # Actual
        if ny1['close'] > ny1['open']:
            row['actual'] = 'LONG'
        elif ny1['close'] < ny1['open']:
            row['actual'] = 'SHORT'
        else:
            row['actual'] = 'NEUTRAL'
        
        rows.append(row)
    
    df_oos = pd.DataFrame(rows)
    
    # Filter NEUTRAL
    df_oos = df_oos[df_oos['actual'] != 'NEUTRAL']
    
    if len(df_oos) == 0:
        return None
    
    # Load model
    model_path = MODEL_DIR / f"{ticker}_binary_model.pkl"
    if not model_path.exists():
        return None
    
    model_data = joblib.load(model_path)
    model = model_data['model']
    scaler = model_data['scaler']
    feature_cols = model_data['features']
    le_aln = model_data['le_aln']
    
    # Encode
    df_oos['aln_encoded'] = df_oos['aln'].apply(
        lambda x: le_aln.transform([x])[0] if x in le_aln.classes_ else 0
    )
    
    X = df_oos[feature_cols].values
    X_scaled = scaler.transform(X)
    
    y_pred = model.predict(X_scaled)
    y_actual = df_oos['actual'].values
    
    accuracy = accuracy_score(y_actual, y_pred)
    
    print(f"\n--- OUT-OF-SAMPLE TEST (TradingView December) ---")
    print(f"Samples: {len(df_oos)}")
    print(f"Accuracy: {accuracy:.1%}")
    print("\nDay-by-Day:")
    
    correct = 0
    for i, (_, row) in enumerate(df_oos.iterrows()):
        match = "✅" if y_pred[i] == row['actual'] else "❌"
        if y_pred[i] == row['actual']:
            correct += 1
        print(f"  {row['date']}: Pred={y_pred[i]:5} Act={row['actual']:5} {match}")
    
    return {
        'ticker': ticker,
        'oos_samples': len(df_oos),
        'oos_accuracy': accuracy,
    }


if __name__ == "__main__":
    print("="*70)
    print("BINARY LONG/SHORT CLASSIFIER (Class Balanced)")
    print("="*70)
    
    all_results = []
    
    for ticker in TICKERS:
        result = train_binary_model(ticker)
        if result:
            all_results.append(result)
            
            # Test on TradingView
            oos_result = test_on_tradingview(ticker)
            if oos_result:
                result['oos_accuracy'] = oos_result['oos_accuracy']
                result['oos_samples'] = oos_result['oos_samples']
    
    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    
    print("\n{:<8} {:>8} {:>10} {:>12} {:>12}".format(
        "Ticker", "Train", "In-Sample", "In-Acc", "OOS-Acc"
    ))
    print("-"*55)
    
    for r in all_results:
        oos = f"{r.get('oos_accuracy', 0):.1%}" if r.get('oos_accuracy') else "N/A"
        print("{:<8} {:>8} {:>10} {:>11.1%} {:>12}".format(
            r['ticker'], r['train_samples'], r['test_samples'], r['accuracy'], oos
        ))
