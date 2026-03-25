import pandas as pd

def analyze_pda_performance(df_arrays: pd.DataFrame):
    if df_arrays.empty:
        print("\n--- PD Array Performance ---")
        print("No PD Arrays detected.")
        return
        
    print("\n--- PD Array Performance ---")
    
    # Filter for Manipulation Zone arrays only?
    # User prompt: "For London-session PD arrays that are in the manipulation zone"
    
    zone_arrays = df_arrays[df_arrays['in_manipulation_zone'] == True]
    
    if zone_arrays.empty:
        print("No PD Arrays in manipulation zone.")
        return
        
    print(f"Analyzing {len(zone_arrays)} arrays in manipulation zone.")
    
    # Group by Type
    stats = zone_arrays.groupby('type').agg({
        'touched': 'mean',
        'respected': 'sum', # Count of respected
        'failed': 'sum',    # Count of failed
        'date': 'count'     # Total
    })
    
    # Calculate Respect Rate relative to TOCUHED arrays
    # respected check logic: a respected array IS touched.
    # So Respect Rate = Respected / Touched
    # Failure Rate = Failed / Touched
    
    # Note: Our logic allows an array to be touched but neither respected nor failed if session ends?
    # Or respected + failed = touched? 
    # Let's check logic: Pending if session ends.
    
    stats['Touch Rate %'] = stats['touched'] * 100
    
    # Counts of touched
    stats['Touched Count'] = zone_arrays.groupby('type')['touched'].sum()
    
    # Avoid div by zero
    stats['Respect Rate %'] = (stats['respected'] / stats['Touched Count'].replace(0, 1)) * 100
    stats['Failure Rate %'] = (stats['failed'] / stats['Touched Count'].replace(0, 1)) * 100
    
    print(stats[['date', 'Touch Rate %', 'Respect Rate %', 'Failure Rate %']].round(1))
    
    return stats
