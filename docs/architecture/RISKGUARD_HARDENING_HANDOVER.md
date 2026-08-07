# RiskGuard / TradeCopier Hardening — Session Handover

**Last updated**: 2026-08-07 (session 8 — the P1 band closes; NT8 up, deployed, compiled clean)
**Branch**: `harden/riskguard-copier-p0` (session-8 work committed here, **not yet merged or pushed**)
**Plan of record**: [RISKGUARD_COPIER_HARDENING_PLAN.md](RISKGUARD_COPIER_HARDENING_PLAN.md) — **50 defects, 38 closed, 12 open** (`P0-9` and `P1-13` are part-closed and counted as open; the other ten are `P2-24`, `P2-25`, `P2-26`, `P2-27`, `P2-29` and the five P3s). `P0-49`/`P0-50` were opened and closed on 2026-08-07 — see §4l
**Live state**: deployed, `shadow`. NT8 compiles clean (0 errors), all 9 addon files in sync.
Suite **622 passed, 0 failed**. Loop selftest **11/11**.

> ✅ **Session 8 closed clean. Nothing is in flight and nothing is blocked.**
>
> | | |
> |---|---|
> | Repo | 11 commits on `harden/riskguard-copier-p0`. **Not merged, not pushed** |
> | NT8 | Running, **all 9 addon files in sync**, `nt_compile` 0 errors, feed connected, no open positions |
> | Suite | 622 passed / 0 failed (was 524) · loop selftest 11/11 |
> | Operational | **Nothing outstanding.** `P2-41` is closed and verified live |
>
> **Closed this session**: `P1-12`, `P1-14`, `P1-36`, `P2-38`, `P2-41`; `P1-13`'s fail-open half;
> `P0-9` items (3) and (4); stress tests `S5`, `S6`, `S8`, `S9`; and **`P0-49`/`P0-50`, two new P0s
> found by a live ATM trade** (§4l). **The P1 band is done apart from `P1-13`'s threading
> inversion.**
>
> **The session-7 caveat resolved — half well, half badly.** A live ATM trade finally exercised the
> mirrored stop, and:
> - ✅ **the signed-offset arithmetic is CORRECT on real fills** (29774.25 = 29789.25 − 15);
> - ❌ **the trigger never fired.** The follower was naked for the whole trade and then collected
>   three orphan stops on a flat account. Fixed as `P0-49`/`P0-50`, deployed, compiles clean.
>
> ✅ **RE-VALIDATED LIVE the same session, after the fix** (15:55:56, MNQ SEP26). Follower filled
> 29822.25; `COPIER_STOP` at 29807.25 was submitted **1 millisecond later**, and the follower's FSM
> was created **`ProtectedPending`** instead of `Unprotected`. Leader entry 29821.75, leader stop
> 29806.75, offset -15.00, follower 29822.25 - 15 = 29807.25 — exact. **`P0-9`'s mirrored stop is
> now validated end to end on real fills: arithmetic, timing and FSM state.**
>
> Note the copier **acts regardless of guard mode** — `shadow` restrains RiskGuard, not the
> copier. Both relationships are enabled and `Sim101 → Sim-ORB` is `ArmedForLive: true`, so the
> next Sim101 fill will place a real stop order on the follower.
>
> **`nt_riskguard_config` with no arguments used to be a destructive write** — see §4k. It is safe
> now, but any older transcript showing that call also shows the live config being flattened.
>
> **What is pending is now §4a**, rewritten as a prioritised backlog rather than a phase list.
> Short version: **validate the mirrored stop on a live feed before writing any more code**; then
> `P0-9`'s targets/OCO item needs *your* decision, not a code change; then `P3-30` (the
> reconciler) is the highest-value thing left. `P1-13`'s threading half needs a
> concurrent-guard-event stress test written first — **the S-series does not cover that**, despite
> being finished. The loop's own backlog is [AGENT_PATCH_LOOP.md](AGENT_PATCH_LOOP.md) §12.

---

## 0. Start here (read this, then §4a for what is pending)

### 0.0 The branch is merged and pushed — and every SHA below this line is stale

On **2026-08-07** the branch was fast-forwarded into `main` and pushed to GitHub.
`origin/main` is `aaecbe8b`. This was done **before shadow validation**, which is the
opposite of what §6 item 4 recommended — the merge was a deliberate call to get 282
unpushed commits off one machine, not a signal that `P0-9` is validated. **The live-feed
shadow session in §6 item 6 is still outstanding and still gates any acting mode.**

> ⚠️ **Commit SHAs cited throughout this document no longer resolve.** Getting the push
> through required rewriting history twice — once to purge `data/` (a 126 MB
> `NQ1_1m.parquet` exceeded GitHub's 100 MB limit and had been silently rejecting every
> push for 202 commits), and once to purge 88 MB of `.m4a`. Both rewrites changed every
> commit SHA in the range. `1d9566fe`, `76137575`, `922b2c44`, `c5a4f035`, `904d44bc`,
> `737533a3`, `a2a519fd`, `fb55d281` and the rest are **orphaned** — the *work* is all
> present in `main`, only the identifiers are dead. Do not cite these SHAs onward, and
> check `git cat-file -t <sha>` before trusting any of them.

Also landed in that push, and relevant if you commit here:

- **`.githooks/pre-commit`** now blocks parquet, audio, video, and anything over 50 MB —
  including via `git add -f`, which is how the 126 MB parquet got in past `.gitignore`.
  It is **not automatic**: run `git config core.hooksPath .githooks` in each clone or it
  silently does nothing. Override a deliberate exception with `ALLOW_BIG_FILES=1 git commit`.
- **A live Gemini API key** was found by GitHub's secret scanning in
  `scripts/trader/chart_agent/test_vision.py:3` and scrubbed from history. It never
  reached GitHub, but **it still needs rotating**.
- **0.28 GB of older parquet remains in published history** (the purges only covered the
  then-unpushed range). Logged in `docs/ROADMAP.md` under Known Issues / Tech Debt.

**33 of 48 defects closed, plus `P0-9`'s naked-follower exposure. Suite 524/0. NT8 compiles clean, and every fix in this session has
been verified on the live box** (see the banner).

| Phase | State |
|---|---|
| **A** — deploy P0 to shadow | Deployed and armed. **T3 validated live (§4g). T5 has never been exercised** — it needs an acting mode |
| **B** — test foundation | ✅ done |
| **C** — P1 safety-critical | ✅ done — `P1-36` closed session 8 |
| **D** — P1 rule semantics | ✅ done — `P1-16`, `P1-17`, `P1-18`, `P1-19` |
| **D2** — stress backlog | ✅ done — `S1`–`S4`, `S7`, and **`S5`/`S6`/`S8`/`S9` (session 8)** |
| **E** — copier fidelity | ✅ `P1-21`, `P1-22`, `P1-23`, and **`P0-9`'s naked-follower half** closed. Targets/ATM remain (see plan `P0-9`) |
| **F–G** | Not started |

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

**2. A machine check is only as good as the paths driven through it.** The lock-scope invariant
was already machine-enforced (`Account.BrokerCallObserver` + `TestIsStateLockHeld()`) and still
missed `P1-43` — four `account.Cancel` calls under `_stateLock` on the order-update path — because
the check only ever drove the sweep and FSM teardown. `S4` now drives every entry point.

**3. Only NT8 proves the build.** `P1-47` compiled clean under net8.0 with the suite green and
failed in net48, because the methods sat inside `#if TESTING`. **Always `nt_compile` after
touching code near the test hooks**, and read `RESULTS:` from a *fresh* build — a `dotnet run
--no-build` after a failed build silently reports the previous assembly's result.

**4. One operational item remains (`P2-41`). The shadow-counter reset is DONE.**

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

**5. `P0-9`'s naked-follower half is closed; what remains is fidelity, not exposure.** Followers
get a mirrored stop anchored to their own fill. Items (3) `StopLimit` and (4) leader-cancels-stop
are pinned by test as of session 8. Only profit targets + OCO remain, and that wants an operator
decision — see §4k. **The mirrored stop has still never been seen on a live fill.**

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
| `d94d5521` | **T1 — P0-1 + P0-4**: stop-guard FSM coverage model |
| `ff72e574` | **Test harness repair** — the suite could not previously catch defects |
| `03dfdfc5` | **T2 — P0-2 + P0-3**: reserve-before-submit auto-stop, sized from the live position |
| `904d44bc` | **T3 — P0-7**: unrealized-only peak for the giveback rule |
| `737533a3` | **T4 — P0-5 + P0-6**: exits clamped to the follower's position; no sub-1 flooring |
| `fb55d281` | **T4 follow-up**: an exit must not round down to zero and strand the follower |
| `a2a519fd` | **T5 — P0-8 + P0-9**: copier respects the lockout; fails closed when unguarded |
| `6129f15a` | Dead half of the auto-stop quantity guard removed |
| `4d7d9557`, `3bc4dfff`, `4de6c6b5`, `10b32c5a` | **Four loop repairs** — see §4d |

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
| T1 | P0-1, P0-4 | ✅ committed `d94d5521` |
| T2 | P0-2, P0-3 | ✅ committed `03dfdfc5` |
| T3 | P0-7 | ✅ committed `904d44bc` |
| T4 | P0-5, P0-6 | ✅ committed `737533a3` (+ exit-rounding follow-up `fb55d281`) |
| T5 | P0-8, P0-9 | ✅ committed `a2a519fd` |

**All five are applied and committed on `harden/riskguard-copier-p0`. Nothing is deployed** —
NinjaTrader is still running the unmodified addon. Deploying is the next decision, and it is a
human one.

### Two things found by review, not by the panel
- **T4's exit rounding** (`fb55d281`). Removing the `Math.Max(1, ...)` floor was right for
  entries — that floor *was* P0-6 — but applying it to exits created the mirror defect: an exit
  that rounds to 0 strands the follower in a position the leader has already left. Not an edge
  case: every partial exit rounds down independently, so a leader who entered 10 MNQ (follower:
  1 NQ) and exits in any increment below 10 produces 0 every time, and even a 5+5 exit strands it
  because `Math.Round(0.5)` is 0 under banker's rounding. Exits now take at least one contract
  when the follower holds one, clamped to the real position size.
- **T3's session reset** (`904d44bc`). Spec item 1 asks for the new peak fields to be cleared
  where `PeakEquity` is, but neither of those two sites was in the ticket's region set, so the
  loop could not have done it. Added by hand.

### Known-acceptable residue in T2 (do not re-open without new evidence)
- ~~A dead clause survives in `ExecuteAction`~~ — removed in `6129f15a`. Recorded because the
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
   (`56fab156`, `a512ef9d`)
2. **Unanimous APPROVE from adversarial reviewers is unreachable.** Three rounds against the
   168-line `ExecuteAction`: 11 findings in round 1, 13 in round 3, **zero overlap**. Every
   finding was fixed; each rewrite exposed new ground. The prompt said "apply every required
   change", so false positives drove the rewrites that generated the next round's findings.
3. **There was no arbiter.** Rung 6 was "a human reads artifacts", which is not a rung. Added
   `arbiter.py`: rules each finding UPHELD / REJECTED / OUT_OF_SCOPE, feeds back only upheld ones,
   and stops the run when rounds stop converging. It cannot overturn a mechanical gate and it
   cannot ship — `ARBITER_SHIP` writes a patch and a rationale and waits for a human. (`9cce2c72`)

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

**The arbiter was also silently discarding its own output** (`4d7d9557`): a mismatched `<<<END>>>`
tag threw away every rationale and all 11 settled nominations across both rounds, and a stray
bracket dropped one ruling. Fixed, and the recovered decisions are now in the loop's `settled`
profile so T3–T5 stop paying for them.

## 4d. Four loop repairs, all one bug (session 3)

T3 exposed the same failure mode four times: **strict format parsing silently discarding valid
content, then reporting the wrong cause.** Every one cost real rounds.

| Commit | What was discarded | Cost |
|---|---|---|
| `4d7d9557` | Arbiter `RATIONALE` + `SETTLED` — a mismatched `<<<END>>>` tag emptied both | 11 settled decisions lost across two T2 rounds, silently |
| `3bc4dfff` | An implementer block closed with `>>` instead of `>>>` | **3 rounds and the whole T3 ticket**; r2/r3/r4 were byte-identical and correct |
| `4de6c6b5` | Arbiter rulings written `- REJECTED #1` without brackets | A clean SHIP downgraded to a spurious ESCALATE |
| `10b32c5a` | The resumed candidate was never written to `rN_impl_raw.txt` | The printed `promote:` command named a **stale candidate carrying two upheld findings** |

The last one is the dangerous one. On resume the loop read the candidate but never persisted it,
while every `resume with` / `promote:` hint is built from the round number — so it recommended
promoting a file it had never reviewed. Following that hint would have put the unfixed
close+reverse flip defect into an addon that flattens live funded accounts. **The hint is now
correct, but keep verifying that the file you promote is the one the arbiter actually saw.**

The general lesson for this loop: when a gate says a model got the format wrong, check whether the
*content* is there before spending another round. Marker punctuation is not what the gates exist
to check.

## 4a. What is pending — the current backlog

**48 defects, 36 closed, 12 open** as of session 8 (2026-08-07). The phase structure below
(A–G) is kept as historical record; **A, B, C, D, D2 and E are all done.** This section is the
live list. Band membership and the P1-30/31 → P1-35/36 renumbering are in the plan's inventory
table.

### The one that outranks everything else

✅ **The mirrored stop is VALIDATED LIVE (2026-08-07, §4l).** Two ATM trades: the first exposed
`P0-49`/`P0-50`, the second — after the fix — mirrored the stop **1 ms** after the follower's fill,
at exactly `followerEntry + (leaderStop - leaderAvgPrice)`, with the follower FSM created
`ProtectedPending`. This was the longest-standing open item in this document.

**What remains unvalidated live**: `T5`'s fail-closed gate, which needs an acting mode
(`IsGuardProtecting` requires `mode == "live"`); and the firm-mirror rules, which are loaded but
unmapped. Note the copier acts regardless of guard mode — `shadow` restrains RiskGuard, not the
copier.

### Needs an operator decision, not a code change

**`P0-9` item (1) — profit targets and OCO.** The last piece of `P0-9`, and **the operator hit it
immediately**: on the validated trade, Sim101 carried `Target1` (Limit Sell 29851.5) and Sim-ORB
received only `COPIER_STOP`. That is by design, and it is the first thing anyone notices.

- *Against building it now*: a mirrored target is **upside, not risk**. The follower already exits
  when the leader's target fill is copied, so the gap is fill quality, not exposure. Building it
  doubles the copier's order-placement surface on a component whose **first** half has never been
  observed live.
- *For*: it is option 1 of the plan's own preferred fix, and the latency gap is real in a fast
  market.
- **If it is built it must use a real broker-side OCO id.** A mirrored target without OCO leaves
  the stop working after the target fills, which flips the follower into a fresh position — the
  same over-cover hazard the cancel-then-replace rule prevents *within* the copier.

**Recommendation: validate the mirrored stop first, then decide.**

### Ready to code, in value order

| | What | Note |
|---|---|---|
| 1 | **`P3-30` — the independent reconciler (REAPER port)** | The plan calls this "the highest-value single addition in the whole plan". It is P3 by **effort, not by value**, and the plan already says to reconsider promoting it once P1 lands — which it now has. It catches the class of defect every review and green suite in this project has repeatedly missed. `P1-36` built the multi-stop coverage sum it needs; share that, do not rebuild it. |
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

### Repo hygiene, carried from session 7 and still open

- The branch **`harden/riskguard-copier-p0` is unmerged and unpushed** (session-8 work is committed
  on it).
- **The Gemini API key** scrubbed from history (`scripts/trader/chart_agent/test_vision.py`) still
  needs **rotating**. It never reached GitHub; that is not the same as it being safe.
- **0.28 GB of older parquet remains in published history** — the purges only covered the
  then-unpushed range. Logged in `docs/ROADMAP.md` under Known Issues / Tech Debt.
- `.githooks/pre-commit` is **not automatic**: run `git config core.hooksPath .githooks` in each
  clone or it silently does nothing.

---

### Phase A — deploy P0 (no new code) — deployed; live-feed validation still outstanding

Nine live-risk fixes are in a branch doing nothing. Shadow mode is also the only way to validate
T3's giveback rule and T5's fail-closed gate against real account data; no unit test can.
**Runbook in §4e — read it, the ordering is not obvious and the live config is not in shadow.**
T3 was validated live (§4g); **T5 has never been exercised** — it needs an acting mode.

### Phase B — foundation: the test suite comes first ✅ DONE (2026-08-07)

**From here on the work is test-first, and it is enforced, not encouraged.** See the plan's
§6.0 for the full model. In short: a ticket declares `expect_green`; the loop **refuses** it
unless those tests are already red at baseline; the test gate **fails** any candidate that leaves
one red; and reviewers must judge the tests' completeness and accuracy, not just the patch.

1. ✅ **`expect_green` and the test-first refusal** — landed (`129a77ac`). Reviewers also now
   receive the acceptance tests read-only.
2. ✅ **Backfilled (2026-08-07, `14a93486`).** Six tests, each *verified to fail with its fix
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

### Phase C — P1 safety-critical ✅ DONE — `P1-36` closed in session 8

✅ **The whole phase is closed except P1-36**: `P1-20` and `P1-37` (`6678bbc3`), then the
concurrency cluster `P1-10`, `P1-35`, `P1-11`, `P1-15` (`1ea33c8d`). All test-first, each
observed red before its fix.

**The lock-scope invariant is now machine-checked.** The stub account reports every
`Cancel`/`Flatten`/`CreateOrder`/`Submit` to an observer and the addon exposes
`TestIsStateLockHeld()`, so a test asserts the design doc's central concurrency claim
directly. `DrainPendingCancels()` throws in the TESTING build if called with the lock held —
the nested-`lock` "fix" is re-entrant and would silently reintroduce P1-35.

~~**P1-36 is deliberately left.**~~ **Closed 2026-08-07 (session 8).** `CoveredQuantity` and
`RecognizedStopOrder` are now derived from a list and read-only; the settled decision that made
the single-stop behaviour deliberate has been **retired in both §5 and `profiles.py`**.

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

### Phase D2 — stress backlog ✅ DONE (S1–S9 all in the suite)

`S1`–`S4` landed 2026-08-07 and closed four defects on their first run (`P1-43`, `P1-44`,
`P1-45`, `P2-46`). `S7` landed with `P0-9`. **`S5`, `S6`, `S8` and `S9` landed in session 8**,
each verified red against the defect it names. Full specs in the plan's §8.

**They are scenario coverage, not concurrency coverage — see the warning at the top of this
section before treating them as a prerequisite for `P1-13`.**

| | Stress test | Relates to |
|---|---|---|
| `S5` | Partial-fill storm, both event orderings | `P1-16`'s late-fill revision is currently proven by unit tests only |
| `S6` | Rapid flip loop | `P1-36`, T1's `CoveredQuantity` model |
| `S7` | Copier fan-out under burst | `P0-5`, `P0-6`, `P1-22` — **run with Phase E, not after it** |
| `S8` | Config reload while armed and in position | `P1-39`, `P1-42` |
| `S9` | Restart mid-trade | `P1-15`, and `P1-16`'s documented restart limit |

Two rules carried from §8: every stress test is **written red first**, and concurrency tests must
assert an observed invariant rather than "no exception thrown" — the pre-existing
`TestCopierGroup_GroupStressAndConcurrency` only asserts the latter, which is why it has never
caught anything. And confirm each one fails *for the reason intended*: the first draft of S1–S4
passed three assertions against code that never executed.

### Phase E — copier fidelity ✅ DONE except `P0-9`'s targets/OCO item

**The naked-follower exposure is closed** (session 7): followers get a mirrored stop carrying the
leader's signed risk distance, anchored to their own fill. Items (3) `StopLimit` and (4)
leader-cancels-stop were pinned by test in session 8. Only profit targets + OCO remain, and that
wants an operator decision — see the top of this section.

Original framing follows, from when this was the largest live exposure.

> Only its fail-closed *precondition* landed in T5 — followers still receive bare market orders
> with no protective legs. Their sole protection today is RiskGuard's `StopAttachSeconds` grace →
> `RiskGuardAutoStop` at a fixed tick offset from *average price*, which bears no relation to the
> leader's actual stop; and if RiskGuard is disarmed, in shadow, or the follower is excluded,
> there is no stop at all.

Read the plan's `P0-9` for the three options in preference order. Two things this session
established that bear on it directly:

- **`P1-22` built the machinery `P0-9` needs.** `_pendingCopies` already links a follower order to
  the leader execution that caused it, keyed by `Order` reference. Bracket replication needs the
  same join, so extend that map rather than adding a second one — and keep the reference keying
  (`OrderId` is neither unique nor stable; see `P1-22`).
- **`S7` runs *with* this work, not after it** (plan §8). Copier fan-out under burst is the only
  planned coverage for the ordering failures bracket replication can introduce.

Sequence it as: `S7` red first → `P0-9` → `S7` green.

### Phase F — P2 structural — `P2-28`, `P2-38`, `P2-41`, `P2-46` closed

Remaining: **`P2-26`** (doc drift — the design doc still overstates what exists, and is the
cheapest real win left), **`P2-24`**, **`P2-25`**, `P2-27`'s remaining CI half, `P2-29`. Note
**`P2-27` is half-closed**: the copy path is in the test build with real coverage; only the CI job
is outstanding. The plan text still describes it as fully open.

### Phase G — P3

**P3-30, the independent reconciler (REAPER port), is the highest-value single addition in the
whole plan** — an auditor that re-derives ground truth from the broker and repairs what the FSM
missed. It is P3 by effort, not by value; reconsider promoting it once P1 lands. **P1 has now
landed, so that condition is met — it is item 1 of the ready-to-code list above.** `P1-36` already
built the multi-stop coverage sum the reconciler needs; share it rather than rebuilding it.

Then P3-31, P3-33, P3-34. **`P3-32` may already be closed by `P0-9`** — see the note above.

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
4. ~~Merge `harden/riskguard-copier-p0` → `main`.~~ ✅ **Done 2026-08-07 — but done *before*
   shadow validation, against the advice this item originally gave.** The trigger was
   operational, not technical: 282 commits had never been pushed, so the work existed on one
   machine only. `main` was fast-forwarded (the branch was a strict ancestor, 0 behind) and
   pushed; `origin/main` is `aaecbe8b`. See §0.0 — the history was rewritten in the process and
   the SHAs in this document are orphaned. The branch did also carry the ~7 unrelated
   narrative/wargaming commits noted here, plus five more committed that day.
   **This changes nothing about validation state**: deployment still copies from the working
   tree, and item 6 below is still the gate on an acting mode.
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
7. ✅ *(both done — `P1-37` fixed, counter reset 2026-08-07; see §0 item 4)*
   **Fix P1-37 and reset `ShadowSessionsCompleted` to `0`** (addon stopped) before considering an
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

**Net**: Phase A is **half validated**. T3 is proven on a live feed and the one blocker the
session found is closed. T5 still requires an acting mode and has never been exercised.

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
**Read the rulings. Same lesson as §4c.3.**

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

## 5. Decisions already made — do not re-litigate

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
