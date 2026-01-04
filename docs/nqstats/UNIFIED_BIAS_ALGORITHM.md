# Unified Bias Algorithm
## Combining ALN + Profiler + ICT for NY AM/PM Prediction

**Ticker**: NQ1 (Nasdaq Futures)  
**Sample Size**: 4,640 Trading Days  
**Generated**: January 3, 2026

---

## Executive Summary

| Setup | Condition | NY AM Long | NY AM Short | Edge |
|-------|-----------|------------|-------------|------|
| **GOLD LONG** | LPEU + Held/Held + L/L | **55.9%** | 2.7% | +53.2% |
| **GOLD SHORT** | LPEU + Broken/Held + L/S | 5.0% | **46.0%** | +41.0% |
| Baseline | Any | 17% | 17% | 0% |

---

## ICT Daily Profile Distribution (NQ1)

Using actual High-of-Day / Low-of-Day timestamps:

| Profile | Days | % | Description |
|---------|------|---|-------------|
| **Classic Buy** | 1,417 | 30.8% | Low forms in AM, High forms in PM |
| **Classic Sell** | 1,312 | 28.5% | High forms in AM, Low forms in PM |
| **Seek & Destroy** | 46 | 1.0% | Both form mid-session (10:00-14:00) |
| **Neutral** | 1,830 | 39.7% | No clear pattern (both AM or both PM) |

### ICT Profile Insights by Setup

| Setup | Classic Buy % | Classic Sell % | Interpretation |
|-------|---------------|----------------|----------------|
| LPEU + Held/Held + L/L | 2.7% | — | **Rare Classic Buy, but strong AM Long edge** |
| LPED + Broken/Broken + L/S | **50.6%** | 18.5% | **High Classic Buy despite LPED!** |
| LPEU + Broken/Held + L/S | — | **40.0%** | **Reversal setup = Classic Sell** |
| LPED + Broken/Broken + S/S | **49.7%** | 22.2% | **Bullish despite bearish ALN** |

---

## Step-by-Step Algorithm

### PRE-MARKET CHECKLIST (7:30 - 8:00 AM ET)

#### STEP 1: Classify ALN Pattern
Compare Asia (18:00-02:00) and London (03:00-08:00) ranges.

| Pattern | Condition | Bias |
|---------|-----------|------|
| **LPEU** | London High > Asia High, London Low ≥ Asia Low | Bullish |
| **LPED** | London Low < Asia Low, London High ≤ Asia High | Bearish |
| **LEA** | London breaks BOTH Asia extremes | Volatile |
| **AEL** | London inside Asia | Wait |

```
IF London broke Asia High but held Asia Low → LPEU → Bullish
IF London broke Asia Low but held Asia High → LPED → Bearish
IF London broke BOTH → LEA → No directional bias, expect expansion
IF London inside Asia → AEL → Wait for NY to establish direction
```

---

#### STEP 2: Check Broken Status
Did the subsequent session break the prior session's range?

| Combo | Meaning | Action |
|-------|---------|--------|
| **Held/Held** | Asia held by London, London held by Pre-NY | ✅ **BEST: High conviction** |
| **Broken/Held** | Asia broken, London held | ✅ Good setup |
| **Held/Broken** | Asia held, London broken | ⚠️ Moderate |
| **Broken/Broken** | Both broken | ❌ **WORST: Reduce size or wait** |

```
IF Asia.broken == FALSE AND London.broken == FALSE:
    CONVICTION = HIGH (rare but powerful)
ELIF Both broken:
    CONVICTION = LOW (most days - expect chop)
ELSE:
    CONVICTION = MEDIUM
```

---

#### STEP 3: Check Profiler Status (P12 Level)
Did Asia and London close above or below their P12 (Prior Close)?

| Asia Status | London Status | Implication |
|-------------|---------------|-------------|
| **Long** | **Long** | Bullish alignment |
| **Long** | **Short** | Reversal brewing |
| Short | Long | Mixed (London reversed) |
| Short | Short | Bearish alignment |

```
IF Asia=Long AND London=Long:
    DIRECTION_CONFIRMATION = BULLISH
ELIF Asia=Long AND London=Short:
    DIRECTION_CONFIRMATION = REVERSAL_WATCH
ELIF Asia=Short AND London=Short:
    DIRECTION_CONFIRMATION = BEARISH
ELSE:
    DIRECTION_CONFIRMATION = MIXED
```

---

### BIAS DECISION MATRIX

#### 🟢 STRONG BULLISH BIAS
**Conditions:**
- ALN: LPEU
- Broken: Held/Held OR Broken/Held
- Status: L/L

**Statistics (111 days):**
- NY AM Long: **55.9%**
- NY AM Short: 2.7%
- NY PM Long: 46.8%

**Action:**
```
BIAS = LONG
SIZE = FULL
ENTRY = Pullback to London Mid or 50% of London range
TARGET 1 = London High
TARGET 2 = London High + 0.5 * London Range (extension)
STOP = Below London Low
```

---

#### 🔴 STRONG BEARISH BIAS
**Conditions:**
- ALN: LPEU (counter-intuitive!)
- Broken: Broken/Held
- Status: L/S (Long Asia, Short London = reversal)

**Statistics (100 days):**
- NY AM Short: **46.0%**
- NY AM Long: 5.0%
- NY PM Short: 35.0%

**Action:**
```
BIAS = SHORT
SIZE = FULL
ENTRY = Rally to London Mid or 50% of London range
TARGET 1 = Asia Low
TARGET 2 = London Low (if not yet broken)
STOP = Above London High
```

---

#### 🟡 NEUTRAL / WAIT
**Conditions:**
- Broken: Broken/Broken (68% of days)
- OR ALN: LEA or AEL

**Statistics:**
- NY AM: ~13-15% Long, ~13-17% Short
- NY Broken: 51%+

**Action:**
```
BIAS = NONE
SIZE = REDUCED (50% or less)
WAIT for NY to establish direction in first 30 minutes
Trade the confirmed breakout direction
```

---

## Targets Framework

| Level | Definition | Use Case |
|-------|------------|----------|
| **London High** | Primary bullish target | LPEU days |
| **London Low** | Primary bearish target | LPED days |
| **Asia High/Low** | Secondary targets | If London already broken |
| **London Mid** | 50% of London range | Entry point for pullbacks |
| **P12 Level** | Prior day close | Profiler status reference |

---

## Daily Checklist Template

```
DATE: ___________

PRE-MARKET (7:30-8:00 AM ET)
─────────────────────────────────────────
[ ] Asia Range: High=______ Low=______
[ ] London Range: High=______ Low=______
[ ] ALN Pattern: ________________
[ ] Broken Status: Asia=____ London=____
[ ] Profiler Status: Asia=____ London=____

DECISION
─────────────────────────────────────────
[ ] BIAS: LONG / SHORT / NEUTRAL
[ ] CONVICTION: HIGH / MEDIUM / LOW
[ ] SIZE: FULL / REDUCED / SKIP

EXECUTION (9:30 AM+ ET)
─────────────────────────────────────────
[ ] Entry: ________ @ ________
[ ] Stop: ________
[ ] Target 1: ________
[ ] Target 2: ________
```

---

## Source Code
- [analyze_unified_bias.py](file:///c:/Users/vinay/tvDownloadOHLC/scripts/nqstats/aln_sessions/analyze_unified_bias.py)
