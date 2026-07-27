#!/usr/bin/env python3
"""
Persist the codebase-memory-mcp default_project setting.

The CLI `config set default_project` command does NOT reliably persist to the
_config.db on disk (writes to an in-memory/ephemeral store). This script writes
directly to the on-disk SQLite config DB so the value survives MCP restarts.

Usage:
    python scripts/utils/persist_mcp_default_project.py
    python scripts/utils/persist_mcp_default_project.py --project c-Users-vinay-tvDownloadOHLC
    python scripts/utils/persist_mcp_default_project.py --verify
"""
import sqlite3
import os
import sys
import argparse

DEFAULT_PROJECT = "c-Users-vinay-tvDownloadOHLC"
CONFIG_DB = os.path.expanduser(r"~\.cache\codebase-memory-mcp\_config.db")


def get_rows(conn):
    return list(conn.execute("SELECT key, value FROM config ORDER BY key"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=DEFAULT_PROJECT, help="project slug to set")
    ap.add_argument("--verify", action="store_true", help="just print current rows")
    args = ap.parse_args()

    if not os.path.exists(CONFIG_DB):
        print(f"ERROR: config db not found at {CONFIG_DB}", file=sys.stderr)
        print("Run the codebase-memory-mcp server once first to initialize it.", file=sys.stderr)
        return 1

    conn = sqlite3.connect(CONFIG_DB)
    try:
        if args.verify:
            rows = get_rows(conn)
            print(f"config db: {CONFIG_DB}")
            print(f"rows ({len(rows)}):")
            for k, v in rows:
                print(f"  {k} = {v}")
            return 0

        rows_before = dict(get_rows(conn))
        print(f"Before: {rows_before}")

        conn.execute(
            "INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)",
            ("default_project", args.project),
        )
        conn.commit()

        rows_after = get_rows(conn)
        print(f"After: {dict(rows_after)}")

        if dict(rows_after).get("default_project") == args.project:
            print(f"SUCCESS: default_project = {args.project} persisted to disk")
            return 0
        else:
            print("ERROR: value did not persist", file=sys.stderr)
            return 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())