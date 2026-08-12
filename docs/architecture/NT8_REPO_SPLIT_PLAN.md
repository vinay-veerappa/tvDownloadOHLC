# NT8 Addon Repo Split — migration plan

**Status**: PLANNED, not executed. Written 2026-08-12 (session 15). Execute in a fresh session.
**Decided by the operator**: **two repos** — the MCP bridge separate, RiskGuard + copier together.

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
