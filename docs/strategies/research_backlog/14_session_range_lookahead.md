# 14 — Session-range lookahead in the shared NQStats layer

**Family**: infrastructure (not a strategy). **Item**: `REG-2`.
**Status**: **CLOSED 2026-09-05** — option A ratified by the user, implemented
as **ADR-026**. See `docs/architecture/ADR.md` for the decision and
`scripts/trading_framework/tests/test_session_range_knowability.py` for the
enforcement. This file remains as the defect record and evidence.

> **What shipped:** `get_nq_session_ranges` emits NaN on every bar before the
> session's window-close bar; `compute_box_status` is as-of-t ("None" before
> the class window, "Pending" while the status can still flip, final from the
> settling break or window close); NaN no longer becomes "Held"/"BEARISH" in
> the classifiers. Verified end-to-end: `box_reversion` on real data is
> `causal=true` under the probe that caught the defect (recorded run
> `RUN_20260905_150321_405`, 977 trades — smaller than the pre-fix 1,601
> because the pre-fix set traded on lookahead labels in overnight sessions;
> that is the defect leaving the trade set, not a regression).

---

## The defect, demonstrated

`scripts/libs_py/nqstats/sessions.py::get_nq_session_ranges` (the `res_map =
agg.reindex(full_groups.values)` at the end) stamps a session's **whole-day
final aggregate** — high, low, open, close, **mid** — onto **every bar of the
logical trading day**, including bars from 18:00 the prior evening, hours
before the session runs.

Measured on NQ1, logical day 2019-03-05 (`data/NQ1_1m.parquet` via
`DataLoader.load_enriched`):

* `ny1box_mid` (the NY1 box, classification window 07:30–08:29 ET) has its
  first valid value at **2019-03-04 18:00:00-05:00** — the evening before.
* An Asia-session bar at 01:21 therefore reads a mid that will not exist for
  another seven hours.
* The workflow's causality probe caught it live: `LOOKAHEAD at 1 of 3
  informative cutoff(s). At 2019-03-05 07:58 the signals before the cutoff
  changed when future bars were appended (532 -> 533 signals)` — a signal at
  01:21 appeared only once the future NY1 bars were in the frame.

The same stamping applies to every `{session}_high/_low/_mid/_open/_close`
column `extract_all_sessions` produces, for both the killzone sessions and
the four profiler boxes.

## Why this is not fixed from here

`extract_all_sessions` feeds ~20 consumers, including **live trader scripts**
(`scripts/trader/signals/intraday_blocks.py` constructs `NQStatsEngine` on
`tail(5000)` windows nine times; `briefing_core.py` three times). Those callers
may deliberately rely on the "current day's session values" reading; a
semantic change made casually in the shared layer is exactly the class of
silent behaviour change this repo has been burned by (three point-value
tables, four execution policies). The fix needs a deliberate decision about
what each consumer should see on bars before a session completes:

| Option | Semantics | Blast radius |
|---|---|---|
| A | NaN before the session's classification window closes, value after | the honest reading; every consumer that reads "today's session" on an early bar must switch to the previous day's value explicitly (`prev_*` columns already exist) |
| B | value only from session start onward, forward-filled | preserves most current reads but still exposes the final aggregate before the session completes |
| C | leave shared layer, fix consumers | per-consumer window gates (what `box_reversion` now does); the lookahead stays for everyone not yet gated |

`box_reversion` currently carries a **consumer-side gate** (option C for
itself): entries restricted to the NY1 evaluation window 08:30–11:30 ET, where
the status is knowable. The probe passes (`causal=true` at the same cutoffs
that failed).

## Evidence commands

```python
from scripts.libs_py.nqstats.sessions import extract_all_sessions
et = df.loc['2019-03-04 18:00':'2019-03-05 17:59'].tz_convert('US/Eastern')
sess = extract_all_sessions(et)
print(sess['ny1box_mid'].first_valid_index())   # -> 18:00 the PRIOR evening
```

## Consumers to audit before changing anything

* `NQStatsEngine.process` (all `*_mid/_high/_low` stats columns) — which feeds
  `nqstats_adapter.get_box_features`, so **every framework hunter using box
  features inherits the lookahead on pre-window bars**
* `scripts/libs_py/profiler/session_box_status.py` (`compute_box_status`,
  `compute_box_broken` — broken checks read `{box}_mid`)
* `scripts/libs_py/profiler/engine.py` (boxes)
* `scripts/trader/briefing_core.py` (3 call sites), `intraday_blocks.py` (9)
* `scripts/analysis/*` daily profiler/nqstats analyses (2)
* `scripts/profiler_manual_test.py`, `check_profiler.py`, `get_current_nqstats.py`

## What makes it adoptable

- [x] One chosen semantics (A) applied in `sessions.py` once, not per consumer — **ADR-026**
- [x] The decision recorded as an ADR (ADR-026, user-ratified 2026-09-05)
- [x] A causality-probe test over a consumer that previously read pre-window bars — `tests/test_session_range_knowability.py` + the recorded `box_reversion` run (`causal=true`)
- [x] The framework suite re-run: 629 passed (was 624) + edgeful 72; the live scripts (`intraday_blocks`, `briefing_core`) are **not diffed yet** — they are live-path consumers and the user owns when they run; the adapter features they read are now NaN-before-close by construction, so any early-bar read returns NaN rather than a fabricated value (loud rather than silent)

## Cross-references

- `13_market_regime_definition.md` (REG-1) — the same class: shared stats
  layer, lookahead, wide consumer list
- `docs/architecture/STRATEGY_WORKFLOW.md` §2.8 (the tz rule this file
  neighbours), §11 item 7 (the ticket that surfaced this)