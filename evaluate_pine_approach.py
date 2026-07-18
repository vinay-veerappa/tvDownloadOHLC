"""Evaluate: can we fit the lookup table into PineScript directly?

Strategy: Instead of embedding raw daily data (5000+ dates × 20+ fields)
and computing at runtime, embed the precomputed lookup table (694 keys ×
per-outcome stats) as a simple lookup. No bit-packing needed — just
flat arrays keyed by context code.

This drops: price model curves, histograms, deep model bags, raw data arrays.
Keeps: samples, probabilities, price_stats (mode/median), timing, broken_rates,
level hit rates + times.
"""
import json
from pathlib import Path

_DATA = Path(__file__).parent / "data" / "derived"

for ticker in ["NQ1", "ES1"]:
    lookup = json.load(open(_DATA / f"{ticker}_profiler_lookup.json"))
    tables = lookup["tables"]
    
    # Count what we'd embed (excluding price model / histograms)
    total_entries = 0
    total_fields = 0
    estimated_chars = 0
    
    for session_name, table in tables.items():
        for key, entry in table.items():
            total_entries += 1
            # Key string
            estimated_chars += len(key) + 10  # key + delimiter
            # samples
            estimated_chars += 8
            # probabilities (4 outcomes)
            estimated_chars += 4 * 8
            # price_stats (4 outcomes × 7 fields)
            for o in entry.get("price_stats", {}):
                estimated_chars += 7 * 8
            # hod_lod_times (4 outcomes × 2 fields)
            for o in entry.get("hod_lod_times", {}):
                estimated_chars += 2 * 14  # "10:30-10:45" = ~11 chars
            # broken_rates (4 outcomes)
            estimated_chars += 4 * 6
            # per_outcome_level_hits (4 outcomes × 20 levels × 3 fields)
            for o in entry.get("per_outcome_level_hits", {}):
                estimated_chars += 20 * (8 + 11 + 11)  # hit_rate + mode_time + median_time
    
    estimated_kb = estimated_chars / 1024
    # PineScript tokens: roughly 1 token per number/string value
    # Each array element is ~1-2 tokens
    estimated_tokens = total_entries * 200  # rough estimate
    
    print(f"\n{'='*60}")
    print(f"{ticker}: {total_entries} entries, ~{estimated_kb:.0f} KB estimated")
    print(f"  Estimated tokens: ~{estimated_tokens:,}")
    print(f"  PineScript limit: 100,000 tokens per script")
    print(f"  Fits in single script: {'YES' if estimated_tokens < 100000 else 'NO'}")
    
    # Per-session breakdown
    for session_name in ["Asia", "London", "NY1", "NY2"]:
        table = tables.get(session_name, {})
        entries = len(table)
        est_tokens = entries * 200
        print(f"  {session_name}: {entries} entries, ~{est_tokens:,} tokens")
    
    # What if we use a compact encoding?
    # Key as int (status*2 + broken for each context session)
    # Values as compact arrays
    print(f"\n  Compact encoding estimate:")
    for session_name in ["Asia", "London", "NY1", "NY2"]:
        table = tables.get(session_name, {})
        entries = len(table)
        # Compact: 1 key int + ~100 values per entry = ~101 tokens
        est_tokens = entries * 101
        print(f"  {session_name}: {entries} entries, ~{est_tokens:,} tokens (compact)")

# Check: how many tokens does the V1 approach use?
# V1 has 14 libraries, each with ~5000 data points
# Each data point = 1-2 tokens
# Total: 14 * 5000 * 1.5 = ~105,000 tokens (spread across 14 libs)
print(f"\n{'='*60}")
print(f"V1 approach: ~105,000 tokens spread across 14 libraries")
print(f"V2 approach: ~200,000+ tokens spread across 20+ libraries (incl deep models)")
print(f"\nLookup approach (no price model/histograms):")
print(f"  NQ1: ~{694 * 101:,} tokens in 1-4 libraries")
print(f"  ES1: ~{703 * 101:,} tokens in 1-4 libraries")
print(f"  MUCH simpler — no bit-packing, no runtime computation, no API calls")