# RedTail Indicators — Quick Reference Index

> **Source**: [github.com/3astbeast/RedTailIndicators](https://github.com/3astbeast/RedTailIndicators)
> **License**: Free and open-source. Use code for free projects. Do not re-brand/sell.
> **Full README**: See `README.md` in this folder (45KB, full feature descriptions)
> **Downloaded**: 2026-07-30

---

## Indicator Index (14 files in this folder)

| # | File | Size | Class | What it does | IB Confluence value | Plot outputs? |
|---|---|---|---|---|---|---|
| 1 | `RedTailAutoVWAP.cs` | 191KB | `RedTailAutoVWAP` | Multi-VWAP (NY Session, Prev Day, Session±bands, HOD/LOD, Monthly/Yearly) + NY Opening Range + **Day Initial Balance** + VWAP Fib bands + voice alerts | 🥇 **Already installed as `MyCustomIndicator.cs`**. Has IB range + OR + all VWAPs. Foundation for IB Confluence. | Yes — VWAP plots |
| 2 | `RedTailMarketStructure.cs` | 225KB | `RedTailMarketStructure` | **BoS/CHoCH** + **volumized Order Blocks** (ATR displacement, breaker conversion) + **FRVP** (Fib+VP on structure shifts) + **strong/weak level scoring** + **equal highs/lows** (liquidity pools) + **liquidity sweeps** (wick+reject) + **displacement candles** + voice alerts | 🥈 **Covers BoS/CHoCH + OB + Liquidity in one indicator**. Replaces 3 custom detectors we planned. Has companion for cross-chart-type mirroring. | Check source — likely has internal lists |
| 3 | `RedTailMarketStructureCompanion.cs` | 36KB | `RedTailMarketStructureCompanion` | Mirrors Market Structure's strong levels + OB zones onto different bar type charts (tick/range/Renko) via static registry | Companion for #2 — use if trading on tick/range charts | — |
| 4 | `RedTailKeyLevels.cs` | 59KB | `RedTailKeyLevels` | Pivots (PP/R1-R3/S1-S3 + midlines) + PDH/PDL + PWH/PWL + PMH/PML + **Monday range** + **Globex range** + **RTH range (9:30-4:00)** + Fib retracements + **smart level merging** | 🥉 **All 33 levels exposed as plot outputs**. PDH/PDL, Monday range, Globex range, RTH range — directly useful for liquidity reference + IB confluence levels. | **Yes — 33 plot series** (PP, R1-R3, S1-S3, midlines, PDH/PDL, PWH/PWL, PMH/PML, MH/ML, GH/GL, NYH/NYL, Fib1-10) |
| 5 | `RedTailFRVP.cs` | 78KB | `RedTailFRVP` | Standalone Fib Retracement + Volume Profile on BOS/CHoCH swings. POC, VA, Fib levels, AVWAP, K-Means clusters. | FVG/OB confluence at structure shift points. FRVP zones for IB retest targets. | — |
| 6 | `RedTailVolumeProfile.cs` | 490KB | `RedTailVolumeProfile` | Full volume profile (Session/Visible Range/Weekly/Monthly/Composite/Anchored). POC, VAH/VAL, naked levels, prev day/week levels, overnight levels, LVN, move profiles, candle profiles, DOM viz. | Volume profile confluence at IB levels. POC/VAH/VAL as IB target/reference. | **Yes — POC, VAH, VAL, PD levels, Overnight levels** |
| 7 | `RedTailVolume.cs` | 42KB | `RedTailVolume` | Buy/sell volume separation + statistics panel (30-day avg, cumulative, buy/sell %). | Volume confirmation for IB breakout direction. | **Yes — Buy Volume, Sell Volume, Volume Average** |
| 8 | `RedTailAutoFibs.cs` | 44KB | `RedTailAutoFibs` | Daily/Weekly/Monthly auto Fibonacci retracements from developing H/L. 10 levels per TF (30 total). | Fib confluence at IB retest depths (38.2%, 50%, 61.8%). | — |
| 9 | `RedTailLVNHunter.cs` | 17KB | `RedTailLVNHunter` | Standalone Low Volume Node detector. Session or fixed-bars lookback. | LVN zones as breakout targets / IB range extensions. | — |
| 10 | `RedTailVWAPFibBands.cs` | 32KB | `RedTailVWAPFibBands` | MIDAS VWAP with ±1σ/±2σ/±3σ bands + Fib sub-bands. Session/Timeframe/Date anchoring. | VWAP band confluence for IB mean-reversion zones. | **Yes — MIDAS, Upper/Lower 1-3, all Fib levels** |
| 11 | `RedTailSwingAnchoredVWAP.cs` | 31KB | `RedTailSwingAnchoredVWAP` | EWMA-smoothed VWAP from swing pivots. ATR-adaptive tracking. | Swing-anchored VWAP for IB retest reference. | **Yes — VWAP value** |
| 12 | `RedTailEMACloud.cs` | 33KB | `RedTailEMACloud` | 5 independent EMA/SMA clouds (8/9, 5/12, 34/50, 72/89, 180/200). | Trend filter for IB breakout direction (200 EMA cloud). | — |
| 13 | `SessionOpeningBarRange.cs` | 30KB | `SessionOpeningBarRange` | First bar's H/L/mid + statistical extensions + OR rotation levels. Session presets (NY/London/Asia/Custom). | Pre-IB opening bar range (first 1m/5m bar of RTH). | — |
| 14 | `SessionStatisticalLevels.cs` | 38KB | `SessionStatisticalLevels` | Percentile-based session range levels (P25/P50/P75/P90/P95, MAE/MFE by bull/bear). Asia/London/NY. | Statistical range projections for IB target/stop placement. | — |

---

## IB Confluence Integration Priority

### Tier 1 — Core (compose into IBConfluenceIndicator)
| Indicator | Role | Why |
|---|---|---|
| **RedTailAutoVWAP** | VWAP + IB range + OR | Already has IB. Foundation layer. |
| **RedTailMarketStructure** | BoS/CHoCH + OB + Liquidity sweeps | Replaces 3 custom detectors. Full SMC suite. |
| **RedTailKeyLevels** | PDH/PDL + Monday range + RTH range + Pivots | 33 plot outputs — all liquidity/confluence levels. |

### Tier 2 — Confluence enhancement
| Indicator | Role | Why |
|---|---|---|
| **RedTailVolumeProfile** | POC/VAH/VAL at IB levels | Volume profile confluence. |
| **RedTailFRVP** | Fib + VP on structure shifts | Retest target zones after IB break. |
| **RedTailAutoFibs** | Daily/Weekly/Monthly Fibs | Fib confluence at IB retest depths. |

### Tier 3 — Optional / supplementary
| Indicator | Role | Why |
|---|---|---|
| **RedTailVWAPFibBands** | MIDAS VWAP ±bands | Mean-reversion zones. |
| **RedTailSwingAnchoredVWAP** | Swing-anchored VWAP | Alternative VWAP reference. |
| **RedTailEMACloud** | 200 EMA cloud | Macro trend filter. |
| **RedTailVolume** | Buy/sell volume | Volume confirmation. |
| **RedTailLVNHunter** | LVN zones | Breakout targets. |
| **SessionOpeningBarRange** | Opening bar range | Pre-IB reference. |
| **SessionStatisticalLevels** | Percentile range projections | Statistical targets. |

---

## Installation

1. Copy `.cs` file(s) to `Documents\NinjaTrader 8\bin\Custom\Indicators\`
2. Open NinjaTrader → NinjaScript Editor → Compile
3. **Note**: Market Structure and Auto VWAP have special installation instructions — see their individual repo READMEs

> **Market Structure**: Both `RedTailMarketStructure.cs` AND `RedTailMarketStructureCompanion.cs` must be installed (companion depends on types in main file).

---

## Source Repos

| Indicator | Repo |
|---|---|
| Auto-VWAP | https://github.com/3astbeast/RedTail-Auto-VWAP |
| Market Structure | https://github.com/3astbeast/RedTail-Market-Structure |
| Key Levels | https://github.com/3astbeast/RedTail-Key-Levels |
| FRVP | https://github.com/3astbeast/RedTail-FRVP |
| Volume Profile | https://github.com/3astbeast/RedTail-Volume-Profile |
| Volume | https://github.com/3astbeast/RedTail-Volume |
| Auto Fibs | https://github.com/3astbeast/RedTail-Auto-Fibs |
| LVN Hunter | https://github.com/3astbeast/RedTail-LVN-Hunter |
| VWAP Fib Bands | https://github.com/3astbeast/RedTail-VWAP-Fib-Bands |
| Swing Anchored VWAP | https://github.com/3astbeast/RedTail-Swing-Anchored-VWAP |
| EMA Cloud | https://github.com/3astbeast/RedTail-EMA-Cloud |
| Session Opening Bar Range | https://github.com/3astbeast/Session-Opening-Bar-Range |
| Session Statistical Levels | https://github.com/3astbeast/Session-Statistical-Levels |
| Full index | https://github.com/3astbeast/RedTailIndicators |