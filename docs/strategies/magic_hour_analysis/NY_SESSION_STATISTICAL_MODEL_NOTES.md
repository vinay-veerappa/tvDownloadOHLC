# NY Session Statistical Model - Detailed Notes

**Source:** [Video](https://www.youtube.com/watch?v=9FT0vq204bs) by @Dokakuri  
**Data:** 5 years of NQ futures data  
**Timezone:** America/New_York  

---

## Executive Summary

This model uses **fixed time window ranges** during the NY open to establish directional bias with statistical edge. Unlike the Magic Hour model (which uses pre-market hours and mean reversion), this focuses on **breakout continuation** during the regular session.

---

## Key Statistical Ranges

| Range | Window | Protection | Until |
|-------|--------|------------|-------|
| **10-Minute** | 9:30-9:40 ET | 78% opposite side won't break | 11:00 |
| **15-Minute** | 9:30-9:45 ET | 82% opposite side won't break | 11:00 |
| **Hourly** | 9:00-10:00 ET | 80% opposite side won't break | 14:00 |

---

## Core Concepts

### 1. What is a "Break"?
- A **5-minute candle must CLOSE** beyond the range high or low
- Intrabar wicks do NOT count
- This is a key distinction from other ORB strategies

### 2. What the Probabilities Mean
> **The probabilities are NOT about price moving in the direction of the break.**  
> **They are about the OPPOSITE SIDE of the range NOT breaking.**

This is crucial: The edge is that your stop (placed beyond the protected side) has 78-82% chance of NOT being hit.

### 3. Directional Confluence
- When all 3 ranges (10m, 15m, 1hr) break in the same direction → Strong confluence
- Alignment strengthens bias significantly

---

## Execution Framework

### Entry Strategy (00:02:33)
1. **Wait for first 5 minutes** to form (9:30-9:35)
2. **Plan entries aligned with highest probability breaks**
3. If bullish reaction early → Enter near expected range LOW
4. If bearish reaction early → Enter near expected range HIGH
5. **Place stop beyond the statistically protected side**

### Scaling Strategy
- Initial entry: Before confirmed break (reduced size)
- Add position: After 10-minute break confirms
- Scale further: After hourly break confirms on retracement

### Key Principle
> "We are NOT chasing a breakout candle. We are POSITIONING EARLY, placing the stop beyond the statistically protected side."

---

## The 10:00 PO3 (Power of Three) Concept

### 4-Hour Candle Structure
- 6:00-10:00 candle (pre-market into open)
- 10:00-14:00 candle (main session)

### How to Use
- The 9:00-10:00 hourly range often guides the 10:00 candle direction
- If price breaks above 9:00-10:00 range → Hourly LOW acts as projected low for 10:00-14:00 window
- Manipulation wick (if any) forms between 10:00 open and hourly range boundary

### Why NOT Primary Entry
- Price often trends strongly INTO 10:00 → No clean retracement
- Choppy behavior near hourly boundary
- **Use 10:00 mainly for re-entry/scaling, NOT primary entry**

---

## Failure Scenarios

### Scenario 1: Wrong Read on Initial Move (06:01)
- Entry before confirmed break → Can get stopped
- **Response:** If stopped and opposite side breaks → Switch direction
- Prefer retracement entry, NOT chasing
- If no clear signal after stopout → Stay flat, wait for break

### Scenario 2: Double Break (<18% occurrence)
- Price breaks one side, then breaks the other
- This invalidates initial plan
- **Response:** Shift to hourly range for direction
- Prefer retracement entries toward hourly boundary
- If price runs far without pullback → Stand aside for day

---

## Recommended Tools

1. **Standard Deviation Bands** (Daily, Hourly, 4H) - Frame context and reaction zones
2. **VWAP** - Intraday confluence on pullbacks and retests

---

## Session Flow Summary (07:01)

```
9:30-9:35  →  First 5 min forms baseline
9:35-9:40  →  Directional bias often set inside 10-min range
9:40-9:45  →  10-min break leads to one-sided action until 11:00
9:45-10:00 →  15-min break adds confluence, fewer deep pullbacks
10:00      →  Hourly break defines main morning leg
10:00-14:00 →  Opposite side of hourly usually protected
```

---

## Comparison: Magic Hour vs NY Session Model

| Aspect | Magic Hour Model | NY Session Model |
|--------|------------------|------------------|
| **Time Window** | Pre-market (06:00-08:00 ET) | Regular session (9:30-10:00 ET) |
| **Core Strategy** | Mean reversion (fade breakout) | Breakout continuation (trade with break) |
| **Target** | 50% reversion to midline | Trend continuation until 11:00/14:00 |
| **Edge** | Reverting to range center | Protected stop, ride trend |
| **Entry** | After breakout, fade it | Early, near protected side |
| **Add Points** | On zone pullbacks | On retracements to range |

---

## Integration Opportunities

1. **Combine with Magic Hour**: Use Magic Hour (07:00) for pre-market, then NY Session model for regular hours
2. **Use 9:00-10:00 range** as the "hourly statistical range" - this overlaps with Magic Hour 08:00 analysis window
3. **Protected side concept** can enhance Magic Hour stop placement
4. **10:00 PO3** can be used as re-entry for Magic Hour trades that are still live

---

## Key Takeaways

1. ⏰ **Time = Edge** - Specific time windows have statistical significance
2. 🛡️ **Protection, not prediction** - The edge is knowing what WON'T happen (opposite break)
3. 🎯 **Position early** - Get in before confirmation, size up after
4. 📍 **Stop = Protected side** - Statistical protection informs stop placement
5. 🔄 **Confluence stacks** - 10m + 15m + 1hr alignment = strongest setup

---

*Learn more on Glasp: https://glasp.co/reader?url=https://www.youtube.com/watch?v=9FT0vq204bs*
