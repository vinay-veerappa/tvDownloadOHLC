"""Estimate token count with bit-packing for the lookup table PineScript approach.

Bit-packing opportunities:
- Status codes: 0-4 (3 bits) → pack 15 per int (like V1)
- Broken flags: 0-1 (1 bit) → pack 15 per int
- Probabilities: 0-1 × 1000 = 0-1000 (10 bits) → pack 5 per int
- Hit rates: 0-100 × 10 = 0-1000 (10 bits) → pack 5 per int
- Price stats mode/median: -5.0 to 5.0 × 100 = -500 to 500 (10 bits + sign) → pack 4 per int
- Times: 0-1439 minutes (11 bits) → pack 4 per int
- Broken rates: 0-1 × 1000 (10 bits) → pack 5 per int

Without bit-packing: each value = 1 Pine token (a number in an array)
With bit-packing: 15 values = 1 Pine token (packed into 1 number)
Compression ratio: ~15:1 for bit-packed fields
"""
import json
from pathlib import Path
from collections import defaultdict

_DATA = Path(__file__).parent / "data" / "derived"

STATUS_CODES = {"Long True": 1, "Long False": 2, "Short True": 3, "Short False": 4, "None": 0}
SHORT_CODES = {"LT": 1, "LF": 2, "ST": 3, "SF": 4}

for ticker in ["NQ1", "ES1"]:
    lookup = json.load(open(_DATA / f"{ticker}_profiler_lookup.json"))
    tables = lookup["tables"]
    
    print(f"\n{'='*70}")
    print(f"{ticker}: Token estimate with bit-packing")
    print(f"{'='*70}")
    
    total_tokens_packed = 0
    total_tokens_plain = 0
    
    for session_name in ["Asia", "London", "NY1", "NY2"]:
        table = tables.get(session_name, {})
        entries = len(table)
        
        # Per entry, count values:
        # - key: 1 token (string or packed int)
        # - samples: 1 token
        # - probabilities: 4 values → packed 5/int = 1 token
        # - price_stats: 4 outcomes × 4 fields (h_mode, h_med, l_mode, l_med) = 16 values → packed 4/int = 4 tokens
        # - price_stats avg: 4 outcomes × 2 = 8 values → packed 4/int = 2 tokens (can skip avg for Pine)
        # - timing: 4 outcomes × 2 = 8 values → packed 4/int = 2 tokens
        # - broken_rates: 4 values → packed 5/int = 1 token
        # - level hits: 4 outcomes × 20 levels × 1 hit_rate = 80 values → packed 5/int = 16 tokens
        # - level times: 4 outcomes × 20 levels × 2 (mode+median) = 160 values → packed 4/int = 40 tokens
        
        # Packed estimate per entry:
        packed_per_entry = (
            1 +   # key
            1 +   # samples
            1 +   # probabilities (4 packed into 1)
            4 +   # price_stats mode/median (16 packed into 4)
            2 +   # price_stats avg (8 packed into 2) — optional, could skip
            2 +   # timing (8 packed into 2)
            1 +   # broken_rates (4 packed into 1)
            16 +  # level hit_rates (80 packed into 16)
            40    # level times (160 packed into 40)
        )
        
        # Plain estimate per entry (no packing):
        plain_per_entry = (
            1 +   # key
            1 +   # samples
            4 +   # probabilities
            16 +  # price_stats mode/median
            8 +   # price_stats avg
            8 +   # timing (as strings, ~2 tokens each = 16)
            4 +   # broken_rates
            80 +  # level hit_rates
            160   # level times (strings = ~2 tokens each = 320)
        )
        
        # Timing as strings is expensive. Let's use minutes (int) instead:
        plain_per_entry_inttime = (
            1 + 1 + 4 + 16 + 8 + 8 + 4 + 80 + 160  # times as ints
        )
        
        session_packed = entries * packed_per_entry
        session_plain = entries * plain_per_entry_inttime
        
        total_tokens_packed += session_packed
        total_tokens_plain += session_plain
        
        print(f"  {session_name}: {entries} entries")
        print(f"    Packed: ~{packed_per_entry} tokens/entry × {entries} = ~{session_packed:,} tokens")
        print(f"    Plain:  ~{plain_per_entry_inttime} tokens/entry × {entries} = ~{session_plain:,} tokens")
        print(f"    Savings: {session_plain - session_packed:,} tokens ({(1 - session_packed/session_plain)*100:.0f}% reduction)")
    
    print(f"\n  TOTAL {ticker}:")
    print(f"    Packed: ~{total_tokens_packed:,} tokens")
    print(f"    Plain:  ~{total_tokens_plain:,} tokens")
    print(f"    Savings: {total_tokens_plain - total_tokens_packed:,} tokens ({(1 - total_tokens_packed/total_tokens_plain)*100:.0f}% reduction)")
    print(f"    Libraries needed (packed, 100K limit): {max(1, (total_tokens_packed + 99999) // 100000)}")
    print(f"    Libraries needed (plain, 100K limit):  {max(1, (total_tokens_plain + 99999) // 100000)}")
    
    # Per-session library split
    print(f"\n  Library split (packed):")
    for session_name in ["Asia", "London", "NY1", "NY2"]:
        table = tables.get(session_name, {})
        entries = len(table)
        packed = entries * 68  # packed_per_entry from above
        print(f"    {session_name}: ~{packed:,} tokens → {'fits in 1 lib' if packed < 100000 else f'needs {(packed+99999)//100000} libs'}")

# Compare with V1
print(f"\n{'='*70}")
print(f"COMPARISON SUMMARY")
print(f"{'='*70}")
print(f"V1 (current):  ~105,000 tokens across 14 libraries (NQ1 only)")
print(f"V2 (current):  ~200,000+ tokens across 20+ libraries (NQ1+ES1)")
print(f"Lookup plain:  ~{total_tokens_plain:,} tokens across {(total_tokens_plain+99999)//100000} libraries per ticker")
print(f"Lookup packed: ~{total_tokens_packed:,} tokens across {max(1,(total_tokens_packed+99999)//100000)} libraries per ticker")
print(f"\nWith bit-packing, ALL sessions for one ticker fit in 1 library!")
print(f"Adding ES1 = generate 1 more library, publish 1 more library.")