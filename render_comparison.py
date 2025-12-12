
import json
import matplotlib.pyplot as plt
import pandas as pd
import requests
import datetime

def render_comparison():
    # 1. Load Reference Data
    try:
        with open('docs/reference_medians.json', 'r') as f:
            ref_data = json.load(f)
        ref_df = pd.DataFrame(ref_data.get('medians', []))
    except Exception as e:
        print(f"Error loading reference: {e}")
        return

    # 2. Fetch App Data
    # Assuming standard session for comparison (e.g. NY1, Short False to get some data)
    # The reference doesn't specify which session it is, but it seems to be a full day aggregate?
    # We will fetch 'NY1' 'Short False' as a representative sample
    url = "http://localhost:8000/stats/price-model/NQ1?session=NY1&outcome=Short%20True"
    print(f"Fetching: {url}")
    try:
        res = requests.get(url)
        if res.status_code != 200:
            print(f"API Error: {res.text}")
            app_df = pd.DataFrame() # Empty
        else:
            app_json = res.json()
            app_df = pd.DataFrame(app_json.get('average', []))
    except Exception as e:
        print(f"Connection Error: {e}")
        app_df = pd.DataFrame()

    # 3. Setup Plot
    fig, axes = plt.subplots(2, 1, figsize=(14, 10))
    plt.style.use('bmh')
    
    # Plot 1: Reference
    ax1 = axes[0]
    if not ref_df.empty:
        # X-Axis is 'time' string. We'll pick every 12th tick for readability
        ax1.plot(ref_df.index, ref_df['med_high_pct'], label='Ref High', color='green', linewidth=1.5)
        ax1.plot(ref_df.index, ref_df['med_low_pct'], label='Ref Low', color='red', linewidth=1.5)
        ax1.fill_between(ref_df.index, ref_df['med_high_pct'], ref_df['med_low_pct'], color='gray', alpha=0.1)
        
        # Set ticks
        n_ticks = 15
        step = max(1, len(ref_df) // n_ticks)
        ax1.set_xticks(ref_df.index[::step])
        ax1.set_xticklabels(ref_df['time'][::step], rotation=45)
        
        ax1.set_title("Reference Medians (Source: provided JSON)")
        ax1.set_ylabel("Change %")
        ax1.legend()
        ax1.grid(True)
    else:
        ax1.text(0.5, 0.5, "Reference Data Missing", ha='center')

    # Plot 2: App Data
    ax2 = axes[1]
    if not app_df.empty:
        # Convert time_idx to Time String (Start 09:30)
        start_time = datetime.datetime(2000, 1, 1, 9, 30)
        
        def fmt_time(idx):
            t = start_time + datetime.timedelta(minutes=int(idx))
            return t.strftime("%H:%M")
            
        times = [fmt_time(x) for x in app_df['time_idx']]
        
        ax2.plot(app_df['time_idx'], app_df['high'], label='App Avg High (Median)', color='blue', linewidth=1.5)
        ax2.plot(app_df['time_idx'], app_df['low'], label='App Avg Low (Median)', color='orange', linewidth=1.5)
        ax2.fill_between(app_df['time_idx'], app_df['high'], app_df['low'], color='blue', alpha=0.05)
        
        # Ticks every 60m
        ticks = range(0, int(app_df['time_idx'].max()) + 1, 60)
        tick_labels = [fmt_time(t) for t in ticks]
        ax2.set_xticks(ticks)
        ax2.set_xticklabels(tick_labels)
        
        ax2.set_title(f"App Generated Model (NY1 Short False) - {len(app_df)} pts")
        ax2.set_ylabel("Change %")
        ax2.legend()
        ax2.grid(True)
    else:
        ax2.text(0.5, 0.5, "App Data Copuld Not Be Fetched / Empty", ha='center')

    plt.tight_layout()
    output_path = 'docs/comparison_chart.png'
    plt.savefig(output_path, dpi=100)
    print(f"Saved to {output_path}")

if __name__ == "__main__":
    render_comparison()
