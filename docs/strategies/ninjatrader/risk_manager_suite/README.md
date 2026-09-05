# Risk Manager Suite — moved. This is a pointer, not an implementation.

**Nothing in this folder is source any more.** The suite was split out on 2026-08-12
and the last local copy of `RiskManagerBase.cs` was deleted on 2026-09-05. Where
everything actually lives:

| Artifact | Owner | Path |
|---|---|---|
| `RiskManagerBase.cs` | **nt8-riskguard** | `strategies/Vinay/RiskManagerBase.cs` |
| `RiskGatekeeper.cs` | **nt8-riskguard** | `strategies/Vinay/RiskGatekeeper.cs` |
| `IntradayStrategyBase.cs` | **nt8-riskguard** | `strategies/Vinay/IntradayStrategyBase.cs` |
| `RiskManagerAddOn.cs` | **nt8-riskguard** | `addons/RiskManagerAddOn.cs` |
| `VWAPReclaimBot.cs` · `EMAPullbackBot.cs` · `FailedAuctionBot.cs` | **this repo** | `scripts/ninjatrader/strategies/<feature>/` |

ADR-025: one artifact, one owner. `sync_nt8_strategies.py` allowlists the three
framework filenames as `EXTERNAL_FRAMEWORK_FILES` because they arrive in NT8
through the bridge's vendored-core sweep, not from here.

## Why the old copy had to go

It was a **fork**, and it had drifted *ahead* of the file that owns the behaviour —
carrying three changes that had never shipped, while the canonical copy and the
deployed copy were byte-identical. So the live bots ran the older logic and this
one looked authoritative.

It was invisible to every check: it sat outside all three directories
`sync_nt8_strategies.py` scans, so `--verify` reported `0 orphan(s)` and never
compared it to anything. And it was the copy a reader working in *this* repo would
open — a second source of truth with a lower profile.

Two live documents pointed at it as "the existing base class to extend", which is
how it got there and how it stayed.

The three unlanded changes are recorded, with a recommendation for each, in
[BOT_FIX_BACKLOG.md](../../../architecture/BOT_FIX_BACKLOG.md) **B9**. Nothing was
lost; git history has the file.

## Do not add a `.cs` back here

`scripts/trading_framework/tests/test_base_class_ownership.py` fails if a copy of
`RiskManagerBase.cs` reappears anywhere in this repo, and it also checks that the
members `GovernedStrategy` needs are still offered at the accessibility it needs
them at — the only compile check available here, since nothing in this repo builds
NinjaScript and a broken NT8 Custom assembly is invisible (NT8 keeps running the
last good one).

## What to read instead

* **How to write a bot**: [STRATEGY_WORKFLOW.md §5.7](../../../architecture/STRATEGY_WORKFLOW.md) —
  a new bot inherits `GovernedStrategy` (`scripts/ninjatrader/shared/`), which is
  this repo's own layer over `RiskManagerBase` and needs no change to it.
* **Deploying**: `python scripts/utils/sync_nt8_strategies.py --verify` then without
  `--verify`. ⚠️ The old version of this README told you to hand-copy `.cs` into
  `Documents/NinjaTrader 8/bin/Custom/`, which is explicitly prohibited — NT8
  compiles `Indicators/` recursively and a stray second copy is a duplicate class
  definition.
* **The guard's own design**: `docs/RISKGUARD_HARDENING_HANDOVER.md` in
  nt8-riskguard.
