# Strategy Evaluation & NT8 Parity — Architecture and Directions

> **Status**: DESIGN RECORD. Reasoning and evidence. The phased build is in
> [STRATEGY_EVALUATION_PIPELINE_PLAN.md](STRATEGY_EVALUATION_PIPELINE_PLAN.md).
>
> **Created**: 2026-09-04 · **Last updated**: 2026-09-04
>
> **Relationship to [NT8_PYTHON_PARITY_STANDARD.md](NT8_PYTHON_PARITY_STANDARD.md)**: that
> document is the *checklist* accumulated from six sessions of IB debugging and remains
> valid as a list of traps. This document argues the checklist treats symptoms, and asks
> what structure generates them.

---

## 1. The Requirement

Four statements from the user that together constrain the design:

1. **Trade-set parity.** *"If a trade was executed in Python I expect the same trade setup
   to be executed in NT8."* Parity is defined on the **trade set**, not on P&L. Result
   agreement is secondary.
2. **The C# bots are the product.** *"The idea was to use these C# strategies as bots to
   automate my trading in due time."* → **NT8 is authoritative for behaviour.** When the two
   disagree, the presumption is that the Python model is wrong. Python's job is to *predict
   what the live bot will do*, and to under-promise while doing it.
3. **Python exists for speed and feasibility.** To iterate through strategies and options
   faster than a build→compile→test→verify cycle on NT8, and to verify prop-firm viability.
4. **Scale: hundreds of variants.** Which makes selection bias a first-order error source,
   not a footnote, and makes per-strategy translation cost compound.

### 1.1 Consequence: Python is a screen, so what must be preserved is the *ranking*

For a search instrument, absolute P&L accuracy is not required — correct **ordering** is.
A biased estimator is acceptable if the bias is monotonic and does not reorder candidates.

**The current bias reorders them.** Intrabar optimism scales with
`(stop distance + target distance) / bar range`, so tight-target strategies are inflated far
more than wide-target ones. The sweep therefore preferentially promotes the variants most
likely to disappoint in NT8, and the disappointment always arrives *after* the expensive NT8
cycle is paid. This is a better explanation of "the numbers invariably differ" than any
individual bug: **the selection process is steered toward the candidates with the largest
error.**

### 1.2 Consequence: prop feasibility has the opposite requirement

Prop pass/fail is driven by **tails** — max drawdown, worst day, daily-loss breaches,
consecutive losers. The optimistic fill converts would-be losers into scratches, which
truncates precisely the left tail being measured. `nt8_parity_engine.py:345-372` is a
drawdown suppressor by construction. Feeding that into `PropFirmSimulator` (ADR-021) yields
an optimistic pass rate that no Monte Carlo iteration count can reveal, because the bias is
in the input distribution, not the sampling.

**So: a monotonic bias is survivable for ranking and disqualifying for prop feasibility.**

---

## 2. Evidence (measured 2026-09-04)

Recorded with locations so this can be re-verified rather than believed.

### 2.1 The NT8 side of every backtest is uncontrolled

`~/nt8-mcp-bridge/addons/McpBridgeAddOn.cs:1089-1112` sets exactly five things on the
Strategy Analyzer: `Strategy`, `InstrumentOrInstrumentList`, `BarsPeriod` (type + value),
the strategy params, and the From/To dates.

Everything else is inherited from whatever that SA window was last configured with — and the
window is **deliberately reused and never closed** across runs
(`_saWindow = FindExistingSaWindow()`, adopting windows orphaned by prior hot-swaps;
`McpBridgeAddOn.cs:1076-1086`). Not set, therefore whatever a human last clicked:

- **Order Fill Resolution** (Standard vs High, + sub-period) — the dominant intrabar determinant
- **Tick Replay**
- Slippage ticks, commission template
- **Limit orders fill on touch**
- **Trading Hours template** — decides session boundaries *and which bars exist*
- Break at EOD, merge policy / back-adjustment
- Account, Min bars required, `Calculate` mode

The result JSON never echoes back what was in effect. Two identical `nt_backtest` calls on
different days can return materially different numbers, and no parity artifact can name the
configuration that produced it. Same family as `configured-evaluated-enforcing` and
`measure-the-deployed-system`.

**This alone is sufficient to explain why the numbers vary by a large magnitude.**

### 2.2 The parity metric is blind to the failure the requirement cares about

`scripts/validation/ib_parity_harness.py:746-751`:

> *"NT8 may take multiple trades per day (re-entry); Python takes one per day. Match by
> closest entry time within ±60s on the same side."*

In the canonical result of standard doc §8 — Python 55, NT8 73, matched 47, "NT8-only 0",
agreement 97.9% — **26 NT8 trades are surplus re-entries the metric never penalizes**, and
the Python one-trade-per-day cap is a harness modelling choice, not a property of the
strategy. The headline is *result agreement conditional on trades that matched*.

Under the §1.1 requirement the score is **47/73 trade-set recall**, never driven toward
zero. Related: `an-order-is-not-one-fill`, `a-green-that-can-never-be-red`.

Matching on `entry_time` within ±60s also matches on an **output** — off-by-one-bar entries,
exactly the class worth catching, are absorbed by the tolerance.

### 2.3 Python assumes the favourable intrabar path

`scripts/execution/nt8_parity_engine.py:345-372`: within a single bar the engine tests the
+10bps queen target **first**, sets the stop to breakeven on that fill, and only then tests
the stop. When both prices lie inside `[low, high]` of one 1-minute bar, Python books
winner-then-BE.

Not a bug — **missing information**. 1m OHLC does not contain sequence. Any bar-based engine
must choose; the Python choice is optimistic and the NT8 choice is different.

`scripts/libs_py/strategy_engine/intrabar_1m_simulator.py:6` claims 1m bars "eliminate all
High/Low ambiguity". True for a 5m strategy resolved on 1m bars; **false** whenever stop and
target both sit inside one 1m bar. Overclaim; do not rely on it.

**Measured 2026-09-04, and it partly walks back the magnitude claim above.** With the policy
implemented (plan 0.2), `scripts/research/measure_ambiguity_impact.py` ran a year of NQ 1m
(353,152 bars, 774 trades) under both assumptions:

| metric | adverse | favourable | gap |
|---|---|---|---|
| trades | 774 | 774 | 0 |
| win rate % | 8.40 | 8.53 | +0.13 |
| total points | −111.12 | −101.25 | +9.88 |
| profit factor | 0.896 | 0.905 | +0.009 |
| max drawdown pts | 305.75 | 295.88 | −9.88 |

**About one trade in 774 changes outcome.** That is the `(stop + target) / bar range` scaling
doing exactly what it predicts: this fixture uses a 1.5 pt stop against a ~15 pt (+10bps)
first target, so a bar spanning *both* is rare on 1m NQ. **On this geometry the intrabar
assumption is not the source of large NT8 divergence** — it is a correctness and drawdown-tail
fix, and cause 1 (uncontrolled NT8 config) plus cause 7 (signal drift) remain the likely
dominant causes of magnitude.

Caveat: the fixture is a synthetic deterministic signal, not a real strategy. The effect is
geometry-dependent by construction, so it must be re-measured per strategy family — tight
scalps with both legs a few points apart, and wide-range bars, are where it bites. **Do not
generalise either the small number here or the earlier large-magnitude claim.**

### 2.4 The two sides are on different price scales by construction

Standard doc §10 measured it: NT8 SA applies back-adjustment to **fill prices** while
exporting **raw bars**. Monthly offsets −412 / −293 / −292 / −170 / −4 pts. The "100%
parity" result appeared in July 2026 only because the offset was ≈0 there.

### 2.5 There is no single engine and no regression corpus

~10 independent Python execution/simulation modules (`nt8_parity_engine`,
`trading_framework/core/{backtest_engine, multi_contract_backtester, portfolio_sim,
execution}`, `libs_py/strategy_engine/{engine, intrabar_1m_simulator}`,
`edgeful/lib/trade_simulator`, `nqstats/ib.py`, `range_probability/confluence_backtester`).
Of the three read directly, each carries its own fill assumptions.

`nt8_parity_engine` is **not generic** — it hardcodes the Queen/Runner two-lot at +10/+30
bps, 09:45/15:30/15:55 windows, and a lunch filter. A new strategy inherits none of the
parity work and re-earns all six divergence classes.

The canonical 97.9% was measured against `scratch/nt8_ib_breakout_nq_sep26_h1_2026.json`.
`git ls-files` shows **no committed NT8 trade list anywhere**, and that file is not in
`scratch/` today. **The canonical parity claim is not reproducible.**

### 2.6 An unused asset: the NT8 tick database

`~/Documents/NinjaTrader 8/db/tick/` — real `Last` tick prints, 5.3 GB total:

| Contract | Files | Size | Range |
|---|---|---|---|
| `NQ 09-26` | 1122 | 115 MB | 2026-06-08 → 2026-08-14 |
| `ES 09-26` | 1183 | 183 MB | 2026-06-11 → 2026-08-21 |
| `MNQ 03-26` | 1489 | 414 MB | 2025-12-10 → 2026-03-20 |
| `MNQ 06-25` | 1593 | — | 2025-03-13 → 2025-06-16 |

MNQ has directories for every quarterly from `06-20` to `09-26`. **Coverage is not
complete** — `MNQ 12-22` exists and contains **zero files**. Any plan built on this needs a
per-contract file-count and date-range audit first.

Nothing in the Python stack reads any of it. §2.3 is unsolvable without it.

### 2.7 The framework is built; its orchestration is used zero times

| Module | Lines | Importers |
|---|---|---|
| `research/lifecycle_runner.py` | 300 | **0** |
| `ml/leakage_guard.py` | 95 | **1** |
| `ml/walk_forward.py` | 82 | 14 |
| `ml/optimizer.py` (Optuna) | 71 | — |
| `ml/prop_firm_simulator.py` | 735 | 14 |
| `reporting/monte_carlo.py` | 93 | 29 |
| `reporting/tearsheet.py` | 279 | 11 |
| bespoke `run_*` / backtest scripts | — | **34** |

The framework is not unused — its **parts** are used heavily and its **orchestration** is
used *zero* times. The README calls `lifecycle_runner.py` the way to "instantly deploy a
full top-to-bottom strategy test," and nothing imports it. 34 scripts each assemble their
own pipeline from the parts, in their own order, with their own choices about whether to
purge, whether to check leakage, and how the prop sim is fed.

**This is why results are not comparable across strategies.** `leakage_guard.py` at one
importer is `dead-safety-machinery-gate` again: written, never called, passes every other
check. `walk_forward.py` at 82 lines is thin for purged-and-embargoed CV and needs an audit
for whether it actually does both.

### 2.8 The bridge cannot drive the NT8 Optimizer

`McpBridgeAddOn.cs:1121` only ever calls `OnRun` — the single-backtest path. No Optimizer
support exists in the addon or the wrapper. NT8's native Optimizer sweeps parameters
in-process with **no recompile**, so *parameter* search could run against ground truth with
no parity requirement at all. That capability is currently unreachable.

---

## 3. Root Causes, Ranked

| # | Cause | Effect | Fixable? |
|---|---|---|---|
| 1 | Uncontrolled NT8 SA configuration (§2.1) | Ground truth is a moving target | Yes — bounded |
| 2 | Workflow not enforced (§2.7) | Results not comparable; safety modules dead | Yes — highest leverage |
| 3 | Metric can't see trade-set divergence (§2.2) | Success declared on the wrong measure | Yes — cheap |
| 4 | Intrabar sequence unknown at 1m (§2.3) | Screen reorders candidates; prop tail truncated | Partly cheap, fully with tick |
| 5 | Selection bias at hundreds of arms (§1) | Best-of-N is a winner by luck | Machinery exists, unenforced |
| 6 | Price-scale mismatch (§2.4) | Level logic sees different geometry | Yes — unadjusted per contract |
| 7 | Rules implemented twice (§2.5) | Drift permanent and per-strategy | Structurally, or by testing |
| 8 | Python→C# port cost (§4.3) | Drift is *born* at promotion, per survivor | Config-document layer |

Causes 1, 4 and 6 are *why today's numbers differ*. Causes 2, 5, 7 and 8 are *why it keeps
coming back*. **Cause 2 outranks everything** — nothing else is attributable without it.

---

## 4. Decisions

### 4.1 The funnel

| Stage | Runs on | Gate to advance |
|---|---|---|
| **1. Screen** | Python, 1m bars, **adverse fills**, all candidates | Rank-based; conservative — false positives cost NT8 cycles |
| **2. Robustness** | Python, purged walk-forward, deflated for arms tested | Survives OOS + PBO threshold |
| **3. Accuracy** | Python, **tick-resolved**, finalists only | Trade set matches NT8; economics within tolerance |
| **4. Verify** | NT8 SA, frozen config, unadjusted contract | Trade-set parity both directions |
| **5. Feasibility** | `PropFirmSimulator` on stage-3 output | Prop pass rate on adverse fills |
| **6. Forward** | Sim101 live forward-run | Real fills, real slippage |

Key consequence: **tick data is needed only at stage 3**, for a handful of finalists.
Screening needs ranking, not accuracy. That removes the ~1B-tick materialization problem —
resolve on demand for a few dozen candidates instead.

Second consequence: **parity with SA is not the finish line.** SA will not reproduce live
fills either. Match the *trade set* to SA (stage 4); match the *economics* to Sim101 (stage
6). Conflating them is part of why prior parity work felt unbounded.

### 4.2 Layer decomposition — what to share and how

| Layer | Examples | Share it? | Mechanism |
|---|---|---|---|
| **Config / geometry** | thresholds, session windows, stop & target formulas, filters, flatten times | **Yes — by construction** | One document, read by both sides |
| **Detection** | FVG, CISD, MSS, IB boundary, sweeps | **No — but prove equality** | Golden corpus, bar-by-bar |
| **Execution / OMS** | order placement, brackets, OCO, risk gates | **Never** | C# owns it; Python models it pessimistically |

Execution must not be shared because the C# bot is what goes live (§1.2). The Python
execution model exists to *predict* it, deliberately pessimistically. One shared
implementation would mean the live order path is exercised by backtests — the wrong
direction of risk.

### 4.3 The port problem, and the deliberately limited answer

Drift is *created* at promotion: validated in Python, then hand-translated to C#. At
hundreds of variants that cost is paid per survivor, and its errors are silent. Divergence
classes A/C/D/E/F in the standard doc are a catalogue of translation errors.

**Rejected: a full strategy DSL.** The idea — strategy as a document interpreted by both
sides, so there is no port — is sound in principle, and the objection to it is well aimed:
DSLs die by growing into programming languages. Held to *composition only, never
computation*, it works; unheld, it becomes a worse programming language than code.

**Adopted: the config-document layer.**

> **strategy = (C# bot class name) + (parameter document)**

Bot logic stays hand-written C#. Parameters, filters, session windows, geometry and
execution settings live in one document both sides read. Rationale: 200 variants is
realistically ~10 strategy *shapes* × ~20 parameter combinations, not 200 distinct logics —
so this covers the overwhelming majority of variant volume, it is incremental, and
`IfvgCisdConfig.cs` + `scripts/utils/gen_ifvg_cisd_config.py` is already the first instance.

Notes on the objection *"how do I uniquely specify 200 variants?"*:
- You do not author 200 documents. A variant is **generated**: base document + parameter
  grid. The documents are *outputs* of the search, not hand-written inputs.
- You already have 200 variants; they are not *addressable*. Today a variant is "CLI args
  plus whatever was edited that afternoon" — it produced a number and cannot be re-run. The
  document names something that already exists anonymously.
- **Identity is free**: hash the canonicalized document → strategy ID. Dedupe comes free,
  and across 200 variants over months accidental duplicates are a certainty.

Revisit declarative *detectors* only if port cost still bites after this, and only with
measurement of how often it does.

### 4.4 If one implementation is ever wanted, it goes in C# — not Rust

A shared Rust core called from both sides (PyO3 for Python, `DllImport` for NT8) makes drift
inexpressible, but under §1.2 the costs are heavier than they look: a native DLL cannot
hot-swap (full NT8 restart per iteration), a panic does not throw but kills the process, and
the real hazard is **silent** — a marshalling error (struct layout, calling convention,
float width, array lifetime) yields wrong numbers from the one component built so that
cross-checking could stop.

Direction of authority settles it: C# is the live path, so the shared core belongs in C#.
NT8 consumes it natively — hot-swappable, exception-safe, no marshalling. Only the research
path pays a boundary, and it can afford one (batch out-of-process, bars in / signals out).
Rust stays where it already earns its place: the Python-side simulation hot loop
(`crates/nt8_parity_core`, ~378× the Python bar loop).

Also: the golden corpus is a **prerequisite** for trusting any shared core, not an
alternative to it — you cannot validate a shared detector without per-bar ground truth.
Build the corpus regardless.

### 4.5 Rejected

- **Shared Rust core inside NT8** — §4.4.
- **`nautilus_trader`** — the only serious off-the-shelf candidate (tick-level,
  futures-aware, real order-lifecycle state machine), but it does not address cause 7:
  divergence is Python↔C# signal drift and Nautilus is a Python execution engine, so it
  becomes a *third* opinion. Separate, later decision about engine quality. Not coupled here.
- **NT8 as the only simulator** — kills vectorized research and sweeps (ADR-022); SA is slow
  and crash-prone (standard doc §6).
- **Point P&L parity with SA** — §4.1.

---

## 5. Metric Definitions to Fix Before Anything Else

- **Unit of comparison** — setup / entry order / execution. §2.2 shows existing headline
  numbers cannot be reconciled without stating it.
- **Join on an input** — signal-bar timestamp + direction. Never entry price or fill time;
  matching on an output makes divergence invisible.
- **Gate both directions** — NT8-only and Python-only both → 0. Result agreement secondary.
- **Bar completeness as a precondition, not a finding** — assert expected bar count per
  session before diffing. The one surviving disagreement in the standard doc (2026-05-25)
  was NT8 holding 15 of 30 IB-window bars.
- **Screen quality is ordinal** — Spearman rank correlation, precision@N, and false
  negatives against NT8. Not agreement.
- **Pessimism as a parameter** — `ambiguity_policy` defaulting to `adverse`, with the option
  to run both bounds and report the interval. If a strategy is only profitable at the
  optimistic bound, it is not profitable.

---

## 6. Corrections to Earlier Analysis in This Document's Own History

- Purged walk-forward and leakage controls were recommended as new work. **They exist**
  (`ml/walk_forward.py`, `ml/leakage_guard.py`). The work is to *enforce* them and to audit
  whether `walk_forward.py` genuinely purges and embargoes at 82 lines.
- The tick-volume concern ("~1B ticks, intractable") was correct arithmetic against the wrong
  requirement. Tick resolution is needed only for stage-3 finalists (§4.1), so the volume
  never materializes.
- "Shared Rust core, defer on live risk" was weighted for a live posture. In dev the crash
  risk is affordable; the argument that survives is the *silent* marshalling error (§4.4),
  and the conclusion changed from "defer Rust" to "put it in C# instead."

---

## 7. Open Decisions

1. Unit of comparison for trade-set parity (setup / order / execution).
2. Limit-order fill rule, and the matching NT8 "fill on touch" setting.
3. Roll-warmup rule for indicators crossing a contract boundary.
4. Whether the frozen backtest profile is one global default or per-strategy-family.
5. Promotion thresholds per funnel stage (set from the Phase 1 calibration, not guessed).
6. Whether `research.db` / `research_optuna.db` already capture trial counts (needed for
   deflated statistics).
7. `nautilus_trader` — separate decision, deliberately not coupled here.
