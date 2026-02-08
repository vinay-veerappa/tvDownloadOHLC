# Pine Script Indicator Plan: ICT Session Probability Map [2026]

## 🎯 Objective
Create a TradingView indicator that automatically contextualizes the current session based on the deterministic probability maps generated from the 5,000+ day research.

---

## 🛠️ Core Features

### 1. Automated Session & Level Plotting
*   **Asia Range (19:30 - 00:00)**: Box High/Low + Midline.
*   **London Range (02:30 - 05:00)**: Box High/Low + Midline.
*   **NY Open (09:30)**: Horizontal Ray.
*   **Midnight Open (00:00)**: Horizontal Ray.
*   **PDC (Prev Day Close)**: Horizontal Ray.

### 2. Context Detection Engine (The Brain)
*   **London Classifier**:
    *   Detects if London High > Asia High AND London Low > Asia Low (`PARTIAL_UP`).
    *   Detects if London Low < Asia Low AND London High < Asia High (`PARTIAL_DOWN`).
    *   Detects sweeps of both (`ENGULFS`) or neither (`INSIDE`).
*   **Position Classifier**:
    *   Calculates `London Midpoint`.
    *   Compares `NY Open Price` vs `London Midpoint`.

### 3. Probability Dashboard (The Output)
*   **Dynamic Data Table** (Top Right):
    *   **Context**: "London Swept Low"
    *   **Alignment**: "Open > Mid"
    *   **Bias**: "BULLISH"
    *   **Target**: "London High"
    *   **Probability**: "89% (Tier 1)"
*   **Visual Magnet**:
    *   Draw a **Dashed Arrow/Line** from NY Open to the weighted target (e.g., London High).
    *   Color code based on probability:
        *   🟢 **> 75%** (High Conviction)
        *   🟡 **60-75%** (Contextual)
        *   ⚪ **< 60%** (Low Edge / Chop)

---

## 💻 Logic & Probability Tables (Hardcoded)

The indicator will contain a hardcoded look-up table for each Ticker (Input: `Ticker Selection`).

### Example Logic (Pseudocode):
```pinescript
// Inputs
symbol_type = input.string("NQ", ["NQ", "ES", "CL", "GC"])

// 1. Define London Context
london_swept_high = high[london_end] > asia_high
london_swept_low = low[london_end] < asia_low
context = "INSIDE"
if (london_swept_high and not london_swept_low) context := "PARTIAL_UP"
if (not london_swept_high and london_swept_low) context := "PARTIAL_DOWN"
if (london_swept_high and london_swept_low) context := "ENGULFS"

// 2. Define Alignment
ny_open_state = open[09:30] > london_mid ? "ABOVE" : "BELOW"

// 3. Lookup Probability (NQ Example)
prob_high = 0.0
if symbol_type == "NQ"
    if context == "PARTIAL_DOWN" and ny_open_state == "ABOVE"
        prob_high := 77.9 // Target London High
    if context == "PARTIAL_UP" and ny_open_state == "BELOW"
        prob_high := 23.8 // Target London Low (High prob for Low)
    // ... complete mapping from report
```

---

## 🎨 Visual Style Guide
*   **London Sweep**: Highlight the swept level with a small "X" or "Sweep" label.
*   **Un-Swept Magnet**: Highlight the opposing level with a "Magnet 🧲" icon if probability > 70%.
*   **Midline**: Dotted Grey line (The Pivot).
*   **Tables**: Clean, compact, minimal clutter.

---

## 🚀 Future Enhancements (Phase 2)
*   **Lunch Fade Alerts**: Highlight AM High/Low at 12:00 ET for potential reversals.
*   **PM Trend Projection**: At 13:30, project the AM Midline extension probabilities.
*   **PDC Radar**: During Asia, highlight PDC distance and "Magnet Strength".
