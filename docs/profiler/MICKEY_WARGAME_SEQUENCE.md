# Mickey's Complete Morning Wargaming Sequence — Canonical Reference

> **Source**: NotebookLM `Pack Trading - Live Wargaming YouTube Transcripts` (68 sources), distilled 2026-09-01.
> **Purpose**: The definitive ordered checklist of everything Mickey runs in his daily wargaming ritual (05:30–08:30 ET), with every rule and probability. Read this before touching any wargame component — do not re-query the transcripts for rules already recorded here.
> **Companion docs**: [`docs/profiler/mickey_session_turn_windows.md`](mickey_session_turn_windows.md) (Dynamic session gating & turn windows) · [`docs/features/htf_ema_analysis/BLUEPRINT.md`](../features/htf_ema_analysis/BLUEPRINT.md) (weekly EMA deep-dive) · [`docs/profiler/mickey_austin_tool_inventory.md`](mickey_austin_tool_inventory.md) (tool inventory) · [`docs/profiler/master_rule_catalog.json`](master_rule_catalog.json) (streak/regime numbers)

## The Three Wargaming Questions

Mickey frames wargaming as deductive reasoning / process of elimination, answering exactly three things before the open:

1. Is the daily candle going to be **green or red**?
2. Is it going to be a **normal, big, or small** candle?
3. Did **overnight put in the HOD or LOD**, or is an extreme still coming in the morning session?

> *"Our job is to solve three things as an intraday trader: Is the daily candle going to be green or red? Is it going to be normal, big, or a small candle? And is the likelihood that overnight put the high of the day in or the low of the day, or is one extreme coming in the morning session?"*

**Never predicts day types**: R1/R2/DWP/DNP are EOD (16:00) diagnostic classifications. Pre-market output is If-Then scenario branches only.

---

## Step 1 — Macro & Monthly Regime (Gatekeepers)

### 1.1 NFP Friday Close + Previous Month 50%
- **Above both** → **70% green / 30% red** daily candles (statistic since 1956 SPX / 1962–63). Intraday signature: low of day locks early (18:00–19:00, 03:00–04:00, or 09:30–10:30), close finishes high into the afternoon.
- **Below either, or stuck between** → **50/50** green/red coin flip with sharp snapbacks. Below both = quarterly pullback → expect **quarterly lows** (≈ previous month lows; count ~60 days back).
- The first-Friday calendar slot counts as NFP Friday even when the release is skipped.
- **Three pullback tiers**: Monthly Slowdown (above both) → Quarterly Pullback (below both) → Yearly Change of Character (fails to reclaim both within the first week of a new month).

### 1.2 Current Month 30% Line
- 30% of the active monthly range. **Red months** statistically suck back into the range and **close above the 30% mark by days 29–30**; green months close at highs (no edge). Late-month red months below the line → expect short-covering snap toward it.

## Step 2 — Daily Candle Science (3-Candle Lookback, C1→C2→C3)

Source: ~3,773–5,788 NASDAQ daily samples (thedailyprofiler.com). C1 = two days ago, C2 = yesterday, C3 = today.

- **Prev-day high/low takeout**: bullish C2 closing above C1's high → **~81% takes prev-day high** vs 21% low. Two consecutive red closes below C1 low → **58% takes prev-day low** vs 22% high. Inside bar broken sequence → 48/37 = "no real edge."
- **Close-position rule**: C2 close evaluated vs C1 (above high / upper wick / inside body / below low). Close **deep in the wick** = footprint rejection / exhaustion alert.
- **⚠️ Open-Price Flag Flip**: the **previous day's opening price** is the probability pivot — touching it drops the dominant takeout probability by **20–30%** and flips the state to mean-reverting chop.
- **Percentile reversal boxes (MAE/MFB off prev-day high/low)**: **30th pct** = 70% of days extend at least that far; **50th** = 50/50; **70th pct** = 70% of days reverse before it (only 30% push through) — his primary mean-reversion target zone.

## Step 3 — Weekly Time & Range Structure (60-min chart)

- **Monday/Tuesday rule**: bullish week puts in the wick/MAE (low) Mon–Tue; bearish week puts in the high Mon–Tue. Body/opposite extreme (MFB) distributes **Thursday–Friday**.
- **Sunday 18:00–19:30** and **Tuesday 09:30–10:30** ranges are the live lock-in elements. Sunday 18:00 holds as the weekly low in ~10 of 56 weeks (mode).
- **Wednesday median**: 50% of weekly extremes form by **Wednesday 09:00 or 23:00**. Both extremes formed Tue/Wed = **Weekly Doji** → expect Thu/Fri range-bound chop.
- **Weekly 5 EMA ladder**: cumulative hit rates (NQ reference): 0.5% ≈ 86–98%, 1.0% ≈ 76–90%, 1.5% ≈ 75%, 2.0% ≈ 61–69%, 2.0–3.0% = magnet/anomaly transition. **Variance multiplier**: 80%+ levels never missed two weeks in a row (his 56-week sample) — a missed week stacks the target.
- Spent-target state machine: levels attacked from the near side, deleted when touched; all of 0.5/1.0/1.5/2.0 spent = 50/50 coin flip.

## Step 4 — Volatility & Range Outlay (DRO "Checkbook")

- **10-day median range (DRO)** = the baseline budget. Session "checkbooks" measured against rolling **16-week quarterly medians** (NQ handles): Asia ~100–120, London ~200–217, NY1 ~200–292.
- **Overspent Asia + overspent London** → volatility **expanding**: NY1 blows through its own checkbook → targets push into the **70th percentile** red box.
- **Underspent sessions** → volatility **contracting/clustering**: tighten targets, expect range-bound chop.

## Step 5 — Overnight Sessions & Profiler (4,500+ historical days)

- **Session boxes**: Asia (18:00–02:30) classified by its **18:00–19:30** range → Long True / Short True / Long False / Short False / None / Broken. London (02:30–07:30) classified by its **02:30–03:30** range. Early London (01:00–02:30) is the parent range, prone to false moves.
- **Magic Hour (06:00–08:30)**: **75% probability of continuation** once price breaks out of the 06:00–07:00 hourly range.
- **Four generic high/low time buckets**: **18:00–19:00** (Globex open), **03:00–04:00** (London open), **09:30–10:30** (RTH open), **15:00–16:00** (power hour). An extreme formed outside these windows = **out-of-stat** → very high probability of being taken out in RTH.
- **Contradicting markets rule**: Asia Short True + London Long True/False (opposite classifications) → statistically **both HOD and LOD form after the 09:30 RTH open**.
- Both-sides-swept overnight (06:00–08:30) → 99.26% both extremes form after 08:30 (goalpost chop day).

## Step 6 — P12 Analysis (18:00–06:00, first 12h of the daily candle)

- **P12 Mid (50%)** = line in the sand. **80–95% probability of being hit between 06:00 and 10:15 AM.** Live price above → bullish expansion bias; below → bearish.
- **06:00–07:00 early rejection window**: P12-high rejection → 84.52% HOD already locked overnight; P12-low rejection → 81.85% LOD locked; P12-mid rejection → 49.52% one extreme set.
- **Inside-candle rule** (P12 inside prior P12): one side gets wiped, then the mid gets hit *"fast and furious."*
- **Overnight retracement targets** (hit window 08:00–12:00): **Midnight Open 65–88%** (mode 09:30–09:45), **Globex Open 71–85%**, **Settlement gap-fill: Thursday 50% gap fill = 80–94%**.
- **Expiration rule**: P12 Mid / London O/U / Midnight Open not tagged by **10:15–10:30** → probability collapses ("shredded"), day flips to True/trend.

## Step 7 — NY1 Box (07:30–08:30, cutoff 11:30)

- **False (mean reversion) 60–70%**: breakout → tags an overnight level → reverses → takes the opposite side of the box by 11:30.
- **True (trend) 30–40%**: expands directionally, never breaches the opposite side. Continuation filter: 40 bps past the 06:00–09:00 range extreme + failed 4-step reversal.
- **Streak variance**: max False streak ≈ 8 days/quarter (9–10/year). Day 7–8 of a False streak → "True Campaign" alert. Max 3 True days in a row (then expect the False).
- **Outcome-conditional HOD/LOD timing** (Daily Profiler): **Short False** → LOD forms 09:30–10:15/10:30 at 0.3–0.8% off Globex Open, HOD forms in power hour (15:00–16:00). **Short True** → HOD already set in London/pre-market, LOD expands 1.2–2.1%+ into 10:30–12:00 or EOD.

## Step 8 — 09:30 RTH Execution

- **4-Step Reversal (confirms False)**: (1) cross back over the 9:30 open's first 1-min candle H/L; (2) through the 09:00 hour 50% mid; (3) the 10:00 candle takes out the 09:00 extreme; (4) in-stat Q1 extreme (10:00–10:14). Probe at 1/4 size per step; full size only at 4/4.
- **4-Step Continuation (confirms True)**: (1) blows through the standard False-day H/L zone; (2) 40 bps past the 06:00–09:00 extreme; (3) through the 50th pct MFB of the 07:30–08:30 breakout; (4) no reversal signature after 09:30.
- **0-5 Boxes**: first 5 minutes of the 10:00 / 11:00 / 12:00 hourly candles; 10 bps threshold breach = momentum confirmation; failure = instant reversal of that hour's extreme.
- **3-Hour Cloud / Line vs Apex**: rolling 3h candles (06:00–09:00, 09:00–12:00, 12:00–15:00); midline ("line") vs apex confirms multi-hour trend alignment.
- **Cover the Queen**: scale ≥50% at +10 bps, stop to breakeven → risk-free runner. Stop ceiling 12 bps. Runner target +25–30 bps toward HTF structure.

---

## Implementation Coverage Map (tvDownloadOHLC, 2026-09-01)

| Step | Component | Engine | Wired into playbook |
|---|---|---|---|
| 1 | Regime gate + monthly 30% | `htf_ema_analysis.py` v2 | ✅ Section 0 + regime line |
| 2 | C1/C2 takeout probs | candle_science.py (partial) | ⚠️ MFE/MAE boxes only |
| 2 | **Open-price flag flip** | ❌ not built | ❌ |
| 3 | Weekly EMA ladder + variance + spent targets + lock-in | `htf_ema_analysis.py` v2 | ✅ |
| 3 | Mon/Tue + Sun/Tue + Wed doji | `weekly_outlook_engine.py` | ✅ |
| 4 | DRO checkbook | `session_budget_engine.py` | ⚠️ engine exists, verdict not rendered |
| 5 | Asia/London status + broken | profiler engine | ✅ |
| 5 | **Magic Hour 75%** | ❌ | ❌ |
| 5 | **Out-of-stat extreme flag** | ❌ | ❌ |
| 5 | **Contradicting-markets rule** | ❌ | ❌ |
| 6 | P12 mid/bias/levels | `p12_scenario_engine.py` | ✅ (106 refs) |
| 6 | Settlement gap-fill / inside-candle | ❌ | ❌ |
| 7 | NY1 True/False | profiler | ✅ |
| 7 | **True/False streak variance** | rule catalog only | ❌ not computed live |
| 8 | 4-step reversal | playbook Section 6 | ✅ |
| 8 | **4-step continuation** | ❌ | ❌ |
| 8 | 0-5 boxes / 3-hr cloud | ❌ (inventory flags) | ❌ |
| — | Cross-asset Section 0 | `cross_asset_directive.py` | ✅ (added 2026-09-01) |

**Priority build order**: (1) open-price flag flip, (2) True/False streak variance live, (3) DRO checkbook verdict rendered, (4) out-of-stat extreme flag, (5) Magic Hour 75%, (6) 4-step continuation checklist.

---
*Document Location: `docs/profiler/MICKEY_WARGAME_SEQUENCE.md` · Distilled 2026-09-01 from the Live Wargaming transcript notebook; re-verify against NotebookLM before extending.*