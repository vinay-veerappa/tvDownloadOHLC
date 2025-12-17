
import pandas as pd
import numpy as np
import os
import plotly.graph_objects as go
from datetime import time, timedelta
import shutil

# --- COPIED LOGIC (Ensure consistency with compare script) ---
def run_trade_logic_for_chart(window, r_high, r_low, fvg_dir, fvg_entry, fvg_sl, fvg_inv, tp_pct, hard_exit):
    # Simplified to just run Option B (Market) or A (Limit) for visualization
    # Let's visualize OPTION B (Market) as default unless limit specified?
    # User likely wants to see the "FVG" trade. Let's try Option B first as it has more trades.
    pos = fvg_dir
    entry = window.iloc[0]['open'] # Market Entry 
    sl = fvg_sl
    tp = entry * (1 + tp_pct) if pos == 'LONG' else entry * (1 - tp_pct)
    entry_t = window.index[0]
    
    trade_events = [{'time': entry_t, 'price': entry, 'type': 'ENTRY'}]

    for t, row in window.iterrows():
        # Exit Checks
        exit_price = 0; reason = None
        if t.time() >= hard_exit: exit_price = row['close']; reason = "TIME"
        elif check_inv(pos, row['close'], fvg_inv): exit_price = row['close']; reason = "FVG_INV" # Invalidation
        elif check_sl(pos, row, sl): exit_price = sl; reason = "SL"
        elif check_tp(pos, row, tp): exit_price = tp; reason = "TP"
        
        if reason:
            trade_events.append({'time': t, 'price': exit_price, 'type': 'EXIT', 'reason': reason})
            return trade_events
            
    return trade_events

def check_inv(pos, close, inv_level):
    if pos == 'LONG': return close < inv_level
    else: return close > inv_level
def check_sl(pos, row, sl): return (row['low'] <= sl) if pos == 'LONG' else (row['high'] >= sl)
def check_tp(pos, row, tp): return (row['high'] >= tp) if pos == 'LONG' else (row['low'] <= tp)

def generate_charts(ticker="NQ1", days=60, max_charts=15):
    print(f"Generating Marked FVG Charts for {ticker} (Limit {max_charts})...")
    
    FVG_SCAN_MINS = 5; HUGE_DISP_PCT = 0.0020; TP_PCT = 0.0015; HARD_EXIT = time(10, 0)
    OUT_DIR = "reports/930_charts"
    if os.path.exists(OUT_DIR): shutil.rmtree(OUT_DIR)
    os.makedirs(OUT_DIR)

    # Load Data
    data_path = f"data/{ticker}_1m.parquet"
    df = pd.read_parquet(data_path)
    if not isinstance(df.index, pd.DatetimeIndex):
        if 'time' in df.columns: df['datetime'] = pd.to_datetime(df['time'], unit='s' if df['time'].iloc[0] > 1e10 else 'ms')
        elif 'datetime' in df.columns: df['datetime'] = pd.to_datetime(df['datetime'])
        df = df.set_index('datetime')
    df = df.sort_index(); 
    if df.index.tz is None: pass 
    else: df = df.tz_convert('US/Eastern')

    # Filter
    start_date = df.index[-1] - pd.Timedelta(days=days)
    df = df[df.index >= start_date]
    dates = df.index.normalize().unique()

    chart_count = 0
    for d in dates:
        if chart_count >= max_charts: break
        day_data = df[df.index.normalize() == d]
        t930 = d + pd.Timedelta(hours=9, minutes=30)
        c930 = day_data[day_data.index == t930]
        if c930.empty: continue
        
        r_high = c930['high'].iloc[0]; r_low = c930['low'].iloc[0]; r_open = c930['open'].iloc[0]; r_close = c930['close'].iloc[0]
        
        # FVG IDENTIFICATION (Same as compare script)
        fvg_dir = None; fvg_top = 0; fvg_bot = 0; fvg_time = None; fvg_inv = 0; mode = None
        
        if abs(r_close - r_open) / r_open > HUGE_DISP_PCT:
            mode = 'HUGE_CANDLE'; fvg_time = t930
            if r_close > r_open: fvg_dir = 'LONG'; fvg_top = r_high; fvg_bot = r_low; fvg_inv = r_low
            else: fvg_dir = 'SHORT'; fvg_top = r_high; fvg_bot = r_low; fvg_inv = r_high
        else:
            scan_end = d + pd.Timedelta(hours=9, minutes=35)
            scan_data = day_data[(day_data.index >= t930) & (day_data.index <= scan_end)]
            largest_gap = 0
            s_row = day_data.index.get_loc(t930); e_row = day_data.index.get_loc(scan_data.index[-1])
            for i in range(s_row + 1, e_row + 1):
                if i < 2: continue
                curr = day_data.iloc[i]; prev2 = day_data.iloc[i-2]
                if curr['low'] > prev2['high']:
                    gap = curr['low'] - prev2['high']
                    # DIRECTION CHECK (Must be Breakout aligned)
                    if prev2['high'] >= r_high or curr['close'] > r_high:
                        if gap > largest_gap:
                            largest_gap = gap; fvg_dir = 'LONG'; fvg_top = curr['low']; fvg_bot = prev2['high']; fvg_inv = curr['low']
                            fvg_time = day_data.index[i]; mode = 'GAP'
                elif curr['high'] < prev2['low']:
                    gap = prev2['low'] - curr['high']
                    # DIRECTION CHECK
                    if prev2['low'] <= r_low or curr['close'] < r_low:
                        if gap > largest_gap:
                            largest_gap = gap; fvg_dir = 'SHORT'; fvg_top = prev2['low']; fvg_bot = curr['high']; fvg_inv = curr['high']
                            fvg_time = day_data.index[i]; mode = 'GAP'

        if fvg_dir:
            # Run Logic (Option B Market) to get markers
            market_time = fvg_time + pd.Timedelta(minutes=1)
            exec_win = day_data[day_data.index >= market_time]
            events = []
            if not exec_win.empty:
                 events = run_trade_logic_for_chart(exec_win, r_high, r_low, fvg_dir, 0, 0, fvg_inv, TP_PCT, HARD_EXIT)
            
            create_chart(day_data, d, t930, r_high, r_low, fvg_dir, fvg_top, fvg_bot, fvg_time, mode, events, OUT_DIR)
            chart_count += 1

def create_chart(day_data, date, t930, r_high, r_low, fvg_dir, fvg_top, fvg_bot, fvg_time, mode, events, out_dir):
    start = date + pd.Timedelta(hours=9, minutes=25)
    end = date + pd.Timedelta(hours=10, minutes=15)
    sliced = day_data[(day_data.index >= start) & (day_data.index <= end)]
    if sliced.empty: return

    fig = go.Figure(data=[go.Candlestick(
        x=sliced.index, open=sliced['open'], high=sliced['high'], low=sliced['low'], close=sliced['close'], 
        name='Price'
    )])

    # Range Lines
    fig.add_hline(y=r_high, line_dash="solid", line_color="gray", line_width=1, annotation_text="OR High")
    fig.add_hline(y=r_low, line_dash="solid", line_color="gray", line_width=1, annotation_text="OR Low")
    
    # FVG Box
    color = "green" if fvg_dir == 'LONG' else "red"
    if mode == 'GAP':
        fig.add_shape(type="rect",
            x0=fvg_time, x1=end, y0=fvg_bot, y1=fvg_top,
            line_color=color, fillcolor=color, opacity=0.2, line_width=1
        )
    
    # TRADE MARKERS
    for e in events:
        if e['type'] == 'ENTRY':
            sym = "triangle-up" if fvg_dir == 'LONG' else "triangle-down"
            fig.add_trace(go.Scatter(
                x=[e['time']], y=[e['price']], mode='markers',
                marker=dict(symbol=sym, size=12, color='blue'), name='Entry'
            ))
        elif e['type'] == 'EXIT':
            sym = "circle-x"
            color_ex = "green" if e['reason'] == 'TP' else "red"
            fig.add_trace(go.Scatter(
                x=[e['time']], y=[e['price']], mode='markers+text',
                marker=dict(symbol=sym, size=12, color=color_ex),
                text=[e['reason']], textposition="top center", name='Exit'
            ))

    res_str = events[-1]['reason'] if events else "NO_FILL"
    
    fig.update_layout(
        title=f"{date.date()} | {mode} {fvg_dir} | Res: {res_str}",
        xaxis_title="Time", yaxis_title="Price",
        template="plotly_dark", xaxis_rangeslider_visible=False, height=700
    )
    
    fname = f"chart_{date.date()}_{res_str}.html"
    fig.write_html(os.path.join(out_dir, fname))

if __name__ == "__main__":
    generate_charts()
