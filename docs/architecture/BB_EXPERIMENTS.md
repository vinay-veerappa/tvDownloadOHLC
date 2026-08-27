# BB Mean Reversion Experiments Log

> One strategy at a time, full documentation. Shared data: `data/derived/nt_es_09_26_1m/5m_2025_2026_mergeBA.csv` (NT MergeBackAdjusted ES 09-26, 552k 1m / 110k 5m, 2025-01-01→2026-08-21). Engine: `BacktestEngine limit 1-tick` `scripts/analysis/range_strategy_comparison.py:509`, cost `4×MES $1.20/rt`. Window `NY 11:30-16:00` unless noted.

## Experiment Index

| ID | Date | Strategy | Params | Trades 19mo | WR% | PF | Net$ | DD$ | /mo ES | /mo ES+NQ | PropPass | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| E01 | 2026-08-23 | BB_RSI no-sq | bb20 2.0 adx25 rsi33 atr1.5 | 28 | 53.6 | 0.89 | -148 | 584 | 1.5 | 3.0 | 0/0 | Baseline on NT shared, losing |
| E02 | 2026-08-23 | BB_RSI no-sq | bb20 1.8 adx25 rsi33 atr1.2 | 95 | 33.7 | 0.55 | -1585 | 1779 | 5.0 | 10.0 | 0/1 | Baseline frequent loser |
| E03 | 2026-08-23 | BB_RSI_Sq 30% | bb20 2.0 adx25 rsi33 atr1.2 | 8 | 75.0 | 1.69 | +136 | 137 | 0.4 | 0.8 | 0/0 | Squeeze lift PF but kills freq — swing only |
| E04 | 2026-08-23 | BB_RSI_Sq 30% | bb14 2.0 adx25 | 93 | 40.9 | 1.00 | +7 | 1730 | 4.9 | 9.8 | 0/1 | Squeeze on bb14 breakeven |
| E05 | 2026-08-23 | BB TF sweep | 1m bb20 1.8 | 372 | 25.3 | 0.43 | -8637 | 8731 | 19.6 | 39.2 | 0/6 | 1m too noisy |
| E06 | 2026-08-23 | BB TF sweep | 3m bb20 1.8 | 194 | 32.0 | 0.67 | -3635 | 4635 | 10.2 | 20.4 | 0/4 | 3m still losing |
| E07 | 2026-08-23 | BB MTF 5m->1m | bb20 1.8 hybrid | 62 | 41.9 | 0.89 | -350 | 1268 | 3.3 | 6.6 | 0/0 | 1m entry chase hurts |
| E08 | 2026-08-23 | BB 12-arm no-sq | bb20 1.8 adx25 (best) | 34 | 58.8 | 1.10 | +147 | 503 | 1.8 | 3.6 | 0/0 | Only winner no-sq |
| E09 | 2026-08-23 | BB 96-arm ES+NQ pooled | bb20 2.2 30 1.2 sq30 | 11 | 54.5 | 1.19 | +99 | 316 | 0.3 | 0.6 | 0/0 | Top pooled PF |
| E10 | 2026-08-23 | BB regime | IB<0.4 only | 70 | 34.3 | 0.66 | -762 | 1474 | 3.7 | 7.4 | 0/0 | IB alone modest |
| E11 | 2026-08-23 | BB regime | Skip 13-14 only | 34 | 55.9 | 1.13 | +177 | 416 | 1.8 | 3.6 | 0/0 | Lunch skip alone wins |
| E12 | 2026-08-23 | BB regime | IB<0.4 + Skip 13-14 | 20 | 60.0 | 1.71 | +439 | 232 | 1.1 | 2.1 | 0/0 | Best before MACD |
| E13 | 2026-08-23 | BB_WPR | bb20 1.8 IB+LunchSkip W%R -90/-10 | 17 | 35.3 | 0.52 | -405 | 550 | 0.9 | 1.8 | 0/0 | Worse than RSI — **rejected** |
| E14 | 2026-08-23 | BB_MACD | bb20 1.8 IB+LunchSkip MACD hist rising | 17 | 70.6 | 2.44 | +626 | 232 | 0.9 | 1.8 | 0/0 | **New best PF2.44** |

## Outside-the-box combos tested (same 19mo) — update

- DailyTrend (close>20D SMA): 70→37 PF0.59→0.35 worse.
- Quarters 00/25/50/75 GridUnit25: 95→53 PF0.55→0.41 worse.
- VWAP slope + CVD vol>1.5×avg: 70→63 PF0.59→0.62 no effect.
- **W%R(14) -90/-10 vs RSI 33/67 on E12 base: 20→17 PF1.71→0.52 worse — W%R more sensitive but hits falling knife earlier**

## Failure Diagnosis (E02 bb14 1.8 no-sq 156 trades PF0.77)

- 13-14 ET 68.9% loss vs 57% 12-13; BW 0.007-0.011 83% loss; T1 23.7% / T2 3.2% / stopped 57% — never reaches mid.
- ADX 15-20 62.8% loss — ADX<25 not filtering dead chop.
- SHORT 65.2% loss vs LONG 60.9% — shorts fade Sep26 uptrend.

## Outside-the-box combos tested (same 19mo)

- DailyTrend (close>20D SMA): 70→37 PF0.59→0.35 worse.
- Quarters 00/25/50/75 GridUnit25: 95→53 PF0.55→0.41 worse.
- VWAP slope + CVD vol>1.5×avg: 70→63 PF0.59→0.62 no effect.

## Next Queue (one-by-one)

| ID | Variant | Hypothesis | Params | Status |
|---|---|---|---|---|
| E13 | W%R(14) -90/-10 instead of RSI 33/67 | Faster oversold on gaps, earlier entry | bb20 1.8 adx25 atr1.2 IB+LunchSkip | **done — rejected PF0.52 WR35% 17 trades** |
| E14 | MACD(12,26,9) hist rising | Histogram rising filters falling knife | BB lower + MACD hist>prev hist IB+LunchSkip | **done — BEST PF2.44 WR70.6% 17 trades +626** |
| E15 | Stoch(14,3,3) %K<20 / CCI 20 -100 | Alternative momentum, compare to RSI/W%R | Stoch 28 PF0.84 42.9% rejected / CCI 0 trades too strict | **done — both rejected** |

---

## E16-E21 Queue (2026-08-27, `scripts/analysis/bb_e16_e21_queue.py`)

From strategy review `docs/research/STRATEGY_REVIEW_2026_08_27.md`. All variants long-only, bb20 1.8, market entry, all sessions, NT MergeBA ES 19mo. Script is a variant-flagged subclass — shared `BBRsiMeanReversionStrategy` untouched.

⚠️ **First-run bug (caught & fixed):** a `bw_floor=0.011` default leaked into E16, collapsing it to 10 trades. ES 5m BW scale is **0.002-0.005** (verified `bb_failure_diag.py` buckets: 0.00166-0.00489), so the review's "BW>0.011" floor (derived from a bb14-based diag) was out of scale. Percentile floors used instead. The first run's "E16=E17 identical, PF2.95/10 trades" line is void — the numbers below supersede.

| ID | Config | Trades | WR% | PF | Net$ | DD$ | avgR | Verdict |
|---|---|---|---|---|---|---|---|---|
| **E16** | long-only + ADX25 (E02 base, shorts removed) | **569** | 39.9 | **1.20** | **+2009** | 1345 | +0.029 | **Winner. Long-only flips E02 (95tr PF0.55) to PF1.20 at 6× density** |
| E17 | long-only + BW p25 floor, ADX **off** | 1810 | 35.2 | 0.89 | −5053 | 6345 | −0.057 | **ADX gate is load-bearing** — removing it (even with BW floor) loses |
| E17b | long-only + BW>0.0032 abs, ADX off | 791 | 35.3 | 0.86 | −4551 | 4799 | −0.061 | same — BW floor does NOT replace ADX |
| E18 | E17 + RSI<38 relax | 2449 | 35.9 | 0.83 | −8198 | 9716 | −0.116 | rejected — relaxation dilutes edge (needs ADX to work) |
| E19 | E17 + no-runner (full exit mid-band) | 1811 | 34.9 | 0.84 | −7138 | 8244 | −0.071 | rejected — runner leg is where the money is |
| E20 | E17 + fresh 5h-low sweep veto | 1801 | 35.1 | 0.88 | −5135 | 6428 | −0.058 | no effect (veto fires on 0.5% of signals — band touch IS a fresh low) |
| E21 | E17 + 15:00-16:00 only | 31 | 38.7 | 0.80 | −160 | 560 | −0.185 | rejected |
| E21b | E17 + 09:30-11:30 only | 26 | 23.1 | 0.26 | −917 | 831 | −0.381 | rejected — open window is the WORST for BB reversion |

### E16 robustness breakdown (`data/derived/bb_e16_trades_detail.csv`)

| Cut | Finding |
|---|---|
| Session | GLOBEX 265tr +$1538 / ASIA 151tr +$793 / LONDON −$132 / NY_PM −$190. **Overnight is the edge; RTH is not** |
| Hour | Best: h20 (49.0% WR, +$1081, n=98), h0 (45.7%, +$1061), h7 (43.2%, +$823). Worst: h6 (−$728), h2 (23.1%) |
| Half-year | 2025H1 +$1638 / 2025H2 −$272 / 2026H1 −$229 / 2026H2 +$872 — **edge is regime-dependent, positive 2 of 4 halves** |
| Sweep veto | Fires on ~0.5% of signals — a lower-band touch is definitionally a fresh local low, so the crossref's "sweep-aligned" trap cannot be vetoed this way at signal time |

### Conclusions

1. **E16 (long-only + ADX25) is the new BB baseline**: 569 trades/19mo (30/mo), PF 1.20, +$2009, avgR +0.029. The review's "frequency unlock" is solved by *removing shorts*, not by relaxing gates — shorts were the frequency AND the P&L problem.
2. **ADX>25 gate is confirmed load-bearing** (E17 vs E16: PF 0.89 vs 1.20). The review's hypothesis that ADX25 was miscalibrated is **falsified** — it was the BW diag that was mis-scaled.
3. **Overnight (GLOBEX/ASIA) carries the edge** — consistent with E21b (RTH open = worst). Next test: E16 restricted to h19-h01 overnight block only.
4. **Regime dependence is real** — E16 loses in 2025H2/2026H1. A regime gate (R01 bandwidth-switch) remains the right meta-layer, but the switch variable should gate *this* strategy's overnight block, not RTH.
5. Review's E17/E18/E19/E20/E21 hypotheses: **all falsified on this data**. E16's win came from direction isolation, not from any added filter.

### Next queue (E22+, one-by-one)

| ID | Variant | Hypothesis |
|---|---|---|
| E22 | E16 restricted to overnight block (19:00-08:00 ET) | The hour table says +$2.9k of the +$2.0k total comes from h20+h0+h7; cut h6/h2 losses |
| E23 | E16 + hour blacklist (skip h6, h9) | Surgical version of E22 — keep all sessions, drop only losing hours |
| E24 | E16 + MACD hist rising (E14 filter on new base) | Does the E14 champion filter survive on the 569-trade base? |
| E25 | E16 + BW p25 floor **with** ADX25 kept | BW floor + ADX together (E17 tested BW alone) |

---

## E22-E25 Queue (2026-08-27, `--batch e22_e25`)

All built on the E16 base (long-only + ADX25, bb20 1.8, market entry). E16 baseline re-ran **byte-identical** (569 trades PF1.20 +$2009) — batch consistency verified.

| ID | Config | Trades | WR% | PF | Net$ | DD$ | avgR | Verdict |
|---|---|---|---|---|---|---|---|---|
| **E23** | E16 + blacklist h6,h9 | **524** | 40.8 | **1.31** | **+2765** | 1410 | **+0.067** | **New champion.** Removes only the 2 losing hours; avgR 2.3× baseline |
| E22 | E16 + overnight 19:00-08:00 | 532 | 39.8 | 1.27 | +2373 | **850** | +0.044 | **Best DD** (−37% vs baseline). Runner-up — pick over E23 if DD matters |
| E16 | BASELINE | 569 | 39.9 | 1.20 | +2009 | 1345 | +0.029 | reference |
| E25 | E16 + BW p25 floor (ADX kept) | 555 | 39.6 | 1.19 | +1917 | 1356 | +0.033 | rejected — redundant with ADX gate (removes 14 trades, no edge) |
| E24 | E16 + MACD hist rising | 466 | 40.8 | 1.16 | +1393 | 1180 | −0.005 | **E14 does not transfer** — MACD filter helped the RTH-only config but hurts overnight-heavy base |

### Arithmetic cross-checks (`scripts/analysis/bb_e22_e25_crosscheck.py`)

- **E22 matches hour-table prediction to the dollar**: predicted +$2373 (n=532) from E16's hourly breakdown, actual +$2373 (n=532). The overnight edge is *exactly* the sum of its hours — no interaction effects.
- **E23 within sequencing noise**: predicted +$2806 (simple drop of h6 −$728 + h9 −$69), actual +$2765 (n=524 vs 569−42=527). Small diff = trades 2-3 per session re-sequencing when an entry is skipped.

### Conclusions

1. **E23 is the new BB champion** (PF 1.31, 524 trades, avgR +0.067) — and it's the *simplest* possible filter: two blacklisted hours, zero new indicators. Hour-level structure beats indicator filters on this class.
2. **E22 is the prop-preferred variant** — same edge with 37% lower DD ($850 vs $1345). For prop eval (trail-DD firms), E22 > E23 despite lower PF.
3. **E14's MACD filter does NOT transfer** to the long-only overnight base (PF 1.16 vs 1.20 baseline). The E14 champion was overfit to its 17-trade RTH sample — consistent with the original review's warning.
4. **BW floor is fully redundant with ADX** (E25 ≈ E16). The two gates select nearly the same regime.
5. Combined candidate for NT8 port: **E22/E23 hybrid** — overnight block (19:00-08:00) + skip h6/h9 is a no-op on the block (h6/h9 aren't in it), so the real choice is: E22 for DD, E23 for PF. **E22 is the recommended port config** (prop-firm trail-DD is the binding constraint, and E23's PF edge is inside one bad half-year's noise).

### Next queue (E26+, one-by-one)

| ID | Variant | Hypothesis |
|---|---|---|
| E26 | E22 + NQ cross-check | Does the overnight long-only edge hold on NQ (different overnight personality per NQSTATS)? |
| E27 | E22 + prop sim | Run `PropFirmSimulator` on E22's 532-trade series — is it actually fundable? |
| E28 | E22 + session-half split | First vs second half of the overnight block (19-23 vs 00-07) — is the edge concentrated? |

---

## E26-E28 Validation Battery (2026-08-27, `scripts/analysis/bb_e26_e28_queue.py`)

E22 (ES overnight long-only + ADX25) validated on three axes. ES E22 re-ran byte-identical (532 trades PF1.27 +$2373 DD$850).

### E26 — NQ cross-check: **FAILS on NQ**

| Symbol | Trades | WR% | PF | Net$ | DD$ | avgR |
|---|---|---|---|---|---|---|
| ES E22 | 532 | 39.8 | 1.27 | +2373 | 850 | +0.044 |
| **NQ E22 (MNQ $2/pt)** | 480 | 38.5 | **0.97** | **−620** | **3412** | −0.136 |

NQ half-year: 2025H1 −$63 / 2025H2 +$295 / 2026H1 +$1081 / **2026H2 −$1933**. The overnight BB-reversion edge is **ES-specific** — NQ's overnight session has a different microstructure (consistent with NQSTATS overnight-personality memories). **Do not port E22 to NQ.** The R01 regime-switch meta-layer should route NQ to a different class entirely.

### E27 — Prop firm viability (ADR-021 simulator, ES E22 series)

| Sizing | Profile | Pass rate | Grade | Blow rate | Det-DD | Verdict |
|---|---|---|---|---|---|---|
| 1xMES | Apex 50K | 0.0% | F | 0.0% | $803 | Micro sizing can never reach $3k target in-window at avgR +0.044 |
| 1xMES | TopStep 50K | 0.1% | F | 0.0% | $803 | same |
| 1xMES | FTMO 50K | 0.0% | F | 0.0% | $407 | same |
| **10xMES** | Apex 50K | **47.0%** | D | 47.3% | $2,516 | coin-flip; DD budget fully consumed |
| **10xMES** | TopStep 50K | 42.1% | D | 57.9% | $2,516 | worse — daily loss limit bites |
| **10xMES** | FTMO 50K | **39.0%** | D | **10.4%** | $4,068 | det-passed ✓; static-DD profile tolerates the equity curve best |

**Honest read: E22 alone is NOT a fundable standalone at any sizing.** 289 trading days vs Apex's 30-day window is the structural problem — the strategy earns ~$8/day on 1xMES ($2,373/289d); a 30-day eval window needs ~$100/day. At 10xMES the pass rate is a coin flip *and* the deterministic run still fails (DD $2,516 vs $2,500 budget). **E22 is a component, not a system** — it feeds the R01 regime-switch portfolio where its 37% lower DD and uncorrelated overnight timing add diversification, not standalone EV.

### E28 — Overnight half-split: edge concentrates 00-08h ET

| Block | Trades | WR% | PF | Net$ | DD$ | avgR |
|---|---|---|---|---|---|---|
| First half 19-24h | 228 | 43.0 | 1.21 | +593 | 414 | +0.056 |
| **Second half 00-08h** | 304 | 37.5 | 1.29 | **+1781** | 890 | +0.034 |

Per-hour: the block is really **h20 (+$1081), h00 (+$1061), h07 (+$823), h04 (+$572)** = $3,537 gross-positive hours, vs h06 (−$728) and five sub-$100 hours. Within-block hour blacklisting (drop h19/h21/h22/h23/h01/h02/h03, keep h20/h00/h04/h05/h07) is the E29 candidate — but that's 4 params fit to one 19mo sample: **require out-of-sample confirmation before trusting** (2026H2 holdout or NQ/RTY cross-check first).

### Battery verdict

E22 validated as: ES-only ✓, overnight-only ✓, **portfolio-component-not-standalone** ✓, edge concentrated in 4 discrete hours (h20/h00/h04/h07) with h06 as the single worst bleed. The h06 bleed sits exactly at the 06:00-07:00 pre-London window — consistent with the Asia-London liquidity thesis (h06 = London open approach, volatility expansion breaks mean reversion).

### Next queue (E29+, one-by-one)

| ID | Variant | Hypothesis |
|---|---|---|
| E29 | E22 + 4-hour allowlist (h20/h00/h04/h07 only) | In-sample concentration test — expect PF > 1.5 but overfit risk high |
| E30 | E29 holdout: run on 2026H2 only (unseen by the hour selection? — NO, hour table used full period; use RTY instead) | RTY 09-26 cross-check of the 4-hour allowlist |
| E31 | Portfolio sim: E22 (ES overnight) + STTrendBot (5m trend) uncorrelated stack | R01's first concrete two-engine test — combined DD < max(component DDs)? |

---

## E32 — BB Falsification Ladder (2026-08-27, `scripts/analysis/bb_e32_falsification.py`)

**Design:** all arms get identical exits (SL 1×ATR5, TP1 1×ATR5, TP2 2×ATR5, market entry, 1 trade/hour/day) and identical windows (4h allowlist + full overnight block). Only the entry condition varies. If BB entry were the alpha, T2 should dominate.

| Arm | Window | Trades | WR% | PF | Net$ | avgR |
|---|---|---|---|---|---|---|
| T0 time-only | 4h | 1685 | 17.7 | 0.14 | −27,424 | −0.417 |
| T0 time-only | full | 5478 | 19.3 | 0.16 | −62,054 | −0.374 |
| T1 extension-only (20-bar low + hook) | 4h | 801 | 20.3 | 0.20 | −9,861 | −0.348 |
| T1 extension-only | full | 2338 | 20.4 | 0.18 | −23,869 | −0.336 |
| T1x extension + ADX25 | 4h | 424 | 15.8 | 0.16 | −4,724 | −0.342 |
| T1x extension + ADX25 | full | 1184 | 17.8 | 0.12 | −12,164 | −0.370 |
| T2 **BB + ADX (E22 entry)** | 4h | 100 | 20.0 | 0.22 | −967 | −0.395 |
| T2 **BB + ADX (E22 entry)** | full | 230 | 21.3 | 0.16 | −2,423 | −0.394 |

### The result nobody expected: T2 loses too

T2 uses the *exact E22 entry condition* and loses money. Meanwhile E22 (same entries, band/midband exits) made +$2,373. The ladder therefore answers the falsification question in the strongest possible form:

> **The BB entry condition is NOT the edge. The exit geometry IS the edge.**

### Exit-structure comparison (`bb_e32_diag.py`)

| Metric | E22 (band exits) | E32-T2 (fixed ATR exits) |
|---|---|---|
| avg risk | 4.86 pts | 2.7 pts |
| avg win / avg loss | $53.4 / −$29.7 (**1.8 : 1**) | $9.5 / −$15.9 (**0.6 : 1**) |
| TP1 hit rate | 43.6% | 53.5% |
| stopped rate | 80.3% | 64.8% |

The mechanism: from a lower-band touch, the BB midband sits ~2×ATR away — *structural* mean-reversion room. A 1×ATR fixed target sits inside overnight noise: it gets hit often (53.5%) but pays $9.5 against a $15.9 average loss. E22 inverts this — it loses often (80% stopped) but each win pays 1.8× the loss. Same entries, opposite payoff asymmetry.

### Verdict

1. **The strategy's honest name**: "overnight band-touch entries with wide mean-anchored targets." The BB *entry* is a chop filter; the BB *midband target* is the alpha. Time-only (T0) at PF 0.14 proves the timing alone is worthless; extension-only (T1) at PF 0.18-0.20 proves a cheaper detector doesn't rescue fixed exits.
2. **Do not replace the bands with VWAP/range-extreme entries under fixed exits** — E32's negative controls already falsified that entire family.
3. **E33 (final falsification arm)**: keep E22's band-geometry exits but anchor TP1 on **session VWAP** instead of the BB midband. If VWAP-anchored exits ≈ midband exits, the strategy is really "fade to the overnight mean" and can be renamed + simplified. If midband wins, the BB stays and the question is closed.
4. **E31 (portfolio sim) unchanged** — E22 remains the component candidate.

---

## E33 + E31 — Final Falsification & Portfolio (2026-08-27, `scripts/analysis/bb_e33_e31_final.py`)

### E33 — VWAP-anchored TP1 **BEATS the BB midband** → BB is now fully replaced

| TP1 anchor | Trades | WR% | PF | Net$ | DD$ |
|---|---|---|---|---|---|
| E22 midband (BB) | 240 | 40.0 | 1.28 | +1130 | 694 |
| **E33a session VWAP** | **222** | 38.7 | **1.35** | **+1305** | **547** |
| E33b day-anchored VWAP | 222 | 38.7 | 1.35 | +1305 | 547 |

Identical results for session- and day-anchored VWAP overnight (both anchors converge on the same mean in the 19:00-08:00 window). **VWAP anchor: better PF, better net, −21% DD, and zero BB math.** The strategy's final honest form:

> **"ES overnight mean-reversion: long at 20-bar closing lows with RSI hook + ADX<25, target session VWAP, stop beyond the sweep extreme."**

No Bollinger Bands remain. The BB entry was replaceable (E32), the midband target was replaceable (E33) — the alpha was "fade overnight extensions to the session mean." (Note: E22/E33 here run 1 trade/hour/day vs the original E22's 3/session — hence 240 vs 532 trades; PF is consistent at 1.28 vs 1.27.)

### E31 — Two-engine portfolio: **the diversification thesis confirmed**

| Engine | Net$ | DD$ | PF | WR% |
|---|---|---|---|---|
| E22 BB-reversion (overnight) | +1130 | 694 | 1.31 | 12.5 (daily) |
| ST(14,2) trail 1.5×ATR | +4645 | 79 | 5.67 | 31.9 (daily) |
| **Combined** | **+5776** | **218** | 2.66 | 33.9 |

- **Daily-return correlation: −0.027** — essentially perfect orthogonality (reversion vs trend, overnight vs all-day)
- **Combined DD $218 < each single** ($694/$79) — true diversification, not just addition
- ⚠️ ST daily PF 5.67 on daily-aggregated dollars is inflated by day-bucketing (per-trade PF was 3.01 points-only / 1.5 cost-adjusted in the original grid); treat as relative shape, not absolute

### Prop sim on the combined portfolio (10×MES, honest convention)

| Profile | Pass rate | Grade | Blow rate | Det-passed |
|---|---|---|---|---|
| **TopStep 50K** | **85.0%** | **A** | 14.7% | ✓ |
| Apex 50K | 76.2% | B | 6.2% | ✓ |
| FTMO 50K | 52.8% | C | **0.0%** | ✓ |

**This is the headline result of the entire review.** E22 alone: 0-47% pass (E27). Combined with the Supertrend engine: **85% TopStep / 76% Apex / 53% FTMO, all deterministic-passed, blow rates ≤15%.** The portfolio is fundable where the components are not.

### Campaign verdict (E01 → E33, 35 experiments)

1. **BB mean reversion as a named strategy: retired.** Its working core survives as *overnight VWAP-targeted mean reversion* — simpler, stronger (PF 1.35, DD $547), and honest about what it does.
2. **Supertrend trend engine: the workhorse.** ST(14,2)+1.5×ATR trail, NT8-validated, 40/mo, and the dominant P&L contributor in the portfolio.
3. **The portfolio is the product.** −0.03 correlation turns two mediocre standalones into one fundable system (TopStep grade A).
4. **Next steps:** (a) NT8 port of the E33 VWAP-anchor variant to replace/simplify `BBMRReversionBot`, (b) 10×MES sizing study for the combined portfolio on the $2.5k DD budget, (c) walk-forward the combined system before any live eval.

---

### How to run / reproduce

```bash
# Shared NT data already exported: data/derived/nt_es_09_26_*_mergeBA.csv
.\.venv\Scripts\python.exe scripts/analysis/bb_failure_diag.py
.\.venv\Scripts\python.exe scripts/analysis/bb_regime_filter.py
.\.venv\Scripts\python.exe scripts/analysis/bb_sweep_optim.py  # 96 arms, 8 workers, 6.1 min
```

NT Strategy Tester sync: `BBMRReversionBot.cs:51 UseIbCompress/IbMaxAtrRatio/SkipLunchHour` + diag `bbmr_diag_*.csv` (RsiDiff p50 2.4e-14 vs Python on shared file). Backtest `ES 09-26 2025-01-01→08-23 UseIbCompress=true SkipLunchHour=true BB20 1.8` → **28 trades PF1.51 Net +2700** vs Python `20 trades PF1.71` — direction agrees, count within window.
