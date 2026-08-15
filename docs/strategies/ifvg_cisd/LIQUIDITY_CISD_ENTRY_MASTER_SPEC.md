# Institutional Trading Specification: Liquidity · CISD · Entry (SCF+L Framework)

## 📌 Executive Summary

This specification establishes the authoritative, quantitative architecture for the **Liquidity Sweep $\rightarrow$ Change in State of Delivery (CISD) $\rightarrow$ Non-Chasing Retest Entry** trading system. It incorporates **Structural Stop Losses**, the **Pack Trading "Cover The Queen" (10 Basis Points)** risk management model, and empirical **Maximum Favorable Excursion (MFE) Basis Points Distributions**.

*Empirical Backtest Benchmark (2022–2026 across 324,000+ bars)*:
* **NQ (Nasdaq-100)**: **Profit Factor 3.08** | **Win Rate: 64.70%** | **Net PnL: +$126,707 (MNQ 2-ct) / +$1,267,076 (NQ)**
* **ES (S&P 500)**: **Profit Factor 3.22** | **Win Rate: 64.90%** | **Net PnL: +$749,147 (ES 2-ct)**
* *For complete details, see [Empirical Quantitative Research & Strategy Audit](file:///c:/Users/vinay/tvDownloadOHLC/docs/research/EMPIRICAL_QUANT_AUDIT_CISD_ES_NQ.md).*

---

## 🏛️ The 5-Step Execution State Machine

```
[ STEP 1: LIQUIDITY SWEEPS (1-HOUR, 4-HOUR, DAILY & SESSIONS) ]
  • 1-Hour Swings: Price sweeps Previous 1-Hour High / Low (Hourly BSL / SSL) or 1H FVG.
  • 4-Hour Swings: Price sweeps Previous 4-Hour High / Low (4H BSL / SSL) or 4H FVG.
  • Daily & Sessions: Price sweeps PDH/PDL, Asia Range (6pm-2am), or London Range (2am-8am).
  • Intraday Pools: Price sweeps 15m Swings / 15m FVGs or 5m fractal pivots.
  • The system captures and locks the exact SWEEP EXTREME (Wick Invalidation SL-1).
                                  │
                                  ▼
[ STEP 2: CANONICAL CISD FLIP (DELIVERY ANCHOR BREACH) ]
  • System walks backwards from the sweep candle to identify the contiguous run of opposing candles.
  • Establishes the authoritative delivery origin anchor level (SL-4).
  • Confirms +CISD (or -CISD) on the first candle BODY-CLOSE across the delivery anchor.
                                  │
                                  ▼
[ STEP 3: NON-CHASING ENTRY ZONE ARMING (50% CE DEFAULT) ]
  • Arms the 50% Consequent Encroachment (CE) of the First Presented FVG / Inversion FVG.
  • Formula: CE = (Top + Bottom) / 2.0.
  • Strictly eliminates market order chasing on candle breakout closes.
                                  │
                                  ▼
[ STEP 4: RETEST EXECUTION & STRUCTURAL STOP PLACEMENT ]
  • Fills limit order ONLY when price pulls back into the armed 50% CE level.
  • Stop Loss: Anchored structurally to SL-4 (CISD Delivery Origin Anchor - Default).
  • Hard Risk Ceiling: Stop distance must not exceed 15 Basis Points (15 bps).
                                  │
                                  ▼
[ STEP 5: BASIS POINTS MFE BRACKET (COVER THE QUEEN) ]
  • Target 1 (The Queen): Scaled out at EXACTLY 10 Basis Points (10 bps).
    --> Trade is instantly mathematically RISK-FREE.
  • Runner Contract: Stop loss automatically moves to BREAKEVEN (saves 88.9% of full reversals).
  • Target 2 (Median MFE): Targets the 50th percentile MFE expansion (~30 bps).
  • Target 3 (Fat Tails): Targets 80th percentile MFE (~70 bps / P12 High/Low / DNP/DWP trend).
```

---

## 🛑 Structural Stop Loss Models

| Model ID | Stop Loss Model | Exact Placement Rule | Empirical Status |
| :--- | :--- | :--- | :--- |
| **SL-4** | **CISD Delivery Origin Anchor** *(Primary Institutional Default)* | 1–2 ticks beyond the extreme body/open of the opposing candle run that was broken by CISD. | 🔥 **Top Performer (PF 3.08 - 3.22, 64.8% WR)**. Clean structural barrier. |
| **SL-1** | **Sweep Wick Invalidation (C2 Extreme)** | 1–2 ticks beyond the extreme wick of the liquidity sweep / C2 candle. | Baseline model (Wider risk, PF 1.01). |
| **SL-2** | **FVG Forming Candle Wicks** | 1–2 ticks beyond Candle 2 or Candle 1 extreme wick of the 3-bar FVG formation. | Tight risk, sensitive to deep retests (PF 1.01). |
| **SL-3** | **Orderblock (OB) High / Low** | 1–2 ticks beyond the entire Orderblock candle extreme. | High-conviction mitigation structure. |
| **SL-5** | **Session Structural Boundary** | 1–2 ticks beyond 09:30 RTH Open bar extreme, Asia High/Low, or London High/Low. | Hard macro session boundary. |

---

## 🎯 Non-Chasing Entry Techniques

1. **ET-2: Consequent Encroachment (50% CE Limit) — *Institutional Default***:
   * Limit resting at exact midpoint: $\text{CE} = \frac{\text{Top} + \text{Bottom}}{2}$.
   * Reduces stop distance by $>35\%$, boosting Profit Factor from $2.54 \rightarrow 3.08$.
2. **ET-1: FVG / IFVG Outer Boundary Limit (Touch)**: Fills on first tap into the imbalance.
3. **ET-3: CISD Level Retest Limit**: Fills on pullback to the breached horizontal delivery line.
4. **ET-4: First Presented FVG**: Initial FVG formed immediately following the CISD displacement candle.
5. **ET-5: Optimal Trade Entry (OTE)**: 62%–79% Fibonacci retracement inside the displacement swing.
6. **ET-6 & ET-7: Breaker Block and Mitigation Block Retests**.

---

## 📐 Basis Points (bps) Conversion Matrix & Alignment

$$1\text{ Basis Point (1 bps)} = \frac{1}{10,000} = 0.0001 = 0.01\%$$

| Level / Increment | Basis Points | NQ @ 30,000 | NQ @ 20,000 | ES @ 5,500 | ES @ 5,000 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Micro Pullback Tolerance** | **5 bps** | 15.0 pts | 10.0 pts | 2.75 pts | 2.50 pts |
| **Cover The Queen (TP1)** | **10 bps** | 30.0 pts | 20.0 pts | 5.50 pts | 5.00 pts |
| **Hard Risk Ceiling** | **15 bps** | 45.0 pts | 30.0 pts | 8.25 pts | 7.50 pts |
| **Target 2 (Median MFE)** | **30 bps** | 90.0 pts | 60.0 pts | 16.50 pts | 15.00 pts |
| **Target 3 (Fat-Tail Trend)** | **70 bps** | 210.0 pts | 140.0 pts | 38.50 pts | 35.00 pts |

---

## ⏰ ICT Killzones & Session Alpha Ranking

1. **PM Afternoon Macro (13:30 – 15:30 ET)**: 🔥 **Highest Alpha** (PF: 4.69, Win Rate: 77.3%, Avg Win: +$503). True institutional trend distribution into close.
2. **Lunch Session Lull (11:30 – 13:30 ET)**: PF: 3.53, Win Rate: 70.2%. Queen 10 bps locks cash flow during consolidation.
3. **London Close Macro (11:00 – 11:30 ET)**: PF: 3.39, Win Rate: 69.7%.
4. **AM NY Open (09:30 – 11:00 ET)**: PF: 2.17, Win Rate: 63.1%. Opening drive volatility.
5. **EOD Flatten**: Hard close at 15:55 ET.

---

## 💻 Synchronized Code References

1. **Python Multi-Year Backtester**: [`scripts/backtests/backtest_liquidity_cisd_strategy.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/backtests/backtest_liquidity_cisd_strategy.py)
2. **Quant Research & BE Trajectory Engine**: [`scripts/backtests/backtest_es_and_trajectory_audit.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/backtests/backtest_es_and_trajectory_audit.py)
3. **TradingView Strategy**: [`scripts/indicators-pine/ifvg_cisd/IFVG_CISD_MTF_Strategy.pine`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/indicators-pine/ifvg_cisd/IFVG_CISD_MTF_Strategy.pine)
4. **TradingView Indicator**: [`scripts/indicators-pine/ifvg_cisd/IFVG_CISD_MTF_Indicator.pine`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/indicators-pine/ifvg_cisd/IFVG_CISD_MTF_Indicator.pine)
5. **NinjaTrader 8 Strategy**: [`scripts/ninjatrader/strategies/ifvg_cisd/ICTFVGCISDBot.cs`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/ninjatrader/strategies/ifvg_cisd/ICTFVGCISDBot.cs)
