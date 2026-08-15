# Institutional Trading Specification: Liquidity · CISD · Entry (SCF+L Framework)

## 📌 Executive Summary

This specification establishes the authoritative, quantitative architecture for the **Liquidity Sweep $\rightarrow$ Change in State of Delivery (CISD) $\rightarrow$ Non-Chasing Retest Entry** trading system. It incorporates **Structural Stop Losses**, the **Pack Trading "Cover The Queen" (10 Basis Points)** risk management model, and empirical **Maximum Favorable Excursion (MFE) Basis Points Distributions**.

---

## 📐 How Maximum Favorable Excursion (MFE) Levels Are Derived

In quantitative trading (and specifically the Matt Mickey & Austin Pack Trading framework), **Maximum Favorable Excursion (MFE)** measures the peak favorable price movement achieved by a trade setup before the trade is closed or invalidated.

### 1. Mathematical Calculation in Basis Points (bps)
$$\text{MFE (bps)} = \left( \frac{\text{Maximum Favorable Price} - \text{Entry Price}}{\text{Entry Price}} \right) \times 10,000$$

*Why Basis Points instead of Static Points?*
* Static points fail across varying asset price levels and changing volatility regimes.
* **10 Basis Points ($10\text{ bps} = 0.10\%$)** scales dynamically across all instruments:
  * NQ @ $15,000 \implies 10\text{ bps} = 15.0\text{ pts}$
  * NQ @ $20,000 \implies 10\text{ bps} = 20.0\text{ pts}$
  * NQ @ $30,000 \implies 10\text{ bps} = 30.0\text{ pts}$
  * ES @ $5,000 \implies 10\text{ bps} = 5.0\text{ pts}$
  * YM @ $40,000 \implies 10\text{ bps} = 40.0\text{ pts}$

### 2. The 3 Core Empirical MFE Percentile Buckets
From rolling in-sample (75–100 day) and outer-sample (20-year) distribution datasets:

| Target Tier | Distribution Percentile | Standard Distance (bps) | Systematic Purpose |
| :--- | :--- | :--- | :--- |
| **Target 1: Cover The Queen** | **~85%–90% Frequency** | **10 Basis Points (10 bps)** | Initial scale-out (50%–70% size). Instantly makes the trade **100% Risk-Free**. |
| **Target 2: Median MFE** | **45th–55th Percentile** | **~25–35 Basis Points (30 bps)** | The median expansion distance of confirmed breakouts. Secondary cash-flow target. |
| **Target 3: Fat-Tail MFE** | **70th–80th+ Percentile** | **~60–100+ Basis Points (70 bps)** | Extended expansion to capture rare but explosive **DNP / DWP** trend continuation days, P12 levels, and daily extremes. |

---

## 🏛️ The 5-Step Execution State Machine

```
[ STEP 1: LIQUIDITY SWEEP & HTF PD ARRAY TAP ]
  • Price sweeps institutional liquidity (PDH/PDL, 4H/1H Swings, Asia/London Ranges)
    OR taps into a Higher Timeframe (HTF) Fair Value Gap (4H/1H FVG/OB).
  • The system captures and locks the exact SWEEP EXTREME (Wick Invalidation).
                                  │
                                  ▼
[ STEP 2: CANONICAL CISD FLIP (DELIVERY ANCHOR BREACH) ]
  • System walks backwards from the sweep candle to identify the contiguous run of opposing candles.
  • Establishes the authoritative delivery origin anchor level.
  • Confirms +CISD (or -CISD) on the first candle BODY-CLOSE across the delivery anchor.
                                  │
                                  ▼
[ STEP 3: NON-CHASING ENTRY ZONE ARMING ]
  • Arms the First Presented FVG, Inversion FVG (IFVG), or breached CISD level.
  • Sets resting limit prices: Outer Boundary, 50% Consequent Encroachment (CE), or CISD Line.
  • Strictly eliminates market order chasing on candle breakout closes.
                                  │
                                  ▼
[ STEP 4: RETEST EXECUTION & STRUCTURAL STOP PLACEMENT ]
  • Fills limit order ONLY when price pulls back into the armed imbalance zone.
  • Stop Loss is anchored structurally (SL-1: Sweep Wick, SL-4: CISD Origin, FVG Forming Wick, or OB H/L).
                                  │
                                  ▼
[ STEP 5: BASIS POINTS MFE BRACKET (COVER THE QUEEN) ]
  • Target 1 (The Queen): Scaled out at EXACTLY 10 Basis Points (10 bps).
    --> Trade is instantly mathematically RISK-FREE.
  • Runner Contract: Stop loss automatically moves to BREAKEVEN (or 90% MAE Pullback boundary).
  • Target 2 (Median MFE): Targets the 50th percentile MFE expansion (~30 bps).
  • Target 3 (Fat Tails): Targets 80th percentile MFE (~70 bps / P12 High/Low / DNP/DWP trend).
```

---

## 🛑 Structural Stop Loss Models

1. **SL-1 (Sweep Wick Invalidation — Default)**: 1–2 ticks beyond the extreme wick of the liquidity sweep / C2 candle.
2. **SL-2 (FVG Forming Candle Wicks)**: 1–2 ticks beyond Candle 2 or Candle 1 extreme wick of the 3-bar FVG formation.
3. **SL-3 (Orderblock High / Low)**: 1–2 ticks beyond the entire Orderblock candle extreme.
4. **SL-4 (CISD Delivery Origin Anchor)**: 1–2 ticks beyond the extreme body/wick of the opposing candle run.
5. **SL-5 (Session Structural Boundary)**: 1–2 ticks beyond the 09:30 RTH Open bar extreme, Asia High/Low, or London High/Low (Max 30 bps rule).

---

## 🎯 Non-Chasing Entry Techniques

1. **ET-1 (FVG / IFVG Outer Boundary Limit)**: Fills on first touch into the zone.
2. **ET-2 (Consequent Encroachment - 50% CE Limit)**: Fills at $\text{CE} = \frac{\text{Top} + \text{Bot}}{2}$ for optimal R:R.
3. **ET-3 (CISD Level Retest Limit)**: Fills on pullback to the horizontal CISD delivery line.
4. **ET-4 (First Presented FVG)**: Initial FVG formed immediately following the CISD displacement candle.
5. **ET-5 (Optimal Trade Entry - OTE)**: 62%–79% Fibonacci retracement inside the displacement swing.
6. **ET-6 (Breaker Block Retest)**: Retest of the failed swing that swept liquidity before breaking.
7. **ET-7 (Mitigation Block Retest)**: Retest of the failed swing that did not take liquidity before breaking.

---

## ⏰ Statistical Time Windows (Macro Windows)

Arbitrary bar-count stops (like 15 bars) are eliminated. Time filters rely on institutional Macro cycles:
* `08:50 – 09:10 ET` (Pre-market Futures Macro)
* `09:50 – 10:10 ET` (AM Cash Open Macro)
* `10:50 – 11:10 ET` (AM London Close Macro)
* `11:50 – 12:10 ET` (Lunch Macro)
* `13:50 – 14:10 ET` (PM Afternoon Macro)
* `15:15 – 15:45 ET` (Market On Close Run)
* `15:55 ET` (Hard EOD Flatten)
