# NinjaTrader 8 File Organization

> **Date**: 2026-07-30, updated 2026-08-07
> **Status**: **Adopted (Option A).** The restructure to `scripts/ninjatrader/` has happened —
> that is where the code lives now. Everything below the "Current State" heading describes the
> *pre-migration* layout and is kept only as the record of why the move was made. For how things
> stand today, read this section.

---

## ⚠️ The addons left this repo on 2026-08-12

Everything this document says about `scripts/ninjatrader/addons/`, `ninjatrader-addon/` and
`--only addons` **describes a layout that no longer exists here**. The addon half of the
split was executed; see [NT8_REPO_SPLIT_PLAN.md](NT8_REPO_SPLIT_PLAN.md).

| What | Where it lives now | Deploy with |
|---|---|---|
| RiskGuard, TradeCopier, reconciler, ATM manager, PropFirm suite | [nt8-riskguard](https://github.com/vinay-veerappa/nt8-riskguard) `addons/` | `python tools/sync_nt8.py` |
| `McpBridgeAddOn.cs` | [nt8-mcp-bridge](https://github.com/vinay-veerappa/nt8-mcp-bridge) `addons/` | `python tools/deploy.py` (deploys the bridge **and** its vendored core) |

Deploying either addon repo without the other fails the whole NT8 Custom assembly, which
stops **every** addon loading, the risk guard included. `nt8-mcp-bridge/tools/deploy.py`
refuses rather than half-deploying.

**This repo still owns strategies, indicators and shared classes**, and the rest of this
document remains authoritative for those.

## Source of truth and deployment — strategies and indicators (this repo)

```
scripts/ninjatrader/strategies/**/*.cs   ← source of truth for NT8 Strategies
scripts/ninjatrader/indicators/**/*.cs   ← source of truth for NT8 Indicators
scripts/ninjatrader/shared/*.cs          ← compiled with the strategies
        │
        │  scripts/utils/sync_nt8_strategies.py
        ▼
%USERPROFILE%/Documents/NinjaTrader 8/bin/Custom/{Strategies/Vinay,Indicators}/
        ← live, untracked, compiled by NT8
```

**Deploying:**

```bash
python scripts/utils/sync_nt8_strategies.py --verify   # what has drifted?
python scripts/utils/sync_nt8_strategies.py            # deploy
# then recompile in NT8 (F5, or the nt_compile MCP tool) and confirm 0 errors
```

`--only addons` now exits 2 with a pointer to the two repos, rather than reporting success
having deployed nothing.

**Rules learned the hard way (P2-28, and the 2026-08-07 deployment):**

- **Never copy `.cs` into the NT8 tree by hand.** Use the script. Manual copies are how canonical
  and deployed drift apart in the first place.
- **Always scope with `--only`.** An unscoped sync also pushes strategies and indicators. During
  the RiskGuard shadow deployment that would have installed 21 unrelated indicator files into a
  live NT8 mid-session.
- **Never put backups inside `bin/Custom/`.** NT8 compiles that tree *recursively*, so a folder of
  `.cs` backups produces duplicate-type errors. Backups belong in
  `Documents/NinjaTrader 8/_riskguard_backups/`.
- **Normalise line endings before believing a diff.** The repo is LF, the NT8 tree tends to CRLF.
  A raw `diff` reports every line of every file as changed. The sync script's hash now normalises;
  by hand, use `diff --strip-trailing-cr`.
- **A hard link from repo to NT8 was considered and rejected.** It would make every keystroke
  change what the live trading system compiles next. The explicit deploy step is deliberate.
- `mcp/ninjatrader-mcp/nt8-addon/` holds its own partial copies, but that path is a **git
  submodule** — fix it in that repo, not this one.

---

## Current State *(pre-migration, historical)*

```
scripts/strategies/nt8/           ← all NT8 code lives here
├── addons/                        ← AddOn .cs files (synced to AddOns/)
├── base/                          ← base classes (RiskManagerBase, IntradayStrategyBase)
├── ib_breakout/                   ← IB strategies (3 bots + IBStrategyBase)
├── ema_pullback/                  ← EMA pullback strategy
├── failed_auction/                ← Failed auction strategy
├── vwap_reclaim/                  ← VWAP reclaim strategy
└── indicators/                    ← NEW (just created)
    └── redtail/                   ← 14 RedTail indicator .cs files
```

**Problems:**
1. Indicators and strategies are under `strategies/nt8/` — misleading path name
2. `sync_nt8_strategies.py` doesn't sync indicators (no `Indicators/` mapping)
3. As we build more indicators (IB Confluence, etc.), the flat structure will get messy
4. `ninjatrader-addon/` has duplicate strategy files — confusing source-of-truth

---

## Proposed Structure

```
scripts/ninjatrader/               ← TOP-LEVEL: all NT8 NinjaScript code
├── strategies/                    ← Strategy .cs files
│   ├── base/                      ← Base classes (RiskManagerBase, IntradayStrategyBase)
│   ├── ib_breakout/               ← IB strategies (3 bots + IBStrategyBase)
│   ├── ema_pullback/              ← EMA pullback strategy
│   ├── failed_auction/            ← Failed auction strategy
│   └── vwap_reclaim/              ← VWAP reclaim strategy
├── indicators/                    ← Indicator .cs files
│   ├── vinay/                     ← Our custom indicators
│   │   └── IBConfluenceIndicator.cs  ← (to be built)
│   ├── redtail/                   ← RedTail indicators (third-party, open-source)
│   │   ├── RedTailMarketStructure.cs
│   │   ├── RedTailAutoVWAP.cs
│   │   ├── RedTailKeyLevels.cs
│   │   └── ... (14 files)
│   └── third_party/               ← Other third-party indicators (future)
│       ├── FairValueGapICT.cs     ← (if we fork/modify)
│       └── ...
├── addons/                        ← AddOn .cs files
│   ├── McpBridgeAddOn.cs
│   ├── RiskGuardAddOn.cs
│   └── ...
└── shared/                        ← Shared code (referenced by both strategies + indicators)
    └── IBConfluenceEngine.cs      ← (to be extracted from IBStrategyBase)
```

### NT8 destination mapping (sync script)

```
scripts/ninjatrader/strategies/**/*.cs  →  Documents/NinjaTrader 8/bin/Custom/Strategies/Vinay/
scripts/ninjatrader/indicators/**/*.cs  →  Documents/NinjaTrader 8/bin/Custom/Indicators/
scripts/ninjatrader/addons/*.cs         →  Documents/NinjaTrader 8/bin/Custom/AddOns/
scripts/ninjatrader/shared/*.cs         →  Documents/NinjaTrader 8/bin/Custom/Strategies/Vinay/  (shared classes compile with strategies)
```

Note: NT8 compiles all `.cs` in `Custom/Strategies/Vinay/` together. Shared classes like `IBConfluenceEngine` need to be in a folder NT8 can find — the simplest approach is to sync them to `Strategies/Vinay/` alongside the strategies (NT8 doesn't enforce folder = namespace). Alternatively, put them in `Custom/Indicators/` if they're indicator-only.

---

## Migration Plan

### Step 1: Create the new folder structure
```powershell
mkdir scripts/ninjatrader/strategies/base
mkdir scripts/ninjatrader/strategies/ib_breakout
mkdir scripts/ninjatrader/strategies/ema_pullback
mkdir scripts/ninjatrader/strategies/failed_auction
mkdir scripts/ninjatrader/strategies/vwap_reclaim
mkdir scripts/ninjatrader/indicators/vinay
mkdir scripts/ninjatrader/indicators/redtail
mkdir scripts/ninjatrader/indicators/third_party
mkdir scripts/ninjatrader/addons
mkdir scripts/ninjatrader/shared
```

### Step 2: Move existing files
- `scripts/strategies/nt8/base/*.cs` → `scripts/ninjatrader/strategies/base/`
- `scripts/strategies/nt8/ib_breakout/*.cs` → `scripts/ninjatrader/strategies/ib_breakout/`
- `scripts/strategies/nt8/ema_pullback/*.cs` → `scripts/ninjatrader/strategies/ema_pullback/`
- `scripts/strategies/nt8/failed_auction/*.cs` → `scripts/ninjatrader/strategies/failed_auction/`
- `scripts/strategies/nt8/vwap_reclaim/*.cs` → `scripts/ninjatrader/strategies/vwap_reclaim/`
- `scripts/strategies/nt8/addons/*.cs` → `scripts/ninjatrader/addons/`
- `scripts/strategies/nt8/indicators/redtail/*.cs` → `scripts/ninjatrader/indicators/redtail/`

### Step 3: Update sync script
Update `sync_nt8_strategies.py` to:
- Read from `scripts/ninjatrader/` instead of `scripts/strategies/nt8/`
- Sync `indicators/` subfolders to `Custom/Indicators/` (flatten — NT8 expects all indicators in one folder)
- Sync `shared/` to `Custom/Strategies/Vinay/` (so strategies can reference shared classes)

### Step 4: Remove old `scripts/strategies/nt8/` folder
After verifying the sync works from the new location.

### Step 5: Update all references
- `CLAUDE.md` — update any paths referencing `scripts/strategies/nt8/`
- `.github/copilot-instructions.md` — update sync command
- `sync_nt8_strategies.py` — update source paths
- Memory files — update any path references

---

## Why this structure

| Principle | How it's addressed |
|---|---|
| **Clear separation** | `strategies/` vs `indicators/` vs `addons/` vs `shared/` — no ambiguity |
| **Third-party isolation** | `indicators/redtail/` and `indicators/third_party/` keep external code separate from ours |
| **Our indicators have a home** | `indicators/vinay/` is where `IBConfluenceIndicator` and future custom indicators live |
| **Shared code** | `shared/` for classes used by both strategies and indicators (e.g., `IBConfluenceEngine`) |
| **Sync-friendly** | Each top-level folder maps 1:1 to an NT8 `Custom/` subfolder |
| **Scalable** | New strategies/indicators just drop into the right folder — no structural changes needed |
| **Git-friendly** | Moving files preserves history with `git mv` |

---

## Alternative: Keep `scripts/strategies/nt8/` but add `indicators/`

If you prefer not to move existing strategy files, we can keep the current root and just formalize the indicators subfolder:

```
scripts/strategies/nt8/
├── addons/
├── base/
├── ib_breakout/
├── ema_pullback/
├── failed_auction/
├── vwap_reclaim/
├── indicators/
│   ├── vinay/                     ← our custom indicators
│   ├── redtail/                   ← RedTail (already here)
│   └── third_party/               ← other third-party
└── shared/                        ← shared classes
```

This is less work (no file moves) but the path `scripts/strategies/nt8/indicators/` is slightly misleading since indicators aren't strategies.

---

## Decision needed

1. **Option A**: Full restructure to `scripts/ninjatrader/` (cleaner, more work)
2. **Option B**: Keep `scripts/strategies/nt8/` and add `indicators/vinay/` + `shared/` (less work, slightly misleading path)

Either way, the sync script needs updating to handle indicators → `Custom/Indicators/`.