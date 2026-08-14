"""
maintain_memory_db.py — CLI entrypoint for memory-store maintenance.

Runs the same routine as the `maintain_memory_store` MCP tool:
- Apply confidence decay to stale user_prefs rows.
- Prune unapproved skill proposals older than 30 days.
- Optionally re-render .agent/USER.md.

Usage:
    python .agent/skills/context_manager/scripts/maintain_memory_db.py [--dry-run] [--render]
"""
import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from store_schema import get_db_connection, maintain_store


def main():
    parser = argparse.ArgumentParser(description="Maintain the .agent/memory.db store")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
    parser.add_argument("--render", action="store_true", help="Re-render .agent/USER.md after maintenance")
    args = parser.parse_args()

    conn = get_db_connection()
    try:
        report = maintain_store(conn, render=args.render, dry_run=args.dry_run)
    finally:
        conn.close()

    print(f"dry_run={report['dry_run']}")
    print(f"decay rows affected: {report['decay']['rows_affected']}")
    for d in report["decay"]["details"]:
        print(
            f"  {d['key']}: conf {d['old_confidence']:.2f} -> {d['new_confidence']:.2f} "
            f"({d['inactive_days']}d inactive)"
        )
    print(f"pruned proposals: {report['pruned_proposals']}")
    if report["rendered_user_md"]:
        print(f"rendered: {report['rendered_user_md']}")


if __name__ == "__main__":
    main()
