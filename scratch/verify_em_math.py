
import math

spot = 737.62
front_iv = 0.07955  # Actual atm_iv from JSON

targets = {
    "2026-05-12": 6.809,
    "2026-05-13": 8.286
}

dtes = {
    "2026-05-12": 3,
    "2026-05-13": 4
}

print(f"{'Method':<50} | May 12 (3d) | May 13 (4d)")
print("-" * 80)
print(f"{'TARGET (TOS)':<50} | {targets['2026-05-12']:<11} | {targets['2026-05-13']:<11}")

combinations = [
    ("Front IV (0.07955), 365 days, no skew", lambda iv, dte: spot * front_iv * math.sqrt(dte/365)),
    ("Front IV (0.07955), 252 days, no skew", lambda iv, dte: spot * front_iv * math.sqrt(dte/252)),
    ("Front IV (0.07955), 365 days, 0.85 skew", lambda iv, dte: spot * front_iv * math.sqrt(dte/365) * 0.85),
    ("Front IV (0.07955), 252 days, 0.85 skew", lambda iv, dte: spot * front_iv * math.sqrt(dte/252) * 0.85),
    # What if TOS is using the specific series IV but with 252?
    ("Per-Expiry IV, 252 days, 0.85 skew", lambda iv, dte: spot * iv * math.sqrt(dte/252) * 0.85),
]

# Re-estimate per-expiry IVs if 252 was the baseline
# Current pipeline used 365. 
# Pipeline May 12: 7.26 = spot * IV * sqrt(3/365) -> IV = 0.1085
# Pipeline May 13: 9.06 = spot * IV * sqrt(4/365) -> IV = 0.1173
pipeline_ivs = {
    "2026-05-12": 0.1085,
    "2026-05-13": 0.1173
}

for desc, formula in combinations:
    val1 = formula(pipeline_ivs["2026-05-12"], dtes["2026-05-12"])
    val2 = formula(pipeline_ivs["2026-05-13"], dtes["2026-05-13"])
    print(f"{desc:<50} | {val1:<11.3f} | {val2:<11.3f}")
