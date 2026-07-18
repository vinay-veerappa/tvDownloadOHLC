"""Audit the lookup table for completeness."""
import json
from pathlib import Path
from collections import defaultdict

_DATA = Path(__file__).parent / "data" / "derived"
lookup = json.load(open(_DATA / "NQ1_profiler_lookup.json"))

print("=" * 80)
print("LOOKUP TABLE COMPLETENESS AUDIT")
print("=" * 80)

# 1. Top-level structure
print(f"\n1. TOP-LEVEL KEYS: {sorted(lookup.keys())}")
tables = lookup.get("tables", {})
print(f"   Sessions covered: {sorted(tables.keys())}")

# 2. Per-session key counts
print(f"\n2. CONTEXT KEY COUNTS:")
for session in ["Asia", "London", "NY1", "NY2"]:
    keys = tables.get(session, {})
    full_keys = [k for k in keys if len(k.split("|")) > 2]  # has broken bits
    status_keys = [k for k in keys if len(k.split("|")) <= 2]  # status only
    total_samples = sum(e.get("samples", 0) for e in keys.values())
    print(f"   {session}: {len(keys)} keys ({len(full_keys)} full + {len(status_keys)} status-only), {total_samples} total samples")

# 3. Entry structure — check what fields each entry has
print(f"\n3. ENTRY STRUCTURE (checking first entry of each session):")
for session in ["Asia", "London", "NY1", "NY2"]:
    keys = tables.get(session, {})
    if not keys:
        print(f"   {session}: NO KEYS")
        continue
    first_key = sorted(keys.keys())[0]
    entry = keys[first_key]
    top_fields = sorted(entry.keys())
    print(f"   {session} [{first_key}]: {top_fields}")
    
    # Check per-outcome fields
    for outcome in ["LT", "LF", "ST", "SF"]:
        ps = entry.get("price_stats", {}).get(outcome, {})
        if ps:
            print(f"     price_stats.{outcome}: {sorted(ps.keys())}")
            break
    
    # Check per-outcome level hits
    polh = entry.get("per_outcome_level_hits", {})
    if polh:
        first_outcome = sorted(polh.keys())[0]
        levels = sorted(polh[first_outcome].keys())
        print(f"     per_outcome_level_hits.{first_outcome}: {len(levels)} levels")
    else:
        print(f"     per_outcome_level_hits: MISSING!")
    
    # Check timing
    timing = entry.get("hod_lod_times", {})
    if timing:
        first_t = sorted(timing.keys())[0]
        print(f"     hod_lod_times.{first_t}: {sorted(timing[first_t].keys())}")
    
    # Check broken rates
    broken = entry.get("broken_rates", {})
    print(f"     broken_rates: {sorted(broken.keys()) if broken else 'EMPTY'}")

# 4. Check which entries are MISSING per_outcome_level_hits
print(f"\n4. ENTRIES MISSING per_outcome_level_hits:")
missing_count = 0
total_count = 0
for session in ["Asia", "London", "NY1", "NY2"]:
    keys = tables.get(session, {})
    session_missing = 0
    session_total = 0
    for key, entry in keys.items():
        session_total += 1
        total_count += 1
        if "per_outcome_level_hits" not in entry:
            session_missing += 1
            missing_count += 1
    if session_missing > 0:
        print(f"   {session}: {session_missing}/{session_total} entries missing per_outcome_level_hits")
    else:
        print(f"   {session}: All {session_total} entries have per_outcome_level_hits")
print(f"   TOTAL: {missing_count}/{total_count} entries missing per_outcome_level_hits")

# 5. Check if all 20 level keys are present in per_outcome_level_hits
print(f"\n5. LEVEL KEY COVERAGE (checking first entry with per_outcome_level_hits):")
EXPECTED_LEVELS = {
    "pdh", "pdm", "pdl",
    "p12h", "p12m", "p12l",
    "ny_p12h", "ny_p12m", "ny_p12l",
    "daily_open", "midnight_open", "open_0730",
    "asia_mid", "london_mid", "ny1_mid", "ny2_mid",
    "prev_asia_mid", "prev_london_mid", "prev_ny1_mid", "prev_ny2_mid",
}
for session in ["Asia", "London", "NY1", "NY2"]:
    keys = tables.get(session, {})
    for key, entry in keys.items():
        polh = entry.get("per_outcome_level_hits", {})
        if polh:
            for outcome in ["LT", "LF", "ST", "SF"]:
                if outcome in polh:
                    levels = set(polh[outcome].keys())
                    missing = EXPECTED_LEVELS - levels
                    extra = levels - EXPECTED_LEVELS
                    print(f"   {session}/{key}/{outcome}: {len(levels)}/20 levels")
                    if missing:
                        print(f"     MISSING: {sorted(missing)}")
                    if extra:
                        print(f"     EXTRA: {sorted(extra)}")
                    break
            break

# 6. Check what the WebUI needs that's NOT in the lookup table
print(f"\n6. WEBUI REQUIREMENTS vs LOOKUP TABLE:")
print(f"   WebUI needs (per filter):")
print(f"     - count/samples: {'YES' if 'samples' in entry else 'NO'}")
print(f"     - distribution/probabilities: {'YES' if 'probabilities' in entry else 'NO'}")
print(f"     - per-outcome price_stats (mode/median/avg): {'YES' if 'price_stats' in entry else 'NO'}")
print(f"     - per-outcome timing (hod/lod mode): {'YES' if 'hod_lod_times' in entry else 'NO'}")
print(f"     - per-outcome broken_rates: {'YES' if 'broken_rates' in entry else 'NO'}")
print(f"     - per-outcome level_hit_rates: {'YES' if 'per_outcome_level_hits' in entry else 'NO'}")
print(f"     - global level_hit_rates: {'YES' if 'level_hits' in lookup else 'NO'}")
print(f"     - base_rates: {'YES' if 'base_rates' in lookup else 'NO'}")

# 7. What's MISSING that the WebUI computes at runtime
print(f"\n7. FIELDS THE WEBUI COMPUTES AT RUNTIME (not in lookup table):")
print(f"   - range_stats (overall high_pct/low_pct median/mean/mode): NOT in lookup")
print(f"   - HOD/LOD timing buckets (full distribution, not just mode): NOT in lookup")
print(f"   - Per-outcome HOD/LOD timing buckets: NOT in lookup")
print(f"   - Session HOD/LOD contribution (which session makes HOD/LOD): NOT in lookup")
print(f"   - Price Model Chart data (median price path per session): NOT in lookup")
print(f"   - Level hit MODE time and MEDIAN time: NOT in lookup (only hit rate)")

# 8. Coverage matrix — how many context combinations are possible vs actual
print(f"\n8. CONTEXT COMBINATION COVERAGE:")
# For NY1: 4 statuses × 2 broken × 4 statuses × 2 broken = 64 full keys
# Plus 4 × 4 = 16 status-only keys = 80 total
for session in ["Asia", "London", "NY1", "NY2"]:
    keys = tables.get(session, {})
    n_keys = len(keys)
    # Theoretical max: 4^num_context * 2^num_context (full) + 4^num_context (status-only)
    if session == "Asia":
        max_full = 4**2 * 2**2  # 2 context sessions
        max_status = 4**2
    elif session == "London":
        max_full = 4**2 * 2**2
        max_status = 4**2
    elif session == "NY1":
        max_full = 4**2 * 2**2
        max_status = 4**2
    elif session == "NY2":
        max_full = 4**3 * 2**3
        max_status = 4**3
    max_total = max_full + max_status
    print(f"   {session}: {n_keys} keys (theoretical max: {max_total} = {max_full} full + {max_status} status-only)")
    if n_keys < max_total:
        print(f"     MISSING {max_total - n_keys} combinations (likely no historical data)")

# 9. Check if status-only keys aggregate properly
print(f"\n9. STATUS-ONLY KEY AGGREGATION CHECK (NY1 LF|LF):")
ny1 = tables.get("NY1", {})
status_entry = ny1.get("LF|LF", {})
full_sum = 0
for bk_a in ["F", "T"]:
    for bk_l in ["F", "T"]:
        full_key = f"LF|{bk_a}|LF|{bk_l}"
        full_entry = ny1.get(full_key, {})
        samples = full_entry.get("samples", 0)
        full_sum += samples
        print(f"   {full_key}: {samples} samples")
print(f"   Sum of full keys: {full_sum}")
print(f"   Status-only LF|LF: {status_entry.get('samples', 0)} samples")
print(f"   Match: {'YES' if full_sum == status_entry.get('samples', 0) else 'NO'}")