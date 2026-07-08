# NQ Session Specification (Second Brain)

> **Source**: [NQStats — ALN Sessions](https://nqstats.com/aln_sessions.html)
> **Study**: 10-year, 2016–2026, n = 2,542 sessions (NQ futures)
> **Verified**: 2026-07-08

## 1. Overview
This module defines the institutional sessions for Nasdaq (NQ) futures based on the NQStats methodology. Each session is anchored in **US/Eastern (New York)** time. Patterns are classified at the **08:00 bar close** (final London bar) and probabilities reflect how often New York price action breaks the London high, London low, or both during the 08:00–16:00 NY window.

## 2. Session Definitions

| Session | Start (ET) | End (ET) | Description |
|---------|------------|----------|-------------|
| **Asia** | 20:00 (Y) | 02:00 (T) | Institutional accumulation / overnight reference range. |
| **London** | 02:00 (T) | 08:00 (T) | European hours; defines pattern vs Asia. Pattern locked at 08:00. |
| **Pre-NY** | 08:00 (T) | 09:30 (T) | Pre-Market window for final alignment. |
| **NY_AM** | 09:30 (T) | 12:00 (T) | Primary AM liquidity expansion (Equities Open). |
| **NY_PM** | 12:00 (T) | 16:00 (T) | PM expansion and Daily rebalancing (Equities Close). |

*(Y) = Previous Day, (T) = Current Day*

> **Note**: NQStats anchors Asia at **20:00** (not 18:00). London at **02:00** (not 03:00). These times have been corrected from the prior spec to match the published methodology.

## 3. ALN Pattern Classification (Asia-London Relationship)
The relationship between Asia and London sessions determines the primary bias. Patterns are classified at the 08:00 ET bar close. Across all 4 patterns, NY breaks **neither** side in **<1%** of sessions.

### Pattern 1 — LEA (London Engulfs Asia)

| | |
|---|---|
| **Structure** | London high > Asia high · London low < Asia low |
| **Interpretation** | London fully expands beyond the overnight range on both sides — elevated two-way volatility into NY open. |
| **Internal Name** | `LEA` |
| **Frequency** | 558 sessions (22.0%) |
| **Breaks London High** | 71.5% |
| **Breaks London Low** | 70.4% |
| **Breaks Both** | 42.5% |
| **Breaks Neither** | 0% (50/50 first-break split; fully symmetric) |
| **First-break edge** | None — coin flip. Lowest confidence pattern. |
| **If high breaks first** | Low also breaks 42.8% of the time (50.7% of sessions high-first) |
| **If low breaks first** | High also breaks 42.6% of the time (48.7% of sessions low-first) |
| **Trade guidance** | No directional edge — wait for NY to resolve before committing. |

### Pattern 2 — AEL (Asia Engulfs London)

| | |
|---|---|
| **Structure** | Asia high > London high · Asia low < London low (London compresses inside Asia) |
| **Interpretation** | London narrowed during European hours — a coiling precursor to a directional NY move. |
| **Internal Name** | `AEL` |
| **Frequency** | 175 sessions (6.9%) |
| **Breaks London High** | 81.1% |
| **Breaks London Low** | 74.9% |
| **Breaks Both** | 56.0% |
| **Breaks Neither** | 0 sessions in 10 years — NY **always** breaks a level |
| **If high breaks first** | Low also breaks 52.7% (53.1% of sessions high-first) |
| **If low breaks first** | High also breaks 59.8% (46.9% of sessions low-first) — **low-first raises high-side probability** |
| **Trade guidance** | High overall break rates, but direction still ambiguous. Low-first break is a bullish tell (59.8% high follow-through). |

### Pattern 3 — LPEU (Partial Engulf Up)

| | |
|---|---|
| **Structure** | London high > Asia high · London low stays inside Asia range |
| **Interpretation** | London pushed higher without taking the Asian low — bullish overnight lean with upside already extended into NY open. |
| **Internal Name** | `LPEU` |
| **Frequency** | 1,042 sessions (41.0%) — **most common pattern** |
| **Breaks London High** | 80.8% |
| **Breaks London Low** | 65.5% |
| **Breaks Both** | 47.6% |
| **Breaks Neither** | 1.2% (13 sessions) |
| **If high breaks first** | Low also breaks 46.4% (62.0% of sessions high-first) |
| **If low breaks first** | High still breaks 51.2% (↓ 29.6pp from base 80.8%) — **edge lost** |
| **Trade guidance** | Highest confidence pattern. Bullish bias — high breaks first 62% of the time. If low breaks first, the bullish edge is gone (high-break rate drops to 51.2%). |

### Pattern 4 — LPED (Partial Engulf Down)

| | |
|---|---|
| **Structure** | London low < Asia low · London high stays inside Asia range |
| **Interpretation** | London pushed lower without taking the Asian high — bearish overnight lean with downside already extended into NY open. |
| **Internal Name** | `LPED` |
| **Frequency** | 767 sessions (30.2%) |
| **Breaks London High** | 68.6% |
| **Breaks London Low** | 75.0% |
| **Breaks Both** | 44.6% |
| **Breaks Neither** | 1.0% (8 sessions) |
| **If high breaks first** | Low still breaks 46.2% (↓ 28.8pp from base 75.0%) — **edge lost** |
| **If low breaks first** | High also breaks 44.1% (54.4% of sessions low-first) |
| **Trade guidance** | Bearish bias — low breaks first 54.4% of the time. If high breaks first, the bearish edge is gone (low-break rate drops to 46.2%). |

## 4. Summary Table

| Pattern | Name | Freq | High Break | Low Break | Both | Neither | Bias |
|---------|------|------|-----------|-----------|------|---------|------|
| P1 / LEA | London Engulfs Asia | 22.0% | 71.5% | 70.4% | 42.5% | 0% | Neutral (coin flip) |
| P2 / AEL | Asia Engulfs London | 6.9% | 81.1% | 74.9% | 56.0% | 0% | Neutral (coiled) |
| P3 / LPEU | Partial Engulf Up | 41.0% | 80.8% | 65.5% | 47.6% | 1.2% | **Bullish** |
| P4 / LPED | Partial Engulf Down | 30.2% | 68.6% | 75.0% | 44.6% | 1.0% | **Bearish** |

## 5. First-Break Edge Rules

| Pattern | If high breaks first | If low breaks first |
|---------|----------------------|---------------------|
| P1 / LEA | 42.8% low follows | 42.6% high follows |
| P2 / AEL | 52.7% low follows | **59.8% high follows** (bullish tell) |
| P3 / LPEU | 46.4% low follows | 51.2% high (↓29.6pp — edge lost) |
| P4 / LPED | 46.2% low (↓28.8pp — edge lost) | 44.1% high follows |

## 6. Asia/London Broken Status (Volatility Regime)

> **Source**: Local 20-year study (n=4,640 sessions, Jan 2026)
> **File**: `docs/nqstats/aln_sessions/ALN_PROFILER_ANALYSIS.md`

The ALN pattern gives directional bias; the **Held/Broken** status gives volatility regime. The `broken` flag indicates whether a session's range was broken by the next session.

| Asia Range | London Range | Days | Freq | NY1 Long | NY1 Short | NY1 Broken | Interpretation |
|------------|-------------|------|------|----------|-----------|------------|----------------|
| **Held** | **Held** | 300 | ~6% | **30.7%** | 22.0% | **25.7%** | 📈 **Best**: Low volatility, long bias, tight stops viable |
| Broken | **Held** | 624 | ~13% | **27.2%** | 22.9% | 34.0% | Good: Moderate vol, long bias. London holding after Asia breaks = consolidation → NY can trend |
| Held | Broken | 512 | ~11% | 18.2% | 13.1% | 48.0% | Neutral: High vol, no directional edge |
| **Broken** | **Broken** | 3,169 | ~68% | 13.7% | 15.2% | **51.3%** | ⚡ **Worst**: High vol, chop, no edge. Reduce size or avoid |

### Key Insights

1. **"Both Held" = Gold Standard** — Only ~6% of days, but when it happens: 31% long bias (vs ~17% baseline) and only 26% NY broken (very low volatility). Strong long bias, tight stops viable.

2. **"Both Broken" = Avoid or Size Down** — Most common (68% of days). NY is 51% broken = high volatility, whipsaw. No directional edge (~14% long vs 15% short).

3. **"Asia Broken + London Held" = Good Setup** — Second best: 27% long, 34% NY broken. London holding after Asia breaks = consolidation, NY can trend.

### Trading Workflow (8:00 AM ET)

1. **Classify ALN Pattern** → directional bias (LPEU bullish, LPED bearish, LEA/AEL neutral)
2. **Check Asia/London Broken Status** → volatility regime
3. **Combine**:
   - LPEU + Both Held → **High-conviction long**, normal sizing, tight stops
   - LPEU + Both Broken → Bullish direction but expect chop, reduce size
   - LPED + Both Held → **High-conviction short**, normal sizing, tight stops
   - LPED + Both Broken → Bearish direction but expect chop, reduce size
   - LEA/AEL + Both Broken → **Avoid** — no edge, high vol

## 7. RTH Breaks (Prior Day Range Open Scenarios)

> **Source**: [NQStats — RTH Breaks](https://nqstats.com/rth_breaks.html)
> **Study**: 10-year, 2016–2026, n = 2,488 RTH sessions (NQ futures)
> **RTH Window**: 09:30–16:00 ET
> **Breach Definition**: Any bar whose high or low extends > 1 tick (0.25 pts) beyond the prior day RTH (pRTH) level

Each session is classified by where the **09:30 open** falls relative to the **prior day's RTH range** (pRTH high and low). Probabilities track: (a) how often the session closes above/below the breached level, and (b) how often price reaches — via wick — the opposite extreme.

### Opening Scenario Distribution

| Scenario | Sessions | Frequency | Description |
|----------|----------|-----------|-------------|
| **Gap Up** (opens above pRTH High) | 654 | 26.3% | RTH open > prior day RTH high |
| **Gap Down** (opens below pRTH Low) | 363 | 14.6% | RTH open < prior day RTH low |
| **Inside Range** (opens within pRTH) | 1,471 | 59.1% | pRTH low < RTH open < pRTH high |

### Scenario 1 — Gap Up (opens above pRTH High)

| | |
|---|---|
| **Sessions** | 654 (26.3%) |
| **Close above pRTH High** (holds gap, bullish close) | **69.9%** (457 days) |
| **Close below pRTH High** (gap fills, closes back inside) | 30.1% (197 days) |
| **Does not breach pRTH Low** (no wick > 1 tick below pRTH low) | 88.1% (576 days) |
| **Trade guidance** | Bullish continuation bias — 70% chance gap holds. Don't fade the gap unless price reclaims pRTH High. Only 12% chance of reaching pRTH Low. |

### Scenario 2 — Gap Down (opens below pRTH Low)

| | |
|---|---|
| **Sessions** | 363 (14.6%) |
| **Close below pRTH Low** (holds gap down, continuation) | **59.5%** (216 days) |
| **Close above pRTH Low** (gap fills, closes back inside) | 40.5% (147 days) |
| **Does not breach pRTH High** (no wick > 1 tick above pRTH high) | 90.4% (328 days) |
| **Trade guidance** | Bearish continuation bias — 60% chance gap holds. Don't fade the gap unless price reclaims pRTH Low. Only 10% chance of reaching pRTH High. |

### Scenario 3 — Inside Range (opens within pRTH)

| | |
|---|---|
| **Sessions** | 1,471 (59.1%) — **most common scenario** |
| **No breach either side** (stays entirely within pRTH range) | 17.7% (261 days) |
| **Breaches one side only** (high OR low > 1 tick beyond pRTH) | **74.0%** (1,088 days) |
| **Breaches both sides** (high AND low > 1 tick beyond pRTH) | 8.3% (122 days) |
| **Trade guidance** | Most days break at least one side. If ALN pattern is bullish (LPEU) and open is inside range, expect pRTH High to be tested. If ALN is bearish (LPED), expect pRTH Low to be tested. 18% chance of a true range day (no breach) — low-vol consolidation. |

### RTH Breaks + ALN Integration

| ALN Pattern | RTH Open Scenario | Combined Read |
|-------------|-------------------|---------------|
| LPEU (bullish) | Gap Up | **High-conviction long** — ALN bullish + gap holds 70%. Strong continuation. |
| LPEU (bullish) | Inside Range | **Bullish** — expect pRTH High to be breached (74% one-side break). Target pRTH High. |
| LPEU (bullish) | Gap Down | **Caution** — ALN says bullish but price gapped below prior low. Wait for reclaim of pRTH Low before longs. |
| LPED (bearish) | Gap Down | **High-conviction short** — ALN bearish + gap holds 60%. Strong continuation. |
| LPED (bearish) | Inside Range | **Bearish** — expect pRTH Low to be breached (74% one-side break). Target pRTH Low. |
| LPED (bearish) | Gap Up | **Caution** — ALN says bearish but price gapped above prior high. Wait for rejection below pRTH High before shorts. |
| LEA / AEL | Any | Use RTH scenario to resolve direction. Gap Up → lean long (70% hold). Gap Down → lean short (60% hold). Inside → wait for first breach. |

## 8. Implementation Reference
This specification is implemented in the following library modules:
- Logic: `scripts/libs_py/nqstats/sessions.py`
- Classifiers: `scripts/libs_py/nqstats/classifiers.py`
