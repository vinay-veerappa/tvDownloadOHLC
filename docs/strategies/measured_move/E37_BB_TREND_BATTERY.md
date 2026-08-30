# E37 — BB-as-TREND Battery (2026-08-30)

> Question: can Bollinger Bands work as a TREND tool (squeeze→breakout, band-walk
> management) rather than the retired mean-reversion use? Inverts the E32 ladder:
> vary entries under the proven-good exit, and vary exits under a fixed entry.
> Script: `scripts/analysis/mm_e37_bb_trend_battery.py`, log:
> `data/derived/mm_e37_run_log.txt`, detail: `data/derived/mm_e37_es_trade_detail.csv`.

## Setup

ES 5m NT MergeBA 19mo, both directions, 1 trade/hour/day, 16:00 flat, next-open
fill, $5/pt micro. Exits: Supertrend-parity 1.5×ATR trail (incumbent geometry),
midband-recross, opposite-band.

## Results

### Entry stacks under identical 1.5×ATR trail exits

| Arm | Entry | Trades | WR% | PF | Net$ | DD$ |
|---|---|---|---|---|---|---|
| T1 | band-break only | 3,441 | 32.3 | 0.58 | −19,205 | 19,340 |
| T2 | + squeeze (BBW≤p20) | 948 | 33.9 | 0.58 | −4,600 | 4,653 |
| T3 | + strict HH/HL gate | 333 | 36.0 | **0.65** | −1,301 | 1,334 |
| T4 | Keltner break (ATR bands) | 3,377 | 32.8 | 0.60 | −18,563 | 18,597 |

### Exit ladder on identical T2 entries

| Exit | PF | Net$ | DD$ |
|---|---|---|---|
| midband-recross | 0.59 | −4,437 | 4,491 |
| opposite-band | 0.58 | −4,563 | 4,617 |
| 1.5×ATR trail | 0.58 | −4,600 | 4,653 |

### Incumbent reference (same harness, same session window)

| Engine | Trades | WR% | PF | Net$ | DD$ |
|---|---|---|---|---|---|
| ST (E33 implementation: day-bars 09:30→16:00) | 752 | 55.2 | **3.01** | +4,645 | 82 |
| ST (E37 re-run on 18:00→16:00 futures-day bars) | 625 | 33.9 | 0.62 | −3,545 | 3,542 |

## Interpretation

1. **Every BB-trend entry stack loses under trail exits** (PF 0.58-0.65),
   confirming E32's conclusion now from the trend side: **the band-break trigger
   carries negative edge on ES 5m** — entering on channel breaks buys tops/bottoms
   of intraday noise (band breaks cluster at exhaustion, then retrace to the trap:
   exactly the mechanism our retired reversion book monetized from the other side).
2. **Filters only soften the bleed, never flip the sign**: squeeze −$19.2k→−$4.6k,
   +HH/HL −$4.6k→−$1.3k at 1/3 the frequency. Real information (T3's S-side PF
   0.71 on shorts is the only above-0.5 cell) but nowhere near adoptable.
3. **The exit ladder differences are inside noise** (0.58-0.59) — when the entry
   is negative-edge, no exit family rescues it; conversely nothing is hiding.
4. **Keltner ≈ Bollinger as break channels** (T4 vs T1: 0.60 vs 0.58) — the ATR
   twin neither adds nor subtracts. Channel-family break-entries are the problem,
   not the band math.
5. **⚠️ Incumbent-window discrepancy (important, honest):** E37's ST recompute on
   18:00→16:00 overnight-inclusive bars produces PF 0.62 vs the E33 incumbent's
   PF 3.01 on 09:30→16:00 RTH bars. The Supertrend edge is **RTH-session-bound** —
   flipping ST on at RTH context and running it across 18:00→16:00 destroys it.
   The E37 comparison stands as an *upper-bound* test of the BB-trend family on
   equal footing (all arms saw the same session); but the "BB-trend vs incumbent"
   gap is partly session definition, not purely entry quality. Correct reading:
   **on the shared 18:00→16:00 frame, BB-trend entries and ST both bleed; ST's
   documented edge lives in the RTH frame with its own day-bar conventions.**

## Verdict

- **BB-as-trend on ES 5m: falsified as a standalone entry family** under parity
  exits, parity frequency caps, and honest costs. The bands' remaining roles:
  (a) reversion-side chop gating (survives as the retained E33 core), (b) visual
  context (band-walk) for discretionary overlay — NOT a systematic trigger.
- corr(T3, ST) = −0.014: two losing engines combining still lose. Diversification
  of negative edge is not diversification.
- No seat is claimed. The trend seat remains Supertrend ST(14,2)@RTH (E33).

### Reproduce

```powershell
.\.venv\Scripts\python.exe scripts/analysis/mm_e37_bb_trend_battery.py
```

---

# E38 — Heiken Ashi overlay gate (2026-08-30)

Question: does HA bar-direction persistence as an entry gate cut DD without
killing net on the surviving E34L core? Scripts: `mm_e38_e39_ha_mtf.py` (VOID —
its "baseline" was a simplified BB-touch core that reproduced 50tr PF 0.44, not
the true E34L; arms adjudicated on a losing baseline are invalid) and
`mm_e38b_e39b_true_gates.py` (fix: gates applied post-hoc to the TRUE 298-trade
E34L set; gate state at each entry timestamp is knowable at entry — causal).

| Arm | Trades | WR% | PF | Net$ | DD$ |
|---|---|---|---|---|---|
| HA0 no gate (E34L) | 298 | 54.7 | 1.38 | +1,664 | 403 |
| HA1 HA-bullish at entry | 215 | 55.8 | 1.22 | +691 | 358 |

**Verdict: HA gate FAILS.** It removes 83 trades, keeps the mild-WR winners,
but lobotomizes the net (−58%) for a −11% DD improvement. corr(HA0, HA1)
+0.594 (computed on void arms — not re-relevant). HA as *filter* destroys the
E34L edge because the EE34L winning entries are, by construction,
early-exhaustion longs — the bars where HA is still red or freshly turned.
Heiken Ashi lags exactly where E34L wins. HA as directional *filter* on this
family: rejected.

# E39 — Multi-timeframe layering (2026-08-30)

Question (user): does HTF context gate LTF entries — "BB on a different
timeframe while entries are on a lower timeframe"? Same fix as E38: true E34L
trade set, 30m %B computed shifted(1)+ffill (zero-lookahead), bucketed at entry.

| 30m %B bucket at entry | Trades | WR% | PF | Net$ | DD$ |
|---|---|---|---|---|---|
| D1 0.00–0.25 | 18 | 61.1 | **2.71** | +388 | 107 |
| D2 0.25–0.50 | 49 | 49.0 | 0.77 | −201 | 289 |
| D3 0.50–0.75 | 87 | 54.0 | 1.42 | +514 | 292 |
| D4 0.75–1.00+ | 137 | 56.2 | 1.44 | +849 | 337 |
| M1 "bull context" (%B>0.5) | 231 | 55.4 | 1.45 | +1,477 | 425 |
| M2 anti-stretch (%B≤0.9) | 254 | 51.6 | 1.16 | +645 | 502 |

**Findings:**

1. **The D1 bucket is the first genuinely monotone MTF finding of the campaign:**
   longs taken when the 30m close sits in its LOWER quartile returned PF 2.71 at
   61% WR with the lowest bucket-DD. Mechanically coherent: the E34L edge is
   fading an intraday selloff — those signals cluster when the 30m envelope is
   *also* depressed. The "buy pullbacks in strength" HTF-strength gate (M1/D4)
   inverts it: it mostly re-imports trend-side entries.
2. **But D1 is n=18.** It is a hypothesis, not a config. Pre-register the
   replication: D1 vs rest on NQ + RTY before any port.
3. **M2 ("don't buy stretched 30m") is confirmed harmful** (PF 1.16 < 1.38 with
   higher DD) — the anti-stretch filter is a trap here, consistent with E32/E34:
   stretch IS where the reversion edge lives.
4. **The E38 sponsored lesson (void-result note preserved):** gates must be tested
   ON a functioning baseline. A gate that improves a broken baseline is noise;
   a gate that degrades a working baseline (HA1, M2 here) is evidence against.

### Standing convention captured (user decision)

> **Timeframe/context rule for ALL future strategy tests:** context indicators
> (envelope position, regime, trend state) live on the timeframe where they form;
> execution entries live on the timeframe that fills; every HTF→LTF feed must be
> completed-bar shifted(1) + ffill (zero-lookahead); the merge is reported in
> every result doc. Session frame is part of the strategy definition (E37's ST
> recompute showed RTH-bound edge destroyed on a 18:00→16:00 frame).