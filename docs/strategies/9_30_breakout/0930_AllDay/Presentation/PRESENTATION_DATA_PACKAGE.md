# 0930 ORB Strategy - Presentation Data Package
**Purpose**: Use this file with NotebookLM, Claude, or AI image generators to create professional presentation graphics.

---

# SECTION 1: RAW DATA

## 1.1 Backtest Performance (MNQ, Jan 2023 - Jan 2026)

| Metric | Value |
|--------|-------|
| Net Profit | $41,953.50 |
| Initial Capital | $3,000 |
| Return | 1,398% |
| Annualized Return (CAGR) | 146.9% |
| Total Trades | 3,085 |
| Winning Trades | 859 (27.8%) |
| Losing Trades | 1,491 |
| Even Trades | 735 |
| Avg Winning Trade | $106.62 (0.26%) |
| Avg Losing Trade | $33.29 (0.06%) |
| Win/Loss Ratio | 3.20x |
| Profit Factor | 1.85 |
| Largest Win | $925.50 |
| Largest Loss | $143.00 |
| Max Drawdown | $379 |

## 1.2 NQ1 Retest Forensics (4,045 events)

### Global Statistics
| Metric | Value |
|--------|-------|
| Win Rate | 81.8% |
| Avg MFE (Reward) | 0.45% |
| Avg MAE (Risk) | 0.03% |

### Hourly Performance Breakdown
| Hour | Volume | Win Rate | Median MFE | p75 MFE | p90 MFE | Median MAE |
|------|--------|----------|------------|---------|---------|------------|
| 09:00 | 3,331 | 81.2% | 0.32% | 0.63% | 1.07% | 0.00% |
| 10:00 | 438 | 85.4% | 0.25% | 0.52% | 0.92% | 0.00% |
| 11:00 | 108 | 84.3% | 0.18% | 0.40% | 0.64% | 0.00% |
| 12:00 | 61 | 80.3% | 0.21% | 0.43% | 0.79% | 0.00% |
| 13:00 | 33 | 75.8% | 0.15% | 0.26% | 0.71% | 0.00% |
| 14:00 | 36 | 86.1% | 0.14% | 0.30% | 0.37% | 0.00% |
| 15:00 | 37 | 89.2% | 0.07% | 0.24% | 0.45% | 0.00% |

### Best 5-Min Entry Windows (09:00 Hour)
| Window | Win Rate | Sample Size |
|--------|----------|-------------|
| 09:55 | 90.8% 💎 | 87 trades |
| 09:35 | 81.9% | 1,020 trades |
| 09:30 | 80.7% | 1,444 trades |
| 09:40 | 80.6% | 412 trades |

### Worst 5-Min Entry Windows
| Window | Win Rate | Warning |
|--------|----------|---------|
| 11:20 | 53.8% | ⚠️ Avoid |
| 12:10 | 50.0% | ⚠️ Avoid |
| 13:15 | 50.0% | ⚠️ Avoid |
| 14:25 | 50.0% | ⚠️ Avoid |

## 1.3 MAE Filter Impact Analysis

| Metric | Without MAE Filter | With MAE Filter (0.05%) |
|--------|-------------------|------------------------|
| Avg Loss | ~$60 | $33.29 |
| Win/Loss Ratio | ~2.0x | 3.20x |
| Profit Factor | ~1.3 | 1.85 |

**How MAE Filter Works:**
- Cut losing trades early when they show >0.05% adverse movement from range boundary
- Most winners never see more than 0.03% drawdown
- 90th percentile MAE is only 0.08% for winning trades

## 1.4 Multi-Ticker Comparison

| Ticker | Description | Win Rate Range | Notes |
|--------|-------------|----------------|-------|
| MNQ/NQ1 | Nasdaq Micro | 80-85% | Primary focus |
| MES/ES1 | S&P 500 Micro | 82-85% | Similar patterns |
| MYM/YM1 | Dow Micro | 80-83% | Steady performer |
| M2K/RTY1 | Russell Micro | 78-82% | More volatile |
| MCL/CL1 | Crude Oil Micro | 75-80% | Wider ranges |
| MGC/GC1 | Gold Micro | 76-82% | Longer hold times |

---

# SECTION 2: STRATEGY RULES

## 2.1 Entry Criteria
```
Asset: MNQ (Micro E-mini Nasdaq)
Timeframe: 1-minute
Trading Window: 9:31 AM - 3:45 PM ET

OPENING RANGE (OR):
- Use first 1-minute candle (9:30-9:31 AM)
- OR High = High of 9:30 candle
- OR Low = Low of 9:30 candle
- OR Height = OR High - OR Low

LONG ENTRY:
- Triggered when 1m candle CLOSES above OR High


SHORT ENTRY:
- Triggered when 1m candle CLOSES below OR Low


ADDITIONAL FILTERS:
- Range Filter: Skip if OR Height > 0.25% of price
- VVIX Filter: Skip if VVIX > 108 (extreme volatility)
```

## 2.2 Exit Criteria
```
MULTI-TP SYSTEM:
- TP1 (Quick Win): 0.10% from entry (~20 pts on NQ), exit 50% position
- TP2 (Runner): 0.25% from entry (~50 pts), exit remaining or trail

STOP LOSS:
- Primary: Opposite side of OR boundary
- After TP1: Move to breakeven
- Adaptive Trail: Activate at 0.50% profit, trail with 0.25% offset

MAE FILTER (Critical):
- Threshold: 0.05% from range boundary
- Action: Close trade if drawdown exceeds threshold
- Purpose: Cut losers early that show no follow-through
```

## 2.3 Risk Management
```
DAILY LIMITS:
- Max Daily Loss: $200
- Max Attempts: 10 trades/day
- Stop After Win: Optional (single winner mode)

POSITION SIZING:
- Base: 1% risk per trade
- Min Contracts: 1
- Max Contracts: 20
```

---

# SECTION 3: PROMPTS FOR AI GRAPHICS

## Prompt 1: Strategy Overview Infographic
```
Create a professional infographic showing the 0930 Opening Range Breakout strategy flow:

Visual Flow:
1. "9:30 AM" → Single 1-minute candle forms
2. "Opening Range Defined" → Show blue box with High and Low
3. "Breakout Trigger" → Arrow breaking above (long) or below (short)
4. "Multi-TP Exit" → Split showing TP1 (50%) and Runner (50%)

Style: Dark theme, blue and green accents, clean modern look
Include: NQ/MNQ Nasdaq futures, 1-minute timeframe label
```

## Prompt 2: Win Rate vs Time Chart
```
Create a bar chart showing win rate by hour for NQ1 retest entries:

Data:
- 09:00: 81.2% (3,331 trades) - tallest bar
- 10:00: 85.4% (438 trades) - second tallest
- 11:00: 84.3% (108 trades)
- 12:00: 80.3% (61 trades)
- 13:00: 75.8% (33 trades) - lowest
- 14:00: 86.1% (36 trades)
- 15:00: 89.2% (37 trades) - highest

Style: Dark background, green bars, highlight 10:00 and 15:00 as "sweet spots"
Title: "Win Rate by Hour - NQ1 OR Retests"
```

## Prompt 3: MAE Filter Comparison
```
Create a before/after comparison graphic showing MAE Filter impact:

LEFT SIDE (Without MAE):
- Avg Loss: $60
- Win/Loss Ratio: 2.0x
- Many trades run to full stop loss

RIGHT SIDE (With MAE):
- Avg Loss: $33
- Win/Loss Ratio: 3.2x
- Losers cut early at 0.05% threshold from range boundary

Visual: Show a P&L curve comparison, or loss distribution histogram
Title: "The MAE Filter Edge"
```

## Prompt 4: Risk/Reward Distribution
```
Create a scatter plot or histogram showing:

X-axis: MAE % (risk taken)
Y-axis: MFE % (reward achieved)

Key insight: Most winners cluster in the upper-left (high reward, low risk)
Highlight the asymmetry: Average MFE 0.45%, Average MAE 0.03%

Data from 4,045 NQ1 retest events
Win Rate: 81.8%

Style: Dark theme, winners in green dots, losers in red dots
```

## Prompt 5: Performance Scorecard
```
Create a professional scorecard/dashboard for the strategy:

TOP ROW (Key Metrics):
| Net Profit | Return | Profit Factor | Win Rate |
| $41,953 | 1,398% | 1.85 | 27.8% |

MIDDLE ROW (Trade Stats):
| Total Trades | Avg Win | Avg Loss | Win/Loss Ratio |
| 3,085 | $106.62 | $33.29 | 3.20x |

BOTTOM ROW (Risk):
| Max Drawdown | Largest Win | Largest Loss |
| $379 | $925.50 | $143 |

Style: Dark theme, green highlights for positive metrics
Period: Jan 2023 - Jan 2026 (3 years)
```

## Prompt 6: Multi-Ticker Heatmap
```
Create a heatmap showing strategy applicability across futures:

Tickers (rows): MNQ, MES, MYM, M2K, MCL, MGC
Metrics (columns): Win Rate, Avg MFE, MAE Control, Volatility

Color scale: Green (good) to Yellow (moderate) to Red (poor)

Data:
- MNQ: All green (primary ticker)
- MES: All green (correlated)
- MYM: Mostly green
- M2K: Green/Yellow mix (more volatile)
- MCL: Yellow (needs wider stops)
- MGC: Yellow (longer holds)

Title: "Strategy Portability Across Futures"
```

---

# SECTION 4: SUGGESTED SLIDE IMPROVEMENTS

## Slide 5 (Rules of Engagement)
**Current**: Text-heavy entry rules
**Suggestion**: Add visual flowchart showing:
- 9:30 candle → OR defined → Wait for breakout → Check filters → Enter
- Use icons for each step

## Slide 6 (Exit Protocol)
**Current**: Text-based exit rules  
**Suggestion**: Create a visual price ladder showing:
- Entry level
- TP1 level (0.10%)
- TP2 level (0.25%)
- Stop Loss at OR boundary
- MAE threshold zone (shaded)

## Slide 7 (Performance Scorecard)
**Current**: Basic metrics
**Suggestion**: Use the scorecard graphic from Prompt 5 above

## Slide 14 (Hourly Forensics)
**Current**: You have good scatter plots already
**Suggestion**: Add a summary callout box highlighting:
- "10:00 AM = 85.4% WR - Best hour for re-entries"
- "MFE decays: 0.32% → 0.15% as day progresses"

---

# SECTION 5: IMAGE FILES AVAILABLE

These images are in your reports folder and can be embedded:

```
c:\Users\vinay\tvDownloadOHLC\docs\strategies\9_30_breakout\0930_AllDay\reports\

NQ1:
- NQ1_1m_global_risk_reward.png (MFE/MAE scatter)
- NQ1_1m_0900_scatter.png (09:00 hour scatter)
- NQ1_1m_0900_hist.png (distribution histogram)
- NQ1_1m_1000_scatter.png (10:00 hour scatter)
- NQ1_1m_dist.png (overall distribution)

ES1, YM1, RTY1, CL1, GC1: Same structure
```

---

# SECTION 6: NOTEBOOKLM / CLAUDE MASTER PROMPT

Copy this entire prompt to get a comprehensive presentation:

```
I need help creating a professional trading strategy presentation for the "0930 Opening Range Breakout (ORB)" strategy.

STRATEGY SUMMARY:
- Trade the breakout of the 9:30 AM 1-minute candle on Nasdaq futures (MNQ)
- Entry: When price closes above OR High (long) or below OR Low (short)
- Exit: Multi-TP system (TP1 at 0.10%, TP2 at 0.25%) + MAE filter (0.05%)
- 3-year backtest: $41,953 profit, 1,398% return, 3.2x win/loss ratio

KEY DATA TO VISUALIZE:
1. Hourly win rates: 09:00=81.2%, 10:00=85.4%, 11:00=84.3%, 12:00=80.3%, 13:00=75.8%
2. MAE filter impact: Reduces avg loss from $60 to $33
3. Risk/reward asymmetry: Avg MFE 0.45%, Avg MAE 0.03%
4. 81.8% win rate on 4,045 OR retest events

Please create:
1. A strategy overview diagram showing the entry/exit flow
2. A bar chart of win rates by hour
3. A before/after comparison of MAE filter impact
4. A performance scorecard with key metrics
5. Suggested text and bullet points for each slide

Style: Professional, dark theme, suitable for futures trading audience
```
