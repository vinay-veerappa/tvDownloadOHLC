# Master Execution Protocols (All Tickers)

This document defines the rules of engagement for translating statistical probability into executed trades. It covers **NQ, ES, CL, and GC**.

---

## 🚦 Phase 1: Pre-Fight Checklist (09:00 ET)
Before any trade is entered, validate the setup:

1.  **Ticker Selection**:
    *   Is it 08:30? check **CL** (Crude Oil).
    *   Is it 09:30? check **NQ** (Nasdaq) or **ES** (S&P).
    *   Is it 12:00? check **GC** (Gold).
2.  **The "Golden" Condition**:
    *   Did London sweep ONLY ONE side of Asia? (Partial Up/Down).
    *   Is the NY Open on the OPPOSITE side of the London Midline?
    *   **Yes to Both = Tier 1 Setup (Risk 1.5%).**

---

## 🔫 Protocol A: The "Aggressive Limit" (Tier 1 Only)
**Use Criteria**: Probability > 80% (e.g., CL Golden Setup, NQ Momentum).

1.  **Context**: The Bias is clearly defined (e.g., Long to London High).
2.  **The Trigger**:
    *   Identify the **London Midline** or the **09:30 Open Price**.
    *   Place a **Limit Order** at the 09:30 Open Price (retest of open).
    *   **Alternative**: Place Limit at the nearest M1 Fair Value Gap (FVG) formed right at the open.
3.  **Stop Loss**: 
    *   **Aggressive**: Below the M1 swing low that formed the move.
    *   **Conservative**: Below the London Midline.
4.  **Management**:
    *   Move to Breakeven after price clears the first internal swing high.

---

## 🛡️ Protocol B: The "Confirmation Entry" (Tier 2 / General)
**Use Criteria**: Probability 60-79% (Most ES/GC setups).

1.  **Context**: We have a direction, but volatility is likely.
2.  **The Trigger (Wait for M5)**:
    *   Let the initial 09:30 move happen (the "Fake Run").
    *   Wait for a **Market Structure Shift (MSS)** in the direction of the Bias.
        *   *Example (Long)*: Price dips, takes a short-term low, then breaks a swing high with displacement.
    *   **Enter** on the retracement to the FVG created by the displacement candle.
3.  **Stop Loss**: Below the displacement candle low.
4.  **Target**: The Statistical Magnet (London High/Low).

---

## 💡 Ticker-Specific Nuances

### 1. Nasdaq (NQ) / Micro-NQ (MNQ)
*   **Personality**: Momentum Monster.
*   **Execution**:
    *   Does NOT like deep retracements when trending.
    *   **Do not wait** for OTE (62% retracement). Enter on the first shallow FVG (25-30% pullback).
    *   **Danger**: Wicks are violent. Use wider stops (20-30 pts) and smaller size.

### 2. S&P 500 (ES) / Micro-ES (MES)
*   **Personality**: The Tank. Structured and slower.
*   **Execution**:
    *   Respects PD Arrays perfectly. Wait for the Order Block tap.
    *   **Targets**: Often hits the objective to the tick. Place Take Profit exactly on the London High/Low, not above/below.

### 3. Crude Oil (CL) / Micro-Oil (MCL)
*   **Personality**: The Liquidity Sniper.
*   **Execution**:
    *   **The 89% Setup**: If London swept Low and we Open High -> **MARKET BUY** at 09:00/09:30. Do not wait for a deep dip; it often rips immediately.
    *   **Stop Loss**: Can be tight. If the premise is valid, Old Oil rarely looks back.

### 4. Gold (GC) / Micro-Gold (MGC)
*   **Personality**: The Stop Hunter.
*   **Execution**:
    *   Fake-outs are common.
    *   **Protocol B is mandatory**. Always wait for the "Judas" shakeout first.
    *   **Lunch Magnet**: Between 12:00-13:00, simply fading the extremes of the AM range back to the midline is a high-win-rate scalp.

---

## 🛑 Invalidation (Abort Codes)
*   **Code Red**: 15-minute candle CLOSES beyond the London Midline against your direction.
    *   *Action*: Close trade immediately at market. Bias is broken.
*   **Code Yellow**: Price stagnates at the open for > 45 minutes (Chop).
    *   *Action*: Reduce risk or exit. The statistical edge decays over time.

---

## 📐 Position Sizing Guide
| Account Scale | Tier 1 Risk | Tier 2 Risk |
| :--- | :--- | :--- |
| **$50k Challenge/Fund** | 2 Micros (MNQ/MES) | 1 Micro |
| **$100k Challenge/Fund** | 5 Micros | 3 Micros |
| **Live Personal** | 1.0% Equity | 0.5% Equity |
