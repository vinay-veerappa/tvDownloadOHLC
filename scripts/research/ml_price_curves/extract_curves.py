"""
ML Price Curve Extraction & Analysis
======================================
Phase 1: Extract, normalize, and analyze price curves from 1-minute data.

Sessions:
- NY AM: 09:30 - 12:00 ET (150 minutes)
- NY PM: 12:00 - 16:00 ET (240 minutes)

Output:
- Normalized price curves (% from session open)
- Curve metrics (high%, low%, timing)
- Feature matrix for ML
"""

import pandas as pd
import numpy as np
import json
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

# Config
DATA_DIR = Path(__file__).parent.parent.parent.parent / "data"
OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

TICKER = "NQ1"

# Session definitions (ET)
SESSIONS = {
    'NY_AM': {'start_hour': 9, 'start_min': 30, 'end_hour': 12, 'end_min': 0, 'duration_min': 150},
    'NY_PM': {'start_hour': 12, 'start_min': 0, 'end_hour': 16, 'end_min': 0, 'duration_min': 240},
}


def load_1m_data(ticker: str):
    """Load 1-minute OHLC data."""
    file_path = DATA_DIR / f"{ticker}_1m.parquet"
    
    if not file_path.exists():
        print(f"⚠️ File not found: {file_path}")
        return None
    
    df = pd.read_parquet(file_path)
    
    # Convert timestamp to datetime in ET
    if 'time' in df.columns:
        df['datetime'] = pd.to_datetime(df['time'], unit='s').dt.tz_localize('UTC').dt.tz_convert('US/Eastern')
        df = df.set_index('datetime')
    
    return df


def load_profiler_data(ticker: str):
    """Load profiler JSON for session metadata."""
    file_path = DATA_DIR / f"{ticker}_profiler.json"
    
    with open(file_path) as f:
        data = json.load(f)
    
    # Group by date
    by_date = defaultdict(dict)
    for record in data:
        by_date[record['date']][record['session']] = record
    
    return by_date


def extract_session_curves_fast(df: pd.DataFrame, session_name: str, profiler_data: dict):
    """
    OPTIMIZED: Extract normalized price curves using numpy arrays.
    Much faster than pandas datetime comparisons.
    """
    sess_config = SESSIONS[session_name]
    
    # Convert to numpy for speed
    np_high = df['high'].values
    np_low = df['low'].values
    np_open = df['open'].values
    np_close = df['close'].values
    
    # Get hour/minute as integers for fast filtering
    df_idx = df.index
    np_hour = df_idx.hour.values
    np_minute = df_idx.minute.values
    np_date = df_idx.date
    
    curves = []
    metrics = []
    
    # Get unique dates
    unique_dates = np.unique(np_date)
    
    print(f"  Processing {len(unique_dates)} unique dates...")
    
    for i, date in enumerate(unique_dates):
        if i % 500 == 0:
            print(f"    Progress: {i}/{len(unique_dates)}")
        
        date_str = str(date)
        
        # Fast date mask using numpy
        date_mask = np_date == date
        
        # Session time mask
        start_h, start_m = sess_config['start_hour'], sess_config['start_min']
        end_h, end_m = sess_config['end_hour'], sess_config['end_min']
        
        # Combined mask for session
        if start_m == 0:
            time_mask = (np_hour >= start_h) & (np_hour < end_h)
        else:
            # Handle 9:30 start
            time_mask = ((np_hour == start_h) & (np_minute >= start_m)) | \
                        ((np_hour > start_h) & (np_hour < end_h))
        
        session_mask = date_mask & time_mask
        
        if session_mask.sum() < 10:
            continue
        
        # Extract session data
        sess_high = np_high[session_mask]
        sess_low = np_low[session_mask]
        sess_open = np_open[session_mask]
        sess_close = np_close[session_mask]
        sess_minutes = (np_hour[session_mask] - start_h) * 60 + np_minute[session_mask] - start_m
        
        session_open_price = sess_open[0]
        
        if session_open_price <= 0:
            continue
        
        # Normalize to %
        high_pct = (sess_high - session_open_price) / session_open_price * 100
        low_pct = (sess_low - session_open_price) / session_open_price * 100
        close_pct = (sess_close - session_open_price) / session_open_price * 100
        
        # Create standardized curve (resample to duration_min length)
        curve_high = np.zeros(sess_config['duration_min'])
        curve_low = np.zeros(sess_config['duration_min'])
        
        for m in range(sess_config['duration_min']):
            mask_m = sess_minutes == m
            if mask_m.any():
                curve_high[m] = high_pct[mask_m].max()
                curve_low[m] = low_pct[mask_m].min()
            elif m > 0:
                curve_high[m] = curve_high[m-1]
                curve_low[m] = curve_low[m-1]
        
        # Metrics
        session_high_pct = high_pct.max()
        session_low_pct = low_pct.min()
        session_close_pct = close_pct[-1] if len(close_pct) > 0 else 0
        
        high_time = sess_minutes[high_pct.argmax()]
        low_time = sess_minutes[low_pct.argmin()]
        
        # Get profiler features
        profiler_day = profiler_data.get(date_str, {})
        asia = profiler_day.get('Asia', {})
        london = profiler_day.get('London', {})
        
        curves.append({
            'date': date_str,
            'session': session_name,
            'curve_high': curve_high,
            'curve_low': curve_low,
        })
        
        metrics.append({
            'date': date_str,
            'session': session_name,
            'session_open': session_open_price,
            'high_pct': session_high_pct,
            'low_pct': session_low_pct,
            'close_pct': session_close_pct,
            'high_time': high_time,
            'low_time': low_time,
            'asia_broken': 1 if asia.get('broken', False) else 0,
            'london_broken': 1 if london.get('broken', False) else 0,
            'asia_long': 1 if 'Long' in asia.get('status', '') else 0,
            'london_long': 1 if 'Long' in london.get('status', '') else 0,
        })
    
    return curves, metrics


def visualize_curve_samples(curves: list, session_name: str, n_samples: int = 50):
    """Create visualization of sample curves."""
    fig = go.Figure()
    
    if len(curves) == 0:
        return fig
    
    # Take random samples
    sample_indices = np.random.choice(len(curves), min(n_samples, len(curves)), replace=False)
    
    for i in sample_indices:
        curve = curves[i]
        x = list(range(len(curve['curve_high'])))
        
        fig.add_trace(go.Scatter(
            x=x, y=curve['curve_high'],
            mode='lines', line=dict(color='rgba(0,255,0,0.1)', width=1),
            showlegend=False
        ))
        fig.add_trace(go.Scatter(
            x=x, y=curve['curve_low'],
            mode='lines', line=dict(color='rgba(255,0,0,0.1)', width=1),
            showlegend=False
        ))
    
    # Calculate median curves
    all_highs = np.array([c['curve_high'] for c in curves])
    all_lows = np.array([c['curve_low'] for c in curves])
    
    median_high = np.median(all_highs, axis=0)
    median_low = np.median(all_lows, axis=0)
    
    fig.add_trace(go.Scatter(
        x=list(range(len(median_high))), y=median_high,
        mode='lines', line=dict(color='lime', width=3),
        name='Median High'
    ))
    fig.add_trace(go.Scatter(
        x=list(range(len(median_low))), y=median_low,
        mode='lines', line=dict(color='red', width=3),
        name='Median Low'
    ))
    
    fig.add_hline(y=0, line_color='gray', line_dash='dash')
    
    fig.update_layout(
        title=f'{session_name} Price Curves ({len(curves)} sessions)',
        xaxis_title='Minutes from Session Start',
        yaxis_title='% from Open',
        template='plotly_dark',
        height=500
    )
    
    return fig


def analyze_curve_distribution(metrics: list):
    """Analyze distribution of curve metrics."""
    df = pd.DataFrame(metrics)
    
    print(f"\n  Total sessions: {len(df)}")
    print(f"  High % - Mean: {df['high_pct'].mean():.3f}, Std: {df['high_pct'].std():.3f}")
    print(f"  Low %  - Mean: {df['low_pct'].mean():.3f}, Std: {df['low_pct'].std():.3f}")
    print(f"  High Time - Mean: {df['high_time'].mean():.1f} min")
    print(f"  Low Time  - Mean: {df['low_time'].mean():.1f} min")
    
    return df


if __name__ == "__main__":
    print("="*60)
    print("ML PRICE CURVE EXTRACTION (Optimized)")
    print("="*60)
    
    # Load data
    print(f"\nLoading 1-min data for {TICKER}...")
    df = load_1m_data(TICKER)
    print(f"Loaded {len(df)} bars")
    print(f"Date range: {df.index.min()} to {df.index.max()}")
    
    print(f"\nLoading profiler data...")
    profiler = load_profiler_data(TICKER)
    print(f"Loaded {len(profiler)} trading days")
    
    all_curves = {}
    all_metrics = {}
    
    for session_name in ['NY_AM', 'NY_PM']:
        print(f"\n{'='*60}")
        print(f"Extracting {session_name} curves...")
        
        curves, metrics = extract_session_curves_fast(df, session_name, profiler)
        
        print(f"\n  Extracted {len(curves)} valid sessions")
        
        all_curves[session_name] = curves
        all_metrics[session_name] = metrics
        
        # Analyze
        df_metrics = analyze_curve_distribution(metrics)
        
        # Save
        df_metrics.to_csv(OUTPUT_DIR / f'{TICKER}_{session_name}_metrics.csv', index=False)
        print(f"\n  ✅ Metrics saved")
        
        # Visualize
        fig = visualize_curve_samples(curves, session_name, n_samples=100)
        fig.write_html(OUTPUT_DIR / f'{TICKER}_{session_name}_curves.html')
        print(f"  ✅ Chart saved")
    
    # Save curves as numpy arrays
    for session_name, curves in all_curves.items():
        if len(curves) > 0:
            np_highs = np.array([c['curve_high'] for c in curves])
            np_lows = np.array([c['curve_low'] for c in curves])
            dates = [c['date'] for c in curves]
            
            np.savez(
                OUTPUT_DIR / f'{TICKER}_{session_name}_curves.npz',
                highs=np_highs,
                lows=np_lows,
                dates=dates
            )
            print(f"\n✅ {session_name} curves saved: {np_highs.shape}")
    
    print("\n" + "="*60)
    print("PHASE 1 COMPLETE")
    print("="*60)
