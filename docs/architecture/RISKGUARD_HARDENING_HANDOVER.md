# RiskGuard / TradeCopier Hardening — Session Handover

**Last updated**: 2026-08-07 (session 7 — ends with NT8 down; see the resume block below)
**Branch**: `harden/riskguard-copier-p0` — **unmerged**, fast-forward available
**Plan of record**: [RISKGUARD_COPIER_HARDENING_PLAN.md](RISKGUARD_COPIER_HARDENING_PLAN.md) — 48 defects, 32 closed
**Live state**: **NinjaTrader is DOWN** — see below. Suite **499 passed, 0 failed**.

> 🔴 **RESUME HERE. NinjaTrader is DOWN and there is no risk guard running.**
> Nothing is in flight, everything is committed, and a laptop restart is safe and expected.
>
> **State as of 2026-08-07, end of session 7**
>
> | | |
> |---|---|
> | NT8 | **Not running.** Clean `Session End` at 12:14:43 ET — not a crash, not this branch |
> | Restart attempt | Failed at login: `Too many incorrect login attempts. Please wait.` (`penaltyTime='40' captcha='True'`) |
> | Repo | Clean. `441c11e2` on `harden/riskguard-copier-p0`. Suite 499/0 |
> | NT8 `bin/Custom/AddOns` | **Deliberately parked one commit behind, at `3de5947f`** |
> | Guard | Not running. Was `shadow` + armed before shutdown |
>
> **Why the NT8 tree is parked.** `P1-22` is committed but has **never been compiled against
> net48** — the `nt_compile` landed on an already-shutting-down NT8. An unverified file in
> `bin/Custom/AddOns/` makes **every** AddOn fail to compile on startup, RiskGuard included, on a
> box with funded accounts. So `TradeCopierEngine.cs` and `RiskGuardAddOnTests.cs` there are
> pinned to `3de5947f`, the last build NT8 accepted with 0 errors. **`sync --verify` reporting
> drift on exactly those two files is correct, not a problem to fix.**
>
> ### Recovery runbook — do these in order, do not skip (2)
>
> **(1) Get NT8 running.** A laptop restart is the expected fix; the login penalty is time-based
> and clears on its own. Do not retry the login repeatedly — that is what caused the lockout.
>
> **(2) Confirm the restart cleared `P0-48`.** A full NT8 process restart is the *only* thing that
> can detach the 57 orphaned copier handlers. Census — expect `McpBridgeAddOn` to read **1**, not
> 57 (and `TradeCopierEngine` 1, `RiskGuardAddOn` 1):
> ```bash
> TOKEN=$(cat "$HOME/Documents/NinjaTrader 8/mcp_token.txt" | tr -d '\r\n')
> python -c "
> import json
> ops=[{'op':'getStatic','type':'NinjaTrader.Cbi.Account','member':'All'},
>      {'op':'invoke','target':{'result':0},'method':'get_Item','args':[{'type':'System.Int32','value':2}]},
>      {'op':'getProp','target':{'result':1},'member':'ExecutionUpdate'},
>      {'op':'invoke','target':{'result':2},'method':'GetInvocationList','args':[]}]
> for i in range(80):
>     b=len(ops)
>     ops.append({'op':'invoke','target':{'result':3},'method':'GetValue','args':[{'type':'System.Int32','value':i}]})
>     ops.append({'op':'getProp','target':{'result':b},'member':'Target'})
> print(json.dumps({'ops':ops}))" > /tmp/census.json
> curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
>   http://localhost:7890/api/dev/reflect -d @/tmp/census.json | python -c "
> import json,sys,collections
> d=json.load(sys.stdin)['results']; c=collections.Counter()
> for i in range(4,len(d)-1,2):
>     t=d[i+1].get('type')
>     if t: c[t.split('.')[-1]]+=1
> [print(' %-24s %d'%(k,v)) for k,v in c.most_common()]"
> ```
> Index `2` is `Sim101` in `Account.All`; the loop over-runs the real length and the parser skips
> the resulting error entries. **Until this reads 1, do not trade the copier** — each orphan copies
> every Sim101 fill independently, and both relationships are enabled with `Sim101 → Sim-ORB` at
> `ArmedForLive: true`.
>
> **(3) Deploy `P1-22` and prove the net48 build.**
> ```powershell
> .\.venv\Scripts\python.exe scripts\utils\sync_nt8_strategies.py --verify --only addons  # expect the 2 known drifts
> .\.venv\Scripts\python.exe scripts\utils\sync_nt8_strategies.py --only addons
> # then nt_compile -- REQUIRE errorCount 0. If it fails, P1-22 is the only suspect:
> #   git show 3de5947f:scripts/ninjatrader/addons/TradeCopierEngine.cs > "<NT8>/AddOns/TradeCopierEngine.cs"
> #   (same for RiskGuardAddOnTests.cs) to get straight back to a compiling tree.
> ```
>
> **(4) Confirm the guard is actually guarding.** It self-arms in shadow since `P1-47`, but verify
> rather than assume:
> ```bash
> curl -s -H "Authorization: Bearer $TOKEN" http://localhost:7890/api/riskguard/version
> # want: "mode":"shadow","isArmed":true,"guarding":true
> ```
> Also confirm the new code is the loaded code — `Version` is still `1.1.0` and proves nothing.
> Look for `MaxSlippageTicks` in `GET /api/riskguard/config`'s copier section, or
> `MaxAutoStopAttempts`, neither of which exists at the merge-base.

---

## 0. Start here (read this, then §4a for the roadmap)

**32 of 48 defects closed. Suite 499/0.** NT8 compiled clean as of `3de5947f`; `P1-22` is
unverified against net48 (NT8 is down — see the banner).

| Phase | State |
|---|---|
| **A** — deploy P0 to shadow | Deployed and armed. **T3 validated live (§4g). T5 has never been exercised** — it needs an acting mode |
| **B** — test foundation | ✅ done |
| **C** — P1 safety-critical | ✅ done except `P1-36` |
| **D** — P1 rule semantics | ✅ done — `P1-16`, `P1-17`, `P1-18`, `P1-19` |
| **D2** — stress backlog | `S1`–`S4` landed and closed four defects; **`S5`–`S9` open** |
| **E** — copier fidelity | `P1-23`, `P1-21`, `P1-22` closed; `P1-21` exposed **`P0-48`**. **`P0-9`'s real half** is all that remains |
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
- **`POST /api/riskguard/config` does not merge (`P2-41`, open).** Every field a partial POST omits
  returns as its default and is written to disk, while the response echoes your *request* and says
  `"applied"`. Always GET the full document, mutate one key, POST it back, then GET again and
  **diff every key**. That discipline is the only reason `P1-39` was found.

**5. `P0-9`'s real half is the largest remaining live exposure.** Followers still receive bare
market orders with **no protective legs**. Everything else in the copier is secondary to this.

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

### Phase D2 — stress backlog: S5–S9 (OPEN, not optional)

`S1`–`S4` landed 2026-08-07 and closed four defects on their first run (`P1-43`, `P1-44`,
`P1-45`, `P2-46`). **`S5`–`S9` remain open**, and they are the only planned coverage for failure
modes no unit test reaches. Full specs in the plan's §8.

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

### Phase E — copier fidelity — `P1-21`, `P1-22`, `P1-23` all closed; only `P0-9` remains

**`P0-9`'s real half is the next piece of work, and the largest remaining live exposure.** Only its
fail-closed *precondition* landed in T5 — followers still receive bare market orders with no
protective legs. Their sole protection today is RiskGuard's `StopAttachSeconds` grace →
`RiskGuardAutoStop` at a fixed tick offset from *average price*, which bears no relation to the
leader's actual stop; and if RiskGuard is disarmed, in shadow, or the follower is excluded, there
is no stop at all.

Read the plan's `P0-9` for the three options in preference order. Two things this session
established that bear on it directly:

- **`P1-22` built the machinery `P0-9` needs.** `_pendingCopies` already links a follower order to
  the leader execution that caused it, keyed by `Order` reference. Bracket replication needs the
  same join, so extend that map rather than adding a second one — and keep the reference keying
  (`OrderId` is neither unique nor stable; see `P1-22`).
- **`S7` runs *with* this work, not after it** (plan §8). Copier fan-out under burst is the only
  planned coverage for the ordering failures bracket replication can introduce.

Sequence it as: `S7` red first → `P0-9` → `S7` green.

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
