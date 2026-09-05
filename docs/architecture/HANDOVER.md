# Handover — strategy workflow & bots

**Rewritten 2026-09-05.** State only.

> **THIS FILE IS REWRITTEN, NEVER APPENDED TO.** The sibling repo's handover
> accretes and its §0 is stale by many sessions; the same failure is what put
> ~43KB of closed-defect narrative into CLAUDE.md with rotted headline numbers.
> So: **no closure narrative here.** A thing that is finished belongs in
> STRATEGY_WORKFLOW.md §11 under its item number, or in BOT_FIX_BACKLOG.md under
> its `B` id, and nowhere else. If this file disagrees with either of those,
> **they win** — this is a pointer, not a source.
>
> **Do not quote a count from this file.** Run the thing.

---

## 0. Read these, in this order

1. **[STRATEGY_WORKFLOW.md](STRATEGY_WORKFLOW.md)** — canonical and sufficient.
   What a strategy is, the one command, the stage gates, the three layers of
   parity, §9's definition of "validated", §11's open items. Read §0.1, §1.3,
   §9 and §11 before touching anything.
2. **[BOT_FIX_BACKLOG.md](BOT_FIX_BACKLOG.md)** — B1–B9, the C# worklist, with a
   loop prompt whose step 0 is a first-principles read of which layer a change
   belongs in.
3. This file — what is in flight *right now* and what will bite you.

Everything else describing how to build, run or judge a strategy is stale.

## 1. Two standing constraints

**Do not deploy to NT8 and do not recompile.** A successful compile wipes every
static singleton in a live instance. That is the user's call, always, and there
are two things queued behind it (§11 items 11, 15, 20).

**NT8 is authoritative for behaviour.** When Python and NT8 disagree, presume
Python is wrong. Parity is defined on the **trade set** and judged on
**geometry** — a constant price offset *is* the adjustment basis and is not a
divergence.

## 2. Where the workflow stands

`scripts/trading_framework/workflow.py` is the one entry point. It evaluates
**13 promotion criteria** and prints each PASS / FAIL / NOT EVALUATED. Every one
of them now *measures* something — as of 2026-09-05 there is no criterion left
that could never fail, which had been true of two of them for months.

Run the suite rather than trusting a number here:

```powershell
.\.venv\Scripts\python.exe -m pytest scripts/trading_framework/tests/ -q
```

### What changed on 2026-09-05, in one line each

An external review of the workflow returned seven findings. All seven were
verified against the source and all seven were real. They are listed here
because **they change the numbers**, not as a changelog:

| Was | Now |
|---|---|
| Search scored by `VectorizedBacktester`, report by `NT8ParityBacktester` — parameters selected under one payoff and judged under another | `run_backtest.build_engine` is the one constructor, called once, before the search |
| Four execution policies; the canonical document decided nothing | `config/defaults.py::execution_policy()` resolves all of it from `trading_defaults.json` |
| A fixture declaring `profileHash: sha256:STALE` scored `nt8_ground_truth` PASS | The fixture's hash *and* strategy are compared with the current frozen profile |
| Python "Profit Target" vs NT8 "Stop Loss" returned a full parity PASS | `EXIT_FAMILIES` maps both vocabularies; the verdict judges it |
| `out_of_sample` checked that `--oos-start` was *passed* | `statistically_sufficient`: ≥120 trades, ≥3 regimes, bootstrap CI off zero |
| Prop Monte Carlo permuted trades independently; the scheme was in no artifact | `daily_block` default, scheme recorded, historical path must also survive |
| `has_bot` passed on a filename | `_deployment_state` compares the repo source to the deployed copy |

**The reported numbers for every strategy are now produced under a different
execution policy than before** — 1 contract not 2, $0.62 not $1.40, 1 tick of
slippage not 0, no entry cut-off rather than 09:45–15:30, lunch reported rather
than deleted, 15:45 flatten rather than 15:55, no daily trade cap rather than 3.
**Nothing has been re-run under it yet.** Any stored result predating this is
not comparable to one produced after it.

## 3. The four things that will bite you

**The deployed `BBMRReversionBot` is not the repo one.** It carries
`FlattenBy = 1615`, past ADR-020's 16:00 hard exit; the repo source says 1600.
So an NT8 capture taken from the current install is evidence about a bot that
violates ADR-020. §11 item 20. Do not fix it by deploying.

**No bot derives from `GovernedStrategy` yet.** The base class, the mandated
`SetupEvaluation`, the sealed `CheckForSignal()` and the generated
`DecisionLog.cs` all exist and are gated. Until one bot inherits it, every gate
roster diff is one-sided — and **the gate roster is layer 0 of parity**.
`mean_reversion` evaluates 2 conditions and `BBMRReversionBot` has 20
parameters, so no recall figure between them means anything yet. §11 item 15 /
B7+B8. Needs a recompile.

~~**The 200:1 funnel number is stale.**~~ **Re-measured 2026-09-05 and the
stale number is dead**: under the current frozen policy, 3,188 hunter entries
became 2,527 trades (1.26:1); the engine's gates are now counted per reason
and rendered in every tearsheet; the only gate still biting is the order
timeout. Item 13 closed.

**`target1_price` never reaches the sanctioned engine.** `hunt()` declares it,
the parity engine drops it and substitutes `queen_bps`/`runner_bps`. §11 item 19.

## 4. What to pick up

In the order I would do them.

| | Item | Why this order |
|---|---|---|
| 1 | **§11 item 18** — instrument the 14 hunters | Per-strategy population work, each one small. `mean_reversion` is the reference. Frozen in `tests/uninstrumented.py`, which may only shrink |
| 2 | **REG-1 — the remaining arms** (`research_backlog/13_market_regime_definition.md`) | The first cheap step is done (the live lookahead defect in `ib_breakout_filter.py` is fixed and pinned); what remains is the candidate comparison (balance/persistence/separation/stability) and killing the duplicated bucketing code |
| 3 | **§11 item 3** — hosted CI | `tools/ci_local.py` + `.githooks/pre-commit` exist and are authoritative. What is missing is the fresh-clone case, which a local run cannot cover |
| 4 | **§11 items 4, 8** | Parameter documents for non-ICT families; migrate off the legacy `session_block` |

Done this session (2026-09-05, recorded in their own documents): REG-1 first
cheap step; §11 item 13.

Waiting on the user, not on code: §11 items 2 (`WickType`), 11 (deploy), 15
(deploy), 17/B9 (which `RiskManagerBase` changes to land), 20 (deploy).

## 5. Habits this codebase enforces

Learned the hard way, each one from a defect:

- **A green that can never be red is not a gate.** For every status boolean, name
  the input that makes it false. If you cannot, delete it.
- **Every detector needs a negative control.** Three of the gates written on
  2026-09-05 went red on their first run and were right to — the literal scan
  could not see `contracts: int = 2`, `TRAIL` sat below `STOP` so a trailing exit
  collapsed into a hard stop, and treating identical-but-unrecognised exit text
  as "uncomparable" broke two passing tests immediately.
- **A source scan must tell a call from the prose describing one.** Count by AST.
  A substring scan for `VectorizedBacktester(` read 3 and all three were
  docstrings explaining the defect.
- **Unreadable is not the same fact as wrong.** NaN means "not measured", 0.0
  means "measured as zero", and only one of them is detectable downstream.
  Never average the two.
- **Never promote a 🟢/🟡/🔴 marker without naming the enforcer in the same edit.**
- **Do not `git add -A`.** This working tree carries unrelated in-flight work
  (`scripts/mining/`, `web/lib/vela-spike/`, four research-backlog files). Stage
  by path.
- **Bash heredocs lose backslash escapes here.** Use the Edit/Write tools for
  source edits; it has broken patches twice in one session.
- **The console is cp1252.** An em-dash, `≤` or `§` in report output raises
  `UnicodeEncodeError`. Report text is ASCII.
