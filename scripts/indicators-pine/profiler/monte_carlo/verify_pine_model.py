
import re
import matplotlib.pyplot as plt
import numpy as np

# --- 1. Load Data from Pine File ---
def load_pine_array(filepath, func_name):
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Regex to find array.from(...) inside the specific function
    # _get_high_0() =>
    #     array.from(0.008,...)
    pattern = re.compile(rf"{func_name}\(\) =>\s+array\.from\(([\d\.,\s-]+)\)")
    match = pattern.search(content)
    if match:
        vals_str = match.group(1)
        vals = [float(x.strip()) for x in vals_str.split(',')]
        return vals
    return []

PINE_FILE = r"c:\Users\vinay\tvDownloadOHLC\scripts\profiler\ProfilerData_Model_LT.pine"
print(f"Loading data from {PINE_FILE}...")

t_arr = load_pine_array(PINE_FILE, "_get_times_0")
h_arr = load_pine_array(PINE_FILE, "_get_high_0")
l_arr = load_pine_array(PINE_FILE, "_get_low_0")

print(f"Loaded {len(t_arr)} times, {len(h_arr)} highs, {len(l_arr)} lows")

# --- 2. Simulate Pine Script Logic ---
# Defaults from ProfilerIndicator.pine
PM_SCALE = 100.0 # Updated default
BASE_PRICE = 20000.0
SHOW_SMOOTH = False # Default checked in code

# Session Inputs (Simulated)
# NY1 Session: 07:30 - 11:30 ET
# Times in array are minutes from 18:00 ET
# 08:00 ET = 14*60 = 840 min
# 07:30 ET = 810 min
# 11:30 ET = 1050 min

SRC_NY1 = True
# NY1 Logic from Pine:
# range := t_min >= 810 and t_min < 1050

# Logic Variables
pts_h = []
pts_l = []
processed_times = []

# Anchoring Logic (Simplified for verification)
# In Pine: 
# if not na(open_ny) and idx_ny != -1 ...
# Here we assume we anchor to the value at start of NY1 (810 min)

idx_anchor = -1
for i, t in enumerate(t_arr):
    if t >= 810:
        idx_anchor = i
        break

scale_h_base = h_arr[idx_anchor] if idx_anchor != -1 else 0.0
scale_l_base = l_arr[idx_anchor] if idx_anchor != -1 else 0.0

print(f"Anchor Index: {idx_anchor}, Time: {t_arr[idx_anchor]}")
print(f"Base High Val: {scale_h_base}, Base Low Val: {scale_l_base}")

# Smoothing Logic
h_smooth = list(h_arr)
l_smooth = list(l_arr)

if SHOW_SMOOTH:
    # 3-point smooth (simulating k=-1 to 1)
    for i in range(1, len(h_arr)-1):
        sum_h = h_arr[i-1] + h_arr[i] + h_arr[i+1]
        sum_l = l_arr[i-1] + l_arr[i] + l_arr[i+1]
        h_smooth[i] = sum_h / 3.0
        l_smooth[i] = sum_l / 3.0

# Calculation Loop
debug_last_val = 0.0
debug_diff = 0.0

for i, t_min in enumerate(t_arr):
    # Filter strict time window
    in_range = False
    if SRC_NY1:
        in_range = t_min >= 810 and t_min < 1050
    
    if in_range:
        val_h = h_smooth[i]
        val_l = l_smooth[i]
        
        # Scaling
        # val_h := val_h * pm_scale
        val_h_scaled = val_h * PM_SCALE
        val_l_scaled = val_l * PM_SCALE
        
        s_h_eff = scale_h_base * PM_SCALE
        s_l_eff = scale_l_base * PM_SCALE
        
        # Projection Math
        # p_h = base_p * (1.0 + val_h / 100.0) / (1.0 + s_h_eff / 100.0)
        # Note: If val_h is 0.008, scaled is 0.8. 
        # (1 + 0.8/100) = 1.008. 
        # This matches 0.8% move.
        
        p_h = BASE_PRICE * (1.0 + val_h_scaled / 100.0) / (1.0 + s_h_eff / 100.0)
        p_l = BASE_PRICE * (1.0 + val_l_scaled / 100.0) / (1.0 + s_l_eff / 100.0)
        
        pts_h.append(p_h)
        pts_l.append(p_l)
        processed_times.append(t_min)
        
        debug_last_val = val_h # for debug check

# Debug Calculation
if pts_h:
    last_idx = -1
    # Find last index used
    for i, t in enumerate(t_arr):
        if t >= 1050:
            last_idx = i
            break
    
    val_last_h = h_smooth[last_idx] if last_idx != -1 else 0.0
    val_last_h_scaled = val_last_h * PM_SCALE
    
    # Calculate Diff (Raw scaled delta)
    # The label in Pine shows: "Diff: " + str.tostring(val_last - scale_h_base)
    # Be careful: In Pine 'val_last' inside label block uses 'end_idx' logic.
    rec_diff = val_last_h - scale_h_base
    print(f"Calculated Diff (Raw): {rec_diff}")
    print(f"Calculated Diff (Scaled): {rec_diff * PM_SCALE}")
    print(f"Expected Price High End: {pts_h[-1]:.2f}")
    
# Plot
plt.figure(figsize=(10, 6))
plt.plot(processed_times, pts_h, label='Projected High', color='blue')
plt.plot(processed_times, pts_l, label='Projected Low', color='red')
plt.axhline(BASE_PRICE, color='gray', linestyle='--', label='Base Price')
plt.title(f"Simulated Pine Price Model (NY1) - Scale {PM_SCALE}")
plt.xlabel("Minutes from 18:00")
plt.ylabel("Price")
plt.legend()
plt.grid(True)

output_path = r"c:\Users\vinay\tvDownloadOHLC\scripts\profiler\monte_carlo\output\verify_pine_model.png"
plt.savefig(output_path)
print(f"Plot saved to {output_path}")
