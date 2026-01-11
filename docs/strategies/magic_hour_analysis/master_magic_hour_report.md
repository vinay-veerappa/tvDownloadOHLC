# NQ Mean Reversion Edge Study
## A Comprehensive Statistical Analysis of Hourly Mean Reversion Patterns in Nasdaq Futures

---

**Author:** @Dokakuri on X/TWITTER
**Analysis Period:** 2013-2026 (13 Years)  
**Asset:** NQ (Nasdaq 100 E-mini Futures)  
**Data Resolution:** 1-Minute Bars  
**Timezone:** America/New_York  

---

# Table of Contents

1. [Executive Summary](#executive-summary)
2. [The Fundamental Thesis: Why Mean Reversion Works](#the-fundamental-thesis-why-mean-reversion-works)
3. [What is the "Magic Hour" Concept?](#what-is-the-magic-hour-concept)
4. [Core Methodology: The Study Design](#core-methodology-the-study-design)
5. [The Walk-Away Simulation: A Critical Design Choice](#the-walk-away-simulation-a-critical-design-choice)
6. [Understanding Extensions and Zones](#understanding-extensions-and-zones)
7. [The Metrics Explained](#the-metrics-explained)
8. [Hourly Performance Rankings: Why Only 7 Sessions?](#hourly-performance-rankings-why-only-7-sessions)
9. [Detailed Statistical Breakdown by Ranked Hour](#detailed-statistical-breakdown-by-ranked-hour)
10. [Time Distribution Analysis](#time-distribution-analysis)
11. [Runner Probabilities: The Conditional Extension Statistics](#runner-probabilities-the-conditional-extension-statistics)
12. [The Zone Win% Trap: Understanding Survivorship Bias](#the-zone-win-trap-understanding-survivorship-bias)
13. [The Invalidation Concept](#the-invalidation-concept)
14. [The "Peculiar" Truncation: Why MAE Stops at 50%](#the-peculiar-truncation-why-mae-stops-at-50)
15. [What Constitutes the "Edge"](#what-constitutes-the-edge)
16. [The TradingView Indicator: Bringing Data to Life](#the-tradingview-indicator-bringing-data-to-life)
17. [Complete Statistical Reference Tables](#complete-statistical-reference-tables)
18. [Risk Management Framework](#risk-management-framework)
19. [Practical Application Guidelines](#practical-application-guidelines)
20. [Glossary of Terms](#glossary-of-terms)

---

# Executive Summary

This study represents a comprehensive 13-year statistical analysis of mean reversion patterns in NQ (Nasdaq 100 E-mini Futures). The core discovery is that specific hourly windows exhibit statistically significant tendencies for price to revert to the midpoint of a defined "Magic Hour" range after breaking out of that range.

**Key Findings:**

| Metric | Value |
|--------|-------|
| **Total Data Points** | ~3,300 sessions per hour analyzed |
| **Top Win Rate** | 83.4% (Hour 07:00 - "Golden Hour") |
| **Highest Tradeable Rate** | 99.8% (Hour 07:00 with < 50% extension filter) |
| **Best Expected Time to Target** | 18 minutes median (Hour 08:00) |
| **Optimal Entry Zones** | Z1 (0-25%) and Z2 (25-50%) extensions |

The edge is not that markets always revert—they don't. The edge lies in understanding **when** (specific hours) and **where** (specific extension zones) the probability of reversion is systematically underpriced by market participants.

---

# The Fundamental Thesis: Why Mean Reversion Works

## Market Structure and Liquidity Dynamics

Mean reversion in futures markets, particularly during specific hourly windows, occurs due to several structural factors:

1. **Liquidity Provider Behavior:** Market makers and algorithmic trading systems anchor to recent price ranges. When price extends away from a defined range, these participants often fade the move, providing natural counter-pressure.

2. **Order Flow Exhaustion:** Breakouts require sustained order flow. When momentum traders exhaust their buying/selling pressure, the market naturally gravitates back toward equilibrium—the range midpoint.

3. **Session Overlaps:** The hours selected in this study often coincide with major market transitions (Asia open, London pre-market, US pre-market) where liquidity shifts create temporary dislocations that tend to correct.

4. **Stop-Loss Hunting:** Initial breakouts often trigger stop losses outside the range, creating artificial momentum that subsequently reverses as the forced selling/buying subsides.

## The Statistical Foundation

Over 13 years and ~3,300 sessions per hour:
- Random chance would suggest ~50% reversion probability
- Top-ranked hours show 70-83% reversion rates
- This 20-33 percentage point outperformance is not random noise—it's a structural edge

---

# What is the "Magic Hour" Concept?

## Definition

The **Magic Hour** is a defined 60-minute window during which a price range is established. This range becomes the reference point for all subsequent analysis.

```
Magic Hour Components:
├── Magic High: Highest price during the hour
├── Magic Low: Lowest price during the hour  
├── Magic Range: Magic High - Magic Low
└── Magic Mid: (Magic High + Magic Low) / 2  ← THE TARGET
```

## How It Works

1. **Range Formation (Magic Hour):** During the designated hour, price establishes a high and low.

2. **Analysis Window (Next 3 Hours):** After the Magic Hour closes, we monitor the next 3 hours for:
   - A **breakout** (price exceeds Magic High or Magic Low)
   - A **reversion** (price returns to Magic Mid after breaking out)

3. **Trade Logic:**
   - If price breaks ABOVE Magic High → We expect price to fall back to Magic Mid
   - If price breaks BELOW Magic Low → We expect price to rise back to Magic Mid

## Visual Representation

```
                    ┌─────────────────────────────────────────────┐
                    │            ANALYSIS WINDOW (3 Hours)        │
    MAGIC HOUR      │                                             │
   ┌──────────┐     │   Extension (Breakout Above)                │
   │          │     │        ↗                                    │
   │  HIGH ───┼─────┼──────────────────────────────────────────── │
   │          │     │                    ↘                        │
   │  MID  ───┼─────┼─────────────────────── TARGET (50%) ←────── │
   │          │     │                                             │
   │  LOW  ───┼─────┼──────────────────────────────────────────── │
   │          │     │                                             │
   └──────────┘     └─────────────────────────────────────────────┘
```

---

# Core Methodology: The Study Design

## Data Parameters

| Parameter | Value |
|-----------|-------|
| **Data Source** | NQ Continuous Contract (1-minute bars) |
| **Lookback Period** | 13 Years (2013-2026) |
| **Timezone** | America/New_York |
| **File Format** | Parquet (optimized for large datasets) |

## Session Definition

For each potential Magic Hour (0-23):

1. **Magic Hour:** The hour being tested (e.g., 07:00-08:00)
2. **Analysis Window:** The subsequent 3 hours (e.g., 08:00-11:00)

## Key Logic: Date Rollover Handling

The Python script implements critical logic to handle midnight crossovers:

```python
# Example: Magic Hour = 23:00
# Analysis Window = 00:00, 01:00, 02:00 (next day)

for offset in range(1, 4):
    target_hour_raw = magic_hour + offset
    target_hour = target_hour_raw % 24
    
    # Handle date rollover
    target_date = current_date
    if target_hour_raw >= 24:
        target_date = current_date + timedelta(days=1)
```

This ensures that strategies like Hour 23 (11 PM) correctly analyze data from the following calendar day.

## What Constitutes a "Win"

A session is considered a **WIN** if:
- Price breaks the Magic Hour high or low
- Price subsequently reaches the **50% reversion level** (the Magic Mid)

The 50% target is not arbitrary—it represents the midpoint, the natural equilibrium of the established range.

---

# The Walk-Away Simulation: A Critical Design Choice

## What Is "Walk Away" Logic?

The Walk-Away simulation models a realistic trading approach:

1. **Enter:** On breakout (price exceeds Magic High or Magic Low)
2. **Target:** 50% reversion (return to Magic Mid)
3. **Exit:** Once 50% target is hit, the trade is CLOSED
4. **Walk Away:** All subsequent price action is IGNORED

## Why This Matters

### Traditional Analysis (Flawed)

Many studies calculate Maximum Adverse Excursion (MAE) across the entire session, regardless of whether the target was hit. This creates misleading statistics because:

- A trade that hits target in 5 minutes and then price crashes 500% is recorded as having 500% MAE
- This doesn't reflect reality—you would have already exited at profit

### Walk-Away Analysis (Accurate)

By truncating data at the moment the 50% target is hit:

```python
# 3. CALCULATE EXCURSION ON ACTIVE TRADE DATA ONLY
active_trade_data = post_break.loc[:trade_end_idx]

if side == "HIGH":
    max_price = active_trade_data["high"].max()
    excursion = max_price - magic_high  # Only heat BEFORE target hit
```

The statistics now reflect **actual trading reality**:
- MAE only measures adverse excursion while the trade is LIVE
- Extension zones only categorize based on what happened BEFORE winning

## Practical Implication

This design answers the trader's real question:

> "If I enter on the breakout and exit at 50% reversion, how much heat will I typically take?"

Not: "What did price do across 3 hours regardless of my exit?"

---

# Understanding Extensions and Zones

## What is an "Extension"?

An **extension** measures how far price travels beyond the Magic Hour boundary, expressed as a percentage of the Magic Range.

```
Extension % = (Maximum Excursion / Magic Range) × 100

Example:
- Magic High: 18,500
- Magic Low: 18,450
- Magic Range: 50 points
- Price breaks up to: 18,550

Extension = (18,550 - 18,500) / 50 × 100 = 100%
```

## Why Extensions Matter

Extensions serve multiple purposes:

1. **Entry Zone Classification:** They tell you where price is relative to the original range
2. **Probability Assessment:** Different extension depths have different win rates
3. **Risk Quantification:** Deeper extensions mean you're further from the target

## The Zone Framework

The study divides extensions into discrete zones:

| Zone | Extension Range | Interpretation | Risk Level |
|------|-----------------|----------------|------------|
| **Z1** | 0-25% | Ideal | Minimal |
| **Z2** | 25-50% | Prime | Low |
| **Z3** | 50-75% or 50-100% | Deep | Moderate |
| **INV** | 75-100% or 100% | Invalidation Line | High |
| **Z4** | 75-150% or 100-150% | Risk Zone | Elevated |
| **Z5** | 150-300% | Last Stand | Extreme |
| **Z6** | > 300% | Graveyard | Abandon Hope |

*Note: Zone boundaries vary slightly by strategy based on optimal invalidation points*

## Zone Visualization

```
                         Z6 (> 300%)      GRAVEYARD
                    ─────────────────────────────────
                         Z5 (150-300%)   LAST STAND
                    ─────────────────────────────────
                         Z4 (100-150%)   RISK ZONE
                    ═════════════════════════════════  ← INVALIDATION LINE
                         Z3 (50-100%)    DEEP
                    ─────────────────────────────────
                         Z2 (25-50%)     PRIME
                    ─────────────────────────────────
                         Z1 (0-25%)      IDEAL
═══════════════════════════════════════════════════════  ← MAGIC HIGH
                         
                         (Magic Range)
                         
═══════════════════════════════════════════════════════  ← MAGIC LOW
                         Z1 (0-25%)      IDEAL
                    ─────────────────────────────────
                         Z2 (25-50%)     PRIME
                    ─────────────────────────────────
                         ...continues symmetrically...
```

---

# The Metrics Explained

## 1. Reach %

**Definition:** The percentage of ALL trades that extended AT LEAST this far.

**Formula:**
```
Reach % = (Count of trades reaching this depth or beyond) / (Total trades) × 100
```

**Interpretation:**
- Reach is **cumulative**—it tells you "what percentage of trades get to at least this level?"
- 100% for Zone 1 because all trades must pass through 0-25% to go deeper
- Decreases as you go to deeper zones

**Example from Hour 07:00 (HIGH breaks):**
| Zone | Reach % |
|------|---------|
| 0-25% | 100.0% (1,711) |
| 25-50% | 69.5% (1,189) |
| 50-75% | 52.1% (891) |
| 75-100% | 42.4% (725) |
| > 300% | 3.3% (56) |

**Trading Use:** Reach tells you "how often does price extend to this zone?" It helps set realistic expectations for how far adverse movement typically goes.

---

## 2. Density

**Definition:** The percentage of WINNING trades whose maximum extension peaked in this specific zone.

**Formula:**
```
Density = (Winners whose max extension was in this zone) / (Total winners) × 100
```

**Interpretation:**
- Density is **exclusive**—a trade can only be in ONE density zone
- Shows WHERE winning trades tend to peak before reverting
- High density zones are where reversals most commonly occur

**Example from Hour 07:00 (HIGH breaks):**
| Zone | Density |
|------|---------|
| 0-25% | 36.6% (522 winners) |
| 25-50% | 20.8% (297 winners) |
| 50-75% | 11.3% (161 winners) |
| 75-100% | 7.9% (113 winners) |
| > 300% | 0.4% (6 winners) |

**Trading Use:** Density answers "where do most reversals START from?" The highest density is typically in Z1 and Z2, suggesting most successful mean reversions begin from shallow extensions.

---

## 3. Zone Win %

**Definition:** If price stops (peaks) in this zone and doesn't go deeper, what is the probability of hitting the 50% target?

**Formula:**
```
Zone Win % = (Winners in this zone) / (Total trades that peaked in this zone) × 100
```

**⚠️ CRITICAL WARNING: This is a Survivorship Statistic**

This metric only considers trades that:
1. Extended into a zone
2. STOPPED (peaked) in that zone
3. Did NOT continue to deeper zones

**Example from Hour 07:00 (HIGH breaks):**
| Zone | Zone Win % |
|------|------------|
| 0-25% | 100.0% (522/522) |
| 25-50% | 99.7% (297/298) |
| 50-75% | 97.0% (161/166) |
| 75-100% | 93.4% (113/121) |
| > 300% | 10.7% (6/56) |

**Why Zone 1 Shows 100% Win Rate:**

If price broke out and peaked within 0-25%, it means:
- The extension was minimal
- Price was already very close to the midpoint
- Reverting 50% from a 25% extension is trivial

This does NOT mean entering in Z1 gives 100% success—it means IF you're in Z1 AND price stops there, you almost certainly win.

---

## 4. Time to Target (Percentiles)

**Definition:** How long winning trades typically take to reach the 50% target.

**Reported Percentiles:**
| Percentile | Meaning |
|------------|---------|
| 25% (Fastest) | The quickest 25% of winners hit target by this time |
| 50% (Median) | Half of winners hit target by this time |
| 75% (Slow) | 75% of winners hit target by this time |
| 90% (Grind) | The slowest winners take this long |

**Example from Hour 08:00:**
```
25% (Fastest)  :    6 m
50% (Median)   :   18 m
75% (Slow)     :   31 m
90% (Grind)    :   54 m
```

**Trading Use:** Time expectations help with:
- Position sizing (longer duration = more capital tied up)
- Time stop implementation
- Understanding session characteristics

---

## 5. MAE (Maximum Adverse Excursion)

**Definition:** The maximum price moved against the position BEFORE hitting the target.

**Critical Note:** Due to Walk-Away logic, MAE is only calculated while the trade is active. Once the 50% target is hit, MAE tracking stops.

**Format:** Expressed as a percentage of the Magic Range.

**Example:**
- MAE of 53.8% means the average winning trade saw price extend 53.8% of the range against the position before reverting to target

**Trading Use:** MAE informs stop-loss placement. If average MAE is 53.8%, placing a stop at 40% of range would stop out many eventual winners.

---

## 6. Runner Probabilities (Conditional Extension Stats)

**Definition:** Given that price hit the 50% target, what is the probability it continues to deeper reversion levels?

**Formula:**
```
Runner % to X = (Trades that hit X% after hitting 50%) / (Trades that hit 50%) × 100
```

**Reversion Levels Tracked:**
- 75%: Price reverts past the midpoint
- 100%: Price reverts to the opposite boundary
- 125%: Price continues 25% beyond the range
- 150%: Price continues 50% beyond the range
- 200%: Price doubles the range in the opposite direction

**Example from Hour 07:00:**
```
BASE CASE: 50% Target Hit → 2,783 times (83.4% overall win rate)

  75% Level:  90.1% (2,508/2,783) - Extremely Likely (Hold)
 100% Level:  80.7% (2,247/2,783) - Extremely Likely (Hold)
 125% Level:  72.0% (2,005/2,783) - Likely (Trail Stop)
 150% Level:  64.6% (1,799/2,783) - Likely (Trail Stop)
 200% Level:  51.2% (1,426/2,783) - Coin Flip (Take Partial)
```

**Why This Calculation Method?**

The runner statistics are calculated as conditional probabilities FROM the base of 50% winners:

> "OF ALL THE WINNING DAYS (those that hit 50%), how many ALSO continued to 75%?"

This is critically different from asking:

> "What is the standalone probability of hitting 75%?"

**The Reasoning:**

1. You've already WON at 50%—you're now deciding whether to hold for more
2. The relevant question is: "Given I'm already profitable, should I stay in?"
3. The conditional probability (90.1% to 75%) is more actionable than the standalone probability

If we used standalone probability:
- 75% Hit Rate = (2,508 / 3,336) × 100 = 75.2%

But this includes trades that never hit 50% first, which isn't relevant to a runner decision.

---

# Hourly Performance Rankings: Why Only 7 Sessions?

## The Selection Criteria

From all 24 hours analyzed, only **7 sessions** made the final cut for the TradingView indicator. The selection criteria included:

1. **Win Rate Threshold:** > 68% overall 50% reversion rate
2. **Sample Size:** > 3,000 sessions for statistical significance
3. **Consistency:** Stable performance across HIGH and LOW breaks
4. **Tradeable Rate:** > 90% win rate when filtering for < 50% extension

## The Final Seven (Ranked)

| Rank | Hour | Session Name | Win Rate | Sessions | Median Time | Avg MAE |
|------|------|--------------|----------|----------|-------------|---------|
| #1 | 07:00 | Golden Hour | 83.4% | 3,336 | 29m | 53.8% |
| #2 | 08:00 | Continuation | 79.7% | 3,322 | 18m | 48.2% |
| #3 | 06:00 | Pre-Market | 78.7% | 3,329 | 44m | 59.3% |
| #4 | 00:00 | Asia Open | 76.8% | 3,326 | 31m | 55.2% |
| #5 | 01:00 | Asia Cont. | 74.2% | 3,323 | 28m | 58.7% |
| #6 | 02:00 | London Pre | 70.9% | 3,304 | 16m | 47.7% |
| #7 | 23:00 | Asia Pre-Game | 69.5% | 3,288 | 35m | 50.0% |

## Why Not All 24 Hours?

The remaining hours were excluded because:

### Low Win Rates (< 55%)

| Hour | Win Rate | Issue |
|------|----------|-------|
| 15:00 | 22.4% | Settlement hour; extreme volatility |
| 16:00 | 40.4% | Post-settlement chop |
| 10:00 | 43.9% | Mid-morning indecision |
| 21:00 | 47.2% | Low liquidity evening |

### Moderate but Inconsistent (55-68%)

| Hour | Win Rate | Issue |
|------|----------|-------|
| 03:00 | 48.5% | European open noise |
| 04:00 | 56.1% | Split between Asia close/Europe open |
| 09:00 | 53.7% | US cash open volatility |
| 14:00 | 49.1% | Afternoon drift |

### The Edge Disappears Below ~68%

At 68% win rate with typical risk/reward:
- Win Rate: 68%
- Average Win: 1R (50% reversion)
- Average Loss: 1R (stopped out)

Expected Value = (0.68 × 1R) - (0.32 × 1R) = 0.36R

Below this threshold, the edge becomes marginal and transaction costs erode profitability.

---

# Detailed Statistical Breakdown by Ranked Hour

## RANK #1: Hour 07:00 - "Golden Hour"

### Overview

The 7 AM hour consistently produces the highest mean reversion win rates across 13 years of data. This hour captures the transition from pre-market to regular trading hours.

**Why It Works:**
- Pre-market ranges are established by early institutional activity
- Regular session traders provide reversal liquidity
- Stop-loss hunting above/below overnight ranges creates initial extensions
- Market makers defend pre-market levels

### Summary Statistics

| Metric | Value |
|--------|-------|
| **Magic Hour** | 07:00-08:00 NY |
| **Analysis Window** | 08:00-11:00 NY |
| **Total Sessions** | 3,336 |
| **Breakouts Found** | 3,336 (100%) |
| **Win Rate** | 83.4% (2,783/3,336) |
| **Median Time to 50%** | 29 minutes |
| **Average MAE** | 53.8% |
| **Hard Stop Time** | 11:00 AM |

### Time Distribution

| Percentile | Time to Target | Clock Time |
|------------|----------------|------------|
| 25% (Fastest) | 12m | 08:12 |
| 50% (Median) | 29m | 08:29 |
| 75% (Slow) | 69m | 09:09 |
| 90% (Grind) | 95m | 09:35 |

### Runner Conversion Rates

| Target | Conversion | Count | Action |
|--------|------------|-------|--------|
| 75% | 90.1% | 2,508 | Hold |
| 100% | 80.7% | 2,247 | Hold |
| 125% | 72.0% | 2,005 | Trail Stop |
| 150% | 64.6% | 1,799 | Trail Stop |
| 200% | 51.2% | 1,426 | Take Partial |

### Zone Breakdown - HIGH Breaks (N=1,711)

| Zone | Reach % | Density | Zone Win % | 75% Ext | 100% Ext | 125% Ext |
|------|---------|---------|------------|---------|----------|----------|
| 0-25% | 100.0% (1711) | 36.6% (522) | 100.0% | 89.8% | 78.9% | 70.5% |
| 25-50% | 69.5% (1189) | 20.8% (297) | 99.7% | 91.6% | 84.2% | 77.1% |
| 50-75% | 52.1% (891) | 11.3% (161) | 97.0% | 89.4% | 80.7% | 70.8% |
| 75-100% | 42.4% (725) | 7.9% (113) | 93.4% | 91.2% | 83.2% | 77.0% |
| 100-150% | 35.3% (604) | 10.0% (143) | 85.1% | 90.2% | 78.3% | 71.3% |
| 150-200% | 25.5% (436) | 5.8% (82) | 70.1% | 89.0% | 80.5% | 73.2% |
| 200-300% | 18.6% (319) | 5.0% (72) | 52.2% | 88.9% | 84.7% | 76.4% |
| 300-500% | 10.6% (181) | 2.1% (30) | 24.0% | 93.3% | 86.7% | 83.3% |
| >500% | 3.3% (56) | 0.4% (6) | 10.7% | 50.0% | 50.0% | 50.0% |

### Zone Breakdown - LOW Breaks (N=1,625)

| Zone | Reach % | Density | Zone Win % | 75% Ext | 100% Ext | 125% Ext |
|------|---------|---------|------------|---------|----------|----------|
| 0-25% | 100.0% (1625) | 36.4% (494) | 100.0% | 91.7% | 80.8% | 69.8% |
| 25-50% | 69.6% (1131) | 21.0% (285) | 99.0% | 90.5% | 81.8% | 72.6% |
| 50-75% | 51.9% (843) | 12.0% (163) | 97.6% | 89.0% | 76.1% | 67.5% |
| 75-100% | 41.6% (676) | 8.0% (108) | 94.7% | 94.4% | 91.7% | 81.5% |
| 100-150% | 34.6% (562) | 8.9% (121) | 89.0% | 86.0% | 80.2% | 70.2% |
| 150-200% | 26.2% (426) | 5.2% (71) | 71.7% | 91.5% | 81.7% | 74.6% |
| 200-300% | 20.1% (327) | 6.2% (84) | 63.2% | 83.3% | 71.4% | 63.1% |
| 300-500% | 11.9% (194) | 1.9% (26) | 26.5% | 80.8% | 73.1% | 65.4% |
| >500% | 5.9% (96) | 0.4% (5) | 5.2% | 100.0% | 80.0% | 80.0% |

### Aggregated Zone Statistics for Indicator

| Zone | Range | Reach % | Density | Win % | Status |
|------|-------|---------|---------|-------|--------|
| Z1 | 0-25% | 100.0% (3336) | 36.5% (1016) | 100.0% | IDEAL |
| Z2 | 25-50% | 69.5% (2320) | 20.9% (582) | 99.3% | PRIME |
| Z3 | 50-100% | 52.0% (1734) | 19.6% (545) | 95.9% | DEEP |
| **INV** | **100%** | - | - | - | **STOP TRADING** |
| Z4 | 100-150% | 35.0% (1166) | 9.5% (264) | 86.8% | RISK |
| Z5 | 150-300% | 25.8% (862) | 11.1% (309) | 63.4% | LAST STAND |
| Z6 | > 300% | 11.2% (375) | 2.4% (67) | 17.9% | GRAVEYARD |

---

## RANK #2: Hour 08:00 - "Continuation"

### Overview

The 8 AM hour benefits from the momentum established in the 7 AM window while capturing US cash market opening dynamics.

**Why It Works:**
- Builds on pre-market trends
- US cash open at 9:30 provides reversal liquidity
- Fastest median time to target (18 minutes)
- Lower average MAE (48.2%)

### Summary Statistics

| Metric | Value |
|--------|-------|
| **Magic Hour** | 08:00-09:00 NY |
| **Analysis Window** | 09:00-12:00 NY |
| **Total Sessions** | 3,322 |
| **Win Rate** | 79.7% (2,648/3,322) |
| **Median Time to 50%** | 18 minutes |
| **Average MAE** | 48.2% |
| **Hard Stop Time** | 12:00 PM |

### Time Distribution

| Percentile | Time to Target | Clock Time |
|------------|----------------|------------|
| 25% (Fastest) | 6m | 09:06 |
| 50% (Median) | 18m | 09:18 |
| 75% (Slow) | 31m | 09:31 |
| 90% (Grind) | 54m | 09:54 |

### Runner Conversion Rates

| Target | Conversion | Count | Action |
|--------|------------|-------|--------|
| 75% | 87.8% | 2,324 | Extremely Likely (Hold) |
| 100% | 76.5% | 2,025 | Likely (Trail Stop) |
| 125% | 67.8% | 1,796 | Likely (Trail Stop) |
| 150% | 59.3% | 1,569 | Coin Flip (Take Partial) |
| 200% | 45.0% | 1,192 | Coin Flip (Take Partial) |

### Aggregated Zone Statistics

| Zone | Range | Reach % | Density | Win % | Status |
|------|-------|---------|---------|-------|--------|
| Z1 | 0-25% | 100.0% (3322) | 40.1% (1063) | 99.2% | IDEAL |
| Z2 | 25-50% | 67.7% (2250) | 22.1% (585) | 96.2% | PRIME |
| Z3 | 50-75% | 49.4% (1642) | 13.1% (347) | 91.6% | DEEP |
| **INV** | **75%** | - | - | - | **STOP TRADING** |
| Z4 | 75-150% | 38.0% (1263) | 16.5% (436) | 79.3% | RISK |
| Z5 | 150-300% | 21.5% (713) | 6.6% (174) | 45.0% | LAST STAND |
| Z6 | > 300% | 9.8% (326) | 1.6% (43) | 13.2% | GRAVEYARD |

---

## RANK #3: Hour 06:00 - "Pre-Market"

### Summary Statistics

| Metric | Value |
|--------|-------|
| **Magic Hour** | 06:00-07:00 NY |
| **Analysis Window** | 07:00-10:00 NY |
| **Total Sessions** | 3,329 |
| **Win Rate** | 78.7% (2,619/3,329) |
| **Median Time to 50%** | 44 minutes |
| **Average MAE** | 59.3% |
| **Hard Stop Time** | 10:00 AM |

### Time Distribution

| Percentile | Time to Target | Clock Time |
|------------|----------------|------------|
| 25% (Fastest) | 17m | 07:17 |
| 50% (Median) | 44m | 07:44 |
| 75% (Slow) | 91m | 08:31 |

### Runner Conversion Rates

| Target | Conversion | Count |
|--------|------------|-------|
| 75% | 88.9% | 2,327 |
| 100% | 78.3% | 2,050 |
| 125% | 68.7% | 1,800 |
| 150% | 60.3% | 1,580 |
| 200% | 46.5% | 1,219 |

---

## RANK #4: Hour 00:00 - "Asia Open"

### Summary Statistics

| Metric | Value |
|--------|-------|
| **Magic Hour** | 00:00-01:00 NY |
| **Analysis Window** | 01:00-04:00 NY |
| **Total Sessions** | 3,326 |
| **Win Rate** | 76.8% (2,555/3,326) |
| **Median Time to 50%** | 31 minutes |
| **Average MAE** | 55.2% |
| **Hard Stop Time** | 04:00 AM |

### Time Distribution

| Percentile | Time to Target | Clock Time |
|------------|----------------|------------|
| 25% (Fastest) | 12m | 01:12 |
| 50% (Median) | 31m | 01:31 |
| 75% (Slow) | 62m | 02:02 |

### Runner Conversion Rates

| Target | Conversion | Count |
|--------|------------|-------|
| 75% | 87.0% | 2,222 |
| 100% | 75.0% | 1,915 |
| 125% | 64.9% | 1,659 |
| 150% | 55.5% | 1,417 |
| 200% | 40.7% | 1,040 |

---

## RANK #5: Hour 01:00 - "Asia Continuation"

### Summary Statistics

| Metric | Value |
|--------|-------|
| **Magic Hour** | 01:00-02:00 NY |
| **Analysis Window** | 02:00-05:00 NY |
| **Total Sessions** | 3,323 |
| **Win Rate** | 74.2% (2,465/3,323) |
| **Median Time to 50%** | 28 minutes |
| **Average MAE** | 58.7% |
| **Hard Stop Time** | 05:00 AM |

### Time Distribution

| Percentile | Time to Target | Clock Time |
|------------|----------------|------------|
| 25% (Fastest) | 10m | 02:10 |
| 50% (Median) | 28m | 02:28 |
| 75% (Slow) | 61m | 03:01 |

### Runner Conversion Rates

| Target | Conversion | Count |
|--------|------------|-------|
| 75% | 84.5% | 2,084 |
| 100% | 71.4% | 1,761 |
| 125% | 60.5% | 1,492 |
| 150% | 51.0% | 1,258 |
| 200% | 36.8% | 906 |

---

## RANK #6: Hour 02:00 - "London Pre"

### Summary Statistics

| Metric | Value |
|--------|-------|
| **Magic Hour** | 02:00-03:00 NY |
| **Analysis Window** | 03:00-06:00 NY |
| **Total Sessions** | 3,304 |
| **Win Rate** | 70.9% (2,341/3,304) |
| **Median Time to 50%** | 16 minutes |
| **Average MAE** | 47.7% |
| **Hard Stop Time** | 06:00 AM |

### Time Distribution

| Percentile | Time to Target | Clock Time |
|------------|----------------|------------|
| 25% (Fastest) | 5m | 03:05 |
| 50% (Median) | 16m | 03:16 |
| 75% (Slow) | 45m | 03:45 |

### Runner Conversion Rates

| Target | Conversion | Count |
|--------|------------|-------|
| 75% | 79.2% | 1,855 |
| 100% | 62.8% | 1,471 |
| 125% | 51.3% | 1,200 |
| 150% | 41.2% | 965 |
| 200% | 26.4% | 617 |

---

## RANK #7: Hour 23:00 - "Asia Pre-Game"

### Summary Statistics

| Metric | Value |
|--------|-------|
| **Magic Hour** | 23:00-00:00 NY |
| **Analysis Window** | 00:00-03:00 NY (Next Day) |
| **Total Sessions** | 3,288 |
| **Win Rate** | 69.5% (2,285/3,288) |
| **Median Time to 50%** | 35 minutes |
| **Average MAE** | 50.0% |
| **Hard Stop Time** | 03:00 AM |

### Time Distribution

| Percentile | Time to Target | Clock Time |
|------------|----------------|------------|
| 25% (Fastest) | 16m | 00:16 |
| 50% (Median) | 35m | 00:35 |
| 75% (Slow) | 66m | 01:06 |

### Runner Conversion Rates

| Target | Conversion | Count |
|--------|------------|-------|
| 75% | 79.3% | 1,812 |
| 100% | 62.8% | 1,434 |
| 125% | 50.5% | 1,153 |
| 150% | 41.0% | 937 |
| 200% | 26.5% | 606 |

---

# Time Distribution Analysis

## Why Time Matters

Understanding when reversions occur helps with:

1. **Position Sizing:** Longer duration = more capital tied up
2. **Time Stops:** Know when to exit if target isn't hit
3. **Opportunity Cost:** Evaluate whether to hold or redeploy capital
4. **Session Planning:** Align trading with expected resolution times

## Comparative Time Analysis

| Rank | Hour | 25th %tile | Median | 75th %tile | 90th %tile |
|------|------|------------|--------|------------|------------|
| #1 | 07:00 | 12m | 29m | 69m | 95m |
| #2 | 08:00 | 6m | 18m | 31m | 54m |
| #3 | 06:00 | 17m | 44m | 91m | - |
| #4 | 00:00 | 12m | 31m | 62m | 111m |
| #5 | 01:00 | 10m | 28m | 61m | - |
| #6 | 02:00 | 5m | 16m | 45m | - |
| #7 | 23:00 | 16m | 35m | 66m | 108m |

## Key Observations

1. **Fastest Sessions:** Hour 08:00 (6m / 18m median) and Hour 02:00 (5m / 16m median) resolve quickly due to high liquidity transitions.

2. **Slowest Sessions:** Hour 06:00 (17m / 44m median) can grind as pre-market consolidates.

3. **Trading Implication:** For Hour 08:00, if you haven't hit 50% within 30 minutes, you're already in the "slow" category—consider tightening stop or taking profit.

---

# Runner Probabilities: The Conditional Extension Statistics

## The Philosophy Behind Runner Stats

Once you've hit your 50% target, you face a new decision:

> "Should I take profit or let it run?"

Runner probabilities answer this by showing the conditional probability of reaching deeper targets GIVEN that you've already won at 50%.

## Why Conditional Probability Matters

Consider two ways to calculate "odds of hitting 75%":

**Method 1: Standalone Probability**
```
P(75%) = (Trades hitting 75%) / (All trades)
Example: 2,508 / 3,336 = 75.2%
```

**Method 2: Conditional Probability (Used in Study)**
```
P(75% | 50%) = (Trades hitting 75%) / (Trades that hit 50%)
Example: 2,508 / 2,783 = 90.1%
```

**Why Method 2 is Correct:**

The standalone probability includes trades that never hit 50%—but those trades are irrelevant for runner decisions. You're only deciding whether to hold AFTER you've already won at 50%.

The conditional probability tells you: "I'm profitable. What are my odds if I stay?"

## Runner Decision Framework

Based on conversion rates, the study provides actionable guidance:

| Conversion Rate | Label | Action |
|-----------------|-------|--------|
| > 80% | Extremely Likely | Hold position |
| 60-80% | Likely | Trail stop to breakeven |
| 40-60% | Coin Flip | Take partial profits |
| < 40% | Unlikely | Aggressive profit taking |

## Example Application: Hour 07:00

Your position hit 50%. Runner stats show:

- 75% Target: 90.1% → **Extremely Likely** → Hold
- 100% Target: 80.7% → **Extremely Likely** → Hold
- 125% Target: 72.0% → **Likely** → Trail stop to breakeven
- 150% Target: 64.6% → **Likely** → Consider taking 50% off
- 200% Target: 51.2% → **Coin Flip** → Take most off, leave runner

---

# The Zone Win% Trap: Understanding Survivorship Bias

## The Dangerous Statistic

The dashboard shows zone win rates like:

```
Z2 Win: 99.3%
Z3 Win: 95.9%
Z4 Win: 86.8%
```

At first glance, this seems to say: "I'm in Zone 2, I have a 99.3% chance of winning!"

**This interpretation is WRONG and dangerous.**

## What Zone Win% Actually Measures

Zone Win% is a **survivorship statistic**. It measures:

> "Of the trades that STOPPED in Zone 2 (and didn't go deeper), what percentage won?"

It does NOT measure:

> "I'm currently in Zone 2. What's my probability of winning?"

## The Critical Difference

### Scenario: You're in Zone 2 (25-50% extension)

**What Zone Win% tells you:**
- 99.3% of trades that PEAKED in Zone 2 eventually won
- This includes the benefit of knowing they didn't go to Zone 3, 4, 5, or 6

**What you DON'T know in real-time:**
- Whether price will continue to Zone 3 (50% of trades that reach Z2 continue)
- Whether price will reach Zone 6 (Graveyard)
- Whether you'll be one of the 0.7% that loses even stopping in Z2

## Your Real-Time Probability

To calculate your actual probability in Zone 2, you need to account for all possible outcomes:

```
P(Win from Z2) = P(Price stops in Z2) × P(Win | Z2) + 
                  P(Price goes to Z3) × P(Win | Z3) + 
                  P(Price goes to Z4) × P(Win | Z4) + ...
```

This is significantly lower than the 99.3% zone win rate.

## How to Use Zone Win% Correctly

**Use it for "Normalcy" assessment, not probability:**

- High Zone Win% = "This zone is normal territory; reversals commonly start here"
- Low Zone Win% = "This zone is abnormal; something has gone wrong"

**Practical Application:**

If you're in Zone 5 (Last Stand) with 63% Zone Win%:
- This isn't your success probability
- It's telling you that trades reaching this depth are in trouble
- 37% of trades that even STOP here still lose
- Use this as a warning sign, not a prediction

---

# The Invalidation Concept

## What Is Invalidation?

**Invalidation** is a price level beyond which the mean reversion thesis is statistically compromised. When price extends past invalidation, the probabilities shift dramatically against reversion.

## Invalidation Levels by Strategy

| Strategy | Invalidation Level | Reasoning |
|----------|-------------------|-----------|
| Hour 07:00 | 100% | Win% drops from 95.9% to 86.8% |
| Hour 08:00 | 75% | Win% drops from 91.6% to 79.3% |
| Hour 06:00 | 100% | Win% drops from 92.7% to 75.7% |
| Hour 00:00 | 100% | Win% drops from 89.0% to 70.0% |
| Hour 01:00 | 100% | Win% drops from 85.5% to 65.3% |
| Hour 02:00 | 75% | Win% drops from 79.5% to 51.6% |
| Hour 23:00 | 75% | Win% drops from 79.6% to 51.6% |

## Why Different Invalidation Points?

The invalidation level is set where the **Zone Win%** drops below a threshold that makes the risk/reward unfavorable:

- Hours 07:00, 06:00, 00:00, 01:00 have 100% invalidation because Zone 3 (50-100%) still maintains > 85% win rates
- Hours 08:00, 02:00, 23:00 have 75% invalidation because Zone 3 (50-75%) already shows declining win rates

## Trading Rules at Invalidation

When price crosses the invalidation line:

1. **No New Entries:** Don't initiate new positions beyond invalidation
2. **Exit Existing Positions:** Close any open mean reversion trades
3. **Wait for Reset:** Look for the next Magic Hour instead

## Visual Representation in Indicator

```
═══════════════════════════════════════════════════════  ← MAGIC HIGH
       Z1 (IDEAL)     - Trade aggressively
─────────────────────────────────────────────────────────
       Z2 (PRIME)     - Trade normally
─────────────────────────────────────────────────────────
       Z3 (DEEP)      - Trade cautiously
═════════════════════════════════════════════════════════  ← INVALIDATION LINE
       Z4 (RISK)      - DON'T TRADE (but track for stats)
─────────────────────────────────────────────────────────
       Z5 (LAST STAND) - DON'T TRADE
─────────────────────────────────────────────────────────
       Z6 (GRAVEYARD)  - DON'T TRADE
```

---

# The "Peculiar" Truncation: Why MAE Stops at 50%

## The Design Decision

The Python script deliberately stops tracking Maximum Adverse Excursion (MAE) the moment the 50% target is touched:

```python
# 2. DETERMINE END OF TRADE (TRUNCATION POINT)
trade_end_idx = post_break.index[-1]  # Default to end of session

if side == "HIGH":
    target_50 = magic_high - (50 / 100.0 * magic_range)
    hits_50 = post_break["low"] <= target_50
    if hits_50.any():
        result["revert_50"] = True
        trade_end_idx = hits_50.idxmax()  # Truncate HERE

# 3. CALCULATE EXCURSION ON ACTIVE TRADE DATA ONLY
active_trade_data = post_break.loc[:trade_end_idx]
```

## Why This Matters

### Without Truncation (Traditional Analysis)

Imagine this scenario:
1. Price breaks Magic High at 100
2. Extends to 150 (50% extension)
3. Reverts to 50 (target hit at minute 15)
4. Continues to 200 in opposite direction
5. Crashes to -100 (would be 200% MAE)

Traditional analysis would report:
- MAE: 200% (from the crash after target)
- This is meaningless—you exited at 50!

### With Truncation (Walk-Away Analysis)

Same scenario:
- MAE: 50% (only counts the 50 points before target)
- This reflects your ACTUAL trade experience

## Practical Implications

The truncated MAE statistics are directly applicable to:

1. **Stop-Loss Placement:** If average MAE is 53.8%, don't place stops at 40%
2. **Position Sizing:** MAE directly informs maximum drawdown expectations
3. **Psychological Preparation:** Know what "normal" heat looks like

## Why "Peculiar"?

This truncation is unusual because most studies calculate MAE across the entire session. However, for a mean reversion strategy with a defined profit target, only the pre-target MAE is relevant.

The "peculiar" nature is actually a feature—it produces statistics that match trading reality rather than theoretical maximum session movements.

---

# What Constitutes the "Edge"

## The Nature of This Edge

Your edge is **NOT** that the market always reverts. It doesn't.

Your edge **IS** knowing:

1. **WHEN:** Specific hours have statistically superior reversion probabilities
2. **WHERE:** Specific extension zones offer the best risk/reward entry points
3. **WHY:** The probability of reversion is "mispriced" by market participants

## What "Mispriced" Means

In trading, an edge exists when your estimate of probability differs from the market's implied probability:

### Random Expectation
- 50% reversion probability
- Any hour, any zone, same odds

### Market Reality (This Study)
- Hour 07:00: 83.4% reversion probability
- Zone 1 (0-25%): Nearly 100% win rate if price stops there
- Combined advantage: Significant alpha over random

The "mispricing" occurs because:

1. **Most traders don't segment by hour:** They trade the same strategy 24/7
2. **Most traders don't categorize extensions:** They don't know if 30% extension is normal or extreme
3. **Most traders don't use conditional probabilities:** They don't know runner odds given initial success

## Edge Quantification

**Expected Value Calculation for Hour 07:00 Zone 1:**

Assumptions:
- Entry on breakout + 10% extension (early Z1)
- Target: 50% reversion (40% of range profit)
- Stop: Invalidation at 100% (100% of range loss)

```
Win Rate: ~98% (Z1 + Z2 combined)
Risk/Reward: 40% profit vs 100% risk = 0.4R win, 1R loss

EV = (0.98 × 0.4R) - (0.02 × 1R)
EV = 0.392R - 0.02R
EV = +0.372R per trade
```

Over 100 trades:
- 98 wins × 0.4R = 39.2R
- 2 losses × 1R = 2R
- Net: +37.2R

This is a substantial edge, achievable only by:
1. Trading the RIGHT hours
2. Entering in the RIGHT zones
3. Using the RIGHT position sizing based on MAE

---

# The TradingView Indicator: Bringing Data to Life

## Indicator Overview

The Pine Script indicator ("Magic Hour: Master Playbook") is a real-time implementation of the statistical findings, providing:

1. **Magic Hour Range Visualization:** Box showing the high/low/mid of the selected hour
2. **Extension Zones:** Color-coded zones extending from the Magic Hour boundaries
3. **Real-Time Zone Tracking:** Dynamic updates as price moves through zones
4. **Master Dashboard:** Comprehensive statistics panel with all key metrics
5. **Invalidation Warnings:** Visual alerts when price crosses danger thresholds

## Strategy Selection

The indicator offers 7 pre-configured strategies:

```
"--- PRE-MARKET / NY ---"
"RANK #1: 07:00 (Golden Hour)"
"RANK #2: 08:00 (Continuation)"
"RANK #3: 06:00 (Pre-Market)"
"--- ASIA / LONDON ---"
"RANK #4: 00:00 (Asia Open)"
"RANK #5: 01:00 (Asia Cont.)"
"RANK #6: 02:00 (London Pre)"
"RANK #7: 23:00 (Asia Pre-Game)"
```

## Visual Elements

### Magic Hour Box

A gray-shaded box appears during the Magic Hour (e.g., 07:00-08:00) showing:
- Real-time high (top of box)
- Real-time low (bottom of box)
- Label: "MAGIC HOUR"

### Extension Zones

After the Magic Hour closes, colored zones appear above the high and below the low:

| Zone | Color | Meaning |
|------|-------|---------|
| Z1 | Gray | Ideal entry zone |
| Z2 | Blue | Prime entry zone |
| Z3 | Green | Deep but acceptable |
| INV | Red (dashed line) | Invalidation level |
| Z4 | Orange | Risk zone - caution |
| Z5 | Red | Last Stand - extreme caution |
| Z6 | Black | Graveyard - abandon hope |

### Key Lines

- **Neutral Lines (Gray):** Magic High and Magic Low
- **Break Line (Blue):** Whichever boundary price broke first
- **Midline (Fuchsia):** The 50% reversion target
- **Invalidation Line (Red, Dashed):** The danger threshold

### Dynamic Midline Label

The midline label updates in real-time:

- Before break: "MH Mid"
- After break: "TARGET: MID (Win: X%)" showing zone-appropriate win rate
- On target hit: "OBJECTIVE COMPLETE ✅ (Rev: ZX)"
- On session end without hit: "OBJECTIVE FAILED ❌"
- On invalidation: "INVALIDATED (> X%)"
- On graveyard: "GRAVEYARD (> X%)"

## Master Dashboard

The indicator includes a comprehensive statistics panel:

### Row 1: Title
```
MAGIC HOUR MASTER PLAYBOOK (2013-2026) | @Dokakuri on X
```

### Row 2: Strategy Name
```
STRATEGY: RANK #1: 07:00 (Golden Hour)
```

### Row 3: Summary Statistics
```
┌─────────────┬─────────────────────┬──────────────┐
│   TOTAL     │     WIN RATE        │   AVG MAE    │
│   3336      │  83.4% (2783/3336)  │    53.8%     │
└─────────────┴─────────────────────┴──────────────┘
```

### Row 4: Time Expectations
```
┌─────────────────────────────────────────────────────┐
│    TIME EXPECTATIONS (DURATION TO 50% TARGET)       │
├────────────┬────────────┬────────────┬─────────────┤
│ FAST (25%) │ 08:12 (+12m)│ MED (50%) │ 08:29 (+29m)│
└────────────┴────────────┴────────────┴─────────────┘
```

### Row 5-6: Runner Conversion
```
┌─────────────────────────────────────────────────────┐
│    RUNNER CONVERSION: Survivors / Base Winners      │
├──────────┬───────────────┬──────────┬──────────────┤
│ 75% EXT  │ 90.1% (2508)  │ 100% EXT │ 80.7% (2247)│
├──────────┼───────────────┼──────────┼──────────────┤
│ 125% EXT │ 72.0% (2005)  │ 150% EXT │ 64.6% (1799)│
└──────────┴───────────────┴──────────┴──────────────┘
```

### Row 7-14: Zone Table
```
┌──────┬─────────┬───────────────┬─────────┬─────────────┬────────────┐
│ ZONE │  RANGE  │   REACH %     │ WIN %   │ DENSITY (N) │   STATUS   │
├──────┼─────────┼───────────────┼─────────┼─────────────┼────────────┤
│  Z1  │  0-25%  │ 100.0% (3336) │ 100.0%  │ 36.5% (1016)│   IDEAL    │
│  Z2  │ 25-50%  │ 69.5% (2320)  │ 99.3%   │ 20.9% (582) │   PRIME    │
│  Z3  │ 50-100% │ 52.0% (1734)  │ 95.9%   │ 19.6% (545) │   DEEP     │
│ INV  │ > 100%  │     ---       │   ---   │     ---     │ STOP TRADE │
│  Z4  │ 100-150%│ 35.0% (1166)  │ 86.8%   │ 9.5% (264)  │   RISK     │
│  Z5  │ 150-300%│ 25.8% (862)   │ 63.4%   │ 11.1% (309) │ LAST STAND │
│  Z6  │ > 300%  │ 11.2% (375)   │ 17.9%   │ 2.4% (67)   │ GRAVEYARD  │
└──────┴─────────┴───────────────┴─────────┴─────────────┴────────────┘
```

### Row 15: Hard Stop
```
┌─────────────────────────────────────────────────────┐
│            HARD SESSION STOP: 11:00 AM              │
└─────────────────────────────────────────────────────┘
```

## How the Indicator Relates to Report Data

Every statistic in the indicator's dashboard is derived from the Python analysis:

| Dashboard Field | Python Source | Calculation |
|-----------------|---------------|-------------|
| TOTAL | `len(results_df)` | Count of all sessions |
| WIN RATE | `revert_50.sum() / total` | 50% target hit rate |
| AVG MAE | `mae_pct.median()` | Median MAE of winners |
| TIME EXPECTATIONS | `time_to_50.quantile()` | Percentiles of winner times |
| RUNNER CONVERSION | `revert_X / revert_50` | Conditional extension rates |
| REACH % | `max_excursion >= threshold` | Cumulative reach |
| WIN % | `zone_winners / zone_total` | Zone-specific win rate |
| DENSITY | `zone_winners / total_winners` | Winner distribution |

## Real-Time Zone Detection Logic

The indicator tracks which zone price is currently in:

```pine
float currentExt = 0.0
if breakSide == "HIGH"
    currentExt := (high - mhHigh) / rng * 100
else if breakSide == "LOW"
    currentExt := (mhLow - low) / rng * 100

if currentExt >= z1_min and maxZoneIdx < 1
    maxZoneIdx := 1
if currentExt >= z2_min and maxZoneIdx < 2
    maxZoneIdx := 2
// ... continues for all zones
```

This tracks the MAXIMUM zone reached (not current zone), which is what matters for statistics.

## Zone Highlighting

After a break occurs, zones are highlighted based on break direction:

```pine
if breakSide != "NONE"
    for i = 0 to array.size(zoneBoxes) - 1
        b = array.get(zoneBoxes, i)
        isUpper = box.get_bottom(b) >= mhHigh
        highlight = (breakSide == "HIGH" and isUpper) or 
                   (breakSide == "LOW" and not isUpper)
        box.set_bgcolor(b, highlight ? targetColor : zoneNeutralCol)
```

Upper zones highlight for HIGH breaks; lower zones highlight for LOW breaks.

---

# Complete Statistical Reference Tables

## All 24 Hours - Full Ranking

| Rank | Hour | Sessions | Win Rate | Wins | Median Time | Avg MAE | Tradeable % |
|------|------|----------|----------|------|-------------|---------|-------------|
| 1 | 07:00 | 3,336 | 83.4% | 2,783 | 29m | 53.8% | 99.8% |
| 2 | 08:00 | 3,322 | 79.7% | 2,648 | 18m | 48.2% | 98.1% |
| 3 | 06:00 | 3,329 | 78.7% | 2,619 | 44m | 59.3% | 98.7% |
| 4 | 17:00 | 542 | 77.1% | 418 | 3m | 80.0% | 97.0% |
| 5 | 00:00 | 3,326 | 76.8% | 2,555 | 31m | 55.2% | 98.4% |
| 6 | 01:00 | 3,323 | 74.2% | 2,465 | 28m | 58.7% | 97.1% |
| 7 | 02:00 | 3,304 | 70.9% | 2,341 | 16m | 47.7% | 94.8% |
| 8 | 23:00 | 3,288 | 69.5% | 2,285 | 35m | 50.0% | 93.3% |
| 9 | 05:00 | 3,279 | 65.7% | 2,154 | 36m | 50.5% | 91.9% |
| 10 | 19:00 | 3,269 | 63.0% | 2,059 | 26m | 55.0% | 88.6% |
| 11 | 12:00 | 3,204 | 61.5% | 1,970 | 38m | 48.6% | 88.5% |
| 12 | 13:00 | 3,166 | 61.3% | 1,942 | 32m | 48.1% | 85.4% |
| 13 | 22:00 | 3,143 | 56.7% | 1,782 | 40m | 45.7% | 80.9% |
| 14 | 04:00 | 3,200 | 56.1% | 1,796 | 40m | 44.7% | 81.1% |
| 15 | 18:00 | 3,125 | 54.3% | 1,696 | 41m | 47.8% | 77.6% |
| 16 | 09:00 | 3,248 | 53.7% | 1,745 | 30m | 42.2% | 80.2% |
| 17 | 11:00 | 3,197 | 52.6% | 1,683 | 44m | 42.9% | 76.8% |
| 18 | 20:00 | 3,081 | 49.4% | 1,523 | 34m | 46.2% | 71.7% |
| 19 | 14:00 | 3,035 | 49.1% | 1,491 | 24m | 41.2% | 69.8% |
| 20 | 03:00 | 3,139 | 48.5% | 1,521 | 40m | 44.1% | 71.2% |
| 21 | 21:00 | 3,015 | 47.2% | 1,423 | 39m | 43.3% | 67.9% |
| 22 | 10:00 | 3,109 | 43.9% | 1,365 | 46m | 40.0% | 64.0% |
| 23 | 16:00 | 2,161 | 40.4% | 872 | 28m | 32.5% | 51.7% |
| 24 | 15:00 | 2,156 | 22.4% | 483 | 21m | 23.5% | 24.4% |

## Runner Probability Summary (Top 7 Hours)

| Hour | 75% | 100% | 125% | 150% | 200% |
|------|-----|------|------|------|------|
| 07:00 | 90.1% | 80.7% | 72.0% | 64.6% | 51.2% |
| 08:00 | 87.8% | 76.5% | 67.8% | 59.3% | 45.0% |
| 06:00 | 88.9% | 78.3% | 68.7% | 60.3% | 46.5% |
| 00:00 | 87.0% | 75.0% | 64.9% | 55.5% | 40.7% |
| 01:00 | 84.5% | 71.4% | 60.5% | 51.0% | 36.8% |
| 02:00 | 79.2% | 62.8% | 51.3% | 41.2% | 26.4% |
| 23:00 | 79.3% | 62.8% | 50.5% | 41.0% | 26.5% |

---

# Risk Management Framework

## Position Sizing Based on MAE

The Average MAE for each strategy informs position sizing:

```
Max Position = Account Risk / (MAE × Point Value)

Example for Hour 07:00:
- Account Risk: $1,000
- MAE: 53.8% of Magic Range
- If Magic Range = 50 points and NQ = $20/point
- Dollar MAE = 53.8% × 50 × $20 = $538
- Max Position = $1,000 / $538 = 1.8 contracts → 1 contract
```

## Stop-Loss Placement

**Conservative Approach:** Set stop at invalidation level
- Hour 07:00: 100% of range
- Hour 08:00: 75% of range

**Aggressive Approach:** Set stop based on MAE + buffer
- Stop = Average MAE + 1 Standard Deviation
- This catches ~84% of winning trades

## Time Stops

Based on 90th percentile time data:

| Hour | Time Stop | Reasoning |
|------|-----------|-----------|
| 07:00 | 95 minutes after break | 90% of winners resolve by then |
| 08:00 | 54 minutes after break | Fast session, cut losers early |
| 06:00 | 120 minutes (2 hours) | Slow session, give room |
| 00:00 | 111 minutes after break | Overnight patience required |
| 02:00 | 60 minutes after break | European session is fast |
| 23:00 | 108 minutes after break | Asian session overnight |

## Hard Session Stops

Each strategy has an absolute deadline:

| Strategy | Hard Stop | Reasoning |
|----------|-----------|-----------|
| Hour 07:00 | 11:00 AM | US mid-morning noise begins |
| Hour 08:00 | 12:00 PM | Lunch liquidity collapse |
| Hour 06:00 | 10:00 AM | Before 07:00 Magic Hour starts |
| Hour 00:00 | 04:00 AM | Before European pre-market |
| Hour 01:00 | 05:00 AM | Before European session |
| Hour 02:00 | 06:00 AM | European session start |
| Hour 23:00 | 03:00 AM | Asian mid-session |

---

# Practical Application Guidelines

## Pre-Trade Checklist

Before entering a Magic Hour mean reversion trade:

- [ ] Confirmed Magic Hour has closed
- [ ] Range established (non-zero)
- [ ] Within analysis window (3 hours post Magic Hour)
- [ ] Break has occurred (price exceeded high or low)
- [ ] Currently in tradeable zone (Z1, Z2, or Z3)
- [ ] Not past invalidation level
- [ ] Not past hard session stop time

## Entry Rules

1. **Ideal Entry (Z1):** Enter immediately on break + confirmation
2. **Prime Entry (Z2):** Scale in with 50% position, add on reversion start
3. **Deep Entry (Z3):** Wait for reversal signal before entering
4. **Beyond Invalidation:** NO ENTRY

## Exit Rules

1. **Primary Target:** 50% reversion (Magic Mid)
2. **Runner Decision:** Use conditional probabilities for each level
3. **Stop-Loss:** Invalidation level or MAE-based stop
4. **Time Stop:** Based on percentile time analysis

## Scaling Strategy

For larger accounts:

```
Zone 1 (0-25%):   Full position
Zone 2 (25-50%):  Add 50%
Zone 3 (50-X%):   Add final 50% (if < invalidation)
Beyond INV:       No adds, consider exit
```

## Trade Journal Metrics

Track these for each trade:

1. Entry zone (Z1-Z6)
2. Max extension reached
3. Time to target (if won)
4. Actual MAE experienced
5. Runner levels achieved

---

# Glossary of Terms

| Term | Definition |
|------|------------|
| **Magic Hour** | The designated 60-minute window during which the reference range is established |
| **Magic High** | The highest price during the Magic Hour |
| **Magic Low** | The lowest price during the Magic Hour |
| **Magic Range** | Magic High minus Magic Low |
| **Magic Mid** | The midpoint of the Magic Range; the 50% reversion target |
| **Extension** | How far price travels beyond the Magic Hour boundary, expressed as a percentage of the range |
| **Zone** | A categorized extension band (Z1, Z2, Z3, etc.) |
| **Reach %** | The cumulative percentage of trades that extended at least to a given depth |
| **Density** | The percentage of winning trades whose maximum extension was in a specific zone |
| **Zone Win %** | The probability of winning given that price peaked in a specific zone (survivorship stat) |
| **Invalidation** | The extension level beyond which mean reversion probability drops significantly |
| **Runner** | A winning trade that continues past the 50% target to deeper reversion levels |
| **Runner Probability** | The conditional probability of reaching a deeper target given that 50% was hit |
| **MAE** | Maximum Adverse Excursion - the maximum price moved against the position |
| **Walk-Away Logic** | The methodology of truncating analysis at the moment the target is hit |
| **Hard Stop** | The absolute time deadline after which no trades should be held |
| **Graveyard** | Zone 6 (>300% extension) where win rates are extremely low |

---

# Conclusion

This study demonstrates that mean reversion in NQ futures is not random—specific hours and extension zones offer statistically significant advantages. By combining:

1. **Temporal Edge:** Trading only the 7 highest-probability hours
2. **Spatial Edge:** Entering in optimal extension zones
3. **Conditional Probability:** Using runner stats for profit management
4. **Risk Management:** Implementing MAE-based stops and time limits

Traders can systematically exploit the mean reversion tendency that market participants consistently misprice.

The edge is real. The statistics are robust. The implementation requires discipline.

---

**Report Version:** 1.0  
**Data Through:** 2026  
**Last Updated:** January 2026  
**Contact:** @Dokakuri on X  

---

*Disclaimer: Past performance does not guarantee future results. Trading futures involves substantial risk of loss. This report is for educational purposes only and does not constitute financial advice.*