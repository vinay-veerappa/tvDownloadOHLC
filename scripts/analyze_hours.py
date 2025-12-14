import pandas as pd

def analyze_hours():
    csv_file = r"C:\Users\vinay\tvDownloadOHLC\data\SP_1m_verification.csv"
    print("Loading 1m CSV...")
    # Read just the datetime column to save memory if file is huge
    df = pd.read_csv(csv_file, usecols=['datetime'])
    df['datetime'] = pd.to_datetime(df['datetime'])
    
    # Extract Hour and Minute
    df['hour'] = df['datetime'].dt.hour
    df['minute'] = df['datetime'].dt.minute
    df['time_float'] = df['hour'] + df['minute'] / 60.0
    
    # Define RTH (approx 09:30 to 16:15)
    rth_mask = (df['time_float'] >= 9.5) & (df['time_float'] <= 16.25)
    
    eth_count = (~rth_mask).sum()
    total_count = len(df)
    
    print(f"Total Bars: {total_count}")
    print(f"RTH Bars (09:30-16:15): {rth_mask.sum()}")
    print(f"ETH Bars (Outside RTH): {eth_count} ({eth_count/total_count:.1%})")
    
    # Range of hours found
    hours_present = sorted(df['hour'].unique())
    print(f"Hours present in dataset: {hours_present}")
    
    # Verify specific early/late blocks
    print(f"Bars before 08:00: {len(df[df['hour'] < 8])}")
    print(f"Bars after 18:00: {len(df[df['hour'] >= 18])}")

if __name__ == "__main__":
    analyze_hours()
