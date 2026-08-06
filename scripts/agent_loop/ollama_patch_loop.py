"""
ollama_patch_loop.py
====================
Implement -> review -> revise loop over Ollama (local or cloud-routed) models for
surgical, region-scoped source edits.

Design constraints:
  * The loop NEVER invents file paths or line numbers. Regions are located by C#
    method signature and closed by brace matching, so edits stay surgical and
    line numbers cannot drift between tickets.
  * The implementer returns a full replacement for each named region inside
    explicit markers. No unified diffs (models get hunk offsets wrong).
  * The reviewer is a different model family, sees the ORIGINAL region plus the
    proposed replacement, and must return a machine-readable verdict.
  * Applying is a separate, explicit step (--apply). A dry run writes artifacts
    only, so the orchestrator arbitrates before anything touches the tree.

Usage:
  python -m scripts.agent_loop.ollama_patch_loop --tickets scripts/agent_loop/tickets_p0.json --list
  python -m scripts.agent_loop.ollama_patch_loop --tickets ... --ticket T1            # dry run
  python -m scripts.agent_loop.ollama_patch_loop --tickets ... --ticket T1 --apply    # write files
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO = Path(__file__).resolve().parents[2]
ARTIFACT_ROOT = REPO / "logs" / "ollama_loop"

raw_host = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
if not raw_host.startswith("http"):
    raw_host = f"http://{raw_host}"
raw_host = raw_host.replace("0.0.0.0", "127.0.0.1")
if raw_host.count(":") == 1:
    raw_host = f"{raw_host}:11434"
OLLAMA_HOST = raw_host

BLOCK_RE = re.compile(
    r"<<<BLOCK\s+id=\"(?P<id>[^\"]+)\"\s*>>>\r?\n(?P<body>.*?)<<<END\s+id=\"(?P=id)\"\s*>>>",
    re.DOTALL,
)


# --------------------------------------------------------------------------
# Ollama transport
# --------------------------------------------------------------------------
def chat(
    model: str,
    messages: List[Dict[str, str]],
    temperature: float = 0.1,
    timeout: int = 900,
    num_ctx: int = 32768,
) -> str:
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"temperature": temperature, "num_ctx": num_ctx},
    }
    req = urllib.request.Request(
        f"{OLLAMA_HOST}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data.get("message", {}).get("content", "") or ""


# --------------------------------------------------------------------------
# Region location (C# brace matching, comment/string aware enough for our files)
# --------------------------------------------------------------------------
def _strip_code(line: str) -> str:
    """Remove // comments and string/char literal bodies so brace counting is safe."""
    out, i, n = [], 0, len(line)
    while i < n:
        c = line[i]
        if c == "/" and i + 1 < n and line[i + 1] == "/":
            break
        if c == '"':
            i += 1
            while i < n:
                if line[i] == "\\":
                    i += 2
                    continue
                if line[i] == '"':
                    i += 1
                    break
                i += 1
            continue
        if c == "'":
            i += 1
            while i < n:
                if line[i] == "\\":
                    i += 2
                    continue
                if line[i] == "'":
                    i += 1
                    break
                i += 1
            continue
        out.append(c)
        i += 1
    return "".join(out)


def find_region(lines: List[str], anchor: str, kind: str = "method") -> Tuple[int, int]:
    """
    Locate a region by unique anchor. Plain anchors match as a substring; an anchor
    prefixed with "re:" is treated as a regular expression searched against each line
    (needed when one declaration is a prefix of another, e.g. AccountState vs
    AccountStateSnapshot).
      kind="method"/"block": anchor line .. matching closing brace (inclusive)
      kind="line":           the anchor line only
    Returns 0-based inclusive (start, end). Raises if the anchor is not unique.
    """
    if anchor.startswith("re:"):
        pat = re.compile(anchor[3:])
        hits = [i for i, ln in enumerate(lines) if pat.search(ln)]
    else:
        hits = [i for i, ln in enumerate(lines) if anchor in ln]
    if not hits:
        raise LookupError(f"anchor not found: {anchor!r}")
    if len(hits) > 1:
        raise LookupError(f"anchor not unique ({len(hits)} hits): {anchor!r}")
    start = hits[0]
    if kind == "line":
        return start, start

    depth = 0
    seen_open = False
    for i in range(start, len(lines)):
        code = _strip_code(lines[i])
        for ch in code:
            if ch == "{":
                depth += 1
                seen_open = True
            elif ch == "}":
                depth -= 1
                if seen_open and depth == 0:
                    return start, i
    raise LookupError(f"unbalanced braces from anchor: {anchor!r}")


def extract_regions(ticket: Dict[str, Any]) -> List[Dict[str, Any]]:
    regions = []
    for spec in ticket["regions"]:
        path = REPO / spec["file"]
        lines = path.read_text(encoding="utf-8").splitlines()
        start, end = find_region(lines, spec["anchor"], spec.get("kind", "method"))
        regions.append(
            {
                "id": spec["id"],
                "file": spec["file"],
                "path": path,
                "anchor": spec["anchor"],
                "kind": spec.get("kind", "method"),
                "start": start,
                "end": end,
                "text": "\n".join(lines[start : end + 1]),
                "note": spec.get("note", ""),
            }
        )
    return regions


# --------------------------------------------------------------------------
# Prompting
# --------------------------------------------------------------------------
IMPLEMENTER_SYSTEM = """You are a senior C# engineer hardening a NinjaTrader 8 AddOn that manages
real money on funded futures accounts. You make surgical, minimal, provably-correct edits.

HARD CONSTRAINTS (violating any of these fails review):
1. Target C# 8.0 / .NET Framework 4.8 AND a net8.0 test build. No records, no
   target-typed new, no file-scoped namespaces, no raw string literals, no ranges/indices.
2. The file compiles under BOTH `#if TESTING` (net8.0, NinjaTrader stubs) and the real
   NT8 build. If you touch code inside a `#if`/`#else` block, preserve the structure.
3. NEVER call Account.Flatten / Account.Cancel / Account.Submit / Account.CreateOrder while
   holding the _stateLock. Collect intent under lock, execute after releasing it.
4. ASCII only in string literals and comments. No emoji, no smart quotes, no box drawing.
5. Do not rename existing public/internal members, do not change existing method signatures
   that callers depend on, and do not delete existing behaviour that is not part of the ticket.
6. Preserve the existing brace style, 4-space indentation, and the exact leading indentation
   of the first line of each region you return.
7. Fail closed: if a safety precondition cannot be verified, take the conservative action
   (flatten / block / skip the copy), never the permissive one.

OUTPUT FORMAT - obey exactly, no prose outside the blocks:
For every region you were given, emit one block, even if unchanged:

<<<BLOCK id="REGION_ID">>>
...the complete replacement text for that region, first line to last line...
<<<END id="REGION_ID">>>

After all blocks, emit exactly one:
<<<NOTES>>>
- bullet list: what changed per region and why, plus any new config keys or fields you added
<<<END NOTES>>>
"""

REVIEWER_SYSTEM = """You are an adversarial code reviewer for safety-critical trading software.
You are reviewing a proposed patch to a NinjaTrader 8 risk-guard AddOn that protects real funded
accounts. Assume the implementer is confident and wrong. Your job is to find the case where this
patch loses money or leaves a position unprotected.

Check, in priority order:
1. CORRECTNESS OF THE FIX: does it actually close the described defect, in every path?
2. NEW NAKED-RISK PATHS: any path where a position ends up with no covering stop, or a stop
   larger than the position (which flips the position when it triggers).
3. LOCK DISCIPLINE: any Account.Flatten/Cancel/Submit/CreateOrder reachable while _stateLock
   is held; any new lock ordering.
4. RACE CONDITIONS: state written after an async submit; event handlers that can observe a
   half-updated FSM; timers armed twice or never disposed.
5. COMPILE BREAKS: C# 8.0 / net48 + net8.0-with-stubs compatibility, missing fields, wrong
   types, non-ASCII, `#if` structure damage.
6. REGRESSIONS: existing behaviour or existing tests that this would break.

Be specific. Cite the offending line text. Do not restate the ticket. Do not praise.

OUTPUT FORMAT - obey exactly:
<<<VERDICT>>>
APPROVE | REVISE | REJECT
<<<END VERDICT>>>
<<<FINDINGS>>>
- [BLOCKER|MAJOR|MINOR] region_id: what is wrong, quoting the line, and the concrete failure case
(write "- NONE" if you found nothing at that severity)
<<<END FINDINGS>>>
<<<REQUIRED>>>
- imperative instructions the implementer must apply verbatim to reach APPROVE
(write "- NONE" if APPROVE)
<<<END REQUIRED>>>
"""


def build_implement_prompt(ticket: Dict[str, Any], regions: List[Dict[str, Any]]) -> str:
    parts = [
        f"# TICKET {ticket['id']}: {ticket['title']}",
        "",
        "## Defect",
        ticket["defect"].strip(),
        "",
        "## Required change",
        ticket["spec"].strip(),
        "",
    ]
    if ticket.get("context"):
        parts += ["## Additional context you must respect", ticket["context"].strip(), ""]
    parts.append("## Regions to rewrite")
    for r in regions:
        parts += [
            "",
            f"### REGION id=\"{r['id']}\"  file={r['file']}  lines {r['start']+1}-{r['end']+1}",
            (f"Purpose: {r['note']}" if r["note"] else ""),
            "```csharp",
            r["text"],
            "```",
        ]
    parts += [
        "",
        "Return one block per region id above, in the same order. No other output.",
    ]
    return "\n".join(p for p in parts if p is not None)


def build_review_prompt(
    ticket: Dict[str, Any],
    regions: List[Dict[str, Any]],
    blocks: Dict[str, str],
    notes: str,
    orchestrator_note: str = "",
) -> str:
    parts = [
        f"# TICKET {ticket['id']}: {ticket['title']}",
        "",
        "## Defect the patch claims to fix",
        ticket["defect"].strip(),
        "",
        "## Required change",
        ticket["spec"].strip(),
        "",
    ]
    if orchestrator_note:
        parts += [
            "## ORCHESTRATOR DIRECTIVE - AUTHORITATIVE",
            "The human arbiter issued the directive below AFTER an earlier review round. It "
            "SUPERSEDES the ticket text above wherever they conflict, and it records decisions "
            "you must not re-litigate. Do NOT raise a finding that contradicts it, and do NOT "
            "report directive-compliant code as a spec violation. If the patch obeys the "
            "directive, that part is correct by definition.",
            "",
            orchestrator_note.strip(),
            "",
        ]
    parts += [
        "## Implementer notes",
        notes.strip() or "(none)",
        "",
    ]
    for r in regions:
        parts += [
            "",
            f"## REGION \"{r['id']}\" ({r['file']})",
            "### BEFORE",
            "```csharp",
            r["text"],
            "```",
            "### AFTER (proposed)",
            "```csharp",
            blocks.get(r["id"], "(MISSING - implementer did not return this region)"),
            "```",
        ]
    return "\n".join(parts)


# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------
def parse_blocks(text: str) -> Tuple[Dict[str, str], str]:
    blocks = {m.group("id"): m.group("body").rstrip("\n") for m in BLOCK_RE.finditer(text)}
    notes = ""
    m = re.search(r"<<<NOTES>>>\r?\n(.*?)<<<END NOTES>>>", text, re.DOTALL)
    if m:
        notes = m.group(1).strip()
    return blocks, notes


def parse_review(text: str) -> Dict[str, Any]:
    def section(name: str) -> str:
        m = re.search(rf"<<<{name}>>>\r?\n(.*?)<<<END {name}>>>", text, re.DOTALL)
        return m.group(1).strip() if m else ""

    verdict_raw = section("VERDICT").upper()
    verdict = "REVISE"
    for candidate in ("REJECT", "REVISE", "APPROVE"):
        if candidate in verdict_raw:
            verdict = candidate
            break
    findings = section("FINDINGS")
    required = section("REQUIRED")
    blockers = [
        ln
        for ln in findings.splitlines()
        if "[BLOCKER]" in ln.upper() or "[MAJOR]" in ln.upper()
    ]
    return {
        "verdict": verdict,
        "findings": findings,
        "required": required,
        "blocker_count": len(blockers),
        "raw": text,
    }


# --------------------------------------------------------------------------
# Validation gates the orchestrator relies on
# --------------------------------------------------------------------------
LOCK_RISK_RE = re.compile(r"\.(Flatten|Cancel|Submit|CreateOrder)\s*\(")


def static_checks(regions: List[Dict[str, Any]], blocks: Dict[str, str]) -> List[str]:
    problems: List[str] = []
    for r in regions:
        rid = r["id"]
        if rid not in blocks:
            problems.append(f"{rid}: missing from model output")
            continue
        body = blocks[rid]
        if not body.strip():
            problems.append(f"{rid}: empty replacement")
            continue
        try:
            body.encode("ascii")
        except UnicodeEncodeError as exc:
            problems.append(f"{rid}: non-ASCII output ({exc})")
        opens = sum(_strip_code(ln).count("{") for ln in body.splitlines())
        closes = sum(_strip_code(ln).count("}") for ln in body.splitlines())
        if opens != closes:
            problems.append(f"{rid}: unbalanced braces ({opens} open vs {closes} close)")
        orig_indent = len(r["text"]) - len(r["text"].lstrip())
        new_indent = len(body) - len(body.lstrip())
        if orig_indent != new_indent:
            problems.append(
                f"{rid}: leading indentation changed ({orig_indent} -> {new_indent})"
            )
        if "<<<" in body:
            problems.append(f"{rid}: marker leaked into body")
        n_if = len(re.findall(r"^\s*#if", body, re.MULTILINE))
        n_endif = len(re.findall(r"^\s*#endif", body, re.MULTILINE))
        if n_if != n_endif:
            problems.append(f"{rid}: unbalanced #if/#endif ({n_if}/{n_endif})")
    return problems


def lock_scope_report(regions: List[Dict[str, Any]], blocks: Dict[str, str]) -> List[str]:
    """Flag broker calls that appear inside a lock(_stateLock) scope in the new text."""
    flags: List[str] = []
    for r in regions:
        body = blocks.get(r["id"])
        if not body:
            continue
        depth_at_lock: Optional[int] = None
        depth = 0
        for ln in body.splitlines():
            code = _strip_code(ln)
            if depth_at_lock is None and re.search(r"lock\s*\(\s*_stateLock\s*\)", code):
                depth_at_lock = depth
            depth += code.count("{") - code.count("}")
            if depth_at_lock is not None:
                if depth <= depth_at_lock:
                    depth_at_lock = None
                elif LOCK_RISK_RE.search(code):
                    flags.append(f"{r['id']}: broker call under _stateLock -> {ln.strip()}")
    return flags


# --------------------------------------------------------------------------
# Apply
# --------------------------------------------------------------------------
def run_build(build_cmd: str, timeout: int = 900) -> Tuple[bool, str]:
    """Compile gate. The compiler catches every missing symbol / bad C# version the
    model invents, which model review demonstrably does not."""
    import subprocess

    proc = subprocess.run(
        build_cmd, shell=True, cwd=str(REPO), capture_output=True, text=True, timeout=timeout
    )
    out = (proc.stdout or "") + "\n" + (proc.stderr or "")
    return proc.returncode == 0, out


def build_error_digest(output: str, limit: int = 40) -> str:
    lines = [
        ln.strip()
        for ln in output.splitlines()
        if re.search(r"\b(error|warning)\s+[A-Z]{2}\d{3,}", ln)
    ]
    seen, uniq = set(), []
    for ln in lines:
        if ln not in seen:
            seen.add(ln)
            uniq.append(ln)
    return "\n".join(uniq[:limit]) or output[-4000:]


def git_revert(files: List[str]) -> None:
    import subprocess

    for f in files:
        subprocess.run(["git", "checkout", "--", f], cwd=str(REPO), capture_output=True)


def apply_blocks(regions: List[Dict[str, Any]], blocks: Dict[str, str]) -> List[str]:
    """Apply per file, bottom-up, so earlier line numbers stay valid."""
    touched: List[str] = []
    by_file: Dict[Path, List[Dict[str, Any]]] = {}
    for r in regions:
        by_file.setdefault(r["path"], []).append(r)
    for path, regs in by_file.items():
        lines = path.read_text(encoding="utf-8").splitlines()
        for r in sorted(regs, key=lambda x: x["start"], reverse=True):
            body = blocks[r["id"]]
            if body.rstrip() == r["text"].rstrip():
                continue
            lines[r["start"] : r["end"] + 1] = body.splitlines()
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        touched.append(str(path.relative_to(REPO)))
    return touched


# --------------------------------------------------------------------------
# Loop
# --------------------------------------------------------------------------
def run_ticket(
    ticket: Dict[str, Any],
    implementer: str,
    reviewer: str,
    max_rounds: int,
    apply: bool,
    build_cmd: str = "",
    allow_unapproved: bool = False,
    resume_raw: str = "",
    orchestrator_note: str = "",
) -> Dict[str, Any]:
    art = ARTIFACT_ROOT / ticket["id"]
    art.mkdir(parents=True, exist_ok=True)
    regions = extract_regions(ticket)

    print(f"\n=== {ticket['id']}: {ticket['title']}")
    for r in regions:
        print(f"    region {r['id']:<22} {r['file']} lines {r['start']+1}-{r['end']+1}")

    impl_prompt = build_implement_prompt(ticket, regions)
    if orchestrator_note:
        impl_prompt += (
            "\n\n## ORCHESTRATOR DIRECTIVE (overrides the reviewer if they conflict)\n"
            + orchestrator_note.strip()
        )
    history = [
        {"role": "system", "content": IMPLEMENTER_SYSTEM},
        {"role": "user", "content": impl_prompt},
    ]
    (art / "00_implement_prompt.md").write_text(history[1]["content"], encoding="utf-8")

    result: Dict[str, Any] = {"ticket": ticket["id"], "rounds": [], "applied": False}
    blocks: Dict[str, str] = {}

    for rnd in range(1, max_rounds + 1):
        t0 = time.time()
        if rnd == 1 and resume_raw:
            # Resume an interrupted loop: reuse a candidate patch that already passed the
            # earlier gates instead of paying for the implementer rounds again. Cloud calls
            # are long enough that losing them to a session boundary is expensive.
            raw = Path(resume_raw).read_text(encoding="utf-8")
            print(f"  round 1: resumed from {resume_raw}")
        else:
            raw = chat(implementer, history)
        impl_secs = round(time.time() - t0, 1)
        if not (rnd == 1 and resume_raw):
            (art / f"r{rnd}_impl_raw.txt").write_text(raw, encoding="utf-8")
        blocks, notes = parse_blocks(raw)

        problems = static_checks(regions, blocks)
        lock_flags = lock_scope_report(regions, blocks)
        print(
            f"  round {rnd}: implement {impl_secs}s, {len(blocks)}/{len(regions)} blocks, "
            f"{len(problems)} static problems, {len(lock_flags)} lock flags"
        )

        if problems:
            feedback = (
                "Your output failed mechanical validation before review. Fix these and "
                "re-emit ALL blocks:\n" + "\n".join(f"- {p}" for p in problems)
            )
            history += [
                {"role": "assistant", "content": raw},
                {"role": "user", "content": feedback},
            ]
            result["rounds"].append(
                {"round": rnd, "stage": "static", "problems": problems, "impl_secs": impl_secs}
            )
            continue

        # --- compile gate: apply to the tree, build, then revert until a verdict exists
        if build_cmd:
            touched = apply_blocks(regions, blocks)
            t0 = time.time()
            try:
                ok, out = run_build(build_cmd)
            except Exception as exc:  # noqa: BLE001
                ok, out = False, f"build harness error: {exc}"
            build_secs = round(time.time() - t0, 1)
            (art / f"r{rnd}_build.txt").write_text(out, encoding="utf-8")
            git_revert(touched)
            print(f"           build {build_secs}s -> {'OK' if ok else 'FAILED'}")
            if not ok:
                digest = build_error_digest(out)
                result["rounds"].append(
                    {
                        "round": rnd,
                        "stage": "build",
                        "ok": False,
                        "errors": digest,
                        "impl_secs": impl_secs,
                        "build_secs": build_secs,
                    }
                )
                history += [
                    {"role": "assistant", "content": raw},
                    {
                        "role": "user",
                        "content": (
                            "Your patch DOES NOT COMPILE. You may only reference members that "
                            "already exist in the file or that you define inside the regions you "
                            "were given - you cannot rely on helpers, fields, or changed call "
                            "signatures elsewhere in the file. Compiler output:\n\n"
                            f"{digest}\n\nFix every error and re-emit ALL blocks in full."
                        ),
                    },
                ]
                continue

        t0 = time.time()
        review_raw = chat(
            reviewer,
            [
                {"role": "system", "content": REVIEWER_SYSTEM},
                {
                    "role": "user",
                    "content": build_review_prompt(
                        ticket, regions, blocks, notes, orchestrator_note
                    ),
                },
            ],
        )
        rev_secs = round(time.time() - t0, 1)
        (art / f"r{rnd}_review_raw.txt").write_text(review_raw, encoding="utf-8")
        review = parse_review(review_raw)
        print(
            f"           review {rev_secs}s -> {review['verdict']} "
            f"({review['blocker_count']} blocker/major)"
        )

        result["rounds"].append(
            {
                "round": rnd,
                "stage": "review",
                "verdict": review["verdict"],
                "blocker_count": review["blocker_count"],
                "findings": review["findings"],
                "required": review["required"],
                "lock_flags": lock_flags,
                "impl_secs": impl_secs,
                "review_secs": rev_secs,
                "notes": notes,
            }
        )

        if review["verdict"] == "APPROVE" and not lock_flags:
            result["final_verdict"] = "APPROVE"
            break

        note_block = ""
        if orchestrator_note:
            note_block = (
                "\n\nORCHESTRATOR DIRECTIVE (authoritative - overrides the reviewer where they "
                "conflict):\n" + orchestrator_note.strip()
            )
        extra = ""
        if lock_flags:
            extra = "\n\nMechanical lock-scope violations detected:\n" + "\n".join(
                f"- {f}" for f in lock_flags
            )
        history += [
            {"role": "assistant", "content": raw},
            {
                "role": "user",
                "content": (
                    f"An independent reviewer returned {review['verdict']}.\n\n"
                    f"FINDINGS:\n{review['findings']}\n\nREQUIRED CHANGES:\n{review['required']}"
                    f"{extra}{note_block}\n\nApply every required change and re-emit ALL blocks in full."
                ),
            },
        ]
    else:
        result["final_verdict"] = "MAX_ROUNDS_EXHAUSTED"

    if blocks and not static_checks(regions, blocks):
        (art / "final_blocks.json").write_text(
            json.dumps(
                {r["id"]: blocks.get(r["id"], "") for r in regions}, indent=2
            ),
            encoding="utf-8",
        )
        approved = result.get("final_verdict") == "APPROVE"
        if apply and (approved or allow_unapproved):
            result["touched"] = apply_blocks(regions, blocks)
            result["applied"] = True
            print(
                f"  APPLIED{'' if approved else ' (UNAPPROVED - orchestrator override)'} "
                f"-> {', '.join(result['touched'])}"
            )
        elif apply:
            print(
                f"  NOT APPLIED: verdict={result.get('final_verdict')} - artifacts written for "
                f"orchestrator arbitration, tree untouched"
            )
        else:
            print("  dry run: artifacts written, tree untouched")

    (art / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tickets", required=True)
    ap.add_argument("--ticket", action="append", help="ticket id (repeatable); default all")
    ap.add_argument("--implementer", default="deepseek-v4-pro:cloud")
    ap.add_argument("--reviewer", default="kimi-k2.7-code:cloud")
    ap.add_argument("--max-rounds", type=int, default=3)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument(
        "--build-cmd",
        default="dotnet build ninjatrader-addon/RiskGuardTests.csproj --nologo -v q",
        help="compile gate run after each candidate patch; set to '' to disable",
    )
    ap.add_argument(
        "--orchestrator-note",
        default="",
        help="authoritative directive from the human arbiter, injected into the initial prompt "
        "and every revision round; outranks the reviewer",
    )
    ap.add_argument(
        "--resume-raw",
        default="",
        help="path to an existing rN_impl_raw.txt to use as round 1 instead of calling the "
        "implementer (resume an interrupted loop without re-paying for it)",
    )
    ap.add_argument(
        "--allow-unapproved",
        action="store_true",
        help="orchestrator override: apply even when the reviewer did not APPROVE",
    )
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    spec = json.loads(Path(args.tickets).read_text(encoding="utf-8"))
    tickets = spec["tickets"]

    if args.list:
        for t in tickets:
            print(f"{t['id']:<5} {t['title']}")
            for r in t["regions"]:
                try:
                    lines = (REPO / r["file"]).read_text(encoding="utf-8").splitlines()
                    s, e = find_region(lines, r["anchor"], r.get("kind", "method"))
                    print(f"      OK   {r['id']:<22} {r['file']} {s+1}-{e+1}")
                except LookupError as exc:
                    print(f"      FAIL {r['id']:<22} {exc}")
        return 0

    wanted = args.ticket or [t["id"] for t in tickets]
    summary = []
    for t in tickets:
        if t["id"] not in wanted:
            continue
        try:
            res = run_ticket(
                t,
                args.implementer,
                args.reviewer,
                args.max_rounds,
                args.apply,
                build_cmd=args.build_cmd,
                allow_unapproved=args.allow_unapproved,
                resume_raw=args.resume_raw,
                orchestrator_note=args.orchestrator_note,
            )
        except Exception as exc:  # noqa: BLE001 - loop driver must report, not crash
            print(f"  ERROR {t['id']}: {type(exc).__name__}: {exc}")
            res = {"ticket": t["id"], "final_verdict": f"ERROR: {exc}", "applied": False}
        summary.append(res)

    print("\n==== SUMMARY ====")
    for res in summary:
        print(
            f"{res['ticket']:<5} {res.get('final_verdict','?'):<24} "
            f"applied={res.get('applied')}"
        )
    (ARTIFACT_ROOT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
