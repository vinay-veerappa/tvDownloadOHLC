"""
gates.py
========
Mechanical checks a candidate patch must clear before any model opinion counts.

Ordering is deliberate and cost-ascending: the free checks run first, so a
patch that leaked a marker or invented a symbol never reaches a paid reviewer.

    protected -> static -> compile -> test -> lock-scope -> (panel) -> (arbiter)

Every gate here is deterministic. That is the point: a reviewer can be talked
out of a finding, a compiler cannot. Where a gate and the panel disagree, the
gate wins.
"""
from __future__ import annotations

import re
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set, Tuple


@dataclass
class GateResult:
    name: str
    ok: bool
    summary: str
    detail: str = ""
    secs: float = 0.0
    # Set when a gate fails in a way the implementer can act on. Fed back into
    # the next round's prompt verbatim.
    feedback: str = ""


# --------------------------------------------------------------------------
# Gate 0 - protected paths (anti reward-hacking)
# --------------------------------------------------------------------------
# The implementer is told to make the gates pass. Nothing in the loop's shape
# stops a ticket from handing it the verifier itself -- the test file, the test
# project, or the expected-failure baseline. An agent that can edit its own
# grader will eventually do so; the literature reports exactly this (deleting
# failing tests, monkey-patching the verifier) at non-trivial rates. So the
# verifier is made unreachable by construction rather than by instruction.
DEFAULT_PROTECTED = (
    "*Tests.cs",
    "*.csproj",
    "scripts/agent_loop/*",
    "logs/agent_loop/*baseline*",
)


def check_protected_paths(
    region_files: Sequence[str], protected: Sequence[str] = DEFAULT_PROTECTED
) -> GateResult:
    """Refuse a ticket whose regions overlap anything that grades the work."""
    from fnmatch import fnmatch

    hits = []
    for f in region_files:
        norm = f.replace("\\", "/")
        for pat in protected:
            if fnmatch(norm, pat) or fnmatch(Path(norm).name, pat):
                hits.append(f"{f} matches protected pattern {pat!r}")
    if hits:
        return GateResult(
            "protected",
            False,
            f"{len(hits)} region(s) target the verifier",
            "\n".join(hits),
            feedback="This ticket is malformed and must not run: it would let the "
            "patch edit the code that grades it.",
        )
    return GateResult("protected", True, f"{len(region_files)} region file(s) clear of verifier")


# --------------------------------------------------------------------------
# Gate 1 - static
# --------------------------------------------------------------------------
def check_static(regions, blocks: Dict[str, str], strip_code) -> GateResult:
    """Shape checks that need no toolchain. Cheap, so they run first."""
    problems: List[str] = []
    for r in regions:
        rid = r.id
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
        opens = sum(strip_code(ln).count("{") for ln in body.splitlines())
        closes = sum(strip_code(ln).count("}") for ln in body.splitlines())
        if opens != closes:
            problems.append(f"{rid}: unbalanced braces ({opens} open vs {closes} close)")
        orig_indent = len(r.text) - len(r.text.lstrip())
        new_indent = len(body) - len(body.lstrip())
        if orig_indent != new_indent:
            problems.append(f"{rid}: leading indentation changed ({orig_indent} -> {new_indent})")
        if "<<<" in body:
            problems.append(f"{rid}: marker leaked into body")
        n_if = len(re.findall(r"^\s*#if", body, re.MULTILINE))
        n_endif = len(re.findall(r"^\s*#endif", body, re.MULTILINE))
        if n_if != n_endif:
            problems.append(f"{rid}: unbalanced #if/#endif ({n_if}/{n_endif})")
    if problems:
        return GateResult(
            "static",
            False,
            f"{len(problems)} problem(s)",
            "\n".join(problems),
            feedback="Your output failed mechanical validation before review. Fix these "
            "and re-emit ALL blocks:\n" + "\n".join(f"- {p}" for p in problems),
        )
    return GateResult("static", True, f"{len(regions)} block(s) well-formed")


# --------------------------------------------------------------------------
# Gate 2 - compile
# --------------------------------------------------------------------------
_DIAG = re.compile(r"\b(error|warning)\s+[A-Z]{2}\d{3,}")


def _run(cmd: str, cwd: Path, timeout: int) -> Tuple[int, str]:
    proc = subprocess.run(
        cmd, shell=True, cwd=str(cwd), capture_output=True, text=True, timeout=timeout
    )
    return proc.returncode, (proc.stdout or "") + "\n" + (proc.stderr or "")


def _digest(output: str, limit: int = 40) -> str:
    seen: Set[str] = set()
    uniq: List[str] = []
    for ln in output.splitlines():
        ln = ln.strip()
        if _DIAG.search(ln) and ln not in seen:
            seen.add(ln)
            uniq.append(ln)
    return "\n".join(uniq[:limit]) or output[-4000:]


def check_compile(cmd: str, repo: Path, timeout: int = 900) -> GateResult:
    """The gate that catches every invented symbol. Model review demonstrably
    does not -- a reviewer will happily approve a call to a method that does
    not exist."""
    t0 = time.time()
    try:
        code, out = _run(cmd, repo, timeout)
    except subprocess.TimeoutExpired:
        return GateResult("compile", False, f"timed out after {timeout}s", feedback="Build timed out.")
    secs = round(time.time() - t0, 1)
    if code == 0:
        return GateResult("compile", True, "build succeeded", out, secs)
    d = _digest(out)
    return GateResult(
        "compile",
        False,
        "build FAILED",
        out,
        secs,
        feedback=(
            "Your patch DOES NOT COMPILE. You may only reference members that already "
            "exist in the file or that you define inside the regions you were given - "
            "you cannot rely on helpers, fields, or changed call signatures elsewhere "
            f"in the file. Compiler output:\n\n{d}\n\nFix every error and re-emit ALL blocks in full."
        ),
    )


# --------------------------------------------------------------------------
# Gate 3 - test, against a frozen expected-failure baseline
# --------------------------------------------------------------------------
# The suite is not green and is not meant to be: T4/T5 have failing tests
# waiting that only go green when those tickets land. A pass/fail gate would
# therefore reject every candidate. What matters is the SET of failures --
# any failure not in the baseline is a regression, and a baseline failure that
# disappears is the ticket doing its job.
_FAIL_LINE = re.compile(r"^\s*\[FAIL\]\s*(?P<msg>.+?)\s*$", re.MULTILINE)
_RESULTS = re.compile(r"RESULTS:\s*Passed\s*=\s*(\d+),\s*Failed\s*=\s*(\d+)")


@dataclass
class TestOutcome:
    failures: Set[str] = field(default_factory=set)
    passed: int = 0
    failed: int = 0
    ran: bool = False
    raw: str = ""

    @property
    def counted(self) -> bool:
        """True when the RESULTS line was reached -- i.e. the runner did not
        abort mid-way. A truncated run that happens to show no new failures is
        not evidence of anything."""
        return self.ran


def parse_tests(output: str) -> TestOutcome:
    failures = {m.group("msg") for m in _FAIL_LINE.finditer(output)}
    m = _RESULTS.search(output)
    if not m:
        return TestOutcome(failures=failures, ran=False, raw=output)
    return TestOutcome(
        failures=failures,
        passed=int(m.group(1)),
        failed=int(m.group(2)),
        ran=True,
        raw=output,
    )


def run_tests(cmd: str, repo: Path, timeout: int = 900) -> TestOutcome:
    try:
        _, out = _run(cmd, repo, timeout)
    except subprocess.TimeoutExpired:
        return TestOutcome(ran=False, raw=f"test run timed out after {timeout}s")
    return parse_tests(out)


def check_tests(
    cmd: str,
    repo: Path,
    baseline: Set[str],
    timeout: int = 900,
    expect_green: Sequence[str] = (),
) -> Tuple[GateResult, TestOutcome]:
    """Compare this run's failure set against the frozen baseline.

    `baseline` is captured once, before the first candidate is applied, and is
    never recomputed mid-run -- otherwise a patch that breaks a test would
    simply widen the baseline and pass.

    `expect_green` names the tests this ticket exists to fix. Without it the
    gate only proves NO REGRESSION, which is not the same as "the defect is
    closed": T5 reached ARBITER_SHIP with its own acceptance test still red and
    nothing in the ladder objected. Under test-first development the named
    tests ARE the ticket's contract, so failing to flip one is a gate failure,
    not a review opinion.
    """
    t0 = time.time()
    out = run_tests(cmd, repo, timeout)
    secs = round(time.time() - t0, 1)

    if not out.counted:
        return (
            GateResult(
                "test",
                False,
                "runner did not reach RESULTS (aborted or timed out)",
                out.raw[-4000:],
                secs,
                feedback="The test runner did not finish. Its output ends without a "
                "RESULTS line, so no conclusion can be drawn about your patch.",
            ),
            out,
        )

    new = sorted(out.failures - baseline)
    fixed = sorted(baseline - out.failures)
    note = f"{out.passed} passed, {out.failed} failed"
    if fixed:
        note += f", {len(fixed)} expected failure(s) now green"

    # A test named in expect_green is still failing => the ticket did not do its
    # job. Reported separately from a regression because the remedy differs: a
    # regression means "you broke something", this means "you have not finished".
    still_red = [
        t for t in expect_green
        if any(t.lower() in f.lower() for f in out.failures)
    ]
    if still_red and not new:
        return (
            GateResult(
                "test",
                False,
                f"{len(still_red)} acceptance test(s) still failing; {note}",
                "STILL FAILING (this ticket exists to make these pass):\n"
                + "\n".join(f"  - {t}" for t in still_red),
                secs,
                feedback=(
                    "Your patch does not close the defect. These tests define this "
                    "ticket's acceptance criteria and are STILL FAILING:\n\n"
                    + "\n".join(f"- {t}" for t in still_red)
                    + "\n\nThey are correct and you may not change them. Re-read the "
                    "defect and the failing assertion text, then re-emit ALL blocks in full."
                ),
            ),
            out,
        )

    if new:
        detail = "REGRESSIONS (not in baseline):\n" + "\n".join(f"  - {f}" for f in new)
        if fixed:
            detail += "\n\nNewly passing:\n" + "\n".join(f"  - {f}" for f in fixed)
        return (
            GateResult(
                "test",
                False,
                f"{len(new)} regression(s); {note}",
                detail,
                secs,
                feedback=(
                    "Your patch BREAKS tests that passed before it. These failures are "
                    "new and are not part of the known-failing baseline:\n\n"
                    + "\n".join(f"- {f}" for f in new)
                    + "\n\nFix them and re-emit ALL blocks in full."
                ),
            ),
            out,
        )
    if expect_green:
        note += f"; all {len(expect_green)} acceptance test(s) green"
    return GateResult("test", True, f"no regressions; {note}", "\n".join(fixed), secs), out


# --------------------------------------------------------------------------
# Gate 4 - lock scope
# --------------------------------------------------------------------------
LOCK_RISK = re.compile(r"\.(Flatten|Cancel|Submit|CreateOrder)\s*\(")


def check_lock_scope(regions, blocks: Dict[str, str], strip_code, lock_name: str = "_stateLock") -> GateResult:
    """Flag broker calls reachable inside lock(_stateLock).

    This is domain-specific and deliberately overrides an APPROVE: calling into
    the broker under the state lock is how this addon deadlocks with real money
    on the line, and reviewers have waved it through before.
    """
    flags: List[str] = []
    pat = re.compile(r"lock\s*\(\s*" + re.escape(lock_name) + r"\s*\)")
    for r in regions:
        body = blocks.get(r.id)
        if not body:
            continue
        # Ordered event scan rather than per-line depth arithmetic. The naive
        # version deregistered the lock the moment `depth <= depth_at_lock`,
        # which under Allman braces is the very next check -- the opening brace
        # is on the FOLLOWING line, so the scope was closed before it opened and
        # nothing inside it was ever examined.
        depth = 0
        lock_depths: List[int] = []  # depths at which lock scopes opened
        pending_lock = False
        for ln in body.splitlines():
            code = strip_code(ln)
            events = (
                [(m.start(), "lock") for m in pat.finditer(code)]
                + [(m.start(), "risk") for m in LOCK_RISK.finditer(code)]
                + [(i, "open") for i, c in enumerate(code) if c == "{"]
                + [(i, "close") for i, c in enumerate(code) if c == "}"]
            )
            for _, kind in sorted(events):
                if kind == "lock":
                    pending_lock = True
                elif kind == "open":
                    depth += 1
                    if pending_lock:
                        lock_depths.append(depth)
                        pending_lock = False
                elif kind == "close":
                    if lock_depths and depth == lock_depths[-1]:
                        lock_depths.pop()
                    depth -= 1
                elif kind == "risk" and lock_depths:
                    flags.append(f"{r.id}: broker call under {lock_name} -> {ln.strip()}")
    if flags:
        return GateResult(
            "lock-scope",
            False,
            f"{len(flags)} broker call(s) under {lock_name}",
            "\n".join(flags),
            feedback="Mechanical lock-scope violations detected:\n"
            + "\n".join(f"- {f}" for f in flags),
        )
    return GateResult("lock-scope", True, f"no broker calls under {lock_name}")
