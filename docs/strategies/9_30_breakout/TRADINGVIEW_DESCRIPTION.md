# 9:30 AM Breakout Strategy (V6) - Unified & Robust

## 🚀 Overview
The **9:30 AM Breakout Strategy (V6)** is a professional-grade execution system designed to capture the initial range breakout of the US Session (09:30 ET). 

This V6 release introduces a major upgrade to the entry engine: **Close Confirmation Logic**. Instead of using passive Limit Orders (which can catch "falling knives"), this strategy now waits for the candle to **close** effectively testing the pullback level before entering. This significantly improves win rate by filtering out fakeouts and failed breakouts.

---

## 🛠️ Key Features

### 1. Smart Entry Engine (No "Falling Knives")
- **Wait-for-Close**: Pullback entries are only taken if the price touches the level AND *closes* validly (respecting the level).
- **Deep Pullback Guard**: If price crashes through the pullback level and closes deep inside the range, the trade is **cancelled** immediately.
- **No Fakeout Arming**: A trade will only "arm" (prepare to trigger) if the initial breakout candle actually *closes* outside the range, preventing wick-only fakeouts.

### 2. Multi-Target Profit Taking
- **Scale Out**: Automatically close 50% at TP1 (e.g., 0.10%) and 25% at TP2 (e.g., 0.25%).
- **Trailing Runner**: The remaining 25% can trail price to capture large trend days.

### 3. Modular Logic
- **Trigger Modes**: Choose how a breakout is defined (Aggressive Wick, Standard Close, or Displacement).
- **Entry Modes**: Choose your aggression level (Immediate Market Entry vs. Patient Pullback).

### 4. Advanced Risk Management
- **Stop After Win**: Option to lock in daily profits by stopping trading after hitting a target.
- **Max SL Cap**: Automatically caps your stop loss distance for volatile setups.
- **MAE Heat Filter**: Kills a trade instantly if it takes too much heat (move against > 0.12%).

---

## ⚙️ Configuration Guide

### 🧱 Core Settings
*   **Entry Mode**:
    *   `Immediate`: Enters at Market as soon as the range breaks. High risk, high reward.
    *   `Pullback (Wait for Close)`: Waits for price to return to your level (0%, 25%, 50%) and confirm with a close. Safe & Precise.
    *   `Pullback + Fallback`: Tries for a pullback first. If price runs away (timeout), it enters at Market to catch the move.
*   **Trigger Mode**:
    *   `Standard`: Breakout = Candle CLOSE outside range.
    *   `Aggressive`: Breakout = Candle WICK touches outside.
    *   `Displacement`: Breakout = Candle CLOSE +/- Buffer (0.10%).

### 🛡️ Risk & Filters
*   **Use Regime Filter**: Connects to Daily chart. Only takes Longs if Daily Close > SMA20.
*   **Use VVIX Filter**: Avoids execution if volatility is too high (VVIX > 115).
*   **Max Range %**: Skips the day if the 9:30 candle is massive (>0.25% of price), indicating a chop/whipsaw day.

### 🎯 Exit Management
*   **TP1 / TP2**: Set your partial profit targets.
*   **Runner Mode**:
    *   `Trailing`: Uses a percentage trail to follow the trend.
    *   `Forever`: Holds until the end of session (15:55 ET).
*   **Sig Candle Exit**: Emergency exit if price reverses continuously past the breakout candle.

---

## 🎨 Visual Legend
*   **🟡 Yellow Candle**: The 09:30 Opening Range bar.
*   **🔵 Cyan Candle**: The bar that triggered the Breakout signal.
*   **🟢 Lime "⚡"**: A "Fallback" entry (chasing a runaway move).
*   **🔴 Red Box**: 09:30 Range was too big (Filter Active).
*   **Bg Color**: Green (Long) / Red (Short) during active trades.

---

## ⚠️ Disclaimer
This strategy is for educational purposes. Past performance is not indicative of future results. Always backtest with your own settings and data provider.
