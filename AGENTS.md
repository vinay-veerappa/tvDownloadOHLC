# AGENTS.md — read this before touching a trading strategy

This file is the entry point for **every** coding agent (Claude Code, Copilot,
Codex, Cursor, Gemini, Antigravity). `CLAUDE.md` and
`.github/copilot-instructions.md` carry the same rules; this is the tool-neutral
copy, so if you read only one file, read this one.

## If the task mentions a strategy, backtest, parity, or a bot

**Read [`docs/architecture/STRATEGY_WORKFLOW.md`](docs/architecture/STRATEGY_WORKFLOW.md)
FIRST — before writing code, and before proposing a plan.**

It is the *only* document describing how to build, run, judge, report on or
promote a strategy here. Ten documents were subsumed into it and deleted; its
§13 records what moved where. **If you find another document that describes a
strategy procedure, it is stale — do not follow it and do not recreate one.**

The user should never have to restate any of the below. Do not re-derive it, do
not design an alternative, do not "improve" the pipeline as a side effect of a
strategy task.

## The one command

```powershell
.\.venv\Scripts\python.exe -m scripts.trading_framework.workflow `
    --strategy <registry_key> --ticker NQ1 --price-adjustment unadjusted `
    --optimize --trials 200 --oos-start 2025-01-01 `
    --nt8 --nt8-trades scripts/parity/fixtures/<capture>.csv
```

Only `--strategy` is required. **Two defaults will hurt you and must be passed
explicitly:** `--price-adjustment` defaults to `undeclared` (which now FAILS the
`attributable` criterion, by design), and `--ticker` defaults to `NQ1` (it
selects the point-value multiplier — the wrong one silently scales every P&L
figure). Full table: §0.1.

Exit **0** = every criterion PASSED · **1** = something FAILED *or* was never
measured · **2** = a required stage raised.

## Nine rules that are not negotiable

1. **Never write a new backtest runner.** 32 already exist, they are frozen, and
   a 33rd fails `tests/test_no_new_runners.py` — which matches on *behaviour*
   (names an engine + is executable), not on the filename. Use the entry point.
2. **NT8 is authoritative for behaviour.** When Python and NT8 disagree, presume
   Python is wrong.
3. **Parity is defined on the TRADE SET**, judged on signed points travelled —
   not on P&L, and not on absolute price. A constant price offset *is* the
   adjustment basis, so back-adjustment is not a parity gate; a different
   contract **month** is, because it changes which trades exist.
4. **Leg counting follows NT8**: a queen/runner bracket is **two trades**, one
   row per leg (`scripts/parity/legs.py::explode_legs`).
5. **A hunter is `hunt(data, params) -> DataFrame` + `get_param_grid()`.** No
   trade management, no P&L, no data loading, no `iterrows`, no own backtest
   loop. There is no `StrategyBase` — a spec described one for months and no
   strategy ever implemented it (§13).
5a. **A strategy reports the criteria it evaluated** (§5.5). Set
   `self.last_decisions` from `GateRecorder` — masks, not a loop, and the
   `hunt()` signature does not change. **Record every gate, not the first
   failure** (`and` short-circuits, so a first-failure log reports the
   implementation order as the cause), record the **value** and not just
   pass/fail, and use `measure()` for a magnitude — a gate that cannot fail is a
   green with no reachable red. **The gate roster is layer 0 of parity**: if the
   two sides evaluate different criteria they are different strategies and no
   recall number between them is interpretable.
5b. **A new C# bot inherits `GovernedStrategy`** (§3.4) and writes NO logging
   code. Implement `OnEvaluate(SetupEvaluation e)` — `Trigger` / `Gate` /
   `Measure` — plus `ConfigureStrategy()` and `GetStrategyName()`. It contains
   no orders, no clock reads and no `Print`. `CheckForSignal()` is **sealed**
   and the verdict is computed from the declared gates, so an unlogged criterion
   cannot reach a trade. The base also owns ADR-020's hard exit, the frozen
   defaults, unique entry names, and logging its own refusals. Do NOT inherit
   `RiskManagerBase` directly — nt8-riskguard owns it (ADR-025), and the ten
   bots that do inherit it are exactly the ten that hardcoded their own flatten
   times (tickets B1–B6). `tests/test_instrumentation.py` fails a new bot that
   derives from anything else.
5c. **Instrumentation is the DEFAULT and the exceptions only shrink.**
   `scripts/trading_framework/tests/uninstrumented.py` freezes the fourteen
   hunters and fourteen bots that do not yet report their criteria. Not on that
   list and silent = FAIL. On it and now reporting = its line MUST be removed.
   **There is nowhere to add a new strategy**, which is what makes this a
   default rather than a convention. Do not add a line to widen it without
   saying so explicitly and filing a ticket in `BOT_FIX_BACKLOG.md`.
6. **Never hardcode a point value, tick size, session window or risk default.**
   They are frozen in `scripts/trading_framework/config/trading_defaults.json` and
   read through `config/defaults.py`. There were three point-value tables and they
   disagreed by 10x inside one run; `tests/test_frozen_defaults.py` scans for a
   fourth. Default instrument is **MNQ** (micros); `NQ1` resolves to MNQ, `ES1` to
   MES. Sessions are GLOBEX / ASIA / LONDON / NY_PRE / NY_AM / NY_LUNCH / NY_PM,
   and every report breaks down by them.
7. **Reuse before writing** (§2.4). A second implementation of a rule is the
   drift problem at birth.
8. **Never promote a 🟢/🟡/🔴 marker without naming the enforcer in the same
   edit**, and never quote a count you did not just measure. Both rules have
   already caught wrong claims in that document.
9. **Do not create another strategy document.** Extend §-numbered sections of
   `STRATEGY_WORKFLOW.md` instead. Two sources of truth is the failure this repo
   spent a week undoing. The one exception is `docs/architecture/HANDOVER.md`,
   which carries **state, never procedure**, is **rewritten rather than appended
   to**, and loses to the workflow doc and the backlog wherever they disagree.
   Start a session there; do not quote a count from it.

## Known C# bot defects

Do not re-derive these. `docs/architecture/BOT_FIX_BACKLOG.md` carries tickets
B1-B10 with a loop prompt; `scripts/trading_framework/tests/known_bot_divergences.py`
is its machine-readable half and a test fails if the two drift apart. The one to
know: **`BBMRReversionBot` allows 99 trades/day and the Python `mean_reversion`
that predicts it now allows no cap at all** (`risk.maxTradesPerDay: null` since
2026-09-05 — it enforced 3 before that), so that pair still cannot be compared at
the trade-set layer. **And the DEPLOYED copy of that bot still flattens at 16:15**,
past ADR-020's hard exit, while the repo source says 1600.

## Everything else

Global engineering rules (fail-fast, GPU awareness, directory layout) are in
`CLAUDE.md`. Repo-wide context anchors are in `CLAUDE.md`'s
*Workspace Context Anchors* list. Architectural decisions are ADRs in
`docs/architecture/ADR.md`.

**There is no CI in this repo.** Every gate above is green only when someone
runs `pytest scripts/trading_framework/tests -q`. Run it before claiming a
change is safe.
