#!/usr/bin/env python3
"""Generate docs/indicators/DailyNYLevels/ABBREVIATIONS.md from scripts/config/abbreviations.json.

Single source of truth is the JSON. This script renders the human-readable registry
(entries tables, conflicts, planned) so the Markdown never drifts from the JSON.

Usage:
    python -m scripts.tools.generate_abbreviations_md
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
JSON_PATH = ROOT / "scripts" / "config" / "abbreviations.json"
MD_PATH = ROOT / "docs" / "indicators" / "DailyNYLevels" / "ABBREVIATIONS.md"

CATEGORY_ORDER = [
    "price_level",
    "session",
    "options_gamma",
    "ict_structure",
    "statistics",
    "classification",
    "narrative_state",
    "trade_infra",
]


def _row(e: dict) -> str:
    legacy = ", ".join(e.get("legacy") or []) or "—"
    status = e.get("status", "active")
    return f"| `{e['abbrev']}` | {e['full']} | {e['definition']} | {legacy} | {status} |"


def _category_table(entries: list[dict]) -> str:
    lines = ["| Abbrev | Full name | Definition | Legacy | Status |", "|---|---|---|---|---|"]
    lines += [_row(e) for e in entries]
    return "\n".join(lines)


def build() -> str:
    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    entries = data["entries"]
    categories = data["categories"]
    conflicts = data["conflicts"]
    changelog = data["changelog"]
    policy = data["namingPolicy"]

    out: list[str] = []
    out.append("# Abbreviations & Nomenclature Registry")
    out.append("")
    out.append(f"**Schema version:** `{data['schemaVersion']}`")
    out.append("")
    out.append("> **Single source of truth:** `scripts/config/abbreviations.json`.")
    out.append("> This Markdown is **auto-generated** — do not edit by hand.")
    out.append("> Regenerate with `python -m scripts.tools.generate_abbreviations_md`.")
    out.append("")
    out.append("## Naming policy")
    out.append("")
    out.append(f"- **Compact form:** `{policy['compact']}`")
    out.append(f"- **Midpoint suffix:** `{policy['midSuffix']}`")
    out.append(f"- **Case:** `{policy['case']}`")
    out.append(f"- **Rule:** {policy['rule']}")
    out.append("")
    out.append("## Categories")
    out.append("")
    for cid in CATEGORY_ORDER:
        out.append(f"- **`{cid}`** — {categories[cid]}")
    out.append("")

    for cid in CATEGORY_ORDER:
        cat_entries = [e for e in entries if e["category"] == cid]
        out.append(f"## {cid}")
        out.append("")
        out.append(_category_table(cat_entries))
        out.append("")

    planned = [e for e in entries if e.get("status") == "planned"]
    if planned:
        out.append("## Planned (reserved)")
        out.append("")
        out.append("Reserved slots for concepts to be added step by step as indicators are built.")
        out.append("")
        out.append(_category_table(planned))
        out.append("")

    out.append("## Known conflicts")
    out.append("")
    out.append("| Abbrev | Meanings | Resolution | Owner |")
    out.append("|---|---|---|---|")
    for c in conflicts:
        meanings = "; ".join(c["meanings"])
        out.append(f"| `{c['abbrev']}` | {meanings} | {c['resolution']} | {c['owner']} |")
    out.append("")

    out.append("## Changelog")
    out.append("")
    out.append("| Version | Date | Note |")
    out.append("|---|---|---|")
    for c in changelog:
        out.append(f"| {c['version']} | {c['date']} | {c['note']} |")
    out.append("")

    return "\n".join(out)


def main() -> None:
    MD_PATH.parent.mkdir(parents=True, exist_ok=True)
    MD_PATH.write_text(build(), encoding="utf-8")
    print(f"Wrote {MD_PATH} ({MD_PATH.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
