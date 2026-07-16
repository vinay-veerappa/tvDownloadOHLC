# Quarters Theory & Overnight Direction Combinations

> **Status:** Knowledge Base — documented from Boot Camp Week 2 Day 5 + Quarterly Theory sessions
> **Date:** 2026-07-13
> **Related:** Profiler module (`scripts/trader/signals/profiler.py`), NQStats quarterly dynamics

---

## Part 1: Overnight Direction Combinations

### Overview

The Profiler's session status codes (LT/ST/LF/SF) for Asia and London combine to form a **directional signature** that predicts NY session behavior. The key distinction is between **trending markets** (Asia and London agree) and **contradicting markets** (Asia and London disagree → range overnight).

### Trending Combinations (Bullish Examples)

| Asia / London | Asia OU Break Prob (mode) | London OU Break Prob (mode) | 18:00 LOD Support | NY1 Expectation |
|---|---|---|---|---|
| **LT / SF** | 75% (9:30-9:45) | 80% (7:45-8:30) | ✓ Holds | Best supports hitting Asia OU during NY1 when trending higher |
| **LT / LT** | 59% (02:30) | 73% (9:30-9:45) | ✓ Holds | Lower probability of Asia OU break than other trending types |
| **SF / LT** | 76% (10:00) | 75% (9:30) | ✓ Holds overnight LOD | — |
| **SF / SF** (Firecracker) | 91% (02:30-03:30) | 86% (7:30, 8:30, 9:30-9:45) | ✗ **NO** support | Signature for "full firecracker" — price crashes through P12 levels, makes new LOD even in bullish-trending market |

> **OU** = Opening Up (the session's opening range high). "OU Break" = probability that the session's opening high is broken during the subsequent session.
> **Mode** = the most frequent time bucket when the break occurs.

### Contradicting Markets (Asia and London Disagree)

| Characteristic | Implication |
|---|---|
| Overnight action | Market ranged overnight |
| Session breaks | Asia OU and London OU both high probability of being broken ("broken broken") |
| Low/High Day | LOD and HOD more likely set **after RTH open** (not overnight) |
| NY1 strategy | Range-bound RTH. Focus on 9:45 reversal or four-step reversal after one side (H or L) is made, then move to opposite extreme |
| Live price action | Critical — watch which extreme hits first |

### Strategy Alignment

- **Trending markets** → turn on trend systems
- **Contradicting markets** → turn on cash flow / range systems
- Position before 9:30 using these probabilities
- Adjust risk management via the four-step reversal process based on which levels are expected to hold or break

### Relationship to Profiler Module

This extends the Profiler's per-session status (already in `profiler.py`) into a **combination matrix**. The profiler module currently computes conditional predictions for each session independently using the context dependency chain. The combination analysis adds a layer on top: once Asia and London are both resolved, classify the day as trending or contradicting, and apply the corresponding NY1 expectation.

---

## Part 2: Quarterly Theory

### Core Concept

**Any timeframe can be divided into 4 equal quarters.** The theory is fractal — the same structural logic applies at every scale:

| Timeframe | Quarter Size | Example Use |
|---|---|---|
| Year | 3 months | Quarterly earnings cycles |
| Month | ~1 week | Monthly candle structure |
| Week | ~1.5 days | Weekly candle structure |
| Day | 6 hours | Daily candle structure (18:00-17:00) |
| 4 hours | 1 hour | Session quarter (e.g., NY1 = Q1 of RTH) |
| 1 hour | 15 minutes | **Hourly candle structure** (most practical) |
| 15 minutes | ~3.75 minutes | Micro-quarter for scalping |

### The Hourly Candle Structure

The most practical application is the **hourly candle** divided into four 15-minute quarters:

| Quarter | Minutes | Role | Statistical Behavior |
|---|---|---|---|
| **Q1** | :00 - :14 | **Anticipation** | Many hours place the HOD or LOD of the hour here. The '05 box (first 5 min) sets the initial range. |
| **Q2** | :15 - :29 | **Confirmation** | Confirms whether Q1's extreme is the instat (instantaneous statistical) high/low. Opposite side of Q1 range taken → Q1 extreme locked in. |
| **Q3** | :30 - :44 | **Extension** | Typically where the opposite extreme forms in a trending hour. |
| **Q4** | :45 - :59 | **Completion** | Final quarter — can establish the opposite extreme or extend the trend. |

### Normal (Directional) Hourly Candle

A solid-bodied hourly candle follows a predictable pattern:
- **Bullish hour:** Low in Q1 → High in Q3 or Q4
- **Bearish hour:** High in Q1 → Low in Q3 or Q4
- The Q1 extreme is confirmed in Q2 (opposite side taken), then the trend extends through Q3/Q4

### The '05 Box

The first 5 minutes of an hour form the **'05 box** — the initial range. A breakout from this box in Q1 is the first signal of direction. Whether that breakout holds or fails determines the hour's structure.

### Identifying a Doji (Reversal/Indecisive Candle)

A Doji has a small body (open and close close together relative to range). It signals a break from the standard statistical expectation. Two key triggers:

#### Trigger 1 — Q1 Sweep and Retreat
1. Price takes one side of the Q1 range (e.g., breaks the '05 box high)
2. Then **"sucks back in"** — retreats back inside the Q1 range
3. This signals the initial momentum was false → potential Doji/reversal

#### Trigger 2 — Taking Both Sides (Anomaly)
1. After Trigger 1 (one side taken, then retreat)
2. Price takes the **opposite** side of the Q1 range
3. This disrespects the normal structure (only one extreme should be in Q1)
4. If **both sides** of Q1 are taken → the hourly candle will likely be a Doji/reversal

#### Structure Breakdown
- If a Q1 high or low is **confirmed** as the statistical extreme (via Q2 confirmation)
- Breaching that extreme in Q2, Q3, or Q4 = **structure broken**
- → Expect an hourly Doji (reversal or indecisive candle)

### Instat Extremes (Q1 Anticipation → Q2 Confirmation)

1. **Q1 (Anticipation):** Price breaks the '05 box. Measured in basis points to determine if it's a genuine breakout or just an instat high/low.
2. **Q2 (Confirmation):** The Q1 extreme is **confirmed** when the **opposite** side of the Q1 range is taken out in Q2.
   - Example: Q1 made a high → Q2 confirms by taking out the Q1 low → the Q1 high is locked in as the statistical high.
3. Once confirmed, breaching that extreme in any subsequent quarter (Q2/Q3/Q4) = structure broken → hourly Doji anticipated.

### The Football Analogy

- **Normal hourly candle** = a perfect touchdown drive: Q1 sets field position (e.g., statistical low), the team follows a predictable sequence (Q2, Q3, Q4) to achieve the goal (e.g., higher close).
- **Doji candle** = breakdown of that plan: the plays don't work as expected, both sides get tested, indecisive result.

### Existing Quantitative Backing

The `docs/nqstats/quarterly_dynamics/` directory contains 20-year statistical studies confirming:
- **Q1 High probability** by hour (e.g., 18:00 hour: 56.7% of the time, the hour's high is in Q1)
- **Q1 Low probability** by hour
- **Q1-Q4 opposite extremes** (cleanest directional hours)
- **Mutual exclusivity logic:** Q1 High Only, Q1 Low Only, Q1 Both (contained), Neither (expansion)

Files: `NQ1_QUARTER_ANALYSIS.md`, `ES1_QUARTER_ANALYSIS.md`, `CL1_QUARTER_ANALYSIS.md`, `GC1_QUARTER_ANALYSIS.md`, `RTY1_QUARTER_ANALYSIS.md`, `YM1_QUARTER_ANALYSIS.md`

---

## Implementation Notes for Narrative Module

### Overnight Direction Combinations
- Input: Asia + London resolved statuses from profiler JSON
- Output: trending/contradicting classification + NY1 expectation + OU break probabilities + LOD support assessment
- The combination matrix (4 trending + contradicting) can be a static lookup table with the probabilities from the Boot Camp data
- Wire into the profiler block after London resolves (during NY_AM session)

### Quarterly Theory (Doji Detection)
- Input: 1-minute OHLC data for the current hour (or any timeframe)
- Output: Q1/Q2/Q3/Q4 structure status, Doji trigger flags, instat extreme confirmation
- Needs live 1m data (from parquet) — this is a live computation, not historical JSON
- The existing `quarterly_dynamics` studies provide the statistical baseline (Q1 High % by hour)
- Wire into intraday sessions (NY_AM, NY_LUNCH, NY_PM) where hourly candle structure matters most
- Key hours to watch: 09:00-10:00 (RTH open hour), 10:00-11:00, 13:00-14:00, 15:00-16:00 (close hour)