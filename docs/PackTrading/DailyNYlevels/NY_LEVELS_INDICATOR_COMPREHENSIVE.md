# Daily New York Levels Indicator: Comprehensive Specification

This document consolidates the philosophy, requirements, technical design, and visual specifications for the **Daily New York Levels Indicator**.

## 1. Core Philosophy
The indicator is designed to capture high-probability price extensions occurring during the first few hours of the New York cash session. It focuses on the **09:30 - 12:00 PM EST** window, identifying where price "prefers" to trend relative to the initial opening range.

### Key Targets:
- **Cashflow Zone**: Price extensions of **0.1% - 0.3%** from the 9:30 range boundary. These are high-frequency targets used for scalp taking.
- **Extended Target Zone**: Extensions greater than **0.3%**, usually occurring in 20-30% of trading days.

---

## 2. Technical Requirements

### Trading Window & Cutoff
- **Start Time**: 09:30 AM EST (NY Open).
- **Cutoff Time**: 12:00 PM EST (Hard cutoff for statistics and level generation).
- **Core Pivot**: The **09:30 - 09:31 1-minute Opening Range (OR)** high and low.

### Critical Timing Architecture (Futures)

> [!IMPORTANT]
> For futures instruments (NQ, ES, etc.), the `is_new_day` event fires at **end of trading session** (~16:16-17:00 EST), NOT at midnight or 09:30. This creates a critical timing consideration for commit logic.

**Correct Timing Flow:**
```
09:30 AM: Reset is_committed_today = false, Set Opening Range
09:31-11:59 AM: Calculate MFE, update daily_peak_time
12:00 PM: is_at_or_after_cutoff becomes true → COMMIT data to history
12:01+ PM: is_committed_today = true, no more commits
~16:16 PM: is_new_day fires, reset daily values to 0 (for next day)
```

**Key Design Decisions:**
- `is_committed_today` is reset at **09:30** (start of trading session), NOT at `is_new_day`
- Commit condition includes `and not is_new_day` to prevent committing reset values
- MFE calculation skips the 09:30 bar itself (`and not is_0930`) since that's when the OR is set

### Distribution Logic

- **MFE (Max Favorable Excursion)**: The maximum price extension reached during a breakout relative to the OR boundary.
- **Percentile-Based Levels**: Levels are generated based on historical distributions (e.g., the 50th percentile level shows where price reached 50% of the time).

### Multi-Breakout Tracking (v2.0)

> [!IMPORTANT]
> The indicator tracks **ALL breakouts**, not just the daily maximum. Each complete breakout cycle is recorded separately.

**Breakout Definition:**
- **Bull Breakout**: Starts when `high > OR_high`, continues while price stays above OR
- **Bear Breakout**: Starts when `low < OR_low`, continues while price stays below OR

**Breakout End Condition (Critical):**
- **Bull breakout ends** when candle **CLOSES below OR_low** (opposite side breach)
- **Bear breakout ends** when candle **CLOSES above OR_high** (opposite side breach)
- **At Cutoff (12:00 PM)**: Any open breakouts are closed and committed

**Data Captured Per Breakout:**
- `mfe`: Peak percentage extension during the breakout
- `peak_time`: Minutes since 09:30 when peak occurred

**Why This Matters:**
- Multiple breakouts per day create more data points for statistical analysis
- Captures the full range traversal pattern, not just isolated peaks
- Matches reference indicator behavior more closely

---

### MFE Histogram Requirements (v2.2 - Dual Approach)

> [!IMPORTANT]
> The indicator uses TWO different tracking methods for different purposes.

**1. Reference Base (Both):**
- Use the **09:31 candle CLOSE** ±0.01% zone
- Bull reference = Close × 1.0001
- Bear reference = Close × 0.9999

**2. TIME Distribution Histogram:**
- Uses **Daily MAX MFE** (one value per day per direction)
- Tracks the TIME when the daily max was reached
- Commits both bull and bear MFE at 12:00 PM cutoff
- Bar width = count of days that peaked in that time bin

**3. PRICE Distribution Histogram (NEW):**
- Uses **All Pivot Highs/Lows** filtered by day direction
- Long days (MFE > MAE): Track all pivot highs
- Short days (MAE > MFE): Track all pivot lows
- Detection: Pivot = bar high/low > surrounding ±2 bars
- Creates more data points for smoother distribution
- Bar width = count of pivots that fell in each MFE bin

**4. Day Direction Classification:**
- At 12:00 PM cutoff, compare daily MAX bull MFE vs daily MAX bear MAE
- If bull MFE > bear MAE → **LONG day** → use pivot highs for price histogram
- If bear MAE > bull MFE → **SHORT day** → use pivot lows for price histogram

**5. Display Settings:**
- `binSize`: Controls price bin width (default 0.04%)
- `startPercentile`, `endPercentile`: Filter display range
- `histWidthScale`: Controls bar width scaling

---

## 3. UI & Visual Design

The indicator features a dense, information-rich UI designed for quick decision-making.

### Visual Components:
- **NY Opening Range Box**: A vertical zone highlighting the 9:30 candle.
- **MFE Distribution Profile**: 
    - Toggleable between **Box** (solid zones) and **Histogram** (distribution bars).
    - Colors represent Bullish (above OR high) and Bearish (below OR low).
    - **Refined Requirement**: Use TPO-style frequency buckets where bar width reflects the count of historical hits.

#### MFE Histogram Visual Standards:
````carousel
![Bullish MFE Close-up](media/mfe_hist_closeup_bull.png)
<!-- slide -->
![Bearish MFE Close-up](media/mfe_hist_closeup_bear.png)
````

- **MFE Time Distribution**: 
    - A vertical histogram showing the frequency of peak extension timing across the window.
    - Includes **AVG** and **Median** vertical dashed lines with labels.

#### Time Distribution Visual Standards:
![Refined Time Distribution](media/time_dist_refined.png)

### Mockup Reference:
![Indicator UI Mockup](media/indicator_mockup.png)

### User Settings & Inputs:
The indicator allows for granular control over colors, percentile steps (default 2%), and time buckets (default 5m).

![Indicator Settings](media/indicator_settings.png)

---

## 4. Statistical Distribution (Python Engine)

To support the indicator's logic, a background Python engine extracts historical metrics with flexible grouping (Monthly, Quarterly, Yearly).

### MFE Time Distribution reference:
![MFE Time Distribution](media/time_distribution.png)

### Core Metrics Captured:
- **OR 1m OHLC**: Base pivot points.
- **12:00 PM Close**: Market bias at the cutoff.
- **Max Bull/Bear Pts/Pct**: Magnitude of extension.
- **Time of Peak**: The exact minute (localized to NY) the day's peak was reached.

---

## 6. Insights from Transcript (Strategy Logic)

The following core logic was derived from the video training session:

- **Target Progression**: Start by targeting the **Cashflow Zone (0.1%-0.3%)**. If price shows strength beyond 0.3%, look for **Extended Targets**.
- **Stop Loss Strategy**: Use the 9:30 range boundary or a fixed percentage of the range (e.g. 75%) depending on the volatility.
- **Hard Exit**: All intraday positions are closed at **12:00 PM EST** regardless of profit/loss to avoid the lunch-time chop and reversal risks.
- **Bias Confirmation**: Look for the **MFE Time Distribution** to align your entry. If the peak extension typically occurs at 10:15-10:45 AM, avoid chasing moves after 11:30 AM.

---

## 7. TradingView Indicator Description

**Daily NY Levels V2** - A comprehensive NY session analysis indicator displaying Opening Range levels, MFE distribution histograms, and hit-time statistics.

### Key Features

**📊 Opening Range (OR)**
- Displays the 09:30-09:31 NY session opening candle
- Uses 1-minute MTF data for accuracy on all timeframes
- OR High/Low plotted with M1 projection lines (+0.01%)

**📈 MFE Price Distribution Histogram**
- Visualizes historical price extension distribution above/below the Opening Range
- Uses **pivot-based tracking** filtered by day direction (MFE > MAE = bullish days)
- Configurable reference base: "09:31 Close" or "OR High/Low"
- Fixed-bin histogram with percentile filtering (P20-P80 default)

**⏰ Hit Time Distribution**
- Shows when historical MFE targets were typically reached
- Displays AVG and Median time markers

### Settings Quick Reference

| Group | Setting | Description |
|-------|---------|-------------|
| **General** | Cutoff Time | Session end time (default 12:00) |
| **MFE Profile** | Reference Base | "09:31 Close" or "OR High/Low" |
| **MFE Profile** | Start/End Percentile | Filter histogram display range |
| **MFE Profile** | Bin Size (%) | Histogram bar granularity |

### Best Practices
- Works best on NQ, ES, SPY, QQQ during NY session (09:30-12:00 ET)
- Use "OR High/Low" reference for breakout strategies
- Use "09:31 Close" reference for fade/reversion strategies

---

## 8. Associated Files & Resources
- **PineScript v6**: [DailyNYLevelsV2.pine](file:///C:/Users/vinay/tvDownloadOHLC/scripts/indicators/DailyNYLevelsV2.pine)
- **Data Processor**: [precompute_opening_range.py](file:///C:/Users/vinay/tvDownloadOHLC/scripts/derived/precompute_opening_range.py)
- **Stats Analysis**: [precompute_ny_levels.py](file:///C:/Users/vinay/tvDownloadOHLC/scripts/derived/precompute_ny_levels.py)
- **Visualizer**: [visualize_ny_levels.py](file:///C:/Users/vinay/tvDownloadOHLC/scripts/analysis/visualize_ny_levels.py)
- **Strategy Notes**: [DailyLevelsIndicator_TP_Adjustments.md](file:///C:/Users/vinay/tvDownloadOHLC/docs/PackTrading/DailyNYlevels/DailyLevelsIndicator_TP_Adjustments.md)
