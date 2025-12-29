# ORB Strategy V6 - Master Specification

This document serves as the **Single Source of Truth** for the 9:30 AM ORB Strategy (V6), unifying the Logic, Configuration, and Visual systems used in both PineScript and NinjaTrader implementations.

---

## 1. Strategy Overview

**Goal**: Capture the breakout of the first minute (09:30:00 - 09:31:00 EST) of the US Equities session with high precision.

### Dual-Loop Architecture (NinjaTrader Specific)
To achieve "Pine-like" precision on NinjaTrader:
1.  **Loop 1 (Seconds)**: Runs on 1-Second bars to capture the exact High/Low of the range (09:30:00-09:31:00).
2.  **Loop 2 (Minutes)**: Runs on the Primary Timeframe (e.g., 1-Min or 5-Min) to execute entries on **Bar Close** (avoiding wick fakeouts).

---

## 2. Pre-Trade Filters (Component 6)

Before looking for entries, the strategy validates the market environment using specific filters. All are configurable.

| Filter | Default | Condition to SKIP Trade | Description |
|--------|---------|-------------------------|-------------|
| **Regime Filter** | `TRUE` | `Daily Close < Daily SMA(20)` | Trend check. Bullish bias required. |
| **VVIX Filter** | `TRUE` | `VVIX Open > 115` | Volatility check. Avoid extremem extremes. |
| **Tuesday Filter** | `TRUE` | `DayOfWeek == Tuesday` | Statistical edge check (Tuesdays often chop). |
| **Max Range %** | `0.25%` | `Range > 0.25%` of Price | Avoid "Too Big" ranges (poor R:R). |
| **Time Window** | `09:30-10:00` | Current time > 10:00 AM | Entry window closes after 30 mins. |

---

## 3. Entry System

### A. Breakout Trigger
*   **Mode**: `Standard` (Default)
    *   **Logic**: Primary Candle **CLOSES** outside the ORB Range.
    *   **Buffer**: Optional 0.10% buffer lines (visual aid, used in "Displacement" mode).

### B. Execution Logic
*   **Mode**: `Pullback + Fallback` (Default)
    *   **Step 1 (Breakout)**: Signal Detected (Cyan Bar, Green/Red Triangle).
    *   **Step 2 (Arming)**: If Entry Mode is Pullback, we **WAIT**. Marker: Dim Gray Triangle ("Armed").
    *   **Step 3 (Entry)**: 
        *   **Pullback Entry**: Price touches `Pullback Level` (Default 25% depth) AND Valid Close. -> **ENTER LIMIT** (or Market if close).
        *   **Timeout Entry**: If `5 bars` pass without entry -> **ENTER MARKET** (Fallback). Marker: ⚡.

---

## 4. Exit & Risk Management

### A. Position Sizing
*   **Risk Per Trade**: `10.0%` of Equity (Aggressive Scaling).
*   **Default Equity**: `$3,000` (Standard Micro Account).
*   **Formula**: `Qty = (Equity * 0.10) / (RangeSize * PointValue)`.

### B. Stop Loss
*   **Initial SL**: Opposite side of the ORB Range.
*   **Max SL %**: `0.30%` (Cap). If Range > 0.30%, SL is tightened to Entry +/- 0.30%.

### C. Take Profit (Multi-TP Hybrid)
*   **TP1**: `10% target` (exit 50% qty).
*   **TP2**: `25% target` (exit 25% qty).
*   **Runner**: `Trailing Mode` (hold 25% qty).
    *   **Trail**: `0.08%` from peak.

### D. Special Exits
*   **MAE Heat Filter**: Exit immediately if price moves `0.12%` against entry (keeps losses small).
*   **Time Exit**: Hard Close at `10:00 AM` (or 16:00 PM if running full day).

---

## 5. Visual System (Parity Reached)

The visual language is identical across platforms logic.

| Element | Appearance | Meaning |
|---------|------------|---------|
| **ORB Range** | Transparent Box | Span of the Opening Range. |
| **Shading** | **Blue** (Normal), **Orange** (Sweet Spot 98-115 VVIX), **Red** (Too Big). | Quick diagnostic of range quality. |
| **Lines** | Blue (High), Red (Low), Gold (Mid), Gray Dot (0.10% Buffer). | Key levels. |
| **Markers** | Triangles (Green/Red). | Breakout Signal. |
| **Labels** | `PB BUY` / `PB SELL` / `⚡` | Entry Confirmation Type. |
| **Active Risk** | Dashed Red (SL) / Green (TP) | Where the algo is currently protecting/targeting. |
| **HUD** | Text Box (Top Right) | Real-time diagnostics (VVIX, Range %, Status). |

---

## 6. Logic Flowchart

```mermaid
flowchart TD
    A[09:30 ORB Defined] --> B{Filters Passed?}
    B -->|No| C[SKIP DAY]
    B -->|Yes| D{Breakout?}
    
    D -->|Yes| E{Entry Mode?}
    E -->|Immediate| F[Enter Market]
    E -->|Pullback| G[Wait for Retest of 25% Level]
    
    G -->|Touched| H[Enter Limit]
    G -->|Timeout (5 Bars)| I[Fallback: Enter Market]
    
    F & H & I --> J[Manage Trade]
    J --> K{Exits}
    
    K --> L[TP1 Hit (50%)]
    K --> M[TP2 Hit (25%)]
    K --> N[Trail Runner (25%)]
    K --> O[Stop Loss / MAE Hit]
```
