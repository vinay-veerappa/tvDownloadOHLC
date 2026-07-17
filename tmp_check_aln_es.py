"""Check today's ALN mapping for ES using the NQStats engine."""
import pandas as pd
import json
from datetime import date

from scripts.libs_py.nqstats.engine import NQStatsEngine
from scripts.libs_py.nqstats.classifiers import compute_aln_bias, aln_full_string

# Load ES live storage
df = pd.read_parquet("data/live/live_storage_-ES.parquet")
df["dt"] = pd.to_datetime(df["timestamp"])
df = df.set_index("dt")
# Storage timestamps are US/Eastern naive -> localize so engine can tz_convert
df.index = df.index.tz_localize("US/Eastern")
df = df[["open", "high", "low", "close", "volume"]]

print(f"ES data range: {df.index.min()} -> {df.index.max()} ({len(df)} bars)")

# Use the last 5k bars for speed (engine tail(5000) pattern)
engine = NQStatsEngine(df.tail(5000), ticker="ES1")
engine.process()

latest = engine.get_latest_status()
last_ts = df.index[-1]
spot = float(df['close'].iloc[-1])

print(f"\n=== ES ALN Mapping (as of {last_ts}) ===")
print(f"ALN Pattern        : {latest.get('aln')} → {aln_full_string(latest.get('aln'))}")
print(f"Broken Status      : {latest.get('broken')}  (L vs A: {latest.get('l_vs_a')} | PreNY vs L: {latest.get('p_vs_l')})")

# Compute full bias verdict
lh = latest.get("london_high")
ll = latest.get("london_low")
bias = compute_aln_bias(
    latest.get("aln"), latest.get("broken"),
    spot=spot, london_high=lh, london_low=ll,
)
print(f"\n--- Pre-computed Bias Verdict ---")
print(f"Bias               : {bias['bias']} ({bias['conviction']})")
print(f"Reasoning          : {bias['reasoning']}")
print(f"NY Break Prob      : London High {bias['break_high_pct']:.1f}% | London Low {bias['break_low_pct']:.1f}%")
if bias['primary_target'] != 'NONE':
    _tl = 'London High' if bias['primary_target'] == 'LONDON_HIGH' else 'London Low'
    print(f"Primary Target     : {_tl} ({bias['primary_target_pct']:.1f}% probability)")
if bias['edge_spent']:
    print(f"EDGE SPENT         : {bias['edge_spent_note']}")
else:
    print(f"Edge Spent         : No (edge still valid)")

print(f"\nAsiaBox status     : {latest.get('asiabox_status')}")
print(f"LondonBox status   : {latest.get('londonbox_status')}")
print(f"NY1Box status      : {latest.get('ny1box_status')}")
print(f"NY2Box status      : {latest.get('ny2box_status')}")
print(f"Noon Curve         : {latest.get('noon_curve')}")
print()
print("Key Levels:")
print(f"  Asia   H {latest.get('asia_high')}  L {latest.get('asia_low')}  mid {latest.get('asia_mid')}")
print(f"  London H {latest.get('london_high')} L {latest.get('london_low')} mid {latest.get('london_mid')}")
print(f"  Pre-NY H {latest.get('pre-ny_high')} L {latest.get('pre-ny_low')}")
print(f"  P12 (prior close): {latest.get('p12')}")
print(f"  Spot              : {spot:,.2f}")

# Also dump the last few days of ALN pattern history
stats = engine.stats
daily = stats.groupby(stats.index.date).last()
print("\n=== ALN Pattern History (last 5 trading days) ===")
print(daily[["aln", "broken", "l_vs_a", "p_vs_l", "asiabox_status", "londonbox_status"]].tail(5).to_string())