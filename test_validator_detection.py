"""Test that the validator actually catches mismatches.
Deliberately corrupts one per-outcome level hit value in the lookup table
and confirms the validator detects it.
"""
import json
import shutil
import subprocess
import sys
import os
from pathlib import Path

LOOKUP = Path("data/derived/NQ1_profiler_lookup.json")
BACKUP = Path("data/derived/NQ1_profiler_lookup.json.bak")

def run_validator():
    """Run the validator for LF|LF and capture output."""
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "scripts.testing.run",
         "--feature", "profiler", "--ticker", "NQ1",
         "--session", "NY1", "--filter", "LF|LF"],
        capture_output=True, text=True, env=env, encoding="utf-8"
    )
    return result.stdout + result.stderr

def run_json_validator():
    """Run the validator in JSON mode and parse results."""
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "scripts.testing.run",
         "--feature", "profiler", "--ticker", "NQ1",
         "--session", "NY1", "--filter", "LF|LF", "--format", "json"],
        capture_output=True, text=True, env=env, encoding="utf-8"
    )
    try:
        data = json.loads(result.stdout)
        # Normalize status: the enum value is an emoji, convert to readable string
        status_map = {"⚠️": "mismatch", "✅": "match", "❌": "error", "⏭️": "skipped"}
        for r in data.get("results", []):
            r["overall_status"] = status_map.get(r.get("overall_status", ""), r.get("overall_status", ""))
            for fc in r.get("field_comparisons", []):
                fc["status"] = status_map.get(fc["status"], fc["status"])
        return data
    except json.JSONDecodeError:
        print("RAW OUTPUT:")
        print(result.stdout[:2000])
        print("STDERR:")
        print(result.stderr[:2000])
        return None

# ── Test 1: Verify baseline passes ──
print("=" * 60)
print("TEST 1: Baseline (no corruption) — should be all MATCH")
print("=" * 60)
data = run_json_validator()
if data and data.get("results"):
    r = data["results"][0]
    mismatches = [fc for fc in r["field_comparisons"] if fc["status"] == "mismatch"]
    print(f"  Overall: {r['overall_status']}")
    print(f"  Matched: {r['matched_fields']}/{r['total_fields']}")
    print(f"  Mismatches: {len(mismatches)}")
    if mismatches:
        print("  ❌ FAIL: Baseline should have 0 mismatches!")
        for m in mismatches[:5]:
            print(f"     {m['field_path']}: local={m['local_value']} webui={m['webui_value']}")
    else:
        print("  ✅ PASS: Baseline has 0 mismatches")

# ── Test 2: Corrupt a per-outcome level hit and verify detection ──
print()
print("=" * 60)
print("TEST 2: Corrupt per_outcome_level_hits LT.pdh — should MISMATCH")
print("=" * 60)

# Backup the original
shutil.copy2(LOOKUP, BACKUP)

try:
    # Load, corrupt, save
    with open(LOOKUP, "r", encoding="utf-8") as f:
        d = json.load(f)
    original_val = d["tables"]["NY1"]["LF|LF"]["per_outcome_level_hits"]["LT"]["pdh"]
    corrupted_val = original_val + 10.0  # Add 10% to make it clearly wrong
    d["tables"]["NY1"]["LF|LF"]["per_outcome_level_hits"]["LT"]["pdh"] = corrupted_val
    with open(LOOKUP, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2, ensure_ascii=False)
    print(f"  Corrupted LT.pdh: {original_val} -> {corrupted_val}")

    data = run_json_validator()
    if data and data.get("results"):
        r = data["results"][0]
        mismatches = [fc for fc in r["field_comparisons"] if fc["status"] == "mismatch"]
        print(f"  Overall: {r['overall_status']}")
        print(f"  Matched: {r['matched_fields']}/{r['total_fields']}")
        print(f"  Mismatches: {len(mismatches)}")

        # Find the specific corrupted field
        pdh_mismatch = [m for m in mismatches if "per_outcome_level_hit.LT.pdh" in m["field_path"]]
        if pdh_mismatch:
            m = pdh_mismatch[0]
            print(f"  ✅ PASS: Detected mismatch at {m['field_path']}")
            print(f"     local={m['local_value']} webui={m['webui_value']} diff={m['diff']}")
        else:
            print("  ❌ FAIL: Did NOT detect the corrupted LT.pdh!")
            print("  All mismatches found:")
            for m in mismatches[:10]:
                print(f"     {m['field_path']}: local={m['local_value']} webui={m['webui_value']}")
finally:
    # Restore original
    shutil.move(str(BACKUP), str(LOOKUP))
    print("  (Restored original lookup table)")

# ── Test 3: Corrupt a count value and verify detection ──
print()
print("=" * 60)
print("TEST 3: Corrupt samples count — should MISMATCH")
print("=" * 60)

shutil.copy2(LOOKUP, BACKUP)
try:
    with open(LOOKUP, "r", encoding="utf-8") as f:
        d = json.load(f)
    original_samples = d["tables"]["NY1"]["LF|LF"]["samples"]
    d["tables"]["NY1"]["LF|LF"]["samples"] = original_samples + 5
    with open(LOOKUP, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2, ensure_ascii=False)
    print(f"  Corrupted samples: {original_samples} -> {original_samples + 5}")

    data = run_json_validator()
    if data and data.get("results"):
        r = data["results"][0]
        mismatches = [fc for fc in r["field_comparisons"] if fc["status"] == "mismatch"]
        count_mismatch = [m for m in mismatches if m["field_path"] == "count"]
        if count_mismatch:
            m = count_mismatch[0]
            print(f"  ✅ PASS: Detected count mismatch: local={m['local_value']} webui={m['webui_value']}")
        else:
            print(f"  ❌ FAIL: Did NOT detect corrupted count!")
            print(f"  Mismatches: {len(mismatches)}")
            for m in mismatches[:5]:
                print(f"     {m['field_path']}: local={m['local_value']} webui={m['webui_value']}")
finally:
    shutil.move(str(BACKUP), str(LOOKUP))
    print("  (Restored original lookup table)")

# ── Test 4: Corrupt a price_stats value and verify detection ──
print()
print("=" * 60)
print("TEST 4: Corrupt price_stats LT.h_mode — should MISMATCH")
print("=" * 60)

shutil.copy2(LOOKUP, BACKUP)
try:
    with open(LOOKUP, "r", encoding="utf-8") as f:
        d = json.load(f)
    original = d["tables"]["NY1"]["LF|LF"]["price_stats"]["LT"]["h_mode"]
    d["tables"]["NY1"]["LF|LF"]["price_stats"]["LT"]["h_mode"] = original + 0.5
    with open(LOOKUP, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2, ensure_ascii=False)
    print(f"  Corrupted LT.h_mode: {original} -> {original + 0.5}")

    data = run_json_validator()
    if data and data.get("results"):
        r = data["results"][0]
        mismatches = [fc for fc in r["field_comparisons"] if fc["status"] == "mismatch"]
        hmode_mismatch = [m for m in mismatches if "price_stats.LT.h_mode" in m["field_path"]]
        if hmode_mismatch:
            m = hmode_mismatch[0]
            print(f"  ✅ PASS: Detected h_mode mismatch: local={m['local_value']} webui={m['webui_value']}")
        else:
            print(f"  ❌ FAIL: Did NOT detect corrupted h_mode!")
            for m in mismatches[:5]:
                print(f"     {m['field_path']}: local={m['local_value']} webui={m['webui_value']}")
finally:
    shutil.move(str(BACKUP), str(LOOKUP))
    print("  (Restored original lookup table)")

print()
print("=" * 60)
print("SUMMARY")
print("=" * 60)
print("If all 4 tests show PASS, the validator is correctly detecting mismatches.")