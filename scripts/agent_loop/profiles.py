"""
profiles.py
===========
Domain configuration, kept out of the loop driver.

The predecessor hard-coded NinjaTrader, `_stateLock` and naked-position
vocabulary into its system prompts, which meant the loop could only ever be
used on this one addon. Everything domain-specific now lives in a Profile, so
pointing the loop at a different codebase is a config change, not a fork.

The output-format half of each prompt is NOT domain-specific and stays in the
profile only because it must be adjacent to the rest of the system prompt --
`loop.py` parses those markers and they are not user-tunable.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Sequence

_OUTPUT_CONTRACT = """
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

_REVIEW_CONTRACT = """
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


@dataclass
class Profile:
    name: str
    implementer_rules: str
    reviewer_priorities: str
    build_cmd: str = ""
    test_cmd: str = ""
    lock_name: str = "_stateLock"
    protected: Sequence[str] = ()
    # Decisions the arbiter has already made. Injected into every review round
    # so reviewers stop re-raising them -- the predecessor required the human to
    # remember to pass --orchestrator-note by hand, and three known false
    # positives were re-litigated across rounds because nobody did.
    settled: Sequence[str] = ()

    @property
    def implementer_system(self) -> str:
        return self.implementer_rules.rstrip() + "\n" + _OUTPUT_CONTRACT

    @property
    def reviewer_system(self) -> str:
        return self.reviewer_priorities.rstrip() + "\n" + _REVIEW_CONTRACT


NT8_RISKGUARD = Profile(
    name="nt8-riskguard",
    build_cmd="dotnet build ninjatrader-addon/RiskGuardTests.csproj --nologo -v q",
    test_cmd="dotnet run --project ninjatrader-addon/RiskGuardTests.csproj --nologo -v q",
    lock_name="_stateLock",
    protected=("*Tests.cs", "*.csproj", "scripts/agent_loop/*"),
    implementer_rules="""You are a senior C# engineer hardening a NinjaTrader 8 AddOn that manages
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
8. Do not weaken, delete, or work around a test in order to pass. If a test is wrong, say so
   in your notes and leave it alone -- you are not given access to test code.""",
    reviewer_priorities="""You are an adversarial code reviewer for safety-critical trading software.
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

The patch has already passed a compiler and the project's test suite; a claim that it does not
compile, or that it breaks a test, is therefore almost certainly wrong -- say so only with a
concrete mechanism.""",
    settled=(
        "Multi-stop coverage aggregation is OUT OF SCOPE (tracked as P1-36). CoveredQuantity "
        "deliberately follows a single stop order. Do not raise it.",
        "Orphan-cancel under _stateLock STAYS (tracked as P1-35). Do not propose fixing it by "
        "adding a nested lock (_stateLock) -- every caller already holds the lock, so the nested "
        "lock is re-entrant and buys nothing.",
        "SeedFsmsForExistingPositions does NOT need its own lock: both SubscribeToAccount call "
        "sites already hold _stateLock. Reviewers repeatedly flag this as a false positive.",
        "Do not propose new GuardFsmState enum values; existing tests assert on them.",
        # Settled while landing T2. The first is the important one: it looks like a
        # missing safety check, and re-adding it reintroduces a PERMANENT naked position.
        "ValidateInvariant must NOT reject PlaceStopOrder when action.Quantity > the live "
        "position quantity. The action is dropped before ExecuteAction runs, so GraceEmitted "
        "stays latched and both EvaluateGraceExpiry and FsmWatchdog are suppressed forever, "
        "leaving the position permanently naked. ExecuteAction re-sizes from the live "
        "position, so the check buys nothing. Do not propose adding it back.",
        "ArmGraceTimer only schedules a timer callback and makes no broker/account call. "
        "Calling it while holding _stateLock is correct and required (T1). Do not raise it "
        "as a lock-scope violation.",
        "Reading account.Positions outside _stateLock is an accepted pattern here. A stale "
        "read produces a safe abort or a spurious grace timer that aborts harmlessly, not "
        "naked risk. Do not raise it as a lock-scope violation.",
        "A TOCTOU window between the live position read and account.Submit cannot be closed "
        "without holding a lock across a broker call, which is forbidden. Sizing from the "
        "most recent live read satisfies the requirement. Do not raise it as unfixed.",
    ),
)

PROFILES: Dict[str, Profile] = {p.name: p for p in (NT8_RISKGUARD,)}


def get(name: str) -> Profile:
    if name not in PROFILES:
        raise KeyError(f"unknown profile {name!r}; have {sorted(PROFILES)}")
    return PROFILES[name]
