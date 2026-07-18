"""Check if the API count field matches the API distribution total for the 4 mismatched filters."""
import json
import urllib.request

API = "http://127.0.0.1:8000"

FILTERS = [
    ("LF|LT", {"Asia": "Long False", "London": "Long True"}),
    ("LF|T|LT|F", {"Asia": "Long False", "London": "Long True"}, {"London": "No"}),
    ("LT|ST", {"Asia": "Long True", "London": "Short True"}),
    ("LT|T|ST|T", {"Asia": "Long True", "London": "Short True"}, {"Asia": "Yes", "London": "Yes"}),
]

for item in FILTERS:
    filter_key = item[0]
    filters = item[1]
    broken = item[2] if len(item) > 2 else {}

    req = urllib.request.Request(
        f"{API}/stats/filtered-stats",
        data=json.dumps({
            "ticker": "NQ1",
            "target_session": "NY1",
            "filters": filters,
            "broken_filters": broken,
            "intra_state": "Any",
        }).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    result = json.loads(urllib.request.urlopen(req, timeout=30).read())
    count = result.get("count", 0)
    dist = result.get("distribution", {})
    dist_total = sum(dist.values())
    match = "MATCH" if count == dist_total else "MISMATCH"
    print(f"{filter_key}: count={count}, dist_total={dist_total} ({dist}) -> {match}")