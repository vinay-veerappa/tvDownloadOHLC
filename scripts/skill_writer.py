"""
skill_writer.py — the only CLI that persists proposed skills into .agent/skills/.

Convention, not a filesystem gate (design §4.3 + §9). The safety rail is dedupe
+ human approval + this single named CLI.

Usage:
    python scripts/skill_writer.py --name my-skill --source path/to/draft.md
    python scripts/skill_writer.py --name my-skill --source -  # read from stdin
"""
from __future__ import annotations

import argparse
import os
import re
import sys

SKILLS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".agent", "skills")
SKILL_NAMES_FILE = os.path.join(SKILLS_DIR, "_skill_names.txt")

CM_SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           ".agent", "skills", "context_manager", "scripts")
sys.path.insert(0, CM_SCRIPTS)


def _read_skill_names() -> set[str]:
    """Read _skill_names.txt, tolerating a UTF-8 BOM."""
    if not os.path.exists(SKILL_NAMES_FILE):
        return set()
    with open(SKILL_NAMES_FILE, "r", encoding="utf-8-sig") as f:
        return {line.strip() for line in f if line.strip()}


def _append_skill_name(slug: str) -> None:
    existing = _read_skill_names()
    if slug in existing:
        return
    with open(SKILL_NAMES_FILE, "a", encoding="utf-8") as f:
        f.write(f"{slug}\n")


def _inject_front_matter(content: str, slug: str) -> str:
    """Ensure the markdown has a front-matter block containing name and description."""
    stripped = content.strip()
    if not stripped.startswith("---"):
        return f"---\nname: {slug}\ndescription: Procedure distilled from outcomes.\n---\n\n{content}"

    # Proper front-matter extraction: ---\n...\n---
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", stripped, re.DOTALL)
    if not match:
        # Malformed front-matter: treat the whole content as body and prepend a new block.
        return f"---\nname: {slug}\ndescription: Procedure distilled from outcomes.\n---\n\n{content}"

    fm = match.group(1)
    body = stripped[match.end():]
    if "name:" not in fm:
        fm = f"name: {slug}\n{fm}"
    if "description:" not in fm:
        fm = f"{fm}\ndescription: Procedure distilled from outcomes."
    return f"---\n{fm}\n---\n\n{body}"


def write_skill(name: str, content: str) -> str:
    """Write content to .agent/skills/<name>/SKILL.md, append name to _skill_names.txt."""
    slug = name.strip().lower().replace(" ", "-")
    if not slug:
        raise ValueError("name must not be empty")

    skill_dir = os.path.join(SKILLS_DIR, slug)
    os.makedirs(skill_dir, exist_ok=True)
    skill_md = os.path.join(skill_dir, "SKILL.md")

    content = _inject_front_matter(content, slug)

    with open(skill_md, "w", encoding="utf-8") as f:
        f.write(content)

    _append_skill_name(slug)

    # mark process_queue item approved if we can find it
    try:
        from store_schema import get_db_connection, approve_queue_item
        conn = get_db_connection()
        try:
            rows = conn.execute(
                "SELECT id, payload FROM process_queue WHERE type = 'skill_proposal' AND status = 'proposed' ORDER BY created_at DESC LIMIT 5"
            ).fetchall()
            for r in rows:
                if slug in (r["payload"] or ""):
                    approve_queue_item(conn, r["id"])
                    break
        finally:
            conn.close()
    except Exception:
        pass  # queue update is best-effort, not blocking

    return skill_md


def main():
    parser = argparse.ArgumentParser(description="Persist a proposed SKILL.md into .agent/skills/.")
    parser.add_argument("--name", required=True, help="skill name (slug)")
    parser.add_argument("--source", required=True, help="path to draft markdown, or '-' for stdin")
    args = parser.parse_args()

    if args.source == "-":
        content = sys.stdin.read()
    else:
        if not os.path.isfile(args.source):
            print(f"Error: source file not found: {args.source}")
            return 1
        with open(args.source, "r", encoding="utf-8") as f:
            content = f.read()

    path = write_skill(args.name, content)
    print(f"Skill persisted: {path}")
    print(f"Name '{args.name.strip().lower().replace(' ', '-')}' appended to _skill_names.txt")
    return 0


if __name__ == "__main__":
    sys.exit(main())