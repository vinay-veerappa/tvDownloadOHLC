# The Strategy Workflow — from idea to validated bot

> **Status**: CANONICAL PROCEDURE. This is the one document to read before building,
> running, or judging a strategy in this repository.
>
> **Created**: 2026-09-04 · **Owner**: this is the ONLY document for strategy work.
> **Ten documents** were subsumed into it and deleted — nine on 2026-09-04, the engine
> code-generation spec on 2026-09-05: the procedure, the reasoning, the build order, the
> metric spec, the engine spec and three package/CLI overviews. **§13** records what moved
> where and what was dropped. **If you find another document describing how to
> build, run or judge a strategy in this repo, it is stale — read this one.**
>
> The only companion is `scripts/trading_framework/README.md`, which is a *package map*
> (what each module is), not a procedure.

---

## 0. How to read this document

Every rule below carries a status marker. This is the anti-rot device: a document that
claims enforcement it does not have is worse than no document, because it stops people
looking.

| Marker | Meaning |
|:---:|---|
| 🟢 **ENFORCED** | Something *fails* if you violate it. The enforcer is named. If you cannot name the enforcer, the marker is wrong. |
| 🟡 **CONVENTION** | Agreed, written down, and checked by nobody. Violating it is silent. |
| 🔴 **NOT BUILT** | Named here so the gap is visible. Do not treat as a rule you can follow today. |

**Rule for editing this file**: never promote a marker without naming the enforcer in the
same edit, and never quote a count you did not just measure. Both failure modes have
already happened in this repo's docs.

---

## 0.1 The one command

```powershell
.\.venv\Scripts\python.exe -m scripts.trading_framework.workflow `
    --strategy mean_reversion --ticker NQ1 `
    --price-adjustment unadjusted `
    --optimize --trials 200 --oos-start 2025-01-01 `
    --nt8 --nt8-trades scripts/parity/fixtures/<capture>.csv
```

`workflow.py` **is** the procedure below, executed. It runs every stage in order
under **one** run record, and it ends by printing the promotion checklist from §9
with each criterion marked PASS, FAIL or NOT EVALUATED.

| It will not | Because |
|---|---|
| silently skip a stage | a skip is recorded with its reason (`RunRecord.skip_stage`) and reported as **NOT EVALUATED**, never as a pass |
| call a run validated on an empty checklist | `validated` is `all(status == PASS)`, not `not failed` — a run that measured nothing reports "nothing failed; nothing proved it either" |
| guess a timezone | NT8 exports ET-naive timestamps; read as UTC they shift 4–5 hours onto a different entry bar. The zone comes from the fixture's `.meta.json` or `--nt8-tz`, or the run refuses |
| guess a price basis | `--price-adjustment` has no default |
| report in-sample | `--optimize` without `--oos-start` is rejected at argument parsing |

Exit codes, from `workflow.py::exit_code`: **0** every criterion PASSED · **1** not
validated — something FAILED *or* something was never measured · **2** a required stage
raised, so the run is inconclusive rather than failed.

> There is deliberately **no code for "nothing failed but not everything was measured"**;
> that is `1`, because it is not a pass. This was wrong until 2026-09-05: `main` returned
> `1 if check.failed else 0` — the `not failed` reading the row above disavows — so a run
> in which **every** criterion was NOT EVALUATED printed "NOT validated" and exited **0**.
> Any CI gate reading the status would have scored a run that measured nothing as a pass.
> Pinned by `test_workflow_checklist.py::test_a_checklist_that_measured_nothing_does_not_exit_zero`.

Everything below is the reference for what those stages do and why. **You should
not need to run any other script.** If you find yourself assembling a pipeline by
hand, that is the defect this file exists to prevent — see §4.1.

---

## 1. What "a strategy" means here

A strategy is **three artifacts sharing one identity**, not a Python file.

| Artifact | Role | Home |
|---|---|---|
| **Python hunter** | Research. Sweeps ~200 variants fast. Predicts what the bot will do. | `scripts/strategies/<family>/core/<name>.py` |
| **C# bot** | **The product.** What actually trades. | `scripts/ninjatrader/strategies/<feature>/<Name>Bot.cs` |
| **Parameter document** | The single source of the numbers both sides read. | `scripts/strategies/<family>/<name>_config.json` → generated `.cs` |

Two standing facts follow from this and govern every judgement below:

1. **NT8 is authoritative for behaviour.** When Python and NT8 disagree, the presumption
   is that *Python is wrong*. Python's job is to predict the bot and to under-promise
   while doing it.
2. **Parity is defined on the trade set**, not on P&L. "Same trades" first; "same money"
   is a separate and weaker question (§6).

### 1.1 Three pillars, strictly decoupled 🟡 CONVENTION

Where code lives is not filing — each pillar has a rule about what it may *not* do, and
every cross-pillar leak this repo has had became a defect.

| Pillar | Contains | May NOT |
|---|---|---|
| **1 — libraries** `scripts/libs_py/` | stateless vectorized maths: ICT primitives, the Strat, VWAP, regime, IB stats | touch files, databases, or assume a timezone |
| **2 — hunters** `scripts/strategies/` | chaining libraries into setups; exposes `hunt(data, params)` → Signal List | manage trades, track P&L, size positions |
| **3 — engine** `scripts/trading_framework/` | loading, timezone localisation, execution modelling, costs, optimisation, reporting | contain strategy logic |

Data flows one way: UTC parquet → loader (localises to `America/New_York`) → hunter →
engine → reports. A hunter that loads its own data has broken pillar 2 and will not be
comparable to anything else.

### 1.2 The naming rule 🟡 CONVENTION

Registry key is `snake_case`; the bot class is `PascalCaseBot`. One key ↔ one bot.

| Registry key | C# bot |
|---|---|
| `mean_reversion` | `BBMRReversionBot` |
| `ema_pullback` | `EMAPullBackBot` |
| `vwap_reclaim` | `VWAPReclaimBot` |
| `failed_auction` | `FailedAuctionBot` |
| `ib_pullback` | `IBRetestBot`, `IBBreakoutBot`, `IBFadeBot` |
| `ifvg_cisd` | `ICTFVGCISDBot` |

Nothing checks that a key has a bot or a bot has a key. A Python-only strategy is a
research artifact, not a strategy, and must not be reported as one.

---

## 2. Step 1 — Write the Python hunter

### 2.1 The interface 🟢 ENFORCED

```python
class MyStrategy:
    def hunt(self, data: pd.DataFrame, params: dict) -> pd.DataFrame: ...
    def get_param_grid(self) -> dict: ...
```

`hunt()` returns **one row per signal** with exactly these columns:

| Column | Type | Meaning |
|---|---|---|
| `signal_time` | datetime | the bar on which the setup was detected |
| `direction` | `'long'` / `'short'` | |
| `entry_price` | float | intended entry |
| `stop_price` | float | exit if wrong |
| `target1_price` | float | exit if right |

**No signals ⇒ an empty DataFrame *with these columns*.** A column-less frame is not an
empty result; it is an unreadable one.

*Enforcer*: `core/backtest_engine.py::validate_signal_geometry` and
`core/nt8_parity_backtester.py::_prepare_series`, which refuses an unrecognised frame
shape **by name** rather than defaulting to zeros.

### 2.2 Signal geometry 🟢 ENFORCED

Every signal must satisfy, for a long (mirrored for a short):

```
stop_price  <  entry_price  <  target1_price
|entry - stop| >= 1 tick
all four values finite
```

Signals that fail are **dropped and counted**, attributed to the first rule they broke.

> **Why this exists.** `mean_reversion` anchored its stop to a Bollinger band rather than
> to entry, so 15.1% of its signals had the stop on the *profitable* side. The engine
> booked them as wins on "Stop Loss" exits. Refusing them moved that strategy from
> **76.3% → 30.8% win rate** and PF **31.64 → 1.87**. Every "impossible" number this
> project has produced has had a cause of this shape.

*Enforcer*: `validate_signal_geometry`, covered by `tests/test_signal_geometry.py`.

### 2.3 What the hunter must NOT do 🟡 CONVENTION

- **No trade management, no P&L, no position sizing.** It is a pure signal hunter; the
  engine owns execution — "hunters vs execution", the rule the deleted design standard
  was built around (§13).
- **No data loading.** It receives a frame.
- **No look-ahead.** Not "be careful" — the causality probe (§4.4) will demonstrate it.
- **No own backtest loop.** Dozens already exist and are frozen (§4.1).
- **No row-by-row iteration.** `for _, row in df.iterrows()` and `for i in range(len(df))`
  are forbidden — roughly 100× slower, and they make a 200-arm Optuna sweep impractical,
  which is the entire reason the Python side exists. Use boolean masks:

  ```python
  signals['is_long']  = data['high'] > data['ib_high']
  signals['is_short'] = data['low']  < data['ib_low']
  ```

  Compute every indicator as a **column on the frame first**, then hunt over columns.

### 2.4 Which libraries to use 🟡 CONVENTION

Reuse before writing. A second implementation of a rule is the drift problem at birth.

| Need | Use | Do not |
|---|---|---|
| ICT primitives (FVG, IFVG, CISD, order blocks, liquidity, BPR) | `scripts/libs_py/ict_engine/`, `fvg.py`, `ifvg.py`, `cisd.py`, `orderblock.py`, `liquidity.py`, `bpr.py` | reimplement per strategy |
| The Strat (bar classification, wicks, measured targets, FTFC) | `scripts/libs_py/the_strat/` | — mirrored in C# `StratCore.cs`, §6.1 |
| VWAP / anchored VWAP | `scripts/libs_py/avwap.py` | |
| Regime / volatility context | `scripts/libs_py/regime/`, `expected_volatility/` | |
| IB statistics, profiler | `scripts/libs_py/nqstats/`, `profiler/` | |
| Reusable entry/exit filters | `trading_framework/strategy_lib/filters.py` | inline copies |
| Risk primitives | `scripts/libs_py/risk/` | ad-hoc sizing |
| Walk-forward folds | `trading_framework/ml/walk_forward.py::sequential_evaluation_folds` | `walk_forward_split` — **DEPRECATED** |
| Prop-firm viability | `trading_framework/ml/prop_firm_simulator.py` | `prop_eval_mc.py`, `06_prop_sim.py`, `simulate_prop_pass.py` — **frozen legacy** (ADR-021) |
| Load / merge / enrich a frame | `scripts/libs_py/data/loader.py::DataLoader.load_enriched` | `pd.read_parquet` in a hunter — that breaks pillar 2 (§1.1) |
| Session tagging | `scripts/libs_py/data/session_tagger.py` | a hand-rolled `between_time` mask |
| Resampling 1m → 5m / 15m | `scripts/libs_py/data/resampler.py` | a bespoke `.resample()` with its own label/closed choice |
| ATR, EMA, Bollinger, Keltner, VWAP, IB, chop, auction, internals, acceptance/rejection | `scripts/libs_py/features/` — one module each | an inline indicator. Every one of these already exists |
| Trade-management policy (cover-the-queen, fixed target, breakeven trail, time stop, scaled exit, base hits) | `scripts/libs_py/risk/trade_policies.py::get_policy` | a new policy written inside a hunter — the hunter may not manage trades (§2.3) |
| Signal / trade / session / account dataclasses | `scripts/libs_py/risk/risk_config.py` | a dict. Structured state is a dataclass here (§2.8) |
| Session and account limits | `scripts/libs_py/risk/session_manager.py::SessionRiskManager`, `account_manager.py::AccountRiskManager` | per-strategy limit logic |
| Slippage and commission | `trading_framework/core/execution.py` | a cost constant in strategy code |
| Excursion (MFE/MAE) | `trading_framework/core/mfe_mae.py::compute_mfe_mae` | a second excursion loop |
| Multi-strategy P&L | `trading_framework/core/portfolio_sim.py::PortfolioSimulator` | summing per-strategy equity curves |
| Config | `trading_framework/config/config_loader.py::load_config`, `config/sessions.yaml` | module-level constants |

⚠️ **`features/feature_registry.py::FeatureRegistry` exists but is NOT on the sanctioned
path.** `run_backtest.py` enriches through `DataLoader.load_enriched` and never calls the
registry; its only live callers are `run_raw_analysis.py`, `run_trade_optimization.py` and
`scripts/strategies/logic/mean_reversion.py`. A hunter therefore computes what it needs
from the frame it is handed, or the feature is added to `load_enriched` — **it does not
declare required features and expect the orchestrator to resolve them.** The deleted engine
spec (§13) described the opposite, which is one reason it could not stay.

⚠️ **`ml/walk_forward.py::PurgedKFold` is real and is the wrong tool for a parameter
sweep.** It purges and embargoes around a *fitted* model's labels. A sweep fits nothing, so
there is no training set to purge — use `sequential_evaluation_folds`. The deleted spec
named a `PurgedWalkForwardCV` that does not exist under that name, which is how "purged
walk-forward" ended up asserted as a property of a path that has none.

### 2.5 Register it 🟢 ENFORCED (by failure)

Add to `trading_framework/strategies/registry.py::STRATEGY_FACTORY_REGISTRY`. The entry
point resolves `--strategy` through this map; an unregistered strategy simply cannot be
run by the sanctioned path.

### 2.6 The parameter grid 🟢 ENFORCED

`get_param_grid()` must be able to **change the signal frame**. Before any trial budget is
spent, `assert_grid_is_live` evaluates the grid corners and compares the *whole frame
digest*.

> Compared on the whole frame, not on signal times, deliberately: exit-only parameters
> (`sl_atr_mult`, `tp_r_mult`) legitimately leave entry timing untouched. `mean_reversion`
> yields 176 signals at all three corners but three *distinct* frames — a count-based or
> time-based check would have rejected a perfectly good grid.

*Enforcer*: `research/objective.py::assert_grid_is_live`. It has already caught a real
defect: `run_optimization` hardcoded BoxReversion's parameter keys regardless of
`--strategy`, so the search across three other strategies could not change the answer.

### 2.7 The engine contract 🟡 CONVENTION (one item 🟢 ENFORCED)

The hunter hands the engine a signal list; the engine returns a metrics dict. Both sides
of that contract are fixed.

**`risk_params` MUST carry `ticker`** 🟢 — the engine selects the point-value multiplier
from it ($20/pt NQ, $50/pt ES, $2/pt MNQ). It was omitted, and the engine silently applied
its **NQ1** multiplier to every instrument. Every P&L figure produced that way was wrong by
the ratio of the two multipliers and nothing said so.

The metrics dict carries at least: `total_return_%`, `win_rate_%`, `avg_mae_%`,
`num_trades`, `equity_curve`, `trades_detailed`, and `signal_alignment`.

> ⚠️ **The two engines name the trade count differently** — `VectorizedBacktester` returns
> `num_trades`, `NT8ParityBacktester` returns `total_trades`. Never read either key
> directly; call `run_backtest.trade_count(result)`, which raises rather than defaulting.
> A `.get('num_trades', 0)` refused a real run that had taken 38 trades.

### 2.8 Code conventions 🟡 CONVENTION

Nothing checks any of these. They are here because a hunter that ignores them is harder to
compare, not because a gate will stop you.

| | Rule |
|---|---|
| **Python** | 3.11+. Type hints on every public signature |
| **Structured data** | a `@dataclass`, not a dict. A dict's shape is discovered at the call site that breaks |
| **Categorical state** | an `Enum`, not a string literal. `TradeDirection`, `TradeStatus`, `PolicyAction`, `RiskMode` already exist — reuse them |
| **Time series** | a `DataFrame` with `datetime` as the index, tz-aware `America/New_York`. **The loader localises; a hunter never guesses a timezone** (§1.1) |
| **Logging** | the `logging` module. **No `print` in library or hunter code** — a print inside a 200-trial sweep is 200 prints |
| **Imports** | every library module importable on its own. No circular dependency between `libs_py/` and `trading_framework/` — the dependency runs one way, hunter → library |
| **Names** | modules `snake_case.py` · classes `PascalCase` · functions `snake_case` · constants `UPPER_SNAKE_CASE` · config keys `snake_case` · registry keys `snake_case` (§1.2) |

The one that has actually cost time is the timezone rule. Everything upstream is UTC
parquet; `DataLoader.load_enriched` is the single place that localises. A hunter that
re-localises, or that compares a naive `Timestamp` to a tz-aware index, raises
`TypeError: Invalid comparison between dtype=datetime64[s] and Timestamp` — which
`box_reversion` still does when window-filtered (§11).

### 2.9 The three risk modes 🔴 NOT BUILT — a knob wired to nothing

`sessions.yaml` carries `risk_mode: "raw" | "strategy" | "portfolio"`, `config_loader.py`
parses it into a `RiskMode` enum, and two tests assert it round-trips. **Nothing branches on
it.** Outside `config_loader.py` and `tests/`, `RiskMode.` appears in this repo exactly
twice, both of them assertions in those tests.

The intent, which is still the right design, was:

| Mode | Active | Question it answers |
|---|---|---|
| `raw` | no stops, no targets, no limits — record the forward path of every signal | *what risk parameters should this strategy have?* (MFE/MAE, §7.1) |
| `strategy` | trade-level risk only: stop, target, partials via a `trade_policies.py` policy | *what is the per-trade expectancy with realistic exits?* |
| `portfolio` | trade + session + account limits (prop rules) | *does this survive a prop evaluation?* (ADR-021) |

Treat the setting as **decoration until something reads it**. The reports it was meant to
switch between are today selected by which function `run_backtest.py` calls, so setting
`risk_mode` in a config file changes nothing and says nothing about what ran. This is the
same shape as a config file that reads as protection which does not exist — do not cite it
as evidence of what a run enforced, and if you wire it, name the reader here in the same
edit.

---

## 3. Step 2 — Write or update the C# bot

### 3.1 Ownership 🟢 ENFORCED

**One artifact, one owner, one deploy path** (ADR-025,
[NT8_STRATEGY_OWNERSHIP.md](NT8_STRATEGY_OWNERSHIP.md)).

| Artifact | Canonical home | Deployed by |
|---|---|---|
| Trading bots `*Bot.cs` | `tvDownloadOHLC/scripts/ninjatrader/strategies/<feature>/` | `python scripts/utils/sync_nt8_strategies.py` |
| Indicators | `tvDownloadOHLC/scripts/ninjatrader/indicators/<vendor\|feature>/` | same tool → `Indicators/Vinay/`, `Indicators/RedTail/` |
| Framework base classes | `nt8-riskguard/strategies/Vinay/` | `nt8-mcp-bridge` → `python tools/deploy.py` |
| Addons | their own repos | their own deploy tools |

*Enforcer*: `nt8-mcp-bridge/tools/deploy.py::_assert_no_bots_in_vendor` exits 2 if a bot
reappears in the vendored core.

> **Two traps that have both fired.** NT8 compiles `Strategies/` and `Indicators/`
> **recursively** — the same class in two subfolders is CS0101, which fails the *whole*
> Custom assembly and stops **every** addon loading, RiskGuard included. And a broken
> assembly is **invisible**: NT8 keeps serving the last good one, so `nt_health` reads
> healthy and the only symptom is a deploy that appears to do nothing.

### 3.2 Shared logic goes in a shared core 🟡 CONVENTION, 🟢 ENFORCED for `the_strat`

Rules that both languages need are written **once in C#** as a platform-free file
(`scripts/ninjatrader/shared/StratCore.cs`, `shared/ict/`) and mirrored in Python. The
mirror is then held to it by a differential test (§6.1).

For `the_strat` this is enforced: `scripts/parity/csharp/stratcore/` compiles
`StratCore.cs` **alone** against `net8.0` (not `net8.0-windows`), so a NinjaScript
dependency creeping into that file breaks the build — the contract enforcing itself.

### 3.3 The parameter document 🔴 NOT BUILT (except `ifvg_cisd`)

> **strategy = (C# bot class) + (parameter document)**

One JSON read by both sides: parameters, filters, session windows, geometry, execution
settings. The pattern exists (`gen_ifvg_cisd_config.py` → `IfvgCisdConfig.cs`) and has not
been extended to the other families. Until it is, **every parameter is duplicated by hand
and drift is a matter of time**.

Hard line when this is built: the document expresses **composition, never computation**.
Anything needing arbitrary computation becomes a new primitive written once in both
languages. This is explicitly *not* a strategy DSL — that path dies by growing into a
programming language.

---

## 4. Step 3 — Run the Python backtest

### 4.1 The one entry point 🟢 EXISTS (🔴 not yet exclusive)

`scripts/trading_framework/workflow.py` (§0.1) is the entry point. It does not add
a pipeline — it **orders** the ones that exist and holds them under a single run
record, so a result carries the same provenance and the same gates whichever
question was being asked.

Its stages, in order, each recorded with a verdict:

| Stage | Does | Sets |
|---|---|---|
| `resolve` | registry lookup; locate the paired C# bot | `registered`, `has_bot` |
| `python_research` | data → split → gates → optimise → backtest → prop-firm → reports | `signal_geometry`, `grid_live`, `causal`, `out_of_sample` |
| `rule_parity` | Layer 1 differential on the shared core (§6.1) | `rule_parity` |
| `nt8_backtest` | load the NT8 trade list + its declared metadata (§5.4) | `nt8_ground_truth` |
| `trade_set_parity` | per-leg join and verdict (§6.3) | `trade_set_parity` |

`--optimize` may be passed only with `--oos-start`, and `--price-adjustment` has
no default. Both are argument-level refusals, not warnings.

**Still true: `run_*.py` scripts are everywhere and nothing forbids one more.** They
are frozen — do not extend them, do not copy their pattern. This used to say "35", twice,
and no denominator reproduced it (51 exist under `scripts/`; 2 under
`trading_framework/`; the backtest-ish cluster is 38). **Count them, do not quote this
line:**

```powershell
Get-ChildItem scripts -Filter "run_*.py" -Recurse -File | Measure-Object
```
 Making the entry point
*exclusive* is plan §2.4 and needs a CI gate this repo does not yet have (§11).

### 4.2 Which data 🟡 CONVENTION

- **Backtests / deep history** → `data/{ticker}_1m.parquet` (2006–2024), which is what
  `libs_py/data/loader.py::DataLoader.load_enriched` reads. This is the loader the entry
  point uses.
- **Live / current analysis** → `data/live/live_storage_-{ticker}.parquet` directly.
- **Both** → `scripts/utils/fused_data_loader.py::load_fused_data()`.

> ⚠️ There are **three** classes named `DataLoader` in this repo
> (`libs_py/data/loader.py`, `edgeful/lib/data_loader.py`, and one inside
> `nine_thirty_breakout/utils/`). CLAUDE.md's warning about "`DataLoader`" cites
> `scripts/shared/data_loader.py`, **which does not exist**. The one the pipeline uses is
> `libs_py/data/loader.py`. Name the module, never just the class.

### 4.3 What the run produces 🟢 ENFORCED

Every run opens a **run record** before it loads a byte:

```
results/RESEARCH/_pipeline/<TICKER>/<RUN_ID>/     # run-id'd, never overwritten
results/RESEARCH/_run_ledger.jsonl                # append-only, every run, twice
```

The record carries: git hash + dirty flag + package versions, an **exact content hash** of
the data (index as UTC ns + OHLCV — exact, not sampled: 173 MB / 0.11 s on the real
3.6M-row frame), engine config read off the instance, fold geometry, the IS/OOS split rule
*and its realised dates*, `signal_alignment` per stage, and every stage with its verdict
and duration.

The ledger is appended **twice** — once at open, once at finalize — so a run that crashes
still leaves a trace. **An abandoned arm that vanishes from the ledger cannot be counted,
and deflated statistics need N.**

*Enforcer*: `provenance/run_record.py`, 49 tests in `tests/test_run_record.py`
(measured 2026-09-05). `trade_count()` **raises** rather than
defaulting to 0 — it had already refused a real 38-trade run because the key was named
`total_trades` instead of `num_trades`.

### 4.4 The stage gates 🟢 ENFORCED

Stages are ordered and recorded; one that raises is recorded `failed` *before* the
exception propagates, and the run still lands in the ledger. Three gates are live, and
each has been demonstrated both firing and not firing:

| Gate | Refuses when |
|---|---|
| **grid precheck** | the strategy's own grid cannot move its signal frame (§2.6) |
| **causality probe** | signals generated on `data[:m]` differ from signals before `m` generated on all of `data` — lookahead *demonstrated*, not inferred by correlation |
| **zero-trade refusal** | no trades. A null result is not a measurement. |

> The causality probe's blind spot is documented and tested: a cutoff only exposes a
> lookahead of horizon *h* if a signal sits within *h* bars before it. It therefore uses
> several cutoffs, and a pass means "none exposed", not "none exists". When a strategy
> emitted **zero** signals before the cutoff it originally reported `causal=True` —
> `empty == empty`, a green with no reachable red. It now reports `vacuous`.

### 4.5 Optimisation 🟢 ENFORCED

One objective, in `research/objective.py`, used by every path. Folds are equal-length
sequential windows with the exit buffer **reserved from the end**
(`sequential_evaluation_folds`). An empty fold scores `EMPTY_FOLD_SCORE = -1.0`, never
`0.0`.

> `0.0` for an empty fold beat any real loss, so the search was rewarded for finding
> parameters that **stopped trading**. And signals were generated on the train fold and
> scored on the test fold, collapsing 50% of them onto bar 0 — the objective flipped
> **+0.208 → −0.596** at identical parameters. Both defects existed **identically in two
> runners**; the framing logic now lives in one place so a third copy cannot drift.

---

## 5. Step 4 — Validate in NT8

```powershell
# 1. Deploy — ALWAYS dry-run first. Read the diff DIRECTION before syncing.
python scripts/utils/sync_nt8_strategies.py --verify
python scripts/utils/sync_nt8_strategies.py

# 2. Compile. A failure here is invisible from nt_health — read the return.
#    (MCP)  nt_compile

# 3. Prove the Strategy Analyzer configuration
.\.venv\Scripts\python.exe -m scripts.parity.verify_profile_gate

# 4. Backtest  (MCP)  nt_backtest  → then  nt_extract_trades
```

### 5.1 Never hand-copy `.cs` into `Documents/NinjaTrader 8/bin/Custom/` 🟢 ENFORCED

Traps and rules: [NT8_FILE_ORGANIZATION.md](NT8_FILE_ORGANIZATION.md).

> **A drift report does not say which side is stale.** `NtDrawingCore.cs` reported
> `content-differs` for days and the **NT8 copy was newer** — two hand-added attributes
> never backported. Running the sync, the obvious response, would have reverted a live fix
> with returning warnings as the only symptom.

### 5.2 The frozen profile 🟢 ENFORCED

`scripts/parity/backtest_profile.json` + `nt8_profile.py` pin the SA configuration. The
knobs live on `StrategyTemplate` and `Globals.MarketDataOptions`, **not** where you would
look for them, and enums set by *name* were previously dropped silently — every SA
backtest ran back-adjusted with zero slippage without saying so.

`verify_profile_gate.py` **passes by refusing** on a box whose globals disagree. A run that
succeeds means the machine already matches.

### 5.3 A backtest is attributable only if it echoes what you asked for 🟢 ENFORCED

`nt_backtest` returns `effectiveStrategy` and `effectiveGlobals`. **Check them.**

> The Strategy Analyzer window is *reused*, and the strategy used to be applied leniently:
> an unresolvable name failed silently and the window kept whatever it already had. A
> request for `@SampleMACrossOver` ran `_McpTestBot` and returned `totalTrades: 0` —
> indistinguishable from that strategy simply not having traded. Fixed 2026-09-04: the name
> is resolved *before* the shared window is touched, the selection is read *back*, and a
> mismatch fails closed.

### 5.4 Commit the trade list 🔴 LARGELY NOT BUILT

`scripts/parity/fixtures/nt8_trades_<Strategy>_<SYM>_<TF>_<from>_<to>.csv` + a `.meta.json`
naming the profile hash, contract month and price basis.

**Today exactly one exists** (`BollingerCrossOver ES 15m`) and **it has no bracket
exits** — the only exit type the real bots use. Until a corpus exists, no parity claim is
reproducible.

---

## 6. Step 5 — Compare

Parity is checked at **three layers**. Lower layers name the *rule* that diverged; higher
layers only tell you *that* something did.

### 6.1 Layer 1 — Rule parity (no NT8 in the loop) 🟢 ENFORCED for 2 of 7 families

Pure functions run through both languages on identical inputs.

```powershell
.\.venv\Scripts\python.exe scripts\parity\strat_core_parity.py       # the_strat: 874 cases
.\.venv\Scripts\python.exe scripts\parity\run_signal_parity.py --fixture <f>.csv   # ICT, bar-by-bar
```

This is drift detection **at its origin**, it is CI-able, and it needs no NT8 at all. It
found the one live divergence in `StratCore` on its first run (§10).

> **Write these tests to assert the divergence's SCOPE, never its existence.** A test that
> asserts a defect is present goes red when someone fixes it, and the fix gets reverted to
> make it green. The `the_strat` tests say *nothing outside `wick` may diverge* and *a
> `wick` divergence may only occur on a ≤1-tick bar* — closing the defect keeps them green;
> any new divergence fails.

The IB, VWAP, EMA, mean-reversion and failed-auction families have **nothing** at this
layer.

### 6.2 Layer 2 — Signal parity 🟡 partial

Bar-by-bar detector output, C# vs Python, on a hash-stamped fixture
(`scripts/parity/export_fixture.py`). Catches drift at the layer it originates and names
the **first divergent bar** instead of surfacing as a P&L difference at the end.

Exists for the ICT engines. Plan §4.4 generalises it via `nt_indicator_values`.

### 6.3 Layer 3 — Trade-set parity 🟢 harness built, 🔴 not yet a gate

```powershell
.\.venv\Scripts\python.exe scripts\parity\trade_set_parity.py --py <py.csv> --nt8 <nt8.csv>
```

**Join key: `(entry bar, direction, occurrence)`.** An *input*, never entry price or fill
time — joining on an output makes the comparison assume its own conclusion.

#### The leg convention 🟢 DECIDED 2026-09-04 — NT8's convention wins

**One row per leg.** NT8 reports a 2-contract queen/runner bracket as **two trades**
(`entries: 6, totalTrades: 12`). Python must match: the runner and the queen are two rows
sharing an entry bar and direction, ordered by exit time within the bucket.

*Why*: NT8 is authoritative for behaviour (§1). Aggregating NT8 down to one row would mean
the harness *transforming* the authoritative side to fit the model — the exact inversion
this whole effort exists to prevent. It also discards real information: a queen that filled
and a runner that stopped out is a different outcome from both legs stopping, and only the
per-leg view can show it.

*Status* 🟢 **BUILT 2026-09-04.** `scripts/parity/legs.py::explode_legs` projects one
row per leg. It does not re-simulate — every value is recorded or derived exactly:

    leg1 (queen)   price = entry + leg1_points x sign   time = leg1_exit_time
    leg2 (runner)  price = exit_price                   time = exit_time

`leg1_exit_time` had to be **added** to both the Rust kernel (`crates/nt8_parity_core`)
and its Python mirror: the moment the queen filled was computable but nowhere kept. A
queen that never fills leaves with the runner, so both legs then carry the same exit.

Two invariants are asserted inside the projection, so an arithmetic slip fails *there*
rather than surfacing later as a parity divergence blamed on the strategy: per-leg points
sum to the recorded legs, and each leg's exit price agrees with its own points. Note that
`total_points` is deliberately **not** the reference — the engine records it as the *mean*
of the two legs, not their sum.

The queen's `exit_reason` is its own, not the position's: a queen that took its target
while the runner stopped out would otherwise be labelled "Stop Loss", and exit-reason
parity against NT8's `exitName` is one of the checks this projection exists to enable.

#### What the harness judges 🟢 ENFORCED

- **Recall / precision / Jaccard** on the matched trade set. Both directions, always —
  NT8-only and Python-only surpluses are reported separately.
- **Geometry**, not absolute price: signed points travelled `(exit − entry) × direction`.

> **Back-adjustment is NOT a parity gate.** Signed points travelled is invariant to a
> constant price offset, so a *constant* offset **is** the adjustment basis and only the
> **scatter** is real divergence. The harness reports `constant_price_offset` and
> `price_offset_spread` separately. What matters is the geometry of the trade, not the
> price level it happened at.

- **VACUOUS** is a verdict. A comparison of two empty sets is not a pass.

#### Thresholds 🟡 CONVENTION

`min_recall`, `min_precision` are parameters, not constants, because the right bar differs
by strategy family. State them in the run record; do not tune them to make a red go green.

### 6.4 The parity checklist — what to line up BEFORE blaming the engine

Six accumulated over six sessions of IB debugging. Every one has been the cause of a real
divergence in this repository, and every one is cheaper to check than to discover.

**Entry model.** NT8's `EnterLong()`/`EnterShort()` are **market orders** — they fill at
the **next bar's open**, not at the signal bar's close and not at a boundary price. Python
must model `entry = open[signal_idx + 1]`. Only use the signal-bar price when the bot
places a *limit* order at exactly that price.

> This one alone destroyed an edge: `IBFadeBot` entering at the IB boundary in Python
> scored **E[R] +0.259**; modelled as next-bar-open it scored **−0.0024**. The "strongest
> single strategy" was a measurement artifact.

**Stop / target geometry.** Same formula, same base reference, same multipliers. A
range-based stop (`StopRMult × range`) and an ATR-based stop (`StopAtrMult × atr`) differ
by **8–16×**. Both sides must also use the same same-bar tie-break when stop and target sit
inside one bar — **document which**, because a bar cannot tell you what arrived first
(this repo's adverse-fill default is
`scripts/execution/nt8_parity_engine.py::_resolve_ambiguity_policy` — **not** in
`trading_framework/`; §4.2's name-the-module rule applies to this document too).

**Exit / liquidation.** The flatten time must match exactly. NT8 `FlattenBy = 1550`
flattens at 15:50 ET, so Python must exit on the close of the **15:49** bar — not 15:59.
Five extra trades held to close came from exactly this. Neither side may carry overnight
for an RTH strategy (ADR-020).

**Session window.** RTH-only means Python's mask excludes pre-09:30 and post-16:00 ET, and
NT8 has `EarliestEntry`/`LatestEntry` set to match. Both use ET for windows; the trading
date is the **ET session date**, not the UTC date, or calendar filters land on the wrong
days.

**Filters.** Every NT8 gate is either ported to Python or explicitly marked NT8-only with a
reason. **Audit the columns before porting** — TPO/VPOC/volume-profile inputs may simply
not exist in an OHLCV parquet. Then ablate each filter individually: one that cuts trade
count without lifting win rate is removing trades *at random* and adds no alpha.

**Statistical significance.** ≥120 trades per configuration across ≥3 regimes before
claiming an edge; validate out-of-sample on a **different contract or period** than the one
searched. `IBBreakoutBot` held up (IS PF 1.489 → OOS 1.426); `IBFadeBot` did not (2-week PF
1.295 → 3-month 0.742 — the edge was noise). For a marginal PF of 0.8–1.2, bootstrap a
confidence interval on per-session returns; if it crosses zero there is no edge to deploy.

> **Compute the breakeven win rate before tuning anything.** `IBBreakoutBot` ran a target of
> 0.5×range against a stop of 2.0×range — a **1:2 risk-reward, which needs >66.7% WR just to
> break even**. At its measured 55.6% the profit factor cannot exceed 1.0 no matter how the
> filters are tuned. That is geometry, not parameters. Fix the geometry first.

**Contract month.** Use the same contract on both sides. Different months have different
price levels, so an IB boundary lands on a different value and a different set of days
trades — which then reads as a logic divergence. This is *not* the same thing as the price
basis: a constant offset is the adjustment basis and is invariant under §6.3's geometry
test, but a different **contract** changes which trades exist at all.

---

### 6.5 What a red means

| Symptom | Look here first |
|---|---|
| Trade **counts** differ | filters present on one side only; session/flatten windows; signal geometry drops (§2.2) |
| Same count, **different bars** | detector drift → drop to Layer 2 |
| Same trades, **different points** | entry mechanics (boundary vs next-bar-open), stop formula inherited from a base class, slippage/commission |
| Same points, **different prices** | price basis. Check `constant_price_offset` before assuming anything is wrong |
| Python **better** | the default presumption. Look for a signal that could not lose (§2.2) before believing the edge |

---

## 7. Step 6 — Reports

### 7.1 Which report answers which question 🟡 CONVENTION

| Question | Module |
|---|---|
| Is this tradeable? | `reporting/tearsheet.py` |
| How bad can a run of it get? | `reporting/monte_carlo.py` |
| Would it pass a prop evaluation? | `ml/prop_firm_simulator.py` (ADR-021 — **only** this one) |
| Where did the trades leave money? | `reporting/mfe_mae_report.py` |
| Which arm won and by how much? | `reporting/optimization_summary.py` |
| Is the risk profile survivable? | `reporting/risk_profiler.py` |

### 7.2 Metric definitions 🟢 ENFORCED (one implementation, spec-tested)

The metric spec **was** `RISK_PROFILE_DEFINITIONS.md` ("The Edge System"), subsumed into
this section and deleted 2026-09-04 (§13). It no longer exists as a file — its authority
now lives in `scripts/trading_framework/reporting/institutional_metrics.py`, the single
implementation, and in the ten worked systems carried into
`tests/test_institutional_metrics.py::SPEC_SYSTEMS`. The `spec §5` / `spec §13` citations
below refer to that deleted document as it stood; `git log --follow` has it. `tearsheet.py` and `risk_profiler.py` both delegate to it;
they used to hold two copies of every formula that disagreed on the units of `ror`.

*Enforcer*: `tests/test_institutional_metrics.py` runs the spec's **own ten worked systems**
(the deleted spec's §13, preserved as `SPEC_SYSTEMS`) through the grader. That is the only way to check a grader that would otherwise
be checked against itself — and it is what found both defects below.

> **Two corrections, decided 2026-09-04.**
>
> **Combined Edge is scale-free.** The spec contradicts itself: §5 gives `CE = EV_R × PF`,
> while §13's P5 quotes CombinedEdge **357** for EV $146 / PF 2.44 — which is `EV$ × PF`.
> The grading scale (A>150 … D>20) belongs to the dollar reading. The code took the
> *formula* from one and the *grades* from the other, so **all ten spec systems graded F,
> including its A+ exemplar**. Resolved to the normalised form, because the dollar form
> grades the *account*: one strategy at EV_R 0.10 / PF 1.15 under a constant 1% risk policy
> scores **D on $25k and A on $250k**. Thresholds are converted by ÷225, the spec's own
> worked risk-per-trade — a units conversion, not a new opinion.
>
> **Ruin is the prop trailing drawdown, not the account.** §6 says "zero **or blowout
> threshold**"; the code read only the first half and used `account_size / risk_per_trade`
> as the exponent (~200–400). Any base < 1 raised to that underflows, so across the spec's
> ten systems the distinct RoR values were exactly **{0.0, 1.0}** — the four bands
> (<1% / 1–5% / 5–20% / >20%) were **unreachable**. The exponent is now
> `max_trailing_drawdown / risk_per_trade` from the primary prop profile (Apex 50K:
> $2,500 → ~11–19 units), and the bands separate.
>
> ⚠️ **Known limit, tested and pinned**: CombinedEdge is not a probability, so the closed
> form clamps at 0.99 and **saturates** — every system at or above that reports the same
> RoR. It stays discriminating where decisions are hard (marginal systems) and saturates
> towards *safe* for systems already strong on CE and SQN. **Do not rank strong systems by
> RoR**; use `PropFirmSimulator`.
>
> **Every risk of ruin must be printed with its basis.** The same trades read 0.00% against
> the account and ~20% against a trailing drawdown. The tearsheet now prints
> `measured against: <profile> = N losing trades`.

#### The metric definitions

Formulas and thresholds, subsumed from "The Edge System" master guide. `risk_per_trade`
(`$R`) is defined **first** — every other metric depends on it.

| Metric | Formula | Grades |
|---|---|---|
| **EV** | `Win% × AvgWin − Loss% × AvgLoss` | A >$100 · B ≥$50 · C ≥$10 · D >0 · F ≤0 |
| **PF** | `GrossWins / GrossLosses` | A ≥2.0 · B ≥1.4 · C ≥1.1 · D ≥1.0 · F <1.0 |
| **EV_R** | `EV$ / $R` | — (the normalised expectancy) |
| **Combined Edge** | `EV_R × PF` | A >0.667 · B ≥0.444 · C ≥0.222 · D ≥0.089 · F below |
| **SQN** | `(mean(R) / stdev(R)) × √N` | A ≥3.0 · B ≥2.0 · C ≥1.6 · D ≥1.0 · F <1.0 |
| **DRR** | `MaxDD% / RiskPerTrade%` | A <4 · B ≤7 · D ≤10 · F >10 |
| **Risk of Ruin** | `((1−CE)/(1+CE)) ^ Units`, `Units = ruinDistance / $R` | Professional <1% · Acceptable ≤5% · Dangerous ≤20% · Lethal >20% |
| **Max losing streak** | `ln(N) / ln(1/LossRate)` | the psychological load, not a grade |
| **MAE / MFE** | worst/best excursion, in **%** (ADR-002) | low MAE ⇒ tighter stops; MFE ≫ AvgWin ⇒ exiting too early |

**Position sizing follows the grade** — this is what makes the grades load-bearing rather
than decorative: **A** 2–5% · **B** 1–2% · **C** 0.5–1% · **D** 0.25–0.5% · **F** do not
trade.

**When a metric fails, move the lever attached to it**, don't guess:

| Failing | Fix 1 | Fix 2 | Fix 3 |
|---|---|---|---|
| EV | increase AvgWin | reduce AvgLoss | better entry filters |
| PF | remove outlier losses (MAE control) | tighten the stop | capture more MFE |
| Combined Edge | improve EV or PF | reduce AvgLoss | reduce risk per trade |
| **RoR** | **reduce risk per trade** | improve PF | reduce drawdown |
| Max drawdown | reduce risk per trade | increase AvgWin | improve Win% |
| Losing streak | improve Win% | reduce risk | skip chop periods |

> Each formula carries an assumption worth stating: **EV** assumes the win/loss profile is
> stable; **PF** assumes losses stay consistent, and lies when there are outlier losses;
> **RoR** assumes trades are independent, and real markets cluster losses; the **streak**
> formula assumes no regime shift. A high win rate can hide a terrible EV, and a strong PF
> can sit on top of an intolerable drawdown — read them together, never one alone.

#### The metric table 🟡 CONVENTION

| Metric | Definition here | Watch out |
|---|---|---|
| Win rate % | wins / trades, per **leg** once §6.3 lands | changes when the leg convention lands — restate, don't compare across it |
| Profit factor | gross profit / gross loss | `NaN` when there are no losses; do not render as `0` |
| Expectancy (EV) | mean $ per trade | graded A–F by `_grade_ev` |
| SQN | system quality number | high SQN with an F drawdown grade is not a good system |
| Max drawdown % | on the equity curve | which equity curve — see §7.3 |
| Sharpe | daily returns × √252 | meaningless below ~30 trading days |
| R multiple | points / initial risk | requires §2.2 geometry to be valid at all |
| MFE / MAE | excursions, in **%** | ADR-002: report as price percentage, not absolute points |

### 7.3 Two rules for every report 🔴 NOT BUILT — this is the highest-value gap

1. **A report must name its inputs**: strategy, ticker, date range, parameter set, data
   hash, run id, price basis. One that cannot is not evidence.
2. **A report must refuse to exist when it has nothing to say.**

> Both are violated today, and the committed outputs prove it.
> `reporting/outputs/tearsheet_NQ1_box_reversion.md` is **2 bytes** and contains the word
> `ok` — a strategy that emits no signals produced a file that reads as a report.
> `tearsheet_NQ1_ict_displacement.md` reports **Net P&L $178,574.47** beside **Final
> Balance $750.80** and a **74,980% total return** beside a peak equity of $795, because
> the prop-firm balance and the equity-curve return are two different accounts rendered as
> one. It names no strategy, no date range, no parameters, and no data.

Plan §2.6 wires the reporters to consume the run record. Until then, **treat every file in
`reporting/outputs/` as undated and unattributed**.

---

## 8. Step 7 — Store the result

| What | Where | Commit? |
|---|---|---|
| Run record + artifacts | `results/RESEARCH/_pipeline/<TICKER>/<RUN_ID>/` | ❌ no |
| Run ledger (append-only) | `results/RESEARCH/_run_ledger.jsonl` | ❌ no |
| NT8 ground-truth trade lists | `scripts/parity/fixtures/` | ✅ **yes** — this is the corpus |
| Parity fixtures (hash-stamped bars) | `scripts/parity/fixtures/` | ✅ yes |
| Generated tearsheets | run dir | ❌ no — see §7.3 |
| Strategy code, config, C# bot | as §1 | ✅ yes |

🔴 **Never commit a parquet.** A 126 MB one has already blocked 202 commits.

---

## 9. Definition of "validated"

A strategy may be called validated when **all** of these hold. Anything less is a research
result and must be reported as one.

- [ ] Registered, and `hunt()` returns the canonical columns (§2.1) 🟢
- [ ] Zero signals dropped by the geometry gate, or the drops explained (§2.2) 🟢
- [ ] Grid precheck passes — the search can move the answer (§2.6) 🟢
- [ ] Causality probe passes **non-vacuously** (§4.4) 🟢
- [ ] Optimised with `--oos-start`; reported numbers are out-of-sample (§4.1) 🟢
- [ ] Run record is `attributable`, price basis declared (§4.3) 🟢
- [ ] A C# bot exists, deployed by the sanctioned path, and compiles (§3.1, §5) 🟢
- [ ] Layer 1 rule parity green for every shared primitive it uses (§6.1) 🟡
- [ ] An NT8 trade list is **committed** for a pinned range and profile (§5.4) 🔴
- [ ] Trade-set parity meets its stated recall/precision, per-leg (§6.3) 🔴
- [ ] Prop-firm viability via `PropFirmSimulator` only (ADR-021) 🟢
- [ ] Reports name their inputs (§7.3) 🔴 — evaluable only as NOT EVALUATED

This checklist is not prose — `workflow.py` evaluates it on every run and prints it (§0.1).
A criterion it could not evaluate prints **NOT EVALUATED**, which is neither a pass nor a
failure and still blocks `validated` and exit 0.

> **§9 and `CRITERIA` are now tied mechanically.** Until 2026-09-05 this list carried 12
> items while `workflow.py` evaluated 10 — *prop-firm viability* and *reports name their
> inputs* were absent from `CRITERIA` entirely, so two criteria this section calls part of
> "validated" could not block it, and not even as NOT EVALUATED: they simply were not
> there. Both are wired now — `prop_viability` reads the `prop_firm_sim` stage from the run
> record (`workflow.py::_prop_viability`), which had to be added to `run_backtest.py`
> because the prop evaluation ran without being recorded. *Enforcer*:
> `test_workflow_checklist.py::test_section_9_has_exactly_one_checkbox_per_evaluated_criterion`
> parses **this list** and fails if the two ever disagree again.

The 🔴 items are why **no strategy in this repository is validated today**, and saying so
plainly is more useful than a number nobody can reproduce.

---

## 10. Hard-won facts worth not rediscovering

- **`Index.get_indexer(method='bfill')` snaps with no distance limit.** It returns −1 only
  when no later bar exists *at all*, so a signal timestamped weeks outside the frame lands
  silently on a real bar. Bound the snap in **time**, never in bars — between two adjacent
  bars there are no other bars, so a bar-count limit can never bind.
- **`StratCore.WickType` diverges from Python on ≤1-tick bars** — C# `range <= tickSize →
  none`, Python `total_range > 1e-8 → classify`. 24 of 309 cases. Reachable on real NQ
  data. Which side is right is a decision, not a bug fix (§11).
- **A wrong-sided stop books a profit.** Read exit-reason P&L, not summary metrics, when a
  win rate looks impossible.
- **Falsified and withdrawn, with the measurements kept**: intrabar fill ambiguity (≤0.41%
  of trades); `daily_max_loss` truncating losing days (every risk-limit arm identical);
  "most strategies emit zero signals" (mid-grid only — just `box_reversion`);
  `GlobalMergePolicy` gating parity work.
- **`nt_list_strategies` used to read only the top level** of a folder NT8 compiles
  recursively. That is what made "your bots aren't deployed" look true when it wasn't.

### 10.1 The NT8 silent-failure catalogue

**A Strategy Analyzer backtest can return 0 trades with no error at all.** One measured
chain had four independent causes at once:

1. `BarsRequiredToTrade` set inside `OnBarUpdate` — NT8 throws "cannot be set from this
   state" on bar 0 and silently disables the strategy. Set it in `State.Configure`.
2. `RiskGatekeeper` blocking the Strategy Analyzer account, because the AddOn registers
   SA's "Backtest" account with **live** risk limits. Bypass every gate when the account
   name contains `backtest` or `Playback`.
3. A percentage filter double-multiplied by 100, so a 0.5% range was compared against a
   threshold of 1000 and blocked every session.
4. `RequireDirectionBias = true` by default with no bias available, blocking both
   directions.

> ⚠️ **`Print()` output is invisible in a Strategy Analyzer backtest** — it goes to the SA
> UI window only. `Log(msg, LogLevel.Information)` writes to
> `Documents/NinjaTrader 8/log/log.YYYYMMDD.00000.txt`, which is the only way to trace SA
> execution programmatically.

**Over-estimated risk blocks entries on a funded account.** `RiskGatekeeper.potentialLoss`
computed an ATR-based distance (~$143.75 for MNQ) where the actual range-based stop was
~$18 — an **8× over-estimate**, enough to refuse entries against a tight daily loss limit.
`GetPotentialLoss()` is virtual for this reason; each bot's
`GetEstimatedRiskDistance()` must return its *actual* stop geometry.

| Symptom | First check | Then | Then |
|---|---|---|---|
| 0 trades in SA | `BarsRequiredToTrade` in `OnBarUpdate` | gatekeeper blocking the SA account | `RequireDirectionBias` default |
| Over-trading | `PotentialLoss` over-estimate | a percentage filter multiplied twice | `MaxTradesPerDay` unset |
| PF collapses on a longer window | the short window was favourable noise — run OOS | filter over-restriction — ablate | entry-price inflation — check the fill model |
| `Print()` shows nothing | it goes to the SA UI window only | use `Log(..., LogLevel.Information)` | read the NT8 log file, not the Output tab |
| The bridge stops responding | repeated hot-swap compiles crash the SA AppDomain | restart NT8 to reset the SA window | retry |

### 10.2 Diagnosing a divergence

- **Run an empirical tracer before trusting any reasoned diagnosis.** A structured debate
  once settled on same-bar stop/target resolution as the dominant cause; a tracer showed
  NT8's first trade was at 06:34 ET — pre-open Globex — so the real cause was the session
  filter. A plausible mechanism is not evidence that it fired.
- **Ground every diagnosis in the code as it is now.** One diagnosis targeted a stop
  formula the source had already stopped using.
- **Rank the hypotheses rather than picking one**, which is what stops a plausible-but-wrong
  answer from closing the question early.

---

## 11. Open decisions and known gaps

| # | Item | Owner |
|---|---|---|
| ~~1~~ | ~~**Per-leg trade rows**~~ — **DONE 2026-09-04.** `leg1_exit_time` is recorded by both the Rust kernel and its Python mirror; `scripts/parity/legs.py::explode_legs` projects one row per leg and asserts the projection is lossless. Wired into the workflow's parity stage. | done |
| 2 | **`WickType` range guard** — adopt C# (suppress sub-tick bars) and change Python, or the reverse. Recommendation: adopt C#; the wick ratio of a one-tick bar is a quantization artifact, always 0 or 1. **Changes existing `the_strat` results**, so it should land through a recorded run. | **user** |
| 3 | **No CI in this repo at all** — no `.github/workflows`, no `tools/ci_local.py`. Every gate above is green only when someone types `pytest`. | code |
| 4 | Parameter document for the non-ICT families (§3.3) | code |
| 5 | Reports from the run record (§7.3) | code |
| 6 | Freeze the bespoke runners with a gate (§4.1); note an *absence* gate passes silently when code moves — give it a negative control | code |
| 7 | `box_reversion` raises `TypeError: Invalid comparison between dtype=datetime64[s] and Timestamp` when window-filtered | code |

### 11.1 The remaining build order

Subsumed from the phased plan. Ordered by what unblocks what, not by size.

| Phase | Item | State |
|---|---|---|
| **0.2/0.3** | adverse fills already default; **restate the existing prop-firm conclusions on them** — this is where optimism did the most damage, and published numbers may change | 🔴 |
| **1.1** | rank-correlation calibration Python↔NT8 — tells you whether the screen has been lying, and by how much (§12.1: the ranking is what must be preserved) | 🔴 |
| **2.4** | freeze the bespoke runners with a CI check. ⚠️ an *absence* gate passes silently when code moves — give it a negative control | 🔴 |
| **2.5** | arm ledger — log **every** arm ever tested, including abandoned ones. Deflated statistics need N, and the optimisation summary (§7.1) now emits the per-trial table | 🟡 partial |
| **2.6** | reports generated from the run record only (§7.3) | 🔴 |
| **3.1–3.3** | per-contract-month data on both sides; roll-warmup rule; bar-completeness precondition | 🔴 |
| **3.4** | tick-on-demand resolution for finalists — the NT8 tick database is an unused asset | 🔴 |
| **4.2** | committed NT8 ground-truth corpus **with bracket exits** (§5.4) | 🔴 |
| **4.3** | trade-set parity as a CI gate (§6.3) | 🔴 |
| **4.4** | detector golden corpus — `nt_indicator_values` per bar, asserted bar-for-bar, so a red names the first divergent bar (§6.2) | 🔴 |
| **5.1** | parameter document for the non-ICT families (§3.3, §12.3) | 🔴 |
| **5.3** | collapse the execution paths | 🔴 |
| **6.1** | audit `ml/walk_forward.py` — `walk_forward_split` has **no purge and no embargo** and is deprecated; confirm nothing still calls it | 🔴 |
| **6.2** | deflated metrics / probability of backtest overfitting | 🔴 |
| **6.3** | survivor selection on low mutual correlation | 🔴 |
| **7.1** | NT8 Optimizer support in the bridge (the bridge cannot drive it today) | 🔴 |

---

## 12. Decisions that shape all of this

Carried from the design record. These are settled; reopening one needs new evidence, not a
new preference.

### 12.1 The funnel

Python is a **screen**, not a verdict. It sweeps ~200 variants; NT8 decides. What Python
must preserve is therefore the **ranking**, not the absolute numbers — a screen that
reorders candidates is broken even if every metric is close. Prop-firm feasibility has the
*opposite* requirement: there, absolute drawdown matters and optimism is the failure mode,
which is why the adverse intrabar path is the default.

### 12.2 What is shared, and how

Shared logic is written **once in C#** as a platform-free core (`ninjatrader/shared/`) and
mirrored in Python, with a differential test holding the two together (§6.1). Not the
reverse: NT8 is authoritative, so the C# side is the original.

### 12.3 The port problem, and the deliberately limited answer

**strategy = (C# bot class) + (parameter document).** One JSON read by both sides. The hard
line: the document expresses **composition, never computation**. Anything needing arbitrary
computation becomes a new primitive written once in both languages. This is explicitly
**not** a strategy DSL — that path dies by growing into a programming language.

### 12.4 Rejected, with reasons

| Rejected | Why |
|---|---|
| A shared **Rust** core inside NT8 | silent marshalling errors in the very component built to end cross-checking, and no hot-swap. If one implementation is ever wanted it goes in **C#** |
| `nautilus_trader` | a third opinion on execution; does not address Python↔C# signal drift |
| A full strategy DSL | see §12.3 |
| NT8 as the only simulator | kills vectorized research and sweeps (ADR-022); the Strategy Analyzer is slow and crash-prone |
| Point-P&L parity with the Strategy Analyzer | SA does not reproduce live fills either. **Trade set → SA; economics → Sim101** |

---

## 13. What this document replaced

**Ten documents** — nine deleted 2026-09-04, the engine spec 2026-09-05.
`git log --follow` has every one of them.

| Deleted | What moved here | What was dropped, and why |
|---|---|---|
| `NT8_PYTHON_PARITY_STANDARD.md` (603 ln) | the six-part parity checklist (§6.4), the NT8 silent-failure catalogue (§10.1), the diagnosis rules (§10.2) | its sessions 8/9/10 logs — **duplicated** in `SESSION_9_HANDOVER.md` / `SESSION_10_HANDOVER.md`; its file-reference table — 2 of 4 sampled paths deleted by ADR-025 |
| `STRATEGY_DESIGN_STANDARD.md` (88 ln) | the `hunt()` contract (§2.1), hunters-vs-execution and the vectorization rules (§2.3), the engine contract (§2.7) | its ADR-017 gate, which named `lifecycle_runner` — not the sanctioned entry point |
| `BACKTEST_PARITY_ARCHITECTURE.md` (411 ln) | the decisions: the funnel, what is shared, the port problem, and what was rejected (§12) | its evidence section — a snapshot of defects now fixed, and its numbers were superseded within the same week |
| `STRATEGY_EVALUATION_PIPELINE_PLAN.md` (463 ln) | the remaining build order (§11.1) | the closed phases. A plan that keeps its finished items becomes a place where status rots |
| `RISK_PROFILE_DEFINITIONS.md` (302 ln) | every formula, threshold, the fix table and position-sizing-by-grade (§7.2) | its teaching narrative. **Its ten worked systems live in `tests/test_institutional_metrics.py`**, which is a stronger home — they now fail a build |
| `REPORTING_METRICS.md` (55 ln) | nothing new — it was a lossy derivative | it propagated the Combined Edge formula/threshold contradiction that graded every system F |
| `RESEARCH_FRAMEWORK.md` (54 ln) | nothing | described `FrameworkLoader` and a `data/loader.py` that **do not exist**, and a "7-layer protocol" no code implements |
| `CLI_USER_GUIDE.md` (61 ln) | nothing | documented `run_backtest.py` as the CLI; superseded by §0.1 |
| `HARMONISED_TRADING_ARCHITECTURE.md` (49 ln) | the three pillars and their prohibitions (§1.1) | its data-flow diagram, restated in one line |
| `BACKTEST_ENGINE_ARCHITECTURE.md` (2,553 ln) | the code conventions (§2.8), the three risk modes and the fact that nothing reads them (§2.9), and the library map extended to the data / feature / execution / portfolio / config layers (§2.4) | **~2,000 lines of skeleton source.** It was a code-generation spec, and the code it specifies now exists — a spec kept beside its implementation is a second, non-executing copy that drifts. Its `StrategyBase` interface and `FeatureRegistry`-resolves-features design are dropped as **contradicted**, not compressed |

### Why none of them could stay as appendices

`NT8_PYTHON_PARITY_STANDARD.md` was first tried as an "appendix of traps" with a redirect
banner. It did not work: it still opened with *"MANDATORY — all new strategies MUST comply
before being declared validated"*, so a reader arriving cold got **the older answer,
because it was the one that said MANDATORY**. An appendix that contradicts the canonical
document is not an appendix — it is a second source of truth with a lower profile, which is
worse than an obvious one.

### Claims they made that were false

Kept because the shapes recur, and every one of them survived by nobody re-deriving it.

- **"Purged Walk-Forward Cross-Validation to prevent data leakage"** — while
  `walk_forward_split` is marked `DEPRECATED — expanding-window split with NO purge and NO
  embargo`. **A document claiming a safety property the code explicitly denies having.**
  Worse than silence, because it stops the reader checking.
- **`FrameworkLoader` / `trading_framework/data/loader.py`** — neither the class nor the
  directory ever existed at that path.
- **"fully interactive HTML tear sheets"**, `Lifecycle_Test_IS_tearsheet.html` — the
  tearsheet is markdown, and no code has ever produced those filenames.
- **"Layers 2 & 3 splice macro catalysts from SQLite/Prisma"** — no such code exists.
- **Class E** conflated contract month with price basis. A constant price offset *is* the
  adjustment basis and is invariant under the geometry test (§6.3); a different **contract
  month** changes which trades exist. Both halves are stated correctly in §6.4.
- **Combined Edge**: formula from one reading, thresholds from another — so the metric
  graded the spec's own A+ exemplar F (§7.2).
- **`StrategyBase(ABC)` with `generate_signals` / `get_required_features` /
  `get_search_space`** — a full abstract interface, specified in prose, that **no strategy
  has ever implemented.** All 15 registered strategies implement `hunt()` +
  `get_param_grid()` (§2.1), and `scripts/strategies/base.py` is still a three-line stub
  reading *"Pending implementation as per IMPLEMENTATION_SPEC.md"* — **a file that does not
  exist.** Two interfaces for the same thing, one of them dead, and the dead one was the
  documented one.
- **`data/parquet/<SYMBOL>_1m.parquet`** — the store is `data/<TICKER>_1m.parquet` plus
  `data/live/live_storage_-{ticker}.parquet`, and the split between them matters (§4.2).
- **`scripts/libs/`** throughout its directory tree — the package is `scripts/libs_py/`.
  A path that is *almost* right is worse than a missing one; it reads as verified.

### What is deliberately NOT here

- **`scripts/trading_framework/README.md`** — a package *map* (what each module is), not a
  procedure. It defers here for anything procedural.
- **Dated session handovers** (`SESSION_9`/`SESSION_10`) — records of what was true on a
  date. Rewriting a record to match today is how a history stops being evidence.
