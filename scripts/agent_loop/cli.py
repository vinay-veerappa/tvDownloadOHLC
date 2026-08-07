"""
cli.py
======
Entry point.  python -m scripts.agent_loop --help

Any agent that can run a shell command can drive this: there is no interactive
mode and no hidden state. Every decision lands in logs/agent_loop/<TICKET>/ and
logs/agent_loop/ledger.jsonl.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import profiles, regions, workspace
from .loop import run_ticket

REPO = Path(__file__).resolve().parents[2]


def _list(tickets, profile) -> int:
    """Confirm every ticket's regions still resolve against the current tree.

    Worth running before any paid work: an anchor that stopped resolving after
    an unrelated commit is much cheaper to find here than in round 1.
    """
    from . import gates

    bad = 0
    for t in tickets:
        files = sorted({r["file"] for r in t["regions"]})
        g = gates.check_protected_paths(files, profile.protected or gates.DEFAULT_PROTECTED)
        flag = "" if g.ok else "  [REFUSED: targets the verifier]"
        print(f"{t['id']:<5} {t['title']}{flag}")
        for spec in t["regions"]:
            try:
                r = regions.extract(REPO, [spec])[0]
                print(f"      OK   {r.id:<24} {r.file} {r.lines_1based}")
            except regions.RegionError as exc:
                bad += 1
                print(f"      FAIL {spec['id']:<24} {exc}")
    return 1 if bad else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m scripts.agent_loop")
    ap.add_argument("--tickets", default="scripts/agent_loop/tickets_p0.json")
    ap.add_argument("--ticket", action="append", help="ticket id (repeatable); default all")
    ap.add_argument("--profile", default="nt8-riskguard")
    ap.add_argument("--implementer", default="kimi-k2.7-code:cloud")
    ap.add_argument(
        "--reviewers",
        default="glm-5.2:cloud,deepseek-v4-pro:cloud",
        help="comma-separated panel; verdict is the worst returned, APPROVE must be unanimous. "
        "Prefix a model with anthropic:/openai:/ollama: to pick a backend.",
    )
    ap.add_argument("--max-rounds", type=int, default=4)
    ap.add_argument("--apply", action="store_true", help="promote an approved patch into the live tree")
    ap.add_argument(
        "--allow-unapproved",
        action="store_true",
        help="arbiter override: export/promote even without unanimous APPROVE",
    )
    ap.add_argument("--resume-raw", default="", help="reuse an rN_impl_raw.txt as round 1")
    ap.add_argument("--orchestrator-note", default="", help="authoritative directive; outranks reviewers")
    ap.add_argument("--panel-deadline", type=int, default=1800, help="wall-clock seconds for the whole panel")
    ap.add_argument("--keep-worktree", action="store_true", help="leave the worktree for post-mortem")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--prune", action="store_true", help="remove worktrees left by crashed runs")
    args = ap.parse_args(argv)

    if args.prune:
        stale = workspace.list_stale(REPO)
        for p in stale:
            print(f"  removing {p}")
            workspace.prune(REPO, p)
        workspace.prune(REPO)
        print(f"pruned {len(stale)} worktree(s)")
        return 0

    profile = profiles.get(args.profile)
    spec = json.loads(Path(args.tickets).read_text(encoding="utf-8"))
    tickets = spec["tickets"]

    if args.list:
        return _list(tickets, profile)

    wanted = args.ticket or [t["id"] for t in tickets]
    results = []
    for t in tickets:
        if t["id"] not in wanted:
            continue
        print(f"\n=== {t['id']}: {t['title']}")
        try:
            results.append(
                run_ticket(
                    REPO,
                    t,
                    profile,
                    args.implementer,
                    [m.strip() for m in args.reviewers.split(",") if m.strip()],
                    max_rounds=args.max_rounds,
                    apply=args.apply,
                    allow_unapproved=args.allow_unapproved,
                    resume_raw=args.resume_raw,
                    orchestrator_note=args.orchestrator_note,
                    panel_deadline=args.panel_deadline,
                    keep_worktree=args.keep_worktree,
                )
            )
        except Exception as exc:  # noqa: BLE001 - a driver must report, not crash
            print(f"  ERROR {t['id']}: {type(exc).__name__}: {exc}")
            results.append({"ticket": t["id"], "final_verdict": f"ERROR: {exc}", "applied": False})

    print("\n==== SUMMARY ====")
    total = 0.0
    for r in results:
        total += r.get("cost_usd", 0.0) or 0.0
        print(f"{r['ticket']:<5} {r.get('final_verdict','?'):<22} applied={r.get('applied')}")
    if total:
        print(f"total cost ${total:.4f}")
    # Non-zero when nothing was approved, so CI and wrapper scripts can branch.
    return 0 if any(r.get("final_verdict") == "APPROVE" for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
