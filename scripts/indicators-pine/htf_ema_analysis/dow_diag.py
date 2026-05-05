"""Quick diagnostic: signed vs clamped DOW stats, shift hypothesis test."""
import pandas as pd
import numpy as np
import pytz
from pathlib import Path

ET = pytz.timezone("America/New_York")
DIR = Path(__file__).parent

wdf = pd.read_csv(DIR / "CME_MINI_NQ1!, 1W_f166a.csv")
wdf["datetime"] = pd.to_datetime(wdf["time"], unit="s", utc=True).dt.tz_convert(ET)
wdf = wdf.sort_values("datetime").reset_index(drop=True)
wdf["ema5"] = wdf["close"].ewm(span=5, adjust=False).mean()

ddf = pd.read_csv(DIR / "CME_MINI_NQ1!, 1D_a1cee.csv")
ddf["datetime"] = pd.to_datetime(ddf["time"], unit="s", utc=True).dt.tz_convert(ET)
ddf = ddf.sort_values("datetime").reset_index(drop=True)
ddf["dow"] = ddf["datetime"].dt.dayofweek

# EMA[1] map
ema_map = []
for i in range(1, len(wdf)):
    start = wdf.loc[i, "datetime"]
    end = wdf.loc[i + 1, "datetime"] if i + 1 < len(wdf) else pd.Timestamp("2030-01-01", tz=ET)
    ema_map.append((start, end, wdf.loc[i - 1, "ema5"]))

def get_ema(dt):
    for s, e, v in ema_map:
        if s <= dt < e:
            return v
    return np.nan

ddf["ema"] = ddf["datetime"].apply(get_ema)

# Collect per-day SIGNED and ABS data (S3: own HL, close day label)
last_week = wdf.iloc[-1]["datetime"]
days = {d: {"up_signed": [], "dn_abs": []} for d in range(5)}

for _, bar in ddf.iterrows():
    if bar["datetime"] >= last_week or np.isnan(bar["ema"]):
        continue
    close_dow = (bar["dow"] + 1) % 7
    if close_dow == 6:
        close_dow = 0
    if close_dow > 4:
        continue

    ema = bar["ema"]
    up_signed = (bar["high"] - ema) / ema * 100       # SIGNED (can be negative)
    dn_abs = abs(ema - bar["low"]) / ema * 100         # ABSOLUTE (always positive)

    days[close_dow]["up_signed"].append(up_signed)
    days[close_dow]["dn_abs"].append(dn_abs)

names = {0: "Mon", 1: "Tue", 2: "Wed", 3: "Thu", 4: "Fri"}

# Reference DOW data - testing both column orders
ref_original = {
    "Mon": {"h_up": 42.3, "h_dn": 19.2, "c_up": 36.5, "c_dn": 23.1, "mn_hi": 1.38, "mn_lo": 2.28, "md_hi": 1.74, "md_lo": 0.53},
    "Tue": {"h_up": 55.8, "h_dn": 25.0, "c_up": 42.3, "c_dn": 25.0, "mn_hi": 1.84, "mn_lo": 2.33, "md_hi": 2.21, "md_lo": 0.63},
    "Wed": {"h_up": 57.7, "h_dn": 34.6, "c_up": 55.8, "c_dn": 34.6, "mn_hi": 1.74, "mn_lo": 2.62, "md_hi": 2.23, "md_lo": 0.35},
}

# Reordered: Hit↑, Comp↑, Hit↓, Comp↓ (solving impossible Cmp↓>Hit↓)
ref_reordered = {
    "Mon": {"h_up": 42.3, "c_up": 19.2, "h_dn": 36.5, "c_dn": 23.1, "mn_hi": 1.38, "mn_lo": 2.28, "md_hi": 1.74, "md_lo": 0.53},
    "Tue": {"h_up": 55.8, "c_up": 25.0, "h_dn": 42.3, "c_dn": 25.0, "mn_hi": 1.84, "mn_lo": 2.33, "md_hi": 2.21, "md_lo": 0.63},
    "Wed": {"h_up": 57.7, "c_up": 34.6, "h_dn": 55.8, "c_dn": 34.6, "mn_hi": 1.74, "mn_lo": 2.62, "md_hi": 2.23, "md_lo": 0.35},
}

print("=" * 100)
print("HYPOTHESIS: Reference uses SIGNED upside + ABS downside, shifted 1 day")
print("  upPct = (high - ema) / ema * 100          (signed, can be negative)")
print("  dnPct = abs(ema - low) / ema * 100         (absolute, always >= 0)")
print("  Hit↑ = %% of upPct >= 2.0  |  Hit↓ = %% of dnPct >= 2.0")
print("  Comp↑= %% of upPct >= 3.0  |  Comp↓= %% of dnPct >= 3.0")
print("  Shift: S3 Tue→Ref Mon, S3 Wed→Ref Tue, S3 Thu→Ref Wed")
print("=" * 100)

print()
print("ORIGINAL column order test (Hit↑, Hit↓, Comp↑, Comp↓):")
hdr1 = f"{'S3→Ref':<12} {'Hit↑':>7} {'Hit↓':>7} {'Cmp↑':>7} {'Cmp↓':>7} {'MnHi':>7} {'MnLo':>7} {'MdHi':>7} {'MdLo':>7}"
print(hdr1)
print("-" * len(hdr1))
shift_map = [(1, "Mon"), (2, "Tue"), (3, "Wed")]
for s3_idx, ref_name in shift_map:
    u = np.array(days[s3_idx]["up_signed"][-52:])
    d = np.array(days[s3_idx]["dn_abs"][-52:])
    n = len(u)
    
    h_up = (u >= 2.0).sum() / n * 100
    h_dn = (d >= 2.0).sum() / n * 100
    c_up = (u >= 3.0).sum() / n * 100
    c_dn = (d >= 3.0).sum() / n * 100
    mn_hi = np.mean(u)
    mn_lo = np.mean(d)
    md_hi = np.median(u)
    md_lo = np.median(d)
    
    rv = ref_original[ref_name]
    def m(v, r):
        return "✓" if abs(v - r) < 0.06 else f"Δ{v-r:+.1f}"
    
    print(
        f"{names[s3_idx]:>3}→{ref_name:<4}  "
        f"{h_up:>5.1f}%{m(h_up, rv['h_up']):>3} "
        f"{h_dn:>5.1f}%{m(h_dn, rv['h_dn']):>3} "
        f"{c_up:>5.1f}%{m(c_up, rv['c_up']):>3} "
        f"{c_dn:>5.1f}%{m(c_dn, rv['c_dn']):>3} "
        f"{mn_hi:>6.2f}{m(mn_hi, rv['mn_hi']):>5} "
        f"{mn_lo:>6.2f}{m(mn_lo, rv['mn_lo']):>5} "
        f"{md_hi:>6.2f}{m(md_hi, rv['md_hi']):>5} "
        f"{md_lo:>6.2f}{m(md_lo, rv['md_lo']):>5}"
    )

print()
print("REORDERED column order test (Hit↑, Comp↑, Hit↓, Comp↓):")
hdr2 = f"{'S3→Ref':<12} {'Hit↑':>7} {'Cmp↑':>7} {'Hit↓':>7} {'Cmp↓':>7} {'MnHi':>7} {'MnLo':>7} {'MdHi':>7} {'MdLo':>7}"
print(hdr2)
print("-" * len(hdr2))
for s3_idx, ref_name in shift_map:
    u = np.array(days[s3_idx]["up_signed"][-52:])
    d = np.array(days[s3_idx]["dn_abs"][-52:])
    n = len(u)
    
    h_up = (u >= 2.0).sum() / n * 100
    c_up = (u >= 3.0).sum() / n * 100
    h_dn = (d >= 2.0).sum() / n * 100
    c_dn = (d >= 3.0).sum() / n * 100
    mn_hi = np.mean(u)
    mn_lo = np.mean(d)
    md_hi = np.median(u)
    md_lo = np.median(d)
    
    rv = ref_reordered[ref_name]
    
    print(
        f"{names[s3_idx]:>3}→{ref_name:<4}  "
        f"{h_up:>5.1f}%{m(h_up, rv['h_up']):>3} "
        f"{c_up:>5.1f}%{m(c_up, rv['c_up']):>3} "
        f"{h_dn:>5.1f}%{m(h_dn, rv['h_dn']):>3} "
        f"{c_dn:>5.1f}%{m(c_dn, rv['c_dn']):>3} "
        f"{mn_hi:>6.2f}{m(mn_hi, rv['mn_hi']):>5} "
        f"{mn_lo:>6.2f}{m(mn_lo, rv['mn_lo']):>5} "
        f"{md_hi:>6.2f}{m(md_hi, rv['md_hi']):>5} "
        f"{md_lo:>6.2f}{m(md_lo, rv['md_lo']):>5}"
    )

# Summary of all 8 ref values vs computed
print()
print("=" * 100)
print("DETAILED MATCH SUMMARY (all 8 stats per day)")
print("=" * 100)
total_match = 0
total_close = 0
total = 0
for s3_idx, ref_name in shift_map:
    u = np.array(days[s3_idx]["up_signed"][-52:])
    d = np.array(days[s3_idx]["dn_abs"][-52:])
    n = len(u)
    
    computed = {
        "h_up": (u >= 2.0).sum() / n * 100,
        "h_dn": (d >= 2.0).sum() / n * 100,  # These positions depend on original order  
        "c_up": (u >= 3.0).sum() / n * 100,
        "c_dn": (d >= 3.0).sum() / n * 100,
        "mn_hi": np.mean(u),
        "mn_lo": np.mean(d),
        "md_hi": np.median(u),
        "md_lo": np.median(d),
    }
    
    rv = ref_original[ref_name]
    print(f"\n  S3 {names[s3_idx]} → Ref {ref_name}:")
    for key in ["mn_hi", "mn_lo", "md_hi", "md_lo"]:
        delta = computed[key] - rv[key]
        match = "✅ EXACT" if abs(delta) < 0.02 else "≈ close" if abs(delta) < 0.1 else "✗ MISS"
        if abs(delta) < 0.02: total_match += 1
        elif abs(delta) < 0.1: total_close += 1
        total += 1
        print(f"    {key:>6}: computed={computed[key]:>6.2f}  ref={rv[key]:>6.2f}  Δ={delta:>+6.2f}  {match}")
    
    # Test hit/comp with orig order
    for key, cv, rv_val in [("h_up", computed["h_up"], rv["h_up"]), ("h_dn", computed["h_dn"], rv["h_dn"]),
                             ("c_up", computed["c_up"], rv["c_up"]), ("c_dn", computed["c_dn"], rv["c_dn"])]:
        delta = cv - rv_val
        match = "✅ EXACT" if abs(delta) < 0.06 else "≈ close" if abs(delta) < 0.5 else "✗ MISS"
        if abs(delta) < 0.06: total_match += 1
        elif abs(delta) < 0.5: total_close += 1
        total += 1
        print(f"    {key:>6}: computed={cv:>6.1f}%  ref={rv_val:>6.1f}%  Δ={delta:>+6.1f}   {match}")

    # Also test reordered columns for hit/comp
    rv2 = ref_reordered[ref_name]
    print(f"  -- With reordered columns (Hit↑, Comp↑, Hit↓, Comp↓): --")
    for key, cv, rv_val in [("h_up", computed["h_up"], rv2["h_up"]), ("c_up", computed["c_up"], rv2["c_up"]),
                             ("h_dn", computed["h_dn"], rv2["h_dn"]), ("c_dn", computed["c_dn"], rv2["c_dn"])]:
        delta = cv - rv_val
        match = "✅ EXACT" if abs(delta) < 0.06 else "≈ close" if abs(delta) < 0.5 else "✗ MISS"
        print(f"    {key:>6}: computed={cv:>6.1f}%  ref={rv_val:>6.1f}%  Δ={delta:>+6.1f}   {match}")

print(f"\n  TOTAL: {total_match} exact + {total_close} close out of {total} comparisons")
