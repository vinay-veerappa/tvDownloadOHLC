# Profiler Requirements

## Overview
The Profiler is a session-based analysis tool that classifies market behavior based on how price interacts with specific time-based "Session Boxes". It does NOT use daily classifications (R1, R2, etc.) but instead focuses on the structural outcome of key trading sessions: Asia, London, and New York.

## 🕒 Session Definitions
All times are in **New York Time (EST/EDT)**.

| Session | Start Time | End Time | Description |
| :--- | :--- | :--- | :--- |
| **Asia** | 18:00 | 19:30 | The initial overnight range setting the tone. |
| **London** | 02:30 | 03:30 | The European open, often testing Asia's extremes. |
| **NY AM** | 07:30 | 08:30 | The US pre-market header, often leading into the 09:30 open. |

---

## 🚦 Status Definitions
The "Status" of a session is determined by price action **after the session ends** (until the start of the next tracked session). It assesses breakout direction and holding power.

### 1. Long True (LT)
**Definition**: Price breaks the Session High and **never** breaks the Session Low.
- **Sentiment**: Strong Bullish.
- **Logic**: `Break High AND Hold Low`

![Long True Concept](./media/profiler_long_true.png)

### 2. Short True (ST)
**Definition**: Price breaks the Session Low and **never** breaks the Session High.
- **Sentiment**: Strong Bearish.
- **Logic**: `Break Low AND Hold High`

![Short True Concept](./media/profiler_short_true.png)

### 3. Long False (LF)
**Definition**: Price initially breaks the Session High (Fakeout), but then reverses and breaks the Session Low.
- **Sentiment**: Failed Bullish (Bearish Reversal).
- **Logic**: `Break High THEN Break Low`

![Long False Concept](./media/profiler_long_false.png)

### 4. Short False (SF)
**Definition**: Price initially breaks the Session Low (Fakeout), but then reverses and breaks the Session High.
- **Sentiment**: Failed Bearish (Bullish Reversal).
- **Logic**: `Break Low THEN Break High`

![Short False Concept](./media/profiler_short_false.png)

### 5. None / Range (Inside)
**Definition**: Price remains **completely inside** the session's High/Low range logic during the evaluation window. It breaks neither the High nor the Low.
- **Sentiment**: Neutral / Consolidation.
- **Logic**: `!Break High AND !Break Low`

![None Logic Concept](./media/profiler_none_logic.png)

---

## 💔 "Broken" Logic
The "Broken" status is a secondary condition that specificially checks if price **retraces to the mean** in the *subsequent* session timeframe.

> [!IMPORTANT]
> **Timing Constraint**: A session cannot be "Broken" by price action within its own active evaluation window. The "Broken" check begins **strictly after** the next session starts.

- **Condition**: Price touches the **Session Midpoint** `(High + Low) / 2`.
- **Window**: From the start of the **Next Session** (e.g., London Open for Asia) until the end of the day (18:00).
- **Significance**: A "Broken" session suggests the specific session's range has failed to serve as lasting support/resistance.

![Broken Logic Concept](./media/profiler_broken_logic_v2.png)

---

## 🧠 Logic Flowchart

```mermaid
flowchart TD
    subgraph SESSION["1. SESSION COMPLETE"]
        S[Start Time] --> E[End Time]
        E --> CALC[Calc High, Low, Mid]
    end

    subgraph STATUS["2. DETERMINE STATUS (Immediate Window)"]
        CALC --> B{Break High?}
        
        B -->|Yes| C{Break Low?}
        C -->|Yes| LF[🔴 LONG FALSE]
        C -->|No| LT[🟢 LONG TRUE]
        
        B -->|No| D{Break Low?}
        D -->|Yes| E2{Break High?}
        E2 -->|Yes| SF[🟢 SHORT FALSE]
        E2 -->|No| ST[🔴 SHORT TRUE]
        
        D -->|No| N[⚪ NONE / RANGE]
    end

    subgraph BROKEN["3. CHECK BROKEN (Starts @ Next Session Open)"]
        LT & ST & LF & SF --> TIME{Is Time >= Next Session?}
        TIME -->|Yes| CHEK{Touches Mid?}
        
        CHEK -->|Yes| BR[💔 BROKEN]
        CHEK -->|No| H[💎 HELD]
        
        N -.->|N/A| H
    end
```
