# TTrades Time Levels Strategy

**Source**: [Important Time Levels For Trading](https://www.youtube.com/watch?v=EYzP7c24AwM)  
**Last Updated**: January 4, 2026  
**Status**: Documented, Awaiting Validation

---

## Executive Summary

This strategy uses **key time levels** throughout the trading day to identify bias, premium/discount zones, and Judas swings. The core insight is that certain times consistently produce predictable price behavior.

---

## Key Time Levels (Eastern Time)

| Time | Significance | Primary Use |
|------|-------------|-------------|
| **12:00 AM** | New daily candle (midnight open) | Support/resistance, premium/discount |
| **8:30 AM** | News embargo lifts | Judas swing, order block formation |
| **9:30 AM** | NYSE opens | Judas swing, volatility, order block |
| **10:00 AM** | New 4-hour candle | 4H Power of Three |
| **2:00 PM** | New 4-hour candle | Retracement, continuation |

---

## Core Concepts

### 1. Daily Open High Low Close (OHLC)

Use midnight open and daily open as reference:

| Bias | Expected Sequence |
|------|-------------------|
| **Bullish** | Open → Low → High → Close |
| **Bearish** | Open → High → Low → Close |

### 2. 4-Hour Power of Three

| Candle | Time | Expected Behavior |
|--------|------|-------------------|
| 10:00 AM | Start of 4H | Open → Low → High → Close (if bullish) |
| 2:00 PM | Start of 4H | Retracement OR continuation |

### 3. Premium / Discount Zones

| Price Position | Interpretation |
|----------------|----------------|
| **Above** midnight + 8:30 + daily open | **Deep Premium** → Bearish |
| **Below** midnight + 8:30 + daily open | **Deep Discount** → Bullish |

### 4. Judas Swing Detection

Look for **opposing runs** at 8:30 and 9:30:

| Setup | What Happens | Result |
|-------|--------------|--------|
| **Bullish** | 8:30/9:30 makes run DOWN, closes over | Order block → Expect higher |
| **Bearish** | 8:30/9:30 makes run UP, closes below | Order block → Expect lower |

---

## Trading Framework

```
Step 1: Determine daily bias (higher timeframe structure)
Step 2: Mark levels: Midnight, 8:30, 9:30, 10:00, 2:00
Step 3: Assess premium/discount relative to these levels
Step 4: At 8:30 → Watch for Judas swing (opposing run)
Step 5: At 9:30 → Watch for order block OR continuation
Step 6: At 10:00 → Trade the 4H OHLC sequence
Step 7: At 2:00 → Expect retracement or continuation
```

---

## Example Patterns

### Bearish Day Pattern
1. Price above midnight + daily open = **Premium**
2. 8:30 makes opposing run UP into order block
3. 9:30 makes another opposing run UP  
4. Distribution lower begins after 9:30
5. Midnight is used as **resistance** on retracement
6. 10:00 4H candle: Open → High → Low → Close

### Bullish Day Pattern
1. Price below midnight + daily open = **Discount**
2. 8:30 makes opposing run DOWN
3. Closes over the down-close candle = **Order block**
4. 9:30 volatility continues the move higher
5. Midnight is used as **support**
6. 10:00 4H candle: Open → Low → High → Close

---

## Key Insights

### Midnight Open
- Acts as **support/resistance** throughout the day
- Position relative to midnight = **premium or discount**
- Multi-purpose: Reference for daily OHLC + S/R

### 8:30 Open
- **First key time** for Judas swing
- News can cause volatility
- Look for opposing runs that form order blocks

### 9:30 Open (NYSE)
- **Second key time** for Judas swing
- Often confirms or continues 8:30 move
- Volatility entry point

### 10:00 and 2:00 (4H Candles)
- Trade the 4H Power of Three
- 10:00 = Start of AM session 4H
- 2:00 = Retracement or continuation

---

## Validation Tasks (TODO)

1. **Midnight as S/R**: Test if midnight open acts as support/resistance
2. **8:30 Judas Swing**: Test opposing run frequency and reversal rate
3. **Premium/Discount**: Test if position relative to levels predicts direction
4. **4H OHLC**: Validate 10:00 and 2:00 candle behavior

---

## Overlap with Existing Research

| TTrades Concept | Our Existing Work |
|-----------------|-------------------|
| Midnight open | ✗ Not tracked yet |
| 8:30 Judas swing | Similar to Tanja 9:28 analysis |
| 9:30 order block | ✓ Tanja model, ORB strategy |
| Premium/discount | ✓ ALN pattern (Asia/London above/below) |
| 4H OHLC | ✗ Not tracked yet |

---

## Quick Resume Prompt

> "I'm working on the TTrades Time Levels strategy in `docs/strategies/9_30_breakout/ttrades/TIME_LEVELS.md`.
>
> Key concepts: Midnight/8:30/9:30 as Judas times, premium/discount zones, 4H OHLC at 10:00/2:00.
>
> I want to validate [midnight S/R / 8:30 Judas / premium-discount bias / 4H OHLC]."

---

*Document created January 4, 2026*
