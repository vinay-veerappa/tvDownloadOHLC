# Trading Journal - User Guide

A comprehensive guide to using the Trading Journal for tracking, analyzing, and improving your trading performance.

---

## Table of Contents

1. [Getting Started](#getting-started)
2. [Recording Trades](#recording-trades)
3. [Reviewing Trades](#reviewing-trades)
4. [Analytics Dashboard](#analytics-dashboard)
5. [AI Assistant](#ai-assistant)
6. [Goal Tracking](#goal-tracking)
7. [Import/Export](#importexport)
8. [Chart Integration](#chart-integration)

---

## Getting Started

### Accessing the Journal

Navigate to `/journal` from the main application. The journal page displays:
- **Trade list** with all recorded trades
- **Action buttons**: Import/Export, AI Assistant, Analytics, Add Trade

### First-Time Setup

1. **Accounts** are created automatically (default: Simulation Account)
2. **Strategies** can be selected when logging trades
3. **Economic Calendar** is pre-loaded with 8,843 events (2000-2025)

---

## Recording Trades

### Adding a New Trade

1. Click **"+ Add Trade"** button
2. Fill in required fields:
   - **Symbol** (e.g., NQ1, ES1, SPY)
   - **Direction** (LONG or SHORT)
   - **Entry Date/Time**
   - **Entry Price**
   - **Quantity**
3. Optional fields:
   - **Strategy** (select from dropdown)
   - **Stop Loss** / **Take Profit**
   - **Notes**
4. Click **"Add Trade"**

### Closing an Open Trade

1. Click on the trade row to open Trade Detail
2. Click **"Close Trade"** button
3. Enter exit price
4. Trade P&L will be calculated automatically

### Trade Status

| Status | Description |
|--------|-------------|
| **OPEN** | Active position, no exit recorded |
| **CLOSED** | Position closed with P&L calculated |

---

## Reviewing Trades

### Trade Detail Page

Click any trade row to view full details:

- **Summary Card**: Entry/exit, direction, P&L, duration
- **Order Details**: Order type, stop loss, take profit
- **Risk & Metrics**: MAE, MFE, risk amount
- **Market Context**: Session, VIX, VVIX, ATR, trend
- **Notes**: Editable notes section

### Post-Trade Review

After closing a trade, complete the **Trade Review** questionnaire:

1. **Execution Rating** (1-5 stars)
2. **Followed Plan** checkbox
3. **Emotional State** (Calm, Anxious, FOMO, etc.)
4. **Mistakes Made** (checklist of common errors)
5. **What Went Well / Wrong**
6. **Lessons Learned**
7. **Would Take Again** checkbox

---

## Analytics Dashboard

Navigate to `/journal/analytics` for performance insights.

### Summary Cards

| Metric | Description |
|--------|-------------|
| **Total P&L** | Cumulative profit/loss |
| **Today's P&L** | Current day performance |
| **Week/Month P&L** | Period performance |
| **Win Rate** | Percentage of winning trades |
| **Profit Factor** | Gross profit / Gross loss |
| **Avg Win/Loss** | Average P&L per outcome |

### Equity Curve

Visual chart showing cumulative P&L over time with drawdown overlay.

### Strategy Comparison

Horizontal bar chart comparing P&L performance by strategy.

---

## AI Assistant

Navigate to `/journal/ai` for AI-powered trade analysis.

### Quick Prompts

Click any preset prompt:
- 📊 **Summarize today** - Daily trade summary
- 📉 **Losing patterns** - Analyze loss patterns
- 🏆 **Best strategy** - Strategy performance ranking
- ⚠️ **Risk review** - Risk management analysis
- 💡 **Improvement tips** - Personalized suggestions

### Custom Questions

Type any question about your trading:
- "What time of day am I most profitable?"
- "Compare my NQ vs ES performance"
- "What's my average hold time on winners?"

### Provider Selection

Choose AI provider:
- **Gemini** - Google's AI (requires API key)
- **Ollama** - Local LLM (requires Ollama running)

---

## Goal Tracking

### Setting Goals

1. Open Goal Tracker component
2. Click **"Edit"** to modify targets
3. Set goals for:
   - **Daily Target** ($)
   - **Weekly Target** ($)
   - **Monthly Target** ($)
   - **Max Loss/Day** ($)
   - **Max Trades/Day** (count)
4. Click **"Save"**

### Progress Monitoring

- Progress bars show % toward targets
- Color coding: 🟢 Green (target met), 🟡 Yellow (50%+), ⚪ Gray (below 50%)
- **Risk Alerts** appear when approaching max loss

---

## Import/Export

### Exporting Trades

1. Click **"Import/Export"** button
2. Select **"Export CSV"** tab
3. Click **"Download CSV"**
4. File downloads with all trades

### Importing Trades from CSV

1. Click **"Import/Export"** button
2. Select **"Import CSV"** tab
3. Prepare CSV with required columns:
   ```
   ticker,direction,entryDate,entryPrice
   ```
4. Optional columns:
   ```
   exitDate,exitPrice,quantity,pnl,stopLoss,takeProfit,notes
   ```
5. Upload file and click **"Import Trades"**

### Importing Backtest Results

1. Click **"Import/Export"** button
2. Select **"Backtests"** tab
3. View saved backtest results
4. Click **"Import"** on desired backtest
5. Trades are imported as a new account

---

## Chart Integration

### From Chart to Journal

1. On the chart, click **📖 Log Trade** (BookMarked icon in left toolbar)
2. Add Trade dialog opens with chart context pre-filled
3. Complete trade details and save

### From Journal to Chart

1. Open any trade detail page
2. Click **"📈 View on Chart"** button
3. Chart opens at the trade's entry date/time
4. Review price action around your trade

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Esc` | Close dialog |
| `Enter` | Submit form |

---

## Tips for Best Results

### Trade Logging Best Practices

1. ✅ Log trades immediately after execution
2. ✅ Include stop loss and take profit levels
3. ✅ Add notes about your reasoning
4. ✅ Complete the trade review questionnaire
5. ✅ Link trades to your playbook setups

### Review Workflow

1. **Daily**: Review all trades at end of session
2. **Weekly**: Analyze patterns and update goals
3. **Monthly**: Deep dive with AI assistant

### Using AI Effectively

- Be specific in your questions
- Ask about patterns, not individual trades
- Request actionable insights
- Compare strategies over meaningful time periods
