# RiskGuard / TradeCopier Hardening — Session Handover

**Last updated**: 2026-08-11 (session 13 — **the copier RATIO CONVERTER, slice 1 of 3, is
implemented and green but NOT deployed — §4w**. A feature, not a defect: no `P`-number, nothing
closed. **Next work is either slice 2 (cross-instrument `1 MNQ -> 3 MES`) and slice 3 (making the
table settable from disk and the bridge at all), or the still-open `P0-62` — §4a and §4w.**)

> ⚠️ **Session 13 touched NO defect.** The 62/49 counts below are unchanged and correct. Slice 1
> is unit-tested and compiles; it has **never run on a live feed**, and the deployed build is
> still session 12's `f174ba68`.
>
> ⚠️ **Do not treat `ARBITER_SHIP` from the agent loop as a review on this addon.** Across four
> SHIP rulings in session 13 the arbiter upheld **0 of 66 panel findings**, and on one plan the
> panel was right about a signed exit quantity that would have **increased a follower position
> sitting opposite the leader** — `P1-56`'s class, in a plan the arbiter shipped. Read the patch
> against the file. §4w.

**Branch**: `harden/riskguard-p0-51` — **not merged, not pushed.** `main` is untouched.
**`wip/p09-oco-target` is SUPERSEDED** — its work was rebased and shipped as `86c6376f`; do not
deploy or rebase that branch, it predates the holder split and lacks five fixes (§4r).
**Plan of record**: [RISKGUARD_COPIER_HARDENING_PLAN.md](RISKGUARD_COPIER_HARDENING_PLAN.md) — **62 defects, 49 closed**
(`P1-57` and `P2-58` opened 2026-08-10 by watching another copier work — §4p; `P2-58` closed same day)
**Live state**: deployed, `shadow`, feed connected, **all accounts flat, no working orders**.
NT8 compiles clean (0 errors, net48), all **10** addon files in sync (`CopierReconciler.cs` is new).
**The deployed build is `f174ba68`** — session 12's `P0-61` fix, on `harden/riskguard-p0-51`.
(`06c6a484` was the reconciler itself, 15:20–15:48.)
(Earlier builds 2026-08-10: `b5c58ae0` the order-liveness model, `86c6376f` 13:12–14:32,
`c9459121` 06:19–13:12, `995f6402` before that.)
Suite **806 passed, 0 failed** (789 + 17 new CM1 acceptance tests, §4w; it was 787 before session 13 added two more alongside them).

> ✅ **`P0-9`'s mirrored target is CLOSED and deployed (2026-08-10, `86c6376f`).** Followers now get
> the leader's target as well as its stop, in one OCO group, anchored to their own fill. The
> longest-standing "explicitly not done" item in the plan.
>
> ✅ **Live-validated 2026-08-10 on `Sim101 -> Sim-ORB` (§4s), 3 signals of 4.** Both legs mirrored
> into one OCO group at the right distances, on tick, 14 ms after the follower's fill. **The
> single-member OCO group on the stop is accepted by NT8** — that was the one way this change could
> have been worse than what it replaced, and it is now proven rather than inferred.
>
> ✅ **The fourth signal failed, and the defect behind it (`P0-59`) turned out to be one half of a
> larger one (`P0-60`). Both are now closed — see §4t.** NT8 has sixteen `OrderState`s; the two
> addons classified eight between them and **inferred opposite things about the rest**. RiskGuard
> counted a stop being cancelled as coverage (naked position reported as protected); the copier
> counted a leg being modified as gone (duplicate protective leg). Replaced by **one total
> classification with two derived predicates**, `OccupiesSlot` and `ProvidesCoverage`, because the
> two questions callers ask have opposite fail-safe answers.

> ✅ **Seven defects closed since the 2026-08-09 incident**, all deployed and compiling clean:
> `P0-51` (shadow restrained neither the lockout sweep nor the deferred cancel queue), `P1-52` (a
> 2-lot ATM bracket counted as an order flood), `P0-53` (the lockout cancelled a protective stop
> while its position was open), `P1-54` (lockouts never lapsed), `P0-55` (a partial-fill entry left
> the follower with no mirrored stop), `P1-56` (concurrent bracket syncs left **two** protective
> stops — qty 1 *and* qty 2 behind 2 lots, which flips the follower when both fire), and `P0-9`
> item (1) above.
>
> **Only `P0-51` and `P1-52` of those are validated live** (§4n). The rest are unit + compile only.
> Analysis in §4m–§4r; what shipped is in each plan entry.
>
> ⚠️ **Two agent-loop candidates for `P1-56` would have shipped live defects, and both passed every
> gate** — one leaked the reservation forever, one turned the submission bound into 9 attempts and
> reintroduced the defect. The transferable lesson is in §3 and
> [AGENT_PATCH_LOOP.md](AGENT_PATCH_LOOP.md) §9, not in the defect.
>
> ⚠️ **`P1-57` (new) changes how any live validation behaves.** `Sim101 -> Sim-ORB -> {SimCopyTest1,
> SimCopy2}` is a live chain, because `Sim-ORB` is our follower *and* another copier's leader. A
> `Sim101` test trade now reaches **three** follower accounts.
>
> ⚠️ **Do not book live validation outside the permitted edge window.** `EDGE_WINDOW_BREACH` fires on
> an ordinary overnight entry and, armed live, would flatten the trade about a second after it fills
> — destroying the test rather than the defect (§4p).

---

## 0. Start here (read this, then §4a for what is pending)

**49 of 62 defects closed. Suite 787/0. NT8 compiles clean under net48, all 10 addon files in sync,
and both of `P0-9`'s legs are implemented** — the stop validated on real fills (§4l), the target
live-validated (§4s).

**The count did not move this session and that is correct**: `P3-30` and `P3-31` are both still
open, because only the copier's bracket half of the reconciler shipped (§4u). Resist the urge to
tick them.

✅ **The reconciler has now had a live trade (§4v)** — the mirror is exact, and a stray leg the
engine held no reference to was cancelled, which no previous build could do. That trade also found
`P0-61` (fixed and re-validated live) and **`P0-62`, which is OPEN and leaves a scaled-in follower
under-covered.**

### 0.0 ⚠️ Commit SHAs cited in the older sections below no longer resolve

Getting session 7's push through required rewriting history twice — once to purge `data/` (a 126 MB
`NQ1_1m.parquet` exceeded GitHub's 100 MB limit and had been silently rejecting every push for 202
commits), and once to purge 88 MB of `.m4a`. Both rewrites changed every commit SHA in the range.
`1d9566fe`, `76137575`, `922b2c44`, `c5a4f035`, `904d44bc`, `737533a3`, `a2a519fd`, `fb55d281` and
the rest are **orphaned** — the *work* is all present in `main`, only the identifiers are dead. Do
not cite them onward, and run `git cat-file -t <sha>` before trusting any SHA quoted below.

SHAs from session 9 onward (`995f6402`, `c9459121`, `86c6376f`) are on `harden/riskguard-p0-51` and
are live.

**The merge-ordering lesson stands**: that push happened *before* shadow validation, which is the
opposite of what this document recommended. It was a deliberate call to get 282 unpushed commits off
one machine, not a signal that anything was validated.

### Five things to know before you touch anything

**1. The plan's older `**Fix**:` notes are hypotheses, not instructions.** Three "settled"
recommendations were retired this session because following them would have made things *worse*:

- `P1-39` said prefer a serializer-level `ObjectCreationHandling.Replace`. That discards the
  `StringComparer.OrdinalIgnoreCase` dictionaries and silently makes instrument and firm lookups
  case-sensitive. Fixed per-property instead; a test pins the comparer.
- `P1-18` said skip the profile trailing-DD rule whenever `FirmMirror.Enabled`. On the live config
  `FirmMirror.Enabled` is `true` while its `TrailingDD` is `false` and nothing is mapped, so that
  would have left **no trailing-drawdown cover at all**.
- `P1-16`'s obvious fix (judge the trade at the flat transition) silently **drops losses** whenever
  realized PnL lags the position update — an ordering nothing guarantees.

Verify the mechanism against the code before acting on any entry, including ones marked settled.
Settled entries have since been retired for `P1-36`, `P1-13`, and `P0-9`'s "cancel-then-replace, not
modify" — always in this file *and* in `scripts/agent_loop/profiles.py`. Retire from both places or
the review panel keeps arguing for the closed defect.

**2. A machine check is only as good as the paths driven through it.** The lock-scope invariant
was already machine-enforced (`Account.BrokerCallObserver` + `TestIsStateLockHeld()`) and still
missed `P1-43` — four `account.Cancel` calls under `_stateLock` on the order-update path — because
the check only ever drove the sweep and FSM teardown. `S4` now drives every entry point.

**3. Only NT8 proves the build.** `P1-47` compiled clean under net8.0 with the suite green and
failed in net48, because the methods sat inside `#if TESTING`. **Always `nt_compile` after
touching code near the test hooks**, and read `RESULTS:` from a *fresh* build — a `dotnet run
--no-build` after a failed build silently reports the previous assembly's result.

**4. No operational items remain. Both of the ones recorded here are DONE.**

- ✅ **`ShadowSessionsCompleted` reset — done 2026-08-07, session 7.** It read `5`, inflated by
  restarts before `P1-37` was fixed, which made `MinShadowSessions=3` read as satisfied and the
  *live* arming gate untrustworthy. Now `0`, with `LastShadowSessionDate` at `DateTime.MinValue`.
  Backup: `RiskGuard/state.json.bak_20260807_095249`. All 93 `AccountsData` entries and the empty
  `LockedOutAccounts` list were verified unchanged. The next genuine shadow session counts as 1.

  > **The obvious command for this is destructive — do not write `null`.**
  > `LastShadowSessionDate` is a **non-nullable `DateTime`** (`RiskGuardAddOn.cs:4525`, default
  > `DateTime.MinValue`). Json.NET throws converting `null` to it, `LoadPersistedState` catches
  > that and logs `Failed to load persisted state`, and **the entire persisted state is
  > discarded** — every account's PnL baseline and the locked-out list with it. Write
  > `"0001-01-01T00:00:00"` instead. An earlier revision of this handover had the `null` version;
  > it was caught by checking the C# field type before running it, not by testing.
  >
  > Both fields must move together (`P1-37`) — zeroing the count alone lets a restart re-count the
  > same session. `IsArmed` is deliberately left alone: `P1-37` stops it being rehydrated at all,
  > and `P1-47` derives the initial arm state from the resolved mode.
  >
  > **"NT8 closed" really means "the AddOn is not loaded".** The bridge not answering on
  > `localhost:7890` is the reliable check — the listener starts at `State.Configure`. NT8 can sit
  > at its login dialog with the process running and no AddOn loaded, which is when this reset was
  > actually performed.
- ✅ **`POST /api/riskguard/config` now merges (`P2-41`, closed 2026-08-07, verified live).** It
  used to deserialize a partial body into a complete `RiskConfig`, so every omitted field became
  its default and was written to disk while the response echoed your *request* and said
  `"applied"`. The response now returns the **resulting** live config as `config` and your body as
  `requested`.
  > **`nt_riskguard_config` with no arguments POSTs an empty body.** Under the old code that one
  > call flattened the entire live risk configuration. The GET-mutate-POST-GET-diff discipline
  > recorded here is what stood between this box and that happening — and it is still the right
  > habit, but it is no longer load-bearing.

**5. `P0-9` is fully implemented; what is left is live validation, not code.** Followers get a
mirrored **stop and target**, OCO-paired, both anchored to their own fill. Items (3) `StopLimit` and
(4) leader-cancels-stop are pinned by test. **The stop is validated on real fills (§4l). The target
is deployed and has never been seen on one (§4r)** — and the stop path changed with it, so watch the
first live `COPIER_STOP` for a rejection before trusting either.

### What the guard actually does right now

Armed, `shadow`. It evaluates every rule and logs would-be actions; `ProcessAction` returns
`SHADOW (SKIPPED)` before any broker call (`:2895`), so it cannot touch an account. Arming and
acting are **separate switches** — `_isArmed` enables evaluation, `_mode == "live"` enables action.
Since `P1-47` the guard comes up armed in shadow by itself and disarmed in acting modes;
`/api/riskguard/version` reports `mode`, `isArmed` and `guarding`, and coming up disarmed logs
`UNPROTECTED_ON_START`. Arming manually is still UI-only (`TOGGLE ARMED`); `nt_script_execute` does
not work on this box.

**Firm mirror is live but unmapped.** `P1-42` made `AccountFirmMap`/`FirmProfiles` actually load,
but no account is mapped and the top-level sub-rules are disabled, so no firm rule fires. Mapping
`TAKEPROFITPRO524207503` → `TakeProfitTrader` turns on real enforcement with real numbers — do it
deliberately, and run a shadow session on it first.

### Commands

```powershell
# the suite, direct -- ALWAYS build first; --no-build after a failed build
# silently reports the previous assembly's result
cd ninjatrader-addon; dotnet build -v q --nologo; dotnet run --no-build -v q --nologo

# deploy: verify first, then sync, then recompile in NT8 (hot-swaps)
.\.venv\Scripts\python.exe scripts\utils\sync_nt8_strategies.py --verify --only addons
.\.venv\Scripts\python.exe scripts\utils\sync_nt8_strategies.py --only addons
#   then nt_compile, and read errorCount

# free, ~2 min, no models: is the loop tool itself sound?
.\.venv\Scripts\python.exe -m scripts.agent_loop.selftest

# free: do all 18 ticket regions still resolve?
.\.venv\Scripts\python.exe -m scripts.agent_loop --list
```

**The arbiter recommends; it never ships.** A run that ends `ARBITER_SHIP` has *not* applied
anything — and `--resume-raw … --apply` is **not** a promote-what-I-read command, it is a fresh run
seeded with that raw (§4q). To promote an exact candidate, splice it with the loop's `regions.apply`
and diff the result against the `final.patch` you reviewed.

> ✅ **Work is test-first from here.** A ticket declares `expect_green`; the loop refuses it
> unless those tests are already failing at baseline, and fails any candidate that leaves one
> red. Reviewers judge the tests' completeness and accuracy too. This closes the hole T5 went
> through — it reached `ARBITER_SHIP` with its own acceptance test still red. See the plan's
> §6.0.

---

## 1. What landed

The original P0 tickets, all merged into `main` long ago. **Their SHAs are orphaned (§0.0)** and
the table that listed them was removed 2026-08-10; what each one *did* is below, and that is the
part that still matters.

| Ticket | Content |
|---|---|
| T1 — `P0-1` + `P0-4` | stop-guard FSM coverage model |
| T2 — `P0-2` + `P0-3` | reserve-before-submit auto-stop, sized from the live position |
| T3 — `P0-7` | unrealized-only peak for the giveback rule |
| T4 — `P0-5` + `P0-6` | exits clamped to the follower's position; no sub-1 flooring (+ an exit must not round down to zero and strand the follower) |
| T5 — `P0-8` + `P0-9` | copier respects the lockout; fails closed when unguarded |
| — | test-harness repair (the suite could not previously catch defects) |

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

**Suite state at the time**: was 221 visible tests / 2 failures / 25 skipped, then 356 passed / 0
failed once the harness was repaired. **It is 686/0 today.** Any failure is a regression.

---

## 2. Two P0-era findings worth keeping

*(T1–T5 are all long since committed, merged and deployed. The per-ticket status table that used to
sit here was stale and its SHAs are orphaned — see §0.0. Current state is the banner at the top.)*

### Two things found by review, not by the panel
- **T4's exit rounding.** Removing the `Math.Max(1, ...)` floor was right for
  entries — that floor *was* P0-6 — but applying it to exits created the mirror defect: an exit
  that rounds to 0 strands the follower in a position the leader has already left. Not an edge
  case: every partial exit rounds down independently, so a leader who entered 10 MNQ (follower:
  1 NQ) and exits in any increment below 10 produces 0 every time, and even a 5+5 exit strands it
  because `Math.Round(0.5)` is 0 under banker's rounding. Exits now take at least one contract
  when the follower holds one, clamped to the real position size.
- **T3's session reset.** Spec item 1 asks for the new peak fields to be cleared
  where `PeakEquity` is, but neither of those two sites was in the ticket's region set, so the
  loop could not have done it. Added by hand.

### Known-acceptable residue in T2 (do not re-open without new evidence)
- ~~A dead clause survives in `ExecuteAction`~~ — removed. Recorded because the
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

## 3. The loop, and what its history taught us

**Use `python -m scripts.agent_loop`** — full documentation in
[AGENT_PATCH_LOOP.md](AGENT_PATCH_LOOP.md), commands in §0. Its own backlog is that doc's §12.

> ⚠️ **Do not run `scripts/agent_loop/ollama_patch_loop.py`.** Three of its gates were defective:
> an empty reviewer response scored as a dissenting vote so no candidate could ever pass; the
> lock-scope gate closed its scope before the Allman brace and was therefore inert for 28 of 32
> sites; and `summary.json` was overwritten per invocation and is not a ledger. It is kept only so
> the older `logs/ollama_loop/` artifacts stay readable, and **a green run from it is not
> evidence**.

> **§4, §4b, §4c and §4d were retired on 2026-08-10.** They were per-round post-mortems of that
> dead tool. The lessons below are what survived; nothing else referenced them. Section letters are
> deliberately **not** renumbered — they are stable identifiers cited from the plan, from
> `CLAUDE.md` and from older transcripts, so a gap is cheaper than a shifted reference.

**Five lessons, all paid for, none specific to the old tool:**

1. **Unanimous APPROVE from adversarial reviewers is unreachable, and the finding count going *up*
   after a minimal fix is the signature.** Three rounds against one 168-line method produced 11 then
   13 findings with **zero overlap**; a two-line fix in the next round drew 33. That is why there is
   an arbiter.
2. **Reviewers contradict each other on load-bearing facts.** On `AutoStopAttempts`, glm read the
   state machine correctly and deepseek asserted the exact opposite. Verify against the code.
3. **A reviewer's *proposed fix* can be worse than the defect it names**, and this has now happened
   repeatedly — see §4q, where all three of panel, panel and arbiter endorsed a fix that would have
   leaked a reservation forever.
4. **A 0-upheld arbiter ruling is not reassurance.** Read the patch (§4q).
5. **Confirm the candidate you promote is the one that was reviewed.** The old loop once printed a
   `promote:` hint naming a file it had never seen; the new loop's `--resume-raw … --apply` is a
   *fresh run*, not a promotion. Different mechanism, same failure, twice.

**Gates only prove no regression.** The suite had no coverage for the P0-2/P0-3 paths, which is why
those defects existed at all. Passing gates is necessary, never sufficient.

---

## 4a. What is pending — the current backlog

> **Also pending, and NOT a defect:** the copier ratio converter, slices **2** (cross-instrument
> `1 MNQ -> 3 MES`) and **3** (parsing `PerTickerRatios` from the config JSON and exposing it on
> the bridge — today it is settable only from code, so the shipped slice 1 is **not reachable from
> the UI**). Slice 1 is implemented, green and undeployed. See §4w for what is settled and what
> will bite. Neither slice carries a `P`-number.

**62 defects, 49 closed, 13 open.** `P0-61` (closed) and `P0-62` (open) were both opened
2026-08-10 by the live test in §4v. Band membership and the P1-30/31 → P1-35/36 renumbering are
in the plan's inventory table. *(The phase list A–G that used to close this section was retired
2026-08-10: A–G were all done or superseded and it had drifted out of agreement with this list.)*

**What is validated live**: `P0-9`'s mirrored **stop** (§4l — 1 ms after the follower's fill, at
exactly `followerEntry + (leaderStop - leaderAvgPrice)`, FSM created `ProtectedPending`), `P0-51`,
`P1-52`, `P2-41`, `P0-48`, T3's giveback rule (§4g), and **`P0-9`'s mirrored target** (§4s — 3
signals of 4; the fourth opened `P0-59`), and **the reconciler + `P0-61`'s fix** (§4v — the mirror
is exact, a stray leg is cancelled, and a deferred change is re-applied when the leg settles).

**What is NOT**: `P0-53`, `P1-54`, `P0-55`, `P1-56` (unit + compile only); `T5`'s fail-closed gate, which
needs an acting mode (`IsGuardProtecting` requires `mode == "live"`); and the firm-mirror rules,
which are loaded but unmapped. **The copier acts regardless of guard mode** — `shadow` restrains
RiskGuard, not the copier.

### START HERE — the reconciler is the primary path now; finish it

> 🔶 **`P3-30`'s copier half SHIPPED 2026-08-10 (§4u).** `CopierReconciler.cs` is new, and both leg
> syncs decide through `ComputeDesiredBracket` + `Reconcile` instead of from one cached `Order`
> reference. A duplicate leg is now self-healing. Suite 762/0, net48 clean, deployed.
>
> **The next four pieces, in order:**
> 1. **`P0-62`** — a live, open, naked-risk-adjacent defect, so it outranks the enhancement work.
>    `Change()` applies the price but silently refuses a quantity INCREASE, so a scaled-in follower
>    keeps an under-sized protective leg. Two candidate remedies with real costs are written up in
>    the plan entry. **Do not just widen the retry budget.**
> 2. **`P3-31`'s ledger** — required *before* the timer, not after. Between `Submit` and `Accepted`
>    the order is in neither `Account.Orders` nor the cache, so a timer without the ledger creates
>    the second leg. The seam in `Reconcile` is built and tested; the ledger is not.
> 3. **The background timer** — events call the reconciler; nothing calls it on a clock. A
>    divergence arriving with no subsequent event is still permanent. `P0-62` is an example: after
>    the budget gives up, no event brings it back.
> 4. **The RiskGuard-side audit** — naked position, orphan stop, FSM/broker divergence. `P3-30`
>    covers both addons; only the copier's bracket is done.
>
> ⚠️ **Do not confuse `bracket.StopInFlight` with `Reconcile`'s in-flight parameter** when you build
> the timer. Feeding the first into the second placed no stop at all. §4u has the mechanism.
>
> ⚠️ **Two guards in this code are unreachable and labelled as such** (§4u). One mutation SURVIVED
> and is kept deliberately. Read §4u before "simplifying" either.

The rest of this section is the reasoning that led here, and it still stands.

`P0-59`/`P0-60` are closed (§4t), and closing them properly rather than patching the symptom is
what this section is now about.

**The structural finding.** Almost every defect in this project is one shape: *the addon's model of
broker state diverged from the broker, and nothing re-derived it.* The plan said so on page one —
"the FSM is an optimistic fast path… **every P0 below is a case where the fast path can lose the
position and nothing recovers it**" — and then 48 defects were closed by making the fast path handle
one more case. `P3-30`, the item that addresses the class, has never been started, and
`ReconcileFollowerPosition` has sat written-and-never-called the whole time.

**So the next work is `P3-30` + `P3-31` together, built as the PRIMARY mechanism rather than as an
auditor bolted alongside the FSM:**

1. `ComputeDesiredBracket(leader, follower, relationship) → DesiredBracket` — **pure**, computed
   from broker reads with no accumulated state. Every arithmetic defect (`P0-6`, `P0-7`, the signed
   offset, the exit rounding, off-tick prices) becomes a property test here.
2. `Reconcile(desired, owned, inFlight) → Actions` — **pure diff**, and it cancels *extra* owned
   legs. That single rule makes duplicate legs self-healing instead of permanent.
3. Events **and a timer** both just call it. Idempotent, so ordering stops mattering — which
   dissolves `P0-49`, `P0-55`, `P1-56`, `P0-59` as a class rather than one at a time.

> ⚠️ **A reconciler without the in-flight ledger reproduces the duplicate-leg family**: between
> `Submit` and `Accepted` the order is not yet in observed state, so a naive second pass creates a
> second one. `P3-31` is not a follow-up to `P3-30`, it is half of it.

Doing this makes several things we currently maintain by hand unnecessary: `P1-56`'s reservation,
the OCO dead-group conditional, the multi-target refusal, and the `StopInFlight`/`StopResyncOwed`/
`TargetInFlight`/`TargetResyncOwed` flags.

Then `P1-57` — §4s showed its defence held only because the third-party copier happened to embed
our name in its own; a native `Stop1` would have gone straight through.

> **Booking a live session**: `MAX_TRADES_BREACH` now fires on entry on `Sim101`/`Sim-ORB`
> (`MaxTradesPerSession` 8, both past it), as well as `EDGE_WINDOW_BREACH` outside the edge window.
> Armed live either one flattens the trade and cancels its mirrored legs. And a `Sim101` trade
> reaches **three** follower accounts (`P1-57`).

### Ready to code, in value order

| | What | Note |
|---|---|---|
| 1 | **`P3-30` — the reconciler: timer + RiskGuard-side audit** | 🔶 **The copier's bracket half is done (§4u).** What remains is the clock and the guard-side audit (naked position, orphan stop, FSM divergence). `P3-31`'s ledger comes *before* the timer. `P1-36` built the multi-stop coverage sum the audit needs; share that, do not rebuild it. |
| 2 | **`P1-13` — the threading inversion** | **Two pieces of work, not one.** A concurrent-guard-event stress test has to exist first; see the warning below. |
| 3 | **`P2-26` — design-doc drift** | Cheap, and `RiskGuardAddOn.md` is *actively misleading* right now: 8 claims contradicted by code. |
| 4 | **`P2-24` — written-but-never-called safety machinery** | Includes `ReconcileFollowerPosition`. Needs a dispatcher seam to be testable (see §6). |
| 5 | **`P2-25` — the news shield can never fire in production** | |

### Low value or mechanical

`P2-27`'s remaining CI job (the copy path itself is already covered), `P2-29` (split the two large
files into `partial class` files), `P3-31`, `P3-33`, `P3-34`.

> **`P3-32` ("follower risk anchored to the follower's own fill") looks SUPERSEDED by `P0-9`** —
> that is precisely what the signed-offset mirror does. Read it before scheduling it as new work;
> it may simply need closing. Flagged 2026-08-07, not yet verified.

### ⚠️ The S-series is not concurrency coverage

`S1`–`S9` are all in the suite as of session 8, and it is tempting to read "the stress backlog is
done" as covering `P1-13`. **It does not.** `S4` is lock-scope, `S7` is copier fan-out, and
`S5`/`S6`/`S8`/`S9` are **sequential scenario tests**. `P1-13`'s inversion turns six handlers the
dispatcher was implicitly serialising into genuinely concurrent ones, and nothing tests that.

Session 8 deferred `P1-13` explicitly on the grounds that the stress backlog was its prerequisite.
Once that backlog was written it was clear the reasoning was wrong: the tests are sequential and
the risk is concurrent. **Doing the risky half before its coverage exists is how `P1-40` shipped.**

### Repo hygiene — still open

- **`harden/riskguard-p0-51` is unmerged and unpushed**; the deployed build is `b5c58ae0`.
  `main` is untouched. ✅ **`wip/p09-oco-target` was DELETED 2026-08-10** (its tip was `fca83e19`,
  recoverable from reflog for the usual 90 days, but do not) — its work was rebased and shipped, and
  the branch as it stood lacked five fixes (§4r). Rebasing it would have re-introduced them.
- **The Gemini API key** scrubbed from history (`scripts/trader/chart_agent/test_vision.py`) still
  needs **rotating**. It never reached GitHub; that is not the same as it being safe.
- **0.28 GB of older parquet remains in published history** — the purges only covered the
  then-unpushed range. Logged in `docs/ROADMAP.md` under Known Issues / Tech Debt.
- `.githooks/pre-commit` is **not automatic**: run `git config core.hooksPath .githooks` in each
  clone or it silently does nothing.

---

## 4e. Deployment runbook

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
4. **Sync with the script, never by hand.** `sync_nt8_strategies.py --verify --only addons` to see
   the drift, then the same command without `--verify`. Then `nt_compile` and read `errorCount`.
   The test build is net8.0 with stubs, NT8 is net48, and **only NT8 proves the real build**.
   **Put backups outside `bin/Custom/`** — NT8 compiles that tree recursively and a backup folder
   of `.cs` files causes duplicate-type errors.
5. **Check the box is quiet first** — `nt_compile` hot-swaps the running addon. `nt_positions` and
   `nt_orders` should show no open positions and no *working* orders (terminal leftovers are fine).
6. Run a full session in shadow **on a real-time feed**. Kinetick End Of Day gives no Level 1, so
   the simulator cannot fill and no guard path will execute — a session on that feed proves
   nothing. Then read `interventions.jsonl` and ask specifically: did `PEAK_GIVEBACK_BREACH` fire
   on a profitable flat account (T3), and did any `COPY_BLOCKED_NO_GUARD` line name an account
   that should have been allowed (T5)?
7. Only then consider restoring an acting mode. *(The `P1-37` / `ShadowSessionsCompleted` step that
   used to sit here is done — see §0 item 4.)*

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

## 4g. Validation record — 2026-08-07, armed + shadow, real-time feed

The first session in which **any guard path has ever executed**. Feed: TPT (real-time; Kinetick
EOD was disconnected at 12:56 UTC). Mode `shadow`, `isArmed: true` from 13:21:30 UTC after
`PREFLIGHT: passed`. `TAKEPROFITPRO524207503` (the only funded account, $50k) was added to
`ExcludedAccounts` first and confirmed live in memory before arming.

**Setup.** Test account `SimCopyTest1` — Simulator provider, and deliberately not a leader or
follower in either copier relationship (both are `Sim101 → {Sim-ORB, SimCopy2}`), so the copy path
could not confound the result. One MNQ, no attached stop.

| Time (UTC) | Event |
|---|---|
| 13:24:06.036 | entry filled @ 29721.75, Long 1 |
| 13:24:06.396 | `FSM_TRANSITION` — FSM created → `Unprotected`, grace deadline 13:24:09 |
| 13:24:08.78 | `SHADOW_ACTION` FlattenPosition ← **`PEAK_GIVEBACK_BREACH`** (position at −$1.00) |
| 13:24:09.41 | `SHADOW_ACTION` FlattenPosition ← `MISSING_STOP_FLATTEN` (grace expired, no stop) |
| 13:24:10.79 … :40.08 | `PEAK_GIVEBACK_BREACH` ×5 more |
| 13:24:42.22 | exit filled @ 29726.00 |
| 13:24:42.428 | `FSM_TRANSITION` — FSM torn down → `Flat`; realized **+$8.50** |

**What passed.**
- **T3 acceptance criterion — MET.** The account finished **flat and profitable** (+$8.50) and
  emitted **zero** `PEAK_GIVEBACK_BREACH` after `13:24:42.428`. Pre-fix, a peak that included
  realized PnL against a zero unrealized read as a 100% giveback and fired on exactly this state.
- **FSM lifecycle works live**: creation on fill, grace deadline set from
  `StopAttachSeconds`, clean teardown to `Flat` on exit, `nt_riskguard_state` reporting it
  throughout.
- **`MISSING_STOP_FLATTEN` fired correctly**, once, at the grace deadline, on a genuinely
  unprotected position — T1/T2's path behaving as designed.
- **Shadow containment holds.** All seven actions logged `[SHADOW] Would execute …` and the
  position stayed open until *I* closed it. `:2895` (`isLive = _mode == "live"`) is doing its job.

**What failed — `P1-40`, now CLOSED the same session.** `PEAK_GIVEBACK_BREACH` fired **six times
in 36 seconds** on a position whose entire excursion was a few dollars, the first time 2.4 s after
entry with the position *down* $1.00. The rule was proportional-only with no floor on the peak, so
a one-tick peak ($0.50 on MNQ) made any retrace a ≥100% giveback. In an acting mode it would have
flattened nearly every trade seconds after entry and realised the loss doing it. Fixed test-first
with `MinPeakGainDollars` (default 50) and redeployed; see the plan's P1-40.

**T5 was not testable and could not have been.** `IsGuardProtecting` (`:875`) requires
`mode == "live"`, so in shadow it is false for every account. Both copier followers are Simulator
accounts anyway, which skips the `COPY_BLOCKED_NO_GUARD` gate entirely. That criterion needs an
acting mode.

**Net**: half validated. T3 is proven on a live feed and the one blocker the session found is
closed. T5 still requires an acting mode and has never been exercised.

**State left behind.** `TAKEPROFITPRO524207503` has been removed from `ExcludedAccounts` and is
covered again. Live config: mode `shadow`, **6** `WindowsET` entries matching disk exactly now
that P1-39 is closed. The addon was **re-armed at 13:55:55 UTC** after both fixes landed
(`PREFLIGHT: passed` → `isArmed: true`) and is collecting shadow data against live trading. Note
that any recompile reloads the addon and disarms it again — `_isArmed` is deliberately never
rehydrated (P1-37), so check the log before assuming the guard is watching.

**What that session will and will not cover.** Stop-guard and PnL/giveback paths: covered. **Firm
mirror: not covered at all** — `P1-42`, found while scoping this session. `ComputeFirmMirror`
reads only the top-level `TrailingDD`/`DailyLoss`, both `Enabled: false` here, and never consults
`AccountFirmMap`/`FirmProfiles`. The four researched firm profiles, including the real TPT $1,500
EOD trailing drawdown, are dead config. Mapping the account would not change it. Do not read a
clean firm-mirror log as evidence of firm-mirror protection.

**Worth watching in the log**: `StopGuard.OnMissing = "Flatten"` with `StopAttachSeconds = 3`.
ATM entries attach their stop in ~0.35 s and are fine; a manual entry that takes longer than 3 s
to get a stop will log a would-be flatten. Learn whether 3 s matches real trading habits before
that ever becomes an acting rule.

---

## 4h. Session 6 record — 2026-08-07

Twelve defects closed in one session, on a live feed with the guard armed in shadow throughout.
Suite 427 → **481**, closed 24 → **30 of 47** (five of the new ones were *opened* this session).

| Closed | What it was |
|---|---|
| `P1-40` | Giveback rule was proportional-only; a one-tick peak made any retrace a ≥100% breach. Fired **6× in 36 s** live, first at 2.4 s after entry with the position *down* $1.00 |
| `P1-39` | Json.NET appended the default `WindowsET` on every load; a default window could never be deleted, so the window gate silently widened |
| `P1-16` | One trade exited in three partials counted as three consecutive losses |
| `P1-17` | Cumulative $3,000 evaluation target was fed session-scoped PnL, so it only fired if cleared in a single day |
| `P1-18` | Two trailing-drawdown implementations with undefined precedence |
| `P1-19` | A flatten scoped to MES closed MNQ too; one evaluation pass issued five account-wide flattens |
| `P1-42` | `AccountFirmMap`/`FirmProfiles` were read by no evaluation path — the funded account had no firm protection, and mapping it would not have changed that |
| `P1-43` | Four `account.Cancel` calls under `_stateLock` on the order-update path |
| `P1-44` | Flood cancel had no reducing-order guard and could cancel a protective stop |
| `P1-45` | Flood lockout set no `LockoutUntil`, so it never lapsed, and it was persisted |
| `P2-46` | Flood detector counted `Submitted` and `Accepted` as two orders — the nominal 5/sec limit fired near 3/sec |
| `P1-47` | Guard defaulted to disarmed, so every recompile silently removed all protection |
| `P1-23` | Symbol translation was case-sensitive and used a global `Replace`; two sizing modes silently degraded to 1:1 |

### How they were found — worth repeating

**The operator's order-flood stress test produced four of them in an afternoon** (`P1-43`–`P2-46`)
by reading `interventions.jsonl` back. A green suite and months of review had not. That is why
`S1`–`S9` now exist as a standing programme (plan §8) rather than an ad-hoc exercise.

**Reading the live log answered a real trading complaint.** The operator reported being locked out
after a single losing trade. The archive showed `CONSECUTIVE_LOSS_BREACH` flattens on **funded**
accounts (`TAKEPROFIT273495429` 66, `TAKEPROFIT619225465` 27, `TAKEPROFIT648470602` 18). Cause:
scale out at profit, runner comes back to the stop → the last realized delta is negative → the
whole trade recorded as a **loss despite netting a profit**. Three such trades hit
`MaxConsecutiveLosses`. `P1-16` fixes it — the trade is now judged on its net.
*(The runner itself was ordinary price action, not the guard. Only one `MISSING_STOP_FLATTEN` ever
touched a funded account.)*

### Two mistakes made and caught, recorded so they are not repeated

**The first draft of S1–S4 was vacuous.** Passing `null` as `sender` made `ExecuteOrderUpdate`
throw on `(Account)sender` inside its own `try/catch`, so every call was swallowed and **three
assertions passed against code that never ran** — including the lock-scope one. Only the
assertions expecting a *positive* effect failed and gave it away. Once fixed, the same test found
8 violations. **A stress test that drives nothing reports safety.**

**A `dotnet run --no-build` after a failed build reports the previous assembly.** This produced a
false green twice. Read `RESULTS:` only from a build that compiled.

### State left on the box

Deployed and compiling clean. `shadow`, **armed** (self-armed since `P1-47`).
`TAKEPROFITPRO524207503` is covered — it was excluded during T3 validation and restored
afterwards. `config.json` is clean at 6 windows and the live config now matches it exactly.
All accounts flat.


---

## 4i. Session 7 record — 2026-08-07: P1-21, and the defect it uncovered

**`P1-21` closed. Suite 481 → 486. NT8 compiles clean, guard self-armed through the reload.**

The ticket itself was small. What it found was not.

### The structural obstacle, and what was done about it

`P1-21` lives in `McpBridgeAddOn.cs`, which **`RiskGuardTests.csproj` excludes from the test
build**. So does `P2-38`. Under the test-first rule that is a dead end: no acceptance test can
reach the code.

The subscription bookkeeping was therefore moved to `TradeCopierEngine`, which *is* in the test
build — `RefreshAccountSubscriptions()`, `UnsubscribeAllAccounts()`, `SubscribedAccountCount`.
`McpBridgeAddOn` keeps only the four-line `Connection.ConnectionStatusUpdate` wiring. **When a
defect sits in an untestable file, moving the logic to a testable one is usually cheaper than
arguing about coverage** — and here it was also the better design, since the copier should own its
own subscriptions.

`verify_backfill_reverts.py` now reverts across multiple files (it was hardcoded to
`RiskGuardAddOn.cs`). All **9/9** cases falsifiable, including the three new ones — each observed
failing for the intended reason: 0 copies, 5 handlers, 1 surviving handler.

### P0-48 — 57 orphaned handlers, found by looking rather than by testing

The teardown half was written as defensive housekeeping. Checking whether it actually worked meant
reading the live event list through `POST /api/dev/reflect`, which returned **67 handlers on
`Sim101.ExecutionUpdate`** — **57 of them orphaned `McpBridgeAddOn` instances**, one per historical
AddOn reload, each with its own assembly's `TradeCopierEngine` singleton and its own dedupe set.

`RiskGuardAddOn` sat at exactly 1, because it already unsubscribes at `State.Terminated`. That
control is what makes the reading conclusive rather than suggestive.

Full detail, measured table, and the honest limit of the claim (handlers measured, duplicate copies
inferred) are in the plan under `P0-48`. **It requires an NT8 restart**; see the banner at the top.

### P1-22 — measurement, and a defect caught by reading rather than testing

`LatencyMs` and `AvgSlippageTicks` were rendered in the copier UI and written by **nothing**, so it
reported a clean `0ms / 0.0t` however badly a copy filled. Both are now populated from the
follower's own fill, plus a `MaxSlippageTicks` ceiling. Full detail in the plan under `P1-22`.

The part worth remembering: **the pending-copy map was first keyed on `Order.OrderId`, and every
test passed.** `RiskGuardAddOn.cs:4481` already warns that NT8's `OrderId` is neither unique nor
stable across the historical→live transition — the addon tracks recognised stops by object
reference for exactly that reason. The suite could not see it because the test stub assigns one
stable GUID per order, so the stub was *more forgiving than production*. Found by grepping the
production call sites for the API before trusting it, not by a red test. It is now keyed by object
reference (`OrderReferenceComparer`, using `RuntimeHelpers.GetHashCode`), and
`TestCopierSlip_FillIsMatchedWhenOrderIdChanges` makes the stub behave like NT8.

Two design decisions that go against the plan's own `**Fix**:` note, both deliberate:

- **Quarantine is entry-only; a quarantined relationship still copies exits.** The note says
  simply "quarantines the relationship when exceeded". Implemented literally, `IsQuarantined`
  blocks *every* copy — including the one that closes the follower out — stranding it in a
  position the leader has already left. That is `P0-5` reached by another route. Fourth time an
  older `**Fix**:` note would have made things worse if followed as written.
- **Limit-with-offset entries are not implemented.** The note lists it as "consider". It turns a
  guaranteed fill into a maybe-fill, and an unfilled entry diverges the follower's size from the
  leader's with nothing to reconcile it — `P0-9`/`P3-30` territory, not this ticket.

`verify_backfill_reverts.py` is at **14/14**. The price-comparability revert is the one to look
at: with the guard removed the ES↔MNQ case records **−52,000 ticks** and quarantines a healthy
relationship on its first copy.

### Three things worth carrying forward

1. **A green suite and a clean compile said nothing about this.** The defect is in *runtime object
   graph state accumulated across reloads* — a category no unit test in this repo can observe. The
   only thing that found it was inspecting the live process.
2. **`POST /api/dev/reflect` is the tool for that, and it works.** `{"result": N}` chains handles
   between ops; integer args need `{"type":"System.Int32","value":N}` or they arrive as Int64 and
   the invoke fails. A handler census is a two-minute read-only query — **add it to the deployment
   runbook**, since nothing else detects this class of bug.
3. **"It compiles and the tests pass" was true and irrelevant.** The same reload churn §4f
   describes as benign — "it settled by itself" — was silently accruing these handlers the whole
   time. That churn was written off twice in this document before anyone counted.

---

## 4j. Session 7, second half — P0-9, S7, and the loop's review mode

Eight commits. `P1-21` → `P1-22` → `P0-48` verified → `P0-9` → review mode. The through-line worth
carrying: **three separate defects this session were found by asking a question, not by a gate.**

| Commit | What |
|---|---|
| `4b724fbe` | `P1-21` closed; opened `P0-48` (57 leaked handlers) |
| `6e6d9905` | `P1-22` closed — latency/slippage measured, `MaxSlippageTicks` ceiling |
| `d399c976` | Shadow-counter reset, and corrected a destructive command in this file |
| `922b2c44` | `P0-48` closed and **verified live** |
| `76137575` | `P0-9`'s naked-follower half + stress test `S7` |
| `290ce6d1` | Signed-offset fix — a trailed stop was being inverted |
| `1d9566fe` | Loop `review` mode + the two defects it found |

### P0-9 — what shipped, and what did not

Followers are no longer naked. The copier subscribes to `OrderUpdate`, recognises the leader's
protective stop, and mirrors it **by signed offset anchored to the follower's own fill**:

```
followerStop = followerEntry + (leaderStopPrice - leaderPositionAvgPrice)
```

Copying the leader's stop *price* would be wrong by exactly the slippage `P1-22` measures, and
wrong by a whole price scale across a micro/mini conversion.

**Still open under `P0-9`** — read the plan before assuming it is done: profit targets and OCO,
`StopLimit` limit offsets (assessed as safe: `StopMarket` is *more* likely to fill, so the
divergence runs toward the follower being protected), and a leader that cancels its stop while
staying in position. `EnableFollowerAtm`/`FollowerAtmStrategyName` were **deleted**, not
implemented — they were unreachable config that could not be set by any means while implying
followers got a bracket.

> **A copier-side default bracket was deliberately not built.** RiskGuard's auto-stop already owns
> "position with no stop". Two independent stop sources on one position over-cover and flip it when
> both fire — the same hazard the cancel-then-replace rule prevents *within* the copier, but across
> two components that cannot see each other.

### The three defects that gates did not find

**1. The signed-offset inversion (`290ce6d1`).** `Math.Abs` discarded the sign, so a leader
trailing its stop into profit — stop above entry on a long, the most ordinary trade management
there is — mirrored onto the *losing* side of the follower's entry, converting a locked-in gain
into open risk of equal size. It survived a green 515-test suite, a clean net48 compile and a
20/20 falsifiability check. **The trail test moved the stop 17990 → 17995 → 17998, all below
entry, so it could never have caught it.** Found because the operator asked whether the
`StopLimit` conversion could trigger wrong orders; answering honestly meant re-deriving what price
the follower's stop lands on.

**2 and 3. Naked-on-failure (`1d9566fe`), found by review mode.** A stop whose `Submit` threw, or
which the broker rejected moments later, left `WorkingStop` null with a valid offset and **nothing
re-triggered submission** — naked for the life of the position. And the `OrderUpdate` reporting
that rejection **was being received and discarded**, because the handler returned early for any
account with no relationships, which every follower is.

### Loop `review` mode — built, and it earned its keep immediately

`--mode review --review-base <ref>` puts a committed diff in front of the panel and arbiter. No
implementer, no regions, no worktree, no apply path. Full design and properties:
[AGENT_PATCH_LOOP.md](AGENT_PATCH_LOOP.md) §11; the mode backlog is §12.

It exists because **`patch` mode's guarantee does not hold for hand-written work.** Gate 0 makes
`*Tests.cs` unreachable to the implementer precisely so the grader is independent. When one author
writes the change *and* its tests, the tests encode the cases that author already thought of, and
the suite goes green for the same reason the bug got written.

First run, on the `P0-9` diff: **24 findings, 3 upheld, 8 rejected, 13 out of scope.** Two upheld
were real (above). **The third was wrong and the arbiter upheld it anyway** — it claimed a 10-point
ES stop becomes "10 follower-points" on MES, but every pair in the matrix trades at the same price
with the same tick size and only the dollar multiplier differs, which quantity scaling handles.
**Read the rulings** — the arbiter is not a rubber stamp, but it is not sufficient either (§3.4).

> **Fixing an upheld finding introduced the defect a REJECTED finding described.** Re-submission
> creates exactly the reject→resubmit flood finding #13 warned of and the arbiter dismissed *on
> the grounds that no such loop existed* — true before the fix, false after it.
> `MaxBracketStopAttempts` bounds it. The first bound was itself wrong: it reset the counter on
> `Submit` success, but the failure mode is rejection *after* a successful submit, so the bound was
> unreachable. The test caught it at 21 submissions.

### Two operational facts recorded elsewhere but easy to lose

- **`ShadowSessionsCompleted` was reset** (5 → 0) and has since counted **1** genuine session and
  **held at 1 across a recompile** — `P1-37`'s debounce proven from a clean baseline. The live
  arming gate is trustworthy on this box for the first time. Backup:
  `RiskGuard/state.json.bak_20260807_095249`.
- **`P0-48` is closed and verified**: 67 handlers → 8 after restart, and `TradeCopierEngine` held
  at exactly **1** across a further recompile — the event that used to add an orphan every time.

### Method notes worth repeating

- **"NT8 closed" means "the AddOn is not loaded"**, which is not the same as "the process is gone".
  The reliable check is the bridge not answering on `localhost:7890`.
- **Deploy unverified addon code mid-session, never at startup.** A failed `nt_compile` hot-swap
  leaves the running assembly in place and is recoverable; broken sources in `bin/Custom/AddOns/`
  only bite at the next startup, where they stop **every** AddOn loading, RiskGuard included.
- **The test stub can be more forgiving than NT8, and the suite cannot tell you.** `P1-22`'s
  pending-copy map was keyed on `Order.OrderId` and every test passed; NT8's `OrderId` is neither
  unique nor stable. Check how the existing addon uses an API, and why, before relying on it.

---

## 4k. Session 8 record — 2026-08-07: the P1 band closes

Seven commits. `P0-9` items 3/4 → `P1-12` → `P1-14` → `P1-36` → `P1-13` (half) → `S5`–`S9` →
`P2-38`/`P2-41`. Suite 524 → **616**, all green, NT8 `nt_compile` 0 errors, all 9 files in sync.

| Commit | What |
|---|---|
| `c2f54e9b` | `P0-9` items (3) `StopLimit` and (4) leader-cancels-stop, pinned by test |
| `12e0ca12` | `P1-12` — the disk comes off `_stateLock` |
| `35052e86` | `P1-14` — the pending-stop buffer: one order, forever, unchecked |
| `c6c4e02b` | `P1-36` — coverage is the sum of the stops, not one of them |
| `830cfa55` | `P1-13` fail-open half — the guard stopped guarding when the UI was absent |
| `0e21ad3c` | `S5`, `S6`, `S8`, `S9` — the stress backlog closes |
| `6077de0a` | `P2-41` config merge, `P2-38` sim/live gates |

### The through-line: three defects were found by making something a compile error, or by a test

**1. `P1-36` lived in a second place.** Making `CoveredQuantity`/`RecognizedStopOrder` read-only
turned "find every writer" into a compile error, which surfaced nine sites — and the ninth was
`ExecuteAction` re-sizing the auto-stop from the **whole live position**, ignoring existing cover.
`EvaluateGraceExpiry` had always sized its *action* to the uncovered delta; `ExecuteAction` sized
it straight back up. Closing only the FSM half would have left the 9-lots-behind-6 outcome exactly
as it was. **A fix verified only where the defect was reported is a fix that may not have landed.**

**2. `P1-13`'s machine check found a site I had already missed** on my own pass through the file.

**3. `S6`'s first draft was unfalsifiable and looked fine.** It cancelled each stop before flipping
— tidy, realistic-looking, and completely inert: a terminal order cannot contribute coverage to
anything, so the revert probe found nothing and the test reported safety. It now leaves the
previous leg's stop **working** as the flip lands, which is the real shape. This is the second time
a stress test in this programme has been vacuous on the first attempt (see §8 of the plan). **Every
stress test here must be shown red against the defect it names before it is worth anything.**

### `P2-41` was verified live, by accident, one minute after deploying

`nt_riskguard_config` with no arguments POSTs an **empty body**. Under the old code that single
call — the one you would reach for to *read* the config — would have deserialized `{}` into a
complete `RiskConfig` and written it: `Mode` → shadow, `MinShadowSessions` → 0, `EnableWindowGate`
→ false, all six `WindowsET` gone, all four `FirmProfiles` gone, `StopGuard.OnMissing` → `Flatten`.
It would have replied `"applied"` and echoed the request.

The post-fix call returned `"requested": {}` next to the complete, unchanged live config. **The
tool most likely to be reached for as a read was itself a destructive write, and the workaround
recorded in §0 item 4 — GET, mutate, POST, GET, diff — was the only thing standing between this
box and a wiped risk configuration.**

### Two things deliberately NOT done, with reasons

**`P0-9` item (1): profit targets and OCO.** This is the last piece of `P0-9` and it wants an
operator decision rather than a unilateral one. The case against building it: a mirrored target is
*upside*, not risk — the follower already exits when the leader's target fill is copied, so the gap
is fill quality, not exposure. Building it doubles the copier's order-placement surface on a
component whose **first** half has never been observed on a live fill. The case for: it is option 1
of the plan's own preferred fix, and the latency gap is real in a fast market. If it is built, it
must use a real broker-side OCO id — a mirrored target without OCO leaves the stop working after
the target fills, which flips the follower into a fresh position. **Recommendation: validate the
mirrored stop on a live feed first, then decide.**

**`P1-13`'s threading inversion.** The evidence says it is safe — the copier has been submitting
real follower orders straight off NT8's account-event thread, with no marshalling, in production.
But it converts six handlers the dispatcher was implicitly serialising into genuinely concurrent
ones, and **the S-series does not cover that**: `S4` is lock-scope, `S7` is copier fan-out, and
`S5`/`S6`/`S8`/`S9` are sequential scenario tests. I said mid-session that the stress backlog would
be the prerequisite; having written it, it is not. A genuine concurrent-guard-event stress test is.
Doing the risky half before its coverage exists is how `P1-40` shipped.

### Method notes

- **`McpBridgeAddOn.cs` is excluded from the test build**, so the `P2-38`/`P2-41` changes were
  unverifiable until `nt_compile`. That is the `P1-47` shape and it is structural, not incidental.
  The mitigation used here: put the *logic* somewhere compiled (`RiskConfigMerge` lives in
  `RiskGuardAddOn.cs`) and check the bridge's own wiring against **source text**. A source
  assertion proves less than an execution; it proves the exact thing that regressed.
- **A machine check on source text needs its comments stripped**, or it forbids documenting the bug
  it prevents — and then the comment gets deleted instead of the check getting fixed.
- **The TTL in `P1-14` is two grace periods, not one.** One grace period is the longest a
  legitimate stop can lag its position event and still be the thing protecting it. The test asserts
  both edges, because an over-eager TTL breaks the race the buffer exists for.

---

## 4l. Session 8, second half — the live ATM trade that found two P0s

The operator placed an ATM order on `Sim101` with `Sim-ORB` following, and reported that the
follower "did not follow". It had followed — the entry copy was correct. What had not happened
was the protective stop, and chasing that produced **`P0-49` and `P0-50`**, both P0, neither
reachable by any test in the suite.

| | |
|---|---|
| 15:43:21.232 | `COPIER_FOLLOW` Buy 1 MNQ SEP26 filled 29789.25 on Sim-ORB — **the copy worked** |
| 15:43:21.237 | `Created FSM Sim-ORB\|MNQ SEP26 -> Unprotected` |
| 15:43:24.241 | `[SHADOW] Would execute FlattenPosition triggered by MISSING_STOP_FLATTEN` |
| 15:45:22.572 | `COPIER_STOP` submitted — **~2 minutes late, as the position was closing** |
| 15:45:30, :31 | two more `COPIER_STOP` orders, against a **flat** account |

**The follower was naked for the entire trade**, then collected three orphan stops.

### The NT8 fact underneath it

**`ExecutionUpdate` is raised BEFORE `PositionUpdate`.** The bracket anchored itself by re-reading
`followerAcc.Positions` from the execution handler, so on every entry fill it read a position that
did not exist yet, released the bracket, and returned. Nothing rebuilt it, because an ATM stop
sits at `Accepted` and raises no further `OrderUpdate` — so the leader path never fired again
either. One event-ordering assumption, and the whole of `P0-9` silently did nothing.

This is the same class as the `P1-22` lesson in §4j: **the test stub is more forgiving than NT8,
and the suite cannot tell you.** The stub raises whatever the test raises, in whatever order the
test chooses, and every bracket test drove position-then-execution because that is the order a
person writes it in.

### The second trade — validated, 15:55:56

`P0-49`/`P0-50` were deployed and a second ATM trade run immediately:

| | |
|---|---|
| 15:55:56.9857 | Sim-ORB `COPIER_FOLLOW` **Filled** |
| 15:55:56.9988 | Sim-ORB execution, price **29822.25** |
| 15:55:56.9998 | Sim-ORB `COPIER_STOP` **@ 29807.25 — one millisecond later** |
| 15:55:57.0058 | `Created FSM Sim-ORB\|MNQ SEP26 -> ProtectedPending` |

Leader entry 29821.75, leader `Stop1` 29806.75, offset **-15.00**; follower 29822.25 - 15 =
**29807.25**. Exact. And the follower's FSM is created **`ProtectedPending`** rather than
`Unprotected`, so no `MISSING_STOP_FLATTEN` fires at all — compare the first trade, where the FSM
was born naked and the guard would have flattened it three seconds later.

**`P0-9`'s mirrored stop is now validated end to end on real fills: arithmetic, timing, and
resulting FSM state.** That was the longest-standing open item in this document, carried since
session 7.

Worth noting for the next reader: the stop went out at `.9998`, *before* the follower's
`PositionUpdate` event at `1.0058`. NT8's `Account.Positions` collection had already been updated
even though the event had not yet been raised, so the execution path found the anchor and placed
the stop. The `PositionUpdate` subscription added by `P0-49` is the **safety net** for the case
where the collection is not yet updated — which is exactly what happened on the first trade. Both
paths are needed; neither alone is sufficient.

### What is still NOT validated live

- **Profit targets are not mirrored** — the operator noticed within one trade. Sim101 carried
  `Target1` (Limit Sell 29851.5); Sim-ORB got only `COPIER_STOP`. Deliberate, and the last open
  item of `P0-9`. See §4a.
- **`T5`'s fail-closed gate** still needs an acting mode; `IsGuardProtecting` requires
  `mode == "live"`.
- **Firm-mirror rules** are loaded but unmapped, so none of them fire.

### A note on what "it didn't follow" meant

The reported symptom pointed at the wrong relationship. The `SUB_MINIMUM_SKIPPED` line in the
output was **SimCopy2**, not Sim-ORB, and it was **correct behaviour**: SimCopy2 has
`AutoSymbolConversion` on, so MNQ→NQ is micro→mini, 1 MNQ scales to 0.1 NQ, and the copier refuses
rather than rounding up to a 10× notional. That is `P0-6` working as designed. Reading the whole
log rather than the one alarming line is what separated the two.

---

## 4m. Session 9 — 2026-08-09: the guard flattened three accounts while claiming to be in shadow

Another live operator ATM trade, another two defects, and this time one of them undermines the
premise the whole deployment rests on. **No code was changed this session** — the incident was
diagnosed from the live event stream and the source; `P0-51` and `P1-52` are open.

### The four seconds

| Time (ET) | What |
|---|---|
| `21:15:21.9` | Operator enters 2 MNQ SEP26 on `Sim101` with an ATM bracket. Replikanto mirrors the full bracket to `SimCopyTest1` and `SimCopy2`; our copier mirrors entry + `COPIER_STOP` to `Sim-ORB` |
| `21:15:22.0` | `ORDER FLOOD DETECTED: 6 distinct orders in 1s (limit 5)` on **all three** bracket-carrying accounts |
| `21:15:25.0` | `LOCKOUT_PHASE PendingFlatten` + `[SHADOW] Would execute action FlattenPosition triggered by LOCKOUT_FLATTEN` on each |
| `21:15:25.15` | Market `Sell` 2 named **`"Close"`** on each of `Sim101` (`34256`), `SimCopyTest1` (`34257`), `SimCopy2` (`34258`) — all fill at 29848.75 |
| `21:15:25.4` | All three flat, `LOCKOUT_CONFIRMED`. **`Sim-ORB` still long 2** |

### `P0-51` — how the shadow gate was bypassed

Two paths leave a lockout and only one is gated:

- `EvaluateLockoutPhase` (`:2718`) → `GuardAction` → `ProcessAction`'s mode check (`:3277-3285`)
  → `SHADOW (SKIPPED)`. **Correct.**
- The lockout watchdog sweep (`:1848-1889`) builds `cancelBatches` / `flattenBatches` with no
  `_mode` check, then executes them at `:1899-1940` — `Cancel` at `:1901`, `Flatten` at `:1913`.
  **Ungated.**

`Account.Flatten()` cancels the instrument's working orders and submits a market close named
`"Close"`, which is exactly what appeared. The `[SHADOW]` line and the real flatten are the same
lockout, taking two different routes.

> **Attribution was checked, not assumed.** A manual "flatten everything" would also have closed
> `Sim-ORB`, which was long 2 on the same instrument at the same instant. `Sim-ORB` was the only
> account that had not tripped the lockout and the only one left untouched — the flatten tracked
> lockout state, not the operator.

**This is the third instance of §0 lesson 2.** The suite tests `ProcessAction`'s gate, and that
gate is correct. Nothing asserts the negative — *no broker call is issued by any path while in
shadow*. `S4`'s `BrokerCallObserver` already exists to assert exactly that and was never pointed
at this question.

### ⚠️ FOUR tests asserted shadow-mode broker actions. Expect more

`_mode` defaults to `"shadow"` (`RiskGuardAddOn.cs:212`, deliberately, as the fail-safe). A test
that never calls `SetModeForTest` therefore runs in shadow — and four of them asserted that the
guard **cancels or flattens** in that state:

| Test | Asserted |
|---|---|
| `TestP1_10_SweepMakesNoBrokerCallsUnderTheStateLock` | the sweep flattens |
| `TestP1_11_LockoutSweepDoesNotCancelTheProtectiveStopBeforeFlattening` | the sweep flattens and cancels |
| `TestOrderCancelledWhenLockedOnOrderUpdate` | a working order is cancelled |
| `TestOrderCancelledWhenConsecLossesAtMaxNotLocked` | a submitted order is cancelled |

All four were green, and all four were green **because of the defect**. Each has been given an
explicit `SetModeForTest("live")`, which is what they always meant — every one of them is about
*acting* behaviour. Baseline is unchanged by the correction (622/8), because the code acts in
every mode today.

**Two consequences worth carrying forward.** First, this is why `P0-51` survived: the suite did
not merely fail to catch it, it *asserted* it, so any fix looked like a regression — the loop
burned two full runs on exactly that (§4m's loop notes). Second, **`P0-53` was found only because
one of these tests was made honest.** If you touch a test that drives the sweep or an intervention
path, check whether it states a mode before you trust what it proves.

### `P1-52` — why the lockout fired at all

A 2-contract ATM entry is 6 orders (2 entries, 2 stops, 2 targets) against `MaxOrdersPerSecond = 5`.
**Every 2-lot bracketed trade trips it**, and third-party copier fan-out means it trips on every
mirrored account in the same second. Third defect on this governor after `P1-44`, `P1-45`, `P2-46`.

### The leftover, and the one thing still unexplained

`Sim-ORB` was left long 2 @ 29849.75 with `COPIER_STOP` working at 29835 — **protected, but
diverged from a leader that had been flat for hours**. It was flattened by the operator's
instruction at 2026-08-09 ~21:2x ET via `nt_close_position`; that call cancels orders itself, so
**it did not independently exercise `P0-50`'s orphan-stop release** and must not be recorded as a
re-validation of it.

**Open question — do not assume the answer.** Why the copier never mirrored `Sim101`'s exit to
`Sim-ORB` is *not established*. The exit path (`TradeCopierEngine.cs:1621-1748`) looks like it
should have fired: quarantine permits exits, `Sim-ORB` is a Sim follower so `COPY_BLOCKED_NO_GUARD`
does not apply, and `currentFollowerPos` was 2. It could not be settled from the logs because
**the copier's `[CopierEngine]` lines go to the NT8 Output tab and land in no readable sink** —
they are absent from the bridge's event stream, from `log/`, and from `trace/`. Giving those
lines a file sink is a prerequisite for diagnosing anything in the copier and should come before
the next copier change.

---

## 4n. 2026-08-10 — the incident replayed live, with instrumentation

Ran the 2026-08-09 incident again on purpose: same 2-lot MNQ ATM entry on `Sim101`, same Replikanto
fan-out, same `shadow` mode. **`P0-51` and `P1-52` are now validated on a live feed.**

### What the replay proved

| Fix | Evidence |
|---|---|
| **`P1-52`** | **No `ORDER_FLOOD_LOCKOUT` on any account.** The identical bracket that locked out three accounts on 2026-08-09 produced none |
| **`P0-51`** (sweep) | `LOCKOUT_SWEEP_SHADOW`: *"[SHADOW] Would execute lockout sweep for account SimCopyTest1: flatten [MNQ SEP26], cancel 2 order(s)."* — **and nothing was flattened.** `SimCopyTest1`/`SimCopy2` were still locked out from the incident and kept both position and orders |
| **`P0-51`** (queue) | `SHADOW_PENDING_CANCEL`: *"[SHADOW] Withheld 1 intervention cancel(s) in shadow mode."* The `ENTRY_CANCEL` lines still say "Cancelled order X because account is locked out" — **but the orders stayed `Working`.** That log line describes the decision, not the outcome; the outcome is the withheld line |
| **Exit mirroring** | Works. `COPIER_COPY_BEGIN: 2 active relationship(s), isExit=True: Sim-ORB, SimCopy2` → `COPIER_FOLLOW Sell 2` on `Sim-ORB`, filled |

**The 2026-08-09 exit-mirror failure is still unexplained**, but it is no longer *unexplainable*:
the normal exit path demonstrably works, and every abandon point now names itself. If it recurs the
log will say which one it was.

### The instrumentation

`RiskGuardAddOn.LogFromComponent` lets a sibling component write into the guard's structured log, so
copier lines now reach `interventions.jsonl` and the bridge event stream instead of dying in the NT8
Output tab. `TradeCopierEngine.CopierLog` is the dual sink. **Every early return in `OnExecution`
was silent** — seven of them — and each now emits a reason: `COPIER_EXEC_SEEN`, `EXEC_IGNORED`,
`EXEC_IS_FOLLOWER`, `EXEC_SELF_ORIGINATED`, `EXEC_DUPLICATE`, `NO_ACTIVE_RELATIONSHIPS`,
`COPY_BEGIN`.

**The bracket path is no longer dark.** `BRACKET_NO_LEADER_POSITION` and `BRACKET_REANCHOR` were
added while closing `P0-55`, and they are what turned "the follower is naked and nobody knows why"
into a two-line trace. `SyncFollowerStop`'s own internals remain uninstrumented — worth doing before
the next copier change.

### Two defects the replay opened

- **`P0-55`** ✅ **CLOSED same day.** `Sim-ORB` got no `COPIER_STOP` at all and ran the whole trade
  `Unprotected`. The cause was **not** the FSM rejection it appeared to be: the leader's stop
  reached `Accepted` at `.4203` and the leader's position only existed at `.4683`, so
  `OnLeaderOrderUpdate` had nothing to anchor to — and an accepted ATM stop is event-silent
  afterwards, while the leader's own `PositionUpdate` was discarded because the account is not a
  follower. **The leader-side twin of `P0-49`**, whose docstring describes the identical race on the
  follower's anchor. Fixed by re-driving the mirror from the leader's `PositionUpdate`.
- **`P1-54`** ✅ **CLOSED same day.** `Sim101`, `SimCopy2` and `SimCopyTest1` were *still locked out
  ~3 hours later* and blocked the replay. `IsLockedOut` was sticky, `LockoutUntil` was not
  persisted, and the test is an OR, so `LockoutMinutes` never ended a lockout. Fixed by lapsing on a
  passed deadline and persisting it — with `MinValue` still meaning "no deadline", since
  `LockAccount(name, -1)` uses it for an EOD hold.

### Two operational gotchas worth keeping

- **`nt_place_atm_order` caches by `idempotencyKey`.** Reusing a key replays the previous response —
  including a stale error. A blocked order that "stays blocked" after you fix the cause may just be
  the cache. Use a fresh key.
- **`UnlockAccount` also resets that account's metrics** (peak equity, trades today, consecutive
  losses, PnL basis). Fine on a Sim rig, not something to do casually on a funded account.

---

## 4o. 2026-08-10 — OCO research, and the trail fix it licensed

The operator rejected "we cannot propagate the OCO" as an answer. They were right to: **the
earlier claim in this document was wrong.** What follows is the corrected picture, the working
implementation, and the two things blocking it.

### The API facts, established by reflection and two live runs

Reflected on NT8's `NinjaTrader.Core.dll` (in the NinjaTrader 8 `bin` folder):

| Fact | Consequence |
|---|---|
| `Order.Oco` has a **public setter** | The old "create-time only, cannot be joined" claim is false |
| There is **no `OcoChanged`** field (only `LimitPriceChanged`, `StopPriceChanged`, `QuantityChanged`) | `Account.Change()` moves price/qty but **cannot** move a working order between groups |
| ~~**An OCO id cannot be REUSED** — NT8 rejects a new order carrying a used id~~ **CORRECTED 2026-08-10, see §4p** | The rule is about the GROUP'S LIFE, not the id's history: an id can be **joined** while its group still has a live member, and is only rejected once every leg has gone terminal. Re-creating one leg beside a live sibling may keep the same id |
| `Account.CancelOrdersByOcoID(orders, ocoId)` exists | A real group-cancel primitive; the copier currently hand-rolls this |
| `Connection.Features` returns `Feature[]` at runtime | Capability is answerable, not guessable |

**The id-reuse rule was found by the operator hitting the error, not by us.** It is the single
fact that most shapes the design, and nothing in the suite would have surfaced it. **It was also
stated too strongly, and §4p corrects it with a controlled test.**

### What this connection actually supports

Added a read-only probe, `GET /api/connections` (`McpBridgeAddOn.GetConnectionFeatures`). On this
box **one connection, `TPT`, serves both Sim101 and the funded TakeProfit accounts**, and it
advertises:

```
Bars1Minute, BarsDaily, BarsTick, BarsTickIntraday, Hotlists, MarketData, MarketDepth,
NativeGtdOrders, News, Order, OrderChange, ProvidesMarketDataSnapshot,
Quotes1Minute, QuotesDaily, QuotesTick
```

`NativeGtdOrders` is present, **`NativeOcoOrders` is not** — and since the `Native*Orders` family
is demonstrably in use, that absence is meaningful. **OCO here is NT8-simulated, not
broker-native.** It works (every ATM bracket on this box relies on it), but if NT8 dies between
one leg filling and the sibling being pulled, the survivor is live at the broker. That is the
exposure the operator's own manual brackets already carry — not a new one.

`OrderChange` being present is what licensed the trail fix below.

### Shipped: the trail no longer opens a naked window

`SyncFollowerStop` now **modifies** the working stop via `Account.Change()` instead of
cancel-then-create. Cancel-then-create left the follower unprotected on *every* trail step.

> This **revises a settled `P0-9` note** ("cancel-then-replace, not modify"). The note existed to
> stop a stale stop working beside a new one; `Change()` cannot produce that state because there
> is only ever one order. Verified, not assumed — `OrderChange` is advertised — and any failure
> falls through to the old path, logged `BRACKET_MODIFY_FAILED`.

Also: the test double's `Change()` was not calling `ObserveBrokerCall`, so it was **exempt from
the `P1-10` lock-scope check** — the same blind spot that hid `P1-43`'s four cancels. Now observed.

### ~~Parked: the mirrored target~~ — SHIPPED 2026-08-10, see §4r

> **Superseded.** The mirrored target was rebased off `wip/p09-oco-target` and shipped as
> `86c6376f`. **That branch is superseded and should be DELETED, not rebased** — it lacked five
> fixes, four of them live-risk (§4r). The live observations below still stand.

What the parked branch demonstrated live on `Sim101 -> Sim-ORB`:

- the leader's **limit** leg is recognised and mirrored, anchored to the **follower's own fill**;
- both legs carry one shared OCO id;
- both legs **modify in place** (`BRACKET_MODIFIED` / `BRACKET_TARGET_MODIFIED`);
- the `P0-55` re-anchor covers **both** legs (`re-evaluating 2 working protective leg(s)`).

Both of the things that stopped it shipping are resolved:

1. ~~**`P1-56`**~~ — closed 2026-08-10 (§4q).
2. ~~**The OCO-id-reuse rule.**~~ Corrected by controlled live test (§4p): an id can be joined while
   its group still has a live member, so the per-generation redesign shrank to one conditional on
   the cancel-then-create path. Shipped that way in §4r.

> **A mistake worth not repeating**: the first cut of the `P0-55` re-anchor filtered on
> `IsStopType`, so it silently left the *target* unanchored. The live trace said
> *"re-evaluating 1 working protective stop(s)"* on a two-legged bracket. A stop-shaped test
> cannot see an off-by-one-leg; the instrumentation caught it in one line.

### Replikanto is NOT being blocked by us

Asked and answered with evidence: during the clean run there were **zero events of any kind** on
`SimCopyTest1`/`SimCopy2`, and neither is locked out. If we had killed its orders you would see
`ORDER_UPDATE` -> `Cancelled`; no order ever existed. Since `P0-51`, RiskGuard in `shadow`
**withholds** interventions rather than executing them, so it cancels nothing.

Separately and correctly: **our own copier does skip `SimCopy2`** — it has `AutoSymbolConversion`
on, so 1 MNQ scales to 0.1 NQ and `P0-6` refuses rather than rounding to a 10x notional. Expected,
and unrelated.

### Operational gotchas found the hard way

- **`nt_place_atm_order` caches by `idempotencyKey`.** Reusing a key replays the previous
  response, *including a stale error*. An order that "stays blocked" after you fix the cause may
  just be the cache. Use a fresh key.
- **`UnlockAccount` also resets that account's metrics** — peak equity, trades today, consecutive
  losses, PnL basis. Fine on a Sim rig; think twice on a funded account.
- **`nt_close_position` cancels the orders itself**, so using it to clean up does **not**
  independently exercise the copier's orphan-stop release. Do not record it as validating `P0-50`.
- **Two overlapping leader brackets look exactly like a copier bug.** A manual bracket placed
  during a test produced multiple mirrored legs and a qty-4 order. The tell *was* the leader's order
  *names* (`Stop1`/`Target1` vs `Stop_<bracketId>`) — ⚠️ **but that diagnostic is BROKEN**: a
  third-party copier on this box copies leader names verbatim, so its mirrors are indistinguishable
  by name from a native bracket (§4p). Check order *count against position size* and the `oco`
  field instead.

---

## 4p. 2026-08-10 — the OCO id rule, pinned by a controlled live test

§4o's headline OCO fact was **too strong**, and it was the fact "that most shapes the design". It
is now pinned properly, by changing exactly one variable.

### The experiment

A 2-lot bracketed entry on `Sim_All_Day_ORB` (MNQ SEP26, 01:44 ET) via `/api/order/atm`: entry
filled 2 @ 29906.75, and `Stop_5c903ad3` (StopMarket 2 @ 29897.5) plus `Target_5c903ad3`
(Limit 2 @ 29921.75) went working, **both carrying one shared id `4980107b-…`**. Then the same
order — same id, account, side, quantity and price (Sell Limit 1 @ 30200, far from market so it
could not fill) — was submitted twice:

| # | State of the group `4980107b-…` | Result |
|---|---|---|
| 1 | stop + target still **working** | **`Working`** — accepted, it JOINED the group |
| 2 | group retired by `nt_close_position` (3 orders cancelled) | **`Rejected`** |

Nothing else differed between the two submissions. So:

> **An OCO id can be JOINED while its group still has a live member. It cannot be RESURRECTED once
> every leg has gone terminal.**

### Why this mattered, and what was built on it

The parked implementation was believed dead because it "mints one id per bracket and reuses it,
which NT8 rejects on any re-create". That is only true when the re-create happens after the whole
group has died. **Re-creating ONE leg while its sibling is still working may keep the same id**, so
per-generation ids are needed only for the fully-terminal case — and the `Order.Oco` public setter
agrees: group membership is assignable at create time, for a group that still exists.

**This is the fact the shipped implementation rests on** (§4r): a leg created beside a live sibling
*joins* its group, and only the cancel-then-create path — where our own cancel may have retired the
group — mints a fresh id.

### Two other things this trade exposed

- ⚠️ **`EDGE_WINDOW_BREACH` fires on an ordinary overnight entry.** The moment the position opened,
  the guard logged `[SHADOW] Would execute action FlattenPosition triggered by EDGE_WINDOW_BREACH`.
  Shadow only logged it (`P0-51` working), but **armed live this trade would have been flattened
  within a second of filling.** Any live validation booked outside the permitted edge window will be
  destroyed by the guard rather than by the defect under test. Schedule live work accordingly.
- **An ATM leg's price cannot be trailed from outside.** `nt_change_order` on `Stop_5c903ad3`
  returned `"modified"` and the order's timestamp moved, but the stop price did **not** change
  (29897.5 held) — our `DynamicAtmManager` owns that leg and re-asserted it. The copier's own
  `COPIER_STOP` is not ATM-managed, so `P0-9`'s `Change()` trail is unaffected; but do not use an
  ATM-managed order to test it.

### Suspected — one of the two is now addressed

The two `Rejected` `COPIER_TARGET` leftovers from the 01:01/01:03 parked-target run carried
**distinct** ids, so id reuse cannot be why they were rejected. Their tells point elsewhere: one is
qty **4** against a 2-lot position, and the other sits at **29905.625**, which is not a multiple of
MNQ's 0.25 tick.

> ✅ **The off-tick one is now moot** (§4r): both mirrored legs are snapped to the instrument's tick
> before submission. The cause is that the anchor is the follower's *average* fill price, and an
> average across partial fills lands between ticks. It was never *proven* to be the rejection
> reason — the ATM path's own off-tick prices (29897.419…, 29921.633…) were silently **rounded by
> NT8 at `Submitted`**, so off-tick is not always fatal — but there is now no path that sends one.
>
> ⚠️ **The qty-4-against-a-2-lot-position one is still unexplained**, and it is the more worrying
> of the two.

### Replikanto did nothing — until it was fixed, and then it told us a lot

The first attempt produced **no order, no position and no event** on either follower while
`Sim_All_Day_ORB` traded, with our copier correctly standing aside
(`COPIER_NO_ACTIVE_RELATIONSHIPS`). The operator then fixed its configuration; its real leader is
**`Sim-ORB`**, not `Sim_All_Day_ORB`. A 1-lot native ATM bracket on `Sim-ORB` at 01:56:56 then fanned
out cleanly:

| Account | Legs | OCO id |
|---|---|---|
| `Sim-ORB` (leader) | `Stop1` 1 @ 29913.75, `Target1` 1 @ 29958.75 | `75a1929ea45146109fd279b9185ddd4a` |
| `SimCopyTest1` | identical | `cb776ec9359a403cba1bc78238c0de8b` |
| `SimCopy2` | identical | `b32917cd0e9b48828e5626aee06181fc` |

Fan-out latency was ~12 ms and ~29 ms after the leader's legs.

**What this settles for `P0-9`'s mirrored target:**

1. **A mature copier mints a FRESH OCO id per follower account** — it does not propagate the
   leader's id. Three accounts, three unrelated ids. This corroborates the shape the parked
   `wip/p09-oco-target` branch already has (both follower legs sharing one locally-generated id) and
   rules out any design that tries to carry the leader's id across accounts.
2. **It mirrors the FULL bracket, stop and target.** That is precisely the capability we deliberately
   do not have yet, so "a follower with only a stop" is us being behind the field, not being careful.
3. Replikanto's ids are undashed 32-hex (`75a1929e…`); ours are dashed GUIDs. NT8 accepts either, so
   the id is an opaque string.

**⚠️ Two hazards this exposed in OUR code and docs:**

- **§4o's diagnostic rule is broken.** It says the tell for a manual bracket is the leader's order
  *names* (`Stop1`/`Target1` vs `Stop_<bracketId>`). Replikanto copies the leader's names
  **verbatim**, so its mirrors on a follower are indistinguishable by name from a native bracket.
- **We would mirror a mirror.** `OnLeaderOrderUpdate` only refuses orders whose `Name` contains
  `COPIER`. Replikanto's mirrored legs are named `Stop1`/`Target1`, so if an account were ever both a
  Replikanto follower and one of our leaders, we would treat its mirrored stop as a genuine leader
  stop and mirror it onward. **This is live today in one direction:** `Sim-ORB` is our follower
  (`Sim101 -> Sim-ORB`) *and* Replikanto's leader, giving
  `Sim101 -> Sim-ORB -> {SimCopyTest1, SimCopy2}`. A `Sim101` test trade now fans out to three
  follower accounts, which any P1-56 live validation must account for.

**Deliberately NOT concluded: whether Replikanto mirrors stop PRICE or DISTANCE.** All three accounts
filled at exactly 29928.75 in Sim, so both hypotheses predict identical legs and the run cannot
separate them. Ours mirrors distance from the follower's own fill because real fills differ.

### ANSWERED: Replikanto modifies the follower's leg IN PLACE, keeping the OCO group

The operator dragged the leader's `Stop1` in the NT8 UI, 29913.75 -> 29902. All three stops moved,
and everything that would betray a re-create stayed identical:

| Account | `orderId` | `oco` |
|---|---|---|
| `Sim-ORB` (leader) | `655154f7…` unchanged | `75a1929e…` unchanged |
| `SimCopyTest1` | `5491d1b8…` unchanged | `cb776ec9…` unchanged |
| `SimCopy2` | `e877f5f5…` unchanged | `b32917cd…` unchanged |

`Target1` was untouched on all three, and every stop carries the same modification timestamp
(`02:00:11.5915186`), so propagation was effectively instantaneous.

**Three conclusions, and they largely dissolve the blocker §4o put on the mirrored target:**

1. **Modify-in-place is what a mature copier does on a trail.** That retroactively vindicates the
   `Change()` trail fix in `995f6402` over the original `P0-9` "cancel-then-replace, not modify"
   note — and it is the ordinary case, not an edge case.
2. **A price modification PRESERVES OCO group membership, confirmed live.** Previously this was only
   inferred from reflection (`LimitPriceChanged`/`StopPriceChanged`/`QuantityChanged` exist,
   `OcoChanged` does not). Now observed.
3. **The trail path never re-creates a leg, so it never needs a fresh id.** Combined with the
   join-while-live result above, the ONLY case that needs a new id is one where the whole group has
   already gone terminal. `P1-56`'s remaining OCO work is therefore a narrow conditional, not the
   per-generation redesign §4o called for: keep the id when a sibling is still live, mint a fresh one
   only when the group is dead. The parked branch's "one id per bracket" is much closer to correct
   than it was credited for; its real gap is only the dead-group path (which is what its
   `BRACKET_MODIFY_FAILED` cancel-then-create fallback can hit).

### `nt_change_order` cannot trail an ATM-managed leg — confirmed twice

Attempted on our `DynamicAtmManager` bracket (`Stop_5c903ad3`, 29897.5 -> 29900) and on a native NT8
ATM bracket (`Stop1` on `Sim-ORB`, 29913.75 -> 29918.75). **Both returned `"modified"` and moved the
order's timestamp, and in both cases the stop price did not change** — the ATM owns the leg and
re-asserts it. The `"modified"` status is therefore not evidence of anything. The copier's own
`COPIER_STOP` is not ATM-managed, so `P0-9`'s `Change()` trail is unaffected; but never use an
ATM-managed order to test it.

---

## 4q. Session 10 record — 2026-08-10: `P1-56` closed, and the loop tried twice to ship a defect

**Closed**: `P1-56`. **Opened**: `P1-57`, `P2-58`. **Corrected**: the OCO id-reuse rule (§4p).
Suite 637/0 → **653/0**. Deployed build `995f6402` → **`c9459121`**, hot-swapped 06:19, 0 errors.
Seven commits on `harden/riskguard-p0-51`; nothing merged, nothing pushed.

### `P1-56` — what shipped

Body extracted to `SyncFollowerStopOnce`; `SyncFollowerStop` keeps its signature and becomes the
reservation **holder**: publish `StopInFlight` under `_lock` before any broker call, run a bounded
re-drive loop (`MaxBracketResyncPasses = 2`), release exactly once in a `finally` that runs **after**
the loop. A sync arriving mid-flight sets `StopResyncOwed`, returns without touching the broker or
`StopAttempts`, and the holder re-drives so the newer size/price is applied. Both
`bracket.WorkingStop = null` clears removed.

**The order of the two halves is the whole design.** The reservation stops a second sync creating a
duplicate; the *honest* `WorkingStop` is what makes that second sync **modify** the existing order
via the `Change()` trail path instead. Neither half works alone, and the reviewers who argued about
the reservation window never engaged with the second half — which is why they over-stated their
finding in one direction and under-stated it in the other.

### The loop produced three candidates. Two would have shipped live defects. All three passed every gate.

This is the session's most transferable finding, and it is about the **process**, not this defect.

1. **Round 1** put the reservation in place correctly but cleared it in the `finally` *before* the
   recursive re-drive re-took it. Both reviewers spotted the window; the arbiter upheld it. Then all
   three endorsed the same fix: *"do not clear `StopInFlight` when a re-sync is owed; let the
   re-drive's own `finally` clear it."* **That fix leaks the reservation forever** — the re-drive's
   first act is to test `StopInFlight` and back off, so it returns without ever reaching a `finally`,
   and that follower can never be given another protective stop. Redirected with an
   `--orchestrator-note` to hold one reservation across a bounded **loop** instead, which closes the
   window with no leak and no recursion.
2. **The apply run silently produced and applied a third, unreviewed candidate.** `--resume-raw`
   reseeds round 1 *and re-reviews it*; a `REVISE` there triggers a fresh round 2, and `--apply`
   ships **that**. It set `countAttempt = (pass == 0)`, so re-drive passes reached the broker
   **without counting an attempt** — turning `MaxBracketStopAttempts = 3` into effectively **9
   submissions**, the order-flood mode `P1-40`/`P2-46`/the flood cluster already cost us — and it
   restored `WorkingStop = null` on the `catch` and abort paths, losing track of a possibly-live stop
   and **reintroducing the very defect being fixed**. Caught by §9 step 3 (*confirm the candidate is
   the one that was reviewed*), reverted with `git checkout --`, and the reviewed candidate spliced in
   via the loop's own `regions.apply`, then verified **byte-identical** to the gated `final.patch`.

> ⚠️ **`--resume-raw … --apply` is not a promote-what-I-read command.** It is a fresh run seeded with
> that raw. If the panel says `REVISE`, you get a new implementation and *that* is what lands. To
> promote an exact candidate, splice it yourself with `regions.apply` and diff the result against the
> `final.patch` you reviewed. Mirrored into [AGENT_PATCH_LOOP.md](AGENT_PATCH_LOOP.md) §9.

**The arbiter rubber-stamped the winning round**: 22 findings, 0 upheld. A 0-upheld ruling is not
reassurance — on the round before it, the same arbiter upheld a finding and recommended a fix that
would have been a live defect. Read the patch.

### Test-first, and one test written specifically to distrust the arbiter

Three concurrent tests, all hand-written before the fix, because `*Tests.cs` is a protected path the
implementer cannot reach:

- `TestBracket_P1_56_InterleavedSyncsLeaveExactlyOneProtectiveStop` — **red at baseline**, reproducing
  the live shape exactly (two live stops, qty 2+1 behind 2 lots).
- `TestBracket_P1_56_AThirdSyncStillLeavesExactlyOneProtectiveStop` — written because the arbiter
  recorded *"there is no gap between passes"* as a **settled fact on argument alone**, and a settled
  fact nothing tests is how `P1-40` shipped.
- `TestBracket_P1_56_AFailedSubmitDoesNotWedgeLaterSyncs` — **passes at baseline**, and exists to fail
  if the reservation is ever leaked on a throwing path. A reservation leaked on failure is permanent
  and strictly worse than the duplicate-leg defect.

**The deterministic-interleaving technique is reusable and `P1-13` needs it.** `Account.BrokerCallObserver`
fires *inside* `CreateOrder` — the exact window — so the first sync can be parked there while another
thread drives the second. No sleeps, no racing, no flakiness. Every wait is bounded so that a fix
which makes one sync *block* on another reports a failure instead of hanging the suite. This is the
first genuinely concurrent test in the suite; the `S`-series is still sequential.

### Also this session

- **`P1-56` is NOT validated live** — unit + compile only, like `P0-53`/`P1-54`/`P0-55`.
- Two read-only `oco` fields added (`/api/orders`, `ORDER_UPDATE`) — they are what made §4p possible.
- The stale *"NT8's Change path is not available through this seam"* comment corrected; it had sat 60
  lines above the `Change()` call that contradicted it since `995f6402`.
- `MaxBracketResyncPasses` replaced the literals `3` and `2`, which encoded one bound twice and were
  one edit from disagreeing. The arbiter dismissed this as *"hypothetical future maintainers"*.

---

## 4r. Session 11 record — 2026-08-10: the mirrored target ships, and what the parked branch was missing

**Closed**: `P0-9` item (1). Suite 653/0 → **686/0**. Deployed build `c9459121` → **`86c6376f`**,
hot-swapped 13:12, `nt_compile` 0 errors under net48. One commit on `harden/riskguard-p0-51`;
nothing merged, nothing pushed. **`wip/p09-oco-target` is superseded — delete it.**

### The asymmetry between the legs is the design

The stop is **risk**; the target is **upside**. Every place they differ, they differ for that
reason, and tidying them into symmetry would break something:

- The stop's re-create path may **re-mint the OCO id and cancel the target** to rebuild the pair.
  The target's re-create path **joins** whatever live group the stop is in and never touches it.
  Cancelling a working protective stop to tidy up a group is not a trade worth making.
- Each leg has **its own** in-flight reservation, owed-flag and attempt budget. Sharing the stop's
  would let an in-flight *target* sync make the risk leg wait its turn, and would let target churn
  spend the budget that keeps the follower protected.
- The target's flat/side-abort path deliberately does **not** clear `FollowerQuantity`/
  `FollowerSide` as the stop's does — that would let a target sync switch the stop sync off.
- `SyncFollowerBracket` drives **stop first, always**, and every call site goes through it. A site
  that syncs one leg leaves the pair half-rebuilt, and that is a mistake that reads as correct.

### What the parked branch did not have — four of the five are live-risk

`wip/p09-oco-target` "worked" live and was credited as nearly done. Rebasing it onto the holder
split was the small part. These were the rest:

1. **The dead-group id conditional.** It minted one id per bracket and re-used it forever. On the
   cancel-then-create path the broker rejects a re-used id whose group has gone terminal — and that
   path belongs to the **stop**. The feature would have produced a naked follower on the leg it is
   not even about. *(Whether cancelling one leg retires the group is still unverified; the fix is
   written to be correct either way, which is why it does not need the answer.)*
2. **No reservation on the target sync.** It predated `P1-56` and carried that defect verbatim.
3. **No attempt bound on the target.** A rejecting broker would have been answered forever — the
   flood mode the `P1-43`…`P2-46` cluster already cost us.
4. **No OCO-retirement guard.** *This one is created by the pairing itself.* When the target fills,
   NT8 cancels the stop; `OnFollowerOrderUpdate` read that as a **lost** stop and re-submitted it —
   and because NT8 raises ExecutionUpdate before PositionUpdate (`P0-49`'s ordering) the follower
   still read as open, so `P0-50`'s live re-read let it through. An orphan stop on an account that
   has just closed. **A leg whose sibling FILLED was retired, not lost.**
5. **No tick rounding.** Both legs are computed from the follower's *average* fill price, and an
   average across partials lands between ticks. §4p listed the `COPIER_TARGET` Rejected at
   **29905.625** on a 0.25-tick instrument as "suspected, not concluded" — this is almost certainly
   it, and it is now moot on both legs.

### A multi-target leader is refused, not guessed at

A scale-out bracket has several targets; the follower has one mirrored leg. Last-seen makes the
follower's exit an artefact of NT8's event ordering; nearest exits the follower's **whole** position
at the leader's **first** partial. So it withdraws the target, logs `BRACKET_TARGET_AMBIGUOUS`, and
keeps the stop — falling back to the known-good pre-target behaviour. `Target1`/`Target2` is
ordinary ATM usage on this box, not an exotic case.

Deliberately **not** applied to stops: several working stops is a reconciliation problem
(`P1-36`, `P3-30`), and dropping the risk leg over it is the wrong trade in the wrong direction.

### Every guard was verified by mutation, not by argument

Nine tests, hand-written before the code (`*Tests.cs` is a protected path). Six were red at
baseline. The two that were not — the retirement guard and the tick rounding — **cannot** be red at
baseline, because neither situation can arise until targets exist. That is the exact shape of the
"settled fact nothing tests" that shipped `P1-40`, so each guard was instead mutated and the test
observed to fail:

| Mutation | What the suite reported |
|---|---|
| Retirement guard disabled | the orphan stop **is** submitted — 2 `COPIER_STOP` where 1 was expected |
| Id re-used on re-create | the retired group's id carried onto the new stop |
| Target reservation disabled | **2 live targets** against one position |
| Re-drive removed (back off, never re-apply) | a **1-lot** target behind a 2-lot position — under-cover |
| Multi-target refusal disabled | a target mirrored from a scale-out leader |
| Tick rounding disabled | both legs at `.125` on a 0.25 tick |

The stub gained `SimulateChangeFailure` (nothing could reach the cancel-then-create fallback before)
and `FillOrderAndRetireOcoGroup`. The stub models **fill-retires-the-group**, which is what OCO
means; it deliberately does **not** model cancel-retiring-the-group, because that is a guess and
encoding a guess in the double would have made the copier agree with it.

### Still open on this item

- **Not live-validated.** See §4a for exactly what to watch on the first Sim trade.
- **Partial-fill re-pairing across a scaled leader position is untested.**
- The two stop-path changes (OCO id, tick rounding) have not been seen on a real fill.

---

## 4s. 2026-08-10 — the mirrored target's first live trade: 3 of 4 signals pass, and a P0 falls out

**Setup.** `Sim101` ATM bracket, MNQ SEP26, long 1 @ 29788.25, `AtrAdaptive` (which overrode the
requested tick distances): leader stop 29745.75, leader target 29859.75, both in oco `4ac44f1c…`.
RiskGuard `shadow`, armed, guarding. Deployed build `86c6376f`.

### What passed

| | Signal | Result |
|---|---|---|
| 1 | **The mirrored stop is not rejected** now that it carries an OCO id | ✅ `COPIER_STOP` went `Initialized → Submitted → Accepted` under oco `a2e765fd…`. **A single-member OCO group is accepted by NT8** — that was inferred, not proven, and it was the one way this change could be worse than what it replaced |
| 2 | **Both legs, one shared group, right prices, on tick** | ✅ `COPIER_STOP` 1@29745.75 and `COPIER_TARGET` 1@29859.75, both oco `a2e765fd…`. The target JOINED the stop's live group rather than forcing a re-create. Both on a 0.25 boundary |
| 2b | **Distance-mirrored, not price-copied** | ✅ `BRACKET_TARGET_MIRRORED: target 1@29859.75 (leader offset +71.5, follower entry 29788.25)`. Leader and follower both filled 29788.25, so the *orders* alone cannot distinguish the two designs — the log line can, and does |
| — | Ordering and latency | ✅ Stop created 14 ms after the follower's own fill, target 16 ms after the stop. Stop first, as `SyncFollowerBracket` requires |
| — | FSM | ✅ `Created FSM Sim-ORB|MNQ SEP26 -> ProtectedPending` |

### Signal 3 failed, and found `P0-59`

To fill the target on demand its limit was moved to a marketable price. It never got there. The
copier saw the leg enter `ChangeSubmitted`, concluded it was gone, and **created a second
`COPIER_TARGET`** — `BRACKET_TARGET_MIRRORED` at 13:55:56.3437, *before* the modify reached the
broker at .3537. Both ended `Working` at 29859.75 in the same OCO group; the third-party copier
mirrored the pair onward, so three accounts each held two targets against one lot.

Root cause, and the reason it is a **P0 on the stop path**, in the plan's `P0-59`:
`IsPendingOrWorking` omits `ChangeSubmitted`/`ChangePending`, and `OnFollowerOrderUpdate` infers
"terminal" from `!IsPendingOrWorking` — **the two predicates are not complements**. Our own trail
calls `Change()`, so this is reachable on every trail step, on the risk leg, without any
concurrency. `P1-56`'s reservation cannot help: one sync misreading one state is enough.

**The stub enum does not declare those states**, so the suite could not have expressed this at
686/0. That is `P0-49`'s lesson one level lower down — in the enum rather than the event order.

> **The external modify is not what makes this real.** It is what made it *visible in one shot*.
> The production trigger is `Account.Change()`, which the copier calls itself.

### Two other things this trade exposed

- ⚠️ **`MAX_TRADES_BREACH` fired on entry**, on both `Sim101` and `Sim-ORB`, followed by
  `LOCKOUT_PHASE: PendingCancel` and a `LOCKOUT_SWEEP_SHADOW` every 5 s: *"would flatten
  [MNQ SEP26], cancel 2 order(s)"*. `MaxTradesPerSession` is 8 and these accounts are past it.
  **Armed live, this trade would have been flattened on entry and its mirrored legs cancelled** —
  add it to `EDGE_WINDOW_BREACH` on the list of things that will destroy a live validation.
  Shadow contained all of it, which is `P0-51` working.
- **`P1-57` came within one naming convention of firing.** `COPIER_EXEC_SELF_ORIGINATED` shows the
  third-party copier's copy was dropped only because it embedded *our* name
  (`COPIER_FOLLOW-34362-…`) and so matched the `COPIER` substring. Had it named the leg `Stop1`, as
  it does when copying a native bracket, we would have mirrored it onward. The defence held by
  luck, not by design.

### Cleanup

All four accounts flat, no working orders. `nt_close_position` on the leader did **not** propagate
an exit to the followers — each had to be closed explicitly (closing `Sim-ORB` did cascade through
the third-party copier to its two followers). Three `Rejected` leftovers from earlier sessions
remain and are unrelated.

---

## 4t. 2026-08-10 — stepping back: one root cause under both the copier's and RiskGuard's order bugs

`P0-59` looked like "add `ChangeSubmitted` to a list". Reflecting NT8's enum instead of trusting
ours turned it into something much larger.

### The finding

**NT8 has sixteen `OrderState`s.** `IsPendingOrWorking` classified five, `IsTerminal` three. The two
were **not each other's complement**, so eight states were unclassified — and the two addons
independently inferred *opposite* things about them:

| | asked | so an order in… | …was treated as | hazard |
|---|---|---|---|---|
| RiskGuard | `!IsTerminal` | `CancelSubmitted`, `CancelPending` | **coverage** | a position reads as protected while its stop is being pulled |
| copier | `IsPendingOrWorking` | `ChangeSubmitted`, `ChangePending`, `TriggerPending` | **gone** | a duplicate protective leg is created |

Both live. Both naked-risk or over-cover. One root cause, pointing in two directions at once.

### Why the obvious fix was the wrong one

Adding the missing states to `IsPendingOrWorking` would have made the symptom disappear and left
the structure that generates it — the next state NT8 adds lands in the same gap. The reason a single
boolean cannot be right is that **callers ask two questions whose fail-safe answers are opposite**:

- *"is something already here, so do not create a second?"* — answering **no** wrongly over-covers
- *"does this actually protect the position?"* — answering **yes** wrongly leaves it naked

So: one total classification, two derived predicates, and `Indeterminate` **occupies a slot and
provides no coverage** — conservative both ways at once.

**`IsPendingOrWorking` was deleted rather than wrapped**, turning all 21 call sites into compile
errors so each had to declare which question it asked. Nine were coverage questions, four were
cancel-worthiness questions, and they had been sharing one predicate.

### The test double was why none of it was visible

The stub enum carried **ten of sixteen** states. Six could not be named by any test, so the suite
was green at 686/0 with a P0 live. All sixteen are now declared — **reflected out of
`NinjaTrader.Core.dll`, not recalled** — and a conformance test fails if the stub drifts or any
state reaches the default arm. The test file's private copy of the liveness list is deleted too: a
second definition of "alive" living in the grader is this defect one level up.

> This is `P0-49`'s lesson again — *"the test stub raises whatever the test raises"* — one level
> lower down, in the enum rather than the event order. **A green suite is evidence about our
> fiction, not about NT8, unless something forces the two to agree.** That forcing function now
> exists for `OrderState` and for nothing else.

### Verified by mutation, both directions

| Mutation | What the suite reported |
|---|---|
| `ChangeSubmitted` → Terminal (the copier's old belief) | **2 `COPIER_TARGET`s**, exactly as seen live — and **2 `COPIER_STOP`s** on the trail path |
| `CancelSubmitted` → Working (RiskGuard's old belief) | `CoveredQuantity` **6** and state `ProtectedPending` on a position whose stops are *both* being cancelled |

The second is the one worth remembering: a fully naked position, reported as protected, with
nothing arming a replacement.

### What this says about the approach, not the defect

Almost every defect in this project is the same shape: **the model diverged from the broker and
nothing re-derived it.** The plan identified that on page one and then 48 defects were closed by
teaching the fast path one more case. That series does not terminate — the event space belongs to
NT8, and now to a third-party copier as well. The reconciler is not an enhancement to schedule when
convenient; it is the thing that closes the class. See §4a.

---

## 4u. 2026-08-10 — the reconciler lands as the primary path (`P3-30` copier half, `P3-31` seam)

§4t argued that the 48-defect series does not terminate and the reconciler is what closes the
class. This is that work, for the copier's bracket. **New file
`scripts/ninjatrader/addons/CopierReconciler.cs`; both leg syncs now decide through it.**
Suite **762 passed, 0 failed** (from 705). NT8 compiles clean, net48, 0 errors, deployed.

### The structural fact, which is sharper than "the model diverged"

Neither `SyncFollowerStopOnce` nor `SyncFollowerTargetOnce` had **ever** enumerated
`followerAcc.Orders`. Each decided from ONE cached `Order` reference —
`bracket.WorkingStop` / `bracket.WorkingTarget`. So a leg that existed at the broker but was not
the one being held was **invisible, and therefore permanent.**

That is what "two working COPIER_TARGETs against one lot" was on 2026-08-10 (`P0-59`): not a leg
placed wrongly, **a leg nothing was capable of noticing afterwards.** No amount of additional care
on the fast path could have repaired it, because the fast path could not see it. `Reconcile`
enumerating the account and cancelling *extra* owned legs is the whole difference.

### Three states of desire, not two — and why the obvious design is a naked follower

`HasStop: bool` was the first design. It is wrong: "no stop desired" then means both *"the position
is gone, cancel everything"* and *"the leader cancelled its own stop, so we do not know where ours
goes"*. Those need **opposite** handling. Collapsing them reverts `P0-9` item (4) and takes the stop
off an open position — a naked follower delivered as a refactor.

So `LegIntent { Required, Unspecified, Forbidden }`, and `Unspecified` still de-duplicates but never
creates and never cancels the last survivor. `TestDesired_UnknownOffsetIsUnspecifiedNotForbidden`
and `TestReconcile_UnspecifiedLegKeepsOneAndCreatesNone` are the two that hold it down.

### ⚠️ `bracket.StopInFlight` is NOT `Reconcile`'s in-flight parameter

The bracket flags are mutual exclusion between two **syncs**. `Reconcile`'s parameter means
"submitted, and not yet in `Account.Orders`". Feeding the first into the second was the first
wiring and it placed **no stop at all** — `SyncFollowerStop` sets the reservation *before* calling
in, so the reconcile suppressed the very `Create` the sync existed to make. The event-driven
callers pass `false`; a timer is what needs the real ledger.

### Verified by mutation, both layers

18 mutations, each reinstating a belief that was live at some point in this project or an
obvious-looking simplification. **17 caught by a named test.**

| Layer | Mutations | Caught |
|---|---|---|
| the two pure functions | 10 | 10 |
| the wiring into `TradeCopierEngine` | 8 | 7 |

Two results worth more than the tally:

1. **A test caught a real defect in `Reconcile` while it was being written.** The price/quantity
   comparison ran *before* the shape check, so a leg carrying our name with `OrderType.Limit` at
   the stop's price compared equal and was accepted **as the stop** — while a limit below the
   market is not a stop, it fills at once. Shape before price; the order of those two checks is
   the difference between a protective stop and an instant exit.
2. **The mutation harness lied on its first run.** All 10 reported `DID NOT COMPILE`, because the
   build-failure check matched `"error"` — which also matches the `0 Error(s)` summary line. A
   harness that reports every mutation as caught for the wrong reason is worse than none. It now
   matches `": error CS"`. *Check what your gate actually keys on before believing its verdict.*

### Two guards found to be UNREACHABLE, and honestly re-labelled

Mutation testing found two places where I had written something that reads as safety and cannot
change behaviour. Both are recorded rather than quietly kept:

- `AddIfMissing`'s reference-identity check (now `AddCandidate`, a plain append). `Reconcile`'s
  keeper loop already compares by reference, so a doubled entry never produced a cancel.
- `ContainsReference` in the slot collection. **Kept**, but the comment now says plainly that the
  behavioural protection is the keeper loop's `ReferenceEquals` and that this line only makes
  `slotCount` truthful for the operator-facing log. It is not defence.

> The general point: *"I added a guard" is not evidence the guard does anything.* Mutating it away
> and watching the suite stay green is. Both of these would otherwise have been read by the next
> session as load-bearing.

### The one mutation that SURVIVED, stated rather than papered over

`int liveQty = Math.Min(qty, livePos.Quantity)` at the broker call — replacing it with `qty` leaves
the suite green. It is a **second** clamp; `ComputeDesiredBracket` already clamped to the live
position. It is only reachable if the position changes between the reconciler's read and the broker
call, which is a concurrency window the suite cannot drive — the same gap §4a records for `P1-13`,
where the S-series is sequential and the risk is concurrent. **Kept as defence-in-depth, and
explicitly NOT proven.** Do not remove it on the grounds that no test covers it.

### What is NOT done

- **The background timer.** Events call the reconciler; nothing calls it on a clock. Until that
  exists, a divergence that arrives with no subsequent event is still permanent — the reconcile is
  idempotent and ready for it, but unscheduled.
- **`P3-31`'s ledger.** The seam is tested; the ledger does not exist. The timer needs it first.
- **The RiskGuard-side audit** (naked position, orphan stop, FSM/broker divergence). `P3-30`'s
  plan entry covers both addons; only the copier's bracket is done.
- **Live validation.** Everything here is unit + compile + mutation. No live trade has been through
  it. The first live `COPIER_STOP` and `COPIER_TARGET` are the ones to watch, and note that the
  decision path underneath *both* legs changed.

---

## 4v. 2026-08-10 — the reconciler's first live trade: it works, and it found two more defects

§4u shipped with "no live trade has been through this yet". This is that trade, on
`Sim101 -> Sim-ORB` with the guard in `shadow`. **The reconciler did what it was built to do, and
the same hour produced `P0-61` (fixed, live-validated) and `P0-62` (open).**

### ✅ What passed

**The mirror, through the new decision path.** Leader entry 29777.5, ATM stop 29752.75, target
29821.5 → offsets **−24.75 / +44.00**. Follower filled 29778.25 and got stop **29753.50** and
target **29822.25** — both exact, both on tick, **both in one OCO group**.

**The headline: a stray leg the engine held no reference to was cancelled.** A `COPIER_STOP` was
planted directly on `Sim-ORB` at 29745 with no OCO id, so the engine had never heard of it — the
exact state of the original `P0-59` incident. Two working stops then stood behind one lot. On the
next sync:

```
34416 Cancelled                              <- the stray
COPIER_BRACKET_MODIFIED  stop moved to 1@29754.5 in place; no unprotected window
```

The engine's own leg was **modified in place** and the stray was cancelled. The previous build
could not have done this at any price: it read one cached `Order` reference and never enumerated
`followerAcc.Orders`, so the stray was invisible and permanent.

**Exact-match ownership held, live.** The third-party copier mirrored our legs onto `SimCopyTest1`
and `SimCopy2` as `COPIER_STOP-34410-0104CFF5`. Those are not ours, and nothing touched them —
`P1-57`'s hazard from the dangerous direction, and the conservative naming is what covers it.

### ❌ `P0-61` — found by the trade, not by 762 tests

Scaling the leader in exposed it: a second `Change()` against a leg already in
`ChangeSubmitted`/`ChangePending` is **dropped by NT8, and reverts the order to its pre-change
values**. Both follower legs stayed at qty 1 behind 2 lots. Full write-up and the fix are in the
plan's `P0-61`; the short version is that this is `P0-60`'s lesson one step along — a **third**
question (`AcceptsModification`) that the two existing predicates both answer wrongly, because a
mid-change leg occupies a slot *and* provides coverage *and* cannot be changed.

**Re-tested live after the fix**: `BRACKET_DEFERRED` → `BRACKET_DEFERRED_REDRIVE` →
`stop moved to 2@29742.5`, `target moved to 2@29805`. Both legs reached the correct size and price,
which the previous build never managed.

> The transferable half: **declining to act is only safe if something later acts.** The first cut
> reused `*ResyncOwed`, which the sync's own pass loop consumes immediately — re-driving while the
> leg was still mid-change and giving up at the pass bound. It needed its own flag and a settle
> hook placed *before* `OnFollowerOrderUpdate`'s `OccupiesSlot` early return.

### ❌ `P0-62` — still open, and the evidence is inside one `Change()` call

`Account.Change()` **applies the price and silently refuses a quantity increase.** One call carried
both; the order went `1 @ 29743.5` → `1 @ 29742.5`. So a scaled-in follower can never have its
protective leg grown by modification. The attempt budget then stops the retries — it fails quiet
rather than flooding, which is the right failure, but the follower stays under-covered.

Two candidate remedies, both with real costs, written up in the plan. **Do not just widen the
retry budget; the budget is not what is failing.**

### RiskGuard was the only thing that noticed — and shadow is why nothing happened

`FSM_UNDERCOVERED: covered 1 < pos 2`, then `MISSING_STOP_FLATTEN` on all four accounts. **Armed
live, RiskGuard would have flattened the lot.** Worth holding both halves of that: the compensating
control worked exactly as designed, *and* the copier under-covered a live position. Neither fact
cancels the other.

### Operational notes from this session

- ❌ **RETRACTED — there is no ATM lockout bypass. An earlier revision of this section claimed one;
  it was wrong.** The observation was that `nt_place_atm_order` succeeded on `Sim101` while
  `nt_place_order` was blocked on `Sim-ORB`, and I inferred the ATM path skipped the gate. It does
  not: `PlaceAtmOrder`, `PlaceOrder` and `PlaceOcoOrder` all call `IsAccountLocked`
  (`McpBridgeAddOn.cs:3382`), which consults `RiskGuardAddOn.Instance.IsAccountLocked` first.
  **Disproved by direct test 2026-08-10**: `Sim_All_Day_ORB` was locked via
  `nt_emergency_flatten` and *both* endpoints then returned `Order blocked: ... is locked out.`
  > **The real explanation, and the lesson.** `Sim101` was **not** locked at 15:27:46 when the ATM
  > order went in — that entry pushed the trade count past `MaxTradesPerSession` and tripped the
  > lockout about five seconds later (`LOCKOUT_CANCEL` at 15:27:51). I read the status eight
  > minutes afterwards, saw `isLockedOut: true`, and treated it as the state *before* the order.
  > **A lockout state read after the fact is not evidence of the state at submit time**, and on
  > these accounts an ordinary entry is itself enough to cause the transition. Read the gate
  > before the action, or test the gate directly.
- **Both `Sim101` and `Sim-ORB` were locked out on arrival** (`MAX_TRADES_BREACH`, as §4a warns),
  with the shadow sweep logging `[SHADOW] Would execute action CancelAllOrders` every 5 s. I
  **unlocked both** via `POST /api/lockout {"action":"unlock"}` to run the test, which **resets
  those accounts' metrics**. `ShadowSessionsCompleted` is untouched. They are left unlocked.
- **State left clean**: all accounts flat, zero working orders, guard still `shadow`/armed.
- `/api/riskguard/state` does not exist; the FSM route is `/api/riskguard/fsm-state`, and
  `nt_riskguard_state` returned an empty list even with four positions open.

### ⚠️ A test-writing trap that cost an hour, and the product question under it

**Raising two separate leader stop ORDER OBJECTS leaves the first one `Working`, and the copier
re-anchors from whichever it reads last.** A test written that way passes or fails on collection
iteration order — `TestBracket_P0_61_ADeferredChangeIsReappliedWhenTheLegSettles` passed once, then
failed three runs in a row on identical source, which is what sent me looking for a bad mutation
restore that did not exist. Trail the **same** order object instead
(`leaderStop.StopPrice = ...; leader.TriggerOrderUpdate(leaderStop);`) — which is also what NT8
really does, since a trailed leg keeps its id and oco (§4p). `TestBracket_TrailingModifies...` uses
two objects and happens to pass; do not copy that shape.

**The product question it exposes**: with two working leader stops, the copier picks an arbitrary
one to anchor on. `P0-9` refuses a multi-*target* leader outright
(`TestBracket_P0_9_AMultiTargetLeaderIsNotMirroredAtAll`) but there is **no equivalent refusal or
coverage-sum for multi-STOP leaders**, even though `P1-36` built the multi-stop coverage sum that
would answer it. Not filed as a defect — a real leader's ATM trails one leg in place — but worth
resolving when `P1-36`'s sum is shared with the reconciler.

---

## 5. Decisions already made — do not re-litigate

> **`P0-9` item (1)'s five invariants (closed 2026-08-10).** Mirrored verbatim into `profiles.py`'s
> `settled`, per §10.2b of the loop doc. Retire from **both** places or the panel keeps arguing.
>
> 1. **The two legs are deliberately asymmetric.** Do not propose unifying the syncs, sharing
>    `StopInFlight`/`StopAttempts` with the target, or making the target symmetric. Sharing lets an
>    in-flight *target* sync delay the risk leg, and lets target churn spend the stop's budget.
> 2. **The OCO id rule is about the group's life, not the id's history.** A fresh id is minted only
>    on the cancel-then-create path. Not per-generation on every sync; and not never — re-using an
>    id whose group may be retired has the broker reject the new **stop**.
> 3. **A leg terminal while its sibling FILLED was retired, not lost.** `P0-50`'s live re-read does
>    not catch this, because ExecutionUpdate precedes PositionUpdate.
> 4. **A multi-target leader is not mirrored at all.** Not nearest, not last-seen. Not applied to
>    stops.
> 5. **Leg prices are rounded to tick before the already-correct comparison**, not after — after
>    would never match and would re-drive the leg forever.

> **`P1-56`'s two invariants (closed 2026-08-10).** Mirrored verbatim into `profiles.py`'s `settled`,
> per §10.2b of the loop doc.
>
> 1. **`SyncFollowerStop` is the reservation holder; `SyncFollowerStopOnce` does the work and never
>    touches the flags.** `StopInFlight` is published under `_lock` before any broker call and cleared
>    exactly once in a `finally` that runs *after* the bounded re-drive loop. Do not clear it between
>    passes (reopens the window); do not leave it set for the re-drive to clear (**leaks forever** —
>    the re-drive backs off before reaching any `finally`); do not make the re-drive recursive again;
>    and **do not let re-drive passes skip the `StopAttempts` increment** — they make real broker
>    submissions, so not counting them multiplies the bound.
> 2. **`bracket.WorkingStop` is never cleared before a broker call, nor in `OnFollowerOrderUpdate`** —
>    not even on the `catch` or abort paths. An honest `WorkingStop` is what makes a concurrent sync
>    *modify* the existing stop rather than create a second one. If the `Cancel` threw, the old stop
>    may still be live, and forgetting it recreates the duplicate-leg defect.

- **The copier fails closed on ENTRIES, never on EXITS** (settled across `P0-5`, `P0-6`, `P1-23`,
  `P1-22`). A quarantined relationship still copies exits; unimplemented sizing modes block
  entries only; an exit is never rounded or clamped to zero while the follower holds a position.
  Blocking an exit strands the follower in a position the leader has already left — worse than the
  thing being guarded against. Reviewers propose "just quarantine it" every time.
- **Orders are keyed by object reference, never by `Order.OrderId`** (`P1-22`). NT8's `OrderId` is
  neither unique nor stable across the historical→live transition (`RiskGuardAddOn.cs:4481`). The
  test stub assigns one stable GUID per order, so an id-keyed map passes the entire suite.
- **The mirrored bracket stop carries the leader's SIGNED offset**, applied to the follower's own
  fill (`P0-9`). Never `Math.Abs` — a leader trailing into profit puts the stop above entry on a
  long, and an absolute distance mirrors it onto the losing side. Never the leader's stop *price* —
  that is wrong by the slippage `P1-22` measures, and by a whole scale across a micro/mini
  conversion.
- **Bracket re-submission is bounded, and the counter does not reset on a successful `Submit`**
  (`P0-9`). The failure mode is a broker that accepts the submit and rejects the order moments
  later, so "Submit did not throw" is not evidence of protection.
- **Slippage and mirrored distances are computed only between price-comparable instruments**
  (`P1-22`, `P0-9`). A `CustomSymbolMappings` entry may legitimately point ES at NQ.
- **The copier places no default bracket of its own** (`P0-9`). RiskGuard's auto-stop owns
  "position with no stop"; two independent stop sources over-cover and flip the position when both
  fire. `EnableFollowerAtm` was deleted, not implemented.
- **Coverage is the SUM over every live protective stop** (**P1-36**, closed 2026-08-07).
  `CoveredQuantity` and `RecognizedStopOrder` are both **derived** from `PositionGuardFsm`'s stop
  list and neither is assignable — the old pair had to be written together at nine sites and
  nothing stopped them drifting. The auto-stop is sized to `liveQuantity - alreadyCovered`, not to
  the whole position. Do **not** propose restoring a single `RecognizedStopOrder` slot or the
  "replace only with an equal-or-larger stop" rule.
  > This bullet previously read *"multi-stop coverage aggregation is out of scope; `CoveredQuantity`
  > deliberately follows a single stop order"*. Same retirement as the P1-35 entry below: left
  > unedited it would instruct reviewers to approve reintroducing a closed defect.
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

- **NT8 raises `ExecutionUpdate` BEFORE `PositionUpdate`.** Any code that reads `account.Positions`
  from an execution handler is reading a position that does not exist yet on an entry fill. This
  cost `P0-49`: the copier's bracket anchored itself that way and therefore never anchored at all,
  leaving followers naked for the life of every ATM trade. **The test stub raises whatever the
  test raises, in whatever order the test chose** — and every bracket test drove
  position-then-execution, because that is the order a person writes it in. Subscribe to
  `PositionUpdate` for anything that needs the net position.
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

---

## 4w. Session 13 record — 2026-08-11: the copier ratio converter, slice 1 of 3

**This is a FEATURE, not a defect fix.** No `P`-number: the hardening plan's IDs are
never reused, and nothing here closes one. Asked for by the user: *"a ratio
convertor for the copy trader where I can trade for e.g. one MES in one account,
but take 3 in a different account and 5 in another."*

### State

Two commits on `harden/riskguard-p0-51`, **unpushed**, on top of `86c6376f`:

* `36bd59f6` — CM1 acceptance tests, RED at baseline: 789 passed, **17 failed**
* `37cb5193` — the implementation: **806 passed, 0 failed**, build clean under net48
  + net8.0-with-stubs

**Not deployed. Not compiled in NT8. Not live-validated.** Unit + `dotnet build`
only. Before deploying, follow the NT8 sync rules in CLAUDE.md
(`sync_nt8_strategies.py --verify --only addons`, then `--only addons`, then
`nt_compile`) — do not hand-copy.

### What slice 1 changed

`CopierSizingMode.PerTickerMatrix` was declared at `TradeCopierEngine.cs:24` and
implemented **nowhere** — it fell through to the `QuantityRatio` branch. Four
defects followed, each now covered by a test that was red beforehand:

1. **The mini/micro multiplier was applied ON TOP of the table ratio.**
   `PerTickerRatios["MES"] = 3.0` with `AutoSymbolConversion = true` computed
   `round(1 * 3.0 * 0.1) = 0` — MES is in the micro list — and the sub-one-contract
   guard then silently skipped the entry. **The operator asked for 3 contracts and
   got none.**
2. **`TranslateSymbol` applied the same table independently**, routing an MES
   leader fill to **ES** on the follower while sizing it in MES contracts. The
   instrument decision and the quantity decision were made in two places from two
   different keys. That is the root defect, and it is the same shape as `P0-60`:
   two callers inferring different things from one fact.
3. **An unmapped instrument fell through to the flat `QuantityRatio`** — a silent
   unscaled copy. Observed: 1 contract from a configured ratio of 7.0.
4. **The lookup called `Math.Abs(tickerRatio)`**, so a configured **-3.0 would have
   become 3 live contracts.**

Now, inside matrix mode only: the branch is evaluated **first**; the ratio is the
literal contract count with no symbol multiplier; `NaN`, both infinities, zero,
negative, and anything rounding to zero are each treated as **no rule**; no rule
**fails closed on ENTRIES and never on exits**; and the leader's instrument is
preserved, with a cross-instrument `CustomSymbolMappings` entry **refused** rather
than approximated. Every other sizing mode is untouched.

### Settled here — do not re-litigate

* **The ratio is a contract COUNT in the follower's instrument, not a notional
  scaling.** `1 MNQ -> 3 MES` means three MES. The user chose this explicitly.
* **One rule is `(leader root -> follower root, ratio)`** — the instrument and the
  count are one decision, because deciding them separately is defect 2 above.
* **An unmapped instrument fails closed on entries, mirroring the existing
  `NetLiquidationRatio` guard.** The user chose this over falling back to auto
  conversion.
* **A no-rule EXIT mirrors `leaderQty` and lets the existing clamp cap it at the
  live position.** A reviewer raised twice that a partial leader exit can therefore
  flatten the follower completely. Accepted and documented in the code: on that path
  there is no ratio BY DEFINITION, and flat is safer than stranded.
* **`PerTickerRatios` needed no DTO work.** It already existed, was already
  deep-copied per follower by `CopierGroup.ToRelationships()`, and was already read
  by the sizing branch. A four-part plan that proposed re-creating all of that was
  discarded once the file was actually read.

### Still open — slices 2 and 3

* **Slice 2, cross-instrument** (`1 MNQ -> 3 MES`, `1 ES -> 2 MES`). Needs a rule
  type carrying the follower root, and must **replace** slice 1's deliberate
  refusal. Note `P1-22`'s rule survives: a cross-instrument mapping records **no
  slippage**, because the two price scales are incomparable.
* **Slice 3, reachability.** `PerTickerRatios` and `CustomSymbolMappings` are
  parsed by **nothing** and exposed by **nothing** — not by `LoadFromDisk`, not by
  the `McpBridgeAddOn` copier-config endpoint. So the table can still only be set
  from code or a test. This is the same "config that cannot be set" family as the
  fields `P1-23`/`P0-9` deleted. **Until slice 3 lands, the feature is not usable
  from the UI or the bridge.**

### Two constraints that will bite the next session

* **`McpBridgeAddOn.cs` and `RiskGuardAddOnTests.cs` cannot be edited by the agent
  loop at all.** Both contain C-style block comments, and `regions.py` refuses such
  files rather than risk its brace matcher. That makes slice 3's bridge half a
  hand-edit, and it is why slice 1's tests were hand-written.
* **`class Program` in the test harness is not `partial`, and `Assert` is private to
  it.** `TestHarness_AllDeclaredTestsAreInvoked` reflects only over
  `typeof(Program)`, so a test in a NEW file compiles and **runs nothing**. New
  tests must go into `RiskGuardAddOnTests.cs` and be registered in `Main`. The
  CM1 tests are at the end of that file, registered just before the self-check.

### The loop found thirteen of its own defects doing this

Slice 1 was produced by the agent loop (qwen3.5 implementer, glm-5.2 + minimax-m3
panel, deepseek-v4-pro arbiter) over three rounds — the gate ladder caught a
regression in round 1 that round 2 fixed. Getting there required fixing **O37-O50**
in the agent-loop package, now pinned at **v0.6.2**. The full account is
[agent-loop HANDOVER §13](file:///c:/Users/vinay/agent-loop/docs/architecture/HANDOVER.md).

**The one to carry into any future loop run on this addon:** the arbiter upheld
**0 of 66 findings** across four SHIP rulings, and on one plan the panel was right
about a signed exit quantity that would have **increased a follower position sitting
opposite the leader** — `P1-56`'s class, in a plan the arbiter shipped. Three of the
five human corrections to the CM1 ticket came from findings the arbiter had
dismissed. **Do not treat `ARBITER_SHIP` on this profile as a review.** Read the
patch against the file.
