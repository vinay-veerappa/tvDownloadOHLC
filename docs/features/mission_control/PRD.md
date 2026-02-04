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
| | HTF TRINITY      |  | THE BATTLE (MODAL)   |  | CANDLE SCIENCE  ||
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

### 4.2 HTF Trinity Panel

**Purpose**: Top-down directional context from Weekly and Monthly timeframes.

| Sub-Element | Data Source | Logic |
| :--- | :--- | :--- |
| **Confidence %** | `[PLACEHOLDER]` | % of HTF timeframes (1D, 1W, 1Mo) in agreement. |
| **Range & Breakout** | Profiler (`profiler.json`) | Is week Inside/Outside previous week? |
| **Weekly Structure** | `analyze_weekly_profile.py` | "Range Bound", "Expansion", "Consolidation". |
| **Monthly Structure** | `[PLACEHOLDER]` | PM High/Low status vs. current price. |

**Expandable Detail**:
- **Weekly Modal**: Chart embed with Bridge Anchors (Sunday/Tuesday), Variance Gauge, Key Levels (5 EMA, 1% Target).
- **Monthly Modal**: Climate Map (Daily chart), Flight Checklist (NFP Position, PM 50%, Month Color).

---

### 4.3 War Game Matrix

**Purpose**: Scenario-based probability analysis. What happens if X?

| Scenario | Description | Data Source |
| :--- | :--- | :--- |
| **Long TRUE** | Asia/London bullish, NY follows through. | `DailyClassification` + `Profiler` |
| **Long FALSE** | Asia/London bullish, NY reverses. | `DailyClassification` + `Profiler` |
| **Short TRUE** | Asia/London bearish, NY follows through. | `DailyClassification` + `Profiler` |
| **Short FALSE** | Asia/London bearish, NY reverses. | `DailyClassification` + `Profiler` |

**Panel Content (per scenario)**:
- Probability %.
- Median HOD/LOD Times (Histogram).
- Daily High/Low Distribution (Histogram).
- Level Hits (NY1 Mid, NY1 High, NY Open, NY1 Low).
- Price Path (Overlay chart).

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

### 4.5 MOD/LOD Radar

**Purpose**: Statistical timing for the daily High and Low.

> [!NOTE]
> **Uses Unadjusted Data** for HOD/LOD price percentage moves to ensure accurate historical comparison.

| Element | Data Source |
| :--- | :--- |
| **HOD Mode/Median** | `{ticker}_daily_hod_lod_unadjusted.json` |
| **LOD Mode/Median** | `{ticker}_daily_hod_lod_unadjusted.json` |
| **Timing Histogram** | Derived from unadjusted HOD/LOD data (30m buckets). |

---

### 4.6 Fuel (Distribution) Panel

**Purpose**: Volatility context based on recent price action, segmented by session and day of week.

![Distro Reference](distro_reference.png)

#### Calculation Logic

| Metric | Calculation |
| :--- | :--- |
| **Current Session Range** | `Session High - Session Low` (for current session). |
| **Median N-Day Range** | `Median(Last N Session Ranges)` for the **same session type AND day of week**. |
| **Fuel %** | `(Current Range / Median Range) * 100` |
| **Consumed %** | `(Current Range / Daily Median Range) * 100` |

#### Session Types
| Session | Time (NY) |
| :--- | :--- |
| **ASN (Asia)** | 18:00 - 02:00 |
| **LDN (London)** | 02:00 - 08:00 |
| **NY1** | 09:30 - 12:00 |
| **NY2** | 12:00 - 16:00 |
| **09:30-10:00** | First 30m of RTH |

#### Configurable Lookback
- **Default**: 10 days
- **Alternative**: 5 days (user toggle)

#### Day of Week Filtering
- Statistics are calculated **per day of week** (e.g., Monday NY1 vs. Monday NY1).

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

### 4.9 Session Regime & Streak Panel

**Purpose**: Historical regime analysis showing TRUE/FALSE distribution and streak probability for each session.

![Streak Reference](streak_reference.png)

#### Per-Session Statistics
| Metric | Description |
| :--- | :--- |
| **Days in History** | Total days analyzed for this session. |
| **Current State** | `FALSE_ACTIVE` or `TRUE_ACTIVE` - current regime. |
| **BO Direction** | Current breakout direction (LONG/SHORT). |
| **False %** | Historical % of sessions that were FALSE. |
| **True %** | Historical % of sessions that were TRUE. |
| **Max Streak (false)** | Longest consecutive FALSE streak in history. |
| **Max Streak (true)** | Longest consecutive TRUE streak in history. |
| **Current Streak** | Current consecutive streak (e.g., "2 days (true)"). |
| **Days w/ False** | Count of FALSE days in lookback. |
| **Days w/o False** | Count of TRUE days in lookback. |

#### Historical MFE/MAE Percentiles
| Metric | Description |
| :--- | :--- |
| **Hist BO MFE 50%** | Median MFE for historical breakouts. |
| **Hist BO MFE 70%** | 70th percentile MFE. |
| **Hist BO MFE MAX** | Maximum MFE observed. |
| **Hist BO MAE 50%** | Median MAE (adverse excursion). |
| **Range Size** | Typical range as % of price. |

#### Today's Comparison
| Metric | Description |
| :--- | :--- |
| **TODAY BO MFE** | Today's breakout MFE vs historical. |
| **TODAY BO MAE** | Today's breakout MAE vs historical. |
| **TODAY false MFE/MAE** | Stats if today's session flips to FALSE. |

**Key Insight**: When `Current Streak` approaches `Max Streak`, probability of regime flip increases.

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

## 6. Analysis Logic - Pending Clarification

> [!IMPORTANT]
> The following logic blocks require further definition from the user before implementation.

### 6.1 HTF Context: EMA Zone Analysis

**Purpose**: One component of HTF context - define support/resistance zones based on historical hit rates from the Daily 5 EMA.

> [!NOTE]
> **TBD**: How to tie all HTF context elements together (EMA zones, weekly profile, monthly profile, etc.).

![EMA Zone Analysis Reference](ema_zone_analysis_reference.png)

#### Calculation Method
1. **Anchor**: Daily 5 EMA (calculated on Close).
2. **Zone Levels**: Calculate price levels at various % distances from EMA (0.5%, 1%, 1.5%, 2%, 2.5%, 3%, 3.5%, 4%, 5%).
3. **Hit Rate Analysis**: For each zone level, calculate:
   - **Hit Rate ↑**: % of weeks price touched this level moving UP from EMA.
   - **Hit Rate ↓**: % of weeks price touched this level moving DOWN from EMA.
   - **Status**: "Good" if hit rate above threshold, "Fail" otherwise.

#### NQ Sweet Spot: 2-3% Zone
Based on 52-week analysis:
- **Zone Entry**: 61.5% (price enters this zone)
- **Zone Complete**: 46.2% (price completes the move)
- **Completion Rate**: 72.7%

#### All Levels Hit Rate Table (NQ Example)
| Level % | Hit Rate ↑ | Hit Rate ↓ | Status |
| :--- | :--- | :--- | :--- |
| 0.5% | 86.7% | 55.8% | Good |
| 1% | 78.9% | 42.3% | Good |
| 1.5% | 73.1% | 34.5% | Fail |
| 2% | 63.3% | 30.8% | Fail |
| 2.5% | 55.8% | 25% | Fail |
| 3% | 46.2% | 19.2% | Fail |

#### Day of Week Analysis
Hit rates vary by day:
| Day | HR ↑ | HR ↓ | Comp ↑ | Comp ↓ |
| :--- | :--- | :--- | :--- | :--- |
| Mon | 42.3% | 19.2% | 36.5% | 21.2% |
| Tue | 57.7% | 25% | 40.4% | 26.9% |
| Wed | 61.5% | 34.6% | 50% | 30.8% |
| Thu | 46.2% | 26.9% | - | 26.9% |

#### Opening Position Context
- **Opened Above EMA**: 68.8% of weeks
- **Opened Below EMA**: 31.2% of weeks

#### Dashboard Display
- Show current price position relative to Daily 5 EMA.
- Highlight the 2-3% zone as "target zone".
- Color code based on current hit rate probability.

#### Data Source
- Calculated from `public/data/{ticker}_1d/chunk_*.json`.
- Uses `parquet-reader.ts` (JSON implementation).

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

![EMA Zone Analysis](ema_zone_analysis_reference.png)
