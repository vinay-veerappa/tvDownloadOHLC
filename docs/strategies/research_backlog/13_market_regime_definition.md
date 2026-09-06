# 13 — Market Regime: one definition, used everywhere

**Family**: infrastructure research (not a strategy). **Item**: `REG-1`.
**Status**: **DECIDED 2026-09-06 (user): keep the calendar-quarter proxy; adapt
or change it when something better is found.** The lookahead defects are fixed
(filter calibration, classifier features), the live-consumer table is two rows
shorter, and arms 1, 2, 5 and parts of 3–4 are measured (see "Arms" below): A′
(VIX 10d-MA tercile) is the front-runner but **era stability — the hypothesis
H test — is unsatisfied by every market-content candidate**, which is precisely
why the user parked it. **Raised**: 2026-09-05. **Decided**: 2026-09-06.
**Blocks**: nothing any more — the proxy is a *declared* proxy everywhere it
prints, and this item is the standing record of the measured candidates and of
what "better" would have to beat (the adoptability checklist).

---

## Why this is a research item and not a decision

Three separate places in this repository already require a regime and none of
them agree on what one is.

* **The backlog's own learning protocol** (`README.md`) says *"Stratify every
  result by: session bucket, IB regime quint, and day type (R1/R2/DWP/DNP)"* —
  three axes, one of which ("IB regime quint") does not exist as named; the
  implementation is a **tercile**, not a quintile.
* **STRATEGY_WORKFLOW.md §8** requires *"≥120 trades per configuration across ≥3
  regimes"* and never says what a regime is. When that requirement was finally
  wired into a gate (2026-09-05), the only definition that could be built
  without inventing one silently was the **calendar quarter (ET)** of the entry
  — declared as a proxy in the output precisely because it is a bad one. It
  catches *"all the evidence came from one three-month stretch"* and will not
  catch a year of uniformly quiet tape.
* **`scripts/edgeful/` and `scripts/libs_py/nqstats/ib.py`** carry a real
  implementation — `vix_bucket_full`, `vix_bucket_trailing`,
  `range_bucket_full`, `range_bucket_trailing` — which is consumed by the IB
  breakout filter's calibration cells and the universal signal classifier.

So the question is not "should we have regimes". It is **which partition, and
who owns it**, and the answer has to be one thing because the whole point of a
stratified result is that two results can be compared.

## Two defects in what exists, both measured

**1. `*_bucket_full` is computed with lookahead and is in live use.**

```python
q1_3 = ib_agg['range_pct'].quantile(1/3)          # the WHOLE sample
ib_agg['range_bucket_full'] = np.select([...])
```

A day in 2010 is labelled using quantiles computed from data through 2024. The
`*_trailing` variants are the causal ones (`expanding(min_periods=20).quantile(...).shift(1)`),
and **both are exported and both are consumed** — `ib_breakout_filter.py` keys
its calibration cells on `range_bucket_full` specifically.

Measured on `data/VIX_1d.parquet` (9,267 daily closes), full-sample terciles at
15.20 / 20.76 against expanding terciles:

| | disagreement |
|---|---|
| whole sample | **13.6%** of days get a different label |
| earliest fifth | **39.4%** |
| second fifth | 13.7% |
| third fifth | 6.2% |
| fourth fifth | 6.4% |
| latest fifth | **2.4%** |

That gradient *is* the lookahead signature: the full-sample labels know the
future distribution, so the earliest data is relabelled most and the most recent
data barely at all. A backtest stratified on `_full` is reading a label that
could not have been known at the time, and the bias is concentrated in exactly
the deep history that makes the sample look sufficient.

**2. The bucketing code exists twice.**

`scripts/libs_py/nqstats/ib.py:1149-1168` and
`scripts/edgeful/ib_pipeline.py:412-431` contain the same VIX tercile logic,
written out separately. This is the same class of defect as the four execution
policies (fixed 2026-09-05): two copies drift, and the copy that drifts is the
one doing the work.

## The question

> **Which partition of market conditions is (a) causal, (b) stable enough that a
> stratum keeps its meaning across years, and (c) coarse enough that a
> per-stratum trade count is still large enough to conclude anything?**

Those three pull against each other and that tension is the whole item. Terciles
of a slow-moving series give balanced strata but a "Low VIX" day in 2017 and a
"Low VIX" day in 2022 are not the same market. Absolute thresholds keep their
meaning and produce wildly unbalanced strata. That trade-off is what has to be
measured, not argued.

## Candidates on the table

| # | Definition | Exists? | Causal? | Notes |
|---|---|---|---|---|
| A | **VIX tercile, expanding** (`vix_bucket_trailing`) | yes | yes | The incumbent. Balanced by construction; strata not comparable across eras |
| B | **VIX absolute bands** (e.g. <15 / 15-25 / >25) | no | yes | Stable meaning, unbalanced strata, thresholds are a decision |
| C | **Realised-volatility tercile** (ATR% or close-to-close σ, expanding) | partially | yes | No VIX dependency, so it extends to instruments without one |
| D | **IB range tercile** (`range_bucket_trailing`) | yes | yes | Intraday, and the one the IB work already uses. Is it a *regime* or a *day type*? |
| E | **Day type** (R1/R2/DWP/DNP, `DAILY_CLASSIFICATION.md`) | yes | ends-of-day | Only knowable after the fact for the day itself — usable as a *prior* on the NEXT day, not as a same-day gate |
| F | **Calendar quarter (ET)** | yes (the proxy) | yes | Trivially causal, no market content. The placeholder to be replaced |
| G | **Trend/chop** (KER, ADX — see `12_range_chop_congestion.md`) | proposed | yes | Overlaps item 12; settle there or here, not both |

## Arms — 1, 2, 5 MEASURED 2026-09-05; 3, 4 partially

The hypothesis under test, falsifiable:

> **H:** there is a regime definition under which a strategy's per-stratum
> edge is more stable across time than its pooled edge — i.e. the
> stratification explains variance rather than manufacturing it.

**Status of H after measurement: NOT SUPPORTED by any market-content
candidate yet.** Era stability (arm 4) is |ρ| ≤ 0.5 for every VIX candidate;
only the content-free quarter proxy reaches +1.00 (for one strategy). The
arms below carry the numbers; the front-runner survives on the other three
arms, not on H.

Measured on the Globex IB day-level aggregate (`ib_facts_NQ1`, 5,158 trading
days, 2006–2026). Full harness output inlined below; throwaway scripts, nothing
depends on them.

### Arm 1 — balance

| Candidate | Strata shares | Years reaching ≥3 strata (≥5% each) |
|---|---|---|
| A VIX tercile (1d) | 32–34% each | min 1 (whole years in ≤2 strata) |
| A′ VIX 10d-MA tercile | 32–34% each | min 1 — **2017 spent the year in ONE stratum**; 2012–14, 2021–22 in two |
| B VIX abs bands (<15/15–25/>25) | 34/49/17% | min 1 |
| C realvol tercile (range_atr) | 45/29/26% | min 3 |
| D IB range tercile | 44/29/27% | min 1 |
| F quarter (the proxy) | 25% each | min 3 |

### Arm 2 — persistence (the ≥5-day adoptability bar)

| Candidate | Median run | Mean run | Longest |
|---|---|---|---|
| A VIX tercile (1d) | 3.0d | 8.6d | 265d |
| **A′ VIX 10d-MA tercile** | **16.0d** | 31.3d | 302d |
| **A″ VIX 20d-MA tercile** | **27.0d** | 48.2d | 310d |
| B VIX abs bands (1d) | 3.0d | 11.1d | 209d |
| C realvol tercile | 1.0d | 1.7d | 17d |
| D IB range tercile | 1.0d | 2.2d | 100d |
| F quarter | 63d | 62d | 66d |

**No unsmoothed candidate passes.** The range-based ones (C, D) are day
filters, not regimes — median run ONE day, answering the brief's own question
("is it a regime or a day type?": a day type). Smoothing the VIX with a
trailing 10d/20d MA is causal (trailing window) and clears the bar.

### Arm 3 — separation (does the partition make strategies disagree?)

On the two recorded trade sets under the current policy — `mean_reversion`
(fade; 2,527 trades) and `box_reversion` (mid-reversion; 1,601 trades; fixed
this session). Per-stratum mean points per trade:

| Candidate | mean_reversion | box_reversion | stratum-rank corr |
|---|---|---|---|
| A VIX 1d | High +0.68 / Med +0.15 / Low +0.18 | High **+3.64** / Med +11.60 / Low +11.08 | **−1.00** |
| A′ VIX 10d | High +0.51 / Mid +0.38 / Low +0.04 | High **+5.32** / Mid +10.82 / Low +10.27 | −0.50 |
| B abs bands | High +0.35 / Mid +0.37 / Low +0.23 | High **+0.78** / Mid +9.92 / Low +11.05 | −0.50 |
| F quarter | Q1 +0.70 … Q2 −0.25 | Q1 +8.08 … Q4 +9.75 | −0.40 |

**A VIX 1d separates maximally** (−1.00): mean_reversion's edge lives in High
VIX while box_reversion's mid-reversion collapses there (High-VIX days run
through the mid instead of reverting). That is a partition carrying
information, not manufacturing variance. Caveat: box_reversion's trade set is
unvalidated (5 criteria FAIL) and the strategy was dead until this session —
its half of arm 3 is provisional until a recorded run says otherwise. A trend
follower is still needed for the third character the arm asks for.

### Arm 4 — era stability (per-stratum edge, H1 vs H2 rank correlation)

Weak everywhere (|ρ| ≤ 0.5) except the quarter proxy for mean_reversion
(+1.00 — and the proxy has no market content). **H as stated is not yet
supported by the VIX candidates**: strata meanings drift across eras, which the
brief anticipated ("a Low VIX day in 2017 and one in 2022 are not the same
market"). This is the test the surviving candidate must beat, and none has
beaten it yet.

### Arm 5 — full/trailing gap

D (range): **17.1%** whole-sample disagreement, earliest fifth 29%. A (VIX):
**18.3%**, earliest fifths 37/37%. Same earliest-heavy gradient as the IB
aggregate table above. B, C′-smoothed and F are causal by construction (no
`_full` twin exists to disagree with).

### Where this leaves the candidate table

| Candidate | Balance | Persistence ≥5d | Separation | Era stability | Verdict so far |
|---|---|---|---|---|---|
| A VIX tercile 1d | ✅ | ❌ (3d) | ✅ (−1.00) | ❌ | fails persistence |
| **A′ VIX 10d-MA tercile** | ⚠️ (some years 1–2 strata) | ✅ (16d) | ➖ (−0.50) | ❌ | **front-runner, pending era stability** |
| B VIX abs bands | ❌ (17% High) | ❌ (3d; 10d variant 16d) | ➖ | ❌ | thresholds + skew |
| C realvol tercile | ✅ | ❌ (1–3d) | not run | not run | a day filter |
| D IB range tercile | ⚠️ | ❌ (1d) | not run | not run | a day type (its own row says so) |
| F quarter | ✅ | ✅ | ❌ (no content) | ✅ for one strategy | the proxy it already is |

**Open before adoption**: era stability is the unsatisfied criterion for every
market-content candidate. The next measurement worth taking: era stability of
**A′ (VIX 10d tercile)** on more trade sets (a trend follower, and
`ib_pullback`) — if ρ stays ≤ 0.5, the honest conclusion is that a *single*
stable 3-stratum regime does not exist in this data, and the adoptable answer
is A′ anyway (best on the other three arms) with era stability reported per
run rather than assumed. That decision is the user's to ratify, per the
adoptability checklist.

The five arms themselves, for reference (this is how the tables above were
produced): **balance** — trades per stratum per year, arithmetic elimination;
**persistence** — median stratum run length; **separation** — per-stratum edge
across strategies with different characters (a useful partition makes them
disagree); **era stability** — per-stratum edge on each half of history,
rank-correlated; **lookahead control** — every candidate in both `_full` and
`_trailing` form, and a candidate that only works in `_full` form does not
work.

## What makes a definition adoptable

All of these, or it stays a proxy:

- [ ] **Causal by construction** — no statistic computed from data after the bar
      being labelled. Enforced, not asserted.
- [ ] **One implementation**, in `scripts/trading_framework/config/` or a
      library module that both `libs_py` and `edgeful` import. No second copy.
- [ ] **Declared in `trading_defaults.json`**, so it is frozen the way sessions
      and instruments are, with its thresholds and its source recorded.
- [ ] **Instrument-independent or explicitly per-instrument** — a VIX-keyed
      definition silently fails on anything VIX does not cover, and must say so
      rather than defaulting.
- [ ] **≥3 strata reachable in a normal 2-year window**, or §8's requirement is
      unsatisfiable by construction.
- [ ] Median stratum run length **≥ 5 trading days** (a regime, not a filter).
- [ ] The `_full`/`_trailing` gap measured and reported, not assumed small.

## Where it gets used once settled — the "across the board" list

This is the reason to do it once rather than per-consumer. Every one of these is
currently either using a different definition or using none:

| Consumer | Today | After |
|---|---|---|
| `reporting/sufficiency.py::regime_spread` | calendar quarter (proxy) | the definition |
| STRATEGY_WORKFLOW.md §8 / §9 `statistically_sufficient` | "3 regimes", undefined | the definition |
| `research_backlog/README.md` learning protocol | "IB regime quint" (is a tercile) | the definition |
| `reporting/session_breakdown.py`, `trade_ordinal.py` | session only | session × regime |
| `edgeful/ib_breakout_filter.py` calibration cells | ~~`range_bucket_full` (lookahead)~~ → `range_bucket_trailing` **FIXED 2026-09-05** | the definition |
| `edgeful/universal_signal_classifier_input.py` | ~~both `_full` and `_trailing`~~ → **`_trailing` only — FIXED 2026-09-05** | the definition |
| `libs_py/nqstats/ib.py` | its own copy of the bucketing | imports it |
| `edgeful/ib_pipeline.py` | its own copy of the bucketing | imports it |
| `ml/prop_firm_simulator.py` | nothing | per-regime pass rate, so "viable" names its conditions |
| the C# bots | nothing | out of scope for now — a bot cannot compute an expanding quantile live without a state store |

The last row is the one to think about before adopting a definition. **A regime
a bot cannot evaluate in real time is a research instrument, not a gate.** An
expanding quantile needs history the strategy does not carry; absolute bands
(candidate B) need only today's VIX. If the intent is ever to gate live entries
on regime, that constraint should decide the shape now rather than after the
research.

## First cheap step — DONE 2026-09-05, both defects are real

**1. `_full`/`_trailing` disagreement on the actual IB aggregate** (measured on
`data/derived/ib_facts_NQ1.parquet`, 41,352 rows, 2006–2026, all six session
slots; `range_bucket_full` vs `range_bucket_trailing`):

| Session slot | n | whole-sample disagreement | earliest fifth |
|---|---|---|---|
| Globex IB | 5,158 | **17.1%** | 29.2% |
| Tokyo IB | 10,253 | **17.1%** | 22.5% |
| NY PM IB | 5,264 | **24.4%** | 54.1% |
| NY AM IB | 5,262 | **36.0%** | 65.0% |
| London IB | 10,280 | **38.5%** | 59.2% |
| Midnight OR | 5,135 | **42.8%** | 73.0% |

Larger than the VIX-only 13.6% estimate above — 1.3x to 3.1x per slot — and
with the same earliest-heavy gradient. On the IB aggregate, a whole-sample
"regime" label is wrong for **one day in three**, averaged over slots.

**2. The shipped filter's calibration moves when switched to the causal
label** (A/B on `ib_confluence_NQ1`, same rows, `_walk_forward_calibration`
keyed `range_bucket_full` vs `range_bucket_trailing`):

| | full (shipped) | trailing (causal) |
|---|---|---|
| `empirical_win_rate_strict` mean | 0.10604 | 0.10633 |
| cell-level | corr 0.857 · mean abs diff 0.005 · **p95 abs diff 0.032** | · |
| `expectation_bucket` changes | — | **10.5% of all rows, 21.6% of strict rows** |

A cell-level ±0.03 p95 win-rate shift is a whole expectation-bucket boundary
(0.18 / 0.25) wide, and the final recommendation flips on one strict row in
five. **This is a live defect in a shipped filter and it is fixed** (2026-09-05):

- `ib_breakout_filter.py` keys all calibration cells on
  `range_bucket_trailing` (causal), with a fallback to `_full` only when the
  column is absent.
- `_compute_confluence_score` also read `range_bucket_full` through a
  vocabulary (`"normal"/"compressed"/"wide"`) that **never occurs in the
  pipeline output** (`Small/Medium/Large`) — that term scored exactly 0 for
  every row since it was written. Fixed to the real vocabulary, causal column.
- `data/derived/ib_breakout_filter_NQ1.parquet` regenerated under the fixed
  code. The pre-fix parquet is not comparable.
- Pinned by `tests/edgeful/test_ib_breakout_filter_causal.py` — including a
  negative control that flips the full label everywhere and requires the
  calibration to not move.

Still open in this item: the duplicated bucketing code in `nqstats/ib.py` and
`edgeful/ib_pipeline.py` (§"two defects" above); and the candidate comparison
arms below. **The classifier feature list is fixed** (2026-09-05):
`universal_signal_classifier_input.py` no longer feeds `range_bucket_full` /
`vix_bucket_full` to the model (whole-sample quantile labels leak the future
distribution into every training split); only the causal `*_trailing`
variants remain. Pinned by `tests/edgeful/test_classifier_input_no_lookahead.py`.
The A/B harness for the calibration lives at
`%TEMP%\opencode\reg1_ab_calibration.py` — inlined above, nothing depends on it.

---

### Cross-references

- `docs/architecture/STRATEGY_WORKFLOW.md` §8 (the requirement), §9 (the gate)
- `scripts/trading_framework/reporting/sufficiency.py` (the proxy, and its
  docstring naming this item)
- `docs/DailyClassification/DAILY_CLASSIFICATION.md` (candidate E)
- `12_range_chop_congestion.md` (candidate G — do not duplicate it here)
- ADR-002 (report in price % / bps), ADR-001 (ET for session windows)
