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


def _review(args, profile) -> int:
    """Adversarial review of already-written code. Reports; never edits.

    Exit code is 0 when the run PRODUCED A VERDICT, not when the code is
    approved -- review mode is advisory and a non-zero exit would invite
    wrapper scripts to treat it as a gate it is not.
    """
    from . import gates, review_mode

    if not args.review_base:
        print("--mode review needs --review-base (e.g. --review-base HEAD~1)")
        return 2

    intent = args.review_intent
    if args.review_intent_file:
        intent = Path(args.review_intent_file).read_text(encoding="utf-8")

    gate_summary = ""
    if args.review_verify:
        # Reviewers used to waste findings asserting the code did not compile.
        # Telling them the truth is cheaper than letting them guess.
        print("  verifying build + tests before review ...")
        b = gates.check_compile(profile.build_cmd, REPO)
        t = gates.run_tests(profile.test_cmd, REPO)
        gate_summary = (
            f"build: {'PASS' if b.ok else 'FAIL'} ({b.summary})\n"
            f"tests: {t.passed} passed, {len(t.failures)} failed"
            f"{'' if t.reached_results else ' (RUNNER DID NOT REACH RESULTS - treat as unknown)'}"
        )
        print("  " + gate_summary.replace("\n", "\n  "))

    try:
        review_mode.run_review(
            REPO,
            base=args.review_base,
            head=args.review_head,
            paths=args.review_paths,
            profile=profile,
            reviewers=[m.strip() for m in args.reviewers.split(",") if m.strip()],
            arbiter_model=args.arbiter,
            intent=intent,
            title=args.review_title,
            gate_summary=gate_summary,
            orchestrator_note=args.orchestrator_note,
            panel_deadline=args.panel_deadline,
        )
    except review_mode.ReviewError as exc:
        print(f"  REVIEW ERROR: {exc}")
        return 2
    return 0


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
    ap.add_argument(
        "--arbiter",
        default="glm-5.2:cloud",
        help="model that rules on reviewer findings. Wants to be stronger than the panel and "
        "from a different family -- anthropic:claude-opus-5 is the natural choice where a key "
        "is available. Pass '' to disable arbitration (every finding then blocks, which is the "
        "behaviour that failed to converge on T2).",
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

    # ---- modes -----------------------------------------------------------
    # `patch` is the original loop: an implementer edits declared regions.
    # `review` has no implementer at all -- it puts an already-written diff in
    # front of the panel and arbiter. `create` (new files) is designed but not
    # built; see AGENT_PATCH_LOOP.md 9.
    ap.add_argument("--mode", choices=("patch", "review"), default="patch")
    ap.add_argument("--review-base", default="", help="review mode: base ref (e.g. main, HEAD~3)")
    ap.add_argument("--review-head", default="HEAD", help="review mode: head ref")
    ap.add_argument(
        "--review-paths", nargs="*", default=[],
        help="review mode: limit the diff to these paths",
    )
    ap.add_argument("--review-intent", default="", help="review mode: what the change claims to do")
    ap.add_argument(
        "--review-intent-file", default="",
        help="review mode: read the intent from a file (e.g. the commit message or a plan section)",
    )
    ap.add_argument("--review-title", default="", help="review mode: label for the artifacts")
    ap.add_argument(
        "--review-verify", action="store_true",
        help="review mode: run the profile's build+test first so the panel is told the true "
        "gate state instead of guessing at it",
    )
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

    if args.mode == "review":
        return _review(args, profile)

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
                    arbiter_model=args.arbiter,
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
