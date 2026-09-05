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

## Eight rules that are not negotiable

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
6. **Reuse before writing** (§2.4). A second implementation of a rule is the
   drift problem at birth.
7. **Never promote a 🟢/🟡/🔴 marker without naming the enforcer in the same
   edit**, and never quote a count you did not just measure. Both rules have
   already caught wrong claims in that document.
8. **Do not create another strategy document.** Extend §-numbered sections of
   `STRATEGY_WORKFLOW.md` instead. Two sources of truth is the failure this repo
   spent a week undoing.

## Everything else

Global engineering rules (fail-fast, GPU awareness, directory layout) are in
`CLAUDE.md`. Repo-wide context anchors are in `CLAUDE.md`'s
*Workspace Context Anchors* list. Architectural decisions are ADRs in
`docs/architecture/ADR.md`.

**There is no CI in this repo.** Every gate above is green only when someone
runs `pytest scripts/trading_framework/tests -q`. Run it before claiming a
change is safe.
