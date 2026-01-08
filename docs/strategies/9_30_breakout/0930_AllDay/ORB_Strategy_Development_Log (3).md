# ORB Strategy Development Log
## Comprehensive Experiment Tracker & Continuation Guide

**Last Updated:** January 6, 2026  
**Current Focus:** V7 Series - ICT Judas Swing with Runner Optimization  
**Symbol:** CME_MINI:MNQ1! (Micro Nasdaq Futures)  
**Timeframe:** 1 minute

---

## 📋 PROJECT OVERVIEW

### What We're Building
An Opening Range Breakout (ORB) strategy for NQ/MNQ futures incorporating ICT (Inner Circle Trader) methodology. The goal is to:
1. Capture reliable 0.10% moves (cash flow)
2. Let runners capture extended moves (alpha)
3. Control risk through intelligent filtering and position management

### Strategy Evolution
```
V1-V2: Simple ORB with basic filters → Baseline ($6,776)
V3-V4: Added Market Structure, Momentum filters → Mixed results
V5-V6: Skipped (experimental)
V7A: Simple Judas 3-Tier → $5,160 (good entries, SL_2 problem)
V7B: MSS Structure with OTE → Complex, underperformed
V7C: 3-Tier with MS Trail → $3,320 (MSS adds no value)
V7D: Probe + Scale-in + Selective MAE → $4,332 (killed runners!)
V7E: Fixed Exits (2-contract + Quick BE) → -$1,401 (Quick BE too aggressive)
V7F: Dump Pouch Risk Management → $4,200 (best V7 so far!)
V7G: HYBRID (V2 MAE + V7F Dump Pouch + Judas) → TESTING
```

### V7D Failure Analysis (Important Learning)
```
Problem: V7D saved $47K on stops but lost $53K on runners = NET WORSE!

Root Causes:
1. Probes are worthless (442 trades = $498 profit, break-even)
2. Waiting for probe kills timing (missed 50% of entries)
3. MAE filter doesn't help probes (they exit at TP1 first)
4. The REAL problem is position sizing, not entry logic

Key Finding: 128 of 242 SL_2 trades (53%) reached T1 before stopping!
            T1 limit order didn't fill → stop hit remaining contracts
```

---

## 🏆 CURRENT GOLD STANDARD: V2 All-Day

| Metric | V2 Gold Standard |
|--------|------------------|
| Net Profit | $6,776 |
| Total Trades | 2,405 |
| Win Rate | 48.9% |
| Profit Factor | 1.166 |
| Sharpe Ratio | 0.505 |
| Max Drawdown | $1,373 |
| Avg Win | $40.48 |
| Avg Loss | $-33.22 |

### Why V2 Works
1. **MAE Filter** - Cuts losses at 0.15% adverse excursion
2. **Single Contract** - No complex position splitting
3. **Many Attempts** - Up to 15/day, law of large numbers
4. **Immediate Re-entry** - No waiting for "fresh" breakouts
5. **Simple Exit** - TP1 at 0.10% or stop, no runners

---

## 📊 VERSION COMPARISON (Current Session)

| Metric | V2 Gold | V7A 3-Tier | V7C 3-Tier |
|--------|---------|------------|------------|
| **Net Profit** | **$6,776** | $5,160 | $3,320 |
| **Max Drawdown** | **$1,373** | $7,522 | $8,918 |
| **Sharpe Ratio** | **0.505** | 0.136 | 0.109 |
| Win Rate | 48.9% | 59.2% | 58.4% |
| Avg Loss | **$-33** | $-151 | $-151 |
| Total Trades | 2,405 | 1,695 | 1,703 |

---

## 🔴 CRITICAL FINDINGS

### Finding #1: SL_2 is Destroying V7A Profits
```
V7A Exit Breakdown:
  EOD Exits:     +$67,122  ← THE WINNER (captures big moves!)
  T1 Exits:      -$195     ← Break-even
  SL_2 Exits:    -$60,100  ← THE KILLER
  Other:         -$1,667
  ─────────────────────────
  TOTAL:         +$5,160
```

**The Problem:** 3 contracts per reversal trade. When stop hits, SL_2 exits 2 contracts at full loss.
- 242 SL_2 exits × $-248 avg = **-$60,100**

### Finding #2: MAE Filter Would Kill EOD Winners!
```
EOD Exit Analysis:
  133 of 271 EOD winners (49%) had MAE < -0.15%
  These trades went 0.15%+ AGAINST us first, then recovered!
  They ended up averaging +$247 per trade.
```

**The Dilemma:**
- Tight MAE filter → Saves on losers, but kills runners that need room to breathe
- No MAE filter → Runners survive, but losers get too big

### Finding #3: Re-Entry IS Where The Money Is
```
Attempt Analysis:
  REV 1 (first attempt):   9 trades, +$1,332
  REV 2 (re-entry):      849 trades, +$3,128  ← 205 EOD exits = +$55,796!
  REV 3/4:               220 trades, -$132
```

**76% of EOD profits come from second attempt (re-entry)!**

---

## 💡 SOLUTION: SELECTIVE MAE (Probe + Scale-In)

### Proposed V7D Structure

```
┌─────────────────────────────────────────────────────────────────┐
│ PHASE 1: JUDAS SCALP (Optional - 1 contract)                    │
│ • Trade WITH first breakout direction                           │
│ • Quick TP at 0.10%                                             │
│ • MAE filter at 0.15% (cut losers fast)                         │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ PHASE 2: PROBE TRADE (1 contract only!)                         │
│ • First reversal attempt                                        │
│ • Trade OPPOSITE of Judas direction                             │
│ • MAE filter at 0.15% (controlled loss ~$30)                    │
│ • Exit: T1 (0.10%) or MAE stop                                  │
│ • NO RUNNER - just testing the direction                        │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ PHASE 3: CONFIRMED TRADE (2 contracts)                          │
│ • Re-entry after price returns to OR and breaks out again       │
│ • This is the "confirmed" move                                  │
│ • NO MAE FILTER (let it breathe!)                               │
│ • Contract 1: TP at 0.10% (cash flow)                           │
│ • Contract 2: Runner to EOD with MS trail                       │
│ • After TP1: Move runner stop to BE                             │
│ • This is where +$55K in EOD profits comes from!                │
└─────────────────────────────────────────────────────────────────┘
```

### Why This Should Work
1. **Probe with MAE** = Small losses on wrong direction (~$30)
2. **Confirmed trades without MAE** = Runners can survive drawdowns
3. **Scale-in on confirmation** = Bigger position on validated moves
4. **Best of both worlds** = V2's loss control + V7A's EOD upside

### Expected P&L Projection
```
Current V7A:  +$5,160
  - SL_2 leak: -$60,100
  + EOD exits: +$67,122

Proposed V7D with Selective MAE:
  - Probe losses (MAE): ~$-5,000 (small, controlled)
  - Confirmed SL: ~$-20,000 (fewer, runners survive)
  + EOD exits: ~$+65,000 (preserved!)
  ─────────────────────────
  PROJECTED: ~$+40,000
```

---

## 🔍 CROSS-STRATEGY ENTRY ANALYSIS

### V7E: FIXED EXITS (2-Contract + Quick BE)

**File:** `/home/claude/orb_v7e_fixed_exits.pine`

**Philosophy:** Fix V7A's exit mechanics, not entry logic.

**Key Changes:**
| Fix | Description | Expected Impact |
|-----|-------------|-----------------|
| 2-Contract Structure | Enter with 2 (not 3) | Less exposure if stopped |
| Price Touch T1 | Exit when price touches (not limit) | Captures 128 trades that missed T1 |
| Quick Breakeven | Move stop to entry after T1 | Prevents SL_2 scenario |
| MS Trail After BE | Only trail AFTER at breakeven | Protects gains |

**Settings:**
```
Reversal Contracts: 2
TP1 Exit Mode: "Price Touch" (recommended)
Quick Breakeven: ON
BE Buffer: 1.0 points
```

**Expected Results:**
- SL losses: -$60K → ~-$30K (50% reduction)
- EOD profits: Preserved (unlike V7D)
- Net improvement: +$30K better than V7A

---

### V7F: DUMP POUCH RISK MANAGEMENT

**File:** `/home/claude/orb_v7f_dump_pouch.pine`

**Philosophy:** Progressive risk reduction while letting winners run.

**Dump Pouch Rules:**
```
LEVEL 0 (Entry): Initial SL at Judas Extreme/OR Boundary
LEVEL 1 (At TP1): Move SL to 50% of initial risk
LEVEL 2 (At 50% of target): Move SL to Breakeven  
LEVEL 3 (At 75% of target): Move SL to lock 25% of move
```

**Example (Long at 100.00, SL at 99.00, Target 1.00%):**
```
Entry:      Price=100.00, SL=99.00 (100 point risk)
TP1 hit:    Price=100.10, SL→99.50 (50 point risk)
50% hit:    Price=100.50, SL→100.00 (Breakeven)
75% hit:    Price=100.75, SL→100.25 (25 points locked)
```

**Settings:**
```
Target Move %: 1.00% (expected full move)
Level 1: SL to 50% of risk (at TP1)
Level 2 Trigger: 50% of target move
Level 3 Trigger: 75% of target move  
Level 3 Lock: 25% of move
```

**Advantages:**
- Never gives back more than 50% of gains after TP1
- Locks profit at 75% move level
- Still allows runners to EOD
- Works with 2-contract structure

---

### V7G: HYBRID (V2 MAE + V7F Dump Pouch + Judas Bias)

**File:** `/home/claude/orb_v7g_hybrid.pine`

**Philosophy:** Combine the BEST of V2 and V7F - V2's loss control with V7F's runner capture.

**Key Components:**

| From | Feature | Benefit |
|------|---------|---------|
| V2 | MAE Filter (0.15%) | Cuts losers early at $30 avg vs $125 |
| V7F | Dump Pouch Trail | Captures runners to EOD |
| V7F | Judas Direction Bias | 59% win rate vs 49% |

**Trade Flow:**
```
ENTRY: Judas bias determines direction (trade opposite of first breakout)

BEFORE TP1:
  - MAE Filter active: Exit immediately if price hits -0.15%
  - This prevents $125 avg losses, limits to ~$30

AFTER TP1 (0.10%):
  - Exit 1 contract at TP1
  - Dump Pouch activates:
    Level 1: SL moves to 50% of initial risk
    Level 2 (at 50% of target): SL moves to breakeven
    Level 3 (at 75% of target): Lock 25% of move
  - Runner held to EOD
```

**Settings:**
```
MAE Filter: ON (0.15% threshold)
Apply To: All Trades
Dump Pouch: ON
  Level 1: 50% risk reduction at TP1
  Level 2: BE at 50% of target move
  Level 3: Lock 25% at 75% of target
Target Move: 1.00%
```

**Expected Results:**
```
FROM V2:   Losses ~$25K (MAE filter cuts early)
FROM V7F:  Winners ~$50K (runners captured via Dump Pouch)
PROJECTED: NET ~$25K (4x better than either alone!)
```

---

## 📊 MOVE ANALYZER INDICATOR

**File:** `/home/claude/orb_move_analyzer.pine`

**Purpose:** Track raw MFE/MAE for ALL moves (not just trades taken)

**Outputs:**
- Daily MFE/MAE for long and short breakouts
- Historical statistics (avg, percentiles)
- Export via alerts for external analysis

**Use for:**
- Determining optimal TP levels (use percentiles)
- Understanding typical move sizes
- Comparing theoretical vs actual results

---

## 🔍 CROSS-STRATEGY ENTRY ANALYSIS

### First Breakout (Judas/Initial) Comparison

| Metric | V2 Attempt 1 | V7A JUDAS | Winner |
|--------|--------------|-----------|--------|
| Trades | 639 | 617 | Similar |
| **Win Rate** | 49.1% | **64.7%** | **V7A** (+15.6%) |
| Profit | **$3,360** | $832 | **V2** |
| Avg MFE | 0.070% | 0.080% | Similar |

**Insight:** V7A's JUDAS logic (trade WITH first breakout) has 15% higher win rate, but V2's MAE filter converts more of those into profit.

### Reversal/Continuation Comparison

| Metric | V2 Attempt 2 | V7A REV 2 | Winner |
|--------|--------------|-----------|--------|
| Trades | 512 | 849 | V7A takes more |
| **Win Rate** | 45.7% | **56.5%** | **V7A** (+10.8%) |
| Profit | $393 | **$3,128** | **V7A** |
| **Avg MFE** | 0.069% | **0.247%** | **V7A** (3.5x!) |
| **EOD Runners** | $650 | **$55,796** | **V7A** (85x!) |

**Critical Finding:** V7A's "trade OPPOSITE of Judas" reversal logic is VASTLY superior:
- 3.5x higher MFE (catches bigger moves)
- $55K in EOD runner profits vs $650
- The Judas swing concept WORKS for reversals!

### Why V7A Loses Despite Better Entries

```
V7A REV 2 Performance:
  EOD Exits:  +$55,796  (the winners)
  SL_2 Exits: -$49,880  (the killer)
  T1 Exits:   -$1,766   (break-even)
  ─────────────────────
  Net:        +$3,128   (most profit eaten by SL_2)
```

### Recommendations from Entry Analysis

**For JUDAS Scalps:**
- ✓ Keep V7A logic (trade WITH first breakout) - 64.7% WR
- ✓ ADD MAE filter to cut losers fast
- Expected: High WR + controlled losses = better profit

**For Reversals:**
- ✓ V7A's "trade opposite Judas" is SUPERIOR
- ✓ MFE 3.5x higher than V2
- ✓ EOD runners = $55K potential
- ✗ Must fix SL_2 problem with Selective MAE

**V7D implements both recommendations!**

---

## 📁 FILE LOCATIONS

### Current Scripts (in /mnt/user-data/outputs/)
- `orb_v7a_3tier.pine` - Simple Judas + 3-Tier + VVIX filter
- `orb_v7c_3tier.pine` - MSS Structure + 3-Tier + VVIX filter
- `orb_v4_ict.pine` - V4 with ICT filters (momentum, equilibrium, etc.)
- `orb_strategy_experiments.md` - Previous experiment tracker

### Backtest Data (in /mnt/user-data/uploads/)
- `ORB_All-Day_V2_CME_MINI_MNQ1__2026-01-06_bdabc.xlsx` - V2 Gold Standard
- `ORB_V7A_-_3_Tier_Simple_CME_MINI_MNQ1__2026-01-06_bbda5.xlsx` - V7A 3-Tier
- `ORB_V7C_-_3_Tier_CME_MINI_MNQ1__2026-01-06_dd593.xlsx` - V7C 3-Tier
- `ORB_V7B_-_MSS_Debug_CME_MINI_MNQ1__2026-01-06_34343.xlsx` - V7B MSS

### Analysis Transcripts (in /mnt/transcripts/)
- `2026-01-06-23-26-33-orb-v7b-pinescript-debug.txt`
- `2026-01-06-23-33-47-orb-v7c-3tier-runner-optimization.txt`

---

## 🔧 ANALYSIS SCRIPTS

### Standard Excel Analysis Pattern
```python
import pandas as pd

# Load backtest file
file = '/mnt/user-data/uploads/YOUR_FILE.xlsx'
xl = pd.ExcelFile(file)

# Performance metrics
perf = pd.read_excel(xl, sheet_name='Performance').set_index('Unnamed: 0')
trades = pd.read_excel(xl, sheet_name='Trades analysis').set_index('Unnamed: 0')
risk = pd.read_excel(xl, sheet_name='Risk-adjusted performance').set_index('Unnamed: 0')

# Trade list with entry/exit details
trade_list = pd.read_excel(xl, sheet_name='List of trades')
entries = trade_list[trade_list['Type'].str.contains('Entry', na=False)]
exits = trade_list[trade_list['Type'].str.contains('Exit', na=False)]

# Merge entries with exit signals
merged = entries[['Trade #', 'Signal', 'Net P&L USD', 'MFE %', 'MAE %']].copy()
exit_signals = exits[['Trade #', 'Signal']].copy()
exit_signals.columns = ['Trade #', 'Exit Signal']
merged = merged.merge(exit_signals, on='Trade #')
```

### Exit Signal Analysis
```python
for exit_sig in merged['Exit Signal'].unique():
    subset = merged[merged['Exit Signal'] == exit_sig]
    print(f"{exit_sig}: {len(subset)} trades, ${subset['Net P&L USD'].sum():,.0f}")
```

---

## 📅 EXPERIMENT HISTORY

### Session: January 6, 2026 (Current)

| Time | Experiment | Result |
|------|------------|--------|
| Earlier | V7A Simple Judas 3-Tier | $5,160 profit, but SL_2 = -$60K |
| Earlier | V7C MSS 3-Tier | $3,320, worse than V7A |
| Current | Compare V2 vs V7A vs V7C | V2 wins on risk-adjusted basis |
| Current | Analyze SL_2 problem | 128 of 242 reached T1 before stopping |
| Current | MAE filter simulation | Would kill 49% of EOD winners! |
| Current | Design V7D Selective MAE | Probe + Scale-in structure |

### Previous Sessions (from memory)

| Date | Finding |
|------|---------|
| 2026-01-06 | V7A Simple Judas ($6,445 with 1 contract) beats V7B MSS ($4,217) |
| 2026-01-06 | Runner problem: BE stop killed trades before development |
| 2026-01-06 | VALUE mode momentum filter outperforms EXTENDED mode |
| 2026-01-06 | Equilibrium + Time Window filters stack well |
| Earlier | V2 All-Day is gold standard for risk-adjusted returns |

---

## ✅ TODO LIST

### Immediate Next Steps
1. [ ] **Build V7D** with Selective MAE (Probe + Scale-in)
2. [ ] Backtest V7D on same period
3. [ ] Compare exit signal distribution vs V7A
4. [ ] Verify probe losses are controlled
5. [ ] Verify runner EOD exits are preserved

### Future Experiments
- [ ] Test different probe MAE thresholds (0.10%, 0.15%, 0.20%)
- [ ] Test different runner stop modes (BE, MS trail, fixed)
- [ ] Add Gap Direction filter to V7 series
- [ ] Add True Day Open filter to V7 series
- [ ] Combine best V4 filters with V7 structure

---

## 🚀 CONTINUATION PROMPT

To resume this work, share this document and say:

```
"I'm continuing ORB strategy development. Please read the attached 
ORB_Strategy_Development_Log.md to understand where we left off.

Current status:
- V7A 3-Tier has SL_2 problem (-$60K leak)
- V2's MAE filter works but would kill V7A's EOD winners
- Solution: V7D with Selective MAE (probe+scale-in)

What I want to do next: [BUILD V7D / ANALYZE MORE / OTHER]

Backtest files available:
- ORB_V7A_-_3_Tier_Simple_CME_MINI_MNQ1__2026-01-06_bbda5.xlsx
- ORB_V7C_-_3_Tier_CME_MINI_MNQ1__2026-01-06_dd593.xlsx  
- ORB_All-Day_V2_CME_MINI_MNQ1__2026-01-06_bdabc.xlsx
```

---

## 📈 KEY METRICS TO TRACK

| Metric | V2 Target | V7D Goal |
|--------|-----------|----------|
| Net Profit | $6,776 | $40,000+ |
| Max Drawdown | $1,373 | <$3,000 |
| Sharpe Ratio | 0.505 | >0.4 |
| Avg Loss | $-33 | <$-50 |
| EOD Exits P&L | N/A | >$60,000 |
| SL_2 Leak | N/A | Eliminated |

---

*Document maintained by Claude for ORB strategy development sessions*
