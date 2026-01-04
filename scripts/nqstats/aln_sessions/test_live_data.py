"""
Live Data ML Prediction Testing
=================================
Tests the trained ML model against live data from storage parquet files.

Workflow:
1. Load live OHLC data
2. Extract session ranges (Asia, London, NY1)
3. Calculate features for ML model
4. Make predictions
5. Compare to actual outcome
"""

import pandas as pd
import numpy as np
import joblib
from pathlib import Path
from datetime import datetime, timedelta
import pytz

# --- CONFIG ---
DATA_DIR = Path(__file__).parent.parent.parent.parent / "data"
MODEL_DIR = DATA_DIR / "ml_models"

# Session times in ET
SESSIONS = {
    'Asia': {'start': 18, 'end': 2},  # 18:00 - 02:00 (crosses midnight)
    'London': {'start': 3, 'end': 8},  # 03:00 - 08:00
    'NY1': {'start': 9, 'end': 12},  # 09:00 - 12:00 (approx, starts 9:30)
}

ET = pytz.timezone('America/New_York')


def load_live_data(ticker: str = 'NQ'):
    """Load live storage parquet file."""
    # Map ticker to file
    file_map = {
        'NQ': 'live_storage_-NQ.parquet',
        'ES': 'live_storage_-ES.parquet',
    }
    
    file_path = DATA_DIR / file_map.get(ticker, f'live_storage_{ticker}.parquet')
    
    if not file_path.exists():
        print(f"⚠️ File not found: {file_path}")
        return None
    
    df = pd.read_parquet(file_path)
    
    # Convert timestamp to datetime
    if 'timestamp' in df.columns:
        df['datetime'] = pd.to_datetime(df['timestamp'])
    else:
        df['datetime'] = pd.to_datetime(df['time'], unit='ms')
    
    df = df.set_index('datetime')
    
    return df


def extract_session_ranges(df: pd.DataFrame):
    """Extract session high/low from OHLC data."""
    # Group by date
    df['date'] = df.index.date
    
    # Get unique dates
    dates = df['date'].unique()
    
    sessions_by_date = {}
    
    for date in dates:
        day_data = df[df['date'] == date]
        
        sessions_by_date[str(date)] = {}
        
        for session, times in SESSIONS.items():
            start_h = times['start']
            end_h = times['end']
            
            if session == 'Asia':
                # Asia crosses midnight - need to handle differently
                # Use previous day's evening + current day's early morning
                session_mask = (day_data.index.hour >= 18) | (day_data.index.hour < 2)
            else:
                session_mask = (day_data.index.hour >= start_h) & (day_data.index.hour < end_h)
            
            session_data = day_data[session_mask]
            
            if len(session_data) > 0:
                sessions_by_date[str(date)][session] = {
                    'range_high': session_data['high'].max(),
                    'range_low': session_data['low'].min(),
                    'open': session_data['open'].iloc[0],
                    'close': session_data['close'].iloc[-1],
                }
    
    return sessions_by_date


def classify_aln(asia: dict, london: dict) -> str:
    """Classify ALN pattern."""
    if not asia or not london:
        return 'Unknown'
    
    asia_h = asia.get('range_high')
    asia_l = asia.get('range_low')
    london_h = london.get('range_high')
    london_l = london.get('range_low')
    
    if None in (asia_h, asia_l, london_h, london_l):
        return 'Unknown'
    
    if london_h > asia_h and london_l < asia_l:
        return 'LEA'
    if london_h > asia_h and london_l >= asia_l:
        return 'LPEU'
    if london_l < asia_l and london_h <= asia_h:
        return 'LPED'
    return 'AEL'


def create_features_from_live(sessions_by_date: dict):
    """Create feature matrix from live session data."""
    rows = []
    dates = sorted(sessions_by_date.keys())
    
    for i, date in enumerate(dates):
        sessions = sessions_by_date[date]
        asia = sessions.get('Asia')
        london = sessions.get('London')
        ny1 = sessions.get('NY1')
        
        if not asia or not london:
            continue
        
        # Previous day
        prev_date = dates[i-1] if i > 0 else None
        prev_sessions = sessions_by_date.get(prev_date, {}) if prev_date else {}
        
        row = {'date': date}
        
        # ALN Pattern
        aln = classify_aln(asia, london)
        row['aln'] = aln
        
        # Broken Status (simplified - check if London broke Asia range)
        row['asia_broken'] = 1 if (london['range_high'] > asia['range_high'] or london['range_low'] < asia['range_low']) else 0
        row['london_broken'] = 0  # Can't know until NY1 happens
        
        # Session Status (simplified)
        row['asia_long'] = 1 if asia['close'] > asia['open'] else 0
        row['asia_short'] = 1 if asia['close'] < asia['open'] else 0
        row['london_long'] = 1 if london['close'] > london['open'] else 0
        row['london_short'] = 1 if london['close'] < london['open'] else 0
        
        # Gap
        prev_ny1 = prev_sessions.get('NY1', {})
        if prev_ny1:
            row['gap_pts'] = london['open'] - prev_ny1.get('close', london['open'])
        else:
            row['gap_pts'] = 0
        
        row['gap_up'] = 1 if row['gap_pts'] > 10 else 0
        row['gap_down'] = 1 if row['gap_pts'] < -10 else 0
        
        # Prior day features
        row['prev_classic_buy'] = 0  # Would need HOD/LOD data
        row['prev_classic_sell'] = 0
        
        # Opening Range position
        row['or_vs_asia'] = 1 if london['open'] > (asia['range_high'] + asia['range_low']) / 2 else -1
        
        # Day of week
        try:
            dt = datetime.strptime(date, '%Y-%m-%d')
            row['day_of_week'] = dt.weekday()
        except:
            row['day_of_week'] = -1
        
        # London expansion
        asia_range = asia['range_high'] - asia['range_low']
        london_range = london['range_high'] - london['range_low']
        row['london_expansion'] = london_range / asia_range if asia_range > 0 else 1
        
        # Prior day range (approximation)
        row['prev_day_range'] = 0  # Would need historical data
        
        # VIX (default)
        row['vix_level'] = 20
        row['vix_high'] = 0
        row['vix_low'] = 0
        
        # Actual NY1 outcome (if available)
        if ny1:
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


def make_predictions(df: pd.DataFrame, ticker: str = 'NQ1'):
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
    df['aln_encoded'] = df['aln'].apply(lambda x: 0 if x not in le_aln.classes_ else le_aln.transform([x])[0])
    
    # Get available features
    available_cols = [c for c in feature_cols if c in df.columns]
    
    X = df[available_cols].values
    X_scaled = scaler.transform(X)
    
    predictions = model.predict(X_scaled)
    probas = model.predict_proba(X_scaled)
    
    df['prediction'] = predictions
    df['confidence'] = probas.max(axis=1)
    
    return df


def evaluate_predictions(df: pd.DataFrame):
    """Evaluate predictions against actual outcomes."""
    print("\n" + "="*60)
    print("LIVE DATA PREDICTION RESULTS")
    print("="*60)
    
    # Filter to rows with actual outcomes
    evaluated = df[df['actual'].notna()].copy()
    
    if len(evaluated) == 0:
        print("⚠️ No rows with actual outcomes to evaluate")
        return
    
    correct = (evaluated['prediction'] == evaluated['actual']).sum()
    total = len(evaluated)
    accuracy = correct / total if total > 0 else 0
    
    print(f"\nSamples: {total}")
    print(f"Correct: {correct}")
    print(f"Accuracy: {accuracy:.1%}")
    
    print("\n--- Prediction vs Actual ---")
    print(pd.crosstab(evaluated['prediction'], evaluated['actual']))
    
    print("\n--- Detail ---")
    for _, row in evaluated.iterrows():
        match = "✅" if row['prediction'] == row['actual'] else "❌"
        print(f"{row['date']}: Pred={row['prediction']:7} Actual={row['actual']:7} Conf={row['confidence']:.1%} {match}")


if __name__ == "__main__":
    print("="*60)
    print("LIVE DATA ML PREDICTION TEST")
    print("="*60)
    
    # Load NQ live data
    print("\nLoading NQ live data...")
    df_live = load_live_data('NQ')
    
    if df_live is None or len(df_live) == 0:
        print("No live data available")
        exit(1)
    
    print(f"Loaded {len(df_live)} bars")
    print(f"Date range: {df_live.index.min()} to {df_live.index.max()}")
    
    # Extract sessions
    print("\nExtracting session ranges...")
    sessions = extract_session_ranges(df_live)
    print(f"Found {len(sessions)} trading days")
    
    # Create features
    print("\nCreating features...")
    df_features = create_features_from_live(sessions)
    print(f"Created {len(df_features)} feature rows")
    
    # Make predictions
    print("\nMaking predictions...")
    df_predictions = make_predictions(df_features, 'NQ1')
    
    if df_predictions is not None:
        # Evaluate
        evaluate_predictions(df_predictions)
        
        # Show all predictions
        print("\n--- All Predictions ---")
        for _, row in df_predictions.iterrows():
            print(f"{row['date']}: ALN={row['aln']:5} Gap={row['gap_pts']:+6.1f} → {row['prediction']:7} ({row['confidence']:.0%})")
