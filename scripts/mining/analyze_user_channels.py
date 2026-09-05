"""Categorizes user's YouTube subscriptions and maps them to strategy mining archetypes."""
import json
from pathlib import Path

DATA_DIR = Path(r"C:\Users\vinay\tvDownloadOHLC\data\strategies\raw_mined")
PROFILE_FILE = DATA_DIR / "user_youtube_profile.json"
OUTPUT_MD = DATA_DIR / "user_subscribed_channels_analysis.md"

with open(PROFILE_FILE, "r", encoding="utf-8") as f:
    profile = json.load(f)

subs = profile.get("subscriptions", [])

# Define classification rules
CATEGORY_KEYWORDS = {
    "TheStrat": ["strat", "rob smith", "broadening", "inside bar", "2-1-2", "stratalerts"],
    "Pack Trading & Market Profiling": ["pack", "daily profiler", "wargaming", "mickey", "austin", "ac trades"],
    "ICT & Smart Money Concepts": ["ict", "smc", "fvg", "fair value", "order block", "liquidity", "quarterly theory", "mmxm", "inner circle"],
    "Algo & Quantitative Systems": ["algo", "kevin davey", "backtest", "automated", "python", "quantitative", "systematic", "champion trader"],
    "Futures & Prop Firm Execution": ["futures", "es", "nq", "apex", "funded", "topstep", "order flow", "footprint", "dom", "scalping"],
    "Options & Volatility Trading": ["option", "gex", "gamma", "theta", "0dte", "credit spread", "iron condor", "volatility"],
    "Stock Scanners & Momentum": ["scanner", "stock", "screener", "momentum", "small cap", "gap", "rvol", "breakout"],
}

categorized = {cat: [] for cat in CATEGORY_KEYWORDS}
uncategorized = []

for s in subs:
    title = s.get("title", "")
    handle = s.get("handle", "")
    desc = s.get("description", "")
    full_text = f"{title} {handle} {desc}".lower()

    matched = False
    for cat, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in full_text for kw in keywords):
            categorized[cat].append(s)
            matched = True
            break
    if not matched:
        uncategorized.append(s)

lines = [
    "# User YouTube Subscriptions — Strategy Intelligence Analysis",
    "",
    f"> **Total Subscriptions Harvested**: {len(subs)} channels",
    "> **Status**: Successfully authenticated & extracted from live session cookies",
    "",
    "---",
    "",
    "## 1. Subscribed Trading Channels by Discipline",
    "",
]

for cat, channels in categorized.items():
    if not channels:
        continue
    lines.extend([
        f"### {cat} ({len(channels)} Channels)",
        "",
    ])
    for c in channels:
        handle_str = f" (`{c.get('handle')}`)" if c.get('handle') else ""
        desc_snippet = c.get('description', '').replace('\n', ' ')[:100]
        lines.append(f"* **{c.get('title')}**{handle_str}")
        if desc_snippet:
            lines.append(f"  * *Bio*: {desc_snippet}...")
    lines.append("")

if uncategorized:
    lines.extend([
        f"### Other / Unclassified Channels ({len(uncategorized)} Channels)",
        "",
    ])
    for c in uncategorized:
        handle_str = f" (`{c.get('handle')}`)" if c.get('handle') else ""
        lines.append(f"* **{c.get('title')}**{handle_str}")
    lines.append("")

OUTPUT_MD.write_text("\n".join(lines), encoding="utf-8")
print(f"Generated analysis report with {len(subs)} channels at {OUTPUT_MD}")
