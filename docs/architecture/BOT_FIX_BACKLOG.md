# Bot fix backlog

> **Scope**: defects and divergences in the **C# bots**, tracked separately from
> the workflow so that finalising the workflow is not blocked on fixing fourteen
> bots (the count is `tests/uninstrumented.py`; do not restate it). The workflow
> procedure itself is
> [STRATEGY_WORKFLOW.md](STRATEGY_WORKFLOW.md); this file is a *worklist*, not a
> second procedure, and it must never grow a rule of its own.
>
> **Created 2026-09-05.** Every entry below was found by measurement, and each
> names how it was found so it can be re-derived rather than believed.

## How to work this list

Each ticket is written to be handed to an agent one at a time, in a loop. The
prompt template is at the bottom. Three rules, because they are what makes the
result trustworthy:

1. **One bot per run.** Each normalisation changes which trades exist. Ten at
   once means you cannot attribute a change to a cause.
2. **Every fix lands through a recorded run** —
   `python -m scripts.trading_framework.workflow --strategy <key> --ticker NQ1
   --price-adjustment unadjusted` before and after, both run records kept. The
   diff in the promotion checklist *is* the evidence.
3. **Results are expected to change.** These numbers were never agreed with the
   Python side that predicts them, so a changed backtest is the point, not a
   regression. What must not change silently is *which* numbers and *why*.

`scripts/trading_framework/tests/known_bot_divergences.py` is the machine-readable
half of this file. When a ticket closes, its line is **removed** there — the test
`test_the_inventory_has_no_stale_entries` fails if a bot now agrees and still has
a line, so the two cannot drift apart.

---

## B1 — `BBMRReversionBot` allows 99 trades/day; Python now caps at nothing 🔴 highest value

| | |
|---|---|
| **Bot** | `scripts/ninjatrader/strategies/bandits_8020/BBMRReversionBot.cs` |
| **Registry key** | `mean_reversion` |
| **Found by** | `test_bot_defaults.py`, cross-reading the bot against `sessions.yaml` |

`MaxTradesPerDay = 99` in the bot. **This ticket's original text said the Python
engine enforces 3, and that stopped being true on 2026-09-05** — `build_engine`
now takes the cap from the frozen document, which sets it to `null`, so the
engine runs UNCAPPED and `sessions.yaml`'s 3 is recorded beside it as the
disagreement rather than applied. Re-measured 2026-09-05:

| | cap |
|---|---|
| `BBMRReversionBot` | 99 |
| the Python engine, before | 3 (from `sessions.yaml`) |
| the Python engine, now | **none** — `risk.maxTradesPerDay: null` |
| `sessions.yaml`, still | 3, recorded but not applied |

So the direction of the divergence has flipped, and the ticket is now *cheaper*,
not harder: the two sides are 99-vs-uncapped rather than 99-vs-3, and the
question is only whether 99 should be a number at all. **The pair still cannot be
compared at the trade-set layer** until it is settled — one side having a cap the
other does not means any recall figure reads as a Python defect.

*Decide which is right before editing either.* `reporting/trade_ordinal.py`
reports EV_R by trade ordinal so the number can be read off the data. Run that
report first; the answer it gives is the value both sides should carry, and if
its sample is under 20 it will refuse rather than suggest one.

`FlattenBy` in the repo is **1600**, fixed 2026-09-05 (`71536a51`) from 1615,
which was past ADR-020's hard exit. ⚠️ **The DEPLOYED copy is still 1615** —
found 2026-09-05 by `workflow.py::_deployment_state`, recorded as
STRATEGY_WORKFLOW.md §11 item 20. So an NT8 capture taken from the current
install is evidence about a bot that violates ADR-020, and this ticket is not
finished by the repo edit alone. Do not deploy to close it; that is the user's
call.

`LatestEntry = 1600` is deliberate (NY_PM strategy) and is **not** a defect: an
entry may happen at any time (§1.3).

---

## B2 — `STTrendBot` allows 99 trades/day 🟡

| | |
|---|---|
| **Bot** | `scripts/ninjatrader/strategies/supertrend/STTrendBot.cs` |
| **Registry key** | none — **no Python counterpart exists** |
| **Found by** | `test_bot_defaults.py` |

`MaxTradesPerDay = 99`, `LatestEntry = 1555`, `FlattenBy = 1555` — entry and
flatten in the same minute, which means the last entry of the day cannot be a
trade. Worth checking whether it ever fires.

Has no registry key, so **it is a research artifact and not a strategy** (§1.2)
and must not be reported as one. Either give it a hunter or retire it.

---

## B3 — the_strat pair allows 6 trades/day 🟡

| | |
|---|---|
| **Bots** | `the_strat/Strat212ContinuationBot.cs`, `the_strat/Strat22RevStratBot.cs` |
| **Found by** | `test_bot_defaults.py` |

Both `MaxTradesPerDay = 6`, `FlattenBy = 1555`, `LatestEntry = 1530`. These two
share `StratCore.cs` with the Python `the_strat` library and are the **only pair
with Layer-1 rule parity built** (§6.1), so they are the cheapest place to prove
that a normalisation does not break rule parity.

⚠️ Blocked on the open `WickType` range guard decision (§11 item 2): C# suppresses
sub-tick bars, Python classifies them. Fixing the caps without settling that
means re-running this twice.

---

## B4 — `IBFadeBot` / `IBStrategyBase` disagree with each other 🟡 *(flatten disagreement closed 2026-09-05; migration blocked on a design decision)*

| | |
|---|---|
| **Bots** | `ib_breakout/IBFadeBot.cs` (1555 / 2 / 1555), `ib_breakout/IBStrategyBase.cs` (now 1545 / 2 / 1430) |
| **Registry key** | `ib_pullback` → three bots (`IBRetestBot`, `IBBreakoutBot`, `IBFadeBot`) |
| **Found by** | `test_bot_defaults.py` |

✅ **The flatten disagreement is CLOSED (2026-09-05).** The base carried 1550
while its subclass carried 1555 — which one applied depended on construction
order. The base now carries the **frozen 1545** (`IBRetestBot`/`IBBreakoutBot`
inherit it and match), and only `IBFadeBot`'s 1555 remains — a deliberate
PM-window override, recorded as the divergence. `IBStrategyBase` left
`known_bot_divergences.py`.

⚠️ **Migrating the IB chain onto `GovernedStrategy` is BLOCKED on a design
decision, not a value.** `GovernedStrategy` SEALS `CheckForSignal()` and
computes the verdict from declared gates — but `IntradayStrategyBase`
(nt8-riskguard) has a concrete `CheckForSignal()` that drives the whole
range/filter machine and **enters inside** it (`EnterWithRangeStop` /
`EnterWithPackTradingBrackets`, custom qty and pack-bracket legs), returning 0
so the base does not double-enter. `SetupEvaluation` exposes nothing that can
place an order, so the enter-inside pattern cannot live under the seal.
Migrating means either (a) re-plumbing the entire IB entry path through
`RiskManagerBase.EnterTrade` + the custom-target hooks, or (b) relaxing the
seal for this one chain — (b) defeats the guarantee. Four bots are affected
(`IBStrategyBase`, `IBRetestBot`, `IBBreakoutBot`, `IBFadeBot`); the decision
is the user's, and the four remain on `uninstrumented.py` until it is made.

One registry key maps to three bots (§1.2), which means "the Python prediction
for `ib_pullback`" does not identify a bot. That mapping still needs settling.

---

## B5 — `KeltnerChannelBot` sits exactly on the ADR-020 limit 🟡

| | |
|---|---|
| **Bot** | `scripts/ninjatrader/strategies/keltner_channel/KeltnerChannelBot.cs` |
| **Registry key** | none |
| **Found by** | `test_bot_defaults.py` |

`FlattenBy = 1600` — exactly the hard exit, so it passes the gate, but any
slippage on the closing order puts the fill past it. `MaxTradesPerDay = 4`.
No registry key: research artifact, same as B2.

---

## B6 — `Bandits8020Bot`: minor 🟢  *(the `EMAPullbackBot` half is closed)*

| | |
|---|---|
| **Bot** | `bandits_8020/Bandits8020Bot.cs` (1555 / 3 / 1100) |

`Bandits8020Bot`'s `LatestEntry = 1100` is a deliberate morning-only window.

✅ **`EMAPullbackBot` (1545 / 3 / 1530) already left the inventory on 2026-09-05.**
It differed from the frozen defaults only in `LatestEntry`, which stopped being a
frozen field when entries became unrestricted, so the shrink-only inventory
dropped its line and `known_bot_divergences.py` records why. This ticket
described that as still pending until 2026-09-05 — the inventory is the machine
half and it had moved on; **read it rather than this paragraph** if the two ever
disagree again.

**Do these last.** They are the least informative, and doing them first would
mean deciding the convention on the cases that matter least.

---

## B7+B8 — migrate every bot onto `GovernedStrategy` 🔴 one edit, not two

| | |
|---|---|
| **Bots** | all fourteen (frozen in `tests/uninstrumented.py`, shrink-only) |
| **Base** | `scripts/ninjatrader/shared/GovernedStrategy.cs` (STRATEGY_WORKFLOW.md §3.4) |

**These were two tickets and are now one, because one edit closes both.** B7 was
"emit a unique entry signal name" and B8 was "call the decision log" — both were
written as per-bot recipes before the base class existed, and both are now
supplied by inheriting it. Keeping them separate would have had an agent
hand-write machinery that already exists.

Per bot the migration is: change the base to `GovernedStrategy`, move the signal
logic from `CheckForSignal()` into `OnEvaluate(SetupEvaluation e)`, and move
`SetStrategyDefaults()` overrides into `OnStrategyDefaults()`. Everything else
follows — the log, the frozen defaults, the unique per-entry name, and the
recording of the framework's own refusals.

**Declare every gate the bot already has**, including the ones behind a `Use*Gate`
bool: a disabled gate that is still *recorded* as passing is how you discover the
flag was off. ⚠️ Read §5.5 rules 2 and 6 before writing the calls — `&&`
short-circuits, so the conditions must be lifted out of the existing `if` chain
deliberately rather than copied, and a magnitude belongs in `Measure` not `Gate`.

**Start with `BBMRReversionBot`**: it is the bot in the pair that motivated all of
this, and its existing per-bar dump (`%TEMP%/bbmr_diag_<guid>.csv`) already names
most of its gates in 22 columns. **Delete that dump in the same edit** — a GUID
path printed only to the NT8 output window is data that exists and cannot be
addressed.

⚠️ Do not rename **exit** order names while doing this. The exit-reason tally
groups on them, and a rename shifts every historical comparison silently.

⚠️ Needs a recompile. **Do not deploy** — say so and stop.

---

## B9 — a strategy concern living in the risk manager ✅ DONE 2026-09-05 *(riskguard v1.69.0)*

| | |
|---|---|
| **Owner** | `nt8-riskguard` → `strategies/Vinay/RiskManagerBase.cs` (ADR-025) |
| **Found by** | tracing what `GovernedStrategy` inherits, then counting who uses it |
| **Fork** | **deleted from this repo 2026-09-05**; the folder now holds a pointer |

### The measurement that settles it

`AddSecondaryTimeframe` is a property of `RiskManagerBase`. **Eleven bots set it
and nine of them set it to `false`** (re-counted 2026-09-05 —
`grep -rn AddSecondaryTimeframe scripts/ninjatrader/strategies/`; the first
version of this table said eight of ten and had dropped `VWAPReclaimBot`):

| Sets it `true` (2) | Sets it `false` (9) |
|---|---|
| `BBMRReversionBot`, `ICTFVGCISDBot` | `Bandits8020Bot`, `EMAPullbackBot`, `FailedAuctionBot`, `IBFadeBot`, `IBStrategyBase`, `STTrendBot`, `Strat212ContinuationBot`, `Strat22RevStratBot`, `VWAPReclaimBot` |

⚠️ `IBStrategyBase.cs:303` carries a *comment* reading
`AddSecondaryTimeframe=true` immediately above the line that sets it `false`.
A regex over these files will mis-count it; count the assignments.

A feature in a base class that **most of its users must switch off** is in the
wrong layer. And it is not one property — it leaks into the base in seven places:
the `AddDataSeries` call, `atrIndicator` construction, the `BarsInProgress` guard,
the `CurrentBars[1]` warm-up check, `GetCurrentATR()`, and the three
`Close5m`/`High5m`/`Low5m` helpers that **throw** when the flag is false.

### Why it ended up there

`AddDataSeries` may only be called during `State.Configure`, and
`RiskManagerBase` owns `OnStateChange`. So the base owned the only place a data
series could be added, and the answer was to put the knob in the base rather than
to give the strategy a hook that runs at the right moment.

**The real coupling is worse than the knob.** `GetCurrentATR()` lives in the base
and reads the *secondary* series, and ATR drives stop distance and position size.
So a **timeframe** choice became load-bearing for a **risk** calculation: turning
the flag off changes risk behaviour, and the base's own doc comment says
"subclasses MUST override" `GetCurrentATR()` when it is false. That is the
dependency to break, and it runs risk → ATR → data series.

### The fix

`ConfigureStrategy()` is **already** called during `State.Configure`, so a
strategy can call `AddDataSeries` itself today. The knob is pure redundancy.

1. Delete `AddSecondaryTimeframe`, `SecondaryTimeframeMinutes`, the
   `AddDataSeries` call, and the `Close5m`/`High5m`/`Low5m` helpers from the base.
2. Move `AddDataSeries` into each strategy's own `ConfigureStrategy()` — two
   strategies need it.
3. Make ATR a **strategy-supplied input** to the risk layer rather than something
   the risk layer computes from a series it chose. That removes the last reason
   the base needs to know about bars at all.

⚠️ Step 3 changes stop distances and position sizes, so it changes live behaviour.
One commit each, through nt8-riskguard's own suite and mutation batteries.

**WHAT SHIPPED (2026-09-05, riskguard v1.69.0):** all three steps landed in one
commit, because the consumers were measured first and the census made them one
edit: `AddSecondaryTimeframe`/`SecondaryTimeframeMinutes`/`Close5m`/`High5m`/
`Low5m`/`atrIndicator` deleted from the base; `ConfigureStrategy()` now runs
BEFORE any series (fork change #2 — the extension point); the base's
`GetCurrentATR()` falls back to the primary bar's range and every bot with a
real risk metric already overrides it (BBMR, ICT, and `IntradayStrategyBase`
were the only series-readers; each now owns its own). The two bots that had the
series (BBMR, ICT) add it in their own `ConfigureStrategy()` — which is also
the NT8-recommended "program the granular resolution directly into your
strategy" path, and what lets `OrderFillResolution=High` apply to a
multi-series strategy in the Strategy Analyzer (the platform refuses High on
strategies whose series come from the framework). The nine bots that set the
knob false simply lost the line. **Fork change #3 also landed**: breakeven
fires on the bar TOUCHING the queen/TP1 level (High/Low), not the close alone,
in both `ManageCoverTheQueen` and `ManageFixedTP1TP2` (a captured
`customTp1Price` field); gated by `tools/check_intrabar_breakeven.py` with
selftest negative controls.

### The three changes the deleted fork carried

Recorded so nothing is lost (git history has the file). Each needs a decision,
and they are **not** all improvements:

| # | Change | Outcome |
|---|---|---|
| 1 | `SecondaryTimeframeMinutes` (int, default 15) replacing the hardcoded `AddDataSeries(Minute, 5)` | **Not landed** — it would have widened the layering violation. The call moved to the strategy instead |
| 2 | `ConfigureStrategy()` moved **before** the `AddDataSeries` block | **LANDED** — the extension point that lets a subclass add its own series |
| 3 | Breakeven fires on `queenFilled` (position reduced to 1) **or** the bar's high/low touching `entry ± queenPts`, instead of the close alone | **LANDED 2026-09-05**, with `tools/check_intrabar_breakeven.py` (selftest has negative controls). The close-only check missed an intrabar touch, so the runner's stop stayed at risk through a bar that reached the target. It moves a stop on a live position — the most consequential change of the three |

Everything else in that fork's diff was it being **stale**, not ahead: nine
`return false;` that upstream now routes through `Blocked`, and a `GetSignalName`
still `private` there.

---

## Not a bot defect, recorded here so it is not re-filed

- **`FailedAuctionBot` and `VWAPReclaimBot` already match** the frozen defaults
  (1545 / 3 / 1430). They were in my first hand-written inventory and the gate
  removed them — the inventory working, not a gap.
- **`ICTFVGCISDBot`** (1555 / 3 / 1530) is the only bot with a parameter document
  (§3.3), so its numbers should come from that document rather than from a
  normalisation pass. Ticket it with the parameter-document work, not here.

---

## B10 — the queen leg must honour the strategy's DECLARED target ✅ DONE 2026-09-05

| | |
|---|---|
| **Bots** | BBMRReversionBot, EMAPullbackBot, FailedAuctionBot, VWAPReclaimBot, ICTFVGCISDBot (the CoverTheQueen/FixedTP1TP2 five with a declaring Python twin) |
| **Owner** | `nt8-riskguard` → `strategies/Vinay/RiskManagerBase.cs` (the bracket) + this repo (`GovernedStrategy` the declaration) |
| **Found by** | the Python close of section 11 item 19 (option A, user-ratified): the sanctioned engine now exits the queen leg at the hunter's declared `target1_price`, so bot parity carried a NAMED divergence until the bots learned it |

**What shipped.** `SetupEvaluation.DeclareTarget(price)` -- the same
declare-don't-act shape as Trigger/Gate/Measure. `GovernedStrategy.CheckForSignal`
(sealed, unchanged) reads the declaration, logs it either way
(`declared_queen_target` used / `queen_bps_fallback` with the reason -- a
refusal that is silent is the same defect class as one that never happened),
and hands the raw declaration to the risk base through a new virtual hook
`GetDeclaredQueenTarget(signal, entryPrice)`, captured at arm time exactly
like `GetCustomLimitPrice`. `RiskManagerBase.EnterTrade`'s CoverTheQueen path
applies the FILL-TIME guard against the EFFECTIVE entry (which may be a limit
price, not the close the note was recorded against) and falls back to the
frozen queen_bps on NaN / absent / wrong-side. The runner leg is UNCHANGED at
runner_bps and the BE lock does not move: ADR-023 Cover-The-Queen is frozen.

**Declarations, one per bot's Python twin**: BBMR -> the Bollinger mid;
EMAPullback / FailedAuction / VWAPReclaim -> entry +/- (stop distance) x the
twin's `tp_r_mult` (1.8 / 2.0 / 1.8, as a `QueenTargetRMult` parameter, not a
literal); ICTFVGCISD -> 1R of its effective stop on all three paths (MTF
confirm, single-TF, re-entry). Bots with no Python twin (KeltnerChannelBot,
STTrendBot, Bandits8020Bot, the Strat pair -- FixedTP1TP2 already carries its
own TP1) declare nothing, which behaves exactly like the bps fallback, logged.

** queenBps / runnerBps moved into `trading_defaults.json` (execution block)
and are emitted as `TradingDefaults.QueenBps` / `RunnerBps` -- the 0.0010
literal in the risk base was a hand-set number nothing froze.**

**Verification.** riskguard gates 17/17 + suite 3595/0 at `v1.68.0`
(`1ebad82`); bridge pin bumped (`5093041`); NT8 compile green. Behaviour
smoke on BBMRReversionBot: all 28 entries carry `declared_queen_target`
notes naming the Bollinger mid, and Leg1 exits match the declared value
(trade `..._L_00002_Leg1` exit 22029.00 vs logged `used: 22029.1`); runner
legs, quantities and the 16:00 clamp unchanged.

---

## The loop prompt

Paste this with `<TICKET>` replaced by one ID above. Two things it deliberately
asks for before any edit:

* **the measurement**, because what a value *should* be is not obvious from the bot
  alone; and
* **a first-principles read of the layer the change belongs in**, because this code
  evolved and the ticket text may name the wrong fix. B9 is the worked example: it
  was filed as "reconcile a forked base class" and the real finding was a strategy
  concern living in the risk manager, which no amount of reconciling addresses.
  B7 and B8 are the other kind — two tickets that collapsed into one edit once the
  base class existed, and working them separately would have hand-written
  machinery that was already there.

**Redundancy is in scope. Say so and remove it rather than working around it.**

```text
Work ticket <TICKET> from docs/architecture/BOT_FIX_BACKLOG.md.

Read docs/architecture/STRATEGY_WORKFLOW.md first -- it is the canonical
procedure. Section 1.3 defines which execution defaults are frozen,
overridable or analysis-derived; section 5.5 defines the decision log and its
six rules; section 3.4 defines GovernedStrategy and what it already supplies.

0. FIRST PRINCIPLES, BEFORE ANYTHING ELSE. Do not start from the ticket's
   proposed fix. Answer these and say so in your reply:
     * WHICH LAYER does this concern belong in? A strategy concern in the risk
       base, or a risk concern in a strategy, is the defect -- not the symptom
       the ticket describes. Ownership: nt8-riskguard owns RiskManagerBase,
       RiskGatekeeper and IntradayStrategyBase; this repo owns GovernedStrategy
       and the bots. ADR-025 is one artifact, one owner.
     * IS IT ALREADY SUPPLIED? GovernedStrategy already gives every bot the
       decision log, the frozen defaults, ADR-020's hard exit, unique entry
       names and the logging of framework refusals. If the ticket asks you to
       write any of those per bot, the ticket is stale -- say so and inherit
       instead.
     * WHAT IS REDUNDANT HERE? Count the readers of the value you are about to
       change. A knob most callers must switch off, a default restated in ten
       bots, or two tickets that are one edit, are all signals the design is
       wrong rather than the value.
     * WOULD THIS NEED A CHANGE TO RiskManagerBase? If yes, stop and justify
       it. Needing a base-class change per strategy means the extension point
       is missing or in the wrong place -- propose the extension point, do not
       add a strategy-specific branch to a shared class.

1. MEASURE BEFORE EDITING. Run the Python side and read the trade-ordinal
   report, which is what decides a trade cap:
     .\.venv\Scripts\python.exe -m scripts.trading_framework.workflow `
        --strategy <key> --ticker NQ1 --price-adjustment unadjusted
   Record the run id, the promotion checklist, and the suggested cap WITH its
   sample size. If the sample is below 20, say so and do not set a cap from it.
   Read the gate roster and the win/loss sections too: they say which criterion
   is actually costing money, which the ticket text cannot.

2. STATE what the value should be and why, before changing anything. If the bot
   and the Python side disagree, name which one you are changing and what
   evidence says it is the wrong one. NT8 is authoritative for behaviour, so the
   presumption is that Python is wrong -- but a bot that structurally cannot be
   predicted is a bot defect.

3. EDIT. Prefer inheriting GovernedStrategy over writing machinery, and
   TradingDefaults.<Field> over a literal. Never exceed
   TradingDefaults.RthHardExit; that one is a safety limit (ADR-020) and the
   base re-clamps it after your defaults run.

4. UPDATE THE INVENTORIES. They are shrink-only and the tests refuse a stale
   entry, so this is not optional:
     * scripts/trading_framework/tests/known_bot_divergences.py -- remove the
       bot's line if it now matches, or update the tuple if it moved.
     * scripts/trading_framework/tests/uninstrumented.py -- remove the bot from
       UNINSTRUMENTED_BOTS once it derives from GovernedStrategy.

5. RE-RUN the workflow and diff the two promotion checklists. Report what
   changed and why. A changed backtest is expected; an UNEXPLAINED change is the
   failure.

   WARNING: the BEFORE run must be one YOU took in step 1. A stored run record
   from before 2026-09-05 is not a valid baseline -- the execution policy
   changed that day (1 contract not 2, $0.62 not $1.40, 1 tick not 0, no entry
   cut-off rather than 09:45-15:30, lunch reported rather than filtered out,
   15:45 flatten, no daily trade cap), and the search now scores under the same
   engine as the report. Diffing across that boundary attributes the policy
   change to your edit.

6. Run .\.venv\Scripts\python.exe tools\ci_local.py and paste the summary.

If the work belongs in nt8-riskguard, do it THERE, run its suite the way CI does
(`dotnet build tests/RiskGuardTests.csproj` then
`dotnet run --project tests/RiskGuardTests.csproj --no-build`), and say that the
bridge pin needs bumping. Do not add a second copy of a file this repo does not
own -- that is exactly how B9 happened.

Do not deploy to NT8 and do not recompile: a recompile wipes every static
singleton in a live instance, and whether that is acceptable is the user's call.
Stop and say so if the ticket appears to need it.
```
