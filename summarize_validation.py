"""Summarize validation results from JSON output."""
import json
import sys

data = json.load(sys.stdin)
results = data["results"]
passed = sum(1 for r in results if r["overall_status"] == "✅")
failed = sum(1 for r in results if r["overall_status"] == "⚠️")
print(f"Total: {len(results)}, Passed: {passed}, Failed: {failed}")
print()

# Collect all unique mismatch field paths
all_mismatch_fields = set()
for r in results:
    if r["overall_status"] != "✅":
        for fc in r["field_comparisons"]:
            if fc["status"] == "⚠️":
                all_mismatch_fields.add(fc["field_path"].split(".")[0])

print(f"Mismatch categories: {sorted(all_mismatch_fields)}")
print()

# Show only failures with their mismatched fields
for r in results:
    if r["overall_status"] != "✅":
        mismatches = [fc for fc in r["field_comparisons"] if fc["status"] == "⚠️"]
        print(f"FAIL: {r['filter_key']} ({r['local_count']} days) - {len(mismatches)} mismatches")
        for m in mismatches[:5]:
            print(f"  {m['field_path']}: local={m['local_value']} lookup={m['webui_value']} diff={m['diff']}")
        if len(mismatches) > 5:
            print(f"  ... and {len(mismatches)-5} more")
        print()