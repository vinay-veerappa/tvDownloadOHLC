import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

def visualize_data():
    input_file = "ES_1m_continuous.csv"
    if not os.path.exists(input_file):
        print(f"File not found: {input_file}")
        return

    print(f"Loading {input_file}...")
    df = pd.read_csv(input_file)
    
    # Ensure datetime
    df['datetime'] = pd.to_datetime(df['datetime'])
    
    # Convert to NY Time
    # Assuming source is UTC (unix timestamp)
    if df['datetime'].dt.tz is None:
        df['datetime'] = df['datetime'].dt.tz_localize('UTC')
    
    df['datetime'] = df['datetime'].dt.tz_convert('America/New_York')
    
    df.set_index('datetime', inplace=True)
    
    # Filter for last N bars to avoid browser lag if file is huge
    # 10,000 bars is usually fine for Plotly
    max_bars = 20000
    if len(df) > max_bars:
        print(f"Data too large ({len(df)} rows). Showing last {max_bars} bars.")
        plot_df = df.tail(max_bars)
    else:
        plot_df = df

    print("Generating chart...")
    
    # Create single plot (Candlestick only)
    fig = go.Figure()

    # Candlestick
    fig.add_trace(go.Candlestick(
        x=plot_df.index,
        open=plot_df['open'],
        high=plot_df['high'],
        low=plot_df['low'],
        close=plot_df['close'],
        name='OHLC'
    ))

    # Layout styling to look like TradingView
    fig.update_layout(
        title=f'ES Futures (1m) - {input_file}',
        yaxis_title='Price',
        xaxis_title='Time (NY)',
        xaxis_rangeslider_visible=False, # Hide default range slider
        template='plotly_dark', # Dark mode like TV
        height=800,
        margin=dict(l=50, r=50, t=50, b=50),
        hovermode='x unified' # Show all info on hover line
    )
    
    # Enable scroll zoom and crosshair
    fig.update_xaxes(
        type='date',
        showspikes=True, # Crosshair vertical line
        spikemode='across',
        spikesnap='cursor',
        showline=True, 
        showgrid=True
    )
    fig.update_yaxes(
        showspikes=True, # Crosshair horizontal line
        spikemode='across',
        spikesnap='cursor',
        showline=True, 
        showgrid=True
    )
    
    fig.update_layout(dragmode='pan') # Default to pan like TV

    output_html = "chart_view.html"
    fig.write_html(output_html)
    print(f"Chart saved to {output_html}")
    
    # Try to open automatically
    try:
        os.startfile(output_html)
    except:
        print(f"Please open {output_html} in your browser.")

if __name__ == "__main__":
    visualize_data()
