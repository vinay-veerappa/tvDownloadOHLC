
import json
import matplotlib.pyplot as plt
import pandas as pd
import os

def render_chart():
    # Load Data
    with open('docs/reference_medians.json', 'r') as f:
        data = json.load(f)
    
    medians = data.get('medians', [])
    if not medians:
        print("No data found")
        return

    df = pd.DataFrame(medians)
    
    # Setup Plot
    plt.figure(figsize=(12, 6))
    plt.style.use('bmh')  # Nice clean style
    
    # Plot Lines
    plt.plot(df.index, df['med_high_pct'], label='Median High %', color='green', linewidth=2)
    plt.plot(df.index, df['med_low_pct'], label='Median Low %', color='red', linewidth=2)
    
    # Fill between (optional, looks nice)
    plt.fill_between(df.index, df['med_high_pct'], df['med_low_pct'], color='gray', alpha=0.1)

    # Formatting
    plt.title('Reference Price Model (Median Paths)')
    plt.xlabel('Time Index (5m Intervals)')
    plt.ylabel('Percentage Change (%)')
    plt.legend()
    plt.grid(True)
    
    # Save
    output_path = 'docs/reference_chart.png'
    plt.savefig(output_path, dpi=100)
    print(f"Chart saved to {output_path}")

if __name__ == "__main__":
    render_chart()
