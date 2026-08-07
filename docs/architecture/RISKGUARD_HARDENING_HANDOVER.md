# RiskGuard / TradeCopier Hardening — Session Handover

**Last updated**: 2026-08-07 (session 4)
**Branch**: `harden/riskguard-copier-p0`
**Plan of record**: [RISKGUARD_COPIER_HARDENING_PLAN.md](RISKGUARD_COPIER_HARDENING_PLAN.md) (38 defects; P0, Phase B and Phase C all closed)
**DEPLOYED to shadow 2026-08-07.** NinjaTrader is running the current addon in `shadow` mode. The branch is *not* yet merged to `main`. Suite 413 passed, 0 failed.

---

## 0. Start here (read this first, then §2 and §4)

**17 of 38 defects are closed. Suite: 413 passed, 0 failed.** All nine P0, all of Phase B, and
all of Phase C bar `P1-36`. The addon is deployed and running in `shadow`, compiling clean in NT8.

| Phase | State |
|---|---|
| **A** — deploy P0 to shadow | Deployed, **acceptance criteria NOT met** (see below) |
| **B** — test foundation | ✅ T1–T3 tests backfilled and proven falsifiable; `P2-28` |
| **C** — P1 safety-critical | ✅ `P1-20`, `P1-37`, `P1-10`, `P1-35`, `P1-11`, `P1-15`; **`P1-36` left** |
| **D–G** | Not started — §4a |

### Three things to know before you touch anything

**1. Deployed is not validated.** Phase A put the code in front of NinjaTrader but never in front
of a market. The machine is on **Kinetick End Of Day (Free)** — daily bars, no real-time quotes —
so the NT8 simulator cannot fill, no position can open, and **not one guard path has ever
executed live**. A test order sat at `Submitted` and was rejected. The §4e acceptance criteria
(`PEAK_GIVEBACK_BREACH` on a profitable flat account; a wrong `COPY_BLOCKED_NO_GUARD`) are still
unmet and need a session on a real-time feed. Read "compiles clean, suite green, deployed" as
exactly that and no more.

**2. One manual step is outstanding.** The live `state.json` reads `ShadowSessionsCompleted = 5`,
inflated by restarts before `P1-37` was fixed. It no longer climbs, but the value is wrong and
`MinShadowSessions=3` currently reads as satisfied, so the arming gate is not trustworthy on this
box. **Reset it with NinjaTrader closed** — commands are in the plan under P1-37. It was
deliberately not edited live: shutdown flushes in-memory state over the file, and a torn write
loses persisted lockouts.

**3. The branch is still unmerged.** `harden/riskguard-copier-p0`, fast-forward available. It also
carries unrelated narrative/wargaming commits from other background agents.

Deployment happened to be the thing that found `P1-37` — a safety gate that counted addon restarts
instead of sessions, which no amount of review had noticed. That is the argument for finishing
Phase A properly on a real feed.

The roadmap for the remaining 21 defects is §4a; the deployment runbook is §4e and the record of
the one run so far is §4f.


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

> ✅ **Work is test-first from here.** A ticket declares `expect_green`; the loop refuses it
> unless those tests are already failing at baseline, and fails any candidate that leaves one
> red. Reviewers judge the tests' completeness and accuracy too. This closes the hole T5 went
> through — it reached `ARBITER_SHIP` with its own acceptance test still red. See the plan's
> §6.0.

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

## 4a. Roadmap for the remaining 21 defects

**38 defects total, 17 closed, 21 open**: 11 P1, 5 P2, 5 P3. Closed since P0: `P2-28`
(Phase B); `P1-20`, `P1-37`, then the concurrency cluster `P1-10`, `P1-35`, `P1-11`, `P1-15`
(Phase C). `P2-38` was opened on 2026-08-07 — the same name-prefix hole as P1-20, in
`McpBridgeAddOn`'s strategy-deploy guard.

**Still open in P1**: `P1-12`, `P1-13`, `P1-14` (latency / dispatcher / `_pendingStops`),
`P1-16` … `P1-19` (rule semantics), `P1-21` … `P1-23` (copier fidelity), `P1-36`
(multi-stop coverage aggregation — re-read §1 on T1 before touching it). Band membership and the
P1-30/31 → P1-35/36 renumbering are in the plan's inventory table. `P1-37` was found by the
Phase A shadow deployment on 2026-08-07 (§4f).

Decided 2026-08-07: **deploy P0 to shadow before writing more code.** Done — but shadow ran on a
feed with no real-time data, so Phase A's acceptance criteria are still unmet (§4f).

### Phase A — deploy P0 (no new code) — deployed, NOT yet validated

Nine live-risk fixes are in a branch doing nothing. Shadow mode is also the only way to validate
T3's giveback rule and T5's fail-closed gate against real account data; no unit test can.
**Runbook in §4e — read it, the ordering is not obvious and the live config is not in shadow.**

### Phase B — foundation: the test suite comes first ✅ DONE (2026-08-07)

**From here on the work is test-first, and it is enforced, not encouraged.** See the plan's
§6.0 for the full model. In short: a ticket declares `expect_green`; the loop **refuses** it
unless those tests are already red at baseline; the test gate **fails** any candidate that leaves
one red; and reviewers must judge the tests' completeness and accuracy, not just the patch.

1. ✅ **`expect_green` and the test-first refusal** — landed (`eba565fa`). Reviewers also now
   receive the acceptance tests read-only.
2. ✅ **Backfilled (2026-08-07, `8716a479`).** Six tests, each *verified to fail with its fix
   reverted* by `scripts/agent_loop/verify_backfill_reverts.py`. That check caught one test
   that was pinning defence-in-depth rather than the site it named — written without it, it
   would have read as thorough and proven nothing. Original wording follows.
   **Backfill tests for T1–T3.** T4/T5 have real coverage; T1–T3 rest on review and
   not-regressing. Write these before touching any P1 code, and verify each one **fails when the
   fix is reverted** — an unfalsifiable test is the thing this phase exists to prevent:
   auto-stop submit failure rolls back and clears `GraceEmitted`; auto-stop sized from the live
   position, not the emission snapshot; a scaled-down position still gets a stop rather than
   having its action dropped; a stop cancelled mid-position re-arms grace; a profitable-flat
   account emits no giveback action; a close+reverse flip does not carry `PeakOpenGain` into the
   new leg.
3. Pull **P2-28** (three divergent source copies, committed build output) forward from Phase F.
   Mostly deletion, and it removes a live hazard — editing the wrong copy silently does nothing.

**Writing the tests is a human/operator job, not a loop job.** `*Tests.cs` is a protected path:
the implementer cannot reach it by construction (gate 0, anti-reward-hacking). That is deliberate
— the grader is written by a different party than the one being graded.

### Phase C — P1 safety-critical ✅ DONE (2026-08-07), except P1-36

✅ **The whole phase is closed except P1-36**: `P1-20` and `P1-37` (`53129e33`), then the
concurrency cluster `P1-10`, `P1-35`, `P1-11`, `P1-15` (`e0e3bd8b`). All test-first, each
observed red before its fix.

**The lock-scope invariant is now machine-checked.** The stub account reports every
`Cancel`/`Flatten`/`CreateOrder`/`Submit` to an observer and the addon exposes
`TestIsStateLockHeld()`, so a test asserts the design doc's central concurrency claim
directly. `DrainPendingCancels()` throws in the TESTING build if called with the lock held —
the nested-`lock` "fix" is re-entrant and would silently reintroduce P1-35.

**P1-36 is deliberately left.** It modifies T1's `CoveredQuantity` model; re-read §1 and §5
first — the single-stop behaviour is deliberate and the `ReferenceEquals` guard bounds it.

Original reasoning follows.

**Start with P1-20, out of band order.** T5's fail-closed gate keys off
`followerAcc.Name.StartsWith("Sim")`, so a live account named `SimpsonFund` is exempt from the
protection requirement today. The P0 work made that check load-bearing; it needs to be real.

Then the concurrency cluster: **P1-35**, **P1-10**, **P1-11** (the lockout sweep cancels
*protective* stops — a naked window), **P1-15**, **P1-36**.

Sequencing constraints:
- **P1-35 and P1-10 are the same fix twice** — queue the cancel, drain it after the lock releases.
  Do them in one ticket.
- **P1-36 modifies T1's `CoveredQuantity` model.** Re-read §1 (T1) first; the single-stop
  behaviour is deliberate and the `ReferenceEquals` guard exists to bound it.

### Phase D — P1 rule semantics

P1-16 … P1-19. Self-contained, low blast radius, good loop tickets. P1-17 (eval target fed
session-scoped PnL, so it never fires) is the most consequential.

### Phase E — copier fidelity

P1-21, P1-22, P1-23, then the real half of **P0-9**. Only P0-9's fail-closed *precondition*
landed in T5 — followers still receive bare market orders with no protective legs. This is the
largest single piece of remaining work.

### Phase F — P2 structural

P2-28 (if not already done in B), P2-24, P2-26 (doc drift — the design doc still overstates what
exists), P2-25, P2-27's remaining CI half, P2-29. Note **P2-27 is half-closed**: the copy path is
in the test build with real coverage; only the CI job is outstanding. The plan text still
describes it as fully open.

### Phase G — P3

**P3-30, the independent reconciler (REAPER port), is the highest-value single addition in the
whole plan** — an auditor that re-derives ground truth from the broker and repairs what the FSM
missed. It is P3 by effort, not by value; reconsider promoting it once P1 lands. Then P3-31 …
P3-34.

---

## 4e. Deployment runbook (Phase A)

> **Ran once on 2026-08-07 — see §4f for what actually happened, including two claims below
> that turned out to be wrong.** Steps are kept in their corrected form; re-read §4f before
> re-running.

**Do not copy code first.** Set the mode before the new addon runs.

1. **Check the live config is not in an acting mode.** `~/Documents/NinjaTrader 8/RiskGuard/config.json`
   is the file the addon reads (`Path.Combine(Globals.UserDataDir, "RiskGuard", "config.json")`).
   It was `"Mode": "override_with_friction"`, an *acting* mode (`RiskGuardAddOn.cs:2455`).
   Deploying new code without changing this puts freshly-written flatten logic straight in front
   of a funded account. Set `"Mode": "shadow"` **and confirm the running addon actually reloaded
   it** — the config has no file watcher, so it is only re-read on construction or an explicit
   reload. Verify via `GET /api/riskguard/config`, not by reading the file back.
   - ~~There is a second `config.json` at `bin/Custom/AddOns/config.json`~~ — **resolved**: it
     was dead, nothing reads it, and it has been renamed `config.json.UNUSED_not_read_by_addon`.
2. **Diff deployed vs canonical — with line endings normalised.** Deployed files are CRLF and
   the repo's are LF, so a plain `diff` reports *every* line as different and looks like massive
   drift. Use `diff --strip-trailing-cr`. On 2026-08-07 there was **no** pre-existing drift.

Then:

3. Rotate `interventions.jsonl` so shadow output is readable. Safe while running —
   `File.AppendAllLines` never holds the file open.
4. Merge `harden/riskguard-copier-p0` → `main`. **Do this after shadow validation, not before**;
   deployment copies from the working tree, so the merge buys nothing up front. Note the branch
   also carries ~7 unrelated narrative/wargaming commits from other background agents.
5. Copy the **four** changed addon sources into `bin/Custom/AddOns/` (`RiskGuardAddOn.cs`,
   `TradeCopierEngine.cs`, `PropFirmProtectionSuite.cs`, `RiskGuardAddOnTests.cs` —
   `TestingStubs.cs` is unchanged), then compile via `nt_compile` or F5 and confirm zero errors.
   The test build is net8.0 with stubs, NT8 is net48, and only NT8 proves the real build.
   **Put backups outside `bin/Custom/`** — NT8 compiles that tree recursively and a backup folder
   of `.cs` files causes duplicate-type errors.
6. Run a full session in shadow **on a real-time feed**. Kinetick End Of Day gives no Level 1, so
   the simulator cannot fill and no guard path will execute — a session on that feed proves
   nothing. Then read `interventions.jsonl` and ask specifically: did `PEAK_GIVEBACK_BREACH` fire
   on a profitable flat account (T3), and did any `COPY_BLOCKED_NO_GUARD` line name an account
   that should have been allowed (T5)?
7. **Fix P1-37 and reset `ShadowSessionsCompleted` to `0`** (addon stopped) before considering an
   acting mode — the counter is currently inflated by restarts and the arming gate is not
   trustworthy.
8. Only then consider restoring an acting mode.

**Roll back** by restoring the previous `.cs` files and recompiling; nothing here migrates state.
Config is separate from code, so a mode change alone is instant and reversible.

---

## 4f. Deployment record — 2026-08-07, shadow

Executed against a running NT8 (92 accounts, no open positions, no working orders).

| Step | Result |
|---|---|
| Live config → `shadow` | Done. Backup `RiskGuard/config.json.bak_20260806_224830`. Verified **in memory**, not just on disk, via `GET /api/riskguard/config`. |
| Stray `bin/Custom/AddOns/config.json` (`"Mode": "live"`) | Confirmed **dead** — nothing reads it; the addon uses `Globals.UserDataDir/RiskGuard/config.json`. Renamed `config.json.UNUSED_not_read_by_addon`. |
| Rotate `interventions.jsonl` | Done → `interventions.jsonl.20260806_224904` (110 MB). Safe: written with `File.AppendAllLines`, never held open. |
| Merge to `main` | **Deliberately deferred** until shadow validation. Fast-forward confirmed available (`main` is strictly behind, 0 divergent commits). |
| Deploy sources | 4 files, not 5 — `TestingStubs.cs` is unchanged by the branch. Backup at `Documents/NinjaTrader 8/_riskguard_backups/_backup_20260806_224954`. |
| `nt_compile` | **0 errors.** All warnings pre-existing and in unrelated files (`McpBridgeAddOn`, indicators); none in the three addons. |
| Verify | `RiskGuard Add-On v1.1.0 initialized in shadow mode`, `mode: shadow`, `isArmed: false` on every event. |

**Two traps in §4e above were wrong, and both wasted time. Corrected here:**

- **"The deployed sources differ from canonical" was a false alarm.** The deployed files are
  CRLF, the repo's are LF, so a plain `diff` reports every line as changed. Normalised with
  `diff --strip-trailing-cr`, the deployed files were **byte-identical** to canonical at the
  merge-base — there was no pre-existing drift at all. Always normalise line endings before
  concluding anything from a diff against `bin/Custom/AddOns/`.
- **Never put a backup directory inside `bin/Custom/`.** NT8 compiles that tree recursively, so
  a folder of `.cs` backups produces duplicate-type errors. Caught before compiling; backups now
  live in `Documents/NinjaTrader 8/_riskguard_backups/`.

**What shadow could not prove.** The data connection is **Kinetick – End Of Day (Free)**: daily
bars arrive (today's forming bar included) but every real-time quote is `0`, and the NT8
simulator needs Level 1 to fill. A test market order on `Sim101` sat at `Submitted` and was
ultimately **Rejected** without filling. RiskGuard did observe it — `ORDER_UPDATE` events for
`Submitted` → `CancelPending` → `Rejected` — so event monitoring is live on the new build, but
**no position was ever opened, so not one guard path executed.** The §4e acceptance criteria
(`PEAK_GIVEBACK_BREACH` on a profitable flat account; a wrong `COPY_BLOCKED_NO_GUARD`) remain
**unverified**. They need a session on a real-time feed. Do not read "deployed and green" as
"validated".

**Restart churn is expected, and it is not a fault.** The addon cycled `SHUTDOWN`/`INITIALIZE`
roughly every 10 s for about four minutes (24 lifecycle events) and then went quiet. It was
`nt_compile` and `nt_script_execute` recompiling NinjaScript — each recompile reloads every
AddOn. It settled by itself and the heartbeat has been steady since. Pre-deploy the addon
initialised 3 times in 3 days, so if you see this cadence *without* having compiled, that is a
real problem.

That churn is what exposed **P1-37** — see the plan. `nt_script_execute` is also unreliable here
(one `NT8 timeout`, one `ECONNRESET`); don't count on it for runtime probing. The bridge's
`GET /api/riskguard/config` is the dependable way to read live in-memory state, using the token
at `Documents/NinjaTrader 8/mcp_token.txt`.

**How to tell the new code is actually loaded**, given `Version` is still `1.1.0` and so proves
nothing: look for `MaxAutoStopAttempts` in the live config response. That field arrived with T2
and does not exist at the merge-base.

---

## 5. Decisions already made — do not re-litigate

- **Multi-stop coverage aggregation is out of scope** (tracked as **P1-36**). `CoveredQuantity`
  deliberately follows a single stop order. Reviewers will raise this repeatedly; the bounded
  mitigation already in place is the `ReferenceEquals` guard plus "coverage may only be replaced
  by an equal-or-larger stop".
- **Orphan cancels are queued, not inline** (**P1-35**, closed 2026-08-07). `UpdateFsmOnPosition`
  adds to `_pendingCancels` under the lock; `DrainPendingCancels()` sends them after it is
  released. Do **not** move the `Cancel` back inline, and do **not** call the drain from inside
  the lock — the lock is re-entrant, so that reads as correct and changes nothing. The TESTING
  build throws on it.
  > This bullet previously read *"orphan-cancel under `_stateLock` stays"*. Left unedited it
  > would now be instructing reviewers to approve reintroducing the defect. Settled decisions
  > have to be retired when they are settled the other way.
- **`SeedFsmsForExistingPositions` does not need its own lock** — its call sites
  (`SubscribeToAccount`, and `ToggleArmed` since P1-15) all already hold `_stateLock`, and it
  makes no broker call. Reviewers flag this as a false positive.
- **Simulated accounts are identified by `Provider`, never by name** (**P1-20**, closed). Do not
  reintroduce a `Name.StartsWith("Sim")` test or OR one in. Playback is deliberately not exempt.
- **The lockout sweep's three-phase order is deliberate** (**P1-11**, closed): cancel
  risk-increasing orders, flatten, then cancel reducing orders only for instruments confirmed
  flat. Cancelling everything up front and then failing to flatten is the naked-position bug.
- **`_lastShadowSessionDate` travels with `_shadowSessionsCompleted`** (**P1-37**, closed). They
  are one fact; splitting them let a restart re-count a session.
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

Every one of these is also encoded in `scripts/agent_loop/profiles.py` under `settled`, which
injects them into every review round. **Add to both places, and retire from both places.**
A settled decision that has since been settled the other way does not merely go stale — it
actively instructs the panel to approve reintroducing a closed defect. The P1-35 entry above
was exactly that until 2026-08-07.

---

## 6. Known traps

- **Two unrelated background processes commit to this repo.** Stage explicit paths, never
  `git commit -a` and never `git add <dir>` — a `git add docs/architecture/` swept in an
  unrelated agent's file during this work.
- **The test runner still exits non-zero on any failure**, which is correct, but it means a red
  suite masks nothing now that the mid-run exit is gone — read `RESULTS:` at the very end.
- **Never diff the NT8 tree without normalising line endings.** The repo is LF, the NT8 tree is
  CRLF. A plain `diff` reported 8216 changed lines on a 4108-line file that was byte-identical,
  and that false alarm was written into this handover as fact. Use `diff --strip-trailing-cr`;
  the sync script's hash now normalises.
- **Never put backups inside `bin/Custom/`.** NT8 compiles that tree *recursively*, so a folder
  of `.cs` backups produces duplicate-type errors. Use
  `Documents/NinjaTrader 8/_riskguard_backups/`.
- **Never sync to NT8 unscoped.** `sync_nt8_strategies.py` without `--only addons` also pushes
  strategies and indicators; during the shadow deployment that would have installed 21 unrelated
  indicator files into a live NT8 mid-session.
- **`nt_compile` and `nt_script_execute` both reload every AddOn.** Expect a few minutes of
  `SHUTDOWN`/`INITIALIZE` churn after compiling; it settles on its own. That churn is what
  exposed P1-37. `nt_script_execute` is also unreliable (`NT8 timeout`, `ECONNRESET`) — prefer
  `GET /api/riskguard/config` for live state.
- **`interventions.jsonl` grows without bound** — it reached 110 MB and was rotated on
  2026-08-07. Rotate it before a shadow session so the output is readable.
- 844 lines of WPF UI in `RiskGuardAddOn.cs` remain outside the test build (acceptable), as does
  `ReconcileFollowerPosition` (needs `Application.Current.Dispatcher`). If P2-24 wires that method
  up, it needs a dispatcher seam to stay testable.
