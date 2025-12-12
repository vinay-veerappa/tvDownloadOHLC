
import asyncio
import pandas as pd
import plotly.graph_objects as go
from api.services.profiler_service import ProfilerService

# Force pandas to display all columns
pd.set_option('display.max_columns', None)
pd.set_option('display.width', 1000)

async def main():
    ticker = "NQ1"
    target_session = "Daily"
    # No filters for base case
    filters = {}
    broken_filters = {}
    intra_state = "Any"
    bucket_minutes = 5

    print(f"--- Debugging Price Model for {ticker} ({target_session}) ---")

    # 1. Fetch Data directly via Service
    print("Fetching data from ProfilerService...")
    result = ProfilerService.get_filtered_price_model(
        ticker, target_session, filters, broken_filters, intra_state, bucket_minutes
    )
    
    if "error" in result:
        print(f"Error: {result['error']}")
        return

    # Note: 'median' is indeed the key now!
    avg_data = result.get("median", [])
    print(f"Data Points: {len(avg_data)}")
    if avg_data:
        print("First 5 points:", avg_data[:5])
        print("Last 5 points:", avg_data[-5:])

    # 2. Create Plotly Chart
    print("\nGenerating Plotly Chart...")
    
    # Extract data
    labels = [d.get('time', str(d['time_idx'])) for d in avg_data]
    highs = [d['high'] for d in avg_data]
    lows = [d['low'] for d in avg_data]

    fig = go.Figure()

    # High Path
    fig.add_trace(go.Scatter(
        x=labels, 
        y=highs,
        mode='lines',
        name='Median High',
        line=dict(color='green', width=2)
    ))

    # Low Path
    fig.add_trace(go.Scatter(
        x=labels, 
        y=lows,
        mode='lines',
        name='Median Low',
        line=dict(color='red', width=2)
    ))

    fig.update_layout(
        title=f"{ticker} {target_session} Price Model (Median)",
        xaxis_title="Time",
        yaxis_title="% Change from Open",
        template="plotly_dark"
    )

    output_file = "debug_price_model.html"
    fig.write_html(output_file)
    print(f"Chart saved to {output_file}")

if __name__ == "__main__":
    asyncio.run(main())
