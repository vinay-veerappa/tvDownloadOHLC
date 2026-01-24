# RTH Gap Trading Playbook
## Consolidated Statistical Edge Report & Morning Decision System

**Generated:** January 23, 2026  
**Data Range:** 2006-2026 (4,000-5,000 sessions per ticker)  
**Tickers Analyzed:** NQ, ES, YM, RTY, CL, GC

---

# Part 1: Morning Decision Flowchart

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        09:25 ET - PRE-MARKET CHECKLIST                       │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 1: MEASURE THE GAP                                                     │
│  Gap % = (RTH Open - Prior RTH Close) / Prior RTH Close × 100               │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
              ┌───────────────────────┼───────────────────────┐
              │                       │                       │
              ▼                       ▼                       ▼
    ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
    │  GAP < 0.15%    │     │ GAP 0.15-0.45%  │     │  GAP > 0.45%    │
    │    (NOISE)      │     │ (CONFLICT ZONE) │     │   (SIGNAL)      │
    │                 │     │                 │     │                 │
    │ Fill Rate: 85%+ │     │ Fill Rate: 55%  │     │ Fill Rate: 35%  │
    │ Action: FADE    │     │ Action: FILTER  │     │ Action: DEFEND  │
    └────────┬────────┘     └────────┬────────┘     └────────┬────────┘
             │                       │                       │
             │                       ▼                       │
             │     ┌─────────────────────────────────────┐   │
             │     │  STEP 2: CHECK GLOBEX CONTEXT       │   │
             │     └─────────────────────────────────────┘   │
             │                       │                       │
             │         ┌─────────────┼─────────────┐         │
             │         ▼             ▼             ▼         │
             │    ┌─────────┐  ┌─────────┐  ┌─────────┐      │
             │    │ NARROW  │  │ NORMAL  │  │  WIDE   │      │
             │    │ <50%ATR │  │50-100%  │  │ >100%   │      │
             │    │         │  │  ATR    │  │  ATR    │      │
             │    │Fill:76% │  │Fill:61% │  │Fill:41% │      │
             │    │ → FADE  │  │→FILTER  │  │→DEFEND  │      │
             │    └────┬────┘  └────┬────┘  └────┬────┘      │
             │         │            │            │           │
             │         ▼            ▼            ▼           │
             │     ┌─────────────────────────────────────┐   │
             │     │  STEP 3: RTH OPEN POSITION          │   │
             │     │  Where did RTH open within Globex?  │   │
             │     └─────────────────────────────────────┘   │
             │                       │                       │
             │         ┌─────────────┼─────────────┐         │
             │         ▼             ▼             ▼         │
             │    ┌─────────┐  ┌─────────┐  ┌─────────┐      │
             │    │  LOWER  │  │ MIDDLE  │  │  UPPER  │      │
             │    │  THIRD  │  │  THIRD  │  │  THIRD  │      │
             │    │Fill:59% │  │Fill:78% │  │Fill:57% │      │
             │    │Bearish  │  │Neutral  │  │Bullish  │      │
             │    │Pressure │  │ → FADE  │  │Pressure │      │
             │    └────┬────┘  └────┬────┘  └────┬────┘      │
             │         │            │            │           │
             ▼         ▼            ▼            ▼           ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 4: VOLATILITY REGIME CHECK                                             │
│  Is VVIX > 110?  OR  Is ATR in "High" bucket?                               │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                    ┌─────────────────┴─────────────────┐
                    ▼                                   ▼
           ┌───────────────┐                   ┌───────────────┐
           │      NO       │                   │      YES      │
           │  Normal Vol   │                   │   High Vol    │
           │               │                   │               │
           │ Proceed with  │                   │ DEFENSE BIAS  │
           │ gap analysis  │                   │ Skip fades    │
           └───────┬───────┘                   └───────┬───────┘
                   │                                   │
                   ▼                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 5: NEWS CHECK - Is there 8:30 AM News? (NFP/CPI/GDP/Retail)           │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                    ┌─────────────────┴─────────────────┐
                    ▼                                   ▼
           ┌───────────────┐                   ┌───────────────┐
           │      NO       │                   │      YES      │
           │               │                   │               │
           │ Standard      │                   │ Expect wider  │
           │ execution     │                   │ fakeout, but  │
           │               │                   │ NFP fills 68% │
           └───────┬───────┘                   └───────┬───────┘
                   │                                   │
                   ▼                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 6: STREAK CHECK - How many consecutive fills/defends?                  │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
              ┌───────────────────────┼───────────────────────┐
              ▼                       ▼                       ▼
     ┌────────────────┐      ┌────────────────┐      ┌────────────────┐
     │  0-1 Streak    │      │  2-3 Streak    │      │  4+ Streak     │
     │                │      │                │      │                │
     │ Normal sizing  │      │ Next fill ~85% │      │ REGIME WARNING │
     │                │      │ but exhaustion │      │ Mean reversion │
     │                │      │ approaching    │      │ likely - skip  │
     └───────┬────────┘      └───────┬────────┘      └───────┬────────┘
             │                       │                       │
             ▼                       ▼                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 7: DAY OF WEEK FILTER                                                  │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
        ┌─────────────┬───────────────┼───────────────┬─────────────┐
        ▼             ▼               ▼               ▼             ▼
   ┌─────────┐   ┌─────────┐   ┌─────────────┐   ┌─────────┐   ┌─────────┐
   │ MONDAY  │   │ TUESDAY │   │  WEDNESDAY  │   │THURSDAY │   │ FRIDAY  │
   │         │   │         │   │             │   │         │   │         │
   │Fill:59% │   │Fill:65% │   │  Fill:70%   │   │Fill:67% │   │Fill:63% │
   │Defense  │   │Neutral  │   │  BEST FADE  │   │Good Fade│   │Defense  │
   │Prone    │   │         │   │     DAY     │   │         │   │Prone    │
   └─────────┘   └─────────┘   └─────────────┘   └─────────┘   └─────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           FINAL DECISION GATE                                │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
              ┌───────────────────────┴───────────────────────┐
              ▼                                               ▼
┌──────────────────────────────┐             ┌──────────────────────────────┐
│      REVERSION TRADE         │             │     CONTINUATION TRADE       │
│         (Fade Gap)           │             │      (Defend Gap)            │
├──────────────────────────────┤             ├──────────────────────────────┤
│ CRITERIA MET:                │             │ CRITERIA MET:                │
│ • Gap < 0.25%                │             │ • Gap > 0.45%                │
│ • Narrow Globex              │             │ • Wide Globex                │
│ • Middle Third Open          │             │ • Upper/Lower Third Open     │
│ • Normal/Low Vol             │             │ • High Vol/ATR               │
│ • Tue/Wed/Thu                │             │ • Monday or Friday           │
│ • No 4+ fill streak          │             │ • OBR Open Type              │
├──────────────────────────────┤             ├──────────────────────────────┤
│ EXECUTION:                   │             │ EXECUTION:                   │
│ • Entry: Fade at open        │             │ • Entry: With gap direction  │
│ • Stop: 1.0x gap beyond open │             │ • Stop: Prior day close      │
│ • Target: Prior RTH close    │             │ • Target: 1.5-2x gap size    │
│ • Time Stop: 30 min          │             │ • No time stop               │
├──────────────────────────────┤             ├──────────────────────────────┤
│ EXPECTED WIN RATE: 88-91%    │             │ EXPECTED WIN RATE: 60-70%    │
│ (Perfect Reversion Setup)    │             │ (Defense Setup)              │
└──────────────────────────────┘             └──────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         09:30 ET - EXECUTION                                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 8: THE 15-MINUTE MOAT CHECK (Confirmation)                            │
│                                                                              │
│  After first 15-min candle:                                                  │
│  • If prior extreme HOLDS → Defense confirmed, exit fade or join trend      │
│  • If prior extreme BREAKS → Reversion confirmed, hold for fill             │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 9: PARTIAL FILL MANAGEMENT                                             │
│                                                                              │
│  • At 50% fill: 82% chance of full fill - HOLD                              │
│  • At 75% fill: 90% chance of full fill - HOLD                              │
│  • If stalled at 50% for 15+ min: Consider reducing size                    │
│  • If not 50% filled by 30 min: Reassess or exit                            │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

# Part 2: Cross-Ticker Statistical Summary

## Overall Fill Rates & Best Setups

| Ticker | Base Fill | Perfect Reversion | Lift | Sample | Trend Continuation | Defense Rate |
|--------|-----------|-------------------|------|--------|-------------------|--------------|
| **ES** | 64.5% | **91.1%** | +26.7% | 946 | 31.6% | 68.4% |
| **YM** | 63.3% | **91.1%** | +27.8% | 854 | 30.2% | 69.8% |
| **NQ** | 66.8% | **88.9%** | +22.1% | 1085 | 36.9% | 63.1% |
| **RTY** | 65.4% | **90.6%** | +25.2% | 297 | 38.5% | 61.5% |
| **CL** | 55.4% | **88.3%** | +32.9% | 205 | 39.4% | 60.6% |
| **GC** | 51.5% | **78.9%** | +27.4% | 722 | 22.3% | 77.7% |

**Recommendation:** ES or YM for highest "Perfect Reversion" rate (91.1%). NQ for fastest fills.

---

## Fill Probability by Gap Size

| Bucket | NQ | ES | YM | RTY | CL | GC |
|--------|-----|-----|-----|-----|-----|-----|
| Very Small (<0.07%) | 93.5% | 94.3% | 94.2% | 94.7% | 88.2% | 79.2% |
| Small (0.07-0.15%) | 79.0% | 82.7% | 83.2% | 88.8% | 86.5% | 76.3% |
| Medium (0.15-0.25%) | 68.4% | 67.7% | 67.8% | 82.5% | 77.7% | 62.0% |
| Large (0.25-0.45%) | 54.1% | 56.0% | 57.1% | 65.7% | 74.1% | 47.9% |
| Very Large (>0.45%) | 38.6% | 35.0% | 33.9% | 44.6% | 47.1% | 21.9% |

**Key Insight:** Gaps <0.15% fill 85%+ across all equity indices. Gaps >0.45% defend 60%+ of the time.

---

## Time-to-Fill Analysis

### Speed of Fill by Ticker

| Ticker | % Filled <15m | % Filled <30m | Median Fill (Small Gap) |
|--------|---------------|---------------|-------------------------|
| **RTY** | 32.5% | 43.4% | 2 min |
| **NQ** | 33.7% | 45.2% | 11 min |
| **YM** | 29.4% | 38.4% | 9 min |
| **ES** | 28.3% | 39.0% | 16 min |
| **CL** | 16.4% | 23.3% | 0 min |
| **GC** | 16.7% | 25.6% | 3 min |

**Key Insight:** If not 50% filled in 30 minutes, reassess the trade. High-conviction fills happen fast.

### Fill Time by Gap Size (NQ Example)

| Gap Size | Median Fill Time | % Filled <15m |
|----------|------------------|---------------|
| Very Small | 1 min | 83.5% |
| Small | 11 min | 54.8% |
| Medium | 25 min | 36.2% |
| Large | 50 min | 20.0% |
| Very Large | 100 min | 7.5% |

---

## Partial Fill Conditional Probabilities

**Critical for Trade Management:**

| If Price Reaches... | NQ | ES | YM | RTY |
|---------------------|-----|-----|-----|-----|
| 25% of gap | 75.2% | 73.0% | 72.6% | 73.8% |
| 50% of gap | **82.8%** | **81.4%** | **81.3%** | **82.0%** |
| 75% of gap | **90.8%** | **89.7%** | **90.1%** | **90.4%** |

**Key Insight:** Once price reaches 50% of the gap, hold for full fill (82% probability). At 75%, it's 90%+.

---

## Consecutive Day Streak Analysis

### Fill Probability After N Consecutive Fills

| Streak | NQ | ES | YM | RTY |
|--------|-----|-----|-----|-----|
| 1 Fill | 68.6% | 66.6% | 65.0% | 66.2% |
| 2 Fills | 81.9% | 79.7% | 76.4% | 77.5% |
| 3 Fills | 90.1% | 87.9% | 85.9% | 84.0% |
| 4 Fills | **96.9%** | **94.7%** | **94.9%** | 92.5% |
| 5 Fills | **98.6%** | **94.8%** | **96.7%** | 98.0% |

**Key Insight:** After 3+ consecutive fills, a defense day is statistically due. Consider sizing down or skipping.

### Prior Day Impact

| Prior Day Outcome | NQ Fill Today | ES Fill Today | YM Fill Today |
|-------------------|---------------|---------------|---------------|
| Prior Defended | 69.4% | 68.1% | 66.5% |
| Prior Filled | 65.5% | 62.4% | 61.4% |

**Key Insight:** Defense days tend to cluster. If yesterday defended, today has slightly higher fill probability.

---

## Globex Range Context

### Fill Rate by Overnight Range Size

| Globex Range | NQ | ES | YM | RTY |
|--------------|-----|-----|-----|-----|
| Narrow (<50% ATR) | **75.8%** | **76.3%** | **77.4%** | **75.7%** |
| Normal (50-100%) | 62.8% | 61.2% | 59.2% | 61.3% |
| Wide (>100% ATR) | 42.6% | 41.2% | 38.9% | 42.1% |

**Key Insight:** Narrow overnight sessions = highest reversion probability (~76-77%).

### Fill Rate by RTH Open Position in Globex Range

| Position | NQ | ES | YM | RTY |
|----------|-----|-----|-----|-----|
| Lower Third | 63.3% | 59.2% | 58.2% | 61.3% |
| **Middle Third** | **78.0%** | **78.8%** | **78.7%** | **76.1%** |
| Upper Third | 60.6% | 56.6% | 55.7% | 60.1% |

**Key Insight:** Middle third opens have highest fill rate (~78%). Extreme positions signal directional bias.

---

## Day of Week Analysis

| Day | NQ Fill | ES Fill | YM Fill | Best Strategy |
|-----|---------|---------|---------|---------------|
| Monday | 60.6% | 58.4% | 57.9% | Defense Prone |
| Tuesday | 68.0% | 65.0% | 62.3% | Neutral |
| **Wednesday** | **70.0%** | **69.2%** | **69.7%** | **Best Fade Day** |
| Thursday | 69.0% | 66.4% | 66.9% | Good Fade Day |
| Friday | 66.0% | 62.7% | 59.1% | Defense Prone |

**Key Insight:** Mid-week (Tue-Thu) for fades. Monday/Friday gaps that hold tend to continue.

---

## MAE/MFE Precision (Stop Placement)

### Fakeout Before Fill (MFE in Gap Direction)

| Ticker | Median Fakeout | Stop Recommendation |
|--------|----------------|---------------------|
| RTY | 87.6% | 1.0x gap size |
| YM | 85.0% | 1.0x gap size |
| NQ | 83.3% | 1.0x gap size |
| ES | 77.8% | 0.9x gap size |
| CL | 66.7% | 0.8x gap size |
| GC | 57.6% | 0.7x gap size |

**Key Insight:** ES has the tightest fakeout profile - best for defined risk. Place stops beyond 80-100% of gap size.

### Trend Extension (When Gap Defends)

| Ticker | Median Extension | Target Recommendation |
|--------|------------------|----------------------|
| NQ | 160 pts | 1.5-2x gap size |
| RTY | 155 pts | 1.5-2x gap size |
| YM | 147 pts | 1.5-2x gap size |
| ES | 139 pts | 1.5-2x gap size |
| CL | 115 pts | 1.5x gap size |
| GC | 101 pts | 1x gap size |

---

## Volatility Regime Impact

### Fill Rate by ATR Bucket

| ATR Regime | NQ | ES | YM |
|------------|-----|-----|-----|
| Low ATR | 70.6% | 67.7% | 65.3% |
| Normal ATR | 66.8% | 63.6% | 63.2% |
| High ATR | 63.1% | 62.1% | 61.5% |

**Key Insight:** High ATR = larger gaps, lower fill rates. Treat as breakaway signal.

### VIX Impact

| VIX Regime | ES Fill | YM Fill |
|------------|---------|---------|
| Low VIX | 64.0% | 71.7% |
| Normal VIX | 66.3% | 67.0% |
| High VIX (>25) | 65.3% | 59.9% |

**Key Insight:** High VIX widens the "moat" - gaps fill less frequently on YM especially.

---

## News Day Profiles

### 8:30 AM News Impact

| Event | NQ Fill | ES Fill | Avg Gap Size |
|-------|---------|---------|--------------|
| No News | 66.7% | 64.1% | 0.32% |
| NFP | **71.3%** | **68.3%** | 0.30% |
| CPI | 65.0% | 63.5% | 0.35% |
| GDP | 68.8% | 79.2% | 0.23% |

**Key Insight:** NFP has HIGH fakeouts but also HIGH fill rates. Don't fade early - wait for the flush.

---

# Part 3: The Two Optimal Setups

## Setup A: Perfect Reversion (91% Win Rate)

### Entry Criteria (ALL must be true)

| Filter | Requirement | Why |
|--------|-------------|-----|
| Gap Size | 0.07% - 0.25% | Small gaps are noise |
| Globex Range | Narrow (<50% ATR) | Quiet overnight = mean reversion |
| RTH Open Position | Middle third of Globex | No directional pressure |
| Day of Week | Tuesday, Wednesday, Thursday | Mid-week fills best |
| ATR Regime | Low or Normal | High ATR = breakaway |
| Streak | No 4+ consecutive fills | Regime exhaustion |

### Execution Parameters

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| **Entry** | Fade at RTH open or first 5m pullback | Immediate execution |
| **Stop** | 1.0x gap size beyond open | Survives 83% median fakeout |
| **Target** | Prior RTH close (100% fill) | Full gap fill |
| **Time Stop** | 30 minutes | If not 50% filled, reassess |

### Expected Performance

| Ticker | Win Rate | Sample Size | Risk:Reward |
|--------|----------|-------------|-------------|
| ES | 91.1% | 946 days | ~9:1 EV at 1:1 RR |
| YM | 91.1% | 854 days | ~9:1 EV at 1:1 RR |
| NQ | 88.9% | 1085 days | ~8:1 EV at 1:1 RR |
| RTY | 90.6% | 297 days | ~9:1 EV at 1:1 RR |

---

## Setup B: Trend Continuation / Defense (68% Win Rate)

### Entry Criteria (ALL must be true)

| Filter | Requirement | Why |
|--------|-------------|-----|
| Gap Size | >0.45% | Large gaps are signal |
| Open Type | OBR (Outside Bar Range) | Already gapped through prior range |
| Globex Range | Wide (>100% ATR) | Overnight momentum |
| ATR Regime | High | Volatility expansion |
| Day of Week | Monday or Friday | Trend days |

### Execution Parameters

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| **Entry** | With gap direction after 15m moat holds | Confirmation |
| **Stop** | Prior RTH close | If fill starts, exit |
| **Target** | 1.5-2x gap size extension | Trending gaps run |
| **Time Stop** | None | Let it ride |

### Expected Performance

| Ticker | Defense Rate | Sample Size | Best For |
|--------|--------------|-------------|----------|
| GC | 77.7% | 878 days | Most persistent gaps |
| YM | 69.8% | 656 days | Blue chip momentum |
| ES | 68.4% | 651 days | Balanced |

---

# Part 4: Quick Reference Cards

## Morning Checklist (Print This)

```
┌────────────────────────────────────────────────────────────┐
│              09:25 ET MORNING CHECKLIST                    │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  □ Gap Size: _____%   (< 0.15 = Fade | > 0.45 = Defend)   │
│                                                            │
│  □ Globex Range: _____ ATR%                                │
│    (< 50% = Fade | > 100% = Defend)                       │
│                                                            │
│  □ RTH Open Position: Lower / Middle / Upper Third         │
│    (Middle = Fade bias)                                    │
│                                                            │
│  □ Day of Week: _________                                  │
│    (Tue-Thu = Fade | Mon/Fri = Defend)                    │
│                                                            │
│  □ VVIX Level: _____  (> 110 = Defend bias)               │
│                                                            │
│  □ ATR Regime: Low / Normal / High                         │
│    (High = Defend bias)                                    │
│                                                            │
│  □ 8:30 News? Y / N   (NFP = wait for flush then fade)    │
│                                                            │
│  □ Consecutive Fills: _____ days                           │
│    (4+ = skip or size down)                               │
│                                                            │
├────────────────────────────────────────────────────────────┤
│  DECISION:  □ FADE (Reversion)  □ DEFEND (Continuation)   │
│                                                            │
│  TICKER: _____  SIZE: _____  STOP: _____  TARGET: _____   │
└────────────────────────────────────────────────────────────┘
```

## Probability Lookup Table

```
┌─────────────────────────────────────────────────────────────┐
│                    FILL RATE QUICK LOOKUP                   │
├──────────────────┬──────────────────────────────────────────┤
│ CONDITION        │ NQ     ES     YM     RTY                 │
├──────────────────┼──────────────────────────────────────────┤
│ Base Rate        │ 66.8%  64.5%  63.3%  65.4%              │
│ Perfect Setup    │ 88.9%  91.1%  91.1%  90.6%              │
│ Gap < 0.15%      │ 86%    88%    88%    92%                │
│ Gap > 0.45%      │ 39%    35%    34%    45%                │
│ Narrow Globex    │ 76%    76%    77%    76%                │
│ Wide Globex      │ 43%    41%    39%    42%                │
│ Middle Third     │ 78%    79%    79%    76%                │
│ Wednesday        │ 70%    69%    70%    67%                │
│ Monday           │ 61%    58%    58%    64%                │
│ After 3 Fills    │ 90%    88%    86%    84%                │
│ At 50% Retrace   │ 83%    81%    81%    82%                │
│ At 75% Retrace   │ 91%    90%    90%    90%                │
└──────────────────┴──────────────────────────────────────────┘
```

## Stop Placement Guide

```
┌─────────────────────────────────────────────────────────────┐
│                   STOP PLACEMENT GUIDE                      │
├──────────────────┬──────────────────────────────────────────┤
│ TICKER           │ STOP (x Gap Size)  │ SURVIVES           │
├──────────────────┼────────────────────┼────────────────────┤
│ ES               │ 0.9x               │ 78% of fakeouts    │
│ NQ               │ 1.0x               │ 83% of fakeouts    │
│ YM               │ 1.0x               │ 85% of fakeouts    │
│ RTY              │ 1.0x               │ 88% of fakeouts    │
├──────────────────┴────────────────────┴────────────────────┤
│ RULE: Place stop beyond median fakeout to avoid noise      │
│ ES wins here - tightest fakeouts = best defined risk       │
└─────────────────────────────────────────────────────────────┘
```

---

# Part 5: Ticker Selection Guide

## When to Trade Each Ticker

| Ticker | Best For | Avoid When | Edge |
|--------|----------|------------|------|
| **ES** | Defined risk fades | High VIX spikes | Tightest fakeout (78%), most data |
| **YM** | Slow, managed fades | Fast markets | Slowest fills, best for scaling |
| **NQ** | Quick resolution | Need tight stops | Fastest fills, highest base rate |
| **RTY** | Small gaps, fastest fills | Large gaps | 92% fill on <0.15% gaps |
| **CL** | Avoid for fades | Most conditions | Too volatile, lowest edge |
| **GC** | Continuation plays | Fading | 78% defense on large gaps |

## Final Recommendation

**For Defined Risk Reversion Trading:**

1. **Primary:** ES - 91.1% win rate on perfect setup, tightest fakeout profile
2. **Secondary:** YM - Same win rate, slower fills give more management time
3. **Tertiary:** NQ - Slightly lower win rate but fastest resolution

**For Continuation/Defense Trading:**

1. **Primary:** GC - 77.7% defense rate, most persistent gaps
2. **Secondary:** YM - Clean trend days on Monday/Friday

---

*Document generated from 20 years of futures data (2006-2026). Statistics are historical and do not guarantee future performance. Always use proper risk management.*
