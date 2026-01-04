"""
Test ML Model on TradingView OHLC Data
========================================
Tests the trained ML model against TradingView December data.

Data format:
- Columns: time (unix sec), open, high, low, close, Volume
- Time is in UTC, needs conversion to ET
"""

import pandas as pd
import numpy as np
import joblib
from pathlib import Path
from datetime import datetime
import pytz

# --- CONFIG ---
DATA_DIR = Path(__file__).parent.parent.parent.parent / "data"
TV_DIR = DATA_DIR / "TV_OHLC"
MODEL_DIR = DATA_DIR / "ml_models"

# Ticker file mapping
TICKER_FILES = {
    'NQ1': 'CME_MINI_NQ1!, 1_23f45.csv',
    'ES1': 'CME_MINI_ES1!, 1_2e5eb.csv',
    'RTY1': 'CME_MINI_RTY1!, 1_c377c.csv',
    'YM1': 'CBOT_MINI_YM1!, 1_7893b.csv',
}

# Session times in ET (Eastern Time)
SESSIONS_ET = {
    'Asia': {'start': 18, 'end': 2},  # 18:00 - 02:00 (crosses midnight)
    'London': {'start': 3, 'end': 8},  # 03:00 - 08:00
    'NY1': {'start': 9, 'end': 12},  # 09:30 - 12:00
}

UTC = pytz.UTC
ET = pytz.timezone('America/New_York')


def load_tv_data(ticker: str):
    """Load TradingView CSV data."""
    filename = TICKER_FILES.get(ticker)
    if not filename:
        print(f"⚠️ Unknown ticker: {ticker}")
        return None
    
    file_path = TV_DIR / filename
    if not file_path.exists():
        print(f"⚠️ File not found: {file_path}")
        return None
    
    df = pd.read_csv(file_path)
    
    # Convert Unix timestamp to datetime in ET
    df['datetime_utc'] = pd.to_datetime(df['time'], unit='s', utc=True)
    df['datetime_et'] = df['datetime_utc'].dt.tz_convert(ET)
    
    df = df.set_index('datetime_et')
    
    return df


def extract_sessions(df: pd.DataFrame):
    """Extract session ranges from OHLC data."""
    # Add date and hour columns (in ET)
    df['date'] = df.index.date
    df['hour'] = df.index.hour
    
    dates = df['date'].unique()
    sessions_by_date = {}
    
    for date in dates:
        day_data = df[df['date'] == date]
        sessions_by_date[str(date)] = {}
        
        # Asia session (18:00 - 02:00)
        # Need to get previous day's evening + this day's early morning
        asia_evening = df[(df['date'] == date) & (df['hour'] >= 18)]
        prev_date = date - pd.Timedelta(days=1)
        asia_morning = df[(df['date'] == date) & (df['hour'] < 2)]
        asia_data = pd.concat([asia_evening, asia_morning])
        
        if len(asia_data) > 0:
            sessions_by_date[str(date)]['Asia'] = {
                'range_high': asia_data['high'].max(),
                'range_low': asia_data['low'].min(),
                'open': asia_data['open'].iloc[0] if len(asia_data) > 0 else None,
                'close': asia_data['close'].iloc[-1] if len(asia_data) > 0 else None,
            }
        
        # London session (03:00 - 08:00)
        london_data = day_data[(day_data['hour'] >= 3) & (day_data['hour'] < 8)]
        if len(london_data) > 0:
            sessions_by_date[str(date)]['London'] = {
                'range_high': london_data['high'].max(),
                'range_low': london_data['low'].min(),
                'open': london_data['open'].iloc[0],
                'close': london_data['close'].iloc[-1],
            }
        
        # NY1 session (09:00 - 12:00)
        ny1_data = day_data[(day_data['hour'] >= 9) & (day_data['hour'] < 12)]
        if len(ny1_data) > 0:
            sessions_by_date[str(date)]['NY1'] = {
                'range_high': ny1_data['high'].max(),
                'range_low': ny1_data['low'].min(),
                'open': ny1_data['open'].iloc[0],
                'close': ny1_data['close'].iloc[-1],
            }
    
    return sessions_by_date


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


def create_features(sessions_by_date: dict):
    """Create feature matrix from session data."""
    rows = []
    dates = sorted(sessions_by_date.keys())
    
    for i, date in enumerate(dates):
        sessions = sessions_by_date[date]
        asia = sessions.get('Asia')
        london = sessions.get('London')
        ny1 = sessions.get('NY1')
        
        if not asia or not london:
            continue
        
        prev_date = dates[i-1] if i > 0 else None
        prev_sessions = sessions_by_date.get(prev_date, {}) if prev_date else {}
        
        row = {'date': date}
        
        # ALN Pattern
        row['aln'] = classify_aln(asia, london)
        
        # Broken Status
        row['asia_broken'] = 1 if (london['range_high'] > asia['range_high'] or london['range_low'] < asia['range_low']) else 0
        row['london_broken'] = 0
        
        # Session Status
        if asia.get('open') and asia.get('close'):
            row['asia_long'] = 1 if asia['close'] > asia['open'] else 0
            row['asia_short'] = 1 if asia['close'] < asia['open'] else 0
        else:
            row['asia_long'] = 0
            row['asia_short'] = 0
        
        if london.get('open') and london.get('close'):
            row['london_long'] = 1 if london['close'] > london['open'] else 0
            row['london_short'] = 1 if london['close'] < london['open'] else 0
        else:
            row['london_long'] = 0
            row['london_short'] = 0
        
        # Gap
        prev_ny1 = prev_sessions.get('NY1', {})
        if prev_ny1 and prev_ny1.get('close') and london.get('open'):
            row['gap_pts'] = london['open'] - prev_ny1['close']
        else:
            row['gap_pts'] = 0
        
        row['gap_up'] = 1 if row['gap_pts'] > 10 else 0
        row['gap_down'] = 1 if row['gap_pts'] < -10 else 0
        
        # Other features
        row['prev_classic_buy'] = 0
        row['prev_classic_sell'] = 0
        
        asia_mid = (asia['range_high'] + asia['range_low']) / 2 if asia.get('range_high') else 0
        row['or_vs_asia'] = 1 if london.get('open', 0) > asia_mid else -1
        
        try:
            dt = datetime.strptime(date, '%Y-%m-%d')
            row['day_of_week'] = dt.weekday()
        except:
            row['day_of_week'] = -1
        
        # London expansion
        asia_range = asia['range_high'] - asia['range_low'] if asia.get('range_high') else 1
        london_range = london['range_high'] - london['range_low'] if london.get('range_high') else 1
        row['london_expansion'] = london_range / asia_range if asia_range > 0 else 1
        
        row['prev_day_range'] = 0
        row['vix_level'] = 20
        row['vix_high'] = 0
        row['vix_low'] = 0
        
        # Actual NY1 outcome
        if ny1 and ny1.get('open') and ny1.get('close'):
            if ny1['close'] > ny1['open']:
                row['actual'] = 'LONG'
            elif ny1['close'] < ny1['open']:
                row['actual'] = 'SHORT'
            else:
                row['actual'] = 'NEUTRAL'
        else:
            row['actual'] = None
        
        rows.append(row)
    
    return pd.DataFrame(rows)


def make_predictions(df: pd.DataFrame, ticker: str):
    """Load model and make predictions."""
    model_path = MODEL_DIR / f"{ticker}_bias_model.pkl"
    
    if not model_path.exists():
        print(f"⚠️ Model not found: {model_path}")
        return None
    
    model_data = joblib.load(model_path)
    model = model_data['model']
    scaler = model_data['scaler']
    feature_cols = model_data['features']
    le_aln = model_data['le_aln']
    
    # Encode ALN
    df['aln_encoded'] = df['aln'].apply(
        lambda x: le_aln.transform([x])[0] if x in le_aln.classes_ else 0
    )
    
    available_cols = [c for c in feature_cols if c in df.columns]
    
    X = df[available_cols].values
    X_scaled = scaler.transform(X)
    
    predictions = model.predict(X_scaled)
    probas = model.predict_proba(X_scaled)
    
    df['prediction'] = predictions
    df['confidence'] = probas.max(axis=1)
    
    return df


def evaluate(df: pd.DataFrame, ticker: str):
    """Evaluate predictions against actual outcomes."""
    print(f"\n{'='*60}")
    print(f"RESULTS FOR: {ticker}")
    print(f"{'='*60}")
    
    evaluated = df[df['actual'].notna()].copy()
    
    if len(evaluated) == 0:
        print("⚠️ No rows with actual outcomes")
        return None
    
    correct = (evaluated['prediction'] == evaluated['actual']).sum()
    total = len(evaluated)
    accuracy = correct / total
    
    print(f"Days: {total}")
    print(f"Correct: {correct}")
    print(f"Accuracy: {accuracy:.1%}")
    
    print("\n--- Confusion Matrix ---")
    print(pd.crosstab(evaluated['prediction'], evaluated['actual'], margins=True))
    
    print("\n--- Day-by-Day ---")
    for _, row in evaluated.iterrows():
        match = "✅" if row['prediction'] == row['actual'] else "❌"
        print(f"{row['date']}: ALN={row['aln']:5} Gap={row['gap_pts']:+7.1f} → Pred={row['prediction']:7} Act={row['actual']:7} ({row['confidence']:.0%}) {match}")
    
    return {
        'ticker': ticker,
        'days': total,
        'correct': correct,
        'accuracy': accuracy,
    }


if __name__ == "__main__":
    print("="*70)
    print("TRADINGVIEW DATA ML VALIDATION")
    print("="*70)
    
    all_results = []
    
    for ticker in ['NQ1', 'ES1', 'YM1', 'RTY1']:
        print(f"\nProcessing {ticker}...")
        
        df = load_tv_data(ticker)
        if df is None:
            continue
        
        print(f"Loaded {len(df)} bars")
        print(f"Date range: {df.index.min()} to {df.index.max()}")
        
        sessions = extract_sessions(df)
        print(f"Extracted {len(sessions)} trading days")
        
        features = create_features(sessions)
        if len(features) == 0:
            print("No features created")
            continue
        
        predictions = make_predictions(features, ticker)
        if predictions is None:
            continue
        
        result = evaluate(predictions, ticker)
        if result:
            all_results.append(result)
    
    # Summary
    if all_results:
        print("\n" + "="*70)
        print("CROSS-TICKER SUMMARY")
        print("="*70)
        
        print("\n{:<8} {:>6} {:>8} {:>10}".format("Ticker", "Days", "Correct", "Accuracy"))
        print("-"*35)
        for r in all_results:
            print("{:<8} {:>6} {:>8} {:>9.1%}".format(r['ticker'], r['days'], r['correct'], r['accuracy']))
        
        total_days = sum(r['days'] for r in all_results)
        total_correct = sum(r['correct'] for r in all_results)
        print("-"*35)
        print("{:<8} {:>6} {:>8} {:>9.1%}".format("TOTAL", total_days, total_correct, total_correct/total_days))
