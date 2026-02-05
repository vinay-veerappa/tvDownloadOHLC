# Mission Control Dashboard - PRD

**Version:** 1.1.0
**Author:** Claude (Antigravity)
**Last Updated:** 2026-02-03

---

## 1. Executive Summary

**Mission Control** is a unified, high-density trading dashboard designed to synthesize multiple data sources into a single, actionable interface. It serves as the "cockpit" for daily market analysis, consolidating Higher Time Frame (HTF) context, scenario-based "War Game" planning, real-time Candle Science projections, and hourly narrative feeds.

### 1.1 Core Goals
1.  **Single Source of Truth**: Eliminate the need to switch between multiple tabs/tools.
2.  **Professional Aesthetics**: A "Bloomberg Terminal" inspired design suitable for a premium newsletter and Discord distribution.
3.  **Modular & Expandable**: Built with collapsible "panels" to allow progressive disclosure of information.
4.  **Dual-Purpose Output**: Designed for both interactive use and static "snapshot" export for newsletters/Discord.
5.  **Interactive Deep-Dives**: Collapsible panels expand into detailed modals (see [POPUP_SPECIFICATION.md](./POPUP_SPECIFICATION.md)).

---

## 2. User Personas

| Persona | Description | Key Need |
| :--- | :--- | :--- |
| **The Daytrader** | Active intraday trader focused on NQ/ES. Needs quick, actionable bias. | Fast access to "War Game" scenario & 1H Feed. |
| **The Newsletter Subscriber** | Receives daily/weekly market briefings. Consumes content passively. | Clean, static, information-rich snapshot. |
| **The Researcher** | Deep-dives into specific statistical claims. Uses profiler & candle science. | Expandable panels with full historical data. |

---

## 3. Layout Wireframe

The dashboard follows a **"Bento Grid"** design pattern, optimized for a 16:9 aspect ratio.

```
+---------------------------------------------------------------------+
| HEADER: Date | Market State | Daily EM | Fuel | Neutral/Bull/Bear   |
+---------------------------------------------------------------------+
|                                                                     |
| +------------------+  +----------------------+  +------------------+|
| | HTF CONTEXT      |  | THE BATTLE (MODAL)   |  | CANDLE SCIENCE  ||
| | Weekly/Monthly   |  | Scenario Details     |  | 1H / 1D Projs   ||
| | Confidence %     |  | Sniper/Grinder Plan  |  | Edge Probability||
| +------------------+  +----------------------+  +------------------+|
|                                                                     |
| +------------------+  +----------------------+  +------------------+|
| | WAR GAME MATRIX  |  | MOD/LOD RADAR        |  | KEY LEVELS      ||
| | LT/LF/ST/SF %    |  | Timing Histograms    |  | From Profiler   ||
| +------------------+  +----------------------+  +------------------+|
|                                                                     |
| +------------------+  +----------------------+  +------------------+|
| | MARKET PROFILE   |  | 1M CHART (EMBED)     |  | HIT STATISTICAL ||
| | Session Statuses |  | TradingView Embed    |  | Streaks & Stats ||
| +------------------+  +----------------------+  +------------------+|
|                                                                     |
| +--------------------------------------+  +------------------------+|
| | 1H FEED / 3H NARRATIVE               |  | ECONOMIC CALENDAR     ||
| | Quarter Analysis, Stacking, Guidance |  | High-Impact Events    ||
| +--------------------------------------+  +------------------------+|
|                                                                     |
| FOOTER: TRIGGER ACTION (KILLSWITCH STATUS) | XLL SWITCH            |
+---------------------------------------------------------------------+
```

---

## 4. Component Specifications

### 4.1 Header Bar

| Element | Data Source | Description |
| :--- | :--- | :--- |
| **Date & Time** | System Clock (NY TZ) | Current Date & Timestamp. |
| **Market State** | `live_chart_{ticker}.json` | "HISTORICAL" (stale data) or "LIVE" (streaming). |
| **Daily EM** | Prisma `ExpectedMoveHistory` | Daily expected move from options chain. |
| **Fuel (Distro)** | Session Median Range (see 4.6) | `Current Range / Median Range * 100`. |
| **Bias Badge** | `[PLACEHOLDER]` | NEUTRAL / BULL / BEAR based on consensus. |
| **🔄 Update Button** | Manual Trigger | Fetches latest data from Schwab API → Live Storage (JSON chunks). |
| **📤 Publish Button** | Manual Trigger | Screenshots dashboard and posts to Discord. |

---

### 4.2 HTF Context Panel

**Purpose**: Top-down directional context from Weekly and Monthly timeframes.

| Sub-Element | Data Source | Logic |
| :--- | :--- | :--- |
| **Confidence %** | `[PLACEHOLDER]` | % of HTF timeframes (1D, 1W, 1Mo) in agreement. |
| **Range & Breakout** | Profiler (`profiler.json`) | Is week Inside/Outside previous week? |
| **Weekly Structure** | `analyze_weekly_profile.py` | "Range Bound", "Expansion", "Consolidation". |
| **Monthly Structure** | `[PLACEHOLDER]` | PM High/Low status vs. current price. |

**Expandable Detail**:
- **Weekly Modal**: Chart embed with Bridge Anchors (Sunday/Tuesday), Variance Gauge, Key Levels (5 EMA, 1% Target).
- **Monthly Modal**: Climate Map (Daily chart), Flight Checklist (NFP Position, PM 30% Bull/Bear Levels).

---

### 4.3 Integrated Mission Matrix

**Purpose**: The central command deck minimizing screen real estate by combining **Probabilities**, **Timing**, and **Regime Context** into a single high-density view.

**Data Fusion**:
1.  **Regime Context (Header)**: Displays current Asia/London status and active Streaks (e.g., "London: Short True (2 Day Streak)").
2.  **Outcome Probabilities (Rows)**: Long/Short True/False derived from the Regime Context filter.
3.  **HOD/LOD Radar (Columns)**: "Time" columns in the matrix replace the separate Radar panel, showing the **Mode Time** for each specific outcome.

**Layout Specification**:

**A. Header: Context & Streaks**
> "Context: ASIA [Long True] | LONDON [Short False]"
> "Regime: NY Breakout [2 Day Streak] (Max: 4). Reversion Risk: MEDIUM."

**B. The Matrix (Main Table)**
| Scenario | Prob | Count | Bias | LOD Time | HOD Time | Avg HOD % | Avg LOD % | Key Level Hits |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Long True** | **45%** | 12 | 🟩 | 09:45 | 10:30 | +0.85% | -0.12% | PDH (80%) |
| **Long False** | 15% | 4 | 🟥 | 10:30 | 09:45 | +0.32% | -0.45% | NY Open (90%) |
| **Short True** | 10% | 3 | 🟥 | 11:00 | 10:15 | -0.15% | -0.92% | PDL (85%) |
| **Short False** | 30% | 8 | 🟩 | 10:00 | 11:00 | +0.55% | -0.55% | Mid (70%) |

*Columns Explained*:
- **Scenario**: The 4 possible NY outcomes.
- **Prob**: % chance based on filtering historical days with *matching* Asia/London profiles.
- **LOD/HOD Time**: The *Mode Time* (most frequent) for the HOD/LOD.
- **Avg HOD % / LOD %**: The average percentage distance from the Day Open.
    > **RULE**: Must use **Unadjusted Data** (Raw Contract Prices) for percent calculations to ensure accurate historical comparisons. Do not use continuous/back-adjusted contract data which distorts percentage moves.
- **Key Level Hits**: Probability of touching institutional levels (PDH, PDL, Midpoints).

**C. Visual & Display Rules**:
- **Dominant Scenario**: Highlight row with highest probability (Gold/Glow border).
- **Bias Color**: Green for Net Bullish (> +0.1%), Red for Net Bearish (< -0.1%).
- **HOD/LOD Intensity**: Bold text if % > 0.75% (Expansion Day).

---

### 4.4 The Battle Modal

**Purpose**: The detailed "Mission Briefing" for the current trading session.

| Section | Content | Data Source |
| :--- | :--- | :--- |
| **THE BRIEFING** | Narrative summary of the day's thesis. | AI-Generated / Template |
| **THE SNIPER** | Long entry plan with targets & confirmation criteria. | `[PLACEHOLDER]` |
| **THE GRINDER** | Short entry plan with targets & invalidation. | `[PLACEHOLDER]` |
| **EXECUTION SCRIPT** | Numbered sequence of actions (Do/Don't). | Template |
| **HTF CONTEXT** | Weekly/Monthly reminder if market is structureless. | `analyze_weekly_profile` |
| **CANDLE SCIENCE (HTF)** | Directional probability from 1D C3 projection. | `CandleScience` |
| **LTF GUIDANCE** | 05 Box, Hourly Quarter notes. | `QuarterlyStats`, `[PLACEHOLDER]` |
| **TACTICAL RISK PROFILE** | "LOW/MEDIUM/HIGH" conviction + "QUARTER/FULL" sizing. | `[PLACEHOLDER]` |

---

### 4.5 [Merged into Matrix]

---

### 4.6 Fuel (Distribution) Panel

**Purpose**: Volatility context based on recent price action, segmented by session and day of week.

![Distro Reference](distro_reference.png)

#### Calculation Logic

| Metric | Calculation | Notes |
| :--- | :--- | :--- |
| **Trading Day** | 18:00 ET (Prev Day) to 17:00 ET (Curr Day) | **CRITICAL**: Sunday 18:00 merges into Monday session. |
| **Current Range** | `Session High - Session Low` | Developing range for current session. |
| **Median N-Day Range** | `Median(Last N Completed Sessions)` | **Excludes** current developing session to avoid skew. |
| **Fuel %** | `(Current Range / Median Range) * 100` | Volatility consumption metric. |

#### 4.6.2 Session Windows (EST)

Each session is divided into three functional windows strictly following the Profiler "Design Rules":

| Session | Reference Window | Status Window | Broken Window |
| :--- | :--- | :--- | :--- |
| **Asia** | 06:00 PM - 07:29 PM | 07:30 PM - 02:29 AM | 02:30 AM - 05:00 PM |
| **London** | 02:30 AM - 03:29 AM | 03:30 AM - 07:29 AM | 07:30 AM - 05:00 PM |
| **NY1** | 07:30 AM - 08:29 AM | 08:30 AM - 11:29 AM | 11:30 AM - 05:00 PM |
| **NY2** | 11:30 AM - 12:29 PM | 12:30 PM - 04:59 PM | 06:00 PM - 05:00 PM (Next Day) |

#### 4.6.3 Status Determination Logic (Break-Order)

Status is classified based on whether price breaks the **Reference Window's** High/Low during the **Status Window**:

- **Long True (1)**: Price broke **High** ONLY.
- **Long False (2)**: Price broke **High** FIRST, then broke **Low**.
- **Short True (3)**: Price broke **Low** ONLY.
- **Short False (4)**: Price broke **Low** FIRST, then broke **High**.
- **Neutral (0)**: No sides broken.

#### 4.6.4 "Broken" Status

A session is marked as **Broken** if price touches its **Midpoint** (High+Low)/2 during its specific **Broken Window**.

- **Constraint**: The "Broken" flag is only evaluated *after* the session's Status Window has concluded.
- **Active Session Rule**: An active session cannot be "Broken". It is considered `Broken: False` until the window closes.
- **NY2 Exception**: The "Broken Window" for NY2 starts at 18:00 (Next Cycle). Therefore, NY2 can **never** be "Broken" during the current trading day.

#### 4.6.5 Matrix Filtering Logic (`f_match`)

The Mission Matrix identifies "Twin Days" by matching the current day's profile against historical data:

1.  **Session Status Filtering**:
    *   **Strict Matching**: Historical sessions must match the Live session status *exactly*.
    *   **Pending Sessions**: If Live is Pending (e.g., Active), status is treated as the *current state*. (e.g., Live "Long True" matches Historical "Long True").

2.  **"Broken" Filtering**:
    *   **If Live Session is BROKEN**: Filter *strictly* for historical days that were also Broken.
    *   **If Live Session is NOT BROKEN** (or Pending): Do **NOT** filter by the Broken attribute. Allow historical days to be either Broken or Not Broken. (Loose Matching).

#### 4.6.6 Streak Calculation Logic

Streaks track the momentum of regimes:
1.  **Ignore Broken**: The "Broken" status is ignored for streak calculation.
2.  **Individual Streaks**: Tracks runs of identical status (e.g., 3 days of "Long True").
3.  **Group Streaks**: Tracks runs of the same *Side* (True vs False).
    - `Long True` + `Short True` = **TRUE Group**.
    - `Long False` + `Short False` = **FALSE Group**.

#### Analysis Settings
- **Lookback**: 10 Trading Days (Global), 16 samples (Day-Specific Sessions).
- **Day Filtering**: Statistics are calculated per **Day of Week** (e.g., Wednesday stats only use historical Wednesdays).

---

### 4.7 Candle Science Panel
**Purpose**: Probabilistic C3 projections for **Daily (1D) timeframe only**.

> [!NOTE]
> **Mode Detection**: Automatically determines if analysis is for:
> - **Current Day (Live)**: Uses incomplete C3 data, projects forward.
> - **Historical Day**: Uses complete C1-C2-C3 triplet for pattern matching.

| Element | Data Source |
| :--- | :--- |
| **Bullish/Bearish %** | `calculator.ts` |
| **C3 vs C2 Positions** | `calculator.ts` (Open vs High, High vs Low, etc.) |
| **Pattern Match** | Filtered by current C1/C2 context. |

**Expandable Detail**: Full Candle Science modal with chart and probability table.

---

### 4.8 1H / 3H Narrative Feed

**Purpose**: Real-time textual narrative for the current hour.

| Element | Data Source |
| :--- | :--- |
| **Quarter Breakdown** | `hourly_quarter_stats.json` |
| **Projection** | Template: "Expect Q1 to set the [High/Low] of the hour." |
| **Narrative** | Template: Contextual notes (e.g., "If Q1 Low holds, look for continuation."). |
| **Stacking Analysis** | ICT-based checklist (H2 Above HTL, etc.). |

---

### 4.9 [Merged into Matrix]

---

### 4.10 Economic Calendar

**Purpose**: High-impact news events for the current day.

| Element | Data Source |
| :--- | :--- |
| **Event List** | `EconomicEvent` (Prisma) |
| **Impact Level** | HIGH / MEDIUM / LOW |

---

## 5. Data Source Mapping

| Data Point | Source File / Service | Notes |
| :--- | :--- | :--- |
| Session Statuses | `{ticker}_profiler.json` | `status_ts`, `long_true`, `short_true` flags. |
| Daily HOD/LOD | `{ticker}_daily_hod_lod_unadjusted.json` | **Unadjusted** for % moves. |
| Quarterly Stats | `hourly_quarter_stats_{ticker}.json` | Q1-Q4 distribution, breakout dynamics. |
| Candle Science | `calculator.ts` (live) / `candle_science_service.py` (backtest) | C3 projections. |
| Daily Classification | `{ticker}_daily_classification.parquet` | R1, R2, DWP, DNP types. |
| Daily Expected Move | Prisma `ExpectedMoveHistory` | Straddle-based EM. |
| Economic Events | Prisma `EconomicEvent` | FOMC, NFP, CPI, etc. |
| Weekly Profile | `analyze_weekly_profile.py` (output) | Inside/Outside week, Bridge Anchors. |
| ICT Gaps | `ict_nwog_ndog.json` | NWOG/NDOG levels. |
| Key Levels | Profiler / `ny_levels_stats.json` | 5 EMA, 1% Target, Green/Red Box. |

---

## 6. Analysis Logic - Detailed Specifications

### 6.1 HTF Context: EMA & Weekly Profile Analysis

**Purpose**: Define Overbought/Oversold volatility zones based on **Weekly** deviations from the 5-EMA.

> [!NOTE]
> **Data Source**: Weekly Aggregation (Friday Close).
> **Anchor**: Previous Week's 5-EMA.

![EMA Zone Analysis Reference](ema_zone_analysis_reference.png)

#### Calculation Method
1. **Timeframe**: **WEEKLY** (Fri-Fri alignment).
2. **Anchor**: `EMA(Close, 5)` of the **Previous Week**.
3. **Zones**:
   - **Zone 1 (2-3%)**: `Anchor * 1.02` to `Anchor * 1.03`
   - **Zone 2 (2.5-3%)**: `Anchor * 1.025` to `Anchor * 1.03`

### 6.1 HTF Context: EMA & ICT Weekly Profiles

**Purpose**: Synthesize statistical volatility (EMA) with ICT structural narratives to predict the "Shape of the Week".

![EMA Zone Analysis Reference](ema_zone_analysis_reference.png)

#### A. EMA Zones (Volatility Context)
**Data Source**: Weekly Aggregation (Friday Close), Anchor = Prev Week EMA(5).

| Metric | Calculation | NQ Thresholds |
| :--- | :--- | :--- |
| **Zone 1 (Standard)** | `Anchor * 1.02` to `Anchor * 1.03` | Entry: 67% \| Complete: 71% |
| **Zone 2 (Extreme)** | `Anchor * 1.025` to `Anchor * 1.03` | Entry: 30% \| Complete: 86% |

#### B. ICT Weekly Profiles (Structural Context)
**Concept**: Determines the likely "Power Day" and "Liquidity Run" based on the **Opening Price**, **Day of Week**, and **Upcoming News**.

**Key Inputs**:
1.  **Weekly Open**: Price at Sunday 18:00 ET.
2.  **Manipulation Zone**: Price movement *against* the HTF Bias early in the week (Mon/Tue).
3.  **News Driver**: `is_nfp_week` or `is_fomc_week`.

**Profile Types & Logic**:

| Profile Name | Context / Trigger | Expected Behavior |
| :--- | :--- | :--- |
| **Classic Tuesday Low/High** | **Trend Week**. Mon/Tue trades *opposite* to trend. | Low/High of week forms on **Tuesday**. Wednesday/Thursday expands in trend direction. |
| **Mid-Week Reversal** | **Tuesday Consolidation**. Failed breakout Tue. | Low/High of week forms on **Wednesday** (often NY session). Target: Previous Week Extreme. |
| **NFP Consolidation** | **NFP Week**. Mon-Wed range is < 50% of ADR. | Market holds inside range until Friday 08:30. "Stacking Orders". Expect Friday Expansion. |
| **Seek & Destroy** | **Range Bound**. Sweeps both Mon Low and Mon High. | Broadening formation. Target: External Range Liquidity on both sides. |

#### C. The Weekly Narrative (Algorithm)
The system produces a dynamic narrative string based on the current day and profile status.

**Logic Map**:
1.  **IF** `Day == Tuesday` **AND** `Price < Weekly Open` **AND** `Bias == BULLISH`:
    *   *Narrative*: "Potential JUDAS SWING. Watch for Tues Low formation to confirm Classic Buy Week."
2.  **IF** `Day == Wednesday` **AND** `Tuesday == Inside Day`:
    *   *Narrative*: "Volatility delayed. Expect Wednesday Expansion (Mid-Week Reversal profile)."
3.  **IF** `is_nfp_week == TRUE` **AND** `Day < Friday`:
    *   *Narrative*: "NFP Protocol: Expect lower volatility/manipulation until Friday release. Respect local ranges."

#### Data Sources
- **EMA Stats**: `volatility_stats.json`
- **Calculation**: `analyze_weekly_profile.py`
- **Live Context**: `live_chart_{ticker}.json` (for current price vs Weekly Open)

### 6.2 ICT Premium/Discount Multi-Timeframe Analysis

**Purpose**: Show current price position relative to Premium/Discount zones across multiple timeframes.

![Premium Discount Reference](premium_discount_reference.png)

#### Concept
- **Premium Zone** (upper 50% of range): Price is "expensive" - favorable for shorts.
- **Discount Zone** (lower 50% of range): Price is "cheap" - favorable for longs.
- **Equilibrium** (50% level): Fair value / decision point.

#### Timeframes (Configurable)
| Timeframe | Range Definition | Note |
| :--- | :--- | :--- |
| Weekly | Previous Week High/Low | Anchor range |
| Daily | Previous Day High/Low | Primary context |
| 4H | Last 4H candle range | Intermediate |
| 1H | Last 1H candle range | Short-term |
| 15m | Last 15m candle range | Micro context |

> [!NOTE]
> Timeframes are configurable and can be adjusted later for relevance.

#### Dashboard Display (Tabular)
| Timeframe | Range High | Range Low | 50% (EQ) | Current Price | Zone | % of Range |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Weekly | 26,600 | 25,100 | 25,850 | 25,500 | DISCOUNT | 26.7% |
| Daily | 25,800 | 25,300 | 25,550 | 25,500 | DISCOUNT | 40.0% |
| 4H | ... | ... | ... | ... | ... | ... |

#### Pop-Out Chart View
- Base chart: 1H timeframe
- Overlay boxes for each HTF range showing Premium (green) / Discount (red)
- Nested boxes similar to reference image
- Current price line clearly visible

#### Implementation Notes
- **Modular Design**: Timeframe list should be easily configurable.
- **Data Source**: Calculate from `public/data/{ticker}_{tf}/chunk_*.json`.
- **Output**: Aggregated via `MissionControlService`.

### 6.3 ICT Daily Bias (TBD)

> [!NOTE]
> **TBD** - User will define the ICT Daily Bias logic.

- [ ] **Bias Calculation**: How is daily bias (LONG/SHORT/NEUTRAL) determined?
- [ ] **Confirmation Criteria**: What confirms the bias?
- [ ] **Invalidation Rules**: When is bias invalidated?

### 6.4 NQStats / ALN Elements
- [ ] **Session-Specific Probabilities**: Integration of ALN London/NY/Asian-specific stats.
- ~~[ ] **Noon Curve**: Integration of 75% "opposite side" logic.~~ **REMOVED** (too late for actionable use).
- [ ] **9AM Judas**: Integration of 9:30-9:40 sweep reversal probability.

### 6.3 War Game Logic
> [!NOTE]
> **TBD** - User will provide detailed definition.

- [ ] **Scenario Activation Criteria**: What determines if "Long TRUE" vs "Long FALSE" is currently active?
- [ ] **Conviction Score**: How is "LOW / MEDIUM / HIGH" calculated?

### 6.4 Narrative Generation
- [ ] **AI vs. Template**: Should the "Briefing" narrative be AI-generated (LLM call) or template-based?
- [ ] **Trigger Rules**: What conditions trigger specific narrative phrases?

### 6.5 Streak Tracking
- [x] **Streak Definition**: **RESOLVED** - Analyze last N days of history, count TRUE vs FALSE occurrences, track max streak and current streak to predict regime flip probability.
- [x] **Data Source**: Derived from `profiler.json` session statuses.
- [x] **Visualization**: Table format as shown in reference image (see Section 4.9).

---

## 7. Operational Modes

### 7.0 Manual Review Mode (Phase 1 - MVP)

> [!NOTE]
> Initial implementation prioritizes user review before publication.

| Action | Trigger | Behavior |
| :--- | :--- | :--- |
| **🔄 Update** | Button Click | 1. Calls Schwab API for latest OHLC. 2. Writes to `public/data/`. 3. Refreshes all dashboard panels. |
| **📤 Publish to Discord** | Button Click | 1. Sets "Snapshot Mode" (hides buttons, optimizes layout). 2. Takes 1920x1080 screenshot via Playwright. 3. POSTs image to Discord channel via webhook. |

**Rationale**: Allows user to verify dashboard accuracy before broadcasting. Future phases will add scheduling.

---

### 7.1 Interactive Dashboard
- Full Next.js application with expandable modals.
- Real-time data updates via WebSocket or polling.
- Route: `/dashboard/mission-control`

### 7.2 Newsletter Snapshot
- **Trigger**: Manual button or scheduled cron job.
- **Output**: High-resolution PNG (1920x1080).
- **Method**: Playwright screenshot of "Snapshot Mode" (hides interactive elements, optimizes layout for static viewing).

### 7.3 Discord Post
- **Trigger**: After Newsletter Snapshot generation.
- **Method**: Use `discord_notifier` skill to POST image to channel via webhook.
- **Bonus**: Attach Markdown summary as text content.

---

## 8. Implementation Phases

| Phase | Description | Priority |
| :--- | :--- | :--- |
| **Phase 1** | Finalize PRD, resolve all `[PLACEHOLDER]` items. | **NOW** |
| **Phase 2** | Build `MissionControlService` data aggregator. | High |
| **Phase 3** | Implement UI layout with dummy data. | High |
| **Phase 4** | Bind UI to live data engine. | Medium |
| **Phase 5** | Implement Snapshot Mode & Discord integration. | Medium |

---

## 9. Open Questions for User

> [!CAUTION]
> Please provide clarification on the following items before implementation proceeds.

### TBD - User Will Define
1.  **War Game Activation**: How do I determine which of the 4 scenarios (Long TRUE, Long FALSE, etc.) is "active" for the current day? *(User will provide detailed definition)*
2.  **Conviction Score Logic**: What inputs determine LOW/MEDIUM/HIGH conviction? *(User will provide detailed definition)*

### Pending ICT Session
3.  **5-Day EMA**: Calculation method (Close? OHLC4?) and display format.
4.  **1% Target**: Definition (1% of what? Previous close? ATR?).
5.  **Green Box / Red Box**: Specific price levels and calculation logic.

### Resolved ✅
- ~~**Midnight Open / True Day Open**~~: **00:00 EST** (same thing).
- ~~**Streak Definition**~~: Analyze last N days, count TRUE/FALSE, track max/current streak for regime flip probability.

### Low Priority (Refinement)
6.  **Narrative Generation**: Should the "Briefing" text be AI-generated (LLM call) or rule-based templates?
7.  **Confidence % Logic**: How is the HTF Trinity confidence calculated (simple alignment or weighted)?

---

## Appendix: Reference Screenshots

![Main Dashboard](uploaded_media_1770164649875.png)

![The Battle Modal](uploaded_media_0_1770165313171.png)

![War Game Detail](uploaded_media_1_1770165313171.png)

![Weekly Modal](uploaded_media_2_1770165313171.png)

![Monthly Modal](uploaded_media_3_1770165313171.png)

![Candle Science Modal](uploaded_media_4_1770165313171.png)

![Distro Reference Table](distro_reference.png)

![Streak Analysis Reference](streak_reference.png)


---

## 11. Popup Specifications (Appended)

### 11.1 Unified Modal Framework
All popups use the `MissionModal` wrapper for a consistent "Terminal" aesthetic.
- **Background**: `hsl(222, 47%, 4%)` (Ultra-dark navy) with 80% backdrop blur.
- **Borders**: `1px solid hsl(222, 47%, 16%)`.
- **Header**: Monospace Title, Close Icon (X), and "Last Update" timestamp.
- **Animation**: Gentle "Fade + Scale In" from center.

### 11.2 The Battle (War Game) Modal
**Purpose**: High-conviction execution script for the day's primary scenario.
- **Left Column**: Briefing (Why) + Script (If/Then rules).
- **Right Column**: Visual Path (Professional Chart) with Blue Path Line, Red Invalidation Zone, and Target Bubbles.

### 11.3 HTF Context Modal
**Purpose**: Detailed structural mapping.
- **Weekly View**: Bridge Anchor Chart showing Sunday Open and Tuesday Range (Blue Box). Volatility Gauge (Needle).
- **Monthly View**: Climate Map (Heatmap of daily returns) + Flight Checklist.

### 11.4 Candle Science Modal
**Purpose**: Statistical deep dive.
- **Projection Heatmap**: Horizontal BarChart colored by confidence.
- **Level Table**: High-density table for C3 High/Low Projections.

### 11.5 Implementation Standards
1.  **Monochrome Defaults**: Slate/Gray for non-essential lines.
2.  **High Contrast Accents**: Emerald (Bull), Rose (Bear), Sky (Info).
3.  **Typography**: `JetBrains Mono` or `Roboto Mono`.
4.  **Read-Only**: Charts should be snapshots with clear tooltips.
