# Agent Patch Loop — formalised implement → gate → review → apply cycle

**Status**: runnable. All modules landed; `python -m scripts.agent_loop.selftest` passes 5/5
offline. Not yet exercised against live models.
**Predecessor**: `scripts/agent_loop/ollama_patch_loop.py` — superseded, retained only so
in-flight artifacts stay readable. Three of its gates were defective (§4); do not use it.
**Driving work**: [RISKGUARD_HARDENING_HANDOVER.md](RISKGUARD_HARDENING_HANDOVER.md).

```powershell
# confirm every ticket still resolves (free; run before paying for anything)
.\.venv\Scripts\python.exe -m scripts.agent_loop --list

# offline end-to-end check of the loop itself (free, ~2 min, no models)
.\.venv\Scripts\python.exe -m scripts.agent_loop.selftest

# run one ticket; promotes into the live tree only on unanimous APPROVE
.\.venv\Scripts\python.exe -m scripts.agent_loop --ticket T3 --apply

# resume a candidate whose panel was unreachable, without re-paying for it
.\.venv\Scripts\python.exe -m scripts.agent_loop --ticket T2 --resume-raw logs/ollama_loop/T2/r4_impl_raw.txt

# clean up worktrees left behind by a crashed run
.\.venv\Scripts\python.exe -m scripts.agent_loop --prune
```

---

## 1. What this is

A batch loop that applies a *ticket* — a defect description plus a set of source regions — by
having one model rewrite those regions, gating the result mechanically, having a panel of
different models review it adversarially, and applying only on unanimous approval.

It is not an interactive pair-programmer. The unit of work is a ticket, the output is either an
applied patch or a pile of artifacts for a human arbiter, and every decision point in between is
recorded.

### Why not just use an existing tool

Surveyed before rebuilding:

| Tool | Why it doesn't replace this |
|---|---|
| [Aider](https://aider.chat/docs/usage/lint-test.html) | Owns the write cycle and has the lint/test retry loop, but is an interactive pair-programmer: no ticket file, no verdict semantics, no unanimous-approve gate, no arbiter step. |
| [ng/adversarial-review](https://github.com/ng/adversarial-review), [alecnielsen/adversarial-review](https://github.com/alecnielsen/adversarial-review), [formin/multi-model-review](https://github.com/formin/multi-model-review) | All **review-only** — they critique code something else already wrote. None owns implement→gate→apply. |
| [LiteLLM](https://github.com/BerriAI/litellm) | Would replace `providers.py` wholesale, but is a large transitive dependency for ~3 calls per round. Rejected in favour of a ~200-line shim; revisit if provider count grows. |
| [tree-sitter](https://tree-sitter.github.io/) | Evaluated for `regions.py` and **rejected** — see §4. |

What is genuinely ours: ticket-scoped regions, a gate ladder whose mechanical results override
model verdicts, unanimous-approve-to-apply, and an orchestrator directive that outranks reviewers.

---

## 2. Module map

```
scripts/agent_loop/
  cli.py         entry point: python -m scripts.agent_loop
  loop.py        round driver, review panel, arbitration
  gates.py       the mechanical gate ladder
  workspace.py   git-worktree isolation, run lock, baseline freeze
  regions.py     locate + splice source regions
  providers.py   multi-provider chat shim
  profiles.py    domain prompts, gate config, settled decisions
  selftest.py    offline end-to-end exercise with model calls stubbed
  tickets_p0.json  the RiskGuard/Copier P0 tickets
  ollama_patch_loop.py   superseded predecessor - do not use
```

### `workspace.py`

Every ticket runs in its own `git worktree`, sharing the repo's object store. The live tree is
never written to; an approved patch is copied back in an explicit final step. This removes the
hazard described in §4.5 rather than documenting it — and it makes `git checkout --` *safe*,
because it is now scoped to a directory that holds nothing a human authored.

- **Run lock** is hand-rolled rather than `filelock`, for one reason: it records the holder's PID
  and treats a lock whose process is gone as stale. A crashed run must not leave a permanent lock.
- **`capture_baseline`** refuses to run against a dirty worktree — a baseline must describe
  unmodified code.
- **`export_patch`** writes a readable unified diff for the arbiter. `final_blocks.json` is
  JSON-escaped C# and unreadable; the arbiter is the last gate and deserves better.
- `--prune` cleans up worktrees left by a crashed run.

### `loop.py`

The round driver. Its two behavioural differences from the predecessor are both consequences of
the T2 post-mortem in §4.1: **a reviewer that did not answer has not voted**, and **the panel
carries a wall-clock deadline** rather than relying on a per-request timeout.

### `profiles.py`

Everything domain-specific — prompts, `build_cmd`/`test_cmd`, the lock name, protected paths.
Pointing the loop at a different codebase is a config change, not a fork.

`Profile.settled` carries decisions the arbiter has already made, injected into *every* review
round. The predecessor required a human to remember `--orchestrator-note` by hand, and the same
three false positives were re-litigated across rounds because nobody did.

### `providers.py`

One `chat()` over three backends, selected by a `backend:model` prefix. A bare name defaults to
`ollama`, so existing ticket files and CLI flags keep working.

```
ollama:kimi-k2.7-code:cloud      anthropic:claude-opus-5      openai:gpt-oss-120b
```

Returns a uniform `Completion` carrying text, token counts, stop reason, elapsed seconds and a
computed `cost_usd`. Two properties matter more than the transport:

- **`ProviderError` is distinct from a model answering.** Transport failure after retries, an
  Anthropic `stop_reason: "refusal"`, or a missing key all raise. A reviewer that could not be
  reached has *not voted*, and callers must not score it as dissent. This is the direct fix for
  the T2 failure in §4.
- **`temperature` is dropped on models that reject it.** Anthropic returns 400 for
  `temperature`/`top_p`/`top_k` on Opus 5, Sonnet 5, Fable 5 and Opus 4.7+. The loop asks for
  `temperature=0.1` for implementer determinism; sending it to those models would fail 100% of
  calls.

Retries use jittered exponential backoff on 408/409/429/5xx only — a 400 is our bug and fails
identically on retry.

Pricing table (USD per 1M in/out) is in `PRICING`; Ollama cloud models are subscription-billed and
cost 0 per token here.

### `regions.py`

Anchors on a declaration, never a line number, so a ticket written today still resolves after
unrelated commits land. Extent is found by brace matching over a comment/string stripper.

`guard_unsupported_syntax` refuses any file containing a C# verbatim string (`@"..."`) or a block
comment (`/* */`) — the two constructs the stripper cannot parse. This converts a silent bad
splice into a loud, actionable error. Neither construct exists in the addons today.

`apply()` splices bottom-up per file so earlier spans stay valid, and skips blocks identical to the
original so an unchanged region never dirties the file.

### `gates.py`

See §3.

---

## 3. The gate ladder

Cost-ascending, so a patch that leaked a marker or invented a symbol never reaches a paid reviewer.
**Every gate here is deterministic, and where a gate and the panel disagree, the gate wins.**

| # | Gate | Catches | Overrides APPROVE |
|---|---|---|---|
| 0 | **protected** | ticket regions that would let the patch edit its own grader | yes — refuses to run |
| 1 | **static** | missing/empty blocks, non-ASCII, unbalanced braces or `#if/#endif`, changed leading indentation, leaked markers | yes |
| 2 | **compile** | every invented symbol, wrong C# version, `#if` damage | yes |
| 3 | **test** | behavioural regressions, against a frozen baseline | yes |
| 4 | **lock-scope** | `Flatten`/`Cancel`/`Submit`/`CreateOrder` reachable under `lock (_stateLock)` | yes |
| 5 | panel | two reviewers of different families; verdict is the worst returned | — |
| 6 | arbiter | human | — |

### Gate 0 — protected paths (anti reward-hacking)

The implementer is told to make the gates pass. Nothing in the loop's *shape* stops a ticket from
handing it the verifier itself. The literature is blunt about where that leads: verifiers are
[seldom robust and are gamed by deleting failing tests or monkey-patching the
verifier](https://arxiv.org/html/2606.26300v2), with [o3 reward-hacking in 30.4% of RE-Bench
runs](https://arxiv.org/pdf/2605.21384). So the verifier is made unreachable by construction:

```
DEFAULT_PROTECTED = ("*Tests.cs", "*.csproj", "scripts/agent_loop/*", "logs/agent_loop/*baseline*")
```

All five current tickets pass; regions aimed at `RiskGuardAddOnTests.cs`, the `.csproj`, or
`gates.py` are refused before any model is called.

### Gate 3 — test, against a frozen baseline

The suite is **not green and is not meant to be**: T4 and T5 have failing tests waiting that only
go green when those tickets land. A pass/fail gate would reject every candidate. What matters is
the *set* of failures.

- `[FAIL] <message>` lines are parsed into a set; `RESULTS: Passed = N, Failed = M` confirms the
  runner actually finished. A truncated run that happens to show no new failures proves nothing,
  so a missing `RESULTS` line fails the gate.
- The baseline is captured **once, before the first candidate is applied**, and never recomputed
  mid-run — otherwise a patch that breaks a test would simply widen the baseline and pass.
- Failures not in the baseline are regressions and fail the gate. Baseline failures that disappear
  are reported as progress — this is T4/T5's acceptance criterion, now machine-checked.

Current baseline (353 passed / 3 failed):

| Failing assertion | Defect |
|---|---|
| Exit copy is clamped to the follower's actual position (expected ≤ 1, got 5) | P0-5 |
| No copy is submitted to a RiskGuard-locked follower (got 1 order(s)) | P0-8 |
| Sub-one-contract micro→mini conversion is skipped rather than floored to 1 | P0-6 |

### Gate 4 — lock scope

Domain-specific and deliberately able to override an APPROVE: calling the broker under the state
lock is how this addon deadlocks with real money on the line, and reviewers have waved it through.

Implemented as an **ordered event scan** (lock keyword / open / close / risky call), not per-line
depth arithmetic — see §4 for why that distinction cost the project a working gate.

---

## 4. Findings that motivated the rebuild

Each of these was verified against the real repo, not inferred.

### 4.1 The review panel could not approve anything (T2, 2026-08-06)

`parse_review("")` returns `{'verdict': 'REVISE', 'blocker_count': 0}` — an empty response is
scored as a dissenting vote, indistinguishable from a real one.

| Round | glm-5.2 | deepseek-v4-pro |
|---|---|---|
| 2 | REVISE, 3 blockers (3.7 KB) | **0 bytes** |
| 3 | REVISE, 4 blockers (6.1 KB) | **0 bytes** |
| 4 | **HTTP 502** | **HTTP 502** |

`unanimous_approve` requires *all* reviewers to say APPROVE, so the gate was closed from round 1
regardless of candidate quality. Round 4 had both reviewers 502 and the `except` fabricate
`REVISE`, so the final candidate was never reviewed by anything. ~2.5 hours and four implementer
rounds of cloud spend on a ticket with no reachable pass state.

There was also a **2h03m gap** between `r4_build` (16:16) and `r4_review` (18:19) despite
`timeout=900`, so the panel needs its own wall-clock deadline, not just a per-request one.

**Fixed.** `parse_review` now returns `UNPARSEABLE` for an empty or marker-less response and
`UNREACHABLE` for a transport failure; neither is a vote. A panel missing any vote is **invalid** —
the round is not decided, the candidate is kept, and the run stops with `PANEL_UNREACHABLE` plus a
`--resume-raw` hint, rather than being silently vetoed. `review_panel` also bounds the whole set of
calls with `panel_deadline` (default 1800s), not just each request.

Both are covered by `selftest.py`: scenario 3 replays the empty-reviewer case and scenario 4 the
double-502 case, and both must yield `PANEL_UNREACHABLE`.

### 4.2 The lock-scope gate was inert for 88% of its targets

```
ORIGINAL gate on Allman (brace on next line)  -> 0 flags  MISSED
ORIGINAL gate on K&R    (brace on same line)  -> 1 flag   caught

RiskGuardAddOn.cs: 28 Allman-style lock(_stateLock), 4 K&R-style
```

After matching `lock (_stateLock)`, the old code evaluated `depth <= depth_at_lock` before the
opening brace on the *next* line arrived — closing the scope before it opened, so nothing inside
was examined. This codebase is Allman-braced throughout.

**Fixed**: ordered event scan, 9/9 cases correct (single-line, multi-line, nested, deep nesting,
calls outside the scope, calls inside strings, a different lock object).

### 4.3 tree-sitter was not worth its dependency

Evaluated as a replacement for the hand-rolled brace matcher, on the theory that it would fix two
stripper bugs (verbatim strings, block comments).

- All **18** regions across T1–T5 resolve **identically** under both locators. Zero differences.
- `RiskGuardAddOn.cs` and `TradeCopierEngine.cs` contain **zero** verbatim strings and **zero**
  block comments. Both bugs are latent, not live.

Rejected. `guard_unsupported_syntax` covers the latent case at no dependency cost. Revisit if a
second language is ever targeted, or if either construct appears.

### 4.4 `logs/ollama_loop/summary.json` is not a ledger

`main()` overwrites it wholesale per invocation. It currently records T1 as
`applied: false / MAX_ROUNDS_EXHAUSTED` even though T1 is committed at `5fd26995` — the resumed run
that actually landed it was never recorded. **Do not trust it.** Per-ticket `result.json` is
reliable; the run-level summary is not. `loop.py` will write an append-only JSONL ledger instead.

### 4.5 `git checkout --` as the revert mechanism is a data-loss footgun

The build gate applies a candidate, builds, then reverts with `git checkout --` — destroying any
uncommitted work in the same files. The handover has to warn "between tickets you must commit"
purely because of this.

**Fixed** by [git-worktree isolation](http://aq.dev/guides/git-worktrees-for-ai-coding-agents/),
now the standard isolation primitive for parallel agents. The loop runs in its own checkout, the
live tree is never written to, and promotion is an explicit final step. Verified: editing the
addon inside the worktree leaves `git status` on the live repo empty.

The "commit between tickets" rule in the handover no longer applies to the new tool.

### 4.6 Reviewers reviewed blind, and re-litigated settled decisions

Reviewers saw only BEFORE/AFTER of each region — not whether the patch compiled, not whether tests
passed, and not the decisions the arbiter had already made. §5 of the handover exists purely as a
human-maintained list of false positives reviewers kept raising.

**Fixed**: the review prompt now carries a "Mechanical gates already passed" summary, and
`Profile.settled` is injected into every round automatically.

---

## 5. Deferred — test-strategy follow-ups

Not loop architecture, so not blocking the rebuild, but the highest-value next moves for the
RiskGuard work itself:

- **Property-based stateful testing** ([CsCheck](http://anthonylloyd.github.io/blog/2024/07/07/cscheck-happy-state)
  has stateful and parallel testing, C#-first). "A position is never uncovered beyond the grace
  window" is a *property*, not an example. P0-1 and P0-4 are both sequence bugs that example tests
  missed and a state-machine generator would find mechanically.
- **Mutation testing** (Stryker.NET) — the mechanical answer to "does my suite have teeth", which
  is exactly what commit `ddba3433` answered by hand.
- **Record/replay cassettes** for the loop's own model calls, so the gate ladder can be tested
  without paying for models. A tool whose job is gating code on tests currently has no tests.

---

## 6. Conventions

- **Stage explicit paths. Never `git commit -a`.** Two unrelated background processes commit to
  this repo; unrelated commits landed between every pair of commits in this effort.
- The tool pins to `.venv` (Python 3.12). The predecessor was being run under `C:\Python314`,
  which is a separate interpreter with a different package set.
- Artifacts land in `logs/ollama_loop/<TICKET>/` — one file per round per stage, plus
  `result.json`. Everything a human arbiter needs to second-guess a verdict is on disk.
