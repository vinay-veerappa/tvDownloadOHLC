# Institutional Strategy Confluence Playbook & Idea Repository

A definitive, living quantitative and structural guide to high-probability trade confluences across Futures (NQ, ES, YM, RTY) and Equities. Every confluence listed in this document is backed by mathematical statistics, institutional orderflow mechanics, or ICT/SMC principles.

---

## 1. Confluence Philosophy & The Rule of Three

In quantitative and algorithmic trading, single-trigger strategies (e.g. enter when price crosses IB High) suffer from severe regime fragility and drawdown. High-expectancy systematic trading requires **orthogonal confluences** across distinct market dimensions:

`
+---------------------------------------------------------------------------------------------------------------+
|                                      THE 5 ORTHOGONAL CONFLUENCE LAYERS                                       |
+-------------------+---------------------------------------------------------------+---------------------------+
| Layer             | Core Question Answered                                        | Analytical Tool           |
+-------------------+---------------------------------------------------------------+---------------------------+
| **1. Macro/Regime**| Is the market expanding or mean-reverting today?              | IB/ATR Ratio, EM Walls    |
| **2. Session Geom**| Where is price relative to equilibrium / value?               | IB Midpoint, PDH/PDL, P12 |
| **3. Temporal**    | Is it a high-probability institutional participation window?  | 10:30 Fence, Silver Bullet|
| **4. Orderflow/FVG**| Is there real institutional displacement / imbalance defense? | 5m FVG, iFVG, BPR         |
| **5. Liquidity**   | Whose stops were just taken, and where is resting liquidity?  | 09:00 Sweep, Asian/London |
+-------------------+---------------------------------------------------------------+---------------------------+
`

---

## 2. Category 1: Session Geometry & Equilibrium Confluences

### C1.1: IB Midpoint Gravitational Pivot (The 75% / 68% Directional Rule)
* **Definition**: The arithmetic midpoint of the 09:30–10:00 Initial Balance: IB_Mid = (IB_High + IB_Low) / 2.0.
* **Empirical Stat (1,932 sessions, NQ1)**:
  * 10:00 Hour closed **ABOVE IB Mid**: **75.0% probability session closes Green** (+37.1 bps average move).
  * 10:00 Hour closed **BELOW IB Mid**: **68.4% probability session closes Red** (-33.2 bps average move).
* **Strategy Application**:
  * **Long Directional Gate**: Enter Long ONLY when price is trading and accepted above IB_Mid.
  * **Short Directional Gate**: Enter Short ONLY when price is trading and accepted below IB_Mid.
  * **Target Magnet**: Use IB_Mid as the Take Profit 1 (TP1) target for all Play 3 Sweep Fades.

---

### C1.2: IB Size & ATR Ratio Quintile (Regime Routing Standard)
* **Definition**: Ratio of Initial Balance range to 14-day Daily ATR (IB_Range / ATR_14) and range in Basis Points.
* **Empirical Stat (5,270 sessions)**:
  * **Severe Compression (IB < 0.35x ATR or <45 bps)**: Play 3 Sweep Fade achieves **73.5% to 75.2% win rate** and 6.30 PF. Breakouts fail >50% of the time.
  * **Expanded / Trend (IB > 0.75x ATR or >80 bps)**: Play 1 Breakout achieves **92.1% to 95.0% win rate** and 15.92 PF with +107 bps average MFE. Fading here collapses to <30% win rate.
* **Strategy Application**:
  * **Dynamic Router**: Auto-route to Play 3 Fade on compressed days; auto-route to Play 1/2 Continuation on expanded days.

---

### C1.3: Prior Day Levels (PDH, PDL, PDM, PDC)
* **Definition**: Key reference levels from the previous Regular Trading Hours (RTH) session.
* **Mechanics**:
  * **PDH/PDL Sweep Rejection**: If price breaks IB High but immediately hits PDH and prints a rejection candle -> High-probability Fade back into IB.
  * **PDH/PDL Cleared with Displacement**: Breaking IB High that also clears and closes above PDH -> Open-air blue sky continuation (Runner target +50 to +80 bps).

---

## 3. Category 2: Temporal & Macro Window Confluences

### C2.1: 10:00 AM Hourly Candle Liquidity Sweep of 09:00 AM
* **Definition**: Whether the 10:00–11:00 AM hourly candle breaches the 09:00–10:00 AM hourly high or low.
* **Empirical Stat (1,932 sessions)**:
  * **Swept 09:00 High ONLY (43.6% of days)**: **78.3% bullish continuation probability** (+39.7 bps).
  * **Swept 09:00 Low ONLY (38.6% of days)**: **72.9% bearish continuation probability** (-38.3 bps).
  * **Double Sweep (Swept BOTH High & Low - 8.9% of days)**: **R1 Double-Breach Whipsaw Day** (ABSOLUTE ENTRY BAN).
  * **Inside Hour (Neither Swept - 8.9% of days)**: Low-volatility consolidation.

---

### C2.2: 10:30 AM Stabilization Fence (London Fix & Macro Settlement)
* **Definition**: Suppressing continuation entries until 10:30 AM ET.
* **Forensic Stat**: **76.24% of all strategy losses occur before 10:30 AM ET** due to 10:00 AM US Macro News releases and London Fix rebalancing.
* **Strategy Application**: Set EarliestEntryTime = 1030 for all breakout and pullback trend strategies.

---

### C2.3: 11:30–13:30 Lunch Moratorium & The Contrarian Lunch Macro
* **Definition**: Volume drops by ~60% during the NY Lunch window (11:30–13:30 ET).
* **Mechanics**:
  * Continuation breakouts taken during lunch suffer from low-momentum drift and stopout.
  * **Contrarian Setup**: Algorithms frequently run the 10:00 AM low/high during lunch to clear early retail trailing stops before resuming the PM trend.

---

## 4. Category 3: Orderflow & Fair Value Gap (FVG) Confluences

### C3.1: First 5-Minute FVG Post-10:00 AM (The Master Chop Filter)
* **Definition**: The first 3-bar Fair Value Gap formed on the 5-minute timeframe between 10:00 and 10:30 AM ET.
* **Empirical Stat (1,932 sessions)**:
  * **Bullish 5m FVG Respected**: **98.7% Win Rate** (+81.3 bps average gain).
  * **Bearish 5m FVG Respected**: **95.0% Win Rate** (+87.2 bps average gain).
  * **FVG Inversion**: Original direction fails >50%--64%, flipping into a prime Fade setup.
  * **Master Anti-Chop Rule**: If NO 5m FVG forms post-10:00 -> **STAY CASH / NO ENTRY**.

---

### C3.2: Hierarchical 3-Tier FVG Fallback Engine
* **Tier 1 (Primary)**: First 5m FVG post-10:00 AM (10:00–10:30).
* **Tier 2 (Fallback 1)**: First 5m FVG in 09:00–10:00 AM window (Pre-Open / Opening Cash Impulse).
* **Tier 3 (Fallback 2)**: First 1m FVG at 09:30–09:35 AM (RTH Open Catalyst Anchor).

---

### C3.3: Inversion FVG (iFVG) Flip for Reversal Fades
* **Definition**: A Fair Value Gap that gets completely closed through by subsequent price action, flipping polarity:
  * Bullish FVG broken downward -> becomes **Resistance**.
  * Bearish FVG broken upward -> becomes **Support**.
* **Strategy Application**: Play 3 Sweep Fade enters on the first retest of the broken FVG level from the opposite side.

---

### C3.4: Balanced Price Range (BPR) & Consequent Encroachment (CE 50%)
* **Definition**:
  * **BPR**: Overlapping bullish and bearish FVGs creating a neutralized liquidity vacuum.
  * **CE 50%**: The exact 50% midline of any FVG. Institutional limit orders cluster at the CE level. Stops are placed 2 ticks beyond the FVG boundary.

---

## 5. Category 4: Structural Liquidity & Session Sweeps

### C4.1: Asian & London Range Liquidity Sweeps
* **Definition**: Overnight session high/low reference points (Asia: 18:00–02:00, London: 02:00–05:00).
* **Mechanics**:
  * If the 09:30–10:00 NY Open sweeps London Low and rejects back into value -> 82% probability of sweeping London High during the NY session.

---

### C4.2: Equal Highs (EQH) / Equal Lows (EQL) Magnetism
* **Definition**: Two or more intraday wicks within 2 ticks of each other, creating an obvious pool of stop-loss buy/sell liquidity.
* **Mechanics**: Price is gravitationally drawn to clean up EQH/EQL before reversing. Never place stops exactly at equal extremes.

---

## 6. Category 5: Volatility, Expected Move & Delta Confluences

### C5.1: Expected Move (EM) Expiration Walls (0DTE to Weekly)
* **Definition**: Options-implied 1-standard-deviation Expected Move extracted across all available expirations (0DTE, 1DTE, 2DTE... Weekly Friday).
* **Mechanics**:
  * 0DTE +1 EM acts as a hard institutional distribution ceiling (85% intraday containment). Breakouts into +1.5 EM are prime fade exhaustion points.

---

### C5.2: Cumulative Volume Delta (CVD) Absorption Divergence
* **Definition**: Delta divergence between Price and CVD at range boundaries:
  * **Bullish Absorption**: Price makes Lower Low at IB Low, but CVD makes Higher Low -> Passive limit buyers absorbing aggressive selling -> Immediate Long Fade.
  * **Bearish Absorption**: Price makes Higher High at IB High, but CVD makes Lower High -> Passive iceberg sellers absorbing market buyers -> Immediate Short Fade.

---

## 7. Strategy Confluence Scoring Matrix (0 to 10 Points)

Before arming an automated trade, compute the **Composite Confluence Score (S)**:

| Confluence Factor | Points | Condition |
| :--- | :---: | :--- |
| **IB Midpoint Alignment** | **+2** | Long if > Mid, Short if < Mid |
| **5m FVG / iFVG Respected** | **+3** | Valid 5m FVG or iFVG held on candle closes |
| **10:00 Hourly Sweep Alignment**| **+2** | Single sweep of 09:00 High/Low in trade direction |
| **Regime Sizing Fit** | **+2** | Breakout on >= 0.50x ATR; Fade on < 0.35x ATR |
| **Time Window Compliance** | **+1** | Entry between 10:30–11:30 or 13:30–15:30 |
| **R1 Double Sweep Lockout** | **-10** | Both 09:00 High & Low swept -> **ZERO TRADES** |

* **Score >= 8 / 10**: **Full Position Size (100% Pack Trading: 50% Queen + 50% Runner)**.
* **Score 6--7 / 10**: **Half Position Size (50% Sizing)**.
* **Score < 6 / 10**: **NO TRADE / CASH**.

---

## 8. Indicator & Signal Library Inventory

Every indicator, RSI variant, and signal engine built and tested in this repo. Each entry lists what it is, where it lives, and its empirical performance where measured.

### 8.1 RSI Variants (tested on BB mean reversion, ES 5m)

All variants return a 0-100 series and are drop-in replacements for Wilder RSI in the BB strategy. Empirical results from `docs/research/COMPREHENSIVE_EXPERIMENTS.md` (ES 09-26 5m, 2025-01-01 → 2026-08-21, 4×MES, $0 cost).

| Variant | Mechanism | Source | BB PF | BB WR | BB Net | Verdict |
| :--- | :--- | :--- | :---: | :---: | :---: | :--- |
| **Wilder RSI (33/67)** | Fixed 14-period, fixed thresholds | `range_strategy_comparison.py:_wilder_rsi` | 1.12 | 48.0% | $+109 | Baseline — low frequency (25 trades) |
| **Wilder RSI + 2-bar hook** | Fixed 14-period, requires 2-bar confirmation (prior bar at band + RSI extreme, current bar closes back inside) | NT8 `BBMRReversionBot` + Python `BBRsiMeanReversionStrategy` | 1.14 | 54.2% | $+240 | **Doubles trades (25→48)**, improves WR |
| **Wilder RSI SHORT-only** | Drops LONG signals entirely | `comprehensive_experiments.py` | **2.12** | 64.3% | $+420 | **Best single-side config** — short regime bias in ES |
| **Adaptive RSI Zones** | Logit transform + adaptive thresholds (tanh-based zones that widen in vol, tighten in squeeze) | `libs_py/adaptive_rsi.py` + NT8 `AdaptiveRSIZones.cs` | 1.05 | 46.7% | $+34 | Fewer signals (15), no edge over Wilder |
| **Adaptive RSI (relaxed)** | Same but with relaxed zone thresholds | `adaptive_rsi.py` | 0.87 | 45.2% | $-160 | Too many false signals (31 trades) |
| **Chande DMI** | Variable lookback via volatility index (TD = 14/VI, clipped 5-30) | `libs_py/adaptive_rsi_variants.py:chande_dmi_rsi` | 0.28 | 33.3% | $-501 | **Worst variant** — terrible for BB |
| **Kaufman ER RSI** | Efficiency-ratio scaled period (14 in trends → 28 in chop) + adaptive alpha | `libs_py/adaptive_rsi_variants.py:kaufman_er_rsi` | **1.90** | 56.2% | $+450 | **Best RSI for BB** — adapts to regime |
| **Kaufman ER + 2-bar hook** | Same + 2-bar confirmation | NT8 `BBMRReversionBot` (UseKaufmanErRsi=true) | **1.81** | 60.7% | $+652 | **Best overall BB config** (Python) |
| **Kaufman ER SHORT-only** | Drops LONG | `comprehensive_experiments.py` | **2.12** | 63.6% | $+389 | Tied with Wilder SHORT-only |
| **Ehlers Cycle RSI** | Dominant cycle via autocorrelation periodogram, RSI length = half cycle | `libs_py/adaptive_rsi_variants.py:ehlers_cycle_rsi` | 2.03 | 60.0% | $+296 | High PF but only 10 trades — low sample |
| **Connors RSI** | Composite: RSI(3) + RSI(streak,2) + percent-rank(close,100) / 3 | `libs_py/adaptive_rsi_variants.py:connors_rsi` | 0.39 | 50.0% | $-208 | **Fails for BB** — too few trades (6) |

**Key takeaway**: Kaufman ER RSI with 2-bar hook is the winning BB config. Wilder RSI SHORT-only is a strong alternative. Chande DMI and Connors RSI are dead weight for mean reversion.

### 8.2 Trend-Following Indicators

#### Supertrend (ST)
* **Formula**: ATR-based trailing band. Upper = (high+low)/2 + mult×ATR, Lower = (high+low)/2 - mult×ATR. Flip on close beyond band.
* **Source**: NT8 `SupertrendIndicator.cs` + Python `supertrend_intraday_cost.py`
* **Default params**: period=14, multiplier=2.0 (ATR uses crude `(MAX-MIN)/14` to match NT8)
* **Trail policy**: `SupertrendTrail` — ratchet stop on High/Low × trail_mult×ATR, skip entry bar (`trailFirstBar` flag)
* **Empirical results** (ES 5m, 2025, 1×ES):

| Config | Trades | WR | PF | Net | Avg R |
| :--- | :---: | :---: | :---: | :---: | :---: |
| ST baseline (14,2) trail 1.5 | 762 | 38.3% | 1.50 | $+1,876 | +0.29 |
| + ATR regime filter (Q4 only) | 353 | 40.5% | 1.56 | $+1,059 | +0.38 |
| + Time filter (skip 14:00+) | 478 | 42.3% | 1.80 | $+1,958 | +0.46 |
| + ATR + Time | 250 | 42.0% | 1.79 | $+1,046 | +0.53 |
| + ATR + Time + 1.0×trail | 250 | **55.6%** | **3.37** | $+1,844 | +0.56 |

**Key takeaway**: ATR regime + time filter (LatestEntry=1359) + 1.0×ATR trail is the winning ST config (PF 3.37). FVG/HTF confluence HURTS Supertrend.

#### HalfTrend
* **Formula**: ATR-based trend with amplitude filter. Similar to Supertrend but uses a half-cycle detection to avoid whipsaw.
* **Source**: `docs/research/SUPERTREND_HALFTREND.md`
* **Status**: Evaluated, Supertrend preferred for simplicity and parity.

### 8.3 Bollinger Band Configurations

* **Source**: NT8 `BBMRReversionBot.cs` + Python `BBRsiMeanReversionStrategy`
* **Default**: BB(20, 2.0σ) on 5m close, ADX(14) < 25 gate
* **Stop**: min(band, close) - 1.5×ATR_5m, floored at entry - 1.0×ATR_5m
* **TP1**: BB middle band (SMA 20) — scale 50%
* **TP2**: Opposite BB band — runner (stop to BE after TP1)
* **Policy**: `FixedTP1TP2` (Python parity)
* **Session**: NY_MIDDAY + NY_PM (11:30-16:00 ET), one trade per session
* **Filters tested**: ADX gate, squeeze-only (bandwidth percentile), IB compression, MACD histogram, Kaufman ER RSI, 2-bar hook, SHORT-only

### 8.4 VWAP & Volume Indicators

| Indicator | Description | Source | NT8 | Pine | Python |
| :--- | :--- | :--- | :---: | :---: | :---: |
| **RedTailAutoVWAP** | Session-anchored VWAP with std-dev bands | `indicators/redtail/RedTailAutoVWAP.cs` | ✅ | — | — |
| **RedTailSwingAnchoredVWAP** | Swing-point anchored VWAP (from major pivot) | `redtail/RedTailSwingAnchoredVWAP.cs` | ✅ | — | — |
| **RedTailVWAPFibBands** | VWAP with Fibonacci extension bands | `redtail/RedTailVWAPFibBands.cs` | ✅ | — | — |
| **VWAPSMIHybrid** | VWAP + Stochastic Momentum Index hybrid | `vinay/VWAPSMIHybrid.cs` | ✅ | ✅ | — |
| **VWAPReclaimIndicator** | Price reclaim of VWAP after displacement | `vwap_reclaim/VWAPReclaimIndicator.cs` | ✅ | — | — |
| **RedTailVolumeProfile** | Volume profile (POC, VAH, VAL, nodes) | `redtail/RedTailVolumeProfile.cs` | ✅ | — | — |
| **RedTailVolume** | Cumulative delta + volume spikes | `redtail/RedTailVolume.cs` | ✅ | — | — |
| **RedTailFRVP** | Footprint-style relative volume profile | `redtail/RedTailFRVP.cs` | ✅ | — | — |
| **orderflow_bands** | Orderflow-based dynamic bands | `indicators-pine/orderflow_bands/` | — | ✅ | — |

### 8.5 Market Structure & Level Indicators

| Indicator | Description | Source |
| :--- | :--- | :--- |
| **RedTailMarketStructure** | BOS/CHoCH/MSS detection (swing-based structure) | `redtail/RedTailMarketStructure.cs` |
| **RedTailMarketStructureCompanion** | Companion panel for structure overlays | `redtail/RedTailMarketStructureCompanion.cs` |
| **RedTailKeyLevels** | Auto-detect PDH/PDL/IB High/Low/session levels | `redtail/RedTailKeyLevels.cs` |
| **RedTailLVNHunter** | Low-Volume-Node hunter (liquidity voids) | `redtail/RedTailLVNHunter.cs` |
| **SessionStatisticalLevels** | Statistical session high/low levels | `redtail/SessionStatisticalLevels.cs` |
| **SessionOpeningBarRange** | Opening Range (OR) with session presets | `redtail/SessionOpeningBarRange.cs` |
| **SessionRanges** | Configurable session range boxes (Asia/London/NY/IB) | `vinay/SessionRanges.cs` |
| **SessionOpensEngine** | Session open times + overnight levels | `vinay/SessionOpensEngine.cs` |
| **LiquidityLevels** | BSL/SSL sweep detection + liquidity catalog | `vinay/LiquidityLevels.cs` |
| **DailyNYLevels** | PDH/PDL/PWH/PWL + Midnight Open + midnight anchors | Pine `DailyNYLevelsAnalytics.pine` |
| **RangeProbabilityIndicator** | Probability look-up-table for range targets | `range_probability/RangeProbabilityIndicator.cs` |

### 8.6 ICT / SMC Indicators

| Indicator | Description | Source |
| :--- | :--- | :--- |
| **ICTFVGCISDIndicator** | Fair Value Gap + CISD (Change-in-Structure-Delivery) detection | `ifvg_cisd/ICTFVGCISDIndicator.cs` + Pine `IFVG_CISD_MTF_Indicator.pine` |
| **FailedAuctionIndicator** | Failed auction detection (Tape Reading) | `failed_auction/FailedAuctionIndicator.cs` |
| **ProfilerIndicator** | Session profiler (Asia/London/NY status, IB probabilities, broken logic) | Pine `profiler/ProfilerIndicator.pine` |
| **PriceModelIndicator** | Institutional price model overlay (order blocks, MSS, liquidity) | Pine `profiler/PriceModelIndicator.pine` |
| **Pre-computed ICT features** | FVG, HTF levels (PDH/PDL/PWH/PWL), liquidity sweeps | `data/derived/ICT/ES1_{imbalance_5m,htf_levels,liquidity_5m}.parquet` |

### 8.7 Oscillators & Momentum

| Indicator | Description | Source |
| :--- | :--- | :--- |
| **AdaptiveRSIZones** | Adaptive RSI with logit-transform + dynamic zones (tanh-based) | `vinay/AdaptiveRSIZones.cs` + Python `libs_py/adaptive_rsi.py` |
| **KeltnerChannelSignals** | Keltner Channel (EMA + ATR) with breakout signals | `keltner_channel/KeltnerChannelSignals.cs` + Pine `KeltnerChannelSignals.pine` |
| **RedTailEMACloud** | EMA cloud (fast/slow) with trend ribbon | `redtail/RedTailEMACloud.cs` |
| **EMAPullbackIndicator** | EMA pullback entry detection (8/21/55 EMA stack) | `ema_pullback/EMAPullbackIndicator.cs` |
| **MACD** | Standard MACD (12/26/9) — used as BB gate (histogram direction) | Python `vwap_fade.py:_macd` |
| **ADX** | Wilder ADX (14) — regime gate for BB (skip if ≥25) | Python `range_strategy_comparison.py:_adx` |

### 8.8 Strat / Pattern Indicators

| Indicator | Description | Source |
| :--- | :--- | :--- |
| **TheStratClassifier** | TheStrat candle classification (1-2-3 inside/outside) | `the_strat/TheStratClassifier.cs` |
| **TheStratFTFCHud** | Full-Timeframe-continuation HUD for TheStrat | `the_strat/TheStratFTFCHud.cs` |
| **CandleScience** | 3-candle pattern statistical probabilities (Filter-then-Compute) | Pine `CandleScience/candle_science_v17_5.pine` |
| **DailyClassification** | R1/R2/DWP/DNP daily classification + OR logic hierarchy | Pine `DailyClassification/daily_classification_v2.pine` |
| **HTF EMA Analysis** | Higher-timeframe EMA stack analysis (session-by-session) | Pine `htf_ema_analysis/HTF_EMA_Analysis.pine` + Python `wargaming/htf_ema_analysis.py` |
| **ProbabilityMap** | Session-based probability map for directional bias | Pine `ProbabilityMap/ProbabilityMap.pine` |
| **MagicHour** | 7-strategy magic-hour session analysis | Pine `magic_hour_analysis/` |

### 8.9 Options & Dealer-Level Indicators

| Indicator | Description | Source |
| :--- | :--- | :--- |
| **ExpectedMove (EM) Walls** | Options-implied ±1σ expected move per expiration (0DTE-weekly) | Pine `options/ROWExpectedMove_v3.pine` + TOS RTD real-time |
| **DealerLevels** | Gamma/GEX dealer levels (charm, vanna exposure) | Pine `options/DealerLevels.pine` + `MacroDealerLevels.pine` |
| **ExecutionHUD** | Real-time execution HUD (Greeks, delta, gamma exposure) | Pine `options/ExecutionHUD.pine` |
| **DailyOC levels** | Daily Options-Cross levels (max pain, gamma flip) | Pine `options/Daily_OC_levels.pine` |
| **ExpectedVolatility** | Implied volatility regime + term structure | Pine `options/ExpectedVolatality.pine` |

### 8.10 Strategies (Built & Tested)

| Strategy | Type | Description | NT8 | Python | Validated |
| :--- | :--- | :--- | :---: | :---: | :---: |
| **BBMRReversionBot** | Mean reversion | BB(20,2) + RSI + ADX gate, FixedTP1TP2 exit | ✅ | ✅ | ✅ (parity) |
| **STTrendBot** | Trend following | Supertrend(14,2) + ATR regime + time filter, 1.0×trail | ✅ | ✅ | ✅ (parity) |
| **Bandits8020Bot** | Mean reversion | 80/20 bandit (prior IB sweep + BB confirmation) | ✅ | — | — |
| **IBBreakoutBot** | Breakout | IB High/Low breakout continuation | ✅ | — | — |
| **IBRetestBot** | Breakout | IB level retest entry | ✅ | — | — |
| **IBFadeBot** | Mean reversion | IB extreme fade (reject back inside) | ✅ | — | — |
| **ICTFVGCISDBot** | ICT | FVG + CISD confluence entry | ✅ | — | — |
| **FailedAuctionBot** | Tape reading | Failed auction reversal entry | ✅ | — | — |
| **VWAPReclaimBot** | Mean reversion | VWAP reclaim after displacement | ✅ | — | — |
| **KeltnerChannelBot** | Breakout | Keltner Channel breakout with signals | ✅ | — | — |
| **EMAPullbackBot** | Trend following | EMA pullback entry (8/21/55 stack) | ✅ | — | — |
| **Strat212ContinuationBot** | Pattern | TheStrat 2-1-2 continuation | ✅ | — | — |
| **Strat22RevStratBot** | Pattern | TheStrat 2-2 reversal | ✅ | — | — |
| **RangeProbabilityStrategy** | Statistical | Range-target probability LUT | ✅ | — | — |
