# NT8 Addon Repo Split — migration plan (EXECUTED)

**Status**: ✅ **EXECUTED 2026-08-12.** Written earlier the same day (session 15).
**Decided by the operator**: **two repos** — the MCP bridge separate, RiskGuard + copier together.
Both are **public**.

| Repo | Local | Commits | Gates at handover |
|---|---|---|---|
| [nt8-riskguard](https://github.com/vinay-veerappa/nt8-riskguard) | `C:\Users\vinay\nt8-riskguard` | 162 | 926 tests / 0 failed; cm3 14 killed; cm4 10 killed; both structural checks green |
| [nt8-mcp-bridge](https://github.com/vinay-veerappa/nt8-mcp-bridge) | `C:\Users\vinay\nt8-mcp-bridge` | 34 | harness 9 / 0 failed; **bridge itself still not executed — see below** |

Core tagged **`v1.0.0`**; the bridge pins it at `vendor/nt8-riskguard` with a `.gitmodules`
entry, verified by a fresh `--recurse-submodules` clone.

> ## What the plan got wrong, and what was done instead
>
> **1. `git subtree split` was the wrong tool** (§0, §4). It follows one path and does not
> follow renames, but the addon lineage has **three** historical paths —
> `ninjatrader-addon/` → `scripts/strategies/nt8/addons/` (`671d8a18`) →
> `scripts/ninjatrader/addons/` (`a19c2adc`). A single subtree split yields 80 commits
> starting at the Jul-30 restructure; `RiskGuardAddOn.cs` alone loses 18 commits including
> its creation, and the csproj/tools/tickets/docs histories cannot come along at all.
> **Used `git-filter-repo` instead**, one pass per repo with a `--commit-callback` that maps
> all three prefixes onto the new layout. Result: **162 commits reaching the true origin**.
>
> **2. Collapsing three paths onto one silently deletes files.** `a19c2adc` *copied* the
> addons to the new path without removing the old ones, and the stale duplicates were tidied
> up later by unrelated commits (`671d8a18`, `b8f410f4`). Mapped naively, those cleanups
> delete the *live* file. It cost `RiskManagerAddOn.cs` and `TradeCopierWindow.cs` — the only
> two files no later commit happened to rewrite, so nothing resurrected them. Nothing warns
> you; the extraction reports success. The fix is to drop deletes on superseded prefixes,
> justified by measurement: `scripts/ninjatrader/addons/` has never had a single deletion.
> **A blob-level diff of every migrated path against the source is the only check that
> catches this** — run one.
>
> **3. `DynamicAtmManager.cs` belongs to the core, not the bridge** (§2). §2 counted 4
> references from `McpBridgeAddOn` and missed **32 from `RiskGuardAddOnTests.cs`**. Moving it
> produced 71 compile errors and would have dropped its coverage, since the bridge has no
> harness. It stays in the core; the bridge reaches it through `vendor/`.
>
> **4. The core's test suite depended on the bridge.** `TestP2_38` regex-asserted on
> `McpBridgeAddOn.cs`'s *source text* — the exact dependency direction §1 forbids. Its three
> source assertions moved to the bridge's harness; the behavioural half stayed. **That is why
> the core reports 926, not 929.**
>
> **5. WPF was never the blocker** (§5). `net8.0-windows` + `UseWPF` supplies every WPF type
> the bridge touches, so the WPF/HTTP separation §5 proposed is unnecessary. The real blocker
> is that 16 of the 19 NT8 types the bridge needs are stubbed *inside* the core's 663 KB test
> file, which owns a `Main()` and so cannot be imported. Measured: **330 compile errors, 23
> distinct missing types**. Ordered remedy in `nt8-mcp-bridge/tests/README.md`.
>
> **6. §2's "tvDownloadOHLC keeps **Nothing**" could not hold literally.** `scripts/ninjatrader/`
> still holds strategies, indicators and shared classes, so this repo keeps
> `sync_nt8_strategies.py` (addon half removed, `--only addons` now exits 2) and
> `NT8_FILE_ORGANIZATION.md`. §2's doc list was also short two docs that are *about* the
> migrated code: `RiskGuardAddOn.md` (subject of open defect `P2-26`) and
> `TRADE_COPIER_PRD.md`. Both moved.
>
> **7. The mutation batteries were a lying gate.** They printed `SURVIVORS: [...]` and exited
> 0 regardless, so the CI step §6 asks for would have been green with survivors. They now
> exit 1, an unappliable ANCHOR included.
>
> Also, unrelated to the plan but found on the way: `test_version_alignment` in
> `tests/test_mcp_stack_all.py` had been raising `FileNotFoundError` since `671d8a18`, so it
> asserted nothing for two weeks.
>
> **Still open:** CI workflows are parked at `ci/github-workflow-ci.yml` in both repos —
> activating them needs `gh auth refresh -s workflow`. And two stale files
> (`RiskGuardAddOnTests.cs`, `TestingStubs.cs`) remain in the live NT8 `AddOns/` folder: the
> old flat layout deployed the test suite into the trading assembly, and the new tools
> correctly no longer do.

> **Why this exists.** The NT8 addons were never meant to live inside `tvDownloadOHLC`. Nothing on
> the Python side compiles, imports or tests them; they are C# that NinjaTrader builds. The result
> is a repo that mixes a research/trading codebase with an unrelated C# product, and **four copies
> of the same addon** drifting against each other.

---

## 0. Read this before you start

* **This is a MECHANICAL migration with a NON-mechanical trap**: NT8 has no package manager. All
  addons compile into **one assembly** (`NinjaTrader.Custom.dll`) and call each other's types
  directly. Two repos therefore need a **compile-time source dependency**, not a package
  reference. Section 3 is how.
* **`git subtree split` is the extraction tool** — it preserves the 15 sessions of history. Do not
  copy files into a fresh repo; that throws away the reasoning trail this project depends on
  (`RISKGUARD_COPIER_HARDENING_PLAN.md` keys defects to `file:line` across that history).
* **Do not start this with uncommitted work anywhere.** All three repos were at 0 unpushed when
  this plan was written; get back to that state first.

## 1. The measured seam — why two repos is viable

Raw reference counts look alarming (`McpBridgeAddOn` names `RiskGuardAddOn` 37 times and
`TradeCopierEngine` 26 times). **The actual API surface is small and already a facade**, measured
2026-08-12:

| Consumer → provider | Distinct members | Shape |
|---|---|---|
| `McpBridgeAddOn` → `RiskGuardAddOn` | ~13 | **all** through `RiskGuardAddOn.Instance.*` — `Config`, `IsArmed`, `IsAccountLocked`, `UnlockAccount`, `SaveAndReloadConfig`, `RunFirmDiagnostics`, `ResetStateForDev`, `ResetFsm`, `ReloadPersistedState`, `GetMode`, `GetFsmSnapshots`, `GetAccountSnapshots`, plus static `Version` |
| `McpBridgeAddOn` → `TradeCopierEngine` | ~13 | `.Instance.*` — `SaveToDisk`, `LoadFromDisk`, `GetGroups`, `GetRelationships`, `ApplyGroupRequest`, `ApplyRelationshipRequest`, `AddFollowerToGroup`, `RemoveFollowerFromGroup`, `RemoveGroup`, `RemoveRelationship`, `RefreshAccountSubscriptions`, `UnsubscribeAllAccounts`, plus static `IsSimulationAccount` |

**Two singleton facades, ~26 members total.** That is a genuine interface, which is what makes the
split defensible rather than arbitrary.

⚠️ **The dependency is one-way and must stay that way.** `RiskGuardAddOn` names
`TradeCopierEngine` once and nothing names `McpBridgeAddOn` at all. **The bridge depends on the
core; the core must never depend on the bridge.** If that inverts, the two repos become mutually
recursive and the split is dead. Add a check for it (§6).

## 2. Repo layout

### `nt8-riskguard` — the core (new repo)

Everything the copier and guard need to build and be tested on their own.

```
addons/    RiskGuardAddOn.cs  RiskManagerAddOn.cs  TradeCopierEngine.cs
           TradeCopierWindow.cs  CopierReconciler.cs  PropFirmProtectionSuite.cs
tests/     RiskGuardAddOnTests.cs  TestingStubs.cs  RiskGuardTests.csproj
tools/     sync_nt8.py            (from scripts/utils/sync_nt8_strategies.py)
mutation/  mutate_cm3.py  mutate_cm4.py
agent/     nt8_riskguard.py  tickets_*.json
docs/      RISKGUARD_COPIER_HARDENING_PLAN.md  RISKGUARD_HARDENING_HANDOVER.md
           NT8_FILE_ORGANIZATION.md
```

### `nt8-mcp-bridge` — the bridge

```
addons/    McpBridgeAddOn.cs  DynamicAtmManager.cs
vendor/    nt8-riskguard/     <- submodule, pinned to a TAG (see §3)
tests/     (NEW — see §5)
```

**`DynamicAtmManager.cs` goes with the bridge**, not the core: it is referenced **only** by
`McpBridgeAddOn` (4 refs) and references nothing else. Moving it removes work from the seam.
**`PropFirmProtectionSuite.cs` goes with the core** — it is a risk concern and `RiskGuardAddOn`
uses it.

### What `tvDownloadOHLC` keeps

**Nothing.** No addon source, no csproj, no NT8 sync tool. It keeps only a pointer in `CLAUDE.md`
saying where the addons now live. This is the whole point of the exercise.

## 3. The compile-time dependency (the part with no package manager)

`nt8-mcp-bridge` carries `nt8-riskguard` as a **git submodule at `vendor/nt8-riskguard`, pinned to
a tag** (`v1.0.0`, …), and its deploy tool syncs **both** trees into
`Documents/NinjaTrader 8/bin/Custom/AddOns/`.

* A tag, not a branch — the bridge must state which core it was built against, the same discipline
  as `requirements.txt` pinning `agent-loop@v0.6.6`.
* **Add `.gitmodules` when you create it.** `tvDownloadOHLC` shipped five gitlinks with no
  `.gitmodules` at all, so a fresh clone got five empty directories (fixed 2026-08-12, commit
  `49cfc5f1`). Do not repeat it.
* Deploying the bridge alone is **never** valid — the assembly will not compile without the core.
  The deploy tool must refuse rather than half-deploy.

## 4. Execution — in order

```bash
# 1. Extract WITH history. Run in tvDownloadOHLC, on a scratch branch.
git subtree split -P scripts/ninjatrader/addons -b split/nt8-addons

# 2. Seed nt8-riskguard from that branch, then delete the bridge files from it.
#    Seed nt8-mcp-bridge the same way, deleting everything else.
#    Both keep the shared history; each prunes what it does not own.

# 3. In nt8-riskguard, repath (this is the entire coupling surface):
#      tests/RiskGuardTests.csproj      3 lines: ..\scripts\ninjatrader\addons\ -> ..\addons\
#      tools/sync_nt8.py                1 line:  source dir
#      agent/nt8_riskguard.py           2 lines: file_scope_whitelist, test_sources
#      agent/tickets_*.json             every "file": "scripts/ninjatrader/addons/..." -> "addons/..."
#      docs/*.md                        path references

# 4. Verify BEFORE deleting anything from tvDownloadOHLC:
#      dotnet build tests/RiskGuardTests.csproj && dotnet run --project tests/RiskGuardTests.csproj
#      -> must be 929 passed, 0 failed (session 15's number)
#      python mutation/mutate_cm3.py   -> 14 mutants, all killed
#      python mutation/mutate_cm4.py   -> 10 mutants, all killed

# 5. Only then: git rm the addon tree from tvDownloadOHLC, update CLAUDE.md.
```

## 5. ⚠️ The split must not formalise the untestability

`McpBridgeAddOn.cs` is **currently `<Compile Remove>`d from `RiskGuardTests.csproj`** (WPF deps), so
it has **zero executed coverage** — that is `P2-27`, and it is exactly why session 15 had to move
the copier's request→object mapping onto the engine to test it at all.

**If `nt8-mcp-bridge` ships with no test project, the split makes that permanent and blesses it.**
The new repo must get a harness that compiles `McpBridgeAddOn.cs` against the vendored core plus
`TestingStubs.cs`. If the WPF dependency blocks that, the remedy is to separate the WPF surface
from the HTTP handlers — **not** to accept an untested bridge. Same rule for
`TradeCopierWindow.cs`, which is untested for the same reason and is scheduled for a rewrite
(handover §5.5).

## 6. Checks worth automating in the new repos

* **Direction check**: fail CI if the core names `McpBridgeAddOn` (§1's one-way rule).
* **No fourth copy**: fail if an addon `.cs` exists outside `addons/`. `ninjatrader-mcp` currently
  keeps a copy at `nt8-addon/` that was **hardlinked to the deployed NT8 file**, so every deploy
  silently dirtied that repo (broken 2026-08-12; see handover §5.3a).
* **Deploy parity**: the sync tool's `--verify` already does this; keep it and run it in CI.

## 7. What this does NOT fix, and must not be conflated with

* `P0-63` (the mirrored stop has never trailed), `P1-57`, and the rest of handover §5. **Moving code
  between repos fixes no defect.** Do the migration as its own change, green before and after.
* The `ninjatrader-mcp` repo's `nt8-addon/` copy. Once `nt8-mcp-bridge` exists, that directory
  should become a README pointing at it, or consume it as a submodule — decide then, not now.
* `docs/archive/temp_repo` (146 MB vendored `tradingview/lightweight-charts`). Unrelated cleanup,
  recorded so it is not lost. **The dead `scripts/setup/` cluster that referenced it was deleted
  2026-08-12** — see that commit; 31 one-shot scripts against a UI that no longer exists.

## 8. Sequencing

The operator chose: **plan now, execute in a new session.** Handover §5.5 has the next session
opening with `P0-63` + the `P1-22` log line. Decide there whether the split goes before or after —
doing it **first** means those commits do not have to be migrated; doing it **second** means the
safety fix lands sooner. Both are defensible; do not do them interleaved.
