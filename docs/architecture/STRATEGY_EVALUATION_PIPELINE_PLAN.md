# Strategy Evaluation Pipeline — Implementation Plan

> **Status**: PROPOSED. Not started. No code changed as of 2026-09-04.
>
> **Design record and evidence**: [BACKTEST_PARITY_ARCHITECTURE.md](BACKTEST_PARITY_ARCHITECTURE.md)
> **Trap checklist (still valid)**: [NT8_PYTHON_PARITY_STANDARD.md](NT8_PYTHON_PARITY_STANDARD.md)
>
> **Goal**: evaluate hundreds of strategy variants quickly, and know that the numbers are
> right enough to decide on. Python is the screen, NT8 is the verifier, and every promotion
> is traceable.

---

## 0. Ordering Principle

Sequenced by **information per hour**, not by size.

```
Phase 0  Trustworthy measurement   ──┬──> Phase 1  Prove the screen
         (blocks everything)         │
                                     └──> Phase 2  Workflow enforcement
                                                   (highest leverage)
                                                        │
Phase 3  Data & fill correctness  <─────────────────────┤
Phase 4  Parity as a CI gate      <─────────────────────┤
Phase 5  Kill the port cost       <─────────────────────┤
Phase 6  Overfitting controls     <─────────────────────┘
Phase 7  Speed (parallel, optional)
```

**Phase 0 blocks everything** — nothing is measurable while ground truth moves.
**Phases 1 and 2 can run in parallel.**

**Do not start with**: collapsing the ~10 execution engines, the tick pipeline, or any
shared-core work. Each is downstream of a decision Phase 0–2 produces.

---

## Phase 0 — Make the measurement trustworthy

*Cheap. Days, not weeks. Everything downstream is uninterpretable without it.*

### 0.1 Freeze and echo the NT8 Strategy Analyzer configuration
**Repo**: `nt8-mcp-bridge`

#### 0.1a Reflection discovery pass — DONE 2026-09-04

`POST /api/backtest/inspect` added (`BacktestInspect()` + `DescribeObject()`): reflects over
`TabStrategyProperties`, `BarsPeriod`, `StrategyTemplate` and `SelectedTab`, returning name,
type, writability, nullability and — for enums — the legal member names. Deployed, compiled
0/0, returns 200.

**Result: the plan's object model was wrong.** `TabStrategyProperties` has only **14**
properties and holds none of the execution knobs. They are all on **`StrategyTemplate`**
(196 properties, a `StrategyBase`), every one writable:

| Knob | Type | Value as found | Legal values |
|---|---|---|---|
| `OrderFillResolution` | enum | **Standard** | `High`, `Standard` |
| `OrderFillResolutionType` | enum | Minute | Tick, Second, Minute, … |
| `OrderFillResolutionValue` | int | 1 | |
| `IsTickReplay` | bool | **False** | |
| `Slippage` | double | **0** | |
| `IncludeCommission` | bool | **False** | |
| `BacktestCommissionTemplate` | string | None | |
| `IsFillLimitOnTouch` | bool | False | |
| `Calculate` | enum | OnBarClose | OnBarClose, OnEachTick, OnPriceChange |
| `TradingHoursInstance` / `TradingHoursSerializable` | TradingHours / string | `<Use instrument settings>` | |
| `IsExitOnSessionCloseStrategy` / `ExitOnSessionCloseSeconds` | bool / int | True / 30 | |
| `BarsRequiredToTrade` | int | 20 | |
| `StopTargetHandling` | enum | PerEntryExecution | ByStrategyPosition, PerEntryExecution |
| `From` / `To` | **DateTime** | 2026-01-01 → 2026-09-03 | |
| `SetOrderQuantity` | enum | Strategy | DefaultQuantity, Strategy |
| `TimeInForce` | enum | Gtc | Day, Gtc, Ioc, Opg, Gtd |
| `ValidOrderFillResolutions` | **read-only** | — | consult, do not assume |

Four consequences:

1. **Every backtest through this bridge has run with `Slippage=0`, `IncludeCommission=False`,
   `OrderFillResolution=Standard`, `IsTickReplay=False`.** So NT8 has been optimistic on
   *execution cost* while Python was optimistic on *sequence* (§2.3). Two different
   optimisms in opposite dimensions explains directionless divergence better than either.
2. **`From`/`To` are plain `DateTime` properties on `StrategyTemplate`.** `SetSaDateRange`
   drives the Infragistics editors by hand under a comment saying "no config property
   exists" — it was looking on `TabStrategyProperties`. That mechanism can be retired.
3. **`ValidOrderFillResolutions` is read-only and present.** `High` is not legal for every
   bars period, so the profile must consult it rather than assume, or it earns a refusal it
   cannot explain.
4. **Merge policy and break-at-EOD are NOT here** — see 0.1b. `IsTradingHoursBreakLineVisible`
   is cosmetic; do not mistake it for break-at-EOD.

#### 0.1b Global Market Data settings — NOT reachable, no endpoint exists

Measured 2026-09-04, and this is where cause 4 (price scale) actually lives. NT8
**Settings → Market data** holds, as *global* state:

- **Global merge policy** = `Merge back adjusted` ← the back-adjustment control
- **Show Tick Replay** = unchecked ← likely gates whether `IsTickReplay` can take at all
- Adjust for splits (daily / intraday), adjust for dividends, get data from server
- Real-time: filter bad ticks, % off market (0.1), record live data as historical

The Strategy Analyzer takes **no** `MergePolicy` argument, so it inherits the global. **SA
backtests have therefore been running on back-adjusted data via a setting the bridge can
neither read nor set.**

What exists today: `MergePolicy` appears in exactly ONE place — `McpBridgeAddOn.cs:3683-3699`,
a **per-request** parameter on `ExportBars` defaulting to `DoNotMerge`, parsed with
`Enum.TryParse`. That is the one correct enum site in the file, and it is what Phase 3.1
(unadjusted per-contract export) should build on. There is no `/api/settings`,
`/api/options` or `/api/marketdata`; `Globals` is used only for paths and windows.

#### 0.1b (cont.) Settings discovery — DONE 2026-09-04, and the answer is `Globals.MarketDataOptions`

`POST /api/settings/inspect` added (`SettingsInspect()` + `ResolveNtType()`), two-stage:
no `type` lists candidate `*Options`/`*Settings`/`*Preferences` types across loaded
NinjaTrader assemblies (37 found); `{"type":"..."}` resolves one and describes its static
instances. Deployed, compiled 0/0.

The live instance is **`NinjaTrader.Core.Globals.MarketDataOptions`** →
`NinjaTrader.Core.MarketDataOptions`, **27 properties, all read/write**. Note
`MarketDataOptions` itself has NO static members — the instance hangs off `Globals`, so
looking at the type alone finds nothing.

Measured values on this box:

| Property | Value | Legal / note |
|---|---|---|
| **`GlobalMergePolicy`** | **`MergeBackAdjusted`** | `DoNotMerge`, `MergeBackAdjusted`, `MergeNonBackAdjusted`, `UseGlobalSettings`, `UseDefault` |
| **`IsTickReplayEnabled`** | **`False`** | the "Show Tick Replay" checkbox |
| `AdjustForSplitsOnDaily` / `…OnIntraday` | True / True | |
| `AdjustForDividends` | False | |
| `GetDataFromServer` | True | |
| `FilterBadTicks` / `FilterBadTicksPercent` | False / 0.1 | |
| `RecordForPlayback` / `SaveDataAsHistorical` | False / False | |

Two consequences:

1. **Cause 4 is confirmed at its source.** `GlobalMergePolicy = MergeBackAdjusted`, and SA
   takes no MergePolicy argument, so **every SA backtest to date has run on back-adjusted
   prices** — which is exactly the −412/−293/−292/−170/−4 pt monthly offset in standard doc
   §10, now traced to a single global nothing was reading.
2. **`IsTickReplayEnabled = False` is an ordering dependency for Phase 3.4.** Setting
   `StrategyTemplate.IsTickReplay = true` cannot work while the global is off. The global
   must be flipped first, and it is global — every chart on the box.

⚠️ **A global is not a per-run parameter.** Anything written here changes every chart,
strategy and export on the machine. It belongs in the profile as a *precondition that is
asserted and reported*; if the global disagrees with the profile, the run refuses. Do not
set it per backtest.

**Known rough edge**: the `filter` argument narrows candidate *type* names only, not
properties, so a full describe of a `Provider`-typed enum dumps ~100 member names per
property. Add property-level filtering before this is pleasant to use.

⚠️ **A global is not a per-run parameter.** Anything written here changes every chart,
strategy and export on the box, so it belongs in the profile as a *precondition that is
asserted and reported*, not silently set per backtest. If the global disagrees with the
profile, the run should refuse.

#### 0.1c Fix the two enum drop sites — BLOCKS the profile

Every knob in 0.1a worth setting is an enum set **by name**, and both setters silently drop
string enum names:

| Site | Mechanism |
|---|---|
| `SetP()` (~1559) | `Enum.ToObject(t, Convert.ToInt64(val))` — **numeric only**. `"High"` throws into a bare catch, leaves `val` a string, then `SetValue` throws into a *second* bare catch. |
| `Backtest()` params loop (~1103) | `Convert.ChangeType(string, enumType)` throws into a bare catch. This is why `TradePolicy` could not be set remotely. |

Fix both with `Enum.Parse(under, s, ignoreCase: true)` (handling `Nullable<TEnum>`), collect
failures, and **never swallow**. A profile written before this reports success and changes
nothing.

#### 0.1d Profile, echo, refuse

1. Committed `backtest_profile.json` (in *this* repo, applied by the bridge) targeting
   **`StrategyTemplate`**, validated against `ValidOrderFillResolutions`.
2. **Declare → echo → refuse**: apply, return the **effective** values read back, and fail
   closed if any required field did not take.
3. Profile hash in every result.

**Acceptance**: a backtest result JSON names its own configuration; a deliberately
unsettable field produces a refusal, not a silent inherited value.
**Guard**: needs a negative control — assert the refusal path fires, or the gate is a
`green-that-can-never-be-red`. The read-back is also what catches the `StrategyTemplate`
staleness noted below.

⚠️ **`StrategyTemplate` is a persisted live `StrategyBase`.** Its values survive a change to
a strategy's C# defaults, so a param can silently be the OLD default. Read-back is the only
thing that detects this.

### 0.2 Adverse fill policy as the default
**Repo**: `tvDownloadOHLC`

Add an explicit `ambiguity_policy` (`adverse` | `favourable`) to the execution engine,
defaulting to `adverse`, plus a both-bounds mode that reports the interval. Today
`nt8_parity_engine.py:345-372` hardcodes the favourable path.

**Acceptance**: the policy is a required, logged parameter; no caller can get the optimistic
path implicitly.

### 0.3 Restate existing prop-firm conclusions on adverse fills
**Repo**: `tvDownloadOHLC`

Re-run whatever prop-viability numbers currently inform decisions, on adverse fills. Record
what changed. This is a *finding*, not a build task — the point is to learn how much prior
conclusions depended on the optimistic path.

**Acceptance**: a written before/after comparison. Any strategy whose viability does not
survive is flagged.

---

## Phase 1 — Prove the screen works

*One experiment. Highest information per hour in the plan.*

### 1.1 Rank-correlation calibration
1. One strategy that exists on both sides. ~25 parameter arms.
2. Python (adverse fills) ranks them. NT8 SA runs the same 25 under the frozen profile.
3. Compute **Spearman rank correlation**, **precision@5**, and **false negatives** (arms NT8
   likes that Python rejected — the expensive class, normally invisible).

**Acceptance**: a documented verdict on whether Python is a valid screen, plus the
**promotion threshold** for funnel stage 1 derived from the measurement rather than guessed.

**Decision this produces**:
- High correlation → stop chasing point parity; absolute error does not matter for screening.
- Low correlation → the fast loop is actively misleading; Phase 3 becomes urgent rather than
  scheduled.

---

## Phase 2 — Workflow enforcement

*The binding constraint. The machinery exists (§2.7); nothing forces a strategy through it.*

### 2.1 Run-record schema and writer
Every evaluation emits a signed record: strategy/params hash, data range, contract month,
fill policy, engine version, NT8 profile hash, git SHA, funnel stage, arm index.

**Acceptance**: no evaluation can produce a number without provenance. Run #7 and run #180
are comparable.

### 2.2 Single sanctioned entry point
Audit `research/lifecycle_runner.py` (300 lines, **0 importers**) — repair or replace, then
make it the only path. Verify it actually chains loader → signals → engine → walk-forward →
prop → reporting in the mandated order.

### 2.3 Mandatory ordered stages with gates
Implement the §4.1 funnel as enforced stages. `ml/leakage_guard.py` (**1 importer** today)
runs on **every** run, not when remembered.

**Acceptance**: skipping a stage is an error, not a choice. A gate failure blocks promotion.

### 2.4 Freeze the bespoke runners
34 `run_*` / backtest scripts each assemble their own pipeline. Mark them legacy, forbid new
ones, migrate only those still in use.

**Acceptance**: a CI check that fails on a new pipeline assembled outside the entry point.
Note the trap: an *absence* gate passes silently when code moves — give it a negative
control (`a-code-move-disarms-a-source-gate`).

### 2.5 Arm ledger
Log **every** arm ever tested, including abandoned ones. Deflated statistics need N.
First check whether `research.db` / `research_optuna.db` already capture trial counts.

### 2.6 Reports generated from the run record only
`reporting/` is well populated (tearsheet, monte_carlo, optimization_summary, risk_profiler,
mfe_mae). Wire them to consume the run record rather than hand-passed arguments.

**Acceptance**: a tearsheet names its inputs. One that cannot is not evidence.

---

## Phase 3 — Data and fill correctness

### 3.1 Unadjusted, per-contract-month data on both sides
Export per contract, unadjusted; NT8 merge policy `DoNotMerge` / non-back-adjusted.

**Accept the consequence**: no continuous multi-year runs. Backtest per contract, aggregate
across contracts. Stitching reinvents back-adjustment (§2.4).

### 3.2 Roll-warmup rule
Indicators with lookback crossing a contract boundary (EMA200, AVWAP, IPDA) need prior-contract
history at a different price scale. Decide and document the rule. **Open decision.**

### 3.3 Bar-completeness precondition
Assert expected bar count per session on both sides *before* diffing. Prevents re-debugging
missing-bar artifacts (standard doc's 2026-05-25 case: NT8 held 15 of 30 IB-window bars).

### 3.4 Tick-on-demand resolution for stage-3 finalists
1. Audit the tick DB per contract: file count + date range. `MNQ 12-22` is an empty
   directory — coverage is **not** complete.
2. Export tick (or 1s) for finalist trade windows only, to parquet, per contract, unadjusted.
3. Explicit **limit-order fill rule** — `Last` prints prove a price traded, not that your
   order filled. Require trade-through by ≥1 tick rather than touch, and match the NT8
   "limit orders fill on touch" setting. **Open decision.**
4. Engine streams (per-day chunks / Arrow batches / Rust core reading row groups); it must
   not require the series in a DataFrame.

**Acceptance**: finalists resolved on *observed* sequence. Ambiguity reported as zero, not
assumed away.

---

## Phase 4 — Trade-set parity as a CI gate

### 4.1 Generic parity harness
Strategy-agnostic. Join on **signal-bar timestamp + direction** — an input, never entry
price or fill time. Fix the **unit of comparison** first (setup / order / execution);
§2.2 shows the existing numbers cannot be reconciled without it. Report both directions.

### 4.2 Committed ground-truth corpus
`tests/fixtures/nt8_ground_truth/`, one artifact per (strategy, contract, range, profile
hash). Today there is **no committed NT8 trade list anywhere** and the canonical 97.9% claim
is unreproducible.

### 4.3 CI gate
Wire into `tools/ci_local.py` per the local-green mandate. Gate NT8-only **and** Python-only
counts. State the region the gate inspects and print the count actually compared
(`state-the-region-a-gate-inspects`).

### 4.4 Detector golden corpus
Export `nt_indicator_values` per bar for each detector; assert Python matches bar-for-bar.
Catches signal drift at the layer it originates and names the first divergent bar, instead
of surfacing as a P&L difference at the end of the pipeline.

**Acceptance**: parity is red-able, and a red tells you which bar.

---

## Phase 5 — Kill the port cost

### 5.1 Config-document layer
> **strategy = (C# bot class name) + (parameter document)**

One document read by both sides: parameters, filters, session windows, geometry, execution
settings. Bot logic stays hand-written C#. Extend the existing pattern
(`gen_ifvg_cisd_config.py` → `IfvgCisdConfig.cs`) to the other strategy families.

**Explicitly not** a full strategy DSL. Hard line: the document expresses **composition,
never computation**. Anything needing arbitrary computation is a new primitive written once
in both languages — not a new document feature.

### 5.2 Strategy registry
Canonicalized document hash = strategy ID. Enables re-run, dedupe, diff, and the
**cross-survivor correlation matrix** (impractical when every strategy is bespoke code).

### 5.3 Collapse the execution paths
Reduce the ~10 independent engines to one that consumes documents and carries a single fill
model. `nt8_parity_engine` must stop hardcoding Queen/Runner +10/+30bps and
09:45/15:30/15:55.

**Acceptance**: promoting a parameter-level variant to NT8 ships a document, not a
translation.

---

## Phase 6 — Overfitting controls at scale

### 6.1 Audit `ml/walk_forward.py`
82 lines is thin for purged-**and**-embargoed CV. Verify both, or fix.

### 6.2 Deflated metrics / PBO
Using the Phase 2.5 arm ledger. At hundreds of arms the best-looking result is best by luck;
existing practice ("≥120 trades, one OOS run") is not sufficient. Evidence for the failure
mode is already on file: IBFadeBot PF 1.295 (2wk) → 0.742 (3mo).

### 6.3 Survivor selection on low mutual correlation
Select on decorrelation, not top-N by PF. Ten variants of one idea is one idea.

**Acceptance**: a promoted strategy carries a deflated statistic and a correlation profile.

---

## Phase 7 — Speed (parallel, optional)

### 7.1 NT8 Optimizer support in the bridge
`McpBridgeAddOn.cs:1121` only calls `OnRun`. NT8's native Optimizer sweeps parameters
in-process with **no recompile**, so parameter search could run against ground truth with no
parity requirement at all — narrowing Python's necessity to *structural* search.

**Acceptance**: a parameter sweep runs in NT8 from one call and returns per-arm results.

---

## Not in Scope (decided)

| Excluded | Reason |
|---|---|
| Shared Rust core inside NT8 | Silent marshalling errors in the component built to end cross-checking; no hot-swap. If one implementation is wanted, it goes in **C#** (arch §4.4) |
| `nautilus_trader` | A third opinion on execution; does not address Python↔C# signal drift. Separate decision about engine quality |
| Full strategy DSL | Dies by growing into a programming language. Config-document layer instead (§5.1) |
| NT8 as the only simulator | Kills vectorized research and sweeps (ADR-022); SA is slow and crash-prone |
| Point P&L parity with SA | SA does not reproduce live fills either. Trade set → SA; economics → Sim101 |

---

## First Three Things

1. **0.1** — freeze and echo the NT8 profile. Nothing is measurable until ground truth stops moving.
2. **1.1** — rank-correlation calibration. Tells you whether the screen has been lying, and by how much.
3. **0.2 + 0.3** — adverse fills by default, then restate the prop numbers. This is where
   optimism does the most damage, and conclusions may change.

Phase 2 can start in parallel with any of them and is the highest-leverage structural work.
