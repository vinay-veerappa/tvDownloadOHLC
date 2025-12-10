# The Daily Profiler - Replication Requirements

**Goal**: Replicate the statistical dashboard functionality found in "The Daily Profiler" (see screenshot below) to provide deep insights into session behavior, false breakouts, and daily high/low timing.

## 🖼️ Reference UI

![Daily Profiler Dashboard](media/profiler_dashboard.png)

---
## 📝 Statistical Logic Definitions

The following rules define the "Status" and "Broken" metrics used in the Profit Cards.

### 1. Definitions
*   **Session Range**: Based on the High/Low of the defined session hours.
    *   *Asia*: 18:00 - 19:30
    *   *London*: 02:30 - 03:30
    *   *NY1*: 07:30 - 08:30
    *   *NY2*: 11:30 - 12:30
*   **Next Start**: The start time of the *next* chronological session (e.g., for London, Next Start is 07:30/NY1).
*   **Mid**: The arithmetic mean of the Session High and Low.

### 2. "Status" Logic (The Play-Out)
*Window*: **Session End** to **Next Start**.
*   **True Long**: Price breaks **above** Session High and determines direction without breaking Session Low during the window.
*   **True Short**: Price breaks **below** Session Low and determines direction without breaking Session High during the window.
*   **False**: Price breaks **BOTH** Session High and Session Low in any order during the window.
*   **None**: Price remains completely **INSIDE** the Session Range during the window.

### 3. "Broken" Logic
*Window*: **Next Start** to **18:00** (Asia Start / End of Cycle).
*   **Broken (Yes)**: The Session **Mid** is touched or crossed by price at any point during this window.
*   **Broken (No)**: The Session Mid is respected (not touched) during this window.

---


### 4. Conditional Profiling (The "Wizard")
The dashboard must allow filtering historical data based on simple boolean inputs of prior events to predict the current session's outcome.

**Workflow:**
1.  **Select Context**: User inputs the status of completed sessions (e.g. Asia=True Long, London=False Short).
2.  **Filter Data**: System filters the historical dataset to find matching days.
3.  **Display Probabilities**: Shows the probability distribution of the *current* session's 4 outcomes based on that history.
    *   **Outcomes**: Long True, Short True, Long False, Short False.
4.  **Intra-Session Update**: User inputs "what has happened so far" in the current session (e.g. "NY1 has broken High") to further refine the probabilities.


### 1. Profiler Sessions (Statistical Cards)
For each major session (Asia, London, NY1, NY2), display:
*   **Direction Bias**: Percentage of time the session is Long vs Short.
*   **True/False Breakouts**: Stats on whether the initial move was sustained.
*   **Broken Stats**: Frequency of the session range being broken.
*   **Time Histograms**:
    *   **False Times**: Distribution of WHEN false moves occur.
    *   **Broken Times**: Distribution of WHEN the range is broken.

### 2. High and Low of Day (HOD/LOD) Analysis
*   **Timing Distributions**: Histograms showing the probability of the HOD or LOD forming at specific times of the day.
*   **Daily Low/High Distribution**: Visual representation of price levels where H/L often form.

### 3. Price Models
*   **Average Path**: Line charts showing the "typical" price action for each session (aggregated average movement).
*   **Volatility Models**: Expected range expansion over time.

---

## 🛠️ Implementation Strategy (Draft)

1.  **Backend (`/api/stats/profiler`)**:
    *   New endpoints to aggregate historical session data.
    *   Calculate histograms for "Time of High", "Time of Low", etc.
2.  **Frontend (`/profiler`)**:
    *   New page separate from the main Chart.
    *   Grid layout using Shadcn UI Cards.
    *   Charts using `Recharts` (better for bar/line charts than Lightweight Charts).
