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

### The defaults 🟢 ENFORCED (measured from `build_parser()` 2026-09-05)

**Only `--strategy` is required.** Re-derive this table rather than trusting it:
`python -m scripts.trading_framework.workflow --help`.

| Flag | Default | Read this before relying on it |
|---|---|---|
| `--strategy` | *required* | resolved through `STRATEGY_FACTORY_REGISTRY`; an unregistered key cannot run |
| `--ticker` | `NQ1` | ⚠️ **selects the point-value multiplier** ($20/pt NQ, $50 ES, $2 MNQ). A wrong ticker scales every P&L figure and nothing says so (§2.7) |
| `--price-adjustment` | `undeclared` | ⚠️ **there is no honest default, so the default is a refusal.** `undeclared` records honestly, warns, and **FAILS the `attributable` criterion** — pass one of `unadjusted` / `back_adjusted` / `ratio_adjusted` |
| `--engine` | `nt8_parity` | the bracket/leg engine — the right default, since anything compared to NT8 needs it. `vectorized` is faster and not leg-aware |
| `--config` | `config/sessions.yaml` | |
| `--optimize` | off | |
| `--trials` | `20` | the §0.1 example uses 200; 20 is a smoke-test budget |
| `--oos-start` | none | **required with `--optimize`**, refused at parse time |
| `--nt8` | off | adds the NT8 validation + trade-set parity stages |
| `--nt8-trades` | none | the capture CSV |
| `--nt8-tz` | none | ⚠️ no default. Read from the fixture's `.meta.json`, else the run refuses |
| `--bar-seconds` | none | ⚠️ no default *since 2026-09-05*. It is the entry-bar join key; read from the fixture's `barSeconds`, and a flag that **contradicts** the fixture now raises instead of warning |
| `--min-recall` / `--min-precision` | `0.95` / `0.95` | trade-set parity thresholds (§6.3) |
| `--bot` | derived | PascalCase + `Bot` from the key, else `BOT_ALIASES` |
| `--skip-rule-parity` | off | recorded as a SKIP **with its reason**, never as a pass |
| `--allow-unattributable` | off | |

> **Two of these were traps until 2026-09-05.** `--price-adjustment undeclared`
> passed the `attributable` criterion whose own text reads *"and the price basis is
> declared"* — it counted missing fields and refusals, and an undeclared basis is
> only a *warning*. And `--bar-seconds` defaulted to `300`, so a 5-minute join key
> against a 1-minute capture mis-buckets **every** trade while the run still prints
> a parity verdict — a red meaning "wrong join", indistinguishable from a red
> meaning "different trades".

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

### 1.3 The frozen defaults — every strategy inherits these 🟢 ENFORCED

`scripts/trading_framework/config/trading_defaults.json` is the ONE document for
everything that is not the trade setup. One source, three consumers: the Python
engine (via `config/defaults.py`), the C# bot, and the NT8 Strategy Analyzer.

| Group | Frozen value |
|---|---|
| **Instrument** | default **MNQ**; micros are the traded class (ADR-009). `MNQ` $2/pt, `MES` $5/pt, `NQ` $20, `ES` $50. Tick 0.25 throughout |
| **Data ticker vs contract** | `NQ1` → **MNQ**, `ES1` → **MES**. A data ticker names a *price series*; an instrument names the *contract you trade* |
| **Sessions** | `GLOBEX 18:00` · `ASIA 20:00` · `LONDON 02:00` · `NY_PRE 08:00` · `NY_AM 09:30` · `NY_LUNCH 11:00` · `NY_PM 13:30` · `CLOSED 16:00–18:00`, ET. Every session but `CLOSED` is tradeable |
| **Risk** | 1 contract, 1 concurrent position, primary prop profile `apex_50k`, ruin fraction 0.20. **Invariant: hard exit 16:00 ET (ADR-020)** — no exemptions. *Overridable*: `flattenByEt` (15:45). ***Analysis-derived, deliberately unset***: `maxTradesPerDay`, `maxTradesPerSession`, `lastEntryEt` |
| **Execution** | 1 tick slippage, $0.62/contract round trip, `OnBarClose` |
| **NT8** | `MergeNonBackAdjusted`, tick replay off, `OrderFillResolution High`, commission on |

> **Three kinds of value, and my first version called them all one.**
>
> | Kind | Fields | Rule |
> |---|---|---|
> | **Invariant** | `rthHardExitEt` 16:00 | ADR-020. A safety limit, not a tuning choice. Enforced with **no exemptions**, and every exit must be ≤ it |
> | **Overridable** | `flattenByEt` | a strategy may set its own, recorded in `known_bot_divergences.py` and ticketed in the bot backlog |
> | **Analysis-derived** | `maxTradesPerDay`, `maxTradesPerSession`, `lastEntryEt` | **deliberately null.** These are OUTPUTS |
>
> **An entry may happen at any time.** The first version froze `lastEntryEt` at 14:30,
> which would have forbidden a deliberate NY_PM setup — and `BBMRReversionBot` is
> exactly that, entering to 16:00 by design, as its own source says: *"// Time — NY_PM
> only (matches Python v3: 13:30-16:00)"*. Reporting is partitioned by session (§7.1),
> and **when a bot should run is a decision taken *from* those results, not a constraint
> imposed before them.**
>
> **A trade cap is a conclusion, not a setting.** `sessions.yaml` carried
> `max_trades_per_day: 3` with no recorded basis. `reporting/trade_ordinal.py` now
> reports EV_R and win rate by trade ordinal — within the day and within the session,
> marginal *and* cumulative — so the cap can be read off the data. It prints a
> suggestion **with its sample size** and refuses to endorse one below 20 trades,
> because a cap chosen from five observations is noise wearing a number.
>
> Measured across the twelve bots: **five** different flatten times and **six** different
> daily trade caps, every one hand-set, none compared to the Python engine that predicts
> its trades. One was a real ADR-020 violation — `BBMRReversionBot` flattened at **16:15**
> — and was fixed in the repo rather than recorded. ⚠️ **The DEPLOYED copy is still 16:15**
> (§11 item 20), so fixing a source file is not the same as fixing a bot. The rest are
> inventoried in `tests/known_bot_divergences.py`, which freezes the spread so it cannot
> grow: a bot not in it must match, a bot in it may only move *toward* the frozen value,
> and one that now agrees must lose its line — `EMAPullbackBot` lost its line on
> 2026-09-05, which is the mechanism working. **`BBMRReversionBot` still allows 99 trades
> a day where `mean_reversion` now caps at nothing at all** (it enforced 3 until
> 2026-09-05, when the engine started taking the cap from `risk.maxTradesPerDay: null`) —
> that pair is not comparable at the trade-set layer either way.

*Enforcers*: `config/defaults.py::resolve_instrument` **raises** on an unknown
ticker rather than defaulting; `assert_sessions_partition` refuses a window set
that is not a partition; `tests/test_frozen_defaults.py` (30 tests) scans for a
second point-value table, checks both engines agree, and cross-checks the `nt8`
block against `parity/backtest_profile.json`; `tests/test_bot_defaults.py` (23 tests)
regenerates `TradingDefaults.cs` in memory and fails if the committed file has drifted,
parses the C# **back** so the generator cannot vouch for itself, and hard-fails any bot
exiting past 16:00 regardless of the inventory.

> **What this replaced, and what it cost.** There were **three** point-value
> tables. `core/backtest_engine.py` said `NQ1: 20.0`, `core/nt8_parity_backtester.py`
> said `NQ1: 20.0`, and `config_loader.py`'s ADR-009 scaler said `NQ: 2.0` — while
> `run_backtest.py` asked `point_value.get("NQ1", 2.0)`, and **`NQ1` was not a key
> in either config table**, so it took the fallback. The result: *one run valued a
> point at $20 in the P&L and $2 in the prop-firm simulation.* Measured on
> `mean_reversion`/NQ1 the correction moved net P&L **$1,520 → $112** and the Apex
> 50K pass rate **22.4% → 0.0%**. It is not a 10× rescale: commission is unchanged
> per contract, so on a micro it bites ten times harder — which is the whole point
> of grading on the instrument you actually trade. **The 22.4% was a fiction**
> produced by feeding mini-sized dollars to a micro point value.
>
> Two silent defaults were removed alongside it: `backtest_engine.py` valued an
> unrecognised ticker at **$1/pt** (`.get(ticker, 1.0)`), and
> `nt8_parity_backtester.py` chose its tick size by **substring** —
> `0.25 if ("NQ" in ticker or "ES" in ticker ...) else 0.01`, which worked for
> `MES` only because "MES" contains "ES".

> **The legacy session labels are still there.** `session_tagger`'s `session` and
> `session_block` columns are RTH-only — GLOBEX, ASIA and LONDON all collapse into
> `pre_market`, so three of the six sessions the bot trades were *unlabelled*, not
> merely unreported. `session_name` is the frozen partition and the one to build
> on. The legacy columns are deliberately untouched, because changing them would
> silently change every existing strategy's behaviour; migrating them is §11.

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
| Point value, tick size, sessions, risk defaults | `trading_framework/config/defaults.py` | **a table of your own.** There were three, and they disagreed (§1.3) |
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

**`risk_params` MUST carry `ticker`** 🟢 — the engine resolves the instrument from it
through `config/defaults.py::resolve_instrument` (§1.3).

> ⚠️ **This marker was false until 2026-09-05.** Both engines read
> `risk_params.get('ticker', 'NQ1')`, so a caller that omitted it got NQ1's multiplier
> applied to whatever it was actually trading — the exact failure the paragraph claimed
> was enforced against. Both now raise. *Enforcer*:
> `test_frozen_defaults.py::test_both_engines_refuse_a_run_that_did_not_declare_its_ticker`. Every P&L figure produced that way was wrong by
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


### 2.10 Report the criteria you evaluated 🟢 ENFORCED

A `hunt()` that returns signals and nothing else cannot say **why** it took them or why it
skipped the rest. Set `self.last_decisions` from a `GateRecorder`; the `hunt()` signature
does not change and `HunterStrategyAdapter` forwards it.

```python
self.last_decisions = (
    GateRecorder(data.index, run_id="", strategy="mean_reversion")
    .trigger(long_mask, "long").trigger(short_mask, "short")
    .measure("band_excursion_atr", (data['close'] - band).abs() / data['atr'])
    .gate("first_signal_of_day", is_first)
    .to_frame(signal_prefix="mr_"))
```

**It takes masks, not a loop** — a zero-loop hunter (§2.2) has no per-decision hook, and a
row-wise API guarantees it goes uninstrumented. The verdict is *computed* from the gates,
so a hunter cannot record one that disagrees with its own masks.

The six rules, the `gate` / `measure` distinction and the roster diff are **§5.5**. Read
them before writing the calls: `and` short-circuits, so the conditions must be lifted out
of an existing `if` chain deliberately rather than copied.

*Enforcer*: `tests/test_instrumentation.py` — behavioural, it calls `hunt()` and looks.
The fourteen uninstrumented hunters are frozen in `tests/uninstrumented.py` and the list
may only **shrink**, so a new strategy is instrumented from its first commit.

**Instrumenting `mean_reversion` — the reference — immediately showed that
`first_signal_of_day` blocks 99.2% of its setups**, and that its real trade cap is 1/day
while `sessions.yaml` said 3 and its bot allowed 99. That is the class of thing this
surfaces on the first run.


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

### 3.4 The governance base class — `GovernedStrategy` 🟢 ENFORCED

**A new bot inherits `GovernedStrategy` and writes no logging code at all.** It gets
the decision log, the frozen defaults and unique entry names by construction.

```csharp
public class MyBot : GovernedStrategy
{
    protected override void OnEvaluate(SetupEvaluation e)
    {
        e.Trigger(close < lower, "long");           // is there a setup at all?
        e.Gate("adx", adx >= AdxThr, adx, AdxThr);  // a criterion that can BLOCK
        e.Gate("not_lunch", !inLunch);
        e.Measure("band_excursion_atr", dist / atr); // a magnitude, never blocks
    }
    protected override string GetStrategyName() { return "MyBot"; }
    protected override void ConfigureStrategy() { /* indicators */ }
}
```

That is the whole contract. No orders, no clock, no file handles, no `Print`.

#### Why a base class and not a helper

Ten of the fourteen bots **already** inherit `RiskManagerBase`, and tickets B1–B6
exist because those same ten hardcoded their own flatten times and trade caps
anyway. **A default a bot is free to restate is a default it will restate.** The
distinction that matters:

| | |
|---|---|
| a helper the bot **calls** | the bot can log one thing and do another, and nothing notices |
| a base that **decides** | there is no code path by which an unlogged criterion reaches a trade |

`RiskManagerBase` asks its subclass exactly one question — `CheckForSignal()`,
returning 1 / −1 / 0. **`GovernedStrategy` seals it.** The return value is
*computed* from the declared gates rather than supplied alongside them, so a gate
that is not logged does not exist. `SetupEvaluation` deliberately exposes nothing
that can enter, exit, move a stop or open a file — enforced by
`test_the_mandated_structure_cannot_place_an_order`.

#### Ownership — the parent is not ours

ADR-025, one artifact one owner:

| Class | Owner | Responsibility |
|---|---|---|
| `RiskManagerBase` | **nt8-riskguard** | the bar loop, brackets, stops, sizing, the risk gates |
| `GovernedStrategy` | **this repo** (`scripts/ninjatrader/shared/`) | the workflow's rules |

⚠️ There is a **second, tracked copy** of `RiskManagerBase.cs` in this repo under
`docs/strategies/…/risk_manager_suite/`, carrying three unlanded improvements. It
is a fork, it is invisible to `sync_nt8_strategies.py` (which allowlists the
filename as external), and reconciling it is **ticket B9** — a decision, since all
three change live bot behaviour.

#### What it governs

| # | Rule | How, and why it is not left to the bot |
|---|---|---|
| 1 | **ADR-020's 16:00 hard exit** | The frozen defaults are pushed in *before* the bot's `OnStrategyDefaults()`, and the hard-exit clamp is re-applied **after** — so a bot that sets a later flatten time is corrected, not trusted. `BBMRReversionBot` flattened at 16:15 for an unknown period |
| 2 | **A null cap is `NoLimit` (−1)** | `RiskManagerBase` compares `todayTradeCount >= MaxTradesPerDay`, so `0` reads as *no trades allowed* and `int.MaxValue` vanishes into arithmetic. A null cap is simply **not assigned** |
| 3 | **Unique entry signal names** | `RiskManagerBase.GetSignalName` returned `"<Strategy>_Long"` for *every* long entry ever taken — and that string is `Execution.Name` on the fill, the only join key back to the decision. Now overridden per entry; the base's `_Queen` / `_Runner` suffixes then give one bracket's legs a shared key, which is exactly what the leg convention needs (was ticket B7) |
| 4 | **Its own refusals are gates** | Recorded under the frozen names in `trading_defaults.json → governance.gates`, generated into `TradingDefaults.Gate*`. Frozen because the Python reader groups on these strings: a rename on one side alone splits one gate into two rows that never compare |
| 5 | **`CanEnterTrade`'s nine refusals** | gatekeeper · account blown · done for day · paused after consecutive losses · max trades · two time fences · two daily-loss limits. Each was computed and surfaced **only** under `DebugMode && CurrentBar % 100 == 0` — off by default, 1% of bars when on. So a bot that quietly stopped trading had nine possible causes and no record of which. `OnEntryBlocked` (added upstream, gated by `check_entry_refusals_reported.py` with five negative controls) turns each into a logged gate |

Rule 5 is the C# half of the funnel gap §11 item 13 records for Python. **A refusal a
consumer cannot read is indistinguishable from the strategy simply not having a
setup.**

#### Instrumentation is the default; the exceptions are a shrinking list 🟢 ENFORCED

Fifteen strategies are registered and **one** is instrumented, so a blanket rule
would fail fourteen times and be switched off within a day. Instead
`tests/uninstrumented.py` freezes the population, and
`tests/test_instrumentation.py` enforces:

* a strategy **not** on the list that emits no decision log **fails**
* one on the list that now emits one **must lose its line**
* so a **new** strategy is instrumented from its first commit, because there is
  nowhere to add it without saying so in the same edit

The Python check is **behavioural** — it calls `hunt()` and looks at
`last_decisions`, because an import of `GateRecorder` that is never called would
pass a source scan. The C# check is a source scan for the *derivation*, and that
is sound precisely because `CheckForSignal()` is sealed: deriving is the whole
condition.

### 3.5 How a bot is tested — and what cannot be tested here 🟡 CONVENTION

**Nothing in this repo compiles NinjaScript.** Every bot names `NinjaTrader.*` types, so
there is no unit test of a bot's logic and there will not be one without a harness that
stubs the platform. That is the constraint every line below works around, and the reason
the evidence is layered rather than direct.

| Layer | What it proves | Enforcer |
|---|---|---|
| **Source gates** | the bot derives from `GovernedStrategy`; no bot exits past ADR-020's 16:00; no bot sets a flatten time outside the recorded inventory; the generated files match their source | `tests/test_instrumentation.py`, `test_bot_defaults.py`, `test_base_class_ownership.py` |
| **Parse check** | the file is valid C# | `nt8-riskguard/tools/check_window_parses.py` pattern; ⚠️ **not a compile** — type errors are out of scope by design |
| **Compile** | it builds | `nt_compile`. ⚠️ **Read the return.** Hundreds of errors can come back while `nt_health` reads healthy, because NT8 keeps serving the **last good assembly** — the only symptom is a deploy that appears to do nothing |
| **Rule parity** | the bot's rules match Python's, per rule | §6.1. Built for `the_strat` only (2 of 7 families) |
| **Gate roster diff** | both sides evaluate the same criteria | §5.5. Free, no NT8 needed, and **meaningless until a bot emits a log** (§11 item 16) |
| **Trade-set parity** | the same trades exist | §6.3. Harness built, not yet a gate |
| **Behaviour** | what it actually does | `nt_backtest` under the frozen profile (§5.0/§5.2), captured automatically |

**The honest summary**: a bot's *structure* is gated mechanically, its *rules* are gated
for one family, and its *behaviour* is only observable through NT8. So the presumption in
§0 holds — **NT8 is authoritative for behaviour** — and a disagreement is investigated
starting from the assumption that Python is wrong.

⚠️ **A source gate needs a negative control.** A regex cannot see reachability: a call
inside a comment or an `if (false)` has three times been reported as WIRED in this
project's sibling repos. Every gate added here asserts the failing direction too.


---

## 4. Step 3 — Run the Python backtest

### 4.1 The one entry point 🟢 ENFORCED — the population is frozen

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

**A 33rd bespoke runner now fails a test.** 🟢

*Enforcer*: `tests/test_no_new_runners.py`, against the inventory in
`tests/frozen_runners.py`.

> ⚠️ **The inventory is a `.py` and not a `.txt` on purpose.** It was written as
> `frozen_runners.txt`, and `.gitignore` carries a blanket `*.txt`, so `git add` dropped
> it **without failing** and the gate would have errored on every fresh clone. A gate whose
> data is untracked is not a gate. `test_the_inventory_is_populated_and_tracked_by_git`
> now asserts both `git check-ignore` and `git ls-files` on it. The same blanket-extension
> hazard on `*.csv` was hiding the NT8 ground-truth capture (§5.4) — fixed in the same
> commit with a negative-ignore rule. **It matches on behaviour, not on the filename**: a module
counts as a runner if it names a backtest engine (`VectorizedBacktester`,
`NT8ParityBacktester`, `BacktestEngine`, `run_research_pipeline`) *and* is executable
(`__main__` or an `ArgumentParser`). Two modules are sanctioned — `workflow.py` and
`run_backtest.py`; **32** others are frozen. Deleting one is allowed: drop its line in the
same commit, which `test_the_inventory_has_no_stale_entries` requires.

> **Why not freeze `run_*.py`.** That was the obvious gate and it would have been nearly
> vacuous. There are **51** `run_*.py` files under `scripts/`, of which only **6** drive
> an engine — and **26** modules that *do* drive one are not named `run_*` at all
> (`analysis/bb_grid_optim.py`, `research/verify_mtf_framework.py`, …). A filename gate
> freezes 6 and lets 26 keep breeding under any name. This is also why the old "35 bespoke
> `run_*` scripts" figure reproduced from no denominator: 35 was roughly the *behavioural*
> count, attached to the *filename* description.
>
> **Three negative controls keep it non-vacuous**, because an absence gate passes silently
> when the code it inspects moves — this repo has had four of those. The sanctioned pair
> **must** be detected (a rotted pattern fails there first, loudly); a synthetic runner in
> a temp tree must be detected; and a library that merely *imports* an engine must **not**
> be, so the filter cannot match everything. Verified by planting a real file in
> `scripts/analysis/` and watching the gate name it.

Do not extend the frozen scripts, and do not copy their pattern.
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

### 5.0 The capture is automated 🟢 ENFORCED

`--nt8` **captures the NT8 run itself.** It resolves the paired C# bot class, POSTs to the
bridge at `localhost:7890/api/backtest` under the frozen profile, and writes the trade list
plus a `.meta.json` into the run directory as recorded artifacts.

```powershell
.\.venv\Scripts\python.exe -m scripts.trading_framework.workflow `
    --strategy mean_reversion --ticker NQ1 --price-adjustment unadjusted `
    --nt8 --nt8-symbol "MNQ 12-26" --nt8-from 2025-01-01 --nt8-to 2025-06-30
```

`--nt8-trades` still accepts a hand-made CSV; it is now the exception, not the procedure.
This used to read *"live capture is not driven from this process"* and tell the operator to
run `nt_backtest` by hand — a manual step inside the procedure whose whole point is one
command, when the bridge had an HTTP endpoint and a token on disk the entire time.

*Enforcer*: `scripts/parity/capture_nt8.py`, three refusals, each for something that has
happened — `tests/test_nt8_capture.py` (17 tests) drives all of them without touching NT8.

| Refusal | Why |
|---|---|
| **`len(trades) == maxTrades`** | indistinguishable from a TRUNCATED list. The MCP tool's own default is **50**, so a 300-trade backtest returns 50 and looks complete; recall against a truncated ground truth is a false red that reads as a strategy defect. The capture asks for 5000 and refuses on equality rather than guessing |
| **`effectiveStrategy` != requested** | the Analyzer window is REUSED, so an unresolved name leaves whatever was loaded. Those trades are not evidence about the strategy asked for |
| **any bridge `error`** | `requireGlobals` are asserted, never written. A `MergeBackAdjusted` box silently rescales every price; the reason is surfaced instead of an empty result |

`--nt8-symbol` has **no default**: NT8 needs a *contract*, and the contract **month** changes
which trades exist (§6.4), so it cannot be derived from `--ticker`.

### 5.4 Commit the trade list 🔴 LARGELY NOT BUILT

`scripts/parity/fixtures/nt8_trades_<Strategy>_<SYM>_<TF>_<from>_<to>.csv` + a `.meta.json`
naming the profile hash, contract month and price basis.

**Today exactly one exists** (`BollingerCrossOver ES 15m`) and **it has no bracket
exits** — the only exit type the real bots use. Until a corpus exists, no parity claim is
reproducible.

### 5.5 The decision log — why a trade was taken 🟢 ENFORCED (schema + generator)

A trade list says **what** happened. It cannot say **why**, and **no MCP change can make
it**: the criteria live in the strategy and are never handed to the platform. So the
emitter has to be in the strategy, on both sides, writing one format.

**The gate roster is the cheapest parity check there is, and it runs before any trade-set
comparison.** Measured 2026-09-05 on `mean_reversion` / `BBMRReversionBot`, which §6 treats
as one strategy:

| | Criteria evaluated |
|---|---|
| Python `hunt()` | 2 conditions (close vs a Bollinger band), then `groupby('date').head(1)` |
| C# `BBMRReversionBot` | 20 `[NinjaScriptProperty]` parameters; gates for RSI, ADX, squeeze, IB compression, lunch, MACD, Kaufman ER, a 2-bar hook, short-only |

They are **not one strategy with a divergence — they are two different strategies**, and no
recall number between them means anything. `compare_rosters` says so in one call. A
trade-set comparison says "recall 11%" and invites a week of hunting a fill-model bug.

#### How to instrument a hunter

`GateRecorder` takes **masks**, because a zero-loop hunter (§2.2) has no per-decision loop —
handing it a row-wise API guarantees it goes uninstrumented. Set `self.last_decisions`; the
`hunt()` signature does **not** change. `HunterStrategyAdapter.last_decisions` forwards it,
so one property instruments every registered hunter.

```python
self.last_decisions = (
    GateRecorder(data.index, run_id="", strategy="mean_reversion")
    .trigger(long_mask, "long").trigger(short_mask, "short")
    .measure("band_excursion_atr", (data['close'] - band).abs() / data['atr'])
    .gate("first_signal_of_day", is_first)
    .to_frame(signal_prefix="mr_"))
```

The verdict is **computed from the gates** — `ENTRY` if all passed, `REJECTED` otherwise —
so a hunter cannot record a verdict that disagrees with its own masks.

#### Six rules, each one a failure mode of the dump this replaces

`BBMRReversionBot` already writes 22 indicator columns for **every bar** to
`%TEMP%/bbmr_diag_<guid>.csv` and prints the path only to the NT8 output window. The data
exists and is unaddressable, which is indistinguishable from not having it.

| # | Rule | Why |
|---|---|---|
| 1 | Log **decisions**, not bars | A per-bar state dump makes you re-implement the rule in your head. Rows are bounded by triggers × gates |
| 2 | Record **every** gate, not the first failure | `&&` and `and` short-circuit, so a first-failure log reports the *implementation order* as the cause |
| 3 | Record the **value**, not just pass/fail | "ADX passed" is not analysable. "ADX 18.2 vs 15" says the trade was marginal |
| 4 | A rejection needs a **denominator** | `SKIP` counts bars that never triggered, or "gate X blocked 40 setups" has no scale |
| 5 | **Long format**, one row per (decision, gate) | A wide format needs a column per gate, so adding one is a migration and two strategies cannot share a schema |
| 6 | A **`gate`** is not a **`measure`** | A magnitude recorded as a gate has a structural 0% failure rate — a green that can never be red — and would sit at the top of every roster, inflating the set the parity diff runs over |

**An `ENTRY` carrying a failed gate is refused at write time** on the Python side and
**reported by the reader** for both sides (the C# emitter deliberately never throws into a
running strategy). A log that can record a self-contradiction is worse than no log, because
it looks like evidence.

#### Transport — no bridge change needed

`DecisionLog.cs` is **generated** from `decision_log.COLUMNS` by
`scripts/utils/generate_decision_log.py` (`--check` fails a build on drift, exactly like
`TradingDefaults.cs`). It writes `mcp_decisions_*.csv` into `Globals.UserDataDir` —
precisely the filename shape the bridge's existing `nt_list_exports` / `nt_get_export` /
`nt_delete_export` endpoints already serve behind their path-traversal gate.

| Concern | How it is handled |
|---|---|
| SA optimisation runs many instances **concurrently** | `Interlocked.Increment` in the filename; two instances on one path is a truncated file, not an error |
| A cancelled run loses the tail | Flush per **decision** (not per bar — see rule 1) |
| A logging failure kills the backtest | It cannot: every write is wrapped. But it is **not silent** — `LastError` is set and `Banner()` says `DISABLED`, because a short file reads as "the strategy took no trades" |
| A comma in a gate name | Quoted; otherwise every column shifts right |

### 5.6 What the bridge was not sending 🟢 fields added, 🔴 not deployed

`nt_backtest` iterates `SystemPerformance.AllTrades` with both `Execution` objects in hand
and projected ten fields. Ten more were one line each. Added 2026-09-05
(`nt8-mcp-bridge`, 706/0, **not deployed — a recompile wipes every static singleton in a
live instance, which is the user's call**):

| Field | Why it was the missing one |
|---|---|
| `maeCurrency` `maePoints` `mfeCurrency` `mfePoints` | Separates a bad **entry** (the loser never went your way) from a bad **exit** (it did, and was given back). No P&L column distinguishes those. Available **only** from a backtest `SystemPerformance` — the bridge's own account-level path carries a source note saying so |
| `entryGroup` | Which rows are legs of **one** bracket. `ExtractBacktest` **already grouped by this key** to compute entry-level win rate and never emitted it, so the aggregate could not be reproduced or checked |
| `entryName` | The **join key** to the decision log. Falls back to the entry order's `Name`, the same two-step the exit-reason tally already needed |
| `entryQuantity` `exitQuantity` | Per-**leg** size. `Trade.Quantity` is the trade's; on a scale-out the executions differ from it and from each other, which is the whole content of the leg convention |
| `tradeNumber` `commission` | Ordering, and the cost that bites 10× harder on micros (§1.3) |

Property names were confirmed by **reflecting on `NinjaTrader.Core.dll`**, not assumed:
`GetP` is reflection-based, so a wrong name returns `null` rather than failing to compile —
it would have read as "this strategy has no MAE".


---

## 6. Step 5 — Compare

Parity is checked at **three layers**. Lower layers name the *rule* that diverged; higher
layers only tell you *that* something did.

**Layer 0 is the gate roster (§5.5).** Run it first: it is free, it needs no NT8, and if the
two rosters differ the layers below cannot be interpreted.

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
| **Which sessions carry the edge?** | `reporting/session_breakdown.py` — appended to every tearsheet, keyed on the §1.3 partition |
| **Where should the trade cap be?** | `reporting/trade_ordinal.py` — EV_R by trade ordinal, per day and per session, marginal and cumulative, with the sample size beside the suggestion |
| **Why did it take these trades?** | `reporting/decision_log.py` — the gate roster, with `blocked_alone` as the diagnostic column and a `never_fails` flag (§5.5) |
| **What separated winners from losers?** | `reporting/win_loss_attribution.py` — three questions, in order of what they are worth |

#### 7.1a What the win/loss report actually asks

Three questions, and **only the third can name a line to change**:

| | Question | Needs |
|---|---|---|
| 1 | **Where** did the losses come from — session × exit reason | the trade list only; works on both sides today |
| 2 | **How** did the losers behave — went against you at once (bad entry) or ran and came back (bad exit) | MAE/MFE (§5.6) |
| 3 | **Which criterion** was wrong — gate values on winners vs losers, against the threshold | the decision log (§5.5) |

A win rate tells you a strategy is bad. *"Winners entered with ADX median 24.8, losers with
15.9, and the gate is set at 15"* tells you which line to change. Nothing derivable from a
trade list can produce that sentence.

**Three refusals, because a confident number from a dead column is worse than a gap.** Each
was found by running the report on the live `mean_reversion` set, not imagined:

| Refusal | What it found |
|---|---|
| An identically-zero excursion column is **dead, not measured** | `mae_points` and `mfe_points` are present and `0.0` on all 16 trades — including 11 that exited on a stop, which is impossible. "Median MAE 0.0" reads as a finding about the strategy; it is one about the pipeline |
| A **stop-loss exit that booked a profit** is surfaced first | 3 of 16 trades did. A stop on the wrong side of entry fills immediately and pays; `signal_geometry` FAILS the same run with `stop_wrong_side=372`. Every figure below is computed over those rows too |
| The **funnel gap** is named | The log records 3,188 hunter entries; under the pre-2026-09-05 entry window the trade set had 16, a 200:1 gap the report could only name. The engine's gates are now counted per reason and rendered as section 0 of the report; re-measured under the current policy the funnel is 3,188 -> 2,527, and the only gate still biting is the order timeout — see item 13 |

A median is refused below 10 trades **per outcome side**; same reasoning as the cap
threshold in `trade_ordinal.py`.

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

### 7.3 Two rules for every report 🟢 ENFORCED

1. **A report names its inputs**: strategy, ticker, date range, parameter hash,
   data hash, run id, price basis, commit. One that cannot is not evidence.
2. **A report refuses to exist when it has nothing to say** — and says so with a
   reason.

*Enforcers*: `reporting/provenance.py` (`write_report` prepends the header, so a
report **cannot be written without one**) and the `reports_attributed` criterion,
which reads the recorded artifacts off disk.

⚠️ **THIS CRITERION USED TO BE A CONSTANT.** It set NOT EVALUATED with a fixed
string on every run, so `validated` — which is `all(status == PASS)` — was
unreachable for **every** strategy however good it was. A criterion that cannot
change its answer is the exact shape §0 exists to forbid, and it sat in the
module written to enforce that. Four reds are now reachable: no header, a
recorded file absent from disk, a stub, and **zero reports checked** — because
`not problems` over an empty set is `True`, and a run that produced no reports
would otherwise pass by not being looked at.

#### Why the header is derived, never passed

`render_provenance` takes the run-record **document** and nothing else. A
reporter handed a `ticker=` argument can be handed the wrong one, and the report
is then confidently mislabelled — worse than unlabelled, because it looks
attributed. Anything absent from the record renders as `(not recorded)` rather
than being invented.

Two things the header surfaces that a reader would otherwise assume away:

* **an undeclared price basis** — every P&L figure below it is unattributable by
  construction, and `--price-adjustment` defaults to `undeclared` (§0.1);
* **a dirty working tree** — `code.dirty` was `True` on every run measured while
  this was written, and a report produced from uncommitted code does **not**
  reproduce from the commit hash it prints.

> **The evidence that motivated these rules is gone, and the rules stand.**
> §7.3 used to cite `reporting/outputs/tearsheet_NQ1_box_reversion.md` — 2 bytes
> containing the word `ok` — and a tearsheet reporting $178,574 net P&L beside a
> $750 final balance. That whole directory was deleted when reports moved under
> the run id, so those files no longer exist. Citing them as current was the same
> defect as an open item describing a state that had changed.

#### Rule 2 measures the BODY, not the file

The first version compared the whole file against 200 bytes — and the provenance
header alone is ~600, so the refusal **could never fire**: a green with no
reachable red, inside the module written to remove one. The stub test caught it.
The floor is now 40 characters of stripped body, chosen against both ends: the
motivating stub was 2, and the smallest *legitimate* body is a named refusal,
which `refuse_empty` renders at ~65.

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
- [ ] ≥120 out-of-sample trades, ≥3 regimes, bootstrap CI off zero (§8) 🟢
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

> **`out_of_sample` was checking that a split EXISTS, not that it proved anything.**
> It asked whether `--oos-start` was passed. §8 has required **≥120 trades across ≥3
> regimes**, and a bootstrap CI for a marginal profit factor, since this document was
> written, and **nothing measured either** — so a run whose out-of-sample window
> contained four trades, three of them winners, passed every criterion the checklist
> had. `statistically_sufficient` (added 2026-09-05) measures all three and fails on a
> sample that looks excellent: 6 trades and a 100% win rate is its first test.
> *Enforcer*: `reporting/sufficiency.py` + `tests/test_sufficiency.py` (19 tests).
> Two things it deliberately does **not** claim. The regime bucket is the **calendar
> quarter (ET)** of the entry — a *proxy*, declared as one in the output, because this
> repository has four session definitions and no volatility-regime one; it catches "all
> the evidence came from one stretch of tape" and will not catch a year of uniformly
> quiet market. And the bootstrap resamples trades **independently**, which understates
> the interval when returns are serially dependent — so a CI that straddles zero is
> decisive, and one that excludes it is the weaker of the two readings. Both are marked
> for review rather than buried.

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
| 3 | **No hosted CI in this repo** — no `.github/workflows`. `tools/ci_local.py` (4 checks) and `.githooks/pre-commit` DO exist and are the authoritative gate; what is missing is the fresh-clone case, which is the one thing a local run cannot cover. ⚠️ This row read "no CI at all, no `tools/ci_local.py`" until 2026-09-05, after both had shipped — a gap that had been closed still being advertised as open | code |
| 4 | Parameter document for the non-ICT families (§3.3) | code |
| ~~5~~ | ~~**Reports from the run record**~~ — **DONE 2026-09-05.** `reporting/provenance.py`; `write_report` prepends a header derived from the run record, and `reports_attributed` now MEASURES instead of returning a constant. It was the last criterion that could never pass, so it was the last thing blocking the word "validated" | done |
| ~~6~~ | ~~Freeze the bespoke runners with a gate~~ — **DONE 2026-09-05.** `tests/test_no_new_runners.py` + `frozen_runners.txt`, matched on behaviour with three negative controls (§4.1) | done |
| 7 | `box_reversion` raises `TypeError: Invalid comparison between dtype=datetime64[s] and Timestamp` when window-filtered | code |
| 8 | **Migrate strategies off the legacy `session_block`** onto §1.3's `session_name`. The legacy labels are RTH-only and every existing strategy reads them, so this changes results and must land through a recorded run per strategy | code |
| ~~9~~ | ~~Generate `TradingDefaults.cs`~~ — **DONE 2026-09-05.** `scripts/utils/generate_trading_defaults.py` emits it; `--check` fails a build when the JSON moves and the C# does not | done |
| 10 | **Normalise the inventoried bot divergences** — tracked as tickets B1–B9 in [BOT_FIX_BACKLOG.md](BOT_FIX_BACKLOG.md), with a loop prompt. Deliberately a separate file: finalising the workflow must not be blocked on fixing twelve strategies | code |
| 11 | **Capture SA *executions*, not just trades** — 🟡 **mostly closed 2026-09-05.** `nt_backtest` still returns entry/exit PAIRS, but the fields that made a pair insufficient are now projected: `entryQuantity`, `exitQuantity`, `entryGroup`, `entryName`, MAE/MFE (§5.6). Per-leg size and the bracket key were the whole reason fills were needed. **Not deployed** — a recompile wipes every static singleton in a live instance. What genuinely still needs fills is a *partial* fill of one leg | **user** (deploy) |
| ~~12~~ | ~~**Win/loss attribution report**~~ — **DONE 2026-09-05.** `reporting/win_loss_attribution.py`, three questions (§7.1a), works on either side, appended to every tearsheet. Three refusals rather than confident numbers over dead data | done |
| ~~13~~ | ~~**The engine's own gates are not instrumented.**~~ — **DONE 2026-09-05.** The engine now counts every one of its gates per reason (`entry_window`, `daily_cap`, `pause_after_consecutive_losers`, `hard_stop`, `daily_max_loss`, `order_timeout`, `position_lockout`): counted in the Rust kernel (`rejection_counts`) and in the Python mirror (`last_rejections`), surfaced as `engine_rejections` in the result dict and rendered as section 0 of the win/loss report. gate2 now asserts the counts equal. Pinned by `tests/test_engine_rejection_counts.py`. **Re-measured under the current policy: 3,188 hunter entries became 2,527 trades — 1.26:1, not the stale 200:1** (that number was an artifact of the 09:45–15:30 entry window the frozen policy has since removed; the only gate still biting is the order timeout, 134 bar-rejections). Also fixed while there: gate2's "python" side had always dispatched to the RUST kernel, so the v1 trade comparison was vacuous — it now runs `use_rust=False` for real. `simulate_mtf` still counts nothing (v2 predates this); the mtf path is favourable-only and deprecated for ranking | done |
| 19 | **`target1_price` never reaches the sanctioned engine.** `hunt()` declares it, `backtest_engine.py` honours it, and `NT8ParityBacktester` — the ADR-024 default — drops it and substitutes `queen_bps`/`runner_bps`. So a hunter's declared target does not affect the reported result at all. Found by the 2026-09-05 review while unifying the search and report engines; it is now the same gap on both sides rather than a divergence between them, which is why the run no longer *silently* selects and judges under two payoff functions. Either the parity engine learns the target, or `hunt()` stops declaring one | code |
| 20 | **The deployed `BBMRReversionBot.cs` carries `FlattenBy = 1615`** — past ADR-020's 16:00 hard exit — while the repo source has been corrected to 1600. Found 2026-09-05 the first time `_deployment_state` ran for real. The bot at the centre of the parity work is, as installed, the unfixed one, so **any NT8 capture taken from the current install is evidence about a bot that violates ADR-020**. Not deployed from here: a recompile wipes every static singleton in a live instance | **user** (deploy) |
| 21 | **No agreed definition of a "regime"**, while §8 requires "≥3 regimes" and §9 now gates on it. Three definitions exist in this repo and disagree; `*_bucket_full` is computed with **lookahead** and is in live use in `edgeful/ib_breakout_filter.py` — measured on 9,267 VIX daily closes, **13.6%** of days get a different label from the causal version, rising to **39.4%** in the earliest fifth. `statistically_sufficient` currently uses the calendar quarter (ET) as a declared proxy. Research item **REG-1**, `docs/strategies/research_backlog/13_market_regime_definition.md`, which lists seven candidates, the acceptance criteria and every consumer that switches over | research |
| ~~14~~ | ~~**`mae_points` / `mfe_points` identically zero**~~ — **DONE 2026-09-05.** My first diagnosis ("the excursion stage is not populating them") was WRONG. Measured by calling the kernel: `simulate_bars_v1` returned twelve keys and no excursion among them, while `_simulate_mtf_rust` had always read `res["mae_points"]` because v2 returned them — one of two readers of the same kernel invented its answer with `np.zeros`. v1 now tracks and returns them (ported from v2, `crates/nt8_parity_core`), the adapter reads them, and a STALE wheel degrades to NaN rather than back to zero. P&L element-wise unchanged; question 2 of §7.1a is live and says losers' median MAE is 9.5pts against winners' 1.0 | done |
| 15 | **Migrate the fourteen C# bots onto `GovernedStrategy`** (§3.4). The base class, the mandated `SetupEvaluation`, the frozen governance gate names and the two upstream hooks all exist and are gated; **no bot derives from it yet**, so every roster diff is one-sided until one does. Inheriting it also supplies the unique per-entry signal name — the join key from a fill back to its decision — which was a separate item until the base class made it one edit. Filed as **B7+B8**; the population is frozen in `tests/uninstrumented.py` and may only shrink. Needs a recompile | **user** (deploy) |
| 16 | *(merged into 15 — it was the signal-name half of the same edit)* | — |
| 17 | **Three unlanded `RiskManagerBase` changes, and a layering fix.** The fork is DELETED (2026-09-05) and `test_base_class_ownership.py` keeps it gone. What remains is a decision: which of its three changes to land upstream, and whether to move `AddSecondaryTimeframe` out of the risk base — eight of its ten users switch it off, and `GetCurrentATR()` reads that series while ATR drives stop distance and position size. **B9** | **user** |
| 18 | **Instrument the fourteen uninstrumented hunters** (§3.4). `mean_reversion` is the reference; the rest are frozen in `tests/uninstrumented.py`. Each one is small, and each is where a strategy's real gate roster becomes visible for the first time | code |

### 11.1 The remaining build order

Subsumed from the phased plan. Ordered by what unblocks what, not by size.

| Phase | Item | State |
|---|---|---|
| **0.2/0.3** | adverse fills already default; **restate the existing prop-firm conclusions on them** — this is where optimism did the most damage, and published numbers may change | 🔴 |
| **1.1** | rank-correlation calibration Python↔NT8 — tells you whether the screen has been lying, and by how much (§12.1: the ranking is what must be preserved) | 🔴 |
| ~~**2.4**~~ | ~~freeze the bespoke runners with a CI check~~ — **DONE 2026-09-05** as a pytest gate; still not in CI, because there is no CI (item 3). ⚠️ an *absence* gate passes silently when code moves — give it a negative control | 🔴 |
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
