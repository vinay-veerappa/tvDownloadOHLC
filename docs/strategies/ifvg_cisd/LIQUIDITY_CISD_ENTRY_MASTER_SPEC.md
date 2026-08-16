# Institutional Trading Specification: Liquidity · CISD · Entry (SCF+L Framework)

## 📌 Executive Summary

This specification establishes the authoritative, quantitative architecture for the **Liquidity Sweep → Change in State of Delivery (CISD) → Non-Chasing Retest Entry** trading system. It incorporates **Structural Stop Losses**, the **Pack Trading "Cover The Queen" (10 Basis Points)** risk management model, **risk-based position sizing**, and empirical **Maximum Favorable Excursion (MFE) Basis Points Distributions**.

*v3 Backtest Benchmark (2022–2026, NQ 5m)*:
* **NQ (Nasdaq-100)**: **Profit Factor 3.48** | **Win Rate: 68.9%** | **Net PnL: +$686,644 (50K prop, risk-based sizing)**
* **Baseline (no filters)**: **Profit Factor 2.66** | **Win Rate: 63.9%** | **7,813 trades**
* *For complete details, see [Empirical Quantitative Research & Strategy Audit](file:///c:/Users/vinay/tvDownloadOHLC/docs/research/EMPIRICAL_QUANT_AUDIT_CISD_ES_NQ.md).*

---

## 🏛️ The 5-Step Execution State Machine

```
[ STEP 1: LIQUIDITY SWEEPS (1-HOUR, 4-HOUR, DAILY, SESSIONS & INTRADAY) ]
  • 4-Hour Swings: Price sweeps Previous 4-Hour High / Low (4H BSL / SSL).
  • 1-Hour Swings: Price sweeps Previous 1-Hour High / Low (1H BSL / SSL).
  • Daily: Price sweeps PDH/PDL.
  • Sessions: Price sweeps Asia Range High/Low (18:00-02:00 ET), London Range (02:00-08:00 ET),
              NYAM IB Range (09:30-10:00 ET).
  • Intraday: Price sweeps 3-bar fractal swing highs/lows (5m chart).
  • Sweeps can arm before RTH — entries only fill during the configured trading window.
                                │
                                ▼
[ STEP 2: CANONICAL CISD FLIP (DELIVERY ANCHOR BREACH) ]
  • System walks backwards from the sweep candle to identify the contiguous run of opposing candles.
  • Records the run HIGH (CISD trigger level) and run LOW (SL-4 stop anchor).
  • Confirms +CISD (or -CISD) on the first candle BODY-CLOSE above the run HIGH (full reclamation).
  • Sets the delivery regime (+1 bull / -1 bear) for continuation FVG arming.
                                │
                                ▼
[ STEP 3: NON-CHASING ENTRY ZONE ARMING (FVG TOUCH) ]
  • Arms the FVG Touch entry (top of FVG for longs, bottom for shorts).
  • Requires a First Presented FVG on the CISD confirmation bar, OR a continuation FVG
    in the established delivery regime.
  • Strictly eliminates market order chasing on candle breakout closes.
  • Entry zones arm on bar N, fill from bar N+1 onward (no-cheating execution).
                                │
                                ▼
[ STEP 4: RETEST EXECUTION & STRUCTURAL STOP PLACEMENT ]
  • Fills limit order ONLY when price pulls back into the armed entry level.
  • Stop Loss: Anchored structurally to SL-4 (CISD Delivery Origin — run LOW ± 2 ticks).
  • Hard Risk Ceiling: Stop distance must be ≥ 2 bps and ≤ 15 Basis Points (15 bps).
  • Volume Gate: Entry bar volume must be ≥ 1.5× the 20-period volume SMA.
                                │
                                ▼
[ STEP 5: BASIS POINTS MFE BRACKET (COVER THE QUEEN) ]
  • Target 1 (The Queen): Scaled out at EXACTLY 10 Basis Points (10 bps).
    --> Trade is instantly mathematically RISK-FREE.
  • Runner Contract: Stop loss automatically moves to BREAKEVEN (saves 88.9% of full reversals).
  • Runner Target: 30 Basis Points (median MFE expansion).
  • EOD Flatten: Hard close at 15:55 ET.
```

---

## 🛑 Structural Stop Loss Models

| Model ID | Stop Loss Model | Exact Placement Rule | Empirical Status |
| :--- | :--- | :--- | :--- |
| **SL-4** | **CISD Delivery Origin Anchor** *(Primary Default)* | 2 ticks beyond the run LOW (bullish) or run HIGH (bearish) of the contiguous opposing candle run. | 🔥 **Top Performer (PF 2.66-3.48, 63-69% WR)**. |
| **SL-1** | **Sweep Wick Invalidation (C2 Extreme)** | 2 ticks beyond the extreme wick of the liquidity sweep candle. | Baseline (wider risk, PF ~1.0). |
| **FVG_Wick** | **FVG Forming Candle Wicks** | 2 ticks beyond Candle 2 or Candle 1 extreme wick of the 3-bar FVG. | Tight risk, sensitive to deep retests. |

---

## 🎯 Non-Chasing Entry Techniques

1. **ET-1: FVG Touch (Outer Boundary Limit) — *v3 Default***:
   * Limit resting at the top of the FVG (longs) or bottom (shorts).
   * Fills on first tap into the imbalance boundary.
   * Tightest risk (entry close to SL-4 stop), highest Queen fill rate.
2. **ET-2: Consequent Encroachment (50% CE Limit)**:
   * Limit resting at exact midpoint: CE = (Top + Bottom) / 2.
   * Deeper entry, further from stop, lower Queen fill rate but larger profit per winner.
3. **ET-3: CISD Level Retest Limit**: Fills on pullback to the breached delivery level.

---

## 📐 Basis Points (bps) Conversion Matrix

$$1\text{ Basis Point (1 bps)} = \frac{1}{10,000} = 0.0001 = 0.01\%$$

| Level / Increment | Basis Points | NQ @ 30,000 | NQ @ 20,000 | ES @ 5,500 | ES @ 5,000 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Min Risk (entry threshold)** | **2 bps** | 6.0 pts | 4.0 pts | 1.10 pts | 1.00 pts |
| **Cover The Queen (TP1)** | **10 bps** | 30.0 pts | 20.0 pts | 5.50 pts | 5.00 pts |
| **Hard Risk Ceiling** | **15 bps** | 45.0 pts | 30.0 pts | 8.25 pts | 7.50 pts |
| **Runner Target (TP2)** | **30 bps** | 90.0 pts | 60.0 pts | 16.50 pts | 15.00 pts |

---

## 💰 Position Sizing & Prop Firm Risk Model

Contracts are sized from the SL distance and a fixed dollar risk per trade:

```
contracts = risk_usd / (sl_distance_points × point_value)
contracts = max(2, min(contracts, max_contracts))
```

### Prop Firm Presets

| Preset | Account Size | Risk % | Risk $/Trade | Max Contracts | Instrument |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **50K** | $50,000 | 1.0% | $500 | 10 | MNQ |
| **25K** | $25,000 | 1.0% | $250 | 5 | MNQ |
| **150K** | $150,000 | 0.5% | $750 | 20 | MNQ |
| **MNQ_50K** | $50,000 | 0.5% | $250 | 20 | MNQ |

*Note: The 2-contract minimum ensures the Queen + Runner pack structure is always intact. Position sizing scales with the SL distance — tighter stops get more contracts, wider stops get fewer, but dollar risk per trade stays constant.*

---

## ⏰ Session Windows & Sweep Sources

### Trading Day
Futures trade nearly 24 hours. The **trading day** starts at **18:00 ET** (Sunday-Thursday) — the start of the overnight/globex session. All daily levels (PDH/PDL), session ranges, and trade counts reset at this boundary.

### Sweep Sources (checked in priority order)

| Priority | Source | Level | ET Hours |
| :--- | :--- | :--- | :--- |
| 1 | Daily | PDH / PDL | Prior day H/L |
| 2 | 4-Hour | 4H BSL / SSL | Prior 4H bar H/L (shifted 1) |
| 3 | 1-Hour | 1H BSL / SSL | Prior 1H bar H/L (shifted 1) |
| 4 | Session | Asia H / Asia L | 18:00-02:00 ET (sweeps only after 02:00) |
| 5 | Session | London H / London L | 02:00-08:00 ET (sweeps only after 08:00) |
| 6 | Intraday | Swing High / Swing Low | 3-bar fractal pivots on 5m |

### Entry Window
Entries fill during RTH: **09:45-15:30 ET**. Sweeps can be detected and CISD armed outside this window (overnight, London session), but the limit order only fills when RTH opens.

*Future: session-configurable entry windows to enable Asia/London/PM-only trading.*

### EOD Flatten
Hard close at **15:55 ET** — all positions exit at market.

---

## 🔧 Volume & Risk Filters

| Filter | Value | Effect |
| :--- | :--- | :--- |
| **Volume Gate** | 1.5× SMA(20) | Entry bar volume must exceed 1.5× the 20-period volume SMA |
| **Risk Ceiling** | 15 bps | Skip setup if SL distance > 15 bps |
| **Min Risk** | 2 bps | Skip setup if SL distance < 2 bps (degenerate entries) |
| **Max Daily Trades** | 5 | Hard limit per trading day |
| **Max Retest Wait** | 20 bars | Pending zone expires after 20 bars if not filled |
| **Sweep Staleness** | 25 bars | Sweep expires if no CISD confirmation within 25 bars |

---

## 📊 v3 Backtest Results (NQ, 2020-2026)

| Configuration | Trades | WR | PF | Net PnL | Max DD |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Baseline** (SL-4, FVG Touch, no filters) | 7,813 | 63.9% | 2.66 | +$301K | -$1,797 |
| **+ Session Sweeps** (Asia/London/NYAM) | 7,919 | 68.0% | 3.15 | +$326K | -$1,921 |
| **+ 15bps + 1.5× vol gate** | 4,814 | 66.8% | 3.57 | +$208K | -$678 |
| **+ 50K prop sizing** ($500/trade) | 4,814 | 66.8% | 3.58 | +$1,028K | -$3,392 |
| **+ 1m execution** (2022-2026) | 3,519 | 68.9% | 3.48 | +$687K | -$2,729 |

### Sweep Source Win Rates (no-filter baseline)
| Source | Trades | WR |
| :--- | :--- | :--- |
| London H/L | 317 | 77-82% |
| 1H BSL/SSL | 2,648 | 68-71% |
| 4H BSL/SSL | 710 | 51-69% |
| NYAM H/L | 1,039 | 64-67% |
| Swing H/L | 3,240 | 59-61% |
| PDH/PDL | 585 | 48-64% |

---

## 💻 Synchronized Code References

1. **Python v3 Backtester**: [`scripts/backtests/run_ict_v3_backtest.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/backtests/run_ict_v3_backtest.py)
2. **Python Original Backtester** (experiment matrix): [`scripts/backtests/backtest_liquidity_cisd_strategy.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/backtests/backtest_liquidity_cisd_strategy.py)
3. **TradingView Strategy (Pine v6)**: [`scripts/indicators-pine/ifvg_cisd/IFVG_CISD_MTF_Strategy.pine`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/indicators-pine/ifvg_cisd/IFVG_CISD_MTF_Strategy.pine)
4. **NinjaTrader 8 Strategy**: [`scripts/ninjatrader/strategies/ifvg_cisd/ICTFVGCISDBot.cs`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/ninjatrader/strategies/ifvg_cisd/ICTFVGCISDBot.cs)
5. **Empirical Audit**: [`docs/research/EMPIRICAL_QUANT_AUDIT_CISD_ES_NQ.md`](file:///c:/Users/vinay/tvDownloadOHLC/docs/research/EMPIRICAL_QUANT_AUDIT_CISD_ES_NQ.md)

### Key Parameters (all platforms aligned)

| Parameter | Value | Python | Pine | NT8 |
| :--- | :--- | :--- | :--- | :--- |
| Queen Target | 10 bps | ✅ | ✅ | ✅ |
| Runner Target | 30 bps | ✅ | ✅ | ✅ |
| Risk Ceiling | 15 bps | ✅ | ✅ | ✅ |
| Volume Gate | 1.5× SMA20 | ✅ | ✅ | ✅ |
| Entry Model | FVG Touch | ✅ | ✅ | ✅ |
| SL Model | SL-4 Origin | ✅ | ✅ | ✅ |
| Max Daily Trades | 5 | ✅ | ✅ | ✅ |
| Max Retest Wait | 20 bars | ✅ | ✅ | ✅ |
| RTH Window | 09:45-15:30 | ✅ | ✅ | ✅ |
| EOD Flatten | 15:55 | ✅ | ✅ | ✅ |
| Position Sizing | risk_usd / SL | ✅ | ✅ | ✅ |

### Known Platform Differences (to resolve)

1. **Session data**: Python uses 24h continuous parquet; NT8 may use RTH-only MNQ contract data → fewer overnight sweeps detected
2. **Same-bar execution**: NT8 evaluates stop loss on the entry bar; Python delays stop check to bar after entry → NT8 has lower WR
3. **1H/4H bar construction**: Python resamples from 5m; NT8 uses native AddDataSeries → different swing levels
4. **Swing detection**: Python uses 3-bar fractal on 5m; NT8 uses 3-bar fractal on primary series → should match but timing may differ by 1 bar