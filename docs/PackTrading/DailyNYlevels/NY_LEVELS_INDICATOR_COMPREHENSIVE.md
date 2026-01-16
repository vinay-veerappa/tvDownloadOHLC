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
- **MFE (Max Favorable Excursion)**: The maximum price extension reached between 09:30 and 12:00 relative to the 9:30 OR boundary.
- **Percentile-Based Levels**: Levels are generated based on historical distributions (e.g., the 50th percentile level shows where price reached 50% of the time).

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

## 7. Associated Files & Resources
- **PineScript v6**: [DailyNYLevelsV2.pine](file:///C:/Users/vinay/tvDownloadOHLC/scripts/indicators/DailyNYLevelsV2.pine)
- **Data Processor**: [precompute_opening_range.py](file:///C:/Users/vinay/tvDownloadOHLC/scripts/derived/precompute_opening_range.py)
- **Stats Analysis**: [precompute_ny_levels.py](file:///C:/Users/vinay/tvDownloadOHLC/scripts/derived/precompute_ny_levels.py)
- **Visualizer**: [visualize_ny_levels.py](file:///C:/Users/vinay/tvDownloadOHLC/scripts/analysis/visualize_ny_levels.py)
- **Strategy Notes**: [DailyLevelsIndicator_TP_Adjustments.md](file:///C:/Users/vinay/tvDownloadOHLC/docs/PackTrading/DailyNYlevels/DailyLevelsIndicator_TP_Adjustments.md)
