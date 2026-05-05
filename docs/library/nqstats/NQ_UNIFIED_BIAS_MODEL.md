# NQ Unified Bias Model (Second Brain)

## 1. Overview
The NQ Unified Bias Algorithm synthesizes ALN Patterns, session break status, and profiler (P12) alignment to determine a high-conviction daily market direction.

## 2. Decision Matrix

| ALN Pattern | Broken Status | Profiler (Status) | Final Bias | Conviction |
|-------------|---------------|-------------------|------------|------------|
| **LPEU** | Held/Held | **L/L** | **Strong Bullish** | High |
| **LPEU** | Broken/Held | **L/L** | **Strong Bullish** | High |
| **LPEU** | Broken/Held | **L/S** | **Strong Bearish** | High (Reversal) |
| **LPED** | Broken/Broken | S/S | **Bearish Expansion** | Medium |
| **Any** | Broken/Broken | Any | **Neutral / Chop** | Low |

## 3. Components

### 3.1 ALN Pattern (LPEU / LPED / LEA / AEL)
Relationship between Asia and London session ranges.

### 3.2 Broken Status (Held / Broken)
Did the current session breach the range of the previous session?
- **Held/Held**: High conviction (stable structure).
- **Broken/Broken**: Low conviction (choppy expansion).

### 3.3 Profiler Status (L / S)
Relationship between session closes and the Prior Close (P12, 16:00 ET).
- **L**: Close > P12
- **S**: Close < P12

## 4. Implementation Reference
- Logic: `scripts/libs_py/nqstats/classifiers.py`
- Orchestration: `scripts/libs_py/nqstats/engine.py`
