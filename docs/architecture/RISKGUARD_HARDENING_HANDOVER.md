# RiskGuard / TradeCopier Hardening — Session Handover

**Last updated**: 2026-08-06 (session 3)
**Branch**: `harden/riskguard-copier-p0`
**Plan of record**: [RISKGUARD_COPIER_HARDENING_PLAN.md](RISKGUARD_COPIER_HARDENING_PLAN.md) (31 defects, P0→P3)
**Nothing is deployed.** NinjaTrader is running live with the *unmodified* addon. All five P0 tickets are committed on this branch; the suite is 356 passed, 0 failed.

---

## 0. Start here (read this first, then §2 and §4)

**All five P0 tickets have landed (T1–T5). The suite is fully green: 356 passed, 0 failed.**
Every one of the nine live-risk P0 defects is closed, including all three that had deliberate
failing acceptance tests waiting.

State in one paragraph: session 3 landed T2, T3, T4 and T5, fixed four defects in the loop itself
(§4d), and repaired the P0-8 test, which could never have gone green because it never wired
`RiskGuardAddOn.Instance` and so could not observe its own subject. **Nothing is deployed** —
NinjaTrader is still running the unmodified addon, and that is now the single most important open
item. The next work is P1, starting with the two deferred items this work created:
**P1-30** (orphan-cancel under `_stateLock`) and **P1-31** (multi-stop coverage aggregation).

```powershell
# free, ~2 min, no models: is the tool sound?
.\.venv\Scripts\python.exe -m scripts.agent_loop.selftest

# free: do all 18 ticket regions still resolve?
.\.venv\Scripts\python.exe -m scripts.agent_loop --list

# the suite, direct
cd ninjatrader-addon; dotnet build -v q --nologo; dotnet run --no-build -v q --nologo
```

**The arbiter recommends; it never ships.** A run that ends `ARBITER_SHIP` has *not* applied
anything. Read `logs/agent_loop/<T>/rN_arbiter.txt` and the candidate itself, then promote with
`--resume-raw <rN_impl_raw.txt> --allow-unapproved --apply` and commit explicit paths.

> ⚠️ **The test gate only proves no *regression*, not that the ticket's defect is closed.** T5
> reached `ARBITER_SHIP` with its own acceptance test still red, and nothing in the ladder
> objected. If a ticket has a failing test waiting, check by name that it went green before
> promoting. Worth encoding as an `expect_green` field on the ticket.

**Do not run `scripts/agent_loop/ollama_patch_loop.py`.** Three of its gates were defective; it is
kept only so the older `logs/ollama_loop/` artifacts stay readable.

---

## 1. What landed

| Commit | Content |
|---|---|
| `5fd26995` | **T1 — P0-1 + P0-4**: stop-guard FSM coverage model |
| `ddba3433` | **Test harness repair** — the suite could not previously catch defects |
| `76d8c947` | **T2 — P0-2 + P0-3**: reserve-before-submit auto-stop, sized from the live position |
| `c4ab4c48` | **T3 — P0-7**: unrealized-only peak for the giveback rule |
| `404b8053` | **T4 — P0-5 + P0-6**: exits clamped to the follower's position; no sub-1 flooring |
| `56f32317` | **T4 follow-up**: an exit must not round down to zero and strand the follower |
| `4667f794` | **T5 — P0-8 + P0-9**: copier respects the lockout; fails closed when unguarded |
| `179769d5` | Dead half of the auto-stop quantity guard removed |
| `fe5bb5ce`, `8f798b09`, `08cd12cb`, `5af12984` | **Four loop repairs** — see §4d |

### T2 (P0-2 + P0-3)
The auto-stop now **reserves before it submits**: `AutoStopOrder`, `RecognizedStopOrder`,
`CoveredQuantity` and `State = ProtectedPending` are written under `_stateLock` *before*
`account.Submit`, and the lock is released before `CreateOrder`/`Submit`. Both failure modes roll
back — clearing the stop fields, `CoveredQuantity` and **`GraceEmitted`** (or T1's latch would
suppress every future grace action and leave the position naked), re-arming grace, and rethrowing
so `ProcessAction` records `EXECUTION_ERROR`. The post-submit FSM write is gone; `UpdateFsmOnOrder`
owns all further state. The stop is sized from a live re-read immediately before `CreateOrder`,
aborting if the position went flat or changed side. `StopGuardConfig.MaxAutoStopAttempts`
(default 2, `<= 0` treated as 2) bounds retries, after which the instrument is flattened.

**The one thing not to undo**: `ValidateInvariant` deliberately does *not* reject
`PlaceStopOrder` when `action.Quantity > liveQuantity`. It reads like a missing safety check, and
it was in the candidate — the arbiter caught it. Because the action is dropped *before*
`ExecuteAction` runs, nothing clears `GraceEmitted`, so `EvaluateGraceExpiry` (`if
(fsm.GraceEmitted) return`) and `FsmWatchdog` (`&& !fsm.GraceEmitted`) are both suppressed
permanently and the position never gets another stop. `ExecuteAction` re-sizes from the live
position, so the check bought nothing. This is now recorded in the loop's `settled` profile.

### T1 (P0-1 + P0-4)
`PositionGuardFsm` gained `CoveredQuantity`, `GracePending`, `GraceEmitted`, `GraceGeneration`.
A new `ArmGraceTimer(fsm, account, instrument, delayMs)` (must be called under `_stateLock`)
replaces both inline timer sites. Every transition into `Unprotected` while the position is open
now re-arms grace. `EvaluateGraceExpiry` is coverage-aware and sizes its action to the
**uncovered delta** (`pos.Quantity - CoveredQuantity`) — emitting the full quantity on top of a
live partial stop would over-cover and flip the position. `FsmWatchdog` remediates by arming a
250 ms timer (it runs under `_stateLock`, so it must not touch the broker); dedupe is
`!GracePending && !GraceEmitted`.

### Test harness repair — read this before trusting any test result
Four structural defects, all found while trying to use the suite as a gate:

1. **`TestExecuteOrderUpdateProcessesActionsOutsideLock` had been destroyed by a bad merge.** Its
   body was the *tail of `Main()`* — ten test invocations, a summary print, and
   `Environment.Exit(1)`. It asserted nothing, and its stray exit aborted the process at call 92
   of 117 whenever any earlier test failed, **silently skipping the last 25 tests (21%)** —
   every copier-group, hedging, order-verification and ATM test.
2. **`EvaluateFirmMirror` declared a `nowEt` parameter and ignored it**, reading `DateTime.UtcNow`.
   Past the firm daily-reset boundary (`DailyResetHourUtc`, default 22:00 UTC) the session rolls
   over and rebases P&L, so two firm-mirror tests failed **every day after 18:00 ET** — which then
   triggered the early exit in (1). Parameter is now honoured; the production call site passes UTC
   (it previously passed ET, silently discarded); both tests pinned to a fixed clock.
3. **One test was never invoked**, and 13 were reachable only from inside another test.
4. **Nothing detected any of this while the suite was green.** Added
   `TestHarness_AllDeclaredTestsAreInvoked` — `Assert()` records its caller via
   `[CallerMemberName]`, and the guard reflects over every declared `Test*` method, failing with
   exact names if the runner stops reaching one. Negative-tested by deleting an invocation.

**Coverage**: `TradeCopierEngine.OnExecution` — the trade-copy path, the riskiest code in the
addon — was compiled out of the test build by `#if !TESTING` and had **zero** coverage. The only
real blocker was a missing `Instrument.GetInstrument` stub. It is now in the test build, with
three copy-path tests that reproduce P0-5, P0-6 and P0-8 as **executable failures**:

| Test | Expected | Was | Proves |
|---|---|---|---|
| `TestCopyPath_ExitDoesNotFlipFollowerShort` | ≤ 1 | **5** | P0-5: follower left short 4 |
| `TestCopyPath_MicroToMiniDoesNotInflateNotional` | 0 | **1** | P0-6: 1 MNQ → 1 NQ, 10× notional |
| `TestCopyPath_LockedFollowerReceivesNoCopy` | 0 orders | **1** | P0-8: copier ignores lockout |

**All three now pass.** The P0-8 one also needed a harness repair before it could ever have
passed: it built a locked RiskGuard but never assigned `RiskGuardAddOn.Instance` (production only
does that in `State.Configure`), so `OnExecution` saw no guard, took the unguarded branch, and
allowed the copy because the follower is named `SimFollower`. The assertion could not observe its
own subject. `SetInstanceForTest` now wires it, and `SetupCopyPath` clears it so the static cannot
leak between tests; the assertion itself is unchanged.

**Suite state**: was 221 visible tests / 2 failures / 25 skipped. Then 353 assertions with 3
expected failures. Now **356 passed, 0 failed**. Any failure is now a regression.

---

## 2. Current state of play

| Ticket | Defects | Status |
|---|---|---|
| T1 | P0-1, P0-4 | ✅ committed `5fd26995` |
| T2 | P0-2, P0-3 | ✅ committed `76d8c947` |
| T3 | P0-7 | ✅ committed `c4ab4c48` |
| T4 | P0-5, P0-6 | ✅ committed `404b8053` (+ exit-rounding follow-up `56f32317`) |
| T5 | P0-8, P0-9 | ✅ committed `4667f794` |

**All five are applied and committed on `harden/riskguard-copier-p0`. Nothing is deployed** —
NinjaTrader is still running the unmodified addon. Deploying is the next decision, and it is a
human one.

### Two things found by review, not by the panel
- **T4's exit rounding** (`56f32317`). Removing the `Math.Max(1, ...)` floor was right for
  entries — that floor *was* P0-6 — but applying it to exits created the mirror defect: an exit
  that rounds to 0 strands the follower in a position the leader has already left. Not an edge
  case: every partial exit rounds down independently, so a leader who entered 10 MNQ (follower:
  1 NQ) and exits in any increment below 10 produces 0 every time, and even a 5+5 exit strands it
  because `Math.Round(0.5)` is 0 under banker's rounding. Exits now take at least one contract
  when the follower holds one, clamped to the real position size.
- **T3's session reset** (`c4ab4c48`). Spec item 1 asks for the new peak fields to be cleared
  where `PeakEquity` is, but neither of those two sites was in the ticket's region set, so the
  loop could not have done it. Added by hand.

### Known-acceptable residue in T2 (do not re-open without new evidence)
- ~~A dead clause survives in `ExecuteAction`~~ — removed in `179769d5`. Recorded because the
  *proposed fix* mattered: glm-5.2 wanted the comparison made against the earlier
  `position.Quantity` from the pricing read, which would abort the auto-stop whenever the
  position scaled **up** between reads, leaving it naked. The dead clause was harmless; that
  fix would not have been.
- **`AutoStopAttempts` is consumed by transient failures** — it increments before `CreateOrder` and
  rollback does not decrement it, so two broker hiccups escalate to flattening a live position.
  This is spec-conformant and fail-closed (the alternative is retrying forever while naked).
  Reviewers split on this: glm read it correctly, deepseek claimed the counter is *always* reset
  and is simply wrong — the setter only zeroes it when the previous state was `Protected`, and the
  submit-failure path is `ProtectedPending → Unprotected`.

---

## 3. The loop (how the work gets done)

> ⚠️ **Superseded. Use `python -m scripts.agent_loop` — see
> [AGENT_PATCH_LOOP.md](AGENT_PATCH_LOOP.md).** Everything below describes the *old*
> `ollama_patch_loop.py`, three of whose gates were defective (§4). It is retained only so the
> in-flight T2 artifacts stay readable. **Do not run it, and do not treat a green run from it as
> evidence** — its panel could not approve, and its lock-scope gate almost never fired.
>
> ```powershell
> .\.venv\Scripts\python.exe -m scripts.agent_loop --list        # free: do regions still resolve?
> .\.venv\Scripts\python.exe -m scripts.agent_loop.selftest      # free: is the loop itself sound?
> .\.venv\Scripts\python.exe -m scripts.agent_loop --ticket T3 --apply
> ```

`scripts/agent_loop/ollama_patch_loop.py` + `scripts/agent_loop/tickets_p0.json`.

```powershell
# see every ticket and confirm its regions still resolve
python -m scripts.agent_loop.ollama_patch_loop --tickets scripts/agent_loop/tickets_p0.json --list

# run one ticket (applies only on UNANIMOUS panel APPROVE)
python -m scripts.agent_loop.ollama_patch_loop --tickets scripts/agent_loop/tickets_p0.json --ticket T3 --apply --max-rounds 4
```

**Roles** (all via Ollama cloud):
- implementer `kimi-k2.7-code:cloud`
- review panel `glm-5.2:cloud` + `deepseek-v4-pro:cloud`, run concurrently; verdict is the
  **worst** returned and APPROVE must be **unanimous**
- cheap high-volume work `deepseek-v4-flash:0731-cloud`

**Gates, in order** — a candidate must clear all of them:
1. *static* — all blocks present, ASCII, balanced braces, balanced `#if/#endif`, unchanged
   leading indentation, no leaked markers
2. *compile* — `dotnet build` (~3 s). Catches every invented symbol. This gate is why round 3 of
   T1's first run was rejected: it referenced `_ordersToCancel` and `ProcessPendingCancellations()`
   which do not exist.
3. *lock-scope* — walks brace depth inside `lock (_stateLock)` and flags any
   `Flatten/Cancel/Submit/CreateOrder` reachable there; overrides APPROVE
4. *panel* — two reviewers
5. *arbiter* — me/you

Useful flags: `--orchestrator-note "<text>"` injects an authoritative directive into **both** the
implementer and the reviewers (it outranks reviewer findings); `--resume-raw <rN_impl_raw.txt>`
restarts from a saved candidate without re-paying for the implementer rounds;
`--allow-unapproved` is an explicit override. Artifacts per round land in `logs/ollama_loop/<T>/`.

**Between tickets you must commit.** The build gate reverts with `git checkout --`, so uncommitted
work in the same file would be destroyed by the next ticket. *(Old loop only — the new loop runs
in a worktree and never writes to the live tree, so this rule no longer applies.)*

---

## 4. What happened to T2, and why the loop is being rebuilt

T2 ran four rounds and exhausted without applying. The candidate was not the problem —
**the gate was closed from round 1.**

`parse_review("")` returns `{'verdict': 'REVISE', 'blocker_count': 0}`: an empty reviewer response
is scored as a dissenting vote, indistinguishable from a real one.

| Round | glm-5.2 | deepseek-v4-pro |
|---|---|---|
| 2 | REVISE, 3 blockers (3.7 KB) | **0 bytes** |
| 3 | REVISE, 4 blockers (6.1 KB) | **0 bytes** |
| 4 | **HTTP 502** | **HTTP 502** |

`unanimous_approve` requires every reviewer to say APPROVE, so no candidate could ever pass. In
round 4 both reviewers 502'd and the `except` fabricated `REVISE` for each — the final candidate
was never reviewed by anything at all. ~2.5 hours and four implementer rounds of cloud spend on a
ticket with no reachable pass state.

Two further defects were found while rebuilding, both verified against the repo:

- **The lock-scope gate was inert for 88% of its targets.** After matching `lock (_stateLock)` it
  closed the scope before the Allman-style opening brace on the next line arrived. 28 of 32
  `lock (_stateLock)` sites in `RiskGuardAddOn.cs` are Allman-braced, so the gate the §3 ladder
  describes as overriding APPROVE almost never fired.
- **`logs/ollama_loop/summary.json` is not a ledger** — it is overwritten per invocation, and
  still records T1 as `applied: false` even though T1 is committed. Trust per-ticket
  `result.json`, not the summary.

Full analysis and the rebuild design: **[AGENT_PATCH_LOOP.md](AGENT_PATCH_LOOP.md)**.

### T2's work is not lost

`logs/ollama_loop/T2/r4_impl_raw.txt` (25.9 KB) and `final_blocks.json` carry three rounds of real
`glm-5.2` feedback, including a genuine blocker: the candidate reset `AutoStopAttempts` only on
`Unprotected → Protected|Flat`, but the success path is `Unprotected → ProtectedPending →
Protected`, so the counter never reset and the guard would escalate straight to flatten after two
*successful* auto-stops. Resume from that artifact rather than starting T2 over.

## 4b. What the live T2 runs taught us (session 2)

Running T2 on the new loop found three more structural defects — in the *loop*, not the addon.
All are fixed; recording them so they are not rediscovered.

1. **A reasoning reviewer looked exactly like a dead one.** `deepseek-v4-pro` returns chain of
   thought in `message.thinking` and the answer in `message.content`, and was spending its whole
   output budget on the former. `_call_ollama` also accepted `max_tokens` and never sent it.
   Reviewers now run with `think=False` — 21s and ten findings, versus 159s and no verdict.
   (`7364c22c`, `dce023b2`)
2. **Unanimous APPROVE from adversarial reviewers is unreachable.** Three rounds against the
   168-line `ExecuteAction`: 11 findings in round 1, 13 in round 3, **zero overlap**. Every
   finding was fixed; each rewrite exposed new ground. The prompt said "apply every required
   change", so false positives drove the rewrites that generated the next round's findings.
3. **There was no arbiter.** Rung 6 was "a human reads artifacts", which is not a rung. Added
   `arbiter.py`: rules each finding UPHELD / REJECTED / OUT_OF_SCOPE, feeds back only upheld ones,
   and stops the run when rounds stop converging. It cannot overturn a mechanical gate and it
   cannot ship — `ARBITER_SHIP` writes a patch and a rationale and waits for a human. (`e0cd3c54`)

Note the gates only prove no *regression*: the suite has no coverage for the P0-2/P0-3 paths, which
is why those defects exist. Passing gates is necessary, not sufficient.

## 4c. The arbiter's first live use, and what it proved (session 3)

T2 went from parked candidate to commit in two rounds.

| Round | Panel | Arbiter |
|---|---|---|
| 1 (resumed r3 candidate) | deepseek REJECT(10), glm REVISE(6) | **REVISE** — 1 upheld, 10 rejected, 8 out of scope |
| 2 | deepseek REJECT(15), glm REVISE(11) | **SHIP** — 0 upheld, 29 rejected, 4 out of scope |

**The single upheld finding was real, and it was introduced by the patch.** The candidate's
new `ValidateInvariant` rejected `PlaceStopOrder` when `action.Quantity > liveQuantity`. Because
`ProcessAction` drops a rejected action before `ExecuteAction` runs, nothing clears `GraceEmitted`,
so the position is left permanently naked (details in §1). Round 2 fixed it in **two lines** and
changed nothing else — `ExecuteAction`, `PositionGuardFsm` and `StopGuardConfig` came back
byte-identical.

Three things this settles:

1. **The non-convergence pathology is confirmed and the arbiter neutralises it.** Round 2's panel
   produced *33* findings against a two-line change to code it had already reviewed — more than
   round 1's 20. Without adjudication this loops forever; the count going *up* after a minimal
   fix is the signature.
2. **Reviewers contradict each other on load-bearing facts, so their findings cannot be taken at
   face value.** On `AutoStopAttempts`, glm read the state machine correctly and deepseek asserted
   the exact opposite. Verified by hand against the code: glm was right.
3. **The arbiter is not a rubber stamp, but it is not sufficient either.** Its one upheld finding
   was correct and its rejections held up on spot-check — including a subtle one about a stale FSM
   side, which is safe only because a genuine side flip passes through flat and
   `UpdateFsmOnPosition` tears the FSM down and recreates it with grace armed. But glm's *proposed
   fix* for the dead-clause finding would have introduced a naked position, and it rejected all 33
   round-2 findings wholesale. Read the rulings.

**The arbiter was also silently discarding its own output** (`fe5bb5ce`): a mismatched `<<<END>>>`
tag threw away every rationale and all 11 settled nominations across both rounds, and a stray
bracket dropped one ruling. Fixed, and the recovered decisions are now in the loop's `settled`
profile so T3–T5 stop paying for them.

## 4d. Four loop repairs, all one bug (session 3)

T3 exposed the same failure mode four times: **strict format parsing silently discarding valid
content, then reporting the wrong cause.** Every one cost real rounds.

| Commit | What was discarded | Cost |
|---|---|---|
| `fe5bb5ce` | Arbiter `RATIONALE` + `SETTLED` — a mismatched `<<<END>>>` tag emptied both | 11 settled decisions lost across two T2 rounds, silently |
| `8f798b09` | An implementer block closed with `>>` instead of `>>>` | **3 rounds and the whole T3 ticket**; r2/r3/r4 were byte-identical and correct |
| `08cd12cb` | Arbiter rulings written `- REJECTED #1` without brackets | A clean SHIP downgraded to a spurious ESCALATE |
| `5af12984` | The resumed candidate was never written to `rN_impl_raw.txt` | The printed `promote:` command named a **stale candidate carrying two upheld findings** |

The last one is the dangerous one. On resume the loop read the candidate but never persisted it,
while every `resume with` / `promote:` hint is built from the round number — so it recommended
promoting a file it had never reviewed. Following that hint would have put the unfixed
close+reverse flip defect into an addon that flattens live funded accounts. **The hint is now
correct, but keep verifying that the file you promote is the one the arbiter actually saw.**

The general lesson for this loop: when a gate says a model got the format wrong, check whether the
*content* is there before spending another round. Marker punctuation is not what the gates exist
to check.

## 4a. Immediate next steps

The P0 phase is done. In priority order:

1. **Decide about deploying.** All nine live-risk defects are fixed in the repo and none of it is
   in front of NinjaTrader. Shadow mode first is the obvious path.
2. **Add tests for T1/T2/T3 behaviour.** T4 and T5 have real coverage now; T1–T3 are verified only
   by review and by not regressing. Good candidates: auto-stop submit failure rolls back and
   clears `GraceEmitted`; auto-stop sized from the live position, not the emission snapshot; a
   scaled-down position still gets a stop rather than having its action dropped; stop cancelled
   mid-position re-arms grace; profitable-flat account emits no giveback action; a close+reverse
   flip does not carry `PeakOpenGain` into the new leg.
3. **Add an `expect_green` field to tickets** so the test gate can require a named test to flip,
   not merely require no regression. T5 shipped past a red acceptance test (§0).
4. **P1 work**, starting with **P1-30** (orphan-cancel under `_stateLock`) and **P1-31**
   (multi-stop coverage aggregation), both deferred out of this phase by decision (§5).

---

## 5. Decisions already made — do not re-litigate

- **Multi-stop coverage aggregation is out of scope** (tracked as **P1-31**). `CoveredQuantity`
  deliberately follows a single stop order. Reviewers will raise this repeatedly; the bounded
  mitigation already in place is the `ReferenceEquals` guard plus "coverage may only be replaced
  by an equal-or-larger stop".
- **Orphan-cancel under `_stateLock` stays** (tracked as **P1-30**). Do **not** "fix" it by adding
  a nested `lock (_stateLock)` and claiming the cancel happens outside — every caller already
  holds the lock, so the nested lock is re-entrant and buys nothing. The real fix queues the
  cancel and drains it in `ExecutePositionUpdateDetails` after it releases the lock.
- **`SeedFsmsForExistingPositions` does not need its own lock** — both `SubscribeToAccount` call
  sites already hold `_stateLock`. Reviewers flag this as a false positive.
- **No new `GuardFsmState` enum values** — existing tests assert on them.
- **`ValidateInvariant` must not reject `PlaceStopOrder` on `action.Quantity > liveQuantity`**
  (settled landing T2). It looks like a missing safety check and it leaves the position
  permanently naked — see §1. `ExecuteAction` re-sizes from the live position.
- **`ArmGraceTimer` under `_stateLock` is correct and required** (T1). It only schedules a timer
  callback; it makes no broker call. Reviewers raise it as a lock-scope violation every round.
- **Reading `account.Positions` outside `_stateLock` is accepted.** A stale read yields a safe
  abort or a harmless spurious grace timer, not naked risk.
- **The TOCTOU window between the live position read and `account.Submit` cannot be closed**
  without holding a lock across a broker call, which is forbidden.

These four are also encoded in `scripts/agent_loop/profiles.py` under `settled`, which injects
them into every review round. Add to both places, not one.

---

## 6. Known traps

- **Two unrelated background processes commit to this repo.** An unrelated `feat(narrative)`
  commit landed between the two commits above. Stage explicit paths, never `git commit -a`.
- **The test runner still exits non-zero on any failure**, which is correct, but it means a red
  suite masks nothing now that the mid-run exit is gone — read `RESULTS:` at the very end.
- **`interventions.jsonl` is 110 MB** in the live NT8 RiskGuard folder. Unrelated to this work but
  worth rotating.
- 844 lines of WPF UI in `RiskGuardAddOn.cs` remain outside the test build (acceptable), as does
  `ReconcileFollowerPosition` (needs `Application.Current.Dispatcher`). If P2-24 wires that method
  up, it needs a dispatcher seam to stay testable.
