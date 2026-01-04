"""
Multi-Ticker ML Bias Prediction with Enhanced Features
========================================================
Expands the ML model to ES, YM, RTY, NQ with additional features.

New Features:
- VIX levels (if available)
- Prior day range (high - low)
- Prior day close position within range
- London range expansion ratio

Output:
- Cross-ticker model performance
- Trading signal generator
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
from sklearn.metrics import classification_report, accuracy_score
import joblib

# --- CONFIG ---
DATA_DIR = Path(__file__).parent.parent.parent.parent / "data"
TICKERS = ['ES1', 'RTY1', 'YM1', 'NQ1']
MODEL_DIR = DATA_DIR / "ml_models"
MODEL_DIR.mkdir(exist_ok=True)


def load_all_data(ticker: str):
    """Load all relevant data sources for a ticker."""
    profiler_file = DATA_DIR / f"{ticker}_profiler.json"
    hod_lod_file = DATA_DIR / f"{ticker}_daily_hod_lod.json"
    opening_range_file = DATA_DIR / f"{ticker}_opening_range.json"
    
    if not profiler_file.exists():
        print(f"  ⚠️ Missing profiler for {ticker}")
        return {}
    
    with open(profiler_file) as f:
        profiler_data = json.load(f)
    
    hod_lod_data = {}
    if hod_lod_file.exists():
        with open(hod_lod_file) as f:
            hod_lod_data = json.load(f)
    
    or_by_date = {}
    if opening_range_file.exists():
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


def load_vix_data():
    """Load VIX data if available."""
    vix_file = DATA_DIR / "VIX_profiler.json"
    if not vix_file.exists():
        return {}
    
    with open(vix_file) as f:
        vix_data = json.load(f)
    
    vix_by_date = {}
    for record in vix_data:
        if record['session'] == 'NY1':  # Use NY1 session
            vix_by_date[record['date']] = record
    
    return vix_by_date


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


def create_feature_matrix(daily: dict, vix_data: dict = None) -> pd.DataFrame:
    """Create enhanced feature matrix."""
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
        
        row = {'date': date}
        
        # === EXISTING FEATURES ===
        row['aln'] = classify_aln(asia, london)
        row['asia_broken'] = 1 if asia.get('broken', False) else 0
        row['london_broken'] = 1 if london.get('broken', False) else 0
        
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
        
        # Opening Range Position
        if opening_range:
            or_mid = (opening_range.get('high', 0) + opening_range.get('low', 0)) / 2
            asia_mid = (asia.get('range_high', 0) + asia.get('range_low', 0)) / 2
            row['or_vs_asia'] = 1 if or_mid > asia_mid else -1
        else:
            row['or_vs_asia'] = 0
        
        # Day of Week
        try:
            dt = datetime.strptime(date, '%Y-%m-%d')
            row['day_of_week'] = dt.weekday()
        except:
            row['day_of_week'] = -1
        
        # === NEW FEATURES ===
        
        # Prior Day Range
        if prev_hod_lod:
            prev_high = prev_hod_lod.get('daily_high', prev_hod_lod.get('hod_price', 0))
            prev_low = prev_hod_lod.get('daily_low', prev_hod_lod.get('lod_price', 0))
            if prev_high and prev_low:
                row['prev_day_range'] = prev_high - prev_low
            else:
                row['prev_day_range'] = 0
        else:
            row['prev_day_range'] = 0
        
        # London Range Expansion Ratio
        asia_range = asia.get('range_high', 0) - asia.get('range_low', 0)
        london_range = london.get('range_high', 0) - london.get('range_low', 0)
        row['london_expansion'] = london_range / asia_range if asia_range > 0 else 1
        
        # VIX Level
        if vix_data and date in vix_data:
            vix_record = vix_data[date]
            row['vix_level'] = vix_record.get('open', 20)
            row['vix_high'] = 1 if row['vix_level'] > 25 else 0
            row['vix_low'] = 1 if row['vix_level'] < 15 else 0
        else:
            row['vix_level'] = 20  # Default
            row['vix_high'] = 0
            row['vix_low'] = 0
        
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


def train_model(df: pd.DataFrame, ticker: str):
    """Train and evaluate ML model for a ticker."""
    print(f"\n{'='*60}")
    print(f"TRAINING MODEL FOR: {ticker}")
    print(f"{'='*60}")
    print(f"Samples: {len(df)}")
    print(f"Target: {df['target'].value_counts().to_dict()}")
    
    # Encode ALN
    le_aln = LabelEncoder()
    df['aln_encoded'] = le_aln.fit_transform(df['aln'])
    
    # Features
    feature_cols = [
        'aln_encoded', 'asia_broken', 'london_broken',
        'asia_long', 'asia_short', 'london_long', 'london_short',
        'gap_pts', 'gap_up', 'gap_down',
        'prev_classic_buy', 'prev_classic_sell',
        'or_vs_asia', 'day_of_week',
        'prev_day_range', 'london_expansion',
        'vix_level', 'vix_high', 'vix_low'
    ]
    
    # Filter available features
    available_cols = [c for c in feature_cols if c in df.columns]
    
    X = df[available_cols].values
    y = df['target'].values
    
    # Scale features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # Split
    X_train, X_test, y_train, y_test = train_test_split(X_scaled, y, test_size=0.2, random_state=42)
    
    # Train Gradient Boosting (best from previous)
    model = GradientBoostingClassifier(n_estimators=100, max_depth=5, random_state=42)
    model.fit(X_train, y_train)
    
    y_pred = model.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    
    print(f"\nAccuracy: {acc:.2%}")
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred))
    
    # Feature importance
    print("\nTop 5 Features:")
    importances = list(zip(available_cols, model.feature_importances_))
    importances.sort(key=lambda x: x[1], reverse=True)
    for feat, imp in importances[:5]:
        print(f"  {feat}: {imp:.3f}")
    
    # Save model
    model_path = MODEL_DIR / f"{ticker}_bias_model.pkl"
    joblib.dump({'model': model, 'scaler': scaler, 'features': available_cols, 'le_aln': le_aln}, model_path)
    print(f"\n✅ Model saved: {model_path}")
    
    return {
        'ticker': ticker,
        'samples': len(df),
        'accuracy': acc,
        'top_features': importances[:5]
    }


def generate_trading_signals(model_data: dict, df: pd.DataFrame, ticker: str):
    """Generate trading signals for the most recent data."""
    model = model_data['model']
    scaler = model_data['scaler']
    feature_cols = model_data['features']
    le_aln = model_data['le_aln']
    
    # Get last 5 days
    recent = df.tail(5).copy()
    recent['aln_encoded'] = le_aln.transform(recent['aln'])
    
    X = recent[feature_cols].values
    X_scaled = scaler.transform(X)
    
    predictions = model.predict(X_scaled)
    probas = model.predict_proba(X_scaled)
    
    print(f"\n{'='*60}")
    print(f"TRADING SIGNALS: {ticker}")
    print(f"{'='*60}")
    
    classes = model.classes_
    for i, (idx, row) in enumerate(recent.iterrows()):
        print(f"\nDate: {row['date']}")
        print(f"  ALN: {row['aln']}, Broken: Asia={row['asia_broken']}, London={row['london_broken']}")
        print(f"  Gap: {row['gap_pts']:.1f} pts")
        print(f"  Prediction: {predictions[i]}")
        print(f"  Confidence: {', '.join([f'{c}={p:.1%}' for c, p in zip(classes, probas[i])])}")


if __name__ == "__main__":
    print("="*70)
    print("MULTI-TICKER ML BIAS PREDICTION")
    print("="*70)
    
    # Load VIX data
    print("\nLoading VIX data...")
    vix_data = load_vix_data()
    print(f"VIX data: {len(vix_data)} days")
    
    all_results = []
    
    for ticker in TICKERS:
        print(f"\n{'='*70}")
        print(f"Processing {ticker}...")
        
        daily = load_all_data(ticker)
        if not daily:
            continue
        
        print(f"Loaded {len(daily)} trading days")
        
        df = create_feature_matrix(daily, vix_data)
        if len(df) < 100:
            print(f"  ⚠️ Insufficient data for {ticker}")
            continue
        
        result = train_model(df, ticker)
        all_results.append(result)
        
        # Generate signals
        model_path = MODEL_DIR / f"{ticker}_bias_model.pkl"
        model_data = joblib.load(model_path)
        generate_trading_signals(model_data, df, ticker)
    
    # Summary
    print("\n" + "="*70)
    print("CROSS-TICKER SUMMARY")
    print("="*70)
    
    print("\n{:<8} {:>10} {:>12}".format("Ticker", "Samples", "Accuracy"))
    print("-"*35)
    for r in all_results:
        print("{:<8} {:>10} {:>11.1%}".format(r['ticker'], r['samples'], r['accuracy']))
