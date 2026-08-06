# RiskGuard / TradeCopier Hardening — Session Handover

**Session date**: 2026-08-06
**Branch**: `harden/riskguard-copier-p0`
**Plan of record**: [RISKGUARD_COPIER_HARDENING_PLAN.md](RISKGUARD_COPIER_HARDENING_PLAN.md) (31 defects, P0→P3)
**Nothing is deployed.** NinjaTrader is running live with the *unmodified* addon.

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
| T2 | P0-2, P0-3 | 🔄 in flight — see §4 |
| T3 | P0-7 | queued |
| T4 | P0-5, P0-6 | queued — has failing tests waiting |
| T5 | P0-8, P0-9 | queued — has a failing test waiting |

---

## 3. The loop (how the work gets done)

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
work in the same file would be destroyed by the next ticket.

---

## 4. Immediate next steps

1. **Check T2** — `logs/ollama_loop/T2/` and the background task output. If it applied, run the
   suite (expect 3 failures, no more), then commit. If it stopped at `MAX_ROUNDS_EXHAUSTED`,
   read `r*_review_*.txt`, decide which findings are real, and re-run with `--resume-raw` plus an
   `--orchestrator-note`.
2. **T3, T4, T5** in order, committing each. T4 and T5 should turn the three failing copy-path
   tests green — that is their acceptance criterion.
3. **Add tests for T1/T2/T3 behaviour** (currently only T4/T5 have failing tests waiting). Good
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
