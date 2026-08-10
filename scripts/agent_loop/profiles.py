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
    # Globs holding the acceptance tests. Read-only: used to show reviewers the
    # tests named in a ticket's expect_green so they can judge coverage. These
    # files are in `protected`, so nothing in the loop can write them.
    test_sources: Sequence[str] = ()
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
    test_sources=("scripts/ninjatrader/addons/*Tests.cs",),
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
5. TEST ADEQUACY -- the suite is a first-class artifact, review it as such. You are shown the
   acceptance tests for this ticket. Ask:
   (a) COMPLETENESS: which behaviours in the spec, and which failure paths in the patch, does
       NO test cover? Name the specific uncovered path. A patch can close the defect on the
       happy path and leave the rollback, abort or escalation branch untested.
   (b) ACCURACY: does each test actually assert the thing that matters, and would it FAIL if
       the defect were reintroduced? A test that cannot observe its own subject is worse than
       no test, because it reads as proof. This has happened here: the P0-8 test built a
       locked RiskGuard but never wired the static Instance the copier reads, so it could
       never have passed however correct the fix.
   (c) Report gaps as findings with severity MAJOR, naming the missing case concretely enough
       to write. Do NOT propose editing a test to make the patch pass.
6. COMPILE BREAKS: C# 8.0 / net48 + net8.0-with-stubs compatibility, missing fields, wrong
   types, non-ASCII, `#if` structure damage.
7. REGRESSIONS: existing behaviour or existing tests that this would break.

Be specific. Cite the offending line text. Do not restate the ticket. Do not praise.

The patch has already passed a compiler and the project's test suite, INCLUDING every acceptance
test listed for this ticket; a claim that it does not compile, or that it fails a test, is
therefore almost certainly wrong -- say so only with a concrete mechanism. Gaps in what the tests
COVER are still fair game and are what item 5 is for.""",
    settled=(
        # RETIRED 2026-08-07 (P1-36 closed). This used to read "multi-stop coverage aggregation
        # is OUT OF SCOPE; CoveredQuantity deliberately follows a single stop order". Left in
        # place it would now instruct the panel to approve reintroducing a closed defect.
        "CoveredQuantity is the SUM over every live protective stop on the position, and both it "
        "and RecognizedStopOrder are DERIVED from PositionGuardFsm's stop list -- neither is "
        "assignable (P1-36, closed 2026-08-07). Do not propose restoring a single "
        "RecognizedStopOrder slot or a 'replace only with an equal-or-larger stop' rule: on a "
        "6-lot position covered by two 3-lot stops that reports 3 of 6, and the auto-stop that "
        "follows makes 9 lots of protection behind 6. The auto-stop is likewise sized to "
        "liveQuantity MINUS existing cover, not to the whole position.",
        "NT8 raises ExecutionUpdate BEFORE PositionUpdate. Code that reads account.Positions "
        "from an execution handler reads a position that does not exist yet on an entry fill "
        "(P0-49, closed 2026-08-07). The copier's follower bracket anchors from "
        "Account.PositionUpdate for this reason; do not propose collapsing that back into the "
        "execution handler. On the execution path a flat read is AMBIGUOUS and the anchor "
        "disambiguates it: no anchor yet means the position event is still in flight, so do not "
        "release; anchor present means genuinely flat, so do release.",
        "SyncFollowerStop is split in two and the split is load-bearing (P1-56, closed "
        "2026-08-10). SyncFollowerStop is the reservation HOLDER: it publishes "
        "bracket.StopInFlight under _lock before any broker call, runs a bounded re-drive loop, and "
        "clears the flag exactly once in a finally that runs AFTER the loop. SyncFollowerStopOnce "
        "does the work and never touches StopInFlight or StopResyncOwed. Do NOT propose (a) clearing "
        "StopInFlight between passes -- that reopens the window; (b) leaving it set for the re-drive "
        "to clear -- the re-drive backs off before reaching any finally, so the reservation leaks "
        "FOREVER and the follower can never be given another stop; (c) making the re-drive recursive "
        "again; (d) letting re-drive passes skip the StopAttempts increment -- they make real broker "
        "submissions, and not counting them turns MaxBracketStopAttempts into 3x its value, which is "
        "the order-flood mode P1-40/P2-46 already cost us.",
        "bracket.WorkingStop is NEVER cleared before a broker call, nor in OnFollowerOrderUpdate "
        "(P1-56, closed 2026-08-10). An honest WorkingStop is what makes a concurrent sync MODIFY "
        "the existing stop via the Change() trail path instead of creating a second one, keeps "
        "OnFollowerOrderUpdate's ReferenceEquals guard meaningful during an in-flight sync, and lets "
        "ReleaseFollowerBracket still cancel a leg an abort abandoned. Do not restore either clear, "
        "including on the catch or abort paths: if the Cancel threw, the old stop may still be live "
        "and forgetting it recreates the duplicate-leg defect.",
        "The mirrored bracket's two legs are DELIBERATELY asymmetric (P0-9 item 1, closed "
        "2026-08-10). The stop is risk, the target is upside, and every difference follows from "
        "that: only the stop's re-create path may re-mint bracket.OcoId and cancel the target to "
        "rebuild the pair, while the target JOINS whatever live group the stop is in and never "
        "cancels or re-creates it; each leg has its OWN in-flight flag, owed-flag and attempt "
        "budget; and the target's abort path does not clear FollowerQuantity/FollowerSide as the "
        "stop's does. Do NOT propose unifying the two syncs, sharing StopInFlight/StopAttempts "
        "with the target, or making the target symmetric with the stop -- sharing lets an "
        "in-flight TARGET sync delay the risk leg and lets target churn spend the budget that "
        "keeps the follower protected.",
        "The OCO id rule is about the GROUP'S LIFE, not the id's history (pinned by controlled "
        "live test 2026-08-10, handover 4p). An id can be JOINED while its group still has a live "
        "member and is REJECTED only once every leg has gone terminal, and a Change() in place "
        "preserves group membership. So a fresh id is minted ONLY on the cancel-then-create path. "
        "Do not propose per-generation ids on every sync, and do not propose dropping the fresh "
        "mint on re-create: re-using an id whose group may have been retired has the broker reject "
        "the new STOP, which is a naked follower produced by the target feature.",
        "A leg that goes terminal while its OCO sibling has FILLED was RETIRED, not lost, and must "
        "not be re-submitted (P0-9 item 1, closed 2026-08-10). NT8 cancels the sibling when one leg "
        "fills, and because ExecutionUpdate precedes PositionUpdate the follower still reads as "
        "open, so P0-50's live re-read does not catch it. Re-submitting places a protective order "
        "against a position that has just closed. Do not propose removing that check as redundant.",
        "A leader with MORE THAN ONE working target is not mirrored at all (P0-9 item 1, closed "
        "2026-08-10). Do not propose picking the nearest, the furthest, or the last seen: nearest "
        "exits the follower's WHOLE position at the leader's FIRST partial, and last-seen makes the "
        "exit an artefact of NT8's event ordering. Refusing falls back to the known-good "
        "pre-target behaviour. This is NOT applied to stops -- multiple working stops is a "
        "reconciliation problem (P1-36, P3-30) and dropping the risk leg over it is the wrong trade.",
        "Both mirrored leg prices are rounded to the instrument's tick BEFORE the already-correct "
        "comparison (P0-9 item 1, closed 2026-08-10). The anchor is an average fill price and "
        "averages land between ticks; a live COPIER_TARGET came back Rejected at 29905.625 on a "
        "0.25-tick instrument. Rounding after the comparison instead would compare a rounded "
        "working price against an unrounded desired one, never match, and re-drive the leg forever.",
        "The follower's live position is re-read immediately before every broker call and the leg "
        "is abandoned on flat or side mismatch (P0-50, closed 2026-08-07). Since P3-30 this lives "
        "in ComputeDesiredBracket, which returns HasPosition=false and marks BOTH legs Forbidden. "
        "Do not propose removing it as redundant with the bracket state -- three orphan "
        "COPIER_STOP orders were submitted against a flat live account because the snapshot was "
        "trusted to Submit. An orphan stop on a flat account opens a position when it triggers.",
        # --- order-state liveness, settled 2026-08-10 (P0-59, P0-60, P0-61) ------
        "NT8 has SIXTEEN OrderStates and there is ONE total classification with THREE derived "
        "predicates (P0-59/P0-60/P0-61, all closed 2026-08-10, two of them found live). "
        "OrderLiveness{Working,Changing,Departing,Inert,Terminal,Indeterminate}; OccupiesSlot = "
        "'something is here, do not create a second'; ProvidesCoverage = 'this will actually "
        "protect the position'; AcceptsModification = 'I may issue Account.Change() against it "
        "right now'. Do NOT propose collapsing any two of them, nor reintroducing a single "
        "'IsAlive' boolean: the three questions have DIFFERENT fail-safe answers, so no one "
        "boolean can be conservative for all of them. Answering 'is something here' wrongly with "
        "NO over-covers (two stops flip the position); answering 'does this protect' wrongly with "
        "YES leaves it naked; answering 'may I change it' wrongly with YES silently reverts the "
        "order. IsPendingOrWorking was DELETED rather than wrapped, on purpose, so that every "
        "call site had to declare its question -- do not propose restoring a convenience wrapper.",
        "A leg in ChangeSubmitted/ChangePending occupies a slot AND provides coverage AND must "
        "NOT be changed again (P0-61, closed 2026-08-10, found by a live trade). NT8 drops a "
        "second Change() and REVERTS the order to its pre-change values, so it ends up at neither "
        "change's values -- live this left a 2-lot follower behind a 1-lot stop and target. "
        "Reconcile emits Defer, and Defer must NOT fall back to cancel-then-replace: pulling a "
        "protective leg whose change is landing opens a naked window in order to fix a price. "
        "Declining to act is only safe if something later acts, so the deferred instruction is "
        "re-driven by ReDriveDeferredLeg from OnFollowerOrderUpdate, which MUST stay ABOVE that "
        "method's OccupiesSlot early return -- a leg settling out of ChangeSubmitted still "
        "occupies its slot and would otherwise be dropped. It uses its own per-leg "
        "*ChangeDeferred flag: do not propose reusing *ResyncOwed, which SyncFollowerStop's pass "
        "loop consumes immediately and would re-drive while the leg is still mid-change.",
        # --- the reconciler, settled 2026-08-10 (P3-30 copier half) --------------
        "The mirrored bracket is decided by a PURE reconciler over the legs the BROKER holds, not "
        "by the engine's cached Order reference (P3-30 copier half, shipped and live-validated "
        "2026-08-10). ComputeDesiredBracket is pure and takes values; Reconcile is a pure diff "
        "that also CANCELS EXTRA owned legs. That last rule is the whole point: neither leg sync "
        "had ever enumerated followerAcc.Orders, so a leg at the broker that the engine held no "
        "reference to was invisible and therefore PERMANENT -- which is what two live "
        "COPIER_TARGETs against one lot were. Do not propose deciding from bracket.WorkingStop / "
        "WorkingTarget alone, dropping the CollectCandidateOrders enumeration, or removing the "
        "cancel-extras rule as over-reach.",
        "A desired leg has THREE intents, not a bool (P3-30, 2026-08-10). LegIntent{Required, "
        "Unspecified, Forbidden}. Unspecified still de-duplicates but never creates and never "
        "cancels the last survivor. Do NOT propose a HasStop/HasTarget boolean: it collapses 'the "
        "position is gone, cancel everything' with 'the leader retired its own stop so we do not "
        "know where ours goes', and those need OPPOSITE handling -- the boolean version takes the "
        "stop off an open position, reverting P0-9 item (4), i.e. a naked follower shipped as a "
        "refactor.",
        "Reconcile checks a leg's SHAPE (order type and action) BEFORE its price and quantity "
        "(P3-30, 2026-08-10). A leg carrying our name with OrderType.Limit at the stop's price "
        "compares equal on price and quantity and would be accepted AS the stop -- while a limit "
        "below the market is not a stop, it fills at once. The order of those two checks is the "
        "difference between a protective stop and an instant exit. Caught by a test while the "
        "function was being written; do not propose reordering them.",
        "Ownership of a follower leg is EXACT-MATCH on the order name, deliberately unlike "
        "ReevaluateLeaderStops' Name.Contains(\"COPIER\") (P3-30, and P1-57 from the dangerous "
        "direction). Reconcile's output gets CANCELLED, so a false positive cancels a stranger's "
        "protective stop or the user's manual one; a false negative merely leaves a visible "
        "foreign order alone while the position stays covered. Verified live: a third-party "
        "copier's COPIER_STOP-34410-0104CFF5 legs were correctly untouched. Do not propose "
        "widening this to a substring or prefix test.",
        "Reconcile's stopSubmitInFlight/targetSubmitInFlight parameters are NOT "
        "bracket.StopInFlight/TargetInFlight (P3-31 seam, 2026-08-10). The bracket flags are "
        "mutual exclusion between two SYNCS; the parameters mean 'submitted and not yet visible "
        "in Account.Orders'. Feeding the first into the second placed NO STOP AT ALL, because "
        "SyncFollowerStop sets its reservation before calling in and the reconcile then suppressed "
        "the very Create the sync existed to make. The event-driven callers pass false on purpose. "
        "They suppress Create ONLY and never a Cancel -- a reservation that suppressed cancels "
        "would let an orphan leg survive on a flat account, which is P0-50 resurrected through the "
        "ledger.",
        # --- copier decisions, settled 2026-08-07 (session 7) -------------------
        "The copier FAILS CLOSED ON ENTRIES, NEVER ON EXITS. A quarantined relationship still "
        "copies exits (P1-22), unimplemented sizing modes block entries only (P1-23), and an "
        "exit is never rounded or clamped to zero while the follower holds a position (P0-5, "
        "P0-6). Blocking an exit strands the follower in a position the leader has already left, "
        "which is worse than the thing being guarded against.",
        "Pending copies and recognised stops are keyed by Order OBJECT REFERENCE, never by "
        "Order.OrderId. NT8's OrderId is neither unique nor stable across the historical->live "
        "transition (RiskGuardAddOn.cs:4481). The test stub assigns one stable GUID per order, so "
        "an id-keyed map passes the whole suite and fails in production.",
        "The mirrored bracket stop carries the leader's SIGNED offset "
        "(leaderStopPrice - leaderPositionAvgPrice) applied to the FOLLOWER's own fill. Never "
        "Math.Abs: a leader trailing its stop into profit puts it above entry on a long, and an "
        "absolute distance mirrors that onto the losing side of the follower's entry. Never the "
        "leader's stop PRICE either -- that is wrong by the slippage P1-22 measures.",
        "Bracket stop re-submission is BOUNDED by MaxBracketStopAttempts, and the counter must "
        "NOT reset when Submit returns without throwing. The failure mode is a broker that "
        "accepts the submit and rejects the order a moment later, so 'Submit did not throw' is "
        "not evidence of protection and resetting there makes the bound unreachable.",
        "Slippage figures and mirrored stop distances are computed ONLY between price-comparable "
        "instruments (same root, or either direction of the built-in mini/micro matrix). A "
        "CustomSymbolMappings entry may legitimately point ES at NQ, whose prices are unrelated.",
        "The copier does NOT place a default/ATM bracket of its own when the leader has no stop. "
        "RiskGuard's StopAttachSeconds auto-stop already owns 'position with no stop', and two "
        "independent stop sources on one position over-cover and flip it when both fire. "
        "EnableFollowerAtm was deleted rather than implemented.",
        # P1-35 was CLOSED on 2026-08-07. This entry used to read "orphan-cancel under
        # _stateLock STAYS", which would now tell a reviewer to approve reintroducing the
        # defect. A settled decision that has gone stale is worse than none.
        "Orphan auto-stop cancels are QUEUED on _pendingCancels under _stateLock and sent by "
        "DrainPendingCancels() after the lock is released (P1-35, closed). Do not propose "
        "moving the Cancel back inline, and do not propose calling the drain from inside the "
        "lock: the lock is re-entrant, so that reads as correct and changes nothing. The "
        "TESTING build throws if the drain is called with the lock held.",
        "SeedFsmsForExistingPositions does NOT need its own lock: its call sites "
        "(SubscribeToAccount, and ToggleArmed since P1-15) all already hold _stateLock. It "
        "makes no broker call. Reviewers repeatedly flag this as a false positive.",
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
        # Settled while landing Phase C (2026-08-07).
        "Simulation accounts are identified by account.Provider == Provider.Simulator, never "
        "by a name prefix (P1-20, closed). Do not propose restoring a Name.StartsWith(\"Sim\") "
        "check or OR-ing one in: account names are user-chosen, and 'SimpsonFund' is a funded "
        "account. Playback is deliberately NOT treated as simulated -- that is fail-closed.",
        "The lockout sweep deliberately cancels risk-INCREASING orders first, flattens, and "
        "only then cancels position-reducing orders for instruments confirmed flat (P1-11, "
        "closed). Do not propose cancelling all non-terminal orders up front: if the flatten "
        "then fails, that cancels the protective stop and leaves the position naked, which is "
        "the defect this ordering exists to prevent.",
        "_lastShadowSessionDate is persisted alongside _shadowSessionsCompleted and must stay "
        "that way (P1-37, closed). They are one fact. Persisting the counter without the date "
        "made every addon restart look like a new day, so the MinShadowSessions arming gate "
        "could be satisfied by recompiling.",
        "ExecuteSafetySweep uses collect-then-execute: the lock block only DECIDES, and every "
        "Cancel/Flatten/CreateOrder/Submit/ProcessAction runs after it (P1-10, closed). Do not "
        "propose moving any of them back inside the lock for atomicity.",
    ),
)

PROFILES: Dict[str, Profile] = {p.name: p for p in (NT8_RISKGUARD,)}


def get(name: str) -> Profile:
    if name not in PROFILES:
        raise KeyError(f"unknown profile {name!r}; have {sorted(PROFILES)}")
    return PROFILES[name]
