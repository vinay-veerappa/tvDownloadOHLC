# Bot fix backlog

> **Scope**: defects and divergences in the **C# bots**, tracked separately from
> the workflow so that finalising the workflow is not blocked on fixing twelve
> strategies. The workflow procedure itself is
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

## B1 — `BBMRReversionBot` allows 99 trades/day; Python allows 3 🔴 highest value

| | |
|---|---|
| **Bot** | `scripts/ninjatrader/strategies/bandits_8020/BBMRReversionBot.cs` |
| **Registry key** | `mean_reversion` |
| **Found by** | `test_bot_defaults.py`, cross-reading the bot against `sessions.yaml` |

`MaxTradesPerDay = 99` in the bot; the Python engine that predicts it enforces 3.
**The pair cannot be compared at the trade-set layer** — the C# side can take
trades the Python side structurally cannot, so any recall figure is meaningless
and would read as a Python defect.

*Decide which is right before editing either.* The frozen document no longer
imposes a cap at all (`risk.analysisDerived`), and
`reporting/trade_ordinal.py` now reports EV_R by trade ordinal so the number can
be read off the data. Run that report first; the answer it gives is the value
both sides should carry.

`FlattenBy` was **1615**, past ADR-020's 16:00 hard exit — already fixed
2026-09-05 (`71536a51`). `LatestEntry = 1600` is deliberate (NY_PM strategy) and
is **not** a defect: an entry may happen at any time (§1.3).

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

## B4 — `IBFadeBot` / `IBStrategyBase` disagree with each other 🟡

| | |
|---|---|
| **Bots** | `ib_breakout/IBFadeBot.cs` (1555 / 2 / 1555), `ib_breakout/IBStrategyBase.cs` (1550 / 2 / 1430) |
| **Registry key** | `ib_pullback` → three bots (`IBRetestBot`, `IBBreakoutBot`, `IBFadeBot`) |
| **Found by** | `test_bot_defaults.py` |

The **base class and its subclass carry different flatten times**, so which one
applies depends on construction order — a question no report answers today.
`IBFadeBot` also has `LatestEntry == FlattenBy == 1555`.

One registry key maps to three bots (§1.2), which means "the Python prediction
for `ib_pullback`" does not identify a bot. That mapping needs settling as part
of this ticket, not after.

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

## B6 — `Bandits8020Bot` and `EMAPullbackBot`: minor 🟢

| | |
|---|---|
| **Bots** | `bandits_8020/Bandits8020Bot.cs` (1555 / 3 / 1100), `ema_pullback/EMAPullbackBot.cs` (1545 / 3 / 1530) |

`EMAPullbackBot` differs from the frozen defaults only in `LatestEntry`, which is
no longer a frozen field — it may simply lose its inventory line once B1–B5 have
settled what a normalised bot looks like. `Bandits8020Bot`'s `LatestEntry = 1100`
is a deliberate morning-only window.

**Do these last.** They are the least informative, and doing them first would
mean deciding the convention on the cases that matter least.

---

## B7 — no bot emits a unique entry signal name 🔴 blocks all attribution

| | |
|---|---|
| **Bots** | all twelve |
| **Found by** | building the decision-log join (STRATEGY_WORKFLOW.md §5.5) |

`entryName` — `Execution.Name` on the entry fill — is the **join key** from an NT8 fill to
the strategy's own decision log. A bot that names every entry `"long"` makes all its entries
indistinguishable downstream, and the reporting falls back to a nearest-entry-time join that
is approximate **by construction**: a decision is a *bar* time and a fill can be the next
bar's open.

Give each entry a unique name — `<tag>_<L|S>_<counter>` — and pass the same string to
`DecisionBuilder.Entry(signalName)`. **Audit before editing**: some bots may already do this.

⚠️ The exit-reason tally depends on exit order names; do not rename exits while doing this,
or `exitName` grouping changes silently and every historical comparison shifts.

---

## B8 — no bot writes a decision log 🔴 every roster diff is one-sided

| | |
|---|---|
| **Bots** | all twelve |
| **Shared class** | `scripts/ninjatrader/shared/DecisionLog.cs` — **generated and committed, called by nothing** |

Until a bot calls it, `compare_rosters` has a Python roster and an empty NT8 one, so the
cheapest parity check in the workflow (§5.5) cannot run in the direction that matters —
*which criteria does the bot evaluate that the hunter does not*.

Per bot: construct in `State.DataLoaded`, `Print(log.Banner())` once, `Skip()` on a bar with
no setup, `Decision(...).Gate(...).Entry(name)` / `.Reject()` at the decision, `Dispose()` in
`OnTermination`. **Add every gate the bot already has**, including the ones behind a
`Use*Gate` bool — a disabled gate that still gets recorded as passing is how you find out the
flag was off.

⚠️ **Read rules 2 and 6 in §5.5 before writing the calls.** `&&` short-circuits, so the gates
must be evaluated deliberately rather than lifted out of the existing `if`; and a magnitude
recorded as a `Gate` instead of a `Measure` has a structural 0% failure rate.

**Start with `BBMRReversionBot`** — it is the bot in the pair that motivated all of this, and
it already writes a per-bar dump (`%TEMP%/bbmr_diag_<guid>.csv`) whose 22 columns name most
of the gates. **Delete that dump in the same edit**: it goes to a GUID path printed only to
the output window, which is data that exists and cannot be addressed.

⚠️ Needs a recompile. **Do not deploy** — say so and stop.

---

## B9 — a forked `RiskManagerBase` with unlanded work 🔴 **needs a decision, not a fix**

| | |
|---|---|
| **Canonical** | `nt8-riskguard` → `strategies/Vinay/RiskManagerBase.cs` (ADR-025 owner) |
| **Fork** | `docs/strategies/ninjatrader/risk_manager_suite/RiskManagerBase.cs` (this repo, tracked) |
| **Found by** | tracing what `GovernedStrategy` inherits (§5.7) |
| **Gate** | `tests/test_base_class_ownership.py` — shrink-only on fork-only lines |

Two copies exist. **The canonical one and the DEPLOYED one are byte-identical**, so
the live bots run canonical — and the fork carries **three improvements that have
never shipped**:

1. a configurable `SecondaryTimeframeMinutes` (default 15) replacing a hardcoded
   `AddDataSeries(BarsPeriodType.Minute, 5)`
2. `ConfigureStrategy()` called **before** `AddDataSeries` rather than after —
   which is what lets a subclass influence which series is added, and is a
   prerequisite for (1)
3. a breakeven trigger that also fires on the bar's high/low (`Highs[0][0] >= …`)
   and checks whether the queen leg actually filled, instead of testing the close
   alone

**This is a decision, not a defect.** All three change live bot behaviour, so
whose version wins is not mine to choose. What is *not* in question is that two
copies must not both exist: the fork sits outside all three directories
`sync_nt8_strategies.py` scans, so `--verify` reports `0 orphan(s)` and never
compares it to anything — a second source of truth with a lower profile.

⚠️ **Do not "fix" this by syncing either direction blind.** A drift report does not
say which side is stale, and here the answer differs per hunk: the fork is *ahead*
on those three changes and *behind* on the two hooks added upstream 2026-09-05
(nine `return false;` now routed through `Blocked`, `GetSignalName` now virtual).

**Suggested resolution**: land (1)–(3) in `nt8-riskguard` through its own suite and
mutation batteries, bump the bridge's pin, then delete the fork and let the
allowlisted vendored copy be the only one. Each of the three wants its own commit —
(3) changes when a stop moves on a live position.

---

## Not a bot defect, recorded here so it is not re-filed

- **`FailedAuctionBot` and `VWAPReclaimBot` already match** the frozen defaults
  (1545 / 3 / 1430). They were in my first hand-written inventory and the gate
  removed them — the inventory working, not a gap.
- **`ICTFVGCISDBot`** (1555 / 3 / 1530) is the only bot with a parameter document
  (§3.3), so its numbers should come from that document rather than from a
  normalisation pass. Ticket it with the parameter-document work, not here.

---

## The loop prompt

Paste this with `<TICKET>` replaced by one ID above. It deliberately asks for the
measurement *before* the edit, because the decision of what the value should be
is not obvious from the bot alone.

```text
Work ticket <TICKET> from docs/architecture/BOT_FIX_BACKLOG.md.

Read docs/architecture/STRATEGY_WORKFLOW.md first -- it is the canonical
procedure and section 1.3 defines which execution defaults are frozen,
overridable, or analysis-derived.

1. MEASURE BEFORE EDITING. Run the Python side and read the trade-ordinal
   report, which is what decides a trade cap:
     .\.venv\Scripts\python.exe -m scripts.trading_framework.workflow `
        --strategy <key> --ticker NQ1 --price-adjustment unadjusted
   Record the run id, the promotion checklist, and the suggested cap WITH its
   sample size. If the sample is below 20, say so and do not set a cap from it.

2. STATE what the value should be and why, before changing anything. If the bot
   and the Python side disagree, name which one you are changing and what
   evidence says it is the wrong one. NT8 is authoritative for behaviour, so the
   presumption is that Python is wrong -- but a bot that structurally cannot be
   predicted is a bot defect.

3. EDIT the bot. Prefer TradingDefaults.<Field> over a literal. Never exceed
   TradingDefaults.RthHardExit; that one is a safety limit (ADR-020).

4. REMOVE the bot's line from
   scripts/trading_framework/tests/known_bot_divergences.py if it now matches,
   or update the recorded tuple if it moved but still differs. The test refuses
   a stale entry, so this is not optional.

5. RE-RUN the workflow and diff the two promotion checklists. Report what
   changed and why. A changed backtest is expected; an UNEXPLAINED change is the
   failure.

6. Run .\.venv\Scripts\python.exe tools\ci_local.py and paste the summary.

Do not deploy to NT8 and do not recompile: a recompile wipes every static
singleton in a live instance, and whether that is acceptable is the user's call.
Stop and say so if the ticket appears to need it.
```
