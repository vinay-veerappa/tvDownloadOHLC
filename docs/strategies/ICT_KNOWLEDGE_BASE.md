# ICT Knowledge Base & Systematic Framework

This document outlines the Inner Circle Trader (ICT) concepts, algorithmic microstructure rules, and quantitative execution models implemented across this codebase.

---

## 1. The Authoritative Execution Pipeline: `Liquidity -> CISD -> Retest Entry`

The core trading philosophy rests on a strict 5-step state machine:

```
[ STEP 1: LIQUIDITY SWEEP / HTF TAP ]
  • Price purges institutional liquidity (PDH/PDL, 4H/1H Swings, Asia/London Ranges)
    OR delivers from an HTF Fair Value Gap (4H/1H FVG/OB).
  • Captures the exact Sweep Invalidation Extreme (Lowest Low for Bullish, Highest High for Bearish).
                                  │
                                  ▼
[ STEP 2: CANONICAL CISD FLIP (DELIVERY ANCHOR BREACH) ]
  • Walks backwards from the sweep candle to identify the contiguous run of opposing candles.
  • Establishes the authoritative delivery origin anchor level.
  • Confirms +CISD (or -CISD) on the first candle BODY-CLOSE across the delivery anchor.
                                  │
                                  ▼
[ STEP 3: NON-CHASING ENTRY ZONE ARMING ]
  • Arms the First Presented FVG, Inversion FVG (IFVG), or breached CISD level.
  • Sets resting limit prices: Outer Boundary, 50% Consequent Encroachment (CE), or CISD Line.
  • Zero market order chasing on breakout closes.
                                  │
                                  ▼
[ STEP 4: RETEST EXECUTION & STRUCTURAL STOP PLACEMENT ]
  • Fills limit order ONLY when price pulls back into the armed imbalance zone.
  • Stop Loss is anchored structurally (SL-1: Sweep Wick, SL-4: CISD Origin, FVG Forming Wick, or OB H/L).
                                  │
                                  ▼
[ STEP 5: "COVER THE QUEEN" TRADE MANAGEMENT (PACK MODEL) ]
  • Target 1 (The Queen): Scaled out at EXACTLY 10 Basis Points (10 bps) (e.g. +20–30 pts on NQ).
    --> Trade is instantly mathematically RISK-FREE.
  • Runner Contract: Stop loss automatically moves to BREAKEVEN (or 90% MAE Pullback boundary).
  • Target 2 (Median MFE): Targets the 45th–55th percentile MFE expansion (~30–40 pts).
  • Target 3 (Fat Tails): Targets 70th–80th+ percentile MFE (P12 High/Low, PDH/PDL, or DNP/DWP trend).
```

*For complete details, see the [Liquidity · CISD · Entry Master Specification](file:///c:/Users/vinay/tvDownloadOHLC/docs/strategies/ifvg_cisd/LIQUIDITY_CISD_ENTRY_MASTER_SPEC.md).*

---

## 2. Structural Stop Loss Models

All stops in this system are strictly structural:
1. **SL-1 (Sweep Wick Invalidation)**: 1–2 ticks beyond the extreme wick of the liquidity sweep / C2 candle.
2. **SL-2 (FVG Forming Candle Wicks)**: 1–2 ticks beyond Candle 2 or Candle 1 extreme wick of the 3-bar FVG formation.
3. **SL-3 (Orderblock High / Low)**: 1–2 ticks beyond the entire Orderblock candle extreme.
4. **SL-4 (CISD Delivery Origin Anchor)**: 1–2 ticks beyond the extreme body/wick of the opposing candle run.
5. **SL-5 (Session Structural Boundary)**: 1–2 ticks beyond the 09:30 RTH Open bar extreme, Asia High/Low, or London High/Low (Max 30 bps rule).

---

## 3. Non-Chasing Entry Techniques

1. **ET-1 (FVG / IFVG Outer Boundary Limit)**: Fills on first touch into the zone.
2. **ET-2 (Consequent Encroachment - 50% CE Limit)**: Fills at $\text{CE} = \frac{\text{Top} + \text{Bot}}{2}$ for optimal R:R.
3. **ET-3 (CISD Level Retest Limit)**: Fills on pullback to the horizontal CISD delivery line.
4. **ET-4 (First Presented FVG)**: Initial FVG formed immediately following the CISD displacement candle.
5. **ET-5 (Optimal Trade Entry - OTE)**: 62%–79% Fibonacci retracement inside the displacement swing.
6. **ET-6 (Breaker Block Retest)**: Retest of the failed swing that swept liquidity before breaking.
7. **ET-7 (Mitigation Block Retest)**: Retest of the failed swing that did not take liquidity before breaking.

---

## 4. "Cover The Queen" & "Dump Pouch" Risk Architecture

Sourced from Matt Mickey & Austin (Pack Trading):
* **Cover The Queen (10 Basis Points Scale-Out)**:
  $$\text{Target 1 (The Queen)} = \text{Entry Price} \pm (\text{Entry Price} \times 0.0010)$$
  Scale out 50% to 70% of position at 10 bps to make the active trade mathematically **100% Risk-Free**.
* **Runner Trailing**: The moment the Queen is covered at 10 bps, the stop on the runner is moved to **Breakeven** or tucked just behind the **90th percentile MAE pullback boundary**.
* **Extended Targets**: Target 2 at **45th–55th percentile MFE**; Target 3 at **70th–80th+ percentile MFE** (P12, PDH/PDL, settlement gap).
* **Dump Pouch**: Dynamic volatility sizing tool calculating live Expected Value (EV) and MAE/MFE boundaries.

---

## 5. Statistical Time Windows (Macro Windows)

Arbitrary bar-count stops (like 15 bars) are eliminated. Time filters rely on institutional Macro cycles:
* `08:50 – 09:10 ET` (Pre-market Futures Macro)
* `09:50 – 10:10 ET` (AM Cash Open Macro)
* `10:50 – 11:10 ET` (AM London Close Macro)
* `11:50 – 12:10 ET` (Lunch Macro)
* `13:50 – 14:10 ET` (PM Afternoon Macro)
* `15:15 – 15:45 ET` (Market On Close Run)
* `15:55 ET` (Hard EOD Flatten)

---

## 6. Implemented Code Reference Matrix

| Component | File Path | Language | Status |
| :--- | :--- | :--- | :--- |
| **Strategy Engine** | [`scripts/indicators-pine/ifvg_cisd/IFVG_CISD_MTF_Strategy.pine`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/indicators-pine/ifvg_cisd/IFVG_CISD_MTF_Strategy.pine) | Pine Script v6 | Active |
| **Indicator Overlay** | [`scripts/indicators-pine/ifvg_cisd/IFVG_CISD_MTF_Indicator.pine`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/indicators-pine/ifvg_cisd/IFVG_CISD_MTF_Indicator.pine) | Pine Script v6 | Active |
| **NinjaTrader 8 Bot** | [`scripts/ninjatrader/strategies/ifvg_cisd/ICTFVGCISDBot.cs`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/ninjatrader/strategies/ifvg_cisd/ICTFVGCISDBot.cs) | C# / NinjaScript | Compiled (0 errors) |
| **Python JIT Core** | [`scripts/libs_py/cisd.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/libs_py/cisd.py) | Python / Numba | Active |
| **Master Specification** | [`docs/strategies/ifvg_cisd/LIQUIDITY_CISD_ENTRY_MASTER_SPEC.md`](file:///c:/Users/vinay/tvDownloadOHLC/docs/strategies/ifvg_cisd/LIQUIDITY_CISD_ENTRY_MASTER_SPEC.md) | Markdown | Active |
