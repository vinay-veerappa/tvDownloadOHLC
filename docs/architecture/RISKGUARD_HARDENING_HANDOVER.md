# RiskGuard / TradeCopier Hardening — Session Handover

**Last updated**: 2026-08-06 (session 2)
**Branch**: `harden/riskguard-copier-p0`
**Plan of record**: [RISKGUARD_COPIER_HARDENING_PLAN.md](RISKGUARD_COPIER_HARDENING_PLAN.md) (31 defects, P0→P3)
**Nothing is deployed.** NinjaTrader is running live with the *unmodified* addon.

---

## 0. Start here (read this first, then §2 and §4)

**One ticket has landed (T1). Session 2 landed no addon code at all** — it went into rebuilding the
tool that lands tickets, because the old one could not approve anything. That was the right call
but it means the hardening itself has not moved since `5fd26995`.

State in one paragraph: the addon is untouched at `ddba3433`-equivalent; the suite is 353 passed /
3 failed (those 3 are the deliberate T4/T5 acceptance tests); the patch loop was rebuilt from
scratch with a working test gate, worktree isolation, and an arbiter rung, and passes 8/8 offline —
but **has never closed a ticket end to end**. T2 is parked with a live candidate on disk.

```powershell
# free, ~2 min, no models: is the tool sound?
.\.venv\Scripts\python.exe -m scripts.agent_loop.selftest

# free: do all 18 ticket regions still resolve?
.\.venv\Scripts\python.exe -m scripts.agent_loop --list

# the next real action (see §4b)
.\.venv\Scripts\python.exe -m scripts.agent_loop --ticket T2 `
    --resume-raw logs/agent_loop/T2/r3_impl_raw.txt --arbiter glm-5.2:cloud
```

**Do not run `scripts/agent_loop/ollama_patch_loop.py`.** Three of its gates were defective; it is
kept only so the older `logs/ollama_loop/` artifacts stay readable.

---

## 1. What landed

| Commit | Content |
|---|---|
| `5fd26995` | **T1 — P0-1 + P0-4**: stop-guard FSM coverage model |
| `ddba3433` | **Test harness repair** — the suite could not previously catch defects |

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

| Test | Expected | Actual today | Proves |
|---|---|---|---|
| `TestCopyPath_ExitDoesNotFlipFollowerShort` | ≤ 1 | **5** | P0-5: follower left short 4 |
| `TestCopyPath_MicroToMiniDoesNotInflateNotional` | 0 | **1** | P0-6: 1 MNQ → 1 NQ, 10× notional |
| `TestCopyPath_LockedFollowerReceivesNoCopy` | 0 orders | **1** | P0-8: copier ignores lockout |

**Suite state**: was 221 visible tests / 2 failures / 25 skipped. Now **353 assertions, 3
expected failures** — exactly the three above, which go green when T4 and T5 land. Any *other*
failure is a regression.

---

## 2. Current state of play

| Ticket | Defects | Status |
|---|---|---|
| T1 | P0-1, P0-4 | ✅ committed `5fd26995` |
| T2 | P0-2, P0-3 | ⏸ parked with a live candidate that passes every gate but has 13 un-adjudicated findings — see §4b |
| T3 | P0-7 | queued |
| T4 | P0-5, P0-6 | queued — has failing tests waiting |
| T5 | P0-8, P0-9 | queued — has a failing test waiting |

**Nothing beyond T1 is applied. The addon is clean.** T3–T5 are blocked on the loop rebuild
(§3), by decision — they will run on the new tool, not the old one.

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

**Where T2 actually stands.** Its round-3 candidate is on disk at
`logs/agent_loop/T2/r3_impl_raw.txt` and **passes every mechanical gate** — compiles, 353 passed /
3 failed with no regressions, no broker call under `_stateLock`. What it has never had is an
adjudication of its 13 findings. That is exactly what the arbiter was built for, and T2 is its
natural first case.

Note the gates only prove no *regression*: the suite has no coverage for the P0-2/P0-3 paths, which
is why those defects exist. Passing gates is necessary, not sufficient.

## 4a. Immediate next steps

1. **Run T2 with the arbiter** (command in §0). Read `logs/agent_loop/T2/rN_arbiter.txt` before
   trusting the outcome — this is the arbiter's first live use and its rulings are unvalidated.
   Promote only after reading `final.patch`:
   `--resume-raw <candidate> --allow-unapproved --apply`, then stage explicit paths and commit.
2. **If it escalates or still will not converge, split T2** into P0-2 and P0-3 as separate tickets
   with tighter region sets. `ExecuteAction` at 168 lines is very likely too much surface for one
   patch, and that hypothesis is untested.
3. **T3, T4, T5** in order, committing each. T4 and T5's acceptance criterion is the three baseline
   failures going green — now checked mechanically by the test gate rather than by eye.
3. **T3, T4, T5** in order, committing each. T4 and T5 should turn the three failing copy-path
   tests green — that is their acceptance criterion, and it is now checked mechanically by the
   test gate rather than by eye.
4. **Add tests for T1/T2/T3 behaviour** (currently only T4/T5 have failing tests waiting). Good
   candidates: stop cancelled mid-position re-arms grace; auto-stop submit failure rolls back and
   clears `GraceEmitted`; auto-stop sized from live position, not the emission snapshot;
   profitable-flat account emits no giveback action.

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
