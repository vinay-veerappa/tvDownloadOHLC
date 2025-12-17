
import asyncio
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from api.services.profiler_service import ProfilerService
from datetime import timedelta
import sys
import os
import json

# Add project root to sys.path
sys.path.append(os.getcwd())

async def generate_charts():
    ticker = "RTY1"
    target_session = "Daily"
    # Filter for NO specific outcome to get general volatility model
    outcome_name = "Any" 
    
    print(f"Fetching data for {ticker} {target_session}...")
    
    # 1. Fetch Raw Sessions
    stats_result = ProfilerService.analyze_profiler_stats(ticker, days=5000) # Use 5000 days for full stats (matches API)
    if "error" in stats_result:
        print(f"Error: {stats_result['error']}")
        return

    all_sessions = stats_result.get("sessions", [])
    
    # Filter for target session
    if target_session == 'Daily':
        # Construct synthetic Daily sessions (Start 18:00 -> End 16:00 next day)
        sessions = []
        for s in all_sessions:
            if s['session'] == 'Asia':
                # Asia start is 18:00. We want to capture 22 hours from this start.
                sessions.append({
                    'start_time': s['start_time'],
                    'open': s['open'],
                    'session': 'Daily',
                    'date': s['date']
                })
        print(f"Constructed {len(sessions)} synthetic Daily sessions.")
    else:
        sessions = [s for s in all_sessions if s['session'] == target_session]
    
    print(f"Found {len(sessions)} sessions.")
    
    # 2. Define Custom Aggregation Function with Percentiles
    def calculate_bands(bucket_minutes):
        df = ProfilerService._cache.get(ticker)
        if df is None:
             from api.services.data_loader import DATA_DIR
             file_path = DATA_DIR / f"{ticker}_1m.parquet"
             df = pd.read_parquet(file_path)
             df = df.sort_index()
             if df.index.tz is None: df = df.tz_localize('UTC').tz_convert('US/Eastern')
             else: df = df.tz_convert('US/Eastern')
             ProfilerService._cache[ticker] = df

        duration_hours = 22.0 if target_session == 'Daily' else 7.0
        
        # Valid Starts
        tz = df.index.tz
        start_ts_list = []
        for s in sessions:
            ts = pd.Timestamp(s['start_time'])
            if ts.tz is None and tz is not None: ts = ts.tz_localize(tz)
            elif ts.tz != tz: ts = ts.tz_convert(tz)
            start_ts_list.append(ts)

        start_locs = df.index.searchsorted(start_ts_list)
        end_ts_list = [ts + pd.Timedelta(hours=duration_hours) for ts in start_ts_list]
        end_locs = df.index.searchsorted(end_ts_list)
        
        all_time_idxs = []
        all_norm_highs = []
        all_norm_lows = []
        
        np_high = df['high'].values
        np_low = df['low'].values
        np_index = df.index.values
        
        for i, (start_idx, end_idx) in enumerate(zip(start_locs, end_locs)):
            if start_idx >= len(df) or end_idx > len(df) or start_idx >= end_idx: continue
            
            sess_open = sessions[i]['open']
            if sess_open <= 0: continue

            chunk_ts = np_index[start_idx:end_idx]
            if len(chunk_ts) == 0: continue
            base_ts = chunk_ts[0]
            
            time_deltas_m = (chunk_ts - base_ts).astype('timedelta64[m]').astype(int)
            
            chunk_high = np_high[start_idx:end_idx]
            chunk_low = np_low[start_idx:end_idx]
            
            norm_high = ((chunk_high - sess_open) / sess_open) * 100
            norm_low = ((chunk_low - sess_open) / sess_open) * 100
            
            all_time_idxs.append(time_deltas_m)
            all_norm_highs.append(norm_high)
            all_norm_lows.append(norm_low)
            
        if not all_time_idxs: return None
        
        combined_idx = np.concatenate(all_time_idxs)
        combined_high = np.concatenate(all_norm_highs)
        combined_low = np.concatenate(all_norm_lows)
        
        # Bucketing
        if bucket_minutes > 1:
            combined_idx = (combined_idx // bucket_minutes) * bucket_minutes

        combined = pd.DataFrame({
            'time_idx': combined_idx,
            'norm_high': combined_high,
            'norm_low': combined_low
        })
        
        # Aggregation with Custom Percentiles
        def p99(x): return x.quantile(0.99)
        def p95(x): return x.quantile(0.95)
        def p90(x): return x.quantile(0.90)
        def p75(x): return x.quantile(0.75)
        
        def p25(x): return x.quantile(0.25)
        def p10(x): return x.quantile(0.10)
        def p05(x): return x.quantile(0.05)
        def p01(x): return x.quantile(0.01)

        grouped = combined.groupby('time_idx')
        stats = grouped.agg({
            'norm_high': ['median', p99, p95, p90, p75],
            'norm_low':  ['median', p01, p05, p10, p25]
        })
        
        return stats

    print("Calculating 5m stats (Fan Chart)...")
    stats_5m = calculate_bands(5)
    
    if stats_5m is not None:
        # Create Fan Chart
        fig = make_subplots(rows=1, cols=1) # Single chart for Highs and Lows
        
        x_vals = stats_5m.index
        # Convert time_idx to readable Time Strings
        # Start is 18:00
        start_time = pd.Timestamp("2000-01-01 18:00:00")
        time_labels = [(start_time + pd.Timedelta(minutes=int(m))).strftime('%H:%M') for m in x_vals]
        
        # High Paths
        med_h = stats_5m[('norm_high', 'median')]
        p75_h = stats_5m[('norm_high', 'p75')]
        p90_h = stats_5m[('norm_high', 'p90')]
        p95_h = stats_5m[('norm_high', 'p95')]
        p99_h = stats_5m[('norm_high', 'p99')]
        
        # Low Paths
        med_l = stats_5m[('norm_low', 'median')]
        p25_l = stats_5m[('norm_low', 'p25')]
        p10_l = stats_5m[('norm_low', 'p10')]
        p05_l = stats_5m[('norm_low', 'p05')]
        p01_l = stats_5m[('norm_low', 'p01')]
        
        # Plotting - Fan Style
        
        # 99% / 1% (Extreme) - Dotted
        fig.add_trace(go.Scatter(x=time_labels, y=p99_h, mode='lines', name='99% High', line=dict(color='green', width=1, dash='dot')))
        fig.add_trace(go.Scatter(x=time_labels, y=p01_l, mode='lines', name='1% Low', line=dict(color='red', width=1, dash='dot')))

        # 95% / 5% - Dashed
        fig.add_trace(go.Scatter(x=time_labels, y=p95_h, mode='lines', name='95% High', line=dict(color='rgba(0, 255, 0, 0.4)', width=1.5, dash='dash')))
        fig.add_trace(go.Scatter(x=time_labels, y=p05_l, mode='lines', name='5% Low', line=dict(color='rgba(255, 0, 0, 0.4)', width=1.5, dash='dash')))

        # 90% / 10% - Solid Thin
        fig.add_trace(go.Scatter(x=time_labels, y=p90_h, mode='lines', name='90% High', line=dict(color='rgba(0, 200, 0, 0.6)', width=2)))
        fig.add_trace(go.Scatter(x=time_labels, y=p10_l, mode='lines', name='10% Low', line=dict(color='rgba(200, 0, 0, 0.6)', width=2)))

        # 75% / 25% - Solid Medium
        fig.add_trace(go.Scatter(x=time_labels, y=p75_h, mode='lines', name='75% High', line=dict(color='darkgreen', width=2.5)))
        fig.add_trace(go.Scatter(x=time_labels, y=p25_l, mode='lines', name='25% Low', line=dict(color='darkred', width=2.5)))

        # Medians (Center) - Solid Thick
        fig.add_trace(go.Scatter(x=time_labels, y=med_h, mode='lines', name='Median High', line=dict(color='lime', width=4)))
        fig.add_trace(go.Scatter(x=time_labels, y=med_l, mode='lines', name='Median Low', line=dict(color='orange', width=4)))
        
        fig.update_layout(
            title=f"{ticker} Historical Path Probability Cone (Fan Chart) - 99% Percentile Cutoff",
            xaxis_title="Time (EST)",
            yaxis_title="Change from Open (%)",
            template="plotly_dark",
            height=800,
            width=1600
        )
        
        output_path = "reports/price_model_fan_chart_v2.html"
        os.makedirs("reports", exist_ok=True)
        fig.write_html(output_path)
        print(f"Fan Chart saved to {output_path}")

if __name__ == "__main__":
    asyncio.run(generate_charts())
