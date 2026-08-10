"""
nt8_riskguard.py — the NT8 RiskGuard profile as a consumer of agent-loop.

Usage:
    agent-loop --profile nt8-riskguard --profile-module scripts.agent_loop_config.nt8_riskguard \
        --tickets tickets.json --ticket T1
"""
from __future__ import annotations

from agent_loop.profiles import Profile, register

NT8_RISKGUARD = Profile(
    name="nt8-riskguard",
    language="csharp",
    file_suffixes=(".cs",),
    line_comment="//",
    block_comment=("/*", "*/"),
    block_kind="decl",  # brace-delimited
    preprocessor_directives=("#if", "#endif"),
    # NinjaTrader's log pane mangles non-ASCII, so the static gate rejects it.
    # This is an NT8 constraint, not a universal one -- hence a profile flag.
    ascii_only=True,
    # Build and test
    build_cmd="dotnet build ninjatrader-addon/RiskGuardTests.csproj --nologo -v q",
    test_cmd="dotnet run --project ninjatrader-addon/RiskGuardTests.csproj --nologo -v q",
    # Lock-scope gate (C# has a lock primitive)
    lock_name="_stateLock",
    risk_calls=(".Flatten", ".Cancel", ".Submit", ".CreateOrder"),
    # File scope (Developer mode)
    file_scope_whitelist=("scripts/ninjatrader/addons/", "ninjatrader-addon/"),
    # Protected paths
    protected=(
        "*Tests.cs",
        "*.csproj",
        "scripts/agent_loop/*",
        "scripts/agent_loop_config/*",
    ),
    test_sources=("scripts/ninjatrader/addons/*Tests.cs",),
    # Context and token budgets
    context_token_budget=3000,
    round_input_token_budget=40000,
    # Graph project (codebase-memory-mcp)
    graph_project="C-Users-vinay-tvDownloadOHLC",
    # Prompts (carried over from the original profiles.py)
    implementer_rules="""\
You are a senior C# engineer hardening a NinjaTrader 8 AddOn that manages
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
    reviewer_priorities="""\
You are an adversarial code reviewer for safety-critical trading software.
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
5. TEST ADEQUACY: the suite is a first-class artifact, review it as such.
6. COMPILE BREAKS: C# 8.0 / net48 + net8.0-with-stubs compatibility.
7. REGRESSIONS: existing behaviour or existing tests that this would break.

Be specific. Cite the offending line text. Do not restate the ticket. Do not praise.""",
    # This text used to live in the package as a hardcoded ARBITER_SYSTEM, which
    # meant every consumer -- including the Python profile -- got the NT8 bar for
    # UPHELD ("state the sequence of events that loses money"). It belongs to
    # this profile, where it is true.
    arbiter_rules="""\
You are the arbiter for a patch to a NinjaTrader 8 risk-guard AddOn that
protects real funded futures accounts.

The mechanical gates have already established that it compiles, that the full test suite runs
with no regressions, and that no broker call is reachable while the state lock is held.

An UPHELD finding must state the concrete sequence of events that loses money or leaves a
position unprotected. "Could be clearer", "might be safer", and "consider also handling" are
NOT upheld.

An unsound SHIP here reaches a live trading account, so prefer ESCALATE over a confident wrong
answer. On naked-position risk, a model does not get the last word.""",
    # Settled decisions (carried from the original profile)
    settled=(
        "CoveredQuantity is the SUM over every live protective stop on the position, and both it "
        "and RecognizedStopOrder are DERIVED from PositionGuardFsm's stop list -- neither is "
        "assignable (P1-36, closed 2026-08-07).",
        "NT8 raises ExecutionUpdate BEFORE PositionUpdate. Code that reads account.Positions "
        "from an execution handler reads a position that does not exist yet on an entry fill "
        "(P0-49, closed 2026-08-07).",
        "The copier FAILS CLOSED ON ENTRIES, NEVER ON EXITS.",
        "Pending copies and recognised stops are keyed by Order OBJECT REFERENCE, never by "
        "Order.OrderId. NT8's OrderId is neither unique nor stable.",
        "The mirrored bracket stop carries the leader's SIGNED offset applied to the FOLLOWER's "
        "own fill. Never Math.Abs, never the leader's stop PRICE.",
        "Simulation accounts are identified by account.Provider == Provider.Simulator, never "
        "by a name prefix (P1-20, closed).",
    ),
)

register(NT8_RISKGUARD)