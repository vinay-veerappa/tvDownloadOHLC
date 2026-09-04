# ADR-025: NT8 Bot Strategy & Indicator Ownership

> **Status**: Accepted — 2026-09-04
> **Context**: three-way ownership mess uncovered while reviewing the ICT FVG/CISD strategy

## The Rule

| Artifact | Canonical home | Deployed by |
|---|---|---|
| **Trading bots** (`*Bot.cs`) | `tvDownloadOHLC/scripts/ninjatrader/strategies/<feature>/` | `tvDownloadOHLC` → `python scripts/utils/sync_nt8_strategies.py` |
| **Indicators** | `tvDownloadOHLC/scripts/ninjatrader/indicators/<vendor|feature>/` | same tool (`Indicators/Vinay/`, `Indicators/RedTail/`) |
| **Framework** (`RiskManagerBase.cs`, `RiskGatekeeper.cs`, `IntradayStrategyBase.cs`) | `nt8-riskguard/strategies/Vinay/` | `nt8-mcp-bridge` → `python tools/deploy.py` (vendored-core sweep) |
| **Addons** (`RiskGuard*`, `McpBridge*`, `TradeCopier*`, …) | their own repos (`nt8-riskguard/addons/`, `nt8-mcp-bridge/addons/`) | their own deploy tools |

**One artifact, one owner, one deploy path. No exceptions.**

## Why (measured failures, not preference)

1. **Silent live-bot reversion (armed as of 2026-09-04)**: `nt8-mcp-bridge/vendor/nt8-riskguard/strategies/Vinay/ICTFVGCISDBot.cs` (Aug 29 pin) was 5 days behind the live deployed bot (Sep 3). `deploy.py`'s strategy sweep copies vendor → `Strategies/Vinay/` unconditionally. One `python tools/deploy.py` would have reverted the live ICT bot to a version whose `Variant` parameter was dead — while `--verify` showed "OK" for the framework files. Two other copies existed (riskguard main: Aug 25; this repo: Sep 3) and none was designated canonical.
2. **Dead-parameter drift**: the Aug-25 riskguard copy lost `Variant` branching in the `43630431` decoupled-indicator refactor; the Sep-3 copy here kept developing. Benchmark docs cited per-variant NT8 results that the then-current C# could not produce.
3. **Duplicate-class compile trap**: this repo had `KeltnerChannelBot.cs` in three folders (`base/`, `vinay/`, `keltner_channel/`). NT8 compiles `Strategies/` recursively; two copies of one class in different subfolders = CS0101, the whole Custom assembly fails, **every addon stops loading, RiskGuard included** — and `nt_health` still reads healthy because NT8 keeps serving the last good assembly.

## Invariants (mechanically enforced)

1. **Bridge deploy denylist** (`nt8-mcp-bridge/tools/deploy.py` → `_assert_no_bots_in_vendor`): if any bot name reappears in the vendored core's `strategies/`, deploy exits 2 before touching NT8. The strategies sweep also skips `BOT_DENYLIST` as a second layer.
2. **Sync-tool allowlist** (`sync_nt8_strategies.py` → `EXTERNAL_FRAMEWORK_FILES`): the three framework files are expected contents of `Strategies/Vinay/`, not orphans. This repo's sync never writes them; the bridge's sweep is their only deploy path (P1-149 pair rule: `RiskGatekeeper` → `ContractCapGate` deploy together).
3. **Version/tag pairing** (riskguard, pre-existing): the addon `Version` constant must bump in the same commit as the tag (`check_version_matches_tag.py`).
4. **Shared config manifest** (this repo): `configs/strategies/ifvg_cisd.yaml` is the single source of truth for Python *and* C# defaults; `scripts/utils/gen_ifvg_cisd_config.py --verify` fails on drift. Never hand-tune a default in one platform.

## Workflow for a strategy change (Python ↔ NT8 parity)

1. Change the **manifest** (`configs/strategies/<strategy>.yaml`), not platform code.
2. Run the generator + `--verify` gate; regenerate `IfvgCisdConfig.cs`.
3. Change the Python engine and the C# indicator/bot **in the same commit**.
4. `python scripts/utils/sync_nt8_strategies.py --verify` then sync; recompile via `nt_compile`.
5. Signal parity: run the parity runner (`scripts/parity/run_signal_parity.py`, fixture-pinned) — target is 0 mismatches per variant.
6. **NT8 Strategy Analyzer is ground truth** for WR/PF. Python sim numbers are directional until signal parity is green AND the trade-by-trade sim diff vs an NT8 backtest export is clean.
7. Never port a "validated" Python variant to C# by rewriting it — port the *kernel* and prove parity. The 2026-09-04 review found the C# rewrite had dropped variant branching entirely while the benchmark doc claimed per-variant parity.

## Migration record (2026-09-04)

- riskguard `strategies/Vinay/`: 15 bot `.cs` deleted (tag `v1.67.0`); framework-only remains.
- bridge vendor pin: bumped to `v1.67.0`; `deploy.py` denylist added; `McpBridgeAddOn.cs` backported from live (deployed was newer — drift direction rule).
- this repo: `strategies/base/` vestigial snapshot deleted (18 files, all dups); `strategies/vinay/` duplicate Keltner deleted; `ICTFVGBoS.cs` moved to `ifvg_cisd/`; sync-tool `STRATEGIES_SRC_DIRS` now enumerates feature folders only, with the framework allowlist for orphan detection.
- Pre-existing red (not caused by this migration, follow-up): bridge CI fails `mutate_p1106.py` / `mutate_p1149sizing.py` anchor checks — anchors written against the pre-CM0 `McpBridgeAddOn.cs`; the live-side fix was never backported until now; batteries need re-anchoring to the backported code.