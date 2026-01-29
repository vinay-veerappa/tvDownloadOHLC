# NQ London Playbook — Decision Tree and Statistical Trading Framework for Nasdaq Futures (NQ) — Herman Trading

NQ London Playbook — Decision Tree (with Stats)
By Herman Trading

## Introduction
This research presents a data-driven trading framework for the London session on Nasdaq Futures (NQ), built from more than three years of verified historical data.
Using Python and Jupyter Notebooks, each session interaction between Asia, Pre-London, Opening Range (OR), and London was statistically measured — identifying how often sweeps, continuations, and reversals occur, and how far price typically extends after each.
The result is both a research study and a trading playbook — a structured decision tree that translates probabilities into actionable logic for intraday traders.

## Dataset and Methodology
*   Data source: BacktestMarket.com
*   Instrument: Nasdaq Futures (NQ)
*   Timeframe: January 2022 → August 2025
*   Resolution: 1-minute OHLCV data
*   Timezone: Converted from Chicago (CT) → New York (ET)
*   Sample size: 719 trading days
*   Average Asia range: 70.86 points

### [Table: NQ Trading Sessions (New York Time)]
*Transcribed from Image p4_0.png*

| Session | Time (ET) | Notes |
| :--- | :--- | :--- |
| **Asia** | 20:00 – 00:00 | Previous day → Current day |
| **Pre-London** | 00:00 – 02:00 | "Dead Zone" |
| **Opening Range** | 02:00 – 03:00 | Setting the stage |
| **London** | 03:00 – 05:00 | Expansion phase |

All timestamps were normalized to ensure consistency across years and volatility regimes.

   ### [Table: Key Definitions]
*Transcribed from Image p3_2.png*

| Concept | Description |
| :--- | :--- |
| **Asia Size** | Range (High–Low) between 20:00 – 00:00 ET.<br>• Large > 70.9 pts • Small ≤ 70.9 pts |
| **Sweep** | A session trades through (by ≥ 1 tick) the High/Low of a prior session |
| **First Sweep** | The first side (High or Low) taken within that window |
| **Follow vs Flip** | *Follow*: OR sweeps the same side as Pre-London.<br>*Flip*: OR sweeps the opposite side. |
| **Penetration (pts)** | Distance from sweep level to extreme after the sweep |
| **Time-to-Sweep (min)** | Minutes from session open (02:00 or 03:00) to first sweep |
| **Retest** | Price revisits the OR edge ± 2 pts within 60 minutes (high-quality trigger) |

## Why Asia Size Matters
Asia defines the volatility regime for the entire day.
*   **Large Asia (> 70.9 pts)**: High probability of strong continuation after OR (≈ 69 – 87%) with faster resolution (2–12 min).
*   **Small Asia (≤ 70.9 pts)**: Shorter expansions (≈ 17–29 pts), more retests, and slower development (6–12 min).

### High-Level Probabilities
These aggregated probabilities help identify the likely path for the London session based on Asia range and Pre-London behavior.

### [Table: High-Level Context Bias]
*Transcribed from Image p3_1.png*

| Context | London Sweep Rate | Bias | Median Penetration | Median Time |
| :--- | :--- | :--- | :--- | :--- |
| Asia ↓ & PL Low → **OR High** (Small Asia) | **76.9%** | **Bullish** | +24.8 pts | 6.0 min |
| Asia ↓ & PL High → **OR Low** (Small Asia) | **81.9%** | **Bearish** | -29.5 pts | 6.0 min |
| Asia ↑ & PL Low → **OR High** (Large Asia) | **86.1%** | **Bullish** | +38.3 pts | 2.0 min |
| Asia ↑ & PL High → **OR Low** (Large Asia) | **72.1%** | **Bearish** | -38.7 pts | 5.5 min |

## How to Use This Intraday
**Step 1 – Classify the Day at 02:00 ET**
At the Opening Range start:
1.  Measure Asia range (20:00–00:00 ET).
    *   > 70.9 = Large
    *   ≤ 70.9 = Small
2.  Identify what Pre-London did to the Asia range:
    *   No sweep
    *   Swept High
    *   Swept Low
This combination defines the Opening Range bias (High vs Low vs None).

### Opening Range (02:00–03:00) First Sweep Bias
*Transcribed from Image p6_0.png*

**Interpretation**: Before OR is done, which side is more likely to be swept first given Asia size and what Pre-London did to Asia.

**Large Asia (> 70.9 pts)**
| Pre-London vs Asia | Sample (n) | First sweep = High | First sweep = Low | No sweep |
| :--- | :--- | :--- | :--- | :--- |
| No sweep | 20 | 40.0% | **50.0%** | 10.0% |
| Swept High | 125 | 37.6% | **52.8%** | 9.6% |
| Swept Low | 98 | **50.0%** | 33.7% | 16.3% |

Quick Read: With a Large Asia, OR leans Low-first after PL swept High, but leans High-first after PL swept Low. With PL no seeep, its roughly balanced, slight Low-first tilt.

**Small Asia (< 70.9 pts)**
| Pre-London vs Asia | Sample (n) | First sweep = High | First sweep = Low | No sweep |
| :--- | :--- | :--- | :--- | :--- |
| No sweep | 21 | **52.4%** | 42.9% | 4.8% |
| Swept High | 189 | 38.6% | **52.9%** | 8.5% |
| Swept Low | 259 | **54.1%** | 37.5% | 8.5% |

Quick Read: With a smalll Asia, OR leans High-first after PL swept Low, but leans Low-first after PL swept High. With PL no seeep, its roughly balanced, slight High-first tilt.

**Practical Takeaway**: The sweep direction of Pre-london vs Asia is the dominant clue for which side OR probes first
*   **PL swept High → Low-first bias in OR**
*   **PL swept Low → High-first bias in OR**
Asia size modulates the strength of the bias (large Asia = more balanced except when PL made a clear sweep)

### [Benchmarks: All Days]
*Transcribed from Image p3_0.png*
*   **Average Asia Range**: **70.86 pts** (This is the cutoff for Large vs Small)
*   **Average Pre-London Range**: **45.08 pts**
*   **Average Opening Range (02:00)**: **44.73 pts**




### Opening Range (02:00 – 03:00 ET) Overview
**Asia Above Average (> 70.9 pts)**
*   PL Swept High → Low-first bias (≈ 50%)
*   PL Swept Low → High-first bias (≈ 48%)
*   No Sweep → Balanced tilt
*   **Interpretation**: Large Asia tends to flip the Pre-London direction. A Pre-London high sweep often leads to a low-first OR break, and vice-versa.

### [OR Strategy Tree 1: Large Asia (> 70.9 pts)]
*Transcribed from Image p5_0.png*

**Did Pre-London sweep Asia HIGH?**
*   **YES (PL swept HIGH)** [n=125 | CONF: Strong]
    *   **Primary**: **FLIP ↓** (sweep PL Low) ≈ **48.8%**
    *   **Opposite**: FOLLOW ↑ (sweep PL High) ≈ 32.8%
    *   **Bias**: **SHORT** (flip favored)
    *   **Medians**: flip pushes ≈ **20–22 pts**, ~6–14 min
    *   **Plan**: First clean break of PL Low → quick retest → **SELL**. TP1 ≈ ½ median; TP2 ≈ median.

*   **NO → Did Pre-London sweep Asia LOW?**
    *   **YES (PL swept LOW)** [n=98 | CONF: Strong]
        *   **Primary**: **FLIP ↑** (sweep PL High) ≈ **43.9%**
        *   **Opposite**: FOLLOW ↓ (sweep PL Low) ≈ 27.6%
        *   **Bias**: **LONG** (flip favored)
        *   **Medians**: flip pushes ≈ **20–22 pts**, ~7–15 min
        *   **Plan**: First clean break of PL High → retest → **BUY**.

*   **NO (PL NO SWEEP)** [n=20 | CONF: Low]
    *   **Outcomes**: PL Low ≈ 45% | PL High ≈ 40%
    *   **Bias**: Slight SHORT tilt, but two-way risk is high.
    *   **Plan**: Trade the **first decisive** PL-edge breach + retest only.

### [OR Strategy Tree 2: Small Asia (≤ 70.9 pts)]
*Derived from Image p6_0.png Data*

**Did Pre-London sweep Asia HIGH?**
*   **YES (PL swept HIGH)** [n=189]
    *   **Primary**: **FLIP ↓** (sweep PL Low) ≈ **52.9%** (vs 38.6% Follow)
    *   **Bias**: **Stronger FLIP SHORT** than Large Asia.
    *   **Plan**: Look for OR to break PL Low first.

*   **NO → Did Pre-London sweep Asia LOW?**
    *   **YES (PL swept LOW)** [n=259]
        *   **Primary**: **FLIP ↑** (sweep PL High) ≈ **54.1%** (vs 37.5% Follow)
        *   **Bias**: **Strong FLIP LONG**.
        *   **Plan**: Look for OR to break PL High first.

*   **NO (PL NO SWEEP)** [n=21]
    *   **Primary**: **Sweep High** ≈ **52.4%** (vs 42.9% Low)
    *   **Bias**: Slight LONG tilt.

**Asia Below Average (≤ 70.9 pts)**
*   PL Swept Low → High-first bias (≈ 54%)
*   PL Swept High → Low-first bias (≈ 53%)
*   No Sweep → Slight High-first tilt
*   **Interpretation**: Small Asia is more trend-biased; price more often continues in the direction of Pre-London’s last sweep.

## London Session (03:00 – 05:00 ET)
**What Typically Happens After OR Breaks**
Once the Opening Range establishes a direction (High or Low break), the London session often expands that move.
Continuation probability: ~69 – 87% depending on the branch.

### [Table: London Follow-Through (Large & Small Asia)]
*Transcribed from Image p7_0.png*
Once OR complete (you know whether OR broke High or Low)
you can use the table below to set expectations for sweep in London, typical time to sweep and median penetrations beyond the OR edge.

Notes:
* First sweep  = which OR side London hits first
* Win % = probability of first sweep being in the direction of the OR break
* Median Time = median time to first sweep
* Median Penetration = median penetration beyond the OR edge
* Range Expansion % = probability of range expansion beyond the OR edge
* High sample sizes are bolded., tiny n (<= 10) means be cautious.

London follow-through (by Asia Size -> PL vs ASia -> OR outcome)

| Asia Size | PL vs Asia | OR Outcome | London First Sweep | Win % | Median Time | Median Penetration | Range Expansion % |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Large** | Swept High | OR High (n=41) | **High** | **60.98%** | 12.0m | +24.87 pts | **95.1%** |
| **Large** | Swept High | OR Low (n=61) | **Low** | **62.30%** | 5.5m | -38.68 pts | **(Reversal Rejection)** |
| **Large** | Swept Low | OR High (n=43) | **High** | **72.09%** | 2.0m | +38.28 pts | **81.4%** |
| **Large** | Swept Low | OR Low (n=27) | **Low** | **77.78%** | 4.0m | -27.53 pts | **96.3%** |
| **Large** | No Sweep | OR High (n=8) | **High** | **62.50%** | 3.5m | +44.90 pts | **100.0%** |
| **Large** | No Sweep | OR Low (n=9) | **Low** | **55.56%** | >1m | -34.50 pts | **(Low sample)** |
| | | | | | | | |
| **Small** | Swept Low | OR High (n=134) | **High** | **58.96%** | 6.0m | +24.78 pts | **92.5%** |
| **Small** | Swept Low | OR Low (n=78) | **Low** | **51.28%** | 5.0m | -13.96 pts | **91.0%** |
| **Small** | Swept High | OR High (n=68) | **High** | **58.82%** | 3.0m | +17.43 pts | **89.7%** |
| **Small** | Swept High | OR Low (n=94) | **Low** | **61.70%** | 6.0m | -29.51 pts | **92.6%** |
| **Small** | No Sweep | OR High (n=10) | **High** | **80.00%** | 8.0m | +29.57 pts | **(High Conf)** |
| **Small** | No Sweep | OR Low (n=7) | **Low** | **57.14%** | 0.5m | -18.24 pts | **(Low sample)** |

> **Range Expansion Key**: This metric (from Image p8_0/p10_0) measures how often London expands the OR range.
> *   **Large Asia**: Expansion is near-guaranteed (95-100%) on strong setups.
> *   **Small Asia**: Still very high (90%+), but requires more patience.

### Trade Planning Implications:
1.  **Continuation is common.** If OR breaks High, London's first sweep often favors High.
2.  **Timing is quick.** Median time to first sweep is often **2–8 minutes**.
3.  **Penetration guides targets.** Typical moves extend **17–39 pts** beyond OR edge.

## [London Continuation Tree 3: Large Asia]
*Transcribed from Image p8_0.png*

**START: 03:00 London (ASIA ABOVE average > 70.9 pts)**
Determine OR (02:00–02:59) vs Pre-London outcome, then follow the branch.
*(n shown per branch; use extra caution when n<10)*

**1. OR SWEPT HIGH**
*   **PL SWEPT HIGH (n=41)**
    *   First sweep: **High 61.0%** | Low 39.0%
    *   Medians: +24.87 pts (12.0m) | -51.89 pts (8.5m)
    *   **Close if London sweeps High**: Bullish 73.3% ; if Low - Bearish 61.5%
    *   **Range expansion**: 95.1%
    *   **TRADE**: **Bias = Long**. Buy the retest/reclaim of OR High; TP ladder ~25–30 pts. If immediate rejection, be ready for reversal run to OR Low (faster & deeper).

*   **PL SWEPT LOW (n=43)**
    *   First sweep: **High 72.1%** | Low 25.6%
    *   Medians: +38.28 pts (2.0m) | -21.24 pts (15.0m)
    *   **Close if London sweeps High**: Bullish 75.7% ; if Low - Bearish 38.9%
    *   **Range expansion**: 81.4%
    *   **TRADE**: **Continuation UP** setup. Buy pullback to OR High after quick take. Faster upside (2m) suggests using a stop just under OR High; trail early.

**2. OR SWEPT LOW**
*   **PL SWEPT HIGH (n=61)**
    *   First sweep: High 37.7% | **Low 62.3%**
    *   Medians: +30.93 pts (14.0m) | -38.68 pts (5.5m)
    *   **Close if London sweeps High**: Bullish 80.0% ; if Low - Bearish 63.6%
    *   **Range expansion**: 93.4%
    *   **TRADE**: **Bias = Short**. Sell retest of OR Low; quicker move down (~5–6m). If contrary squeeze above OR Low, flip to reclaim-long only on solid close.

*   **PL SWEPT LOW (n=27)**
    *   First sweep: High 22.2% | **Low 77.8%**
    *   Medians: +51.97 pts (21.0m) | -27.53 pts (4.0m)
    *   **Close if London sweeps High**: Bullish 72.2% ; if Low - Bearish 57.1%
    *   **Range expansion**: 96.3%
    *   **TRADE**: **Down-continuation** is dominant. Prioritize short; TP1 ~15-20, TP2 ~25+. If price rips through OR Low and instantly reclaims, the squeeze upside can be large.

**3. OR SWEPT BOTH (n=11/12)**
*   **PL Swept High**: Two-sided potential. Initial fake moves are common.
*   **PL Swept Low**: Lean **short**. If High goes first, treat as liquidity grab.

**4. OR NO SWEEP (n=12/16)**
*   **PL Swept High**: First sweep High 58.3%. Range expansion 100%. **Wait** for first London breach.
*   **PL Swept Low**: Neutral bias. Take the first side that breaks & retests cleanly. Downside penetration is **deeper**, upside **more frequent** later.

**Takeaway (Asia large)**: Expect **directional continuation** from OR into London (first sweep aligns with the OR side 60–72% of the time). Median extensions after the sweep are **~25–40 pts**, with occasional deeper squeezes (50+ pts) when the move flips.

## [London Continuation Tree 4: Small Asia]
### [Detailed Logic Tree: Small Asia (≤ 70.9 pts)]
*Transcribed from Image p11_0.png*

**START: 02:00 Opening Range. First, what did Pre-London do vs Asia?**

**1) PL Swept Low (n=259) [Largest Bucket]**
*   **OR Swept High (n=134)**
    *   London First: **High 59.0%** (cont.) / Low 38.8%
    *   Median penetration: +24.8 pts (6m) / -26.2 pts (8m)
    *   **Cue**: Buy the OR-H reclaim/hold; this is the **most common path** on small-Asia days.
*   **OR Swept Low (n=78)**
    *   London First: Low 51.3% / High 48.7% (Balanced)
    *   Median penetration: +22.1 pts (10m) / -14.0 pts (5m)
    *   **Cue**: Tradable both ways; keep targets tighter on the downside.
*   **OR Swept Both (n=25)**
    *   London First: **High 68.0%**
    *   Median penetration: +19.8 pts (3m) / -36.9 pts (21m)
    *   **Cue**: Often a "fake down then up" day; fade the downside flush once reclaimed.
*   **OR No Sweep (n=22)**
    *   London First: **High 63.6%**
    *   Median penetration: +24.2 pts (17m) / -15.5 pts (5m)
    *   **Cue**: Wait for London breach; favor the first High breach.

**2) PL Swept High (n=189)**
*   **OR Swept Low (n=94)**
    *   London First: **Low 61.7%** (cont.) / High 38.3%
    *   Median penetration: +20.3 pts (9.5m) / -29.5 pts (6m)
    *   **Cue**: Short the OR-L retest; continuation down dominates.
*   **OR Swept High (n=68)**
    *   London First: **High 58.8%** / Low 39.7%
    *   Median penetration: +17.4 pts (3m) / -22.9 pts (18.5m)
    *   **Cue**: Upside can continue, but downside tails are long/slow → trail and be patient.
*   **OR Swept Both (n=11) [Low N]**
    *   London First: **High 63.6%**
    *   Median penetration: +11.0 pts (7m) / -26.9 pts (53.5m)
    *   **Cue**: If London sweeps Low later, bearish closes show 87.5% in sample → watch for late-session roll.
*   **OR No Sweep (n=16)**
    *   London First: High 50% / Low 50%
    *   Median penetration: +18.7 pts (5m) / -27.0 pts (11m)
    *   **Cue**: Two-sided; trade the first London break with modest targets.

**3) PL No Sweep of Asia (n=21)**
*   **OR Swept High (n=10)**
    *   London First: **High 80.0%** (Cont.) / Low 20.0%
    *   Median penetration: +29.6 pts (8m) / -4.1 pts (5m)
    *   **Cue**: Classic "thin Asia → trend up" day; prefer longs from OR-H.
*   **OR Swept Low (n=7)**
    *   London First: **Low 57.1%** (Cont.) / High 42.9%
    *   Median penetration: +21.2 pts (10m) / -18.2 pts (0.5m)
    *   **Cue**: Short is fine, but magnitude is smaller than up-days in this bucket.
*   **OR Swept Both (n=3) [Low N]**: Two-way; wait for London confirmation.
*   **OR No Sweep (n=1) [Low N]**: Expansion day; follow the first London breach.

**Small-Asia Takeaways**
*   With a **quiet Asia**, the market most often trends **with** the OR break (PL-Low → OR-High is **51.7%**, PL-High → OR-Low is **49.7%**).
*   London continuation after the OR side is common (often ~59–62% on the dominant branches).
*   Expect slightly **smaller medians** than big-Asia days: **~17–30 pts** from the breached OR edge, with quicker follow-through on continuation.


## Median Penetration vs Time-to-Sweep
### [Chart: Median Penetration Scatter Plot]
*(Visual Scatter Plot from p12_0.png)*

The comparison shows how penetration depth scales with volatility regime.
*   **Large Asia**: Faster, broader extensions. Center of mass around **2-5 mins** and **25-40 pts**.
*   **Small Asia**: Slower, tighter moves. Center of mass around **6-15 mins** and **15-25 pts**.

**Practical Application**
1.  **Same-Side Continuation after OR**: Enter on retest of the sweptOR edge (reclaim/fall). Continuation probability ≈ 70–86%. TP1 = ½ median; TP2 = 1x median.
2.  **Flip-and-Go after Fakeout**: If OR flips against PL, let London sweep and reclaim. Enter on retest.book ealier profits due to two-sided risk
3.  **Avoid Weak Contexts**: Tiny OR range + no retest = low probability. Flat tape after  Asia + no clear edge -> stand down or trade smaller size

## The Professional Edge
London is the expansion engine of the Nasdaq session map. Across 719 days, London expanded the OR range ≈ 90–100% of the time — and on OR no-sweep days, expansion was 100%. That means traders can plan for movement, not guesswork. The first London breach + retest remains the highest-quality entry in the entire model.

**Access the Data in Real Time**
You can explore and visualize these probabilities directly inside TradingView using the free indicator:
👉 NQ Asia–London Session Edge (Herman)
The NQ London Playbook shows how statistical structure can replace intuition in day trading.
*   London sweeps at least one OR edge on ≈ 80–90% of days.
*   Continuations occur ≈ 70–87% of the time.
*   Median penetrations range 17–40 pts.

Quantified probabilities. Real data. Mechanical logic for a discretionary world.
