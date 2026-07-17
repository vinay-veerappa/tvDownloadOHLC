"""Inspect prediction dataset contents."""
import json
import os

DATA = "data"
for f in ["NQ1_asia_predictions.json", "NQ1_london_predictions.json"]:
    path = os.path.join(DATA, f)
    if not os.path.exists(path):
        print(f"{f}: NOT FOUND")
        continue

    with open(path) as fh:
        data = json.load(fh)

    keys = list(data.keys())
    size_kb = os.path.getsize(path) / 1024
    print(f"{f}: {len(keys)} context keys, {size_kb:.1f} KB")

    for k in keys[:5]:
        v = data[k]
        probs = v.get("probabilities", {})
        samples = v.get("samples", 0)
        print(f"  {k}: samples={samples}, probs={probs}")
    print()
